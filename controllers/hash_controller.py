#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hash controller - coordinates hash operations between UI and workers
"""

from pathlib import Path
from typing import List, Optional, Dict, Any

from core.workers.hash_worker import SingleHashWorker, VerificationWorker
from core.settings_manager import settings
from core.logger import logger


class HashController:
    """Coordinates all hash operations"""
    
    def __init__(self):
        self.current_operation: Optional[SingleHashWorker | VerificationWorker] = None
        
    def start_single_hash_operation(
        self,
        paths: List[Path],
        algorithm: str = None
    ) -> SingleHashWorker:
        """Start a single hash operation (hash files/folders)
        
        Args:
            paths: List of file/folder paths to hash
            algorithm: Hash algorithm to use (defaults to settings)
            
        Returns:
            SingleHashWorker thread
        """
        if self.current_operation and self.current_operation.isRunning():
            raise RuntimeError("Another hash operation is already running")
            
        # Use default algorithm if none specified
        if algorithm is None:
            algorithm = settings.hash_algorithm
            
        # Validate algorithm
        if algorithm.lower() not in ['sha256', 'md5']:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        
        # Validate paths
        if not paths:
            raise ValueError("No files or folders specified")
            
        valid_paths = [p for p in paths if p.exists()]
        if not valid_paths:
            raise ValueError("No valid files or folders found")
        
        # Create and return worker
        worker = SingleHashWorker(valid_paths, algorithm)
        self.current_operation = worker
        
        logger.info(f"Starting single hash operation with {algorithm} on {len(valid_paths)} paths")
        return worker
        
    def start_verification_operation(
        self,
        source_paths: List[Path],
        target_paths: List[Path],
        algorithm: str = None
    ) -> VerificationWorker:
        """Start a verification operation (compare two sets of files)
        
        Args:
            source_paths: Source file/folder paths to hash
            target_paths: Target file/folder paths to compare against
            algorithm: Hash algorithm to use (defaults to settings)
            
        Returns:
            VerificationWorker thread
        """
        if self.current_operation and self.current_operation.isRunning():
            raise RuntimeError("Another hash operation is already running")
            
        # Use default algorithm if none specified
        if algorithm is None:
            algorithm = settings.hash_algorithm
            
        # Validate algorithm
        if algorithm.lower() not in ['sha256', 'md5']:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        
        # Validate source paths
        if not source_paths:
            raise ValueError("No source files or folders specified")
            
        valid_source_paths = [p for p in source_paths if p.exists()]
        if not valid_source_paths:
            raise ValueError("No valid source files or folders found")
            
        # Validate target paths
        if not target_paths:
            raise ValueError("No target files or folders specified")
            
        valid_target_paths = [p for p in target_paths if p.exists()]
        if not valid_target_paths:
            raise ValueError("No valid target files or folders found")
        
        # Create and return worker
        worker = VerificationWorker(valid_source_paths, valid_target_paths, algorithm)
        self.current_operation = worker
        
        logger.info(f"Starting verification operation with {algorithm} on {len(valid_source_paths)} source and {len(valid_target_paths)} target paths")
        return worker
        
    def cancel_current_operation(self):
        """Cancel the current operation if running"""
        if self.current_operation and self.current_operation.isRunning():
            logger.info("Cancelling current hash operation")
            self.current_operation.cancel()
            self.current_operation.wait(timeout=5000)  # Wait up to 5 seconds for cancellation
            
    def is_operation_running(self) -> bool:
        """Check if an operation is currently running"""
        return self.current_operation is not None and self.current_operation.isRunning()
        
    def get_current_operation(self) -> Optional[SingleHashWorker | VerificationWorker]:
        """Get the current operation worker"""
        return self.current_operation
        
    def cleanup_finished_operation(self):
        """Clean up finished operations"""
        if self.current_operation and not self.current_operation.isRunning():
            self.current_operation = None