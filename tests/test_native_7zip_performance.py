#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Performance test comparing Native 7zip vs Buffered Python ZIP operations
Tests the hybrid implementation to validate 7-14x performance improvements
"""

import time
import tempfile
import os
import shutil
from pathlib import Path
from typing import Dict, Any, List

# Import hybrid implementation
from utils.zip_utils import ZipUtility, ArchiveMethod, ZipSettings
from core.native_7zip.controller import Native7ZipController
from core.buffered_zip_ops import BufferedZipOperations
from core.logger import logger


class PerformanceTestSuite:
    """Test suite for comparing archive performance across methods"""
    
    def __init__(self):
        """Initialize test suite"""
        self.test_results = []
        
    def create_test_data(self, test_dir: Path, scenario: str) -> Dict[str, Any]:
        """
        Create test data for different performance scenarios
        
        Args:
            test_dir: Directory to create test files in
            scenario: 'small_files', 'large_files', 'mixed_workload', or 'forensic_simulation'
            
        Returns:
            Dictionary with test data metrics
        """
        test_dir.mkdir(exist_ok=True)
        
        if scenario == 'small_files':
            # Many small files (typical forensic evidence)
            file_count = 100
            file_size_kb = 50
            
            for i in range(file_count):
                file_path = test_dir / f"evidence_{i:03d}.txt"
                with open(file_path, 'wb') as f:
                    f.write(os.urandom(file_size_kb * 1024))
                    
            return {
                'scenario': scenario,
                'file_count': file_count,
                'total_size_mb': (file_count * file_size_kb) / 1024,
                'description': f'{file_count} small files (~{file_size_kb}KB each)'
            }
            
        elif scenario == 'large_files':
            # Fewer large files (video evidence)
            file_count = 5
            file_size_mb = 10
            
            for i in range(file_count):
                file_path = test_dir / f"video_evidence_{i:02d}.mp4"
                with open(file_path, 'wb') as f:
                    f.write(os.urandom(file_size_mb * 1024 * 1024))
                    
            return {
                'scenario': scenario,
                'file_count': file_count,
                'total_size_mb': file_count * file_size_mb,
                'description': f'{file_count} large files (~{file_size_mb}MB each)'
            }
            
        elif scenario == 'mixed_workload':
            # Realistic mix of file sizes
            small_count = 50
            medium_count = 10
            large_count = 3
            
            total_size_mb = 0
            
            # Small files
            for i in range(small_count):
                file_path = test_dir / f"small_{i:03d}.txt"
                size = 25 * 1024  # 25KB
                with open(file_path, 'wb') as f:
                    f.write(os.urandom(size))
                total_size_mb += size / (1024 * 1024)
                
            # Medium files
            for i in range(medium_count):
                file_path = test_dir / f"medium_{i:02d}.jpg"
                size = 2 * 1024 * 1024  # 2MB
                with open(file_path, 'wb') as f:
                    f.write(os.urandom(size))
                total_size_mb += size / (1024 * 1024)
                
            # Large files
            for i in range(large_count):
                file_path = test_dir / f"large_{i:02d}.mp4"
                size = 8 * 1024 * 1024  # 8MB
                with open(file_path, 'wb') as f:
                    f.write(os.urandom(size))
                total_size_mb += size / (1024 * 1024)
                
            return {
                'scenario': scenario,
                'file_count': small_count + medium_count + large_count,
                'total_size_mb': total_size_mb,
                'description': f'Mixed: {small_count} small + {medium_count} medium + {large_count} large files'
            }
            
        elif scenario == 'forensic_simulation':
            # Simulate real forensic data structure
            base_dir = test_dir / "forensic_evidence"
            base_dir.mkdir()
            
            # Photos directory
            photos_dir = base_dir / "photos"
            photos_dir.mkdir()
            for i in range(25):
                file_path = photos_dir / f"IMG_{i:04d}.jpg"
                with open(file_path, 'wb') as f:
                    f.write(os.urandom(1024 * 1024))  # 1MB photos
                    
            # Documents directory
            docs_dir = base_dir / "documents"
            docs_dir.mkdir()
            for i in range(15):
                file_path = docs_dir / f"document_{i:02d}.pdf"
                with open(file_path, 'wb') as f:
                    f.write(os.urandom(512 * 1024))  # 512KB documents
                    
            # Video directory
            video_dir = base_dir / "videos"
            video_dir.mkdir()
            for i in range(3):
                file_path = video_dir / f"surveillance_{i:02d}.mp4"
                with open(file_path, 'wb') as f:
                    f.write(os.urandom(15 * 1024 * 1024))  # 15MB videos
                    
            total_size_mb = (25 * 1) + (15 * 0.5) + (3 * 15)  # Approximate
            
            return {
                'scenario': scenario,
                'file_count': 43,
                'total_size_mb': total_size_mb,
                'description': 'Forensic simulation: photos, documents, videos',
                'test_dir': base_dir  # Use subdirectory for this test
            }
            
        else:
            raise ValueError(f"Unknown scenario: {scenario}")
    
    def test_native_7zip_performance(self, test_data_dir: Path, test_info: Dict[str, Any]) -> Dict[str, Any]:
        """Test native 7zip performance"""
        print(f"Testing Native 7-Zip performance...")
        
        try:
            # Initialize native controller
            controller = Native7ZipController()
            
            if not controller.is_available():
                return {
                    'method': 'native_7zip',
                    'success': False,
                    'error': '7za.exe not available',
                    'duration': 0,
                    'speed_mbps': 0
                }
            
            # Create output archive
            output_path = test_data_dir.parent / f"test_native_{test_info['scenario']}.7z"
            
            # Run performance test
            start_time = time.time()
            result = controller.create_archive(test_data_dir, output_path)
            end_time = time.time()
            
            duration = end_time - start_time
            speed_mbps = test_info['total_size_mb'] / duration if duration > 0 else 0
            
            # Get metrics
            metrics = controller.get_metrics()
            
            # Clean up
            if output_path.exists():
                output_path.unlink()
                
            return {
                'method': 'native_7zip',
                'success': result.success,
                'error': str(result.error) if not result.success else None,
                'duration': duration,
                'speed_mbps': speed_mbps,
                'files_processed': metrics.files_processed if metrics else 0,
                'total_files': metrics.total_files if metrics else 0,
                'archive_size': metrics.archive_size if metrics else 0
            }
            
        except Exception as e:
            return {
                'method': 'native_7zip',
                'success': False,
                'error': str(e),
                'duration': 0,
                'speed_mbps': 0
            }
    
    def test_buffered_python_performance(self, test_data_dir: Path, test_info: Dict[str, Any]) -> Dict[str, Any]:
        """Test buffered Python ZIP performance"""
        print(f"Testing Buffered Python performance...")
        
        try:
            # Initialize buffered operations
            buffered_ops = BufferedZipOperations()
            
            # Create output archive
            output_path = test_data_dir.parent / f"test_buffered_{test_info['scenario']}.zip"
            
            # Run performance test
            start_time = time.time()
            result = buffered_ops.create_archive_buffered(test_data_dir, output_path)
            end_time = time.time()
            
            duration = end_time - start_time
            speed_mbps = test_info['total_size_mb'] / duration if duration > 0 else 0
            
            # Clean up
            if output_path.exists():
                output_path.unlink()
                
            return {
                'method': 'buffered_python',
                'success': result.success,
                'error': str(result.error) if not result.success else None,
                'duration': duration,
                'speed_mbps': speed_mbps,
                'files_processed': result.metadata.get('files_processed', 0) if result.success else 0,
                'total_files': result.metadata.get('total_files', 0) if result.success else 0,
                'archive_size': result.metadata.get('archive_size', 0) if result.success else 0
            }
            
        except Exception as e:
            return {
                'method': 'buffered_python',
                'success': False,
                'error': str(e),
                'duration': 0,
                'speed_mbps': 0
            }
    
    def test_hybrid_implementation(self, test_data_dir: Path, test_info: Dict[str, Any]) -> Dict[str, Any]:
        """Test hybrid ZipUtility implementation"""
        print(f"Testing Hybrid implementation (should use Native 7-Zip)...")
        
        try:
            # Initialize hybrid utility with native 7zip preference
            zip_util = ZipUtility(archive_method=ArchiveMethod.NATIVE_7ZIP)
            
            # Create settings
            settings = ZipSettings()
            settings.archive_method = ArchiveMethod.NATIVE_7ZIP
            
            # Create output archive
            output_path = test_data_dir.parent / f"test_hybrid_{test_info['scenario']}"
            # Extension will be determined by active method (.7z for native)
            
            # Run performance test
            start_time = time.time()
            success = zip_util.create_archive(test_data_dir, output_path, settings)
            end_time = time.time()
            
            duration = end_time - start_time
            speed_mbps = test_info['total_size_mb'] / duration if duration > 0 else 0
            
            # Get method info
            method_info = zip_util.get_method_info()
            active_method = zip_util.get_active_method()
            
            # Clean up (native 7zip now creates .zip files)
            archive_path = output_path.with_suffix('.zip')
            if archive_path.exists():
                archive_path.unlink()
                    
            return {
                'method': f'hybrid_{active_method}',
                'success': success,
                'error': None if success else 'Archive creation failed',
                'duration': duration,
                'speed_mbps': speed_mbps,
                'active_method': active_method,
                'method_info': method_info
            }
            
        except Exception as e:
            return {
                'method': 'hybrid',
                'success': False,
                'error': str(e),
                'duration': 0,
                'speed_mbps': 0
            }
    
    def run_comprehensive_test(self, scenarios: List[str] = None) -> List[Dict[str, Any]]:
        """Run comprehensive performance tests across multiple scenarios"""
        if scenarios is None:
            scenarios = ['small_files', 'large_files', 'mixed_workload', 'forensic_simulation']
        
        results = []\n        \n        for scenario in scenarios:\n            print(f\"\\n{'='*60}\")\n            print(f\"Running {scenario.upper()} performance test\")\n            print(f\"{'='*60}\")\n            \n            try:\n                with tempfile.TemporaryDirectory() as temp_dir:\n                    temp_path = Path(temp_dir)\n                    test_data_dir = temp_path / \"test_data\"\n                    \n                    # Create test data\n                    print(f\"Creating test data for {scenario}...\")\n                    test_info = self.create_test_data(test_data_dir, scenario)\n                    \n                    # Override test directory for forensic simulation\n                    if 'test_dir' in test_info:\n                        test_data_dir = test_info['test_dir']\n                    \n                    print(f\"Test data: {test_info['description']}\")\n                    print(f\"Total size: {test_info['total_size_mb']:.1f} MB\")\n                    print(f\"File count: {test_info['file_count']}\")\n                    \n                    # Test all methods\n                    scenario_results = {\n                        'scenario': scenario,\n                        'test_info': test_info,\n                        'results': []\n                    }\n                    \n                    # Test Native 7zip\n                    native_result = self.test_native_7zip_performance(test_data_dir, test_info)\n                    scenario_results['results'].append(native_result)\n                    \n                    # Test Buffered Python\n                    buffered_result = self.test_buffered_python_performance(test_data_dir, test_info)\n                    scenario_results['results'].append(buffered_result)\n                    \n                    # Test Hybrid Implementation\n                    hybrid_result = self.test_hybrid_implementation(test_data_dir, test_info)\n                    scenario_results['results'].append(hybrid_result)\n                    \n                    results.append(scenario_results)\n                    \n                    # Print scenario results\n                    self._print_scenario_results(scenario_results)\n                    \n            except Exception as e:\n                print(f\"Error in {scenario} test: {e}\")\n                results.append({\n                    'scenario': scenario,\n                    'error': str(e),\n                    'results': []\n                })\n        \n        return results\n    \n    def _print_scenario_results(self, scenario_results: Dict[str, Any]):\n        \"\"\"Print results for a single scenario\"\"\"\n        print(f\"\\nResults for {scenario_results['scenario']}:\")\n        print(\"-\" * 50)\n        \n        for result in scenario_results['results']:\n            method = result['method']\n            if result['success']:\n                print(f\"{method:15} | {result['duration']:6.2f}s | {result['speed_mbps']:8.1f} MB/s\")\n            else:\n                print(f\"{method:15} | FAILED: {result['error']}\")\n    \n    def print_summary(self, all_results: List[Dict[str, Any]]):\n        \"\"\"Print comprehensive summary of all test results\"\"\"\n        print(f\"\\n{'='*80}\")\n        print(\"PERFORMANCE TEST SUMMARY\")\n        print(f\"{'='*80}\")\n        \n        for scenario_results in all_results:\n            if 'error' in scenario_results:\n                continue\n                \n            scenario = scenario_results['scenario']\n            test_info = scenario_results['test_info']\n            \n            print(f\"\\n{scenario.upper()} ({test_info['description']})\")\n            print(f\"Total: {test_info['total_size_mb']:.1f} MB, {test_info['file_count']} files\")\n            print(\"-\" * 60)\n            \n            # Find fastest method\n            successful_results = [r for r in scenario_results['results'] if r['success']]\n            if successful_results:\n                fastest = max(successful_results, key=lambda x: x['speed_mbps'])\n                \n                print(f\"{'Method':<20} {'Time':<8} {'Speed':<12} {'Improvement':<12}\")\n                print(\"-\" * 60)\n                \n                for result in scenario_results['results']:\n                    if result['success']:\n                        improvement = result['speed_mbps'] / fastest['speed_mbps'] * 100\n                        print(f\"{result['method']:<20} {result['duration']:6.2f}s {result['speed_mbps']:8.1f} MB/s  {improvement:6.1f}%\")\n                    else:\n                        print(f\"{result['method']:<20} FAILED: {result.get('error', 'Unknown error')}\")\n                        \n                print(f\"\\n🏆 Fastest: {fastest['method']} at {fastest['speed_mbps']:.1f} MB/s\")\n            else:\n                print(\"❌ All methods failed for this scenario\")\n        \n        # Overall performance summary\n        self._print_overall_summary(all_results)\n    \n    def _print_overall_summary(self, all_results: List[Dict[str, Any]]):\n        \"\"\"Print overall performance summary across all scenarios\"\"\"\n        print(f\"\\n{'='*80}\")\n        print(\"OVERALL PERFORMANCE COMPARISON\")\n        print(f\"{'='*80}\")\n        \n        # Aggregate results by method\n        method_stats = {}\n        \n        for scenario_results in all_results:\n            if 'error' in scenario_results:\n                continue\n                \n            for result in scenario_results['results']:\n                method = result['method']\n                if method not in method_stats:\n                    method_stats[method] = {'speeds': [], 'successes': 0, 'failures': 0}\n                \n                if result['success']:\n                    method_stats[method]['speeds'].append(result['speed_mbps'])\n                    method_stats[method]['successes'] += 1\n                else:\n                    method_stats[method]['failures'] += 1\n        \n        # Print method summaries\n        for method, stats in method_stats.items():\n            if stats['speeds']:\n                avg_speed = sum(stats['speeds']) / len(stats['speeds'])\n                max_speed = max(stats['speeds'])\n                print(f\"\\n{method.upper()}:\")\n                print(f\"  Average Speed: {avg_speed:.1f} MB/s\")\n                print(f\"  Peak Speed: {max_speed:.1f} MB/s\")\n                print(f\"  Success Rate: {stats['successes']}/{stats['successes'] + stats['failures']}\")\n            else:\n                print(f\"\\n{method.upper()}: Failed all tests\")\n\n\ndef main():\n    \"\"\"Main test execution function\"\"\"\n    print(\"Native 7-Zip vs Buffered Python Performance Test\")\n    print(\"=\" * 50)\n    \n    # Initialize test suite\n    test_suite = PerformanceTestSuite()\n    \n    # Run comprehensive tests\n    results = test_suite.run_comprehensive_test()\n    \n    # Print summary\n    test_suite.print_summary(results)\n    \n    print(f\"\\n{'='*80}\")\n    print(\"Test completed. Check results above for performance comparison.\")\n    print(\"Expected: Native 7-Zip should be 7-14x faster than Buffered Python\")\n    print(f\"{'='*80}\")\n\n\nif __name__ == \"__main__\":\n    main()