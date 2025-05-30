# core/adaptive_file_operations.py
from typing import List, Dict, Optional, Callable, Any
from pathlib import Path
import time
import shutil
import os
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
        
    def cancel(self):
        """Cancel ongoing operations"""
        self.cancelled = True
        
    def copy_files_adaptive(self, files: List[Path], destination: Path, 
                          calculate_hash: bool = True) -> Dict:
        """Copy files with fully adaptive optimization"""
        
        # Reset cancellation flag
        self.cancelled = False
        
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
                    
                    completed += 1
                    if self.progress_callback:
                        progress = int((completed / total) * 100)
                        self.progress_callback(progress, f"Copied {file.name}")
                        
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
            
            if use_direct_io and hasattr(os, 'O_DIRECT'):
                # Direct I/O for large files (Linux only)
                self._copy_direct_io(src, dst, buffer_size, hasher)
            else:
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
                       hasher: Optional[hashlib._Hash]) -> None:
        """Copy using direct I/O (Linux only)"""
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