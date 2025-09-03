#!/usr/bin/env python3
"""
ExifTool Wrapper for batch metadata extraction
Handles subprocess execution with parallelization and timeout protection
"""

import json
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FutureTimeoutError
from threading import Event

from .exiftool_models import ExifToolMetadata, ExifToolSettings
from .exiftool_command_builder import ExifToolForensicCommandBuilder
from ..logger import logger
from ..exceptions import MediaExtractionError


class ExifToolWrapper:
    """
    Batch processing wrapper for ExifTool
    Follows FFProbeWrapper patterns for consistency
    """
    
    def __init__(self, binary_path: Path):
        """
        Initialize wrapper with ExifTool binary
        
        Args:
            binary_path: Path to validated ExifTool binary
        """
        self.binary_path = binary_path
        self.command_builder = ExifToolForensicCommandBuilder()
        self.cancel_event = Event()
        
        logger.info(f"ExifToolWrapper initialized with binary: {binary_path}")
    
    def extract_batch(
        self,
        files: List[Path],
        settings: ExifToolSettings,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        cancel_event: Optional[Event] = None
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Process files in optimized batches with parallel execution
        
        Args:
            files: List of files to process
            settings: ExifTool extraction settings
            progress_callback: Optional callback for progress updates
            cancel_event: Optional event for cancellation
            
        Returns:
            Tuple of (extracted_metadata_list, error_list)
        """
        if cancel_event:
            self.cancel_event = cancel_event
        
        results = []
        errors = []
        total_files = len(files)
        processed = 0
        
        # Debug logging for settings
        logger.info(f"EXIFTOOL WRAPPER - extract_thumbnails: {getattr(settings, 'extract_thumbnails', False)}")
        
        # Build batch commands
        batch_commands = self.command_builder.build_batch_command(
            self.binary_path,
            files,
            settings,
            max_batch=settings.batch_size
        )
        
        total_batches = len(batch_commands)
        logger.info(f"Processing {total_files} files in {total_batches} batches")
        
        # Process batches in parallel
        with ThreadPoolExecutor(max_workers=settings.max_workers) as executor:
            # Submit all batches
            future_to_batch = {}
            for batch_idx, cmd in enumerate(batch_commands):
                if self.cancel_event.is_set():
                    break
                
                # Get files for this batch
                start_idx = batch_idx * settings.batch_size
                end_idx = min(start_idx + settings.batch_size, total_files)
                batch_files = files[start_idx:end_idx]
                
                future = executor.submit(
                    self._process_batch_command,
                    cmd,
                    batch_files,
                    settings.timeout_per_file * len(batch_files)
                )
                future_to_batch[future] = (batch_idx, batch_files)
            
            # Process results as they complete
            for future in as_completed(future_to_batch):
                if self.cancel_event.is_set():
                    # Cancel remaining futures
                    for f in future_to_batch:
                        f.cancel()
                    break
                
                batch_idx, batch_files = future_to_batch[future]
                
                try:
                    batch_results, batch_errors = future.result(
                        timeout=settings.timeout_per_file * len(batch_files)
                    )
                    results.extend(batch_results)
                    errors.extend(batch_errors)
                    processed += len(batch_files)
                    
                    # Update progress
                    if progress_callback:
                        progress = (processed / total_files) * 100
                        progress_callback(
                            progress,
                            f"Processed batch {batch_idx + 1}/{total_batches} ({processed}/{total_files} files)"
                        )
                    
                except FutureTimeoutError:
                    error_msg = f"Batch {batch_idx + 1} timed out"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    # Add error for each file in batch
                    for f in batch_files:
                        errors.append(f"Timeout: {f.name}")
                    processed += len(batch_files)
                    
                except Exception as e:
                    error_msg = f"Batch {batch_idx + 1} error: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    processed += len(batch_files)
        
        logger.info(f"Extraction complete: {len(results)} successful, {len(errors)} errors")
        return results, errors
    
    def extract_single(
        self,
        file_path: Path,
        settings: ExifToolSettings
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Extract metadata from a single file
        
        Args:
            file_path: Path to file
            settings: Extraction settings
            
        Returns:
            Tuple of (metadata_dict, error_string)
        """
        cmd = self.command_builder.build_single_command(
            self.binary_path,
            file_path,
            settings
        )
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=settings.timeout_per_file
            )
            
            if result.returncode == 0:
                # Parse JSON output
                try:
                    metadata_list = json.loads(result.stdout)
                    if metadata_list and isinstance(metadata_list, list):
                        return metadata_list[0], None
                    return None, "No metadata extracted"
                except json.JSONDecodeError as e:
                    return None, f"JSON parse error: {str(e)}"
            else:
                # Check if it's just a non-media file
                if "No matching files" in result.stderr or "Unknown file type" in result.stderr:
                    return None, "Not a media file"
                return None, f"ExifTool error: {result.stderr}"
                
        except subprocess.TimeoutExpired:
            return None, f"Timeout after {settings.timeout_per_file}s"
        except Exception as e:
            return None, f"Extraction error: {str(e)}"
    
    def get_simple_info(self, file_path: Path) -> Dict[str, Any]:
        """
        Quick extraction for basic info and GPS check
        
        Args:
            file_path: Path to file
            
        Returns:
            Dictionary with basic metadata
        """
        cmd = self.command_builder.build_simple_command(
            self.binary_path,
            file_path
        )
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5  # Quick timeout for simple extraction
            )
            
            if result.returncode == 0:
                metadata_list = json.loads(result.stdout)
                if metadata_list and isinstance(metadata_list, list):
                    data = metadata_list[0]
                    return {
                        'has_gps': any(k.startswith('GPS') for k in data.keys()),
                        'file_type': data.get('FileType'),
                        'mime_type': data.get('MIMEType')
                    }
        except:
            pass
        
        return {'has_gps': False, 'file_type': None, 'mime_type': None}
    
    def _process_batch_command(
        self,
        cmd: List[str],
        batch_files: List[Path],
        timeout: float
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Process a batch command and return results
        
        Args:
            cmd: Command to execute
            batch_files: Files being processed
            timeout: Total timeout for batch
            
        Returns:
            Tuple of (results, errors)
        """
        start_time = time.time()
        results = []
        errors = []
        
        try:
            # Log the actual command for debugging
            logger.debug(f"EXECUTING EXIFTOOL COMMAND: {' '.join(cmd[:20])}..." if len(cmd) > 20 else ' '.join(cmd))
            
            # Execute command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(Path(batch_files[0]).parent) if batch_files else None
            )
            
            execution_time = time.time() - start_time
            
            if result.returncode == 0:
                # Parse JSON output
                try:
                    metadata_list = json.loads(result.stdout)
                    
                    # Match metadata to files
                    file_map = {f.name: f for f in batch_files}
                    
                    for metadata in metadata_list:
                        if 'SourceFile' in metadata:
                            source_path = Path(metadata['SourceFile'])
                            # Debug: Check for thumbnail fields
                            has_thumbnail = any(k in metadata for k in ['ThumbnailImage', 'PreviewImage', 'JpgFromRaw'])
                            if has_thumbnail:
                                logger.info(f"THUMBNAIL FIELDS FOUND in raw output for {source_path.name}")
                            # Add execution time per file
                            metadata['_extraction_time'] = execution_time / len(metadata_list)
                            results.append(metadata)
                        else:
                            errors.append("Missing SourceFile in metadata")
                    
                    # Check for missing files
                    extracted_files = {Path(m['SourceFile']).name for m in metadata_list}
                    for f in batch_files:
                        if f.name not in extracted_files:
                            errors.append(f"No metadata for: {f.name}")
                            
                except json.JSONDecodeError as e:
                    errors.append(f"JSON parse error: {str(e)}")
                    for f in batch_files:
                        errors.append(f"Failed: {f.name}")
            else:
                # Command failed
                error_msg = result.stderr or "Unknown error"
                errors.append(f"Batch command failed: {error_msg}")
                for f in batch_files:
                    errors.append(f"Failed: {f.name}")
                    
        except subprocess.TimeoutExpired:
            errors.append(f"Batch timeout after {timeout}s")
            for f in batch_files:
                errors.append(f"Timeout: {f.name}")
        except Exception as e:
            errors.append(f"Batch error: {str(e)}")
            for f in batch_files:
                errors.append(f"Error: {f.name}")
        
        return results, errors
    
    def validate_extraction(self, metadata: Dict[str, Any]) -> bool:
        """
        Validate extracted metadata has minimum required fields
        
        Args:
            metadata: Extracted metadata dictionary
            
        Returns:
            True if metadata is valid
        """
        required_fields = ['SourceFile', 'FileType']
        return all(field in metadata for field in required_fields)
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics from command builder
        
        Returns:
            Performance metrics dictionary
        """
        return self.command_builder.get_optimization_info()