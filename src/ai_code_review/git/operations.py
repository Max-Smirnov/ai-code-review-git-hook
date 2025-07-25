"""
Git operations for AI Code Review
"""

import os
import subprocess
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, NamedTuple
from dataclasses import dataclass

from ..utils.exceptions import GitError
from ..utils.logging import get_logger, log_performance

logger = get_logger(__name__)


@dataclass
class GitRef:
    """Represents a git reference being pushed"""
    local_ref: str
    local_sha: str
    remote_ref: str
    remote_sha: str
    
    @property
    def branch_name(self) -> str:
        """Extract branch name from remote ref"""
        if self.remote_ref.startswith('refs/heads/'):
            return self.remote_ref[11:]  # Remove 'refs/heads/'
        return self.remote_ref


@dataclass
class FileChange:
    """Represents a change to a file"""
    filename: str
    status: str  # A=added, M=modified, D=deleted, R=renamed, C=copied
    lines_added: int
    lines_removed: int
    diff: str
    old_filename: Optional[str] = None  # For renamed files


class GitOperations:
    """Handles git operations for code review"""
    
    def __init__(self, repo_path: Optional[Path] = None):
        """
        Initialize git operations
        
        Args:
            repo_path: Path to git repository (defaults to current directory)
        """
        self.repo_path = repo_path or Path.cwd()
        self._validate_git_repo()
    
    def _validate_git_repo(self) -> None:
        """Validate that we're in a git repository"""
        git_dir = self.repo_path / '.git'
        if not git_dir.exists():
            # Check if we're in a git worktree
            try:
                self._run_git_command(['rev-parse', '--git-dir'])
            except GitError:
                raise GitError(f"Not a git repository: {self.repo_path}")
    
    def _run_git_command(self, args: List[str], check_output: bool = True) -> str:
        """
        Run a git command and return output
        
        Args:
            args: Git command arguments
            check_output: Whether to capture and return output
            
        Returns:
            Command output if check_output=True
            
        Raises:
            GitError: If command fails
        """
        cmd = ['git'] + args
        logger.debug(f"Running git command: {' '.join(cmd)}")
        
        try:
            if check_output:
                result = subprocess.run(
                    cmd,
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    check=True
                )
                return result.stdout.strip()
            else:
                subprocess.run(
                    cmd,
                    cwd=self.repo_path,
                    check=True
                )
                return ""
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            raise GitError(f"Git command failed: {error_msg}", command=' '.join(cmd))
        except FileNotFoundError:
            raise GitError("Git command not found. Please ensure git is installed and in PATH.")
    
    def parse_push_refs(self, stdin_input: str) -> List[GitRef]:
        """
        Parse git push refs from stdin
        
        Args:
            stdin_input: Input from git pre-push hook stdin
            
        Returns:
            List of GitRef objects
        """
        refs = []
        
        for line in stdin_input.strip().split('\n'):
            if not line:
                continue
            
            parts = line.split()
            if len(parts) != 4:
                logger.warning(f"Invalid ref line: {line}")
                continue
            
            local_ref, local_sha, remote_ref, remote_sha = parts
            
            # Skip deleted refs
            if local_sha == '0000000000000000000000000000000000000000':
                logger.debug(f"Skipping deleted ref: {remote_ref}")
                continue
            
            refs.append(GitRef(
                local_ref=local_ref,
                local_sha=local_sha,
                remote_ref=remote_ref,
                remote_sha=remote_sha
            ))
        
        return refs
    
    def get_current_branch(self) -> str:
        """Get current branch name"""
        try:
            return self._run_git_command(['branch', '--show-current'])
        except GitError:
            # Fallback for detached HEAD
            return self._run_git_command(['rev-parse', '--short', 'HEAD'])
    
    def branch_exists(self, branch: str, remote: str = None) -> bool:
        """
        Check if a branch exists
        
        Args:
            branch: Branch name
            remote: Remote name (optional)
            
        Returns:
            True if branch exists
        """
        try:
            if remote:
                ref = f"{remote}/{branch}"
                self._run_git_command(['rev-parse', '--verify', ref])
            else:
                self._run_git_command(['rev-parse', '--verify', branch])
            return True
        except GitError:
            return False
    
    def fetch_remote_branch(self, remote: str, branch: str) -> bool:
        """
        Fetch a remote branch
        
        Args:
            remote: Remote name
            branch: Branch name
            
        Returns:
            True if successful
        """
        try:
            self._run_git_command(['fetch', remote, branch], check_output=False)
            logger.debug(f"Fetched {remote}/{branch}")
            return True
        except GitError as e:
            logger.warning(f"Failed to fetch {remote}/{branch}: {e}")
            return False
    
    @log_performance
    def get_diff_with_remote_target(self, git_ref: GitRef, remote: str) -> Dict[str, FileChange]:
        """
        Get diff between local ref and remote target branch
        
        Args:
            git_ref: Git reference being pushed
            remote: Remote name
            
        Returns:
            Dictionary of filename -> FileChange
        """
        remote_branch = git_ref.branch_name
        remote_ref = f"{remote}/{remote_branch}"
        
        # Ensure we have the latest remote state
        self.fetch_remote_branch(remote, remote_branch)
        
        # Check if remote branch exists
        if not self.branch_exists(remote_branch, remote):
            logger.info(f"Remote branch {remote_ref} doesn't exist, comparing with empty tree")
            return self._get_diff_with_empty_tree(git_ref.local_ref)
        
        return self._get_diff_between_refs(git_ref.local_ref, remote_ref)
    
    @log_performance
    def get_diff_with_specified_branch(self, local_ref: str, compare_branch: str, remote: str) -> Dict[str, FileChange]:
        """
        Get diff between local ref and specified branch
        
        Args:
            local_ref: Local reference
            compare_branch: Branch to compare with
            remote: Remote name
            
        Returns:
            Dictionary of filename -> FileChange
        """
        remote_ref = f"{remote}/{compare_branch}"
        
        # Try to fetch the compare branch
        if not self.fetch_remote_branch(remote, compare_branch):
            # If fetch fails, try local branch
            if self.branch_exists(compare_branch):
                remote_ref = compare_branch
                logger.info(f"Using local branch {compare_branch} for comparison")
            else:
                logger.warning(f"Branch {compare_branch} not found, using HEAD")
                remote_ref = "HEAD"
        
        return self._get_diff_between_refs(local_ref, remote_ref)
    
    def _get_diff_with_empty_tree(self, local_ref: str) -> Dict[str, FileChange]:
        """Get diff with empty tree (for new branches)"""
        empty_tree = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"  # Git's empty tree hash
        return self._get_diff_between_refs(local_ref, empty_tree)
    
    def _get_diff_between_refs(self, local_ref: str, remote_ref: str) -> Dict[str, FileChange]:
        """
        Get diff between two git references
        
        Args:
            local_ref: Local reference
            remote_ref: Remote reference
            
        Returns:
            Dictionary of filename -> FileChange
        """
        logger.debug(f"Getting diff between {remote_ref} and {local_ref}")
        
        # Get list of changed files with status
        try:
            name_status = self._run_git_command([
                'diff', '--name-status', f"{remote_ref}..{local_ref}"
            ])
        except GitError as e:
            logger.error(f"Failed to get diff name-status: {e}")
            return {}
        
        changes = {}
        
        for line in name_status.split('\n'):
            if not line.strip():
                continue
            
            parts = line.split('\t')
            if len(parts) < 2:
                continue
            
            status = parts[0]
            filename = parts[1]
            old_filename = None
            
            # Handle renamed files
            if status.startswith('R') and len(parts) >= 3:
                old_filename = filename
                filename = parts[2]
            
            # Get detailed diff for this file
            try:
                file_diff = self._get_file_diff(remote_ref, local_ref, filename, old_filename)
                lines_added, lines_removed = self._count_diff_lines(file_diff)
                
                changes[filename] = FileChange(
                    filename=filename,
                    status=status[0],  # Take first character (A, M, D, R, C)
                    lines_added=lines_added,
                    lines_removed=lines_removed,
                    diff=file_diff,
                    old_filename=old_filename
                )
                
            except GitError as e:
                logger.warning(f"Failed to get diff for {filename}: {e}")
                continue
        
        logger.info(f"Found {len(changes)} changed files")
        return changes
    
    def _get_file_diff(self, remote_ref: str, local_ref: str, filename: str, old_filename: str = None) -> str:
        """Get diff for a specific file"""
        if old_filename:
            # Handle renamed files
            diff_args = ['diff', f"{remote_ref}..{local_ref}", '--', old_filename, filename]
        else:
            diff_args = ['diff', f"{remote_ref}..{local_ref}", '--', filename]
        
        return self._run_git_command(diff_args)
    
    def _count_diff_lines(self, diff: str) -> Tuple[int, int]:
        """
        Count added and removed lines in diff
        
        Args:
            diff: Git diff output
            
        Returns:
            Tuple of (lines_added, lines_removed)
        """
        lines_added = 0
        lines_removed = 0
        
        for line in diff.split('\n'):
            if line.startswith('+') and not line.startswith('+++'):
                lines_added += 1
            elif line.startswith('-') and not line.startswith('---'):
                lines_removed += 1
        
        return lines_added, lines_removed
    
    def get_commit_message(self, ref: str = "HEAD") -> str:
        """Get commit message for a reference"""
        try:
            return self._run_git_command(['log', '-1', '--pretty=format:%s', ref])
        except GitError:
            return ""
    
    def get_commit_author(self, ref: str = "HEAD") -> str:
        """Get commit author for a reference"""
        try:
            return self._run_git_command(['log', '-1', '--pretty=format:%an <%ae>', ref])
        except GitError:
            return ""
    
    def get_repository_info(self) -> Dict[str, str]:
        """Get repository information"""
        info = {}
        
        try:
            info['remote_url'] = self._run_git_command(['config', '--get', 'remote.origin.url'])
        except GitError:
            info['remote_url'] = ""
        
        try:
            info['current_branch'] = self.get_current_branch()
        except GitError:
            info['current_branch'] = ""
        
        try:
            info['head_commit'] = self._run_git_command(['rev-parse', 'HEAD'])
        except GitError:
            info['head_commit'] = ""
        
        return info
    
    def is_file_binary(self, filename: str, ref: str = "HEAD") -> bool:
        """
        Check if a file is binary
        
        Args:
            filename: File path
            ref: Git reference
            
        Returns:
            True if file is binary
        """
        try:
            # Use git to check if file is binary
            result = self._run_git_command(['diff', '--numstat', f"{ref}~1", ref, '--', filename])
            
            # Binary files show as "-	-	filename" in numstat
            if result and result.startswith('-\t-\t'):
                return True
            
            # Also check file extension
            binary_extensions = [
                '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff',
                '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
                '.zip', '.tar', '.gz', '.rar', '.7z',
                '.exe', '.dll', '.so', '.dylib'
            ]
            
            return any(filename.lower().endswith(ext) for ext in binary_extensions)
            
        except GitError:
            # If we can't determine, assume it's not binary
            return False