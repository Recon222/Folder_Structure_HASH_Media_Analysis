# core/workload_analyzer.py
import statistics
import psutil
from typing import List, Dict, Tuple, Optional
from pathlib import Path
from collections import defaultdict

class WorkloadAnalyzer:
    """Analyze workload characteristics for optimization"""
    
    @staticmethod
    def calculate_adaptive_thresholds(files: List[Path], 
                                    available_memory: Optional[int] = None) -> Dict[str, int]:
        """Calculate optimal size thresholds based on workload"""
        
        if not files:
            # Default thresholds
            return {
                'tiny': 1_000_000,      # 1MB
                'small': 50_000_000,    # 50MB
                'medium': 500_000_000,  # 500MB
                'large': 1_000_000_000  # 1GB
            }
        
        # Get file sizes
        sizes = []
        for f in files:
            try:
                if f.exists():
                    sizes.append(f.stat().st_size)
            except Exception as e:
                continue
                
        if not sizes:
            return WorkloadAnalyzer.calculate_adaptive_thresholds([])
        
        total_size = sum(sizes)
        
        # Get system resources
        if available_memory is None:
            available_memory = psutil.virtual_memory().available
        
        # Calculate statistics
        sorted_sizes = sorted(sizes)
        stats = {
            'count': len(sizes),
            'total': total_size,
            'mean': statistics.mean(sizes),
            'median': statistics.median(sizes),
            'stdev': statistics.stdev(sizes) if len(sizes) > 1 else 0,
            'min': min(sizes),
            'max': max(sizes),
            'p10': sorted_sizes[len(sizes)//10] if len(sizes) >= 10 else sorted_sizes[0],
            'p25': sorted_sizes[len(sizes)//4] if len(sizes) >= 4 else sorted_sizes[0],
            'p50': sorted_sizes[len(sizes)//2],
            'p75': sorted_sizes[3*len(sizes)//4] if len(sizes) >= 4 else sorted_sizes[-1],
            'p90': sorted_sizes[9*len(sizes)//10] if len(sizes) >= 10 else sorted_sizes[-1]
        }
        
        # Dynamic threshold calculation
        thresholds = {}
        
        # Memory constraints
        memory_per_worker = available_memory // 16  # Assume up to 16 workers
        max_buffer_size = memory_per_worker // 4   # Max 25% of worker memory for buffers
        
        # Tiny files: bottom 10% or very small files
        tiny_threshold = min(
            stats['p10'],
            1_000_000,  # Max 1MB for tiny
            max_buffer_size // 100  # Can handle 100 tiny files in memory
        )
        
        # Small files: bottom 25% with memory constraints
        small_threshold = min(
            stats['p25'],
            max_buffer_size // 10,  # Can handle 10 small files in memory
            100_000_000  # Max 100MB for small
        )
        
        # Large files: top 25% or files requiring special handling
        large_threshold = max(
            stats['p75'],
            500_000_000,  # Min 500MB for large
            memory_per_worker  # Files larger than worker memory
        )
        
        # Medium: between small and large
        medium_threshold = (small_threshold + large_threshold) // 2
        
        # Adjust based on total workload
        if total_size > available_memory * 2:
            # Heavy workload: be more conservative
            tiny_threshold = min(tiny_threshold, 500_000)      # 500KB
            small_threshold = min(small_threshold, 25_000_000) # 25MB
            medium_threshold = min(medium_threshold, 250_000_000) # 250MB
            large_threshold = min(large_threshold, 500_000_000)   # 500MB
        
        # Ensure proper ordering
        thresholds['tiny'] = max(100_000, tiny_threshold)  # Min 100KB
        thresholds['small'] = max(thresholds['tiny'] * 10, small_threshold)
        thresholds['medium'] = max(thresholds['small'] * 5, medium_threshold)
        thresholds['large'] = max(thresholds['medium'] * 2, large_threshold)
        
        return thresholds
    
    @staticmethod
    def optimize_batch_sizes(files: List[Path], 
                           thresholds: Dict[str, int]) -> Dict[str, List[List[Path]]]:
        """Group files with workload-aware batching"""
        
        # First, categorize files by size
        groups = {
            'tiny': [],
            'small': [],
            'medium': [],
            'large': [],
            'huge': []
        }
        
        for file in files:
            try:
                if not file.exists():
                    continue
                    
                size = file.stat().st_size
                
                if size < thresholds['tiny']:
                    groups['tiny'].append(file)
                elif size < thresholds['small']:
                    groups['small'].append(file)
                elif size < thresholds['medium']:
                    groups['medium'].append(file)
                elif size < thresholds['large']:
                    groups['large'].append(file)
                else:
                    groups['huge'].append(file)
            except Exception as e:
                continue
        
        # Optimize batches within each group
        return WorkloadAnalyzer._optimize_group_batches(groups, thresholds)
    
    @staticmethod
    def _optimize_group_batches(groups: Dict[str, List[Path]], 
                              thresholds: Dict[str, int]) -> Dict[str, List[List[Path]]]:
        """Create optimal batches within groups"""
        optimized = {}
        
        # Get available memory for batching decisions
        available_memory = psutil.virtual_memory().available
        
        for group_name, files in groups.items():
            if not files:
                continue
            
            if group_name == 'tiny':
                # Tiny files: large batches for efficient processing
                # Batch by count and total size
                batch_size = min(1000, len(files))  # Max 1000 files per batch
                max_batch_bytes = available_memory // 100  # Max 1% of memory per batch
                
                batches = []
                current_batch = []
                current_batch_size = 0
                
                for file in files:
                    file_size = file.stat().st_size
                    if len(current_batch) >= batch_size or current_batch_size + file_size > max_batch_bytes:
                        if current_batch:
                            batches.append(current_batch)
                        current_batch = [file]
                        current_batch_size = file_size
                    else:
                        current_batch.append(file)
                        current_batch_size += file_size
                
                if current_batch:
                    batches.append(current_batch)
                    
                optimized[group_name] = batches
                
            elif group_name == 'small':
                # Small files: moderate batches
                batch_size = 100  # 100 files per batch
                optimized[group_name] = [
                    files[i:i+batch_size] 
                    for i in range(0, len(files), batch_size)
                ]
                
            elif group_name in ['medium', 'large']:
                # Medium/large files: smaller batches to avoid memory pressure
                batch_size = 10  # 10 files per batch
                optimized[group_name] = [
                    files[i:i+batch_size] 
                    for i in range(0, len(files), batch_size)
                ]
                
            else:  # huge
                # Huge files: process individually
                optimized[group_name] = [[file] for file in files]
        
        return optimized
    
    @staticmethod
    def analyze_workload_pattern(files: List[Path]) -> Dict[str, any]:
        """Analyze workload patterns for optimization hints"""
        
        if not files:
            return {'pattern': 'empty'}
        
        # Collect file information
        file_info = []
        extensions = defaultdict(int)
        total_size = 0
        
        for file in files:
            try:
                if file.exists():
                    size = file.stat().st_size
                    ext = file.suffix.lower()
                    file_info.append({
                        'path': file,
                        'size': size,
                        'ext': ext,
                        'name': file.name
                    })
                    extensions[ext] += 1
                    total_size += size
            except Exception as e:
                continue
        
        if not file_info:
            return {'pattern': 'empty'}
        
        # Analyze patterns
        sizes = [f['size'] for f in file_info]
        
        # Determine dominant file type
        dominant_ext = max(extensions.items(), key=lambda x: x[1])[0] if extensions else ''
        dominant_ratio = extensions[dominant_ext] / len(file_info) if dominant_ext else 0
        
        # Check for common patterns
        pattern = {
            'type': 'mixed',
            'total_files': len(file_info),
            'total_size': total_size,
            'avg_size': statistics.mean(sizes),
            'size_variance': statistics.variance(sizes) if len(sizes) > 1 else 0,
            'dominant_extension': dominant_ext,
            'dominant_ratio': dominant_ratio,
            'recommendations': []
        }
        
        # Identify specific patterns
        video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'}
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
        document_extensions = {'.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt'}
        archive_extensions = {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2'}
        
        # Count file types
        video_count = sum(1 for f in file_info if f['ext'] in video_extensions)
        image_count = sum(1 for f in file_info if f['ext'] in image_extensions)
        document_count = sum(1 for f in file_info if f['ext'] in document_extensions)
        archive_count = sum(1 for f in file_info if f['ext'] in archive_extensions)
        
        # Determine pattern type
        if video_count > len(file_info) * 0.7:
            pattern['type'] = 'video'
            pattern['recommendations'].append('Use minimal compression for archives')
            pattern['recommendations'].append('Large buffer sizes recommended')
            pattern['recommendations'].append('Sequential access pattern likely')
            
        elif image_count > len(file_info) * 0.7:
            pattern['type'] = 'image'
            pattern['recommendations'].append('High parallelism suitable')
            pattern['recommendations'].append('Consider image-specific compression')
            
        elif document_count > len(file_info) * 0.7:
            pattern['type'] = 'document'
            pattern['recommendations'].append('Small buffer sizes sufficient')
            pattern['recommendations'].append('High compression suitable')
            
        elif len(file_info) > 1000 and pattern['avg_size'] < 1_000_000:
            pattern['type'] = 'many_small'
            pattern['recommendations'].append('Maximum parallelism recommended')
            pattern['recommendations'].append('Batch processing essential')
            pattern['recommendations'].append('Consider archive creation')
            
        elif len(file_info) < 10 and pattern['avg_size'] > 1_000_000_000:
            pattern['type'] = 'few_large'
            pattern['recommendations'].append('Limited parallelism to avoid disk thrashing')
            pattern['recommendations'].append('Large buffer sizes essential')
            pattern['recommendations'].append('Consider memory-mapped I/O')
        
        # Add size distribution info
        if sizes:
            sorted_sizes = sorted(sizes)
            pattern['size_distribution'] = {
                'min': min(sizes),
                'p25': sorted_sizes[len(sizes)//4] if len(sizes) >= 4 else sorted_sizes[0],
                'median': statistics.median(sizes),
                'p75': sorted_sizes[3*len(sizes)//4] if len(sizes) >= 4 else sorted_sizes[-1],
                'max': max(sizes)
            }
        
        return pattern
    
    @staticmethod
    def recommend_worker_count(pattern: Dict[str, any], 
                             disk_type: str,
                             cpu_count: int) -> int:
        """Recommend optimal worker count based on workload pattern and disk type"""
        
        base_workers = cpu_count
        
        # Adjust based on pattern type
        if pattern['type'] == 'many_small':
            # Many small files benefit from high parallelism
            if disk_type == 'nvme':
                return min(32, cpu_count * 2)
            elif disk_type == 'ssd':
                return min(16, cpu_count)
            else:  # HDD
                return min(4, cpu_count)  # Limited to avoid seek thrashing
                
        elif pattern['type'] == 'few_large':
            # Few large files need limited parallelism
            if disk_type == 'nvme':
                return min(8, cpu_count)
            elif disk_type == 'ssd':
                return min(4, cpu_count)
            else:  # HDD
                return 2  # Minimal parallelism
                
        elif pattern['type'] == 'video':
            # Video files are typically large and sequential
            if disk_type in ['nvme', 'ssd']:
                return min(6, cpu_count)
            else:
                return 2
                
        else:
            # Mixed or other patterns: balanced approach
            if disk_type == 'nvme':
                return min(16, cpu_count)
            elif disk_type == 'ssd':
                return min(8, cpu_count)
            else:
                return min(4, cpu_count)