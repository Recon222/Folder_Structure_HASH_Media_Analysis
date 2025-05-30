# core/disk_analyzer.py
import psutil
import platform
import os
import time
import tempfile
import logging
from pathlib import Path
from typing import Dict, Any, Optional

class DiskAnalyzer:
    """Analyze disk characteristics for optimization"""
    
    def __init__(self):
        self._disk_cache = {}  # Cache disk info to avoid repeated analysis
        self._cache_duration = 300  # 5 minutes
        self.logger = logging.getLogger(__name__)
        
    def get_disk_info(self, path: Path) -> Dict[str, Any]:
        """Detect disk type and characteristics"""
        # Check cache first
        cache_key = self._get_mount_point(path)
        if cache_key in self._disk_cache:
            cached_info, timestamp = self._disk_cache[cache_key]
            if time.time() - timestamp < self._cache_duration:
                return cached_info
        
        disk_info = {
            'type': 'unknown',
            'mount_point': None,
            'total_space': 0,
            'free_space': 0,
            'is_network': False,
            'read_speed_mbps': 0,
            'write_speed_mbps': 0
        }
        
        # Get partition info
        partitions = psutil.disk_partitions()
        for partition in partitions:
            if str(path).startswith(partition.mountpoint):
                disk_info['mount_point'] = partition.mountpoint
                disk_info['is_network'] = 'network' in partition.opts or 'smb' in partition.opts or 'nfs' in partition.opts
                
                # Get disk usage
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disk_info['total_space'] = usage.total
                    disk_info['free_space'] = usage.free
                except (OSError, PermissionError) as e:
                    self.logger.warning(f"Cannot access disk usage for {partition.mountpoint}: {e}")
                    disk_info['total_space'] = 0
                    disk_info['free_space'] = 0
                
                # Detect disk type
                if not disk_info['is_network']:
                    disk_info['type'] = self._detect_disk_type(partition)
                    
                    # Quick benchmark for local disks
                    if disk_info['type'] != 'unknown':
                        speeds = self._quick_benchmark(Path(partition.mountpoint))
                        disk_info['read_speed_mbps'] = speeds['read']
                        disk_info['write_speed_mbps'] = speeds['write']
                else:
                    disk_info['type'] = 'network'
                break
        
        # Cache the result
        self._disk_cache[cache_key] = (disk_info, time.time())
        return disk_info
    
    def _get_mount_point(self, path: Path) -> str:
        """Get mount point for a given path"""
        path = Path(path).resolve()
        while not path.exists() and path != path.parent:
            path = path.parent
            
        partitions = psutil.disk_partitions()
        mount_point = '/'
        for partition in partitions:
            if str(path).startswith(partition.mountpoint):
                if len(partition.mountpoint) > len(mount_point):
                    mount_point = partition.mountpoint
        return mount_point
    
    def _detect_disk_type(self, partition) -> str:
        """Detect if disk is SSD or HDD"""
        if platform.system() == 'Windows':
            return self._detect_disk_type_windows(partition)
        elif platform.system() == 'Linux':
            return self._detect_disk_type_linux(partition)
        elif platform.system() == 'Darwin':  # macOS
            return self._detect_disk_type_macos(partition)
        return 'unknown'
    
    def _detect_disk_type_windows(self, partition) -> str:
        """Windows-specific disk type detection"""
        try:
            import subprocess
            # Use wmic to get disk info
            device_id = partition.device.replace('\\', '')
            cmd = f'wmic diskdrive get DeviceID,MediaType,Model | findstr /i "{device_id}"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                output = result.stdout.strip()
                if 'SSD' in output or 'Solid State' in output:
                    return 'ssd'
                elif 'NVMe' in output:
                    return 'nvme'
                else:
                    return 'hdd'
        except (subprocess.SubprocessError, FileNotFoundError, Exception) as e:
            self.logger.debug(f"Windows disk detection failed: {e}")
        
        # Fallback: check for common SSD indicators in the path
        if any(ssd_indicator in str(partition.device).upper() for ssd_indicator in ['SSD', 'NVME']):
            return 'ssd'
        return 'hdd'
    
    def _detect_disk_type_linux(self, partition) -> str:
        """Linux-specific disk type detection"""
        try:
            # Get the base device name (remove partition number)
            device = partition.device.split('/')[-1]
            # Remove partition number
            import re
            base_device = re.sub(r'\d+$', '', device)
            
            # Check for NVMe
            if base_device.startswith('nvme'):
                return 'nvme'
            
            # Check rotational flag (0 = SSD, 1 = HDD)
            rotational_path = f'/sys/block/{base_device}/queue/rotational'
            if os.path.exists(rotational_path):
                with open(rotational_path, 'r') as f:
                    is_rotational = f.read().strip() == '1'
                    return 'hdd' if is_rotational else 'ssd'
        except Exception as e:
            self.logger.debug(f"Linux disk detection failed: {e}")
        
        return 'unknown'
    
    def _detect_disk_type_macos(self, partition) -> str:
        """macOS-specific disk type detection"""
        try:
            import subprocess
            # Use diskutil to get disk info
            result = subprocess.run(
                ['diskutil', 'info', partition.device],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                output = result.stdout.lower()
                if 'solid state' in output or 'ssd' in output:
                    return 'ssd'
                elif 'nvme' in output:
                    return 'nvme'
                elif 'mechanical' in output or 'hard disk' in output:
                    return 'hdd'
        except Exception as e:
            self.logger.debug(f"macOS disk detection failed: {e}")
        
        return 'unknown'
    
    def _quick_benchmark(self, path: Path, size_mb: int = 10) -> Dict[str, float]:
        """Quick disk speed benchmark"""
        speeds = {'read': 0.0, 'write': 0.0}
        
        # Create temporary file for testing
        try:
            with tempfile.NamedTemporaryFile(dir=str(path), delete=False) as tmp:
                test_file = Path(tmp.name)
                test_data = os.urandom(1024 * 1024)  # 1MB of random data
                
                # Write test
                start_time = time.time()
                for _ in range(size_mb):
                    tmp.write(test_data)
                tmp.flush()
                os.fsync(tmp.fileno())
                write_time = time.time() - start_time
                speeds['write'] = size_mb / write_time if write_time > 0 else 0
                
            # Read test
            with open(test_file, 'rb') as f:
                start_time = time.time()
                while f.read(1024 * 1024):
                    pass
                read_time = time.time() - start_time
                speeds['read'] = size_mb / read_time if read_time > 0 else 0
            
            # Cleanup
            test_file.unlink()
            
        except Exception as e:
            # If benchmark fails, use conservative estimates
            disk_type = self._detect_disk_type(None)
            if disk_type == 'nvme':
                speeds = {'read': 3000, 'write': 2000}
            elif disk_type == 'ssd':
                speeds = {'read': 500, 'write': 400}
            else:
                speeds = {'read': 150, 'write': 120}
        
        return speeds
    
    def get_optimal_workers(self, path: Path, operation: str = 'copy') -> int:
        """Determine optimal worker count based on disk type"""
        disk_info = self.get_disk_info(path)
        cpu_count = os.cpu_count() or 4
        
        if disk_info['is_network']:
            # Network drives: limited by bandwidth and latency
            return min(2, cpu_count)
        
        elif disk_info['type'] == 'nvme':
            # NVMe: can handle many parallel operations
            if operation == 'copy':
                return min(16, cpu_count)
            elif operation == 'hash':
                return min(cpu_count, 8)
        
        elif disk_info['type'] == 'ssd':
            # SATA SSD: good parallelism but not as much as NVMe
            if operation == 'copy':
                return min(8, cpu_count)
            elif operation == 'hash':
                return min(cpu_count, 6)
        
        elif disk_info['type'] == 'hdd':
            # HDD: limited parallelism to avoid seek thrashing
            if operation == 'copy':
                return 2  # Max 2 parallel operations
            elif operation == 'hash':
                return min(3, cpu_count)  # Slightly more for CPU-bound
        
        else:
            # Unknown: conservative approach
            return min(4, cpu_count)