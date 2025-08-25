#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core hash operations - business logic for file hashing and verification
"""

import hashlib
import time
from pathlib import Path
from typing import List, Dict, Tuple, Callable, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from core.logger import logger


@dataclass
class HashResult:
    """Result of a hash operation on a single file"""
    file_path: Path
    relative_path: Path
    algorithm: str
    hash_value: str
    file_size: int
    duration: float
    error: Optional[str] = None
    
    @property
    def success(self) -> bool:
        """Whether the hash operation was successful"""
        return self.error is None
    
    @property
    def speed_mbps(self) -> float:
        """Calculate hash speed in MB/s"""
        if self.duration > 0 and self.file_size > 0:
            return (self.file_size / (1024 * 1024)) / self.duration
        return 0.0


@dataclass
class VerificationResult:
    """Result of comparing two hash results"""
    source_result: HashResult
    target_result: Optional[HashResult]
    match: bool
    comparison_type: str  # 'exact_match', 'name_match', 'missing_target', 'ambiguous_match', 'error'
    notes: str = ""
    
    @property
    def source_name(self) -> str:
        """Source file name"""
        return self.source_result.relative_path.name if self.source_result else ""
    
    @property
    def target_name(self) -> str:
        """Target file name"""
        return self.target_result.relative_path.name if self.target_result else ""


@dataclass
class HashOperationMetrics:
    """Metrics for hash operations"""
    start_time: float = 0.0
    end_time: float = 0.0
    total_files: int = 0
    processed_files: int = 0
    failed_files: int = 0
    total_bytes: int = 0
    processed_bytes: int = 0
    current_file: str = ""
    
    @property
    def duration(self) -> float:
        """Total operation duration"""
        if self.end_time > self.start_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time if self.start_time > 0 else 0
    
    @property
    def progress_percent(self) -> int:
        """Progress percentage based on processed files"""
        if self.total_files > 0:
            return int((self.processed_files / self.total_files) * 100)
        return 0
    
    @property
    def average_speed_mbps(self) -> float:
        """Average processing speed in MB/s"""
        if self.duration > 0 and self.processed_bytes > 0:
            return (self.processed_bytes / (1024 * 1024)) / self.duration
        return 0.0


class HashOperations:
    """Core business logic for hash operations"""
    
    SUPPORTED_ALGORITHMS = ['sha256', 'md5']
    BUFFER_SIZE = 64 * 1024  # 64KB buffer for hash calculation
    
    def __init__(self, algorithm: str = 'sha256'):
        """Initialize hash operations
        
        Args:
            algorithm: Hash algorithm to use ('sha256' or 'md5')
        """
        self.algorithm = algorithm.lower()
        if self.algorithm not in self.SUPPORTED_ALGORITHMS:
            raise ValueError(f"Unsupported algorithm: {algorithm}. Must be one of {self.SUPPORTED_ALGORITHMS}")
        
        self.cancelled = False
        self.progress_callback: Optional[Callable[[int, str], None]] = None
        self.status_callback: Optional[Callable[[str], None]] = None
        
    def set_callbacks(self, 
                     progress_callback: Optional[Callable[[int, str], None]] = None,
                     status_callback: Optional[Callable[[str], None]] = None):
        """Set progress and status callbacks
        
        Args:
            progress_callback: Function that receives (progress_percent, status_message)
            status_callback: Function that receives status messages
        """
        self.progress_callback = progress_callback
        self.status_callback = status_callback
        
    def cancel(self):
        """Cancel current operations"""
        self.cancelled = True
        
    def discover_files(self, paths: List[Path]) -> List[Tuple[Path, Path]]:
        """Discover all files from given paths (files and folders)
        
        Args:
            paths: List of file and folder paths
            
        Returns:
            List of (absolute_path, relative_path) tuples
        """
        discovered_files = []
        
        # Find common base path for all selected items to ensure consistent relative paths
        if not paths:
            return discovered_files
            
        # Get all parent directories
        all_parents = []
        for path in paths:
            if path.exists():
                if path.is_file():
                    all_parents.append(path.parent)
                elif path.is_dir():
                    all_parents.append(path.parent)
        
        # Find common base path
        if all_parents:
            # Use the common parent directory of all selected items
            common_base = all_parents[0]
            for parent in all_parents[1:]:
                # Find common path
                try:
                    parent.relative_to(common_base)
                except ValueError:
                    try:
                        common_base.relative_to(parent)
                        common_base = parent
                    except ValueError:
                        # Find actual common ancestor
                        common_parts = []
                        base_parts = common_base.parts
                        parent_parts = parent.parts
                        for i, (b, p) in enumerate(zip(base_parts, parent_parts)):
                            if b == p:
                                common_parts.append(b)
                            else:
                                break
                        if common_parts:
                            common_base = Path(*common_parts)
                        else:
                            common_base = Path("/") if str(common_base).startswith("/") else Path("C:\\")
        else:
            common_base = Path(".")
        
        for path in paths:
            if not path.exists():
                logger.warning(f"Path does not exist: {path}")
                continue
                
            if path.is_file():
                # Single file - use consistent relative path from common base
                try:
                    relative_path = path.relative_to(common_base)
                    discovered_files.append((path, relative_path))
                except ValueError:
                    # Fallback: use parent name + filename
                    parent_name = path.parent.name
                    if parent_name and parent_name not in [".", "/"]:
                        relative_path = Path(parent_name) / path.name
                    else:
                        relative_path = Path(path.name)
                    discovered_files.append((path, relative_path))
            elif path.is_dir():
                # Recursive folder discovery - use same common base
                try:
                    for file_path in path.rglob('*'):
                        if file_path.is_file():
                            relative_path = file_path.relative_to(common_base)
                            discovered_files.append((file_path, relative_path))
                except Exception as e:
                    logger.error(f"Error discovering files in {path}: {e}")
                    
        return discovered_files
    
    def hash_file(self, file_path: Path, relative_path: Path) -> HashResult:
        """Calculate hash for a single file
        
        Args:
            file_path: Absolute path to file
            relative_path: Relative path for display/storage
            
        Returns:
            HashResult with hash information
        """
        start_time = time.time()
        
        try:
            # Get file size
            file_size = file_path.stat().st_size
            
            # Create hash object
            if self.algorithm == 'sha256':
                hash_obj = hashlib.sha256()
            elif self.algorithm == 'md5':
                hash_obj = hashlib.md5()
            else:
                raise ValueError(f"Unsupported algorithm: {self.algorithm}")
            
            # Calculate hash with progress reporting
            processed_bytes = 0
            with open(file_path, 'rb') as f:
                while not self.cancelled:
                    chunk = f.read(self.BUFFER_SIZE)
                    if not chunk:
                        break
                    
                    hash_obj.update(chunk)
                    processed_bytes += len(chunk)
                    
                    # Report progress for large files (every 1MB)
                    if processed_bytes % (1024 * 1024) == 0:
                        if self.progress_callback:
                            file_progress = int((processed_bytes / file_size * 100)) if file_size > 0 else 100
                            self.progress_callback(file_progress, f"Hashing: {relative_path}")
            
            if self.cancelled:
                return HashResult(
                    file_path=file_path,
                    relative_path=relative_path,
                    algorithm=self.algorithm,
                    hash_value="",
                    file_size=file_size,
                    duration=time.time() - start_time,
                    error="Operation cancelled"
                )
            
            # Get final hash
            hash_value = hash_obj.hexdigest()
            duration = time.time() - start_time
            
            return HashResult(
                file_path=file_path,
                relative_path=relative_path,
                algorithm=self.algorithm,
                hash_value=hash_value,
                file_size=file_size,
                duration=duration
            )
            
        except Exception as e:
            logger.error(f"Error hashing {file_path}: {e}")
            return HashResult(
                file_path=file_path,
                relative_path=relative_path,
                algorithm=self.algorithm,
                hash_value="",
                file_size=0,
                duration=time.time() - start_time,
                error=str(e)
            )
    
    def hash_multiple_files(self, paths: List[Path]) -> Tuple[List[HashResult], HashOperationMetrics]:
        """Hash multiple files and folders
        
        Args:
            paths: List of file and folder paths to hash
            
        Returns:
            Tuple of (hash_results, metrics)
        """
        # Discover all files
        discovered_files = self.discover_files(paths)
        
        # Initialize metrics
        metrics = HashOperationMetrics(
            start_time=time.time(),
            total_files=len(discovered_files),
            total_bytes=sum(f[0].stat().st_size for f in discovered_files if f[0].exists())
        )
        
        results = []
        
        if self.status_callback:
            self.status_callback(f"Starting {self.algorithm.upper()} hash calculation for {len(discovered_files)} files")
        
        for i, (file_path, relative_path) in enumerate(discovered_files):
            if self.cancelled:
                break
                
            metrics.current_file = str(relative_path)
            metrics.processed_files = i
            
            # Update progress
            if self.progress_callback:
                progress = int((i / len(discovered_files)) * 100) if len(discovered_files) > 0 else 0
                self.progress_callback(progress, f"Processing: {relative_path.name}")
            
            if self.status_callback:
                self.status_callback(f"Hashing: {relative_path}")
            
            # Hash the file
            result = self.hash_file(file_path, relative_path)
            results.append(result)
            
            # Update metrics
            if result.success:
                metrics.processed_bytes += result.file_size
            else:
                metrics.failed_files += 1
                
        metrics.end_time = time.time()
        metrics.processed_files = len([r for r in results if r.success])
        
        if self.status_callback:
            self.status_callback(f"Hash calculation complete: {metrics.processed_files}/{metrics.total_files} files processed")
        
        return results, metrics
    
    def verify_hashes(self, source_paths: List[Path], target_paths: List[Path]) -> Tuple[List[VerificationResult], HashOperationMetrics]:
        """Verify hashes between two sets of files
        
        Args:
            source_paths: Source files/folders to hash
            target_paths: Target files/folders to compare against
            
        Returns:
            Tuple of (verification_results, metrics)
        """
        if self.status_callback:
            self.status_callback("Starting hash verification process...")
        
        # Hash source files
        if self.status_callback:
            self.status_callback("Hashing source files...")
        source_results, source_metrics = self.hash_multiple_files(source_paths)
        
        if self.cancelled:
            return [], source_metrics
        
        # Hash target files  
        if self.status_callback:
            self.status_callback("Hashing target files...")
        target_results, target_metrics = self.hash_multiple_files(target_paths)
        
        if self.cancelled:
            return [], source_metrics
        
        # Create combined metrics
        combined_metrics = HashOperationMetrics(
            start_time=source_metrics.start_time,
            end_time=target_metrics.end_time,
            total_files=source_metrics.total_files + target_metrics.total_files,
            processed_files=source_metrics.processed_files + target_metrics.processed_files,
            failed_files=source_metrics.failed_files + target_metrics.failed_files,
            total_bytes=source_metrics.total_bytes + target_metrics.total_bytes,
            processed_bytes=source_metrics.processed_bytes + target_metrics.processed_bytes
        )
        
        # Compare results
        if self.status_callback:
            self.status_callback("Comparing hash results...")
        
        # Debug logging: show sample of source and target paths
        logger.debug("=== HASH VERIFICATION DEBUG ===")
        logger.debug(f"Source files ({len(source_results)}):")
        for i, result in enumerate(source_results[:5]):  # Show first 5
            logger.debug(f"  [{i}] {result.relative_path}")
        if len(source_results) > 5:
            logger.debug(f"  ... and {len(source_results) - 5} more")
            
        logger.debug(f"Target files ({len(target_results)}):")
        for i, result in enumerate(target_results[:5]):  # Show first 5
            logger.debug(f"  [{i}] {result.relative_path}")
        if len(target_results) > 5:
            logger.debug(f"  ... and {len(target_results) - 5} more")
        logger.debug("=== END DEBUG ===")
        
        verification_results = self._compare_hash_results(source_results, target_results)
        
        # Summary
        matches = sum(1 for v in verification_results if v.match)
        total_comparisons = len(verification_results)
        
        if self.status_callback:
            self.status_callback(f"Verification complete: {matches}/{total_comparisons} files match")
        
        return verification_results, combined_metrics
    
    def _normalize_relative_path(self, relative_path: Path) -> Path:
        """Normalize relative path by removing root folder variations
        
        This handles cases where source and target have slightly different root folder names
        like 'Folder' vs 'Folder - Copy'
        """
        parts = relative_path.parts
        if len(parts) <= 1:
            return relative_path
            
        # Get the root folder name
        root_folder = parts[0]
        
        # Check if this looks like a copy variation
        # Remove common copy suffixes to normalize
        normalized_root = root_folder
        copy_suffixes = [' - Copy', ' - copy', ' (Copy)', ' (copy)', ' Copy', ' copy', '_Copy', '_copy']
        
        for suffix in copy_suffixes:
            if root_folder.endswith(suffix):
                normalized_root = root_folder[:-len(suffix)]
                break
                
        # Rebuild path with normalized root
        if normalized_root != root_folder:
            return Path(normalized_root) / Path(*parts[1:])
        else:
            return relative_path

    def _compare_hash_results(self, source_results: List[HashResult], target_results: List[HashResult]) -> List[VerificationResult]:
        """Compare two sets of hash results
        
        Args:
            source_results: Results from source files
            target_results: Results from target files
            
        Returns:
            List of verification results
        """
        verification_results = []
        
        # Create lookup maps for target results with normalized paths
        # Primary map: normalized relative path -> result (for exact path matching)
        target_path_map = {}
        # Secondary map: filename only -> list of results (for fallback matching)
        target_filename_map = {}
        
        for target_result in target_results:
            # Normalize the relative path to handle copy variations
            normalized_path = self._normalize_relative_path(target_result.relative_path)
            normalized_path_str = str(normalized_path)
            filename = target_result.relative_path.name
            
            # Store by normalized relative path (primary key)
            target_path_map[normalized_path_str] = target_result
            
            # Store by filename for fallback (handle multiple files with same name)
            if filename not in target_filename_map:
                target_filename_map[filename] = []
            target_filename_map[filename].append(target_result)
        
        # Compare each source file
        for source_result in source_results:
            source_filename = source_result.relative_path.name
            # Normalize source path for comparison
            normalized_source_path = self._normalize_relative_path(source_result.relative_path)
            normalized_source_path_str = str(normalized_source_path)
            source_path_str = str(source_result.relative_path)  # Keep original for logging
            
            # Try to find matching target file
            target_result = None
            comparison_type = "missing_target"
            notes = ""
            
            # PRIORITY 1: Try exact normalized path match (most accurate)
            if normalized_source_path_str in target_path_map:
                target_result = target_path_map[normalized_source_path_str]
                comparison_type = "exact_match"
            # PRIORITY 2: Try filename-only match (fallback for single files)
            elif source_filename in target_filename_map:
                filename_matches = target_filename_map[source_filename]
                if len(filename_matches) == 1:
                    # Only one file with this name, safe to match
                    target_result = filename_matches[0]
                    comparison_type = "name_match"
                else:
                    # Multiple files with same name - cannot determine correct match
                    target_result = None
                    comparison_type = "ambiguous_match"
                    notes = f"Multiple target files named '{source_filename}' - cannot determine correct match"
            
            # Determine match status
            if target_result is None:
                match = False
                if comparison_type == "missing_target":
                    notes = "No corresponding target file found"
                # notes already set for ambiguous_match case
            elif not source_result.success or not target_result.success:
                match = False
                comparison_type = "error"
                notes = f"Hash calculation failed - Source: {source_result.error or 'OK'}, Target: {target_result.error or 'OK'}"
            else:
                match = source_result.hash_value == target_result.hash_value
                if not match:
                    notes = f"Hash mismatch - Source: {source_result.hash_value[:16]}..., Target: {target_result.hash_value[:16]}..."
                    # Log detailed mismatch info for debugging
                    logger.info(f"Hash mismatch: '{source_path_str}' -> '{target_result.relative_path}' ({comparison_type})")
                    logger.debug(f"  Source hash: {source_result.hash_value}")
                    logger.debug(f"  Target hash: {target_result.hash_value}")
                else:
                    notes = f"Hash match: {source_result.hash_value[:16]}... ({comparison_type})"
                    logger.debug(f"Hash match: '{source_path_str}' -> '{target_result.relative_path}' ({comparison_type})")
                    if comparison_type == "exact_match":
                        logger.debug(f"  Normalized: '{normalized_source_path_str}' -> '{normalized_source_path_str}'")
            
            # Log missing or ambiguous files for debugging
            if target_result is None:
                if comparison_type == "missing_target":
                    logger.info(f"Missing target for: '{source_path_str}'")
                elif comparison_type == "ambiguous_match":
                    logger.warning(f"Ambiguous match for: '{source_path_str}' - {notes}")
            
            verification_results.append(VerificationResult(
                source_result=source_result,
                target_result=target_result,
                match=match,
                comparison_type=comparison_type,
                notes=notes
            ))
        
        return verification_results