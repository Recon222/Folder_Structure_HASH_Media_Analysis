# core/storage_optimizer.py
import os
import time
import platform
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import deque
import threading
import re

class StorageQueueMonitor:
    """Monitor storage device queue depth and I/O patterns"""
    
    def __init__(self):
        self.io_stats = {}
        self.queue_depths = {}
        self.optimal_queue_depth = self._determine_optimal_queue_depth()
        self._monitoring = False
        self._monitor_thread = None
        self._lock = threading.Lock()
        
        # I/O statistics tracking
        self.io_history = deque(maxlen=60)  # Last 60 samples
        self.last_io_stats = {}
        self.logger = logging.getLogger(__name__)
        
    def _determine_optimal_queue_depth(self) -> Dict[str, int]:
        """Determine optimal queue depth for each storage device"""
        optimal = {}
        
        if platform.system() == 'Linux':
            optimal.update(self._get_linux_queue_depths())
        elif platform.system() == 'Windows':
            optimal.update(self._get_windows_queue_depths())
        else:
            # Default values for unknown systems
            optimal['default'] = 8
            
        return optimal
    
    def _get_linux_queue_depths(self) -> Dict[str, int]:
        """Get optimal queue depths for Linux systems"""
        optimal = {}
        
        # Check /sys/block for device characteristics
        block_path = Path('/sys/block')
        if block_path.exists():
            for device in block_path.iterdir():
                if device.is_dir() and not device.name.startswith('loop'):
                    try:
                        # Read device characteristics
                        dev_info = self._read_device_info(device / 'queue')
                        
                        # Determine optimal queue depth based on device type
                        if dev_info['rotational']:
                            # HDD: Lower queue depth to avoid seek thrashing
                            optimal[device.name] = min(4, dev_info['nr_requests'] // 32)
                        else:
                            # SSD/NVMe: Higher queue depth
                            if 'nvme' in device.name:
                                # NVMe can handle very deep queues
                                optimal[device.name] = min(32, dev_info['nr_requests'] // 8)
                            else:
                                # SATA SSD
                                optimal[device.name] = min(16, dev_info['nr_requests'] // 16)
                    except Exception as e:
                        # Default if can't read device info
                        if 'nvme' in device.name:
                            optimal[device.name] = 32
                        elif 'sd' in device.name:
                            optimal[device.name] = 8
                        else:
                            optimal[device.name] = 4
                            
        return optimal
    
    def _get_windows_queue_depths(self) -> Dict[str, int]:
        """Get optimal queue depths for Windows systems"""
        optimal = {}
        
        try:
            import subprocess
            # Use wmic to get disk info
            result = subprocess.run(
                ['wmic', 'diskdrive', 'get', 'DeviceID,MediaType,Model'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                for line in lines:
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 2:
                            device_id = parts[0]
                            # Simple heuristic based on device type
                            if 'SSD' in line or 'NVMe' in line:
                                optimal[device_id] = 16
                            else:
                                optimal[device_id] = 4
        except Exception as e:
            self.logger.debug(f"Storage optimization failed: {e}")
            
        # Default if detection fails
        if not optimal:
            optimal['default'] = 8
            
        return optimal
    
    def _read_device_info(self, queue_path: Path) -> Dict[str, any]:
        """Read device queue information from sysfs"""
        info = {
            'nr_requests': 128,  # Default queue depth
            'rotational': True,  # Default to HDD
            'scheduler': 'none',
            'read_ahead_kb': 128
        }
        
        try:
            # Number of requests (queue depth)
            nr_requests_file = queue_path / 'nr_requests'
            if nr_requests_file.exists():
                info['nr_requests'] = int(nr_requests_file.read_text().strip())
                
            # Rotational flag (0 = SSD, 1 = HDD)
            rotational_file = queue_path / 'rotational'
            if rotational_file.exists():
                info['rotational'] = rotational_file.read_text().strip() == '1'
                
            # I/O scheduler
            scheduler_file = queue_path / 'scheduler'
            if scheduler_file.exists():
                scheduler_text = scheduler_file.read_text().strip()
                # Extract active scheduler [mq-deadline] bfq kyber none
                match = re.search(r'\[([^\]]+)\]', scheduler_text)
                if match:
                    info['scheduler'] = match.group(1)
                    
            # Read-ahead size
            read_ahead_file = queue_path / 'read_ahead_kb'
            if read_ahead_file.exists():
                info['read_ahead_kb'] = int(read_ahead_file.read_text().strip())
                
        except (ValueError, OSError):
            pass
            
        return info
    
    def get_current_queue_depth(self, device_path: Path) -> Optional[int]:
        """Get current queue depth for a device"""
        if platform.system() == 'Linux':
            try:
                # Find device for path
                device = self._get_device_for_path(device_path)
                if device:
                    # Read inflight requests
                    inflight_file = Path(f'/sys/block/{device}/inflight')
                    if inflight_file.exists():
                        # Format: reads writes
                        inflight = inflight_file.read_text().strip().split()
                        if len(inflight) >= 2:
                            return int(inflight[0]) + int(inflight[1])
            except Exception as e:
                pass
                
        return None
    
    def _get_device_for_path(self, path: Path) -> Optional[str]:
        """Get block device name for a given path"""
        try:
            # Get device number
            stat_info = os.stat(path)
            dev = stat_info.st_dev
            
            # Major/minor device numbers
            major = os.major(dev)
            minor = os.minor(dev)
            
            if platform.system() == 'Linux':
                # Find device in /sys/dev/block
                dev_path = Path(f'/sys/dev/block/{major}:{minor}')
                if dev_path.exists() and dev_path.is_symlink():
                    # Follow symlink to get device name
                    real_path = dev_path.resolve()
                    # Extract device name from path like /sys/devices/.../block/sda/sda1
                    parts = str(real_path).split('/')
                    for i, part in enumerate(parts):
                        if part == 'block' and i + 1 < len(parts):
                            # Get base device name (remove partition number)
                            device_name = re.sub(r'\d+$', '', parts[i + 1])
                            return device_name
        except Exception as e:
            self.logger.debug(f"Storage optimization failed: {e}")
            
        return None
    
    def start_monitoring(self):
        """Start I/O monitoring in background"""
        if self._monitoring:
            return
            
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        
    def stop_monitoring(self):
        """Stop I/O monitoring"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=10)
            
    def _monitor_loop(self):
        """Background monitoring loop"""
        while self._monitoring:
            try:
                current_stats = self._get_io_statistics()
                
                with self._lock:
                    # Calculate rates if we have previous stats
                    if self.last_io_stats:
                        rates = self._calculate_io_rates(self.last_io_stats, current_stats)
                        self.io_history.append((time.time(), rates))
                        
                    self.last_io_stats = current_stats
                    
            except Exception as e:
                pass
                
            time.sleep(1)  # Sample every second
            
    def _get_io_statistics(self) -> Dict[str, Dict[str, int]]:
        """Get current I/O statistics"""
        stats = {}
        
        if platform.system() == 'Linux':
            # Read from /proc/diskstats
            try:
                with open('/proc/diskstats', 'r') as f:
                    for line in f:
                        parts = line.split()
                        if len(parts) >= 14:
                            device = parts[2]
                            # Skip loop and ram devices
                            if not device.startswith(('loop', 'ram')):
                                stats[device] = {
                                    'reads_completed': int(parts[3]),
                                    'writes_completed': int(parts[7]),
                                    'sectors_read': int(parts[5]),
                                    'sectors_written': int(parts[9]),
                                    'io_time_ms': int(parts[12]),
                                    'weighted_io_time_ms': int(parts[13])
                                }
            except Exception as e:
                pass
                
        return stats
    
    def _calculate_io_rates(self, old_stats: Dict, new_stats: Dict) -> Dict[str, Dict[str, float]]:
        """Calculate I/O rates from statistics"""
        rates = {}
        
        for device in new_stats:
            if device in old_stats:
                old = old_stats[device]
                new = new_stats[device]
                
                # Calculate rates per second
                rates[device] = {
                    'read_iops': new['reads_completed'] - old['reads_completed'],
                    'write_iops': new['writes_completed'] - old['writes_completed'],
                    'read_mbps': (new['sectors_read'] - old['sectors_read']) * 512 / (1024 * 1024),
                    'write_mbps': (new['sectors_written'] - old['sectors_written']) * 512 / (1024 * 1024),
                    'io_utilization': min(100, (new['io_time_ms'] - old['io_time_ms']) / 10)  # Percentage
                }
                
        return rates
    
    def get_device_load(self, device_path: Path) -> Optional[float]:
        """Get current load percentage for a device"""
        device = self._get_device_for_path(device_path)
        if not device:
            return None
            
        with self._lock:
            if self.io_history:
                # Get recent I/O statistics
                recent_stats = [stats for _, stats in list(self.io_history)[-10:]]
                if recent_stats and device in recent_stats[-1]:
                    return recent_stats[-1][device].get('io_utilization', 0)
                    
        return None
    
    def should_throttle_operations(self, device_path: Path) -> bool:
        """Check if operations should be throttled due to high I/O load"""
        load = self.get_device_load(device_path)
        if load is not None:
            # Throttle if device is more than 90% utilized
            return load > 90
        return False
    
    def get_recommended_queue_depth(self, device_path: Path, current_load: Optional[float] = None) -> int:
        """Get recommended queue depth based on device and current load"""
        device = self._get_device_for_path(device_path)
        
        if device and device in self.optimal_queue_depth:
            optimal = self.optimal_queue_depth[device]
        else:
            optimal = self.optimal_queue_depth.get('default', 8)
            
        # Adjust based on current load
        if current_load is None:
            current_load = self.get_device_load(device_path) or 0
            
        if current_load > 80:
            # High load - reduce queue depth
            return max(1, optimal // 2)
        elif current_load > 50:
            # Moderate load - slightly reduce
            return max(2, int(optimal * 0.75))
        else:
            # Low load - use optimal
            return optimal
    
    def get_storage_stats(self, device_path: Path) -> Dict[str, any]:
        """Get comprehensive storage statistics"""
        device = self._get_device_for_path(device_path)
        
        stats = {
            'device': device or 'unknown',
            'optimal_queue_depth': self.optimal_queue_depth.get(device, 8) if device else 8,
            'current_load': self.get_device_load(device_path) or 0,
            'should_throttle': self.should_throttle_operations(device_path)
        }
        
        # Add recent I/O rates if available
        with self._lock:
            if self.io_history and device:
                recent = [stats for _, stats in list(self.io_history)[-10:]]
                if recent and device in recent[-1]:
                    device_stats = recent[-1][device]
                    stats.update({
                        'read_iops': device_stats.get('read_iops', 0),
                        'write_iops': device_stats.get('write_iops', 0),
                        'read_mbps': round(device_stats.get('read_mbps', 0), 1),
                        'write_mbps': round(device_stats.get('write_mbps', 0), 1),
                        'io_utilization': round(device_stats.get('io_utilization', 0), 1)
                    })
                    
        return stats