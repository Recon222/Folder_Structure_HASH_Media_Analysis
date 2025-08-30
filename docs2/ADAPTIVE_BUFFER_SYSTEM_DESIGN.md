# Adaptive Buffer System Design for Dynamic Performance Optimization

## Executive Summary

This document outlines a comprehensive system for programmatically detecting hardware characteristics and dynamically adjusting file I/O buffer sizes for optimal performance in the Folder Structure Utility. The system adapts to varying hardware configurations from high-end i9 systems with NVMe SSDs to field forensic workstations with USB3 sources and HDD destinations.

## System Architecture Overview

### Core Components

1. **Hardware Detection Engine** - Identifies storage types, CPU characteristics, and memory configuration
2. **Performance Monitor** - Real-time throughput and resource usage tracking  
3. **Adaptive Buffer Manager** - Dynamic buffer size adjustment based on hardware and performance
4. **Learning System** - Machine learning approach to optimize buffer sizes over time

## Hardware Detection Implementation

### Storage Type Detection

```python
import psutil
import os
import platform
from pathlib import Path
from typing import Dict, Optional, Tuple
from enum import Enum

class StorageType(Enum):
    NVME = "nvme"
    SSD = "ssd"
    HDD = "hdd"
    USB = "usb"
    NETWORK = "network"
    UNKNOWN = "unknown"

class HardwareDetector:
    """Advanced hardware detection for buffer optimization"""
    
    def __init__(self):
        self.platform = platform.system()
        self._cache = {}
    
    def detect_storage_type(self, path: str) -> StorageType:
        """Detect storage type for given path"""
        if path in self._cache:
            return self._cache[path]
        
        storage_type = StorageType.UNKNOWN
        
        if self.platform == "Linux":
            storage_type = self._detect_linux_storage(path)
        elif self.platform == "Windows":
            storage_type = self._detect_windows_storage(path)
        elif self.platform == "Darwin":  # macOS
            storage_type = self._detect_macos_storage(path)
        
        self._cache[path] = storage_type
        return storage_type
    
    def _detect_linux_storage(self, path: str) -> StorageType:
        """Linux-specific storage detection using /sys filesystem"""
        try:
            # Get the device for the path
            stat_result = os.stat(path)
            device_id = stat_result.st_dev
            
            # Find the block device
            for partition in psutil.disk_partitions():
                if partition.mountpoint in path:
                    device_name = partition.device.split('/')[-1]
                    
                    # Check for NVMe
                    if 'nvme' in device_name:
                        return StorageType.NVME
                    
                    # Check rotational status
                    base_device = device_name.rstrip('0123456789')
                    rotational_path = f'/sys/block/{base_device}/queue/rotational'
                    
                    if os.path.exists(rotational_path):
                        with open(rotational_path, 'r') as f:
                            if f.read().strip() == '0':
                                return StorageType.SSD
                            else:
                                return StorageType.HDD
                    
                    # Check for USB
                    if self._is_usb_device(base_device):
                        return StorageType.USB
            
        except Exception as e:
            print(f"Error detecting storage type: {e}")
        
        return StorageType.UNKNOWN
    
    def _detect_windows_storage(self, path: str) -> StorageType:
        """Windows-specific storage detection using WMI"""
        try:
            import win32file
            import win32api
            
            # Get drive letter
            drive_letter = Path(path).anchor
            
            # Use WMI for detailed hardware info
            try:
                import wmi
                c = wmi.WMI()
                
                # Get physical disk info
                for disk in c.Win32_DiskDrive():
                    if 'NVMe' in disk.Model or 'NVME' in disk.Model:
                        return StorageType.NVME
                    elif 'USB' in disk.InterfaceType:
                        return StorageType.USB
                    elif disk.MediaType == 'Fixed hard disk media':
                        # Check for SSD characteristics
                        if hasattr(disk, 'NominalMediaRotationRate'):
                            if disk.NominalMediaRotationRate == 1:
                                return StorageType.SSD
                            elif disk.NominalMediaRotationRate > 1:
                                return StorageType.HDD
                        
            except ImportError:
                # Fallback without WMI
                drive_type = win32file.GetDriveType(drive_letter)
                if drive_type == win32file.DRIVE_REMOVABLE:
                    return StorageType.USB
                elif drive_type == win32file.DRIVE_FIXED:
                    return StorageType.SSD  # Default assumption for fixed drives
                    
        except Exception as e:
            print(f"Error detecting Windows storage: {e}")
        
        return StorageType.UNKNOWN
    
    def _detect_macos_storage(self, path: str) -> StorageType:
        """macOS-specific storage detection"""
        try:
            import subprocess
            
            # Use diskutil to get device info
            result = subprocess.run(['diskutil', 'info', path], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                output = result.stdout.lower()
                if 'solid state' in output or 'ssd' in output:
                    if 'nvme' in output:
                        return StorageType.NVME
                    return StorageType.SSD
                elif 'rotational' in output or 'hdd' in output:
                    return StorageType.HDD
                elif 'usb' in output or 'external' in output:
                    return StorageType.USB
                    
        except Exception as e:
            print(f"Error detecting macOS storage: {e}")
        
        return StorageType.UNKNOWN
    
    def _is_usb_device(self, device: str) -> bool:
        """Check if device is USB connected"""
        usb_path = f'/sys/block/{device}/removable'
        if os.path.exists(usb_path):
            with open(usb_path, 'r') as f:
                return f.read().strip() == '1'
        return False
    
    def get_cpu_info(self) -> Dict:
        """Get CPU characteristics including cache sizes"""
        cpu_info = {
            'logical_cores': psutil.cpu_count(logical=True),
            'physical_cores': psutil.cpu_count(logical=False),
            'l2_cache_size': None,
            'l3_cache_size': None,
            'frequency': None
        }
        
        # Get CPU frequency
        try:
            freq = psutil.cpu_freq()
            if freq:
                cpu_info['frequency'] = freq.current
        except:
            pass
        
        # Platform-specific cache detection
        if self.platform == "Linux":
            cpu_info.update(self._get_linux_cpu_cache())
        elif self.platform == "Windows":
            cpu_info.update(self._get_windows_cpu_cache())
        
        return cpu_info
    
    def _get_linux_cpu_cache(self) -> Dict:
        """Get CPU cache sizes on Linux"""
        cache_info = {}
        
        try:
            # Read cache information from /sys
            cpu0_cache = '/sys/devices/system/cpu/cpu0/cache'
            if os.path.exists(cpu0_cache):
                for cache_level in os.listdir(cpu0_cache):
                    if cache_level.startswith('index'):
                        level_path = os.path.join(cpu0_cache, cache_level)
                        
                        # Read cache level
                        level_file = os.path.join(level_path, 'level')
                        if os.path.exists(level_file):
                            with open(level_file, 'r') as f:
                                level = int(f.read().strip())
                            
                            # Read cache size
                            size_file = os.path.join(level_path, 'size')
                            if os.path.exists(size_file):
                                with open(size_file, 'r') as f:
                                    size_str = f.read().strip()
                                    # Convert to bytes
                                    if size_str.endswith('K'):
                                        size = int(size_str[:-1]) * 1024
                                    elif size_str.endswith('M'):
                                        size = int(size_str[:-1]) * 1024 * 1024
                                    else:
                                        size = int(size_str)
                                    
                                    cache_info[f'l{level}_cache_size'] = size
                                    
        except Exception as e:
            print(f"Error reading CPU cache info: {e}")
        
        return cache_info
    
    def _get_windows_cpu_cache(self) -> Dict:
        """Get CPU cache sizes on Windows using WMI"""
        cache_info = {}
        
        try:
            import wmi
            c = wmi.WMI()
            
            for cache in c.Win32_CacheMemory():
                level = cache.Level
                size = cache.MaxCacheSize * 1024  # Convert KB to bytes
                cache_info[f'l{level}_cache_size'] = size
                
        except Exception as e:
            print(f"Error reading Windows CPU cache info: {e}")
        
        return cache_info
    
    def get_memory_info(self) -> Dict:
        """Get system memory information"""
        mem = psutil.virtual_memory()
        
        return {
            'total': mem.total,
            'available': mem.available,
            'percent_used': mem.percent,
            'free': mem.free,
            'buffers': getattr(mem, 'buffers', 0),
            'cached': getattr(mem, 'cached', 0)
        }
```

### Performance Monitoring System

```python
import time
import threading
from collections import deque
from dataclasses import dataclass
from typing import List, Optional, Callable

@dataclass
class PerformanceMetrics:
    """Real-time performance metrics"""
    timestamp: float
    throughput_mbps: float
    cpu_percent: float
    memory_percent: float
    io_wait_percent: float
    buffer_size: int
    operation_type: str

class PerformanceMonitor:
    """Real-time performance monitoring and analysis"""
    
    def __init__(self, history_size: int = 100):
        self.history_size = history_size
        self.metrics_history: deque = deque(maxlen=history_size)
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._callbacks: List[Callable] = []
    
    def start_monitoring(self, interval: float = 1.0):
        """Start background performance monitoring"""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, 
            args=(interval,)
        )
        self._monitor_thread.daemon = True
        self._monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop background monitoring"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join()
    
    def add_callback(self, callback: Callable[[PerformanceMetrics], None]):
        """Add callback for performance updates"""
        self._callbacks.append(callback)
    
    def _monitor_loop(self, interval: float):
        """Background monitoring loop"""
        while self._monitoring:
            try:
                # Collect system metrics
                cpu_percent = psutil.cpu_percent(interval=None)
                memory = psutil.virtual_memory()
                io_counters = psutil.disk_io_counters()
                
                # Calculate I/O wait if available
                io_wait = 0.0
                if hasattr(psutil, 'cpu_times'):
                    cpu_times = psutil.cpu_times()
                    if hasattr(cpu_times, 'iowait'):
                        io_wait = cpu_times.iowait
                
                # Create metrics snapshot
                metrics = PerformanceMetrics(
                    timestamp=time.time(),
                    throughput_mbps=0.0,  # Will be updated by operations
                    cpu_percent=cpu_percent,
                    memory_percent=memory.percent,
                    io_wait_percent=io_wait,
                    buffer_size=0,  # Will be updated by operations
                    operation_type="monitor"
                )
                
                self.metrics_history.append(metrics)
                
                # Notify callbacks
                for callback in self._callbacks:
                    try:
                        callback(metrics)
                    except Exception as e:
                        print(f"Error in performance callback: {e}")
                
                time.sleep(interval)
                
            except Exception as e:
                print(f"Error in performance monitoring: {e}")
                time.sleep(interval)
    
    def record_operation_metrics(self, throughput_mbps: float, 
                                buffer_size: int, operation_type: str):
        """Record metrics for a specific operation"""
        metrics = PerformanceMetrics(
            timestamp=time.time(),
            throughput_mbps=throughput_mbps,
            cpu_percent=psutil.cpu_percent(interval=None),
            memory_percent=psutil.virtual_memory().percent,
            io_wait_percent=0.0,  # Calculate if needed
            buffer_size=buffer_size,
            operation_type=operation_type
        )
        
        self.metrics_history.append(metrics)
        return metrics
    
    def get_recent_metrics(self, seconds: int = 30) -> List[PerformanceMetrics]:
        """Get metrics from the last N seconds"""
        cutoff_time = time.time() - seconds
        return [m for m in self.metrics_history if m.timestamp >= cutoff_time]
    
    def get_average_throughput(self, seconds: int = 30) -> float:
        """Calculate average throughput over recent period"""
        recent = self.get_recent_metrics(seconds)
        if not recent:
            return 0.0
        
        throughputs = [m.throughput_mbps for m in recent if m.throughput_mbps > 0]
        return sum(throughputs) / len(throughputs) if throughputs else 0.0
    
    def is_performance_degrading(self, threshold_percent: float = 20.0) -> bool:
        """Check if performance is degrading"""
        if len(self.metrics_history) < 10:
            return False
        
        recent_avg = self.get_average_throughput(10)  # Last 10 seconds
        older_avg = self.get_average_throughput(30)   # Last 30 seconds
        
        if older_avg == 0:
            return False
        
        degradation = ((older_avg - recent_avg) / older_avg) * 100
        return degradation > threshold_percent
```

### Adaptive Buffer Management

```python
from typing import Dict, Tuple
import math

class AdaptiveBufferManager:
    """Dynamic buffer size optimization based on hardware and performance"""
    
    def __init__(self, hardware_detector: HardwareDetector, 
                 performance_monitor: PerformanceMonitor):
        self.hardware_detector = hardware_detector
        self.performance_monitor = performance_monitor
        self.learning_history: Dict[str, List[Tuple[int, float]]] = {}
        
        # Buffer size constraints (in bytes)
        self.min_buffer_size = 8 * 1024        # 8KB minimum
        self.max_buffer_size = 128 * 1024 * 1024  # 128MB maximum
        
    def calculate_optimal_buffer_size(self, source_path: str, 
                                    dest_path: str, 
                                    file_size: int = 0) -> int:
        """Calculate optimal buffer size for given paths and file size"""
        
        # Detect hardware characteristics
        source_storage = self.hardware_detector.detect_storage_type(source_path)
        dest_storage = self.hardware_detector.detect_storage_type(dest_path)
        cpu_info = self.hardware_detector.get_cpu_info()
        memory_info = self.hardware_detector.get_memory_info()
        
        # Base buffer size calculation
        base_buffer = self._calculate_base_buffer(
            source_storage, dest_storage, cpu_info, memory_info
        )
        
        # Adjust for file size
        size_adjusted_buffer = self._adjust_for_file_size(base_buffer, file_size)
        
        # Apply performance-based adjustments
        performance_adjusted = self._adjust_for_performance(
            size_adjusted_buffer, source_path, dest_path
        )
        
        # Apply learning system adjustments
        final_buffer = self._apply_learned_adjustments(
            performance_adjusted, source_storage, dest_storage
        )
        
        # Ensure constraints
        return max(self.min_buffer_size, 
                  min(self.max_buffer_size, final_buffer))
    
    def _calculate_base_buffer(self, source_storage: StorageType, 
                              dest_storage: StorageType,
                              cpu_info: Dict, memory_info: Dict) -> int:
        """Calculate base buffer size based on hardware"""
        
        # Storage type multipliers
        storage_multipliers = {
            StorageType.NVME: 4.0,
            StorageType.SSD: 2.0,
            StorageType.HDD: 1.0,
            StorageType.USB: 0.5,
            StorageType.NETWORK: 0.25,
            StorageType.UNKNOWN: 1.0
        }
        
        # Base on the slower storage type
        slower_multiplier = min(
            storage_multipliers[source_storage],
            storage_multipliers[dest_storage]
        )
        
        # Base buffer (16KB for our optimal case)
        base_buffer = 16 * 1024
        
        # Apply storage multiplier
        storage_adjusted = int(base_buffer * slower_multiplier)
        
        # Adjust for CPU cache
        if cpu_info.get('l3_cache_size'):
            # Don't exceed 1/4 of L3 cache
            cache_limit = cpu_info['l3_cache_size'] // 4
            storage_adjusted = min(storage_adjusted, cache_limit)
        elif cpu_info.get('l2_cache_size'):
            # Don't exceed 1/2 of L2 cache
            cache_limit = cpu_info['l2_cache_size'] // 2
            storage_adjusted = min(storage_adjusted, cache_limit)
        
        # Adjust for available memory
        available_mb = memory_info['available'] // (1024 * 1024)
        if available_mb < 1024:  # Less than 1GB available
            storage_adjusted = min(storage_adjusted, 1 * 1024 * 1024)  # Max 1MB
        elif available_mb < 4096:  # Less than 4GB available
            storage_adjusted = min(storage_adjusted, 4 * 1024 * 1024)  # Max 4MB
        
        return storage_adjusted
    
    def _adjust_for_file_size(self, base_buffer: int, file_size: int) -> int:
        """Adjust buffer size based on file size"""
        if file_size == 0:
            return base_buffer
        
        # File size categories (in bytes)
        if file_size < 1 * 1024 * 1024:  # < 1MB
            return min(base_buffer, file_size // 4)
        elif file_size < 100 * 1024 * 1024:  # < 100MB
            return base_buffer
        elif file_size < 1 * 1024 * 1024 * 1024:  # < 1GB
            return min(base_buffer * 2, 32 * 1024 * 1024)  # Max 32MB
        else:  # >= 1GB
            return min(base_buffer * 4, 64 * 1024 * 1024)  # Max 64MB
    
    def _adjust_for_performance(self, base_buffer: int, 
                               source_path: str, dest_path: str) -> int:
        """Adjust based on recent performance metrics"""
        
        # Check if performance is degrading
        if self.performance_monitor.is_performance_degrading():
            # Reduce buffer size by 25%
            return int(base_buffer * 0.75)
        
        # Check recent throughput
        recent_throughput = self.performance_monitor.get_average_throughput(10)
        
        # If throughput is very low, try smaller buffer
        if recent_throughput > 0 and recent_throughput < 50:  # < 50 MB/s
            return int(base_buffer * 0.5)
        
        # If throughput is high, potentially increase buffer
        elif recent_throughput > 500:  # > 500 MB/s
            return min(int(base_buffer * 1.5), self.max_buffer_size)
        
        return base_buffer
    
    def _apply_learned_adjustments(self, base_buffer: int,
                                  source_storage: StorageType,
                                  dest_storage: StorageType) -> int:
        """Apply machine learning adjustments"""
        
        # Create key for this hardware combination
        hardware_key = f"{source_storage.value}_{dest_storage.value}"
        
        if hardware_key not in self.learning_history:
            return base_buffer
        
        # Find the best performing buffer size for this hardware combination
        history = self.learning_history[hardware_key]
        if len(history) < 3:  # Need at least 3 samples
            return base_buffer
        
        # Sort by performance (throughput)
        history.sort(key=lambda x: x[1], reverse=True)
        
        # Get the top 3 performing buffer sizes
        top_performers = history[:3]
        
        # Calculate weighted average of top performers
        total_weight = sum(perf for _, perf in top_performers)
        if total_weight == 0:
            return base_buffer
        
        weighted_buffer = sum(
            buffer_size * (perf / total_weight) 
            for buffer_size, perf in top_performers
        )
        
        return int(weighted_buffer)
    
    def record_performance_result(self, source_path: str, dest_path: str,
                                 buffer_size: int, throughput_mbps: float):
        """Record performance result for learning"""
        
        source_storage = self.hardware_detector.detect_storage_type(source_path)
        dest_storage = self.hardware_detector.detect_storage_type(dest_path)
        
        hardware_key = f"{source_storage.value}_{dest_storage.value}"
        
        if hardware_key not in self.learning_history:
            self.learning_history[hardware_key] = []
        
        # Add to history (keep last 50 results)
        self.learning_history[hardware_key].append((buffer_size, throughput_mbps))
        if len(self.learning_history[hardware_key]) > 50:
            self.learning_history[hardware_key] = \
                self.learning_history[hardware_key][-50:]
    
    def get_recommended_thread_count(self, source_path: str, 
                                   dest_path: str) -> int:
        """Recommend optimal thread count for file operations"""
        
        source_storage = self.hardware_detector.detect_storage_type(source_path)
        dest_storage = self.hardware_detector.detect_storage_type(dest_path)
        cpu_info = self.hardware_detector.get_cpu_info()
        
        # Base on CPU cores
        logical_cores = cpu_info.get('logical_cores', 4)
        physical_cores = cpu_info.get('physical_cores', 2)
        
        # Storage-based thread recommendations
        if source_storage == StorageType.HDD or dest_storage == StorageType.HDD:
            # HDDs don't benefit from many threads due to seek time
            return min(2, physical_cores)
        
        elif source_storage == StorageType.USB or dest_storage == StorageType.USB:
            # USB has limited bandwidth, moderate threading
            return min(4, logical_cores)
        
        elif source_storage == StorageType.NVME and dest_storage == StorageType.NVME:
            # NVMe can handle high parallelism
            return min(logical_cores, 16)  # Cap at 16
        
        else:  # SSD combinations
            return min(logical_cores // 2, 8)  # Conservative for mixed scenarios
```

### Integration with Existing System

```python
class OptimizedBufferedFileOperations:
    """Enhanced file operations with adaptive buffer management"""
    
    def __init__(self):
        self.hardware_detector = HardwareDetector()
        self.performance_monitor = PerformanceMonitor()
        self.buffer_manager = AdaptiveBufferManager(
            self.hardware_detector, self.performance_monitor
        )
        
        # Start performance monitoring
        self.performance_monitor.start_monitoring(interval=1.0)
        
        # Add callback for buffer adjustments
        self.performance_monitor.add_callback(self._on_performance_update)
        
        self._current_buffer_size = 16 * 1024  # Default 16KB
        self._performance_samples = 0
        self._last_adjustment_time = time.time()
    
    def copy_file_adaptive(self, source_path: str, dest_path: str, 
                          progress_callback: Optional[Callable] = None) -> Dict:
        """Copy file with adaptive buffer optimization"""
        
        # Get file size
        file_size = os.path.getsize(source_path)
        
        # Calculate optimal buffer size
        optimal_buffer = self.buffer_manager.calculate_optimal_buffer_size(
            source_path, dest_path, file_size
        )
        
        # Get recommended thread count
        thread_count = self.buffer_manager.get_recommended_thread_count(
            source_path, dest_path
        )
        
        start_time = time.time()
        bytes_copied = 0
        current_buffer_size = optimal_buffer
        
        try:
            with open(source_path, 'rb') as src, open(dest_path, 'wb') as dst:
                
                while True:
                    chunk_start_time = time.time()
                    
                    # Read chunk
                    chunk = src.read(current_buffer_size)
                    if not chunk:
                        break
                    
                    # Write chunk
                    dst.write(chunk)
                    dst.flush()
                    os.fsync(dst.fileno())  # Forensic-grade integrity
                    
                    bytes_copied += len(chunk)
                    chunk_time = time.time() - chunk_start_time
                    
                    # Calculate throughput
                    if chunk_time > 0:
                        chunk_throughput = (len(chunk) / chunk_time) / (1024 * 1024)
                        
                        # Record metrics
                        self.performance_monitor.record_operation_metrics(
                            chunk_throughput, current_buffer_size, "file_copy"
                        )
                        
                        # Dynamic buffer adjustment every 10MB or 5 seconds
                        if (bytes_copied % (10 * 1024 * 1024) == 0 or 
                            time.time() - self._last_adjustment_time > 5.0):
                            
                            new_buffer = self._adjust_buffer_dynamically(
                                current_buffer_size, chunk_throughput
                            )
                            if new_buffer != current_buffer_size:
                                current_buffer_size = new_buffer
                                self._last_adjustment_time = time.time()
                    
                    # Progress callback
                    if progress_callback:
                        progress_percent = int((bytes_copied / file_size) * 100)
                        progress_callback(progress_percent, 
                                        f"Copying with {current_buffer_size//1024}KB buffer")
            
            # Operation complete
            total_time = time.time() - start_time
            avg_throughput = (bytes_copied / total_time) / (1024 * 1024) if total_time > 0 else 0
            
            # Record result for learning
            self.buffer_manager.record_performance_result(
                source_path, dest_path, optimal_buffer, avg_throughput
            )
            
            return {
                'success': True,
                'bytes_copied': bytes_copied,
                'duration': total_time,
                'avg_throughput_mbps': avg_throughput,
                'optimal_buffer_size': optimal_buffer,
                'final_buffer_size': current_buffer_size,
                'recommended_threads': thread_count
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'bytes_copied': bytes_copied
            }
    
    def _adjust_buffer_dynamically(self, current_buffer: int, 
                                  recent_throughput: float) -> int:
        """Dynamically adjust buffer size based on recent performance"""
        
        # Get performance trend
        avg_throughput = self.performance_monitor.get_average_throughput(10)
        
        # If performance is much lower than recent, reduce buffer
        if avg_throughput > 0 and recent_throughput < avg_throughput * 0.7:
            new_buffer = max(self.buffer_manager.min_buffer_size,
                           int(current_buffer * 0.8))
            return new_buffer
        
        # If performance is consistently high, try increasing buffer
        elif recent_throughput > avg_throughput * 1.2:
            new_buffer = min(self.buffer_manager.max_buffer_size,
                           int(current_buffer * 1.2))
            return new_buffer
        
        return current_buffer
    
    def _on_performance_update(self, metrics: PerformanceMetrics):
        """Handle performance monitoring updates"""
        
        # Log high resource usage
        if metrics.cpu_percent > 90:
            print(f"High CPU usage detected: {metrics.cpu_percent:.1f}%")
        
        if metrics.memory_percent > 90:
            print(f"High memory usage detected: {metrics.memory_percent:.1f}%")
        
        # Could trigger buffer size adjustments here
        pass
    
    def get_system_report(self) -> Dict:
        """Generate comprehensive system performance report"""
        
        cpu_info = self.hardware_detector.get_cpu_info()
        memory_info = self.hardware_detector.get_memory_info()
        recent_metrics = self.performance_monitor.get_recent_metrics(60)
        
        return {
            'hardware': {
                'cpu_cores_logical': cpu_info.get('logical_cores'),
                'cpu_cores_physical': cpu_info.get('physical_cores'),
                'cpu_frequency_mhz': cpu_info.get('frequency'),
                'l2_cache_mb': (cpu_info.get('l2_cache_size', 0) or 0) // (1024*1024),
                'l3_cache_mb': (cpu_info.get('l3_cache_size', 0) or 0) // (1024*1024),
                'total_memory_gb': memory_info['total'] // (1024**3),
                'available_memory_gb': memory_info['available'] // (1024**3),
            },
            'performance': {
                'recent_samples': len(recent_metrics),
                'avg_cpu_percent': sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics) if recent_metrics else 0,
                'avg_memory_percent': sum(m.memory_percent for m in recent_metrics) / len(recent_metrics) if recent_metrics else 0,
                'avg_throughput_mbps': self.performance_monitor.get_average_throughput(60),
            },
            'learning_history': {
                hw: len(samples) for hw, samples in self.buffer_manager.learning_history.items()
            }
        }
    
    def __del__(self):
        """Cleanup resources"""
        if hasattr(self, 'performance_monitor'):
            self.performance_monitor.stop_monitoring()
```

## Implementation Strategy

### Phase 1: Basic Hardware Detection
1. Implement core `HardwareDetector` class
2. Add storage type detection for Windows, Linux, macOS
3. Integrate CPU and memory information gathering
4. Create basic buffer size calculation

### Phase 2: Performance Monitoring
1. Implement `PerformanceMonitor` with background monitoring
2. Add real-time metrics collection and storage
3. Create performance degradation detection
4. Integrate with existing progress reporting

### Phase 3: Adaptive Buffer Management
1. Implement `AdaptiveBufferManager` with learning capabilities
2. Add dynamic buffer size adjustment during operations
3. Create hardware-specific optimization profiles
4. Integrate with existing `BufferedFileOperations`

### Phase 4: Learning and Optimization
1. Implement machine learning for buffer optimization
2. Add performance history tracking
3. Create automatic parameter tuning
4. Add comprehensive reporting and diagnostics

## Expected Performance Improvements

### Scenarios and Projections

| Scenario | Current (Fixed 16KB) | Adaptive System | Improvement |
|----------|---------------------|----------------|-------------|
| **i9 + NVMe → NVMe** | 2:29 (29.2GB) | 2:10-2:20 | 5-10% faster |
| **i7 + SSD → SSD** | ~3:30 (estimate) | 3:00-3:15 | 10-15% faster |
| **i5 + USB3 → HDD** | ~12:00 (estimate) | 8:00-10:00 | 20-35% faster |
| **Low-spec + USB → USB** | ~20:00 (estimate) | 15:00-17:00 | 15-25% faster |

### Key Benefits

1. **Automatic Optimization** - No manual tuning required
2. **Hardware Adaptation** - Works optimally across different systems
3. **Learning System** - Performance improves over time
4. **Real-time Adjustment** - Adapts to changing conditions during operation
5. **Forensic Integrity** - Maintains all existing security and integrity features

## Integration with Current Architecture

The adaptive system integrates seamlessly with the existing architecture:

- **Replace** current fixed buffer size calculation
- **Enhance** `BufferedFileOperations` with adaptive capabilities  
- **Maintain** all existing Result objects and error handling
- **Preserve** forensic integrity features (fsync, hashing, etc.)
- **Add** comprehensive performance reporting

## Configuration and Settings

```python
# Example settings integration
class AdaptiveBufferSettings:
    def __init__(self):
        self.enabled = True
        self.min_buffer_kb = 8
        self.max_buffer_mb = 128
        self.learning_enabled = True
        self.performance_monitoring = True
        self.dynamic_adjustment = True
        self.adjustment_threshold_percent = 20.0
        
    def to_dict(self) -> Dict:
        return {
            'adaptive_buffer_enabled': self.enabled,
            'min_buffer_size_kb': self.min_buffer_kb,
            'max_buffer_size_mb': self.max_buffer_mb,
            'learning_system_enabled': self.learning_enabled,
            'performance_monitoring_enabled': self.performance_monitoring,
            'dynamic_adjustment_enabled': self.dynamic_adjustment,
            'performance_threshold_percent': self.adjustment_threshold_percent
        }
```

## Conclusion

This adaptive buffer system will transform the Folder Structure Utility from a fixed-performance tool to an intelligent system that automatically optimizes for any hardware configuration. The combination of hardware detection, real-time performance monitoring, and machine learning will ensure optimal performance across the wide range of systems used in forensic environments.

The system maintains all existing forensic integrity features while adding significant performance improvements, especially for lower-specification field systems where the impact will be most noticeable.