#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hash controller - coordinates hash operations between UI and workers
Enhanced with service integration, enterprise error handling, and resource coordination
"""

from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from .base_controller import BaseController
from core.workers.hash_worker import SingleHashWorker, VerificationWorker
from core.services.interfaces import IValidationService
from core.settings_manager import settings
from core.exceptions import ValidationError, FileOperationError, ErrorSeverity
from core.result_types import Result
from core.resource_coordinators import WorkerResourceCoordinator


class HashController(BaseController):
    """Coordinates all hash operations with enhanced error handling and resource coordination"""
    
    def __init__(self):
        super().__init__("HashController")
        self.current_operation: Optional[SingleHashWorker | VerificationWorker] = None
        self._current_operation_id: Optional[str] = None
        
        # Service dependencies (injected)
        self._validation_service = None
    
    def _create_resource_coordinator(self, component_id: str) -> WorkerResourceCoordinator:
        """Use WorkerResourceCoordinator for hash worker management"""
        return WorkerResourceCoordinator(component_id)
    
    @property
    def validation_service(self) -> IValidationService:
        """Lazy load validation service"""
        if self._validation_service is None:
            self._validation_service = self._get_service(IValidationService)
        return self._validation_service
        
    def start_single_hash_workflow(
        self,
        paths: List[Path],
        algorithm: str = None
    ) -> Result[SingleHashWorker]:
        """Start a single hash workflow with enhanced validation and error handling
        
        Args:
            paths: List of file/folder paths to hash
            algorithm: Hash algorithm to use (defaults to settings)
            
        Returns:
            Result containing SingleHashWorker or error
        """
        try:
            self._log_operation("start_single_hash_workflow", f"{len(paths)} paths")
            
            # Check if another operation is running
            if self.current_operation and self.current_operation.isRunning():
                error = FileOperationError(
                    "Another hash operation is already running",
                    user_message="Please wait for the current hash operation to complete."
                )
                self._handle_error(error, {'method': 'start_single_hash_workflow'})
                return Result.error(error)
            
            # Validate algorithm
            if algorithm is None:
                algorithm = settings.hash_algorithm
                
            if algorithm.lower() not in ['sha256', 'md5']:
                error = ValidationError(
                    {"algorithm": f"Unsupported algorithm: {algorithm}"},
                    user_message=f"Hash algorithm '{algorithm}' is not supported. Please use SHA256 or MD5."
                )
                self._handle_error(error, {'method': 'start_single_hash_workflow'})
                return Result.error(error)
            
            # Validate paths using service layer
            if not paths:
                error = ValidationError(
                    {"paths": "No files or folders specified"},
                    user_message="Please select files or folders to hash."
                )
                self._handle_error(error, {'method': 'start_single_hash_workflow'})
                return Result.error(error)
            
            # Use validation service for consistent path validation
            path_validation_result = self.validation_service.validate_file_paths(paths)
            if not path_validation_result.success:
                return Result.error(path_validation_result.error)
            
            valid_paths = path_validation_result.value
            
            # Create worker
            worker = SingleHashWorker(valid_paths, algorithm)
            self.current_operation = worker
            
            # Track worker with resource coordinator
            if self.resources:
                self._current_operation_id = self.resources.track_worker(
                    worker,
                    name=f"single_hash_{datetime.now():%H%M%S}"
                )
            
            self._log_operation("hash_worker_created", 
                              f"{algorithm} on {len(valid_paths)} paths")
            return Result.success(worker)
            
        except Exception as e:
            if isinstance(e, (ValidationError, FileOperationError)):
                self._handle_error(e, {'method': 'start_single_hash_workflow'})
                return Result.error(e)
            else:
                error = FileOperationError(
                    f"Failed to start hash workflow: {e}",
                    user_message="Failed to start hash operation."
                )
                self._handle_error(error, {'method': 'start_single_hash_workflow'})
                return Result.error(error)
    
    def start_single_hash_operation(
        self,
        paths: List[Path],
        algorithm: str = None
    ) -> SingleHashWorker:
        """Legacy method - calls new workflow method and extracts result
        
        DEPRECATED: Use start_single_hash_workflow() for better error handling
        """
        result = self.start_single_hash_workflow(paths, algorithm)
        if result.success:
            return result.value
        else:
            # Convert back to exception for backward compatibility
            if isinstance(result.error, ValidationError):
                raise ValueError(result.error.user_message)
            else:
                raise RuntimeError(result.error.user_message)
        
    def start_verification_workflow(
        self,
        source_paths: List[Path],
        target_paths: List[Path],
        algorithm: str = None
    ) -> Result[VerificationWorker]:
        """Start a verification workflow with enhanced validation and error handling
        
        Args:
            source_paths: Source file/folder paths to hash
            target_paths: Target file/folder paths to compare against
            algorithm: Hash algorithm to use (defaults to settings)
            
        Returns:
            Result containing VerificationWorker or error
        """
        try:
            self._log_operation("start_verification_workflow", 
                              f"sources: {len(source_paths)}, targets: {len(target_paths)}")
            
            # Check if another operation is running
            if self.current_operation and self.current_operation.isRunning():
                error = FileOperationError(
                    "Another hash operation is already running",
                    user_message="Please wait for the current hash operation to complete."
                )
                self._handle_error(error, {'method': 'start_verification_workflow'})
                return Result.error(error)
            
            # Validate algorithm (reuse validation logic)
            if algorithm is None:
                algorithm = settings.hash_algorithm
                
            if algorithm.lower() not in ['sha256', 'md5']:
                error = ValidationError(
                    {"algorithm": f"Unsupported algorithm: {algorithm}"},
                    user_message=f"Hash algorithm '{algorithm}' is not supported. Please use SHA256 or MD5."
                )
                self._handle_error(error, {'method': 'start_verification_workflow'})
                return Result.error(error)
            
            # Validate source paths
            if not source_paths:
                error = ValidationError(
                    {"source_paths": "No source files or folders specified"},
                    user_message="Please select source files or folders for verification."
                )
                self._handle_error(error, {'method': 'start_verification_workflow'})
                return Result.error(error)
            
            source_validation_result = self.validation_service.validate_file_paths(source_paths)
            if not source_validation_result.success:
                return Result.error(source_validation_result.error)
            
            valid_source_paths = source_validation_result.value
            
            # Validate target paths
            if not target_paths:
                error = ValidationError(
                    {"target_paths": "No target files or folders specified"},
                    user_message="Please select target files or folders for verification."
                )
                self._handle_error(error, {'method': 'start_verification_workflow'})
                return Result.error(error)
            
            target_validation_result = self.validation_service.validate_file_paths(target_paths)
            if not target_validation_result.success:
                return Result.error(target_validation_result.error)
            
            valid_target_paths = target_validation_result.value
            
            # Create worker
            worker = VerificationWorker(valid_source_paths, valid_target_paths, algorithm)
            self.current_operation = worker
            
            # Track worker with resource coordinator
            if self.resources:
                self._current_operation_id = self.resources.track_worker(
                    worker,
                    name=f"verification_{datetime.now():%H%M%S}"
                )
            
            self._log_operation("verification_worker_created", 
                              f"{algorithm} verification: {len(valid_source_paths)} sources, {len(valid_target_paths)} targets")
            return Result.success(worker)
            
        except Exception as e:
            if isinstance(e, (ValidationError, FileOperationError)):
                self._handle_error(e, {'method': 'start_verification_workflow'})
                return Result.error(e)
            else:
                error = FileOperationError(
                    f"Failed to start verification workflow: {e}",
                    user_message="Failed to start verification operation."
                )
                self._handle_error(error, {'method': 'start_verification_workflow'})
                return Result.error(error)
    
    def start_verification_operation(
        self,
        source_paths: List[Path],
        target_paths: List[Path],
        algorithm: str = None
    ) -> VerificationWorker:
        """Legacy method - calls new workflow method and extracts result
        
        DEPRECATED: Use start_verification_workflow() for better error handling
        """
        result = self.start_verification_workflow(source_paths, target_paths, algorithm)
        if result.success:
            return result.value
        else:
            # Convert back to exception for backward compatibility
            if isinstance(result.error, ValidationError):
                raise ValueError(result.error.user_message)
            else:
                raise RuntimeError(result.error.user_message)
        
    def cancel_current_operation(self):
        """Cancel the current operation with proper cleanup and logging"""
        if self.current_operation and self.current_operation.isRunning():
            self._log_operation("cancel_hash_operation", 
                              f"{self.current_operation.__class__.__name__}")
            self.current_operation.cancel()
            self.current_operation.wait(timeout=5000)  # Wait up to 5 seconds for cancellation
            self._log_operation("hash_operation_cancelled")
        else:
            self._log_operation("no_operation_to_cancel", level="debug")
        
        # Clear references - coordinator handles cleanup
        self.current_operation = None
        self._current_operation_id = None
            
    def is_operation_running(self) -> bool:
        """Check if an operation is currently running"""
        running = self.current_operation is not None and self.current_operation.isRunning()
        if running:
            self._log_operation("operation_status_check", 
                              f"{self.current_operation.__class__.__name__} running", "debug")
        return running
        
    def get_current_operation(self) -> Optional[SingleHashWorker | VerificationWorker]:
        """Get the current operation worker"""
        return self.current_operation
        
    def get_current_operation_status(self) -> Dict[str, Any]:
        """Get detailed status of current operation"""
        if not self.current_operation:
            return {"status": "idle", "operation": None, "can_cancel": False}
        
        return {
            "status": "running" if self.current_operation.isRunning() else "completed",
            "operation": self.current_operation.__class__.__name__,
            "can_cancel": self.current_operation.isRunning()
        }
        
    def cleanup_finished_operation(self):
        """Clean up finished operations with logging"""
        if self.current_operation and not self.current_operation.isRunning():
            operation_name = self.current_operation.__class__.__name__
            self.current_operation = None
            self._current_operation_id = None
            self._log_operation("operation_cleaned_up", operation_name)
    
    def cleanup(self) -> None:
        """Clean up all resources"""
        # Cancel any running operation
        if self.current_operation and self.current_operation.isRunning():
            self.cancel_current_operation()
        
        # Let resource coordinator handle cleanup
        if self.resources:
            self.resources.cleanup_all()
        
        # Clear references
        self.current_operation = None
        self._current_operation_id = None