"""
Change analyzer for AI Code Review
"""

import fnmatch
from pathlib import Path
from typing import Dict, List, Set, Optional
from dataclasses import dataclass

from .operations import FileChange
from ..utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AnalysisResult:
    """Result of change analysis"""
    filtered_changes: Dict[str, FileChange]
    excluded_files: List[str]
    binary_files: List[str]
    large_files: List[str]
    total_lines_added: int
    total_lines_removed: int
    file_count: int


class ChangeAnalyzer:
    """Analyzes and filters git changes for code review"""
    
    def __init__(self, config: Dict):
        """
        Initialize change analyzer
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.git_config = config.get('git', {})
        
        # Extract configuration values
        self.exclude_patterns = self.git_config.get('exclude_patterns', [])
        self.include_patterns = self.git_config.get('include_patterns', [])
        self.binary_extensions = self.git_config.get('binary_file_extensions', [])
        self.max_diff_size = self.git_config.get('max_diff_size', 10000)
        self.max_files = self.git_config.get('max_files', 50)
    
    def analyze_changes(self, changes: Dict[str, FileChange]) -> AnalysisResult:
        """
        Analyze and filter changes for review
        
        Args:
            changes: Dictionary of filename -> FileChange
            
        Returns:
            AnalysisResult with filtered changes and statistics
        """
        logger.info(f"Analyzing {len(changes)} changed files")
        
        filtered_changes = {}
        excluded_files = []
        binary_files = []
        large_files = []
        
        total_lines_added = 0
        total_lines_removed = 0
        
        for filename, change in changes.items():
            # Check if file should be excluded
            if self._should_exclude_file(filename):
                excluded_files.append(filename)
                logger.debug(f"Excluded {filename} (matches exclude pattern)")
                continue
            
            # Check if file should be included (if include patterns specified)
            if self.include_patterns and not self._should_include_file(filename):
                excluded_files.append(filename)
                logger.debug(f"Excluded {filename} (doesn't match include pattern)")
                continue
            
            # Check if file is binary
            if self._is_binary_file(filename):
                binary_files.append(filename)
                logger.debug(f"Excluded {filename} (binary file)")
                continue
            
            # Check if diff is too large
            total_change_lines = change.lines_added + change.lines_removed
            if total_change_lines > self.max_diff_size:
                large_files.append(filename)
                logger.debug(f"Excluded {filename} (too large: {total_change_lines} lines)")
                continue
            
            # File passes all filters
            filtered_changes[filename] = change
            total_lines_added += change.lines_added
            total_lines_removed += change.lines_removed
        
        # Limit number of files if necessary
        if len(filtered_changes) > self.max_files:
            logger.warning(f"Too many files ({len(filtered_changes)}), limiting to {self.max_files}")
            
            # Sort by change size (largest first) and take top files
            sorted_files = sorted(
                filtered_changes.items(),
                key=lambda x: x[1].lines_added + x[1].lines_removed,
                reverse=True
            )
            
            limited_changes = dict(sorted_files[:self.max_files])
            excluded_count = len(filtered_changes) - self.max_files
            excluded_files.extend([f for f, _ in sorted_files[self.max_files:]])
            
            logger.info(f"Limited to {self.max_files} files, excluded {excluded_count} additional files")
            filtered_changes = limited_changes
        
        result = AnalysisResult(
            filtered_changes=filtered_changes,
            excluded_files=excluded_files,
            binary_files=binary_files,
            large_files=large_files,
            total_lines_added=total_lines_added,
            total_lines_removed=total_lines_removed,
            file_count=len(filtered_changes)
        )
        
        logger.info(f"Analysis complete: {result.file_count} files to review, "
                   f"{len(excluded_files)} excluded, {len(binary_files)} binary, "
                   f"{len(large_files)} too large")
        
        return result
    
    def _should_exclude_file(self, filename: str) -> bool:
        """Check if file matches exclude patterns"""
        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(filename, pattern):
                return True
        return False
    
    def _should_include_file(self, filename: str) -> bool:
        """Check if file matches include patterns"""
        if not self.include_patterns:
            return True
        
        for pattern in self.include_patterns:
            if fnmatch.fnmatch(filename, pattern):
                return True
        return False
    
    def _is_binary_file(self, filename: str) -> bool:
        """Check if file is binary based on extension"""
        file_ext = Path(filename).suffix.lower()
        return file_ext in self.binary_extensions
    
    def categorize_changes(self, changes: Dict[str, FileChange]) -> Dict[str, List[str]]:
        """
        Categorize changes by type
        
        Args:
            changes: Dictionary of filename -> FileChange
            
        Returns:
            Dictionary of category -> list of filenames
        """
        categories = {
            'added': [],
            'modified': [],
            'deleted': [],
            'renamed': [],
            'copied': []
        }
        
        for filename, change in changes.items():
            if change.status == 'A':
                categories['added'].append(filename)
            elif change.status == 'M':
                categories['modified'].append(filename)
            elif change.status == 'D':
                categories['deleted'].append(filename)
            elif change.status == 'R':
                categories['renamed'].append(filename)
            elif change.status == 'C':
                categories['copied'].append(filename)
        
        return categories
    
    def get_file_types(self, changes: Dict[str, FileChange]) -> Dict[str, List[str]]:
        """
        Group files by type/extension
        
        Args:
            changes: Dictionary of filename -> FileChange
            
        Returns:
            Dictionary of file_type -> list of filenames
        """
        file_types = {}
        
        for filename in changes.keys():
            file_ext = Path(filename).suffix.lower()
            if not file_ext:
                file_ext = 'no_extension'
            
            if file_ext not in file_types:
                file_types[file_ext] = []
            file_types[file_ext].append(filename)
        
        return file_types
    
    def get_change_statistics(self, changes: Dict[str, FileChange]) -> Dict[str, int]:
        """
        Get statistics about changes
        
        Args:
            changes: Dictionary of filename -> FileChange
            
        Returns:
            Dictionary of statistics
        """
        stats = {
            'total_files': len(changes),
            'total_lines_added': 0,
            'total_lines_removed': 0,
            'files_added': 0,
            'files_modified': 0,
            'files_deleted': 0,
            'files_renamed': 0,
            'largest_change': 0,
            'smallest_change': float('inf')
        }
        
        for change in changes.values():
            stats['total_lines_added'] += change.lines_added
            stats['total_lines_removed'] += change.lines_removed
            
            if change.status == 'A':
                stats['files_added'] += 1
            elif change.status == 'M':
                stats['files_modified'] += 1
            elif change.status == 'D':
                stats['files_deleted'] += 1
            elif change.status == 'R':
                stats['files_renamed'] += 1
            
            # Track largest and smallest changes
            total_lines = change.lines_added + change.lines_removed
            if total_lines > stats['largest_change']:
                stats['largest_change'] = total_lines
            if total_lines < stats['smallest_change']:
                stats['smallest_change'] = total_lines
        
        # Handle edge case where no changes
        if stats['smallest_change'] == float('inf'):
            stats['smallest_change'] = 0
        
        return stats
    
    def chunk_large_diffs(self, changes: Dict[str, FileChange], chunk_size: int = 1000) -> Dict[str, List[str]]:
        """
        Split large diffs into smaller chunks for processing
        
        Args:
            changes: Dictionary of filename -> FileChange
            chunk_size: Maximum lines per chunk
            
        Returns:
            Dictionary of filename -> list of diff chunks
        """
        chunked_diffs = {}
        
        for filename, change in changes.items():
            diff_lines = change.diff.split('\n')
            
            if len(diff_lines) <= chunk_size:
                # Small diff, no chunking needed
                chunked_diffs[filename] = [change.diff]
            else:
                # Large diff, split into chunks
                chunks = []
                current_chunk = []
                header_lines = []
                
                # Extract diff header
                for line in diff_lines:
                    if line.startswith('diff --git') or line.startswith('index ') or \
                       line.startswith('---') or line.startswith('+++'):
                        header_lines.append(line)
                    else:
                        break
                
                # Process remaining lines
                content_lines = diff_lines[len(header_lines):]
                
                for line in content_lines:
                    current_chunk.append(line)
                    
                    if len(current_chunk) >= chunk_size:
                        # Create chunk with header
                        chunk_content = header_lines + current_chunk
                        chunks.append('\n'.join(chunk_content))
                        current_chunk = []
                
                # Add remaining lines as final chunk
                if current_chunk:
                    chunk_content = header_lines + current_chunk
                    chunks.append('\n'.join(chunk_content))
                
                chunked_diffs[filename] = chunks
                logger.debug(f"Split {filename} diff into {len(chunks)} chunks")
        
        return chunked_diffs
    
    def prioritize_files(self, changes: Dict[str, FileChange]) -> List[str]:
        """
        Prioritize files for review based on various factors
        
        Args:
            changes: Dictionary of filename -> FileChange
            
        Returns:
            List of filenames in priority order
        """
        def calculate_priority(filename: str, change: FileChange) -> float:
            """Calculate priority score for a file"""
            score = 0.0
            
            # Size of change (more lines = higher priority)
            total_lines = change.lines_added + change.lines_removed
            score += total_lines * 0.1
            
            # File type priorities
            file_ext = Path(filename).suffix.lower()
            high_priority_extensions = ['.py', '.js', '.ts', '.java', '.go', '.rs']
            medium_priority_extensions = ['.jsx', '.tsx', '.cpp', '.c', '.cs']
            
            if file_ext in high_priority_extensions:
                score += 100
            elif file_ext in medium_priority_extensions:
                score += 50
            
            # New files get higher priority
            if change.status == 'A':
                score += 75
            
            # Security-sensitive files
            security_patterns = ['*auth*', '*security*', '*password*', '*token*', '*key*']
            if any(fnmatch.fnmatch(filename.lower(), pattern) for pattern in security_patterns):
                score += 200
            
            # Configuration files
            config_patterns = ['*.config.*', '*.env*', 'Dockerfile*', '*.yml', '*.yaml']
            if any(fnmatch.fnmatch(filename, pattern) for pattern in config_patterns):
                score += 150
            
            return score
        
        # Calculate priorities and sort
        file_priorities = [
            (filename, calculate_priority(filename, change))
            for filename, change in changes.items()
        ]
        
        file_priorities.sort(key=lambda x: x[1], reverse=True)
        
        prioritized_files = [filename for filename, _ in file_priorities]
        
        logger.debug(f"Prioritized {len(prioritized_files)} files for review")
        return prioritized_files