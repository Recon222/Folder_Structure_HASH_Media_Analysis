#!/usr/bin/env python3
"""
FFProbe wrapper for subprocess operations
Handles metadata extraction from media files using ffprobe
"""

import subprocess
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.result_types import Result
from core.exceptions import MediaExtractionError, FFProbeNotFoundError
from core.logger import logger
from .ffprobe_command_builder import FFProbeCommandBuilder


class FFProbeWrapper:
    """Wrapper for FFprobe subprocess operations"""
    
    def __init__(self, binary_path: Path, timeout: float = 5.0):
        """
        Initialize FFprobe wrapper
        
        Args:
            binary_path: Path to ffprobe binary
            timeout: Timeout in seconds for each extraction
        """
        self.binary_path = binary_path
        self.timeout = timeout
        self.command_builder = FFProbeCommandBuilder()  # NEW: Add command builder
        
        if not binary_path or not binary_path.exists():
            raise FFProbeNotFoundError(f"FFprobe not found at {binary_path}")
    
    def extract_metadata(self, file_path: Path, settings: Any = None) -> Result[Dict[str, Any]]:
        """
        Extract raw metadata from single file using optimized commands
        
        Args:
            file_path: Path to media file
            settings: MediaAnalysisSettings for field selection (uses defaults if None)
            
        Returns:
            Result containing raw metadata dict or error
        """
        try:
            # Use default settings if none provided
            if settings is None:
                from ..core.media_analysis_models import MediaAnalysisSettings
                settings = MediaAnalysisSettings()
            
            # Build optimized command based on settings
            cmd = self.command_builder.build_command(
                self.binary_path,
                file_path,
                settings
            )
            
            # Adjust timeout for frame analysis
            timeout = self.timeout
            if hasattr(settings, 'frame_analysis_fields') and settings.frame_analysis_fields.enabled:
                timeout = max(15.0, self.timeout * 3)  # Triple timeout for frame analysis
            
            logger.debug(f"Extracting from {file_path.name} with {len(cmd)} parameters")
            start_time = time.time()
            
            # Run ffprobe with timeout
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False  # Don't raise on non-zero return
            )
            
            # Check for errors
            if result.returncode != 0:
                # Non-zero return usually means not a valid media file
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                
                # Check if it's just not a media file (common case)
                if "Invalid data" in error_msg or "could not find codec" in error_msg.lower():
                    return Result.error(MediaExtractionError(
                        f"Not a valid media file: {file_path.name}",
                        file_path=str(file_path),
                        extraction_error=error_msg,
                        user_message="File is not a valid media file or format is not supported."
                    ))
                else:
                    return Result.error(MediaExtractionError(
                        f"FFprobe failed on {file_path.name}: {error_msg}",
                        file_path=str(file_path),
                        extraction_error=error_msg,
                        user_message=f"Failed to analyze {file_path.name}"
                    ))
            
            # Parse JSON output
            try:
                metadata = json.loads(result.stdout)
                
                # Add extraction metrics
                extraction_time = time.time() - start_time
                metadata['_extraction_time'] = extraction_time
                metadata['_command_complexity'] = len(cmd)
                
                # Validate we got some data
                if not metadata.get('format') and not metadata.get('streams'):
                    return Result.error(MediaExtractionError(
                        f"No metadata found in {file_path.name}",
                        file_path=str(file_path),
                        user_message="File contains no media metadata."
                    ))
                
                return Result.success(metadata)
                
            except json.JSONDecodeError as e:
                return Result.error(MediaExtractionError(
                    f"Invalid JSON from FFprobe for {file_path.name}: {e}",
                    file_path=str(file_path),
                    extraction_error=str(e),
                    user_message="Failed to parse metadata output."
                ))
                
        except subprocess.TimeoutExpired:
            return Result.error(MediaExtractionError(
                f"Timeout extracting metadata from {file_path.name}",
                file_path=str(file_path),
                user_message=f"Analysis of {file_path.name} took too long and was cancelled."
            ))
            
        except Exception as e:
            return Result.error(MediaExtractionError(
                f"Unexpected error extracting metadata from {file_path.name}: {e}",
                file_path=str(file_path),
                extraction_error=str(e),
                user_message=f"Unexpected error analyzing {file_path.name}"
            ))
    
    def extract_batch(
        self, 
        file_paths: List[Path],
        settings: Any = None,
        max_workers: int = 8,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[Path, Result[Dict]]:
        """
        Extract metadata from multiple files in parallel using optimized commands
        
        Args:
            file_paths: List of file paths to analyze
            settings: MediaAnalysisSettings for field selection (uses defaults if None)
            max_workers: Maximum number of parallel workers
            progress_callback: Callback for progress updates (completed, total)
            
        Returns:
            Dictionary mapping file paths to extraction results
        """
        results = {}
        total_files = len(file_paths)
        
        if total_files == 0:
            return results
        
        # Use default settings if none provided
        if settings is None:
            from ..core.media_analysis_models import MediaAnalysisSettings
            settings = MediaAnalysisSettings()
        
        # Limit workers to reasonable number
        actual_workers = min(max_workers, total_files, 32)
        
        logger.info(f"Batch extraction of {total_files} files with {actual_workers} workers (optimized)")
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=actual_workers) as executor:
            # Submit all extraction tasks with settings
            future_to_path = {
                executor.submit(self.extract_metadata, path, settings): path
                for path in file_paths
            }
            
            # Process results as they complete
            completed = 0
            for future in as_completed(future_to_path):
                path = future_to_path[future]
                
                try:
                    # Get the result (already a Result object)
                    results[path] = future.result()
                except Exception as e:
                    # Wrap unexpected exceptions
                    results[path] = Result.error(MediaExtractionError(
                        f"Thread execution error for {path.name}: {e}",
                        file_path=str(path),
                        user_message=f"Failed to process {path.name}"
                    ))
                
                completed += 1
                
                # Report progress
                if progress_callback:
                    try:
                        progress_callback(completed, total_files)
                    except Exception as e:
                        logger.warning(f"Progress callback error: {e}")
                
                # Log progress periodically
                if completed % 10 == 0 or completed == total_files:
                    elapsed = time.time() - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    logger.debug(f"Processed {completed}/{total_files} files ({rate:.1f} files/sec)")
        
        elapsed_time = time.time() - start_time
        logger.info(f"Batch extraction completed: {completed} files in {elapsed_time:.1f} seconds")
        
        return results
    
    def get_simple_info(self, file_path: Path) -> Result[Dict[str, Any]]:
        """
        Get simplified media information (format, duration, size only)
        Faster than full extraction for quick checks
        
        Args:
            file_path: Path to media file
            
        Returns:
            Result containing basic info dict or error
        """
        try:
            cmd = self.command_builder.build_simple_command(self.binary_path, file_path)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=2.0,  # Shorter timeout for simple info
                check=False
            )
            
            if result.returncode != 0:
                return Result.error(MediaExtractionError(
                    f"Not a media file: {file_path.name}",
                    file_path=str(file_path)
                ))
            
            metadata = json.loads(result.stdout)
            
            # Extract simple info
            format_info = metadata.get('format', {})
            simple_info = {
                'is_media': True,
                'format': format_info.get('format_name', 'unknown'),
                'duration': float(format_info.get('duration', 0)),
                'size': int(format_info.get('size', 0))
            }
            
            return Result.success(simple_info)
            
        except Exception:
            # Any error means it's not a media file we can process
            return Result.success({'is_media': False})