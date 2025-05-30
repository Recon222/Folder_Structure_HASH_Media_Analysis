# core/adaptive_file_operations.py
from typing import List, Dict, Optional, Callable, Any
from pathlib import Path
import time
import shutil
import os
import platform
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import psutil

from .adaptive_performance import AdaptivePerformanceController, WorkloadPriority
from .workload_analyzer import WorkloadAnalyzer

class AdaptiveFileOperations:
    """File operations with adaptive performance control"""
    
    def __init__(self, progress_callback: Optional[Callable] = None):
        self.controller = AdaptivePerformanceController()
        self.logger = logging.getLogger(__name__)
        self.progress_callback = progress_callback
        self.cancelled = False
        
        # Performance tracking for real-time monitoring
        self.start_time = None
        self.total_bytes = 0
        self.bytes_copied = 0
        self.files_completed = 0
        self.total_files = 0
        self.current_speed_mbps = 0.0
        self.average_speed_mbps = 0.0
        self.speed_history = []
        self.last_update_time = 0
        self.last_bytes_copied = 0
        
    def cancel(self):
        """Cancel ongoing operations"""
        self.cancelled = True
        
    def _reset_performance_tracking(self, files: List[Path]):
        """Reset performance tracking for new operation"""
        self.start_time = time.time()
        self.total_bytes = sum(f.stat().st_size for f in files if f.exists())
        self.bytes_copied = 0
        self.files_completed = 0
        self.total_files = len(files)
        self.current_speed_mbps = 0.0
        self.average_speed_mbps = 0.0
        self.speed_history = []
        self.last_update_time = self.start_time
        self.last_bytes_copied = 0
        
    def _update_speed_metrics(self, bytes_copied_delta: int = 0):
        """Update real-time speed metrics"""
        current_time = time.time()
        time_delta = current_time - self.last_update_time
        
        if bytes_copied_delta > 0:
            self.bytes_copied += bytes_copied_delta
        
        # Calculate current speed (MB/s) - update every 0.5 seconds minimum
        if time_delta >= 0.5:
            bytes_delta = self.bytes_copied - self.last_bytes_copied
            if time_delta > 0:
                current_speed_bps = bytes_delta / time_delta
                self.current_speed_mbps = current_speed_bps / (1024 * 1024)
                
                # Add to history (keep last 20 samples for smoothing)
                self.speed_history.append(self.current_speed_mbps)
                if len(self.speed_history) > 20:
                    self.speed_history.pop(0)
                
                # Calculate average speed
                if self.speed_history:
                    # Use recent average for smoother display
                    recent_samples = self.speed_history[-5:]
                    self.current_speed_mbps = sum(recent_samples) / len(recent_samples)
            
            self.last_update_time = current_time
            self.last_bytes_copied = self.bytes_copied
            
        # Calculate overall average speed
        total_time = current_time - self.start_time
        if total_time > 0:
            self.average_speed_mbps = self.bytes_copied / (total_time * 1024 * 1024)
            
    def _get_progress_message(self, file_name: str = "") -> str:
        """Generate detailed progress message with speed info"""
        if self.total_files == 0:
            return "Preparing..."
            
        progress_pct = int((self.files_completed / self.total_files) * 100)
        
        # Format file size info
        if self.total_bytes > 0:
            copied_mb = self.bytes_copied / (1024 * 1024)
            total_mb = self.total_bytes / (1024 * 1024)
            size_info = f" ({copied_mb:.1f}/{total_mb:.1f} MB)"
        else:
            size_info = ""
            
        # Format speed info
        if self.current_speed_mbps > 0:
            speed_info = f" @ {self.current_speed_mbps:.1f} MB/s"
        else:
            speed_info = ""
            
        # Estimate time remaining
        if self.current_speed_mbps > 0 and self.total_bytes > 0:
            remaining_bytes = self.total_bytes - self.bytes_copied
            remaining_mb = remaining_bytes / (1024 * 1024)
            eta_seconds = remaining_mb / self.current_speed_mbps
            
            if eta_seconds < 60:
                eta_info = f" (ETA: {eta_seconds:.0f}s)"
            elif eta_seconds < 3600:
                eta_info = f" (ETA: {eta_seconds/60:.1f}m)"
            else:
                eta_info = f" (ETA: {eta_seconds/3600:.1f}h)"
        else:
            eta_info = ""
            
        base_msg = f"Processing {file_name} ({self.files_completed}/{self.total_files})"
        return f"{base_msg}{size_info}{speed_info}{eta_info}"
        
    def _get_completion_summary(self) -> Dict[str, Any]:
        """Generate completion summary with statistics"""
        total_time = time.time() - self.start_time if self.start_time else 0
        
        return {
            'files_processed': self.files_completed,
            'total_bytes': self.total_bytes,
            'total_time_seconds': total_time,
            'average_speed_mbps': self.average_speed_mbps,
            'peak_speed_mbps': max(self.speed_history) if self.speed_history else 0,
            'total_size_mb': self.total_bytes / (1024 * 1024),
            'efficiency_score': min(self.average_speed_mbps / 100, 1.0) if self.average_speed_mbps > 0 else 0
        }
        
    def copy_files_adaptive(self, files: List[Path], destination: Path, 
                          calculate_hash: bool = True) -> Dict:
        """Copy files with fully adaptive optimization"""
        
        # Reset cancellation flag
        self.cancelled = False
        
        # Initialize performance tracking
        self._reset_performance_tracking(files)
        
        # Ensure destination exists
        destination.mkdir(parents=True, exist_ok=True)
        
        # Get optimal configuration
        config = self.controller.get_optimal_configuration(files, destination)
        
        self.logger.info(f"Starting adaptive copy with config: {config}")
        
        # Apply configuration
        results = {}
        start_time = time.time()
        
        try:
            # Create appropriate executor based on priority
            if config['priority'] == WorkloadPriority.LATENCY:
                results = self._copy_latency_optimized(files, destination, config, calculate_hash)
            elif config['priority'] == WorkloadPriority.THROUGHPUT:
                results = self._copy_throughput_optimized(files, destination, config, calculate_hash)
            else:
                results = self._copy_balanced(files, destination, config, calculate_hash)
                
        except Exception as e:
            self.logger.error(f"Copy operation failed: {e}")
            raise
            
        finally:
            # Update metrics
            duration = time.time() - start_time
            total_size = sum(f.stat().st_size for f in files if f.exists())
            success = all(r.get('success', False) for r in results.values())
            
            self.controller.update_performance_metrics(
                'copy', duration, total_size, success
            )
            
        # Add completion statistics to results
        completion_stats = self._get_completion_summary()
        results['_performance_stats'] = completion_stats
        
        # Log completion summary
        stats = completion_stats
        self.logger.info(f"Copy completed: {stats['files_processed']} files, "
                        f"{stats['total_size_mb']:.1f} MB in {stats['total_time_seconds']:.1f}s "
                        f"(avg: {stats['average_speed_mbps']:.1f} MB/s, "
                        f"peak: {stats['peak_speed_mbps']:.1f} MB/s)")
            
        return results
    
    def _copy_latency_optimized(self, files: List[Path], destination: Path, 
                               config: Dict, calculate_hash: bool) -> Dict:
        """Copy optimized for low latency"""
        results = {}
        
        # Limited workers for low latency
        workers = min(config['workers'], 4)
        
        # Process files immediately with small buffers
        with ThreadPoolExecutor(max_workers=workers) as executor:
            # Submit all files at once for quickest start
            future_to_file = {
                executor.submit(
                    self._copy_single_file,
                    file, destination, config['buffer_size'],
                    calculate_hash, config.get('use_direct_io', False)
                ): file
                for file in files
            }
            
            completed = 0
            total = len(files)
            
            for future in as_completed(future_to_file):
                if self.cancelled:
                    # Cancel remaining futures
                    for f in future_to_file:
                        f.cancel()
                    break
                    
                file = future_to_file[future]
                try:
                    result = future.result()
                    results[str(file)] = result
                    
                    # Update performance tracking
                    self.files_completed += 1
                    if result.get('success') and result.get('size'):
                        self._update_speed_metrics(result['size'])
                    
                    completed += 1
                    if self.progress_callback:
                        progress = int((completed / total) * 100)
                        message = self._get_progress_message(file.name)
                        self.progress_callback(progress, message)
                        
                except Exception as e:
                    results[str(file)] = {
                        'success': False,
                        'error': str(e)
                    }
                    self.logger.error(f"Failed to copy {file}: {e}")
                    
        return results
    
    def _copy_throughput_optimized(self, files: List[Path], destination: Path,
                                  config: Dict, calculate_hash: bool) -> Dict:
        """Copy optimized for maximum throughput"""
        results = {}
        
        # Group files by size for optimal batching
        thresholds = WorkloadAnalyzer.calculate_adaptive_thresholds(files)
        file_groups = WorkloadAnalyzer.optimize_batch_sizes(files, thresholds)
        
        # Process groups with appropriate parallelism
        for group_name, batches in file_groups.items():
            if self.cancelled:
                break
                
            # Determine workers for this group
            if group_name == 'tiny':
                group_workers = min(config['workers'], 16)
            elif group_name == 'small':
                group_workers = min(config['workers'], 8)
            elif group_name == 'medium':
                group_workers = min(config['workers'], 4)
            else:  # large or huge
                group_workers = min(config['workers'], 2)
                
            # Process batches
            for batch in batches:
                if self.cancelled:
                    break
                    
                batch_results = self._process_batch_parallel(
                    batch, destination, config, calculate_hash, group_workers
                )
                results.update(batch_results)
                
        return results
    
    def _copy_balanced(self, files: List[Path], destination: Path,
                      config: Dict, calculate_hash: bool) -> Dict:
        """Balanced copy for mixed workloads"""
        results = {}
        
        # Adaptive approach - analyze files and use appropriate strategy
        thresholds = WorkloadAnalyzer.calculate_adaptive_thresholds(files)
        
        # Split files into size categories
        small_files = []
        large_files = []
        
        for file in files:
            try:
                size = file.stat().st_size
                if size < thresholds['small']:
                    small_files.append(file)
                else:
                    large_files.append(file)
            except:
                continue
                
        # Process small files with high parallelism
        if small_files:
            small_results = self._process_batch_parallel(
                small_files, destination, config, calculate_hash,
                min(config['workers'], 8)
            )
            results.update(small_results)
            
        # Process large files with limited parallelism
        if large_files:
            large_results = self._process_batch_parallel(
                large_files, destination, config, calculate_hash,
                min(config['workers'], 3)
            )
            results.update(large_results)
            
        return results
    
    def _process_batch_parallel(self, files: List[Path], destination: Path,
                               config: Dict, calculate_hash: bool,
                               workers: int) -> Dict:
        """Process a batch of files in parallel"""
        results = {}
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_file = {
                executor.submit(
                    self._copy_single_file,
                    file, destination, config['buffer_size'],
                    calculate_hash, config.get('use_direct_io', False)
                ): file
                for file in files
            }
            
            completed = 0
            total = len(files)
            
            for future in as_completed(future_to_file):
                if self.cancelled:
                    for f in future_to_file:
                        f.cancel()
                    break
                    
                file = future_to_file[future]
                try:
                    result = future.result()
                    results[str(file)] = result
                    
                    completed += 1
                    if self.progress_callback:
                        progress = int((completed / total) * 100)
                        self.progress_callback(progress, f"Processed {file.name}")
                        
                except Exception as e:
                    results[str(file)] = {
                        'success': False,
                        'error': str(e)
                    }
                    self.logger.error(f"Failed to process {file}: {e}")
                    
        return results
    
    def _copy_single_file(self, src: Path, dst_dir: Path, buffer_size: int,
                         calculate_hash: bool, use_direct_io: bool) -> Dict:
        """Copy a single file with optimal settings"""
        dst = dst_dir / src.name
        result = {
            'source': str(src),
            'destination': str(dst),
            'size': 0,
            'success': False
        }
        
        try:
            # Get file size
            file_size = src.stat().st_size
            result['size'] = file_size
            
            # Initialize hash if requested
            hasher = hashlib.sha256() if calculate_hash else None
            
            # Copy with optimal buffer
            start_time = time.time()
            
            if (use_direct_io and hasattr(os, 'O_DIRECT') and 
                platform.system() == 'Linux' and src.stat().st_size > 100_000_000):
                # Direct I/O for large files (Linux only)
                try:
                    self._copy_direct_io(src, dst, buffer_size, hasher)
                except (ValueError, OSError) as e:
                    # Fall back to standard I/O if Direct I/O fails
                    self.logger.warning(f"Direct I/O failed for {src.name}, using standard I/O: {e}")
                    use_direct_io = False
            
            if not use_direct_io:
                # Standard buffered I/O
                with open(src, 'rb') as fsrc:
                    with open(dst, 'wb') as fdst:
                        while True:
                            if self.cancelled:
                                dst.unlink()  # Clean up partial file
                                result['cancelled'] = True
                                return result
                                
                            chunk = fsrc.read(buffer_size)
                            if not chunk:
                                break
                                
                            fdst.write(chunk)
                            if hasher:
                                hasher.update(chunk)
                                
            # Copy metadata
            shutil.copystat(src, dst)
            
            # Record results
            result['success'] = True
            result['duration'] = time.time() - start_time
            result['throughput_mbps'] = (file_size / (1024 * 1024)) / result['duration'] if result['duration'] > 0 else 0
            
            if hasher:
                result['hash'] = hasher.hexdigest()
                
        except Exception as e:
            result['error'] = str(e)
            if dst.exists():
                try:
                    dst.unlink()  # Clean up failed copy
                except:
                    pass
                    
        return result
    
    def _copy_direct_io(self, src: Path, dst: Path, buffer_size: int,
                       hasher: Optional[object]) -> None:
        """Copy using direct I/O (Linux only)"""
        import platform
        
        # Only support Direct I/O on Linux systems
        if platform.system() != 'Linux' or not hasattr(os, 'O_DIRECT'):
            raise ValueError("Direct I/O not supported on this platform")
        
        # Direct I/O requires aligned buffers
        aligned_buffer_size = (buffer_size + 511) & ~511  # Align to 512 bytes
        
        fd_src = os.open(src, os.O_RDONLY | os.O_DIRECT)
        fd_dst = os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_DIRECT, 0o666)
        
        try:
            while True:
                # Use aligned buffer for direct I/O
                data = os.read(fd_src, aligned_buffer_size)
                if not data:
                    break
                    
                if self.cancelled:
                    raise Exception("Operation cancelled")
                    
                os.write(fd_dst, data)
                if hasher:
                    hasher.update(data)
                    
        finally:
            os.close(fd_src)
            os.close(fd_dst)
    
    def hash_files_adaptive(self, files: List[Path]) -> Dict[str, str]:
        """Calculate file hashes with adaptive optimization"""
        # Get optimal configuration
        config = self.controller.get_optimal_configuration(files, Path.cwd())
        
        # Determine optimal worker count for hashing
        workers = min(config['workers'], os.cpu_count() or 4)
        
        results = {}
        
        # Check if we should use hashwise (if available)
        try:
            from hashwise import ParallelHasher
            # Use hashwise for parallel hashing
            if len(files) >= 4:
                hasher = ParallelHasher(
                    algorithm='sha256',
                    workers=workers,
                    chunk_size='auto'
                )
                hash_results = hasher.hash_files(files)
                return {str(path): hash_val for path, hash_val in hash_results.items()}
        except ImportError:
            # Hashwise not available, use our implementation
            pass
            
        # Fallback to our parallel implementation
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_file = {
                executor.submit(self._hash_single_file, file): file
                for file in files
            }
            
            for future in as_completed(future_to_file):
                file = future_to_file[future]
                try:
                    hash_value = future.result()
                    results[str(file)] = hash_value
                except Exception as e:
                    self.logger.error(f"Failed to hash {file}: {e}")
                    results[str(file)] = None
                    
        return results
    
    def _hash_single_file(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of a single file"""
        hasher = hashlib.sha256()
        
        # Determine optimal buffer size based on file size
        file_size = file_path.stat().st_size
        if file_size < 10_000_000:  # < 10MB
            buffer_size = 65536  # 64KB
        elif file_size < 100_000_000:  # < 100MB
            buffer_size = 1048576  # 1MB
        else:
            buffer_size = 10485760  # 10MB
            
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(buffer_size)
                if not chunk:
                    break
                hasher.update(chunk)
                
        return hasher.hexdigest()