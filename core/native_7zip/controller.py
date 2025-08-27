#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Native 7zip controller for high-performance archive operations
Manages subprocess execution with progress monitoring and Result-based error handling
"""

import subprocess
import time
import re
import os
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List
import threading
from dataclasses import dataclass, field

from .binary_manager import Native7ZipBinaryManager
from .command_builder import ForensicCommandBuilder
from core.result_types import Result, ArchiveOperationResult
from core.exceptions import ArchiveError, ValidationError
from core.logger import logger


@dataclass
class Native7ZipMetrics:
    """Performance metrics for native 7zip operations"""
    start_time: float = 0.0
    end_time: float = 0.0
    total_files: int = 0
    files_processed: int = 0
    bytes_processed: int = 0
    archive_size: int = 0
    command_used: List[str] = field(default_factory=list)
    exit_code: int = 0
    execution_time: float = 0.0
    average_speed_mbps: float = 0.0
    method: str = "native_7zip"
    
    def calculate_summary(self):
        """Calculate summary statistics"""
        self.execution_time = self.end_time - self.start_time
        if self.execution_time > 0 and self.bytes_processed > 0:
            self.average_speed_mbps = (self.bytes_processed / (1024 * 1024)) / self.execution_time


class Native7ZipController:
    """
    Main controller for native 7zip operations with progress monitoring
    
    Integrates with existing Result-based architecture and provides the same
    interface as BufferedZipOperations for seamless hybrid operation.
    """
    
    def __init__(self, progress_callback: Optional[Callable[[int, str], None]] = None):
        """
        Initialize native 7zip controller
        
        Args:
            progress_callback: Function that receives (percentage, status_message)
        """
        self.binary_manager = Native7ZipBinaryManager()
        self.command_builder = ForensicCommandBuilder()
        self.progress_callback = progress_callback
        self.cancelled = False
        self.current_process: Optional[subprocess.Popen] = None
        self.metrics = Native7ZipMetrics()
        
        # Thread for progress monitoring
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()
        
        # Log availability on init
        if self.is_available():
            logger.info("Native 7zip controller initialized successfully")
            logger.info(f"Binary: {self.binary_manager.get_binary_path()}")
            logger.info(f"Threads: {self.command_builder.optimal_threads}")
        else:
            logger.warning("Native 7zip controller initialized but 7za.exe not available")
    
    def is_available(self) -> bool:
        """Check if native 7zip is available for use"""
        return self.binary_manager.is_available()
    
    def create_archive(self, source_path: Path, output_path: Path, 
                      compression_mode: str = "store") -> Result[ArchiveOperationResult]:
        """
        Create archive using native 7zip with performance monitoring
        
        Args:
            source_path: Directory or file to archive
            output_path: Output archive path  
            compression_mode: "store" (fastest), "fast", "normal", "max"
            
        Returns:
            Result containing ArchiveOperationResult with performance metrics
        """
        # Reset metrics
        self.metrics = Native7ZipMetrics()
        self.metrics.start_time = time.time()
        self.cancelled = False
        
        # Validation
        validation_result = self._validate_inputs(source_path, output_path)
        if not validation_result.success:
            return validation_result
        
        # Check availability
        if not self.is_available():
            return Result.error(ArchiveError(
                "Native 7zip not available",
                user_message="High-performance archiving unavailable. Check 7za.exe installation."
            ))
        
        # Calculate source metrics
        source_metrics = self._calculate_source_metrics(source_path)
        self.metrics.total_files = source_metrics['file_count']
        self.metrics.bytes_processed = source_metrics['total_bytes']  # Will be updated during processing
        
        # Build command
        binary_path = self.binary_manager.get_binary_path()
        cmd = self.command_builder.build_archive_command(
            binary_path, source_path, output_path, compression_mode
        )
        self.metrics.command_used = cmd
        
        # Execute with monitoring
        result = self._execute_with_monitoring(cmd, source_path, output_path)
        
        # Finalize metrics
        self.metrics.end_time = time.time()
        self.metrics.calculate_summary()
        
        return result
    
    def _validate_inputs(self, source_path: Path, output_path: Path) -> Result[None]:
        """Validate input parameters"""
        try:
            if not source_path or not source_path.exists():
                return Result.error(ValidationError(
                    field_errors={"source_path": f"Source path does not exist: {source_path}"},
                    user_message="Source directory or file not found."
                ))
            
            if not output_path or not output_path.parent.exists():
                return Result.error(ValidationError(
                    field_errors={"output_path": f"Output directory does not exist: {output_path.parent}"},
                    user_message="Output directory does not exist."
                ))
            
            # Check write permissions
            try:
                test_file = output_path.parent / f"test_write_{os.getpid()}.tmp"
                test_file.touch()
                test_file.unlink()
            except (PermissionError, OSError) as e:
                return Result.error(ValidationError(
                    field_errors={"output_path": f"Cannot write to output directory: {e}"},
                    user_message="Cannot write to output directory. Check permissions."
                ))
            
            return Result.success(None)
            
        except Exception as e:
            return Result.error(ValidationError(
                field_errors={"validation": f"Validation error: {e}"},
                user_message="Input validation failed."
            ))
    
    def _calculate_source_metrics(self, source_path: Path) -> Dict[str, Any]:
        """Calculate metrics about the source data"""
        try:
            if source_path.is_file():
                return {
                    'file_count': 1,
                    'total_bytes': source_path.stat().st_size,
                    'is_directory': False
                }
            else:
                files = list(source_path.rglob('*'))
                file_paths = [f for f in files if f.is_file()]
                total_bytes = sum(f.stat().st_size for f in file_paths)
                
                return {
                    'file_count': len(file_paths),
                    'total_bytes': total_bytes,
                    'is_directory': True,
                    'directory_count': len([f for f in files if f.is_dir()])
                }
        except Exception as e:
            logger.warning(f"Error calculating source metrics: {e}")
            return {
                'file_count': 0,
                'total_bytes': 0,
                'is_directory': source_path.is_dir(),
                'error': str(e)
            }
    
    def _execute_with_monitoring(self, cmd: List[str], source_path: Path, 
                                output_path: Path) -> Result[ArchiveOperationResult]:
        """Execute 7zip command with real-time progress monitoring"""
        try:
            logger.info(f"Executing native 7zip: {' '.join(cmd[:3])}... (full command in debug)")
            logger.info(f"Full command: {' '.join(cmd)}")  # Temporarily show full command for debugging
            
            # Report starting progress
            self._report_progress(0, f"Starting native 7zip archive: {output_path.name}")
            
            # Start process
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                cwd=source_path.parent if source_path.is_dir() else source_path.parent,
                startupinfo=self._get_subprocess_startupinfo()
            )
            
            # Start progress monitoring in separate thread
            self._stop_monitoring.clear()
            self._monitor_thread = threading.Thread(
                target=self._monitor_progress,
                args=(self.current_process,),
                daemon=True
            )
            self._monitor_thread.start()
            
            # Wait for completion
            stdout, stderr = self.current_process.communicate()
            self.metrics.exit_code = self.current_process.returncode
            
            # Stop monitoring
            self._stop_monitoring.set()
            if self._monitor_thread and self._monitor_thread.is_alive():
                self._monitor_thread.join(timeout=1.0)
            
            # Process results
            if self.cancelled:
                return Result.error(ArchiveError(
                    "Archive operation was cancelled by user",
                    user_message="Archive creation was cancelled."
                ))
            
            if self.metrics.exit_code == 0:
                # Success - get archive size
                if output_path.exists():
                    self.metrics.archive_size = output_path.stat().st_size
                
                # Create success result
                result = ArchiveOperationResult.create_successful(
                    created_archives=[output_path],
                    compression_level="store" if "mx0" in " ".join(cmd) else "compressed",
                    metadata={
                        'method': 'native_7zip',
                        'execution_time': self.metrics.execution_time,
                        'average_speed_mbps': self.metrics.average_speed_mbps,
                        'total_files': self.metrics.total_files,
                        'files_processed': self.metrics.files_processed,
                        'bytes_processed': self.metrics.bytes_processed,
                        'archive_size': self.metrics.archive_size,
                        'exit_code': self.metrics.exit_code,
                        'threads_used': self.command_builder.optimal_threads,
                        'command_summary': f"7za a -mx0 -mmt{self.command_builder.optimal_threads}"
                    }
                )
                
                # Final progress report
                speed_text = f" ({self.metrics.average_speed_mbps:.1f} MB/s)" if self.metrics.average_speed_mbps > 0 else ""
                self._report_progress(100, f"Archive complete: {output_path.name}{speed_text}")
                
                logger.info(f"Native 7zip completed successfully in {self.metrics.execution_time:.2f}s")
                return result
            else:
                # Error - parse error message
                error_message = self._parse_7zip_error(self.metrics.exit_code, stderr)
                return Result.error(ArchiveError(
                    f"7zip failed with exit code {self.metrics.exit_code}: {error_message}",
                    archive_path=str(output_path),
                    user_message=f"Archive creation failed: {error_message}"
                ))
                
        except subprocess.TimeoutExpired:
            if self.current_process:
                self.current_process.kill()
            return Result.error(ArchiveError(
                "7zip operation timed out",
                user_message="Archive creation timed out. Try with smaller files."
            ))
        except FileNotFoundError:
            return Result.error(ArchiveError(
                f"7za.exe not found at expected location",
                user_message="7-Zip binary not found. Please check installation."
            ))
        except Exception as e:
            return Result.error(ArchiveError(
                f"Unexpected error during 7zip execution: {e}",
                archive_path=str(output_path),
                user_message="Archive creation failed due to an unexpected error."
            ))
    
    def _get_subprocess_startupinfo(self):
        """Get subprocess startup info for Windows (hide console window)"""
        if os.name == 'nt':  # Windows
            import subprocess
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            return startupinfo
        return None
    
    def _monitor_progress(self, process: subprocess.Popen):
        """Monitor subprocess output for progress updates"""
        try:
            while not self._stop_monitoring.is_set() and process.poll() is None:
                if self.cancelled:
                    process.terminate()
                    break
                
                # Read output with timeout
                try:
                    # Read available stdout
                    if process.stdout and process.stdout.readable():
                        line = process.stdout.readline()
                        if line:
                            self._parse_progress_line(line.strip())
                except Exception as e:
                    logger.debug(f"Progress monitoring error: {e}")
                
                # Small delay to prevent excessive CPU usage
                time.sleep(0.1)
                
        except Exception as e:
            logger.error(f"Error in progress monitoring thread: {e}")
    
    def _parse_progress_line(self, line: str):
        """Parse 7zip progress output for status updates"""
        if not line:
            return
        
        try:
            # 7zip with -bb1 outputs basic progress information
            # Look for percentage patterns or file information
            
            # Try to extract percentage (7zip sometimes shows percentages)
            percent_match = re.search(r'(\d+)%', line)
            if percent_match:
                percentage = int(percent_match.group(1))
                self._report_progress(percentage, f"7zip: {line}")
                return
            
            # Look for file processing indicators
            if any(keyword in line.lower() for keyword in ['compressing', 'adding', 'processing']):
                self._report_progress(None, f"7zip: {line}")
                return
            
            # Generic status update
            if len(line) > 5 and not line.startswith('7-Zip'):  # Skip header lines
                self._report_progress(None, f"7zip: {line[:50]}...")
                
        except Exception as e:
            logger.debug(f"Error parsing progress line '{line}': {e}")
    
    def _parse_7zip_error(self, exit_code: int, stderr_output: str) -> str:
        """Convert 7zip exit codes and stderr to meaningful error messages"""
        error_codes = {
            0: "Success",
            1: "Warning (non-fatal errors)", 
            2: "Fatal error",
            7: "Command line error",
            8: "Not enough memory for operation",
            255: "User stopped the process"
        }
        
        base_message = error_codes.get(exit_code, f"Unknown error (exit code {exit_code})")
        
        # Add stderr details if available
        if stderr_output:
            # Clean up stderr (remove common 7zip noise)
            clean_stderr = stderr_output.strip()
            if clean_stderr and not clean_stderr.startswith('7-Zip'):
                return f"{base_message}: {clean_stderr}"
        
        return base_message
    
    def _report_progress(self, percentage: Optional[int], message: str):
        """Report progress if callback is available"""
        if self.progress_callback:
            # Use a reasonable percentage if none provided
            if percentage is None:
                percentage = min(50, max(10, self.metrics.files_processed * 100 // max(1, self.metrics.total_files)))
            self.progress_callback(percentage, message)
    
    def cancel(self):
        """Cancel current operation"""
        self.cancelled = True
        if self.current_process:
            try:
                self.current_process.terminate()
                # Give it a moment to terminate gracefully
                try:
                    self.current_process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't terminate
                    self.current_process.kill()
            except Exception as e:
                logger.error(f"Error cancelling 7zip process: {e}")
    
    def get_metrics(self) -> Native7ZipMetrics:
        """Get performance metrics from last operation"""
        return self.metrics
    
    def get_diagnostic_info(self) -> Dict[str, Any]:
        """Get comprehensive diagnostic information"""
        return {
            'binary_manager': self.binary_manager.get_platform_support_info(),
            'command_builder': self.command_builder.get_optimization_info(),
            'controller_status': {
                'available': self.is_available(),
                'cancelled': self.cancelled,
                'current_process_active': self.current_process is not None and self.current_process.poll() is None,
                'last_metrics': {
                    'execution_time': self.metrics.execution_time,
                    'average_speed_mbps': self.metrics.average_speed_mbps,
                    'files_processed': self.metrics.files_processed,
                    'total_files': self.metrics.total_files,
                    'exit_code': self.metrics.exit_code
                }
            }
        }