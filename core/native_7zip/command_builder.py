#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
7zip command builder optimized for Windows forensic workloads
Creates high-performance archive commands with forensic integrity focus
"""

import os
import platform
from pathlib import Path
from typing import List, Dict, Any, Optional
import psutil

from core.logger import logger


class ForensicCommandBuilder:
    """
    Builds optimized 7zip commands for Windows forensic workloads
    
    Focuses on:
    - Maximum speed (store mode, no compression) 
    - Forensic integrity (preserve paths, timestamps)
    - Windows optimization (thread count, memory usage)
    - Robust error handling
    """
    
    def __init__(self):
        """Initialize with system-optimized settings"""
        self.cpu_count = os.cpu_count() or 4
        self.total_memory_gb = self._get_system_memory_gb()
        self.optimal_threads = self._calculate_optimal_threads()
        self.optimal_memory_percent = self._calculate_memory_usage()
        
        logger.debug(f"ForensicCommandBuilder initialized:")
        logger.debug(f"  CPU cores: {self.cpu_count}")
        logger.debug(f"  System memory: {self.total_memory_gb:.1f} GB")
        logger.debug(f"  Optimal threads: {self.optimal_threads}")
        logger.debug(f"  Memory usage: {self.optimal_memory_percent}%")
    
    def _get_system_memory_gb(self) -> float:
        """Get total system memory in GB"""
        try:
            return psutil.virtual_memory().total / (1024**3)
        except Exception:
            return 8.0  # Default fallback
    
    def _calculate_optimal_threads(self) -> int:
        """
        Calculate optimal thread count for 7zip on Windows
        
        7zip threading considerations:
        - Store mode (no compression): I/O bound, moderate threading benefit
        - Too many threads can hurt performance on slower storage
        - Sweet spot is usually 2-4x CPU cores for modern systems
        """
        if self.cpu_count <= 2:
            return self.cpu_count  # Use all cores on low-core systems
        elif self.cpu_count <= 8:
            return min(self.cpu_count * 2, 16)  # 2x cores, max 16
        elif self.cpu_count <= 16:
            return min(self.cpu_count, 24)     # 1x cores, max 24  
        else:
            return min(32, self.cpu_count)     # Cap at 32 for very high core count
    
    def _calculate_memory_usage(self) -> int:
        """Calculate optimal memory usage percentage for 7zip"""
        if self.total_memory_gb >= 16:
            return 70  # Use 70% on high-memory systems
        elif self.total_memory_gb >= 8:
            return 60  # Use 60% on medium-memory systems
        else:
            return 40  # Be conservative on low-memory systems
    
    def build_archive_command(self, binary_path: Path, source_path: Path, 
                            output_path: Path, compression_mode: str = "store") -> List[str]:
        """
        Build optimized 7zip archive command for forensic workloads
        
        Args:
            binary_path: Path to 7za.exe
            source_path: Directory or file to archive
            output_path: Output archive path (.zip when using -tzip)
            compression_mode: "store" (fastest), "fast", "normal", "max"
            
        Returns:
            Complete command line arguments list
        """
        # Base command structure
        cmd = [str(binary_path)]
        
        # Archive operation
        cmd.append('a')  # Add files to archive
        
        # Force ZIP format output (instead of 7z)
        cmd.append('-tzip')
        
        # Compression settings - optimized for forensic speed
        compression_settings = {
            "store": ['-mx0'],      # No compression (fastest)
            "fast": ['-mx1'],       # Fastest compression
            "normal": ['-mx5'],     # Normal compression
            "max": ['-mx9']         # Maximum compression
        }
        cmd.extend(compression_settings.get(compression_mode, ['-mx0']))
        
        # Threading optimization - use full thread count (16 thread cap removed)
        cmd.append(f'-mmt{self.optimal_threads}')  # Use optimal threads without artificial ZIP cap
        
        # Memory optimization (remove problematic parameter for ZIP)
        # cmd.append(f'-mmemuse=p{self.optimal_memory_percent}')  # Not used for ZIP
        
        # Simplified settings for ZIP format
        cmd.extend([
            '-y',           # Auto-confirm all prompts (non-interactive)
            '-bb1',         # Basic progress output (parseable)
        ])
        
        # Working directory (simplified format)
        # cmd.append(f'-w{source_path.parent}')  # Skip working directory for now
        
        # Output archive path
        cmd.append(str(output_path))
        
        # Source specification
        if source_path.is_dir():
            # For directories, include all contents recursively
            cmd.append(f'{source_path}\\*')
        else:
            # For single files
            cmd.append(str(source_path))
        
        logger.debug(f"Built 7zip command: {' '.join(cmd)}")
        return cmd
    
    def build_test_command(self, binary_path: Path, archive_path: Path) -> List[str]:
        """
        Build command to test archive integrity
        
        Args:
            binary_path: Path to 7za.exe
            archive_path: Archive to test
            
        Returns:
            Command to test archive
        """
        cmd = [
            str(binary_path),
            't',            # Test archive
            '-bb1',         # Basic progress output
            str(archive_path)
        ]
        
        logger.debug(f"Built test command: {' '.join(cmd)}")
        return cmd
    
    def build_list_command(self, binary_path: Path, archive_path: Path) -> List[str]:
        """
        Build command to list archive contents
        
        Args:
            binary_path: Path to 7za.exe  
            archive_path: Archive to list
            
        Returns:
            Command to list archive contents
        """
        cmd = [
            str(binary_path),
            'l',            # List archive contents
            '-slt',         # Technical listing format
            str(archive_path)
        ]
        
        logger.debug(f"Built list command: {' '.join(cmd)}")
        return cmd
    
    def get_optimization_info(self) -> Dict[str, Any]:
        """Get current optimization settings for diagnostics"""
        return {
            'cpu_cores': self.cpu_count,
            'system_memory_gb': self.total_memory_gb,
            'optimal_threads': self.optimal_threads,
            'memory_usage_percent': self.optimal_memory_percent,
            'platform': platform.system(),
            'platform_version': platform.version(),
            'optimization_strategy': self._get_optimization_strategy()
        }
    
    def _get_optimization_strategy(self) -> str:
        """Get description of current optimization strategy"""
        if self.cpu_count <= 4:
            return "Low-core optimization (conservative threading)"
        elif self.cpu_count <= 8:
            return "Mid-range optimization (2x threading)"
        elif self.cpu_count <= 16:
            return "High-core optimization (balanced threading)"
        else:
            return "Very high-core optimization (capped threading)"
    
    def estimate_performance_improvement(self, file_count: int, total_size_mb: float) -> Dict[str, Any]:
        """
        Estimate performance improvement vs Python ZIP
        
        Args:
            file_count: Number of files to archive
            total_size_mb: Total size in MB
            
        Returns:
            Performance estimates
        """
        # Baseline Python ZIP performance (from your current metrics)
        python_zip_speed = 290  # MB/s from current implementation
        
        # 7zip native performance estimates (conservative)
        if total_size_mb < 100:  # Small workloads
            estimated_7zip_speed = 2000  # MB/s
            improvement_factor = 7
        elif total_size_mb < 1000:  # Medium workloads  
            estimated_7zip_speed = 3000  # MB/s
            improvement_factor = 10
        else:  # Large workloads
            estimated_7zip_speed = 4000  # MB/s
            improvement_factor = 14
        
        # Time estimates
        python_time = total_size_mb / python_zip_speed
        native_7zip_time = total_size_mb / estimated_7zip_speed
        time_saved = python_time - native_7zip_time
        
        return {
            'python_zip_speed_mbps': python_zip_speed,
            'estimated_7zip_speed_mbps': estimated_7zip_speed,
            'improvement_factor': improvement_factor,
            'python_time_seconds': python_time,
            'native_7zip_time_seconds': native_7zip_time,
            'time_saved_seconds': time_saved,
            'time_saved_percent': (time_saved / python_time * 100) if python_time > 0 else 0,
            'file_count': file_count,
            'total_size_mb': total_size_mb
        }