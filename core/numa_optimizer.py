# core/numa_optimizer.py
import os
import subprocess
import platform
from typing import Dict, List, Optional
from pathlib import Path
import multiprocessing

class NUMAOptimizer:
    """Optimize thread placement for NUMA systems"""
    
    def __init__(self):
        self.numa_nodes = self._detect_numa_topology()
        self.cpu_affinity = self._get_cpu_affinity()
        self.cpu_count = os.cpu_count() or multiprocessing.cpu_count()
        
    def _detect_numa_topology(self) -> Dict[int, List[int]]:
        """Detect NUMA topology on the system"""
        numa_nodes = {}
        
        if platform.system() == 'Linux':
            # Try numactl first
            try:
                result = subprocess.run(
                    ['numactl', '--hardware'], 
                    capture_output=True, 
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    # Parse numactl output
                    for line in result.stdout.split('\n'):
                        if 'node' in line and 'cpus:' in line:
                            parts = line.split()
                            if len(parts) >= 4 and parts[0] == 'node' and parts[2] == 'cpus:':
                                try:
                                    node_id = int(parts[1])
                                    cpus = [int(cpu) for cpu in parts[3:]]
                                    numa_nodes[node_id] = cpus
                                except ValueError:
                                    continue
                                    
            except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired):
                # numactl not available, try sysfs
                numa_nodes = self._detect_numa_sysfs()
                
        elif platform.system() == 'Windows':
            numa_nodes = self._detect_numa_windows()
            
        # Fallback: single NUMA node with all CPUs
        if not numa_nodes:
            numa_nodes[0] = list(range(self.cpu_count))
            
        return numa_nodes
    
    def _detect_numa_sysfs(self) -> Dict[int, List[int]]:
        """Detect NUMA topology via sysfs on Linux"""
        numa_nodes = {}
        
        try:
            node_path = Path('/sys/devices/system/node')
            if node_path.exists():
                for node_dir in node_path.glob('node*'):
                    if node_dir.is_dir():
                        try:
                            node_id = int(node_dir.name.replace('node', ''))
                            cpulist_file = node_dir / 'cpulist'
                            if cpulist_file.exists():
                                cpu_list = self._parse_cpu_list(
                                    cpulist_file.read_text().strip()
                                )
                                numa_nodes[node_id] = cpu_list
                        except (ValueError, OSError):
                            continue
        except:
            pass
            
        return numa_nodes
    
    def _detect_numa_windows(self) -> Dict[int, List[int]]:
        """Detect NUMA topology on Windows"""
        numa_nodes = {}
        
        try:
            # Use Windows GetLogicalProcessorInformationEx via ctypes
            import ctypes
            from ctypes import wintypes
            
            # This is a simplified version - full implementation would be more complex
            # For now, check processor groups which often correspond to NUMA nodes
            kernel32 = ctypes.windll.kernel32
            
            # Get number of processor groups (often equals NUMA nodes)
            num_groups = kernel32.GetActiveProcessorGroupCount()
            
            if num_groups > 1:
                for group in range(num_groups):
                    count = kernel32.GetActiveProcessorCount(group)
                    # Assign CPUs to groups (simplified)
                    start_cpu = group * (self.cpu_count // num_groups)
                    numa_nodes[group] = list(range(start_cpu, start_cpu + count))
            else:
                numa_nodes[0] = list(range(self.cpu_count))
                
        except:
            # Fallback for Windows
            numa_nodes[0] = list(range(self.cpu_count))
            
        return numa_nodes
    
    def _parse_cpu_list(self, cpu_string: str) -> List[int]:
        """Parse CPU list like '0-3,8-11' into [0,1,2,3,8,9,10,11]"""
        cpus = []
        
        if not cpu_string:
            return cpus
            
        for part in cpu_string.split(','):
            part = part.strip()
            if '-' in part:
                try:
                    start, end = map(int, part.split('-'))
                    cpus.extend(range(start, end + 1))
                except ValueError:
                    continue
            else:
                try:
                    cpus.append(int(part))
                except ValueError:
                    continue
                    
        return sorted(list(set(cpus)))  # Remove duplicates and sort
    
    def _get_cpu_affinity(self) -> Optional[List[int]]:
        """Get current process CPU affinity"""
        try:
            if hasattr(os, 'sched_getaffinity'):
                return sorted(list(os.sched_getaffinity(0)))
            elif platform.system() == 'Windows':
                # Windows process affinity via ctypes
                import ctypes
                kernel32 = ctypes.windll.kernel32
                process_handle = kernel32.GetCurrentProcess()
                
                process_mask = ctypes.c_ulonglong()
                system_mask = ctypes.c_ulonglong()
                
                if kernel32.GetProcessAffinityMask(process_handle, 
                                                  ctypes.byref(process_mask),
                                                  ctypes.byref(system_mask)):
                    # Convert mask to CPU list
                    mask = process_mask.value
                    cpus = []
                    for i in range(64):  # Max 64 CPUs in mask
                        if mask & (1 << i):
                            cpus.append(i)
                    return cpus if cpus else None
        except:
            pass
            
        return None
    
    def get_optimal_worker_distribution(self, 
                                      worker_count: int,
                                      prefer_local: bool = True) -> Dict[int, List[int]]:
        """Distribute workers across NUMA nodes optimally"""
        
        if len(self.numa_nodes) == 1:
            # Single NUMA node, simple distribution
            return {0: list(range(worker_count))}
        
        # Multi-NUMA distribution
        distribution = {}
        
        # Calculate workers per node
        nodes_count = len(self.numa_nodes)
        base_workers_per_node = worker_count // nodes_count
        extra_workers = worker_count % nodes_count
        
        worker_id = 0
        for node_id, cpus in self.numa_nodes.items():
            node_workers = base_workers_per_node
            if extra_workers > 0:
                node_workers += 1
                extra_workers -= 1
                
            distribution[node_id] = list(range(worker_id, worker_id + node_workers))
            worker_id += node_workers
            
        return distribution
    
    def get_node_for_path(self, path: Path) -> Optional[int]:
        """Determine which NUMA node is best for accessing a given path"""
        # This is a simplified heuristic - ideally would check memory locality
        
        if len(self.numa_nodes) == 1:
            return 0
            
        # For now, distribute based on path hash for consistency
        path_hash = hash(str(path.resolve()))
        return path_hash % len(self.numa_nodes)
    
    def optimize_file_distribution(self, files: List[Path]) -> Dict[int, List[Path]]:
        """Distribute files across NUMA nodes for optimal processing"""
        
        if len(self.numa_nodes) == 1:
            return {0: files}
            
        # Distribute files to minimize cross-node memory access
        distribution = {node_id: [] for node_id in self.numa_nodes}
        
        for i, file in enumerate(files):
            # Simple round-robin distribution
            # In production, might consider file location on disk
            node_id = i % len(self.numa_nodes)
            distribution[node_id].append(file)
            
        return distribution
    
    def set_thread_affinity(self, cpu_list: List[int]) -> bool:
        """Set CPU affinity for current thread/process"""
        try:
            if hasattr(os, 'sched_setaffinity'):
                os.sched_setaffinity(0, cpu_list)
                return True
            elif platform.system() == 'Windows':
                import ctypes
                kernel32 = ctypes.windll.kernel32
                
                # Convert CPU list to mask
                mask = 0
                for cpu in cpu_list:
                    mask |= (1 << cpu)
                    
                thread_handle = kernel32.GetCurrentThread()
                if kernel32.SetThreadAffinityMask(thread_handle, mask):
                    return True
        except:
            pass
            
        return False
    
    def get_memory_bandwidth_estimate(self, node_id: int) -> float:
        """Estimate memory bandwidth for a NUMA node (GB/s)"""
        # These are conservative estimates
        # Real implementation might benchmark actual bandwidth
        
        if platform.system() == 'Linux':
            try:
                # Check if this is a high-end server system
                with open('/proc/cpuinfo', 'r') as f:
                    cpuinfo = f.read()
                    if 'Xeon' in cpuinfo or 'EPYC' in cpuinfo:
                        # Server CPUs typically have higher bandwidth
                        return 100.0  # GB/s per node
            except:
                pass
                
        # Default estimates based on node count
        if len(self.numa_nodes) >= 4:
            return 80.0  # High-end multi-socket system
        elif len(self.numa_nodes) >= 2:
            return 60.0  # Dual-socket system
        else:
            return 40.0  # Single socket or unknown
    
    def should_use_numa_optimization(self) -> bool:
        """Determine if NUMA optimization would be beneficial"""
        # NUMA optimization is beneficial when:
        # 1. Multiple NUMA nodes exist
        # 2. System has sufficient memory
        # 3. Workload is large enough to benefit
        
        if len(self.numa_nodes) <= 1:
            return False
            
        try:
            import psutil
            total_memory = psutil.virtual_memory().total
            # Only use NUMA optimization on systems with significant memory
            if total_memory < 32 * 1024 * 1024 * 1024:  # 32GB
                return False
        except:
            pass
            
        return True
    
    def get_numa_stats(self) -> Dict[str, any]:
        """Get NUMA topology statistics"""
        stats = {
            'numa_nodes': len(self.numa_nodes),
            'total_cpus': sum(len(cpus) for cpus in self.numa_nodes.values()),
            'topology': {}
        }
        
        for node_id, cpus in self.numa_nodes.items():
            stats['topology'][f'node_{node_id}'] = {
                'cpu_count': len(cpus),
                'cpu_list': cpus,
                'memory_bandwidth_estimate_gbps': self.get_memory_bandwidth_estimate(node_id)
            }
            
        stats['numa_optimization_recommended'] = self.should_use_numa_optimization()
        
        return stats