#!/usr/bin/env python3
"""
Setup script for AI Code Review Git Hook
"""

from setuptools import setup, find_packages
import os

# Read the README file
def read_readme():
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "AI-powered git pre-push hook for code review using AWS Bedrock"

# Read requirements
def read_requirements(filename):
    req_path = os.path.join(os.path.dirname(__file__), filename)
    if os.path.exists(req_path):
        with open(req_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    return []

setup(
    name="ai-code-review-git",
    version="0.1.0",
    description="AI-powered git pre-push hook for code review using AWS Bedrock",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    author="AI Code Review Team",
    author_email="contact@example.com",
    url="https://github.com/example/ai-code-review-git-hook",
    
    # Package configuration
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    package_data={
        "ai_code_review": [
            "config/*.yaml",
            "config/templates/*.yaml",
        ],
    },
    
    # Dependencies
    install_requires=read_requirements('requirements.txt'),
    extras_require={
        'dev': read_requirements('requirements-dev.txt'),
    },
    
    # Entry points
    entry_points={
        'console_scripts': [
            'ai-code-review=ai_code_review.cli:main',
        ],
    },
    
    # Metadata
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: Software Development :: Version Control :: Git",
    ],
    python_requires=">=3.8",
    keywords="git hook code review ai aws bedrock",
    
    # Project URLs
    project_urls={
        "Bug Reports": "https://github.com/example/ai-code-review-git-hook/issues",
        "Source": "https://github.com/example/ai-code-review-git-hook",
        "Documentation": "https://github.com/example/ai-code-review-git-hook/docs",
    },
)