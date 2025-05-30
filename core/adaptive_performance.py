# core/adaptive_performance.py
import os
import time
import threading
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import statistics
import logging

# Import the optimization modules
from .numa_optimizer import NUMAOptimizer
from .thermal_manager import ThermalManager
from .storage_optimizer import StorageQueueMonitor
from .disk_analyzer import DiskAnalyzer
from .workload_analyzer import WorkloadAnalyzer

class WorkloadPriority(Enum):
    LATENCY = "latency"      # Minimize response time
    THROUGHPUT = "throughput"  # Maximize total processing
    BALANCED = "balanced"     # Balance between latency and throughput

@dataclass
class PerformanceMetrics:
    """Track performance metrics for adaptive optimization"""
    start_time: float = field(default_factory=time.time)
    files_processed: int = 0
    bytes_processed: int = 0
    errors_count: int = 0
    
    # Rolling windows for rates
    throughput_history: deque = field(default_factory=lambda: deque(maxlen=60))
    latency_history: deque = field(default_factory=lambda: deque(maxlen=100))
    cpu_usage_history: deque = field(default_factory=lambda: deque(maxlen=60))
    
    # Current rates
    current_throughput_mbps: float = 0.0
    average_latency_ms: float = 0.0
    cpu_efficiency: float = 0.0
    
    def update_file_completed(self, file_size: int, duration: float):
        """Update metrics when a file is completed"""
        self.files_processed += 1
        self.bytes_processed += file_size
        
        # Calculate throughput
        throughput_mbps = (file_size / (1024 * 1024)) / duration if duration > 0 else 0
        self.throughput_history.append(throughput_mbps)
        
        # Calculate latency
        latency_ms = duration * 1000
        self.latency_history.append(latency_ms)
        
        # Update current rates
        if self.throughput_history:
            self.current_throughput_mbps = statistics.mean(self.throughput_history)
        if self.latency_history:
            self.average_latency_ms = statistics.mean(self.latency_history)
            
    def get_efficiency_score(self) -> float:
        """Calculate overall efficiency score (0-1)"""
        if not self.throughput_history:
            return 0.5
            
        # Normalize throughput (assume 1000 MB/s is excellent)
        throughput_score = min(self.current_throughput_mbps / 1000, 1.0)
        
        # Normalize latency (assume 10ms is excellent)
        latency_score = 1.0 - min(self.average_latency_ms / 100, 1.0)
        
        # CPU efficiency (lower is better)
        cpu_score = 1.0 - (self.cpu_efficiency / 100) if self.cpu_efficiency < 100 else 0
        
        # Weighted average
        return (throughput_score * 0.5 + latency_score * 0.3 + cpu_score * 0.2)

class AdaptivePerformanceController:
    """Master controller that combines all optimizations"""
    
    def __init__(self, log_level: int = logging.INFO):
        # Initialize all optimizers
        self.numa = NUMAOptimizer()
        self.thermal = ThermalManager()
        self.storage = StorageQueueMonitor()
        self.disk_analyzer = DiskAnalyzer()
        self.workload_analyzer = WorkloadAnalyzer()
        
        # Performance tracking
        self.metrics = PerformanceMetrics()
        self.performance_history = deque(maxlen=1000)  # Last 1000 operations
        
        # Configuration cache
        self._config_cache = {}
        self._cache_lock = threading.Lock()
        
        # Adaptive learning
        self.learning_enabled = True
        self.performance_models = {}  # Workload pattern -> optimal config
        
        # Logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)
        
        # Start monitoring
        self._start_monitoring()
        
    def get_optimal_configuration(self, workload: List[Path], 
                                destination: Path) -> Dict[str, Any]:
        """Determine optimal configuration for current conditions"""
        
        # Start with base configuration
        config = {
            'workers': os.cpu_count() or 4,
            'affinity': None,
            'queue_depth': 16,
            'buffer_size': 1048576,  # 1MB default
            'throttle_factor': 1.0,
            'priority': WorkloadPriority.BALANCED,
            'use_direct_io': False,
            'prefetch_enabled': True,
            'compression_enabled': False
        }
        
        # Analyze workload characteristics
        workload_profile = self._analyze_workload_profile(workload)
        
        # Check cache for similar workload
        cache_key = self._get_cache_key(workload_profile)
        with self._cache_lock:
            if cache_key in self._config_cache:
                cached_config = self._config_cache[cache_key]
                if self._is_cache_valid(cached_config):
                    self.logger.debug(f"Using cached config for workload: {cache_key}")
                    return cached_config['config']
        
        # NUMA optimization
        if len(self.numa.numa_nodes) > 1:
            config['workers'] = self._calculate_numa_aware_workers(workload_profile)
            config['affinity'] = self.numa.get_optimal_worker_distribution(config['workers'])
            self.logger.info(f"NUMA optimization: {len(self.numa.numa_nodes)} nodes detected")
            
        # Thermal adjustment
        thermal_state = self.thermal.get_thermal_status()
        if thermal_state['is_throttled']:
            original_workers = config['workers']
            config['workers'] = max(1, int(config['workers'] * thermal_state['throttle_factor']))
            config['throttle_factor'] = thermal_state['throttle_factor']
            self.logger.warning(f"Thermal throttling active: {original_workers} -> {config['workers']} workers")
            
        # Storage optimization
        storage_info = self._analyze_storage(destination)
        config['queue_depth'] = storage_info['optimal_queue_depth']
        config['use_direct_io'] = storage_info['supports_direct_io'] and workload_profile['avg_file_size'] > 10_000_000
        
        # Buffer size optimization based on storage and workload
        config['buffer_size'] = self._calculate_optimal_buffer_size(
            workload_profile, storage_info
        )
        
        # Priority determination
        config['priority'] = self._determine_priority(workload_profile)
        
        # Apply priority-based adjustments
        if config['priority'] == WorkloadPriority.LATENCY:
            # Reduce parallelism to minimize contention
            config['workers'] = min(config['workers'], 4)
            config['prefetch_enabled'] = True
            config['buffer_size'] = min(config['buffer_size'], 262144)  # 256KB max
            
        elif config['priority'] == WorkloadPriority.THROUGHPUT:
            # Maximize parallelism for throughput
            config['workers'] = min(config['workers'], storage_info['optimal_queue_depth'])
            config['prefetch_enabled'] = workload_profile['sequential_ratio'] > 0.7
            
        # Learning-based optimization
        if self.learning_enabled and cache_key in self.performance_models:
            learned_config = self.performance_models[cache_key]
            config = self._apply_learned_optimizations(config, learned_config)
            
        # Cache the configuration
        with self._cache_lock:
            self._config_cache[cache_key] = {
                'config': config,
                'timestamp': time.time(),
                'workload_profile': workload_profile
            }
            
        self.logger.info(f"Optimal config: workers={config['workers']}, "
                        f"priority={config['priority'].value}, "
                        f"buffer={config['buffer_size']//1024}KB")
        
        return config
    
    def _analyze_workload_profile(self, workload: List[Path]) -> Dict[str, Any]:
        """Analyze workload characteristics"""
        if not workload:
            return {}
            
        sizes = [f.stat().st_size for f in workload if f.exists()]
        
        profile = {
            'total_files': len(workload),
            'total_size': sum(sizes),
            'avg_file_size': statistics.mean(sizes) if sizes else 0,
            'median_file_size': statistics.median(sizes) if sizes else 0,
            'size_variance': statistics.variance(sizes) if len(sizes) > 1 else 0,
            'small_files_ratio': len([s for s in sizes if s < 1_000_000]) / len(sizes) if sizes else 0,
            'large_files_ratio': len([s for s in sizes if s > 100_000_000]) / len(sizes) if sizes else 0,
            'sequential_ratio': self._estimate_sequential_ratio(workload),
            'file_types': self._analyze_file_types(workload)
        }
        
        return profile
    
    def _estimate_sequential_ratio(self, workload: List[Path]) -> float:
        """Estimate how sequential the workload is"""
        if len(workload) < 2:
            return 1.0
            
        # Check if files are numbered sequentially
        sequential_count = 0
        for i in range(1, min(len(workload), 10)):
            if self._are_sequential(workload[i-1], workload[i]):
                sequential_count += 1
                
        return sequential_count / min(len(workload) - 1, 9)
    
    def _are_sequential(self, file1: Path, file2: Path) -> bool:
        """Check if two files are likely sequential"""
        # Simple heuristic: similar names with incrementing numbers
        stem1, stem2 = file1.stem, file2.stem
        
        # Extract numbers from filenames
        import re
        nums1 = re.findall(r'\d+', stem1)
        nums2 = re.findall(r'\d+', stem2)
        
        if nums1 and nums2:
            try:
                # Check if any number increments by 1
                for n1, n2 in zip(nums1, nums2):
                    if int(n2) - int(n1) == 1:
                        return True
            except:
                pass
                
        return False
    
    def _analyze_file_types(self, workload: List[Path]) -> Dict[str, int]:
        """Analyze file types in workload"""
        types = {}
        for file in workload:
            ext = file.suffix.lower()
            types[ext] = types.get(ext, 0) + 1
        return types
    
    def _calculate_numa_aware_workers(self, workload_profile: Dict) -> int:
        """Calculate optimal workers for NUMA systems"""
        numa_nodes = len(self.numa.numa_nodes)
        cpus_per_node = self.numa.numa_nodes[0] if self.numa.numa_nodes else []
        
        if workload_profile['small_files_ratio'] > 0.8:
            # Many small files: use more workers
            return min(len(cpus_per_node) * numa_nodes, 32)
        elif workload_profile['large_files_ratio'] > 0.5:
            # Large files: limit workers to avoid memory contention
            return min(numa_nodes * 2, 8)
        else:
            # Mixed workload: balanced approach
            return min(numa_nodes * 4, 16)
    
    def _analyze_storage(self, path: Path) -> Dict[str, Any]:
        """Comprehensive storage analysis"""
        disk_info = self.disk_analyzer.get_disk_info(path)
        device = self.storage._get_device_for_path(path)
        
        storage_info = {
            'type': disk_info.get('type', 'unknown'),
            'is_network': disk_info.get('is_network', False),
            'optimal_queue_depth': 8,
            'supports_direct_io': False,
            'bandwidth_mbps': 100  # Conservative default
        }
        
        if device:
            # Get optimal queue depth
            storage_info['optimal_queue_depth'] = self.storage.optimal_queue_depth.get(device, 8)
            
            # Estimate bandwidth based on device type
            if 'nvme' in device:
                storage_info['bandwidth_mbps'] = 3500  # NVMe Gen3
                storage_info['supports_direct_io'] = True
            elif storage_info['type'] == 'ssd':
                storage_info['bandwidth_mbps'] = 550  # SATA SSD
                storage_info['supports_direct_io'] = True
            elif storage_info['type'] == 'hdd':
                storage_info['bandwidth_mbps'] = 150  # Modern HDD
                
        return storage_info
    
    def _calculate_optimal_buffer_size(self, workload_profile: Dict, 
                                     storage_info: Dict) -> int:
        """Calculate optimal buffer size based on workload and storage"""
        
        # Base buffer size on average file size
        avg_size = workload_profile['avg_file_size']
        
        if avg_size < 1_000_000:  # < 1MB
            base_buffer = 65536  # 64KB
        elif avg_size < 10_000_000:  # < 10MB
            base_buffer = 262144  # 256KB
        elif avg_size < 100_000_000:  # < 100MB
            base_buffer = 1048576  # 1MB
        else:
            base_buffer = 10485760  # 10MB
            
        # Adjust for storage type
        if storage_info['type'] == 'nvme':
            # NVMe can handle larger buffers efficiently
            base_buffer *= 2
        elif storage_info['is_network']:
            # Network storage: larger buffers to reduce round trips
            base_buffer *= 4
            
        # Cap based on available memory
        import psutil
        available_memory = psutil.virtual_memory().available
        max_buffer = available_memory // 100  # Max 1% of available RAM
        
        return min(base_buffer, max_buffer)
    
    def _determine_priority(self, workload_profile: Dict) -> WorkloadPriority:
        """Determine workload priority based on characteristics"""
        
        # Small files with high count -> latency sensitive
        if workload_profile['small_files_ratio'] > 0.8 and workload_profile['total_files'] > 100:
            return WorkloadPriority.LATENCY
            
        # Large files -> throughput focused
        if workload_profile['large_files_ratio'] > 0.7:
            return WorkloadPriority.THROUGHPUT
            
        # Video files -> throughput focused
        video_extensions = {'.mp4', '.avi', '.mkv', '.mov'}
        file_types = workload_profile.get('file_types', {})
        video_count = sum(count for ext, count in file_types.items() if ext in video_extensions)
        if video_count > workload_profile['total_files'] * 0.5:
            return WorkloadPriority.THROUGHPUT
            
        return WorkloadPriority.BALANCED
    
    def _get_cache_key(self, workload_profile: Dict) -> str:
        """Generate cache key for workload profile"""
        # Create a key based on workload characteristics
        key_parts = [
            f"files_{workload_profile.get('total_files', 0)}",
            f"avg_{int(workload_profile.get('avg_file_size', 0) / 1_000_000)}MB",
            f"small_{int(workload_profile.get('small_files_ratio', 0) * 100)}",
            f"large_{int(workload_profile.get('large_files_ratio', 0) * 100)}"
        ]
        return "_".join(key_parts)
    
    def _is_cache_valid(self, cached_entry: Dict) -> bool:
        """Check if cached configuration is still valid"""
        # Cache expires after 5 minutes or if thermal state changes
        age = time.time() - cached_entry['timestamp']
        if age > 300:  # 5 minutes
            return False
            
        # Check if thermal state has changed significantly
        current_thermal = self.thermal.get_thermal_status()
        if abs(current_thermal['throttle_factor'] - cached_entry.get('throttle_factor', 1.0)) > 0.1:
            return False
            
        return True
    
    def update_performance_metrics(self, operation: str, duration: float, 
                                 file_size: int, success: bool):
        """Update performance metrics after an operation"""
        if success:
            self.metrics.update_file_completed(file_size, duration)
        else:
            self.metrics.errors_count += 1
            
        # Record for learning
        self.performance_history.append({
            'operation': operation,
            'duration': duration,
            'file_size': file_size,
            'success': success,
            'timestamp': time.time(),
            'efficiency': self.metrics.get_efficiency_score()
        })
        
    def _apply_learned_optimizations(self, base_config: Dict, 
                                    learned_config: Dict) -> Dict:
        """Apply learned optimizations to base configuration"""
        # Blend learned parameters with current config
        for key in ['workers', 'buffer_size', 'queue_depth']:
            if key in learned_config:
                # Weighted average: 70% learned, 30% calculated
                base_value = base_config.get(key, 0)
                learned_value = learned_config.get(key, base_value)
                base_config[key] = int(0.7 * learned_value + 0.3 * base_value)
                
        return base_config
    
    def learn_from_performance(self):
        """Analyze performance history and update models"""
        if len(self.performance_history) < 100:
            return  # Not enough data
            
        # Group by workload patterns
        pattern_performance = {}
        
        for record in self.performance_history:
            # Extract pattern (simplified)
            pattern = f"size_{record['file_size'] // 10_000_000}"
            
            if pattern not in pattern_performance:
                pattern_performance[pattern] = []
                
            pattern_performance[pattern].append({
                'efficiency': record['efficiency'],
                'config': record.get('config', {})
            })
            
        # Find best configurations for each pattern
        for pattern, performances in pattern_performance.items():
            if performances:
                # Find config with best efficiency
                best = max(performances, key=lambda x: x['efficiency'])
                if best['efficiency'] > 0.7:  # Only learn from good performances
                    self.performance_models[pattern] = best['config']
                    
    def _start_monitoring(self):
        """Start background monitoring threads"""
        # Thermal monitoring
        if self.thermal:
            self.thermal.start_monitoring()
            
        # Performance learning thread
        self.learning_thread = threading.Thread(
            target=self._learning_loop,
            daemon=True
        )
        self.learning_thread.start()
        
    def _learning_loop(self):
        """Background thread for performance learning"""
        while True:
            time.sleep(60)  # Learn every minute
            try:
                self.learn_from_performance()
            except Exception as e:
                self.logger.error(f"Learning error: {e}")
    
    def get_status_report(self) -> Dict[str, Any]:
        """Get comprehensive status report"""
        return {
            'metrics': {
                'files_processed': self.metrics.files_processed,
                'throughput_mbps': self.metrics.current_throughput_mbps,
                'average_latency_ms': self.metrics.average_latency_ms,
                'efficiency_score': self.metrics.get_efficiency_score()
            },
            'system': {
                'numa_nodes': len(self.numa.numa_nodes),
                'thermal_status': self.thermal.get_thermal_status(),
                'cpu_count': os.cpu_count()
            },
            'learning': {
                'patterns_learned': len(self.performance_models),
                'history_size': len(self.performance_history)
            }
        }