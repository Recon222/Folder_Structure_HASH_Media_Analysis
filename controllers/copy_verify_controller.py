#!/usr/bin/env python3
"""
Copy & Verify Controller - Orchestrates copy and verify operations
Follows SOA architecture with full service integration
"""

from pathlib import Path
from typing import List, Optional, Dict, Any

from .base_controller import BaseController
from core.services.interfaces import ICopyVerifyService, IValidationService
from core.workers.copy_verify_worker import CopyVerifyWorker
from core.result_types import Result
from core.exceptions import FileOperationError
from core.logger import logger


class CopyVerifyController(BaseController):
    """Controller for copy and verify operations"""
    
    def __init__(self):
        """Initialize copy verify controller"""
        super().__init__("CopyVerifyController")
        self.current_worker: Optional[CopyVerifyWorker] = None
        
        # Service dependencies (lazy loaded)
        self._copy_service = None
        self._validation_service = None
        
    @property
    def copy_service(self) -> ICopyVerifyService:
        """Lazy load copy verify service"""
        if self._copy_service is None:
            self._copy_service = self._get_service(ICopyVerifyService)
        return self._copy_service
    
    @property 
    def validation_service(self) -> IValidationService:
        """Lazy load validation service"""
        if self._validation_service is None:
            self._validation_service = self._get_service(IValidationService)
        return self._validation_service
    
    def execute_copy_operation(
        self,
        source_items: List[Path],
        destination: Path,
        preserve_structure: bool = True,
        calculate_hash: bool = True,
        csv_path: Optional[Path] = None
    ) -> Result[CopyVerifyWorker]:
        """
        Execute copy and verify operation
        
        This method orchestrates the entire copy workflow:
        1. Validates operation parameters
        2. Validates destination security
        3. Prepares file list
        4. Creates and returns worker thread
        
        Args:
            source_items: List of source files/folders to copy
            destination: Destination directory
            preserve_structure: Whether to preserve folder structure
            calculate_hash: Whether to calculate and verify hashes
            csv_path: Optional path for CSV report
            
        Returns:
            Result containing CopyVerifyWorker or error
        """
        try:
            self._log_operation("execute_copy_operation", 
                              f"sources: {len(source_items)}, dest: {destination}")
            
            # Step 1: Validate operation parameters
            validation_result = self.copy_service.validate_copy_operation(
                source_items, destination
            )
            if not validation_result.success:
                return Result.error(validation_result.error)
            
            # Step 2: Validate destination security
            security_result = self.copy_service.validate_destination_security(
                destination, source_items
            )
            if not security_result.success:
                return Result.error(security_result.error)
            
            # Step 3: Ensure destination exists
            try:
                destination.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                error = FileOperationError(
                    f"Failed to create destination directory: {e}",
                    user_message=f"Cannot create destination folder: {e}"
                )
                self._handle_error(error, {'method': 'execute_copy_operation'})
                return Result.error(error)
            
            # Step 4: Create worker thread with validated parameters
            worker = CopyVerifyWorker(
                source_items=source_items,
                destination=destination,
                preserve_structure=preserve_structure,
                calculate_hash=calculate_hash,
                csv_path=csv_path,
                service=self.copy_service  # Pass service for result processing
            )
            
            self.current_worker = worker
            self._log_operation("worker_created", 
                              f"Worker created for {len(source_items)} items")
            
            return Result.success(worker)
            
        except Exception as e:
            error = FileOperationError(
                f"Copy operation setup failed: {e}",
                user_message="Failed to start copy operation. Please check your inputs."
            )
            self._handle_error(error, {'method': 'execute_copy_operation'})
            return Result.error(error)
    
    def process_operation_results(
        self,
        results: Any,
        calculate_hash: bool = True
    ) -> Result:
        """
        Process operation results through service
        
        Args:
            results: Operation results from worker (can be Result object or dict)
            calculate_hash: Whether hashes were calculated
            
        Returns:
            Result containing SuccessMessageData
        """
        try:
            # Extract the actual results and performance stats
            actual_results = results
            performance_stats = None
            
            # Handle Result object
            if hasattr(results, 'value'):
                actual_results = results.value
                # For FileOperationResult, extract performance directly from attributes
                if hasattr(results, 'duration_seconds'):
                    performance_stats = {
                        'total_time': results.duration_seconds,
                        'average_speed_mbps': results.average_speed_mbps,
                        'peak_speed_mbps': results.average_speed_mbps * 1.2  # Estimate
                    }
                    logger.debug(f"[CopyVerifyController] Extracted performance from FileOperationResult: {performance_stats}")
                elif hasattr(results, 'metadata'):
                    performance_stats = results.metadata
            
            # Handle dict with metadata
            elif isinstance(results, dict):
                if 'value' in results:
                    actual_results = results['value']
                    performance_stats = results.get('metadata', {})
                else:
                    actual_results = results
            
            return self.copy_service.process_operation_results(
                actual_results, 
                calculate_hash,
                performance_stats
            )
        except Exception as e:
            error = FileOperationError(
                f"Failed to process results: {e}",
                user_message="Failed to process operation results."
            )
            self._handle_error(error, {'method': 'process_operation_results'})
            return Result.error(error)
    
    def export_results_to_csv(
        self,
        results: Dict[str, Any],
        csv_path: Path
    ) -> Result:
        """
        Export operation results to CSV
        
        Args:
            results: Operation results to export
            csv_path: Path for CSV file
            
        Returns:
            Result containing path to CSV file
        """
        try:
            return self.copy_service.export_results_to_csv(results, csv_path)
        except Exception as e:
            error = FileOperationError(
                f"CSV export failed: {e}",
                user_message="Failed to export results to CSV."
            )
            self._handle_error(error, {'method': 'export_results_to_csv'})
            return Result.error(error)
    
    def cancel_operation(self) -> Result[None]:
        """
        Cancel current operation if running
        
        Returns:
            Result.success(None) if cancelled or no operation running
        """
        try:
            if self.current_worker and self.current_worker.isRunning():
                self.current_worker.cancel()
                self._log_operation("cancel_operation", "Operation cancelled")
            return Result.success(None)
        except Exception as e:
            error = FileOperationError(
                f"Failed to cancel operation: {e}",
                user_message="Failed to cancel the operation."
            )
            self._handle_error(error, {'method': 'cancel_operation'})
            return Result.error(error)
    
    def pause_operation(self) -> Result[None]:
        """
        Pause current operation
        
        Returns:
            Result.success(None) if paused
        """
        try:
            if self.current_worker and self.current_worker.isRunning():
                self.current_worker.pause()
                self._log_operation("pause_operation", "Operation paused")
            return Result.success(None)
        except Exception as e:
            error = FileOperationError(
                f"Failed to pause operation: {e}",
                user_message="Failed to pause the operation."
            )
            self._handle_error(error, {'method': 'pause_operation'})
            return Result.error(error)
    
    def resume_operation(self) -> Result[None]:
        """
        Resume paused operation
        
        Returns:
            Result.success(None) if resumed
        """
        try:
            if self.current_worker and self.current_worker.isRunning():
                self.current_worker.resume()
                self._log_operation("resume_operation", "Operation resumed")
            return Result.success(None)
        except Exception as e:
            error = FileOperationError(
                f"Failed to resume operation: {e}",
                user_message="Failed to resume the operation."
            )
            self._handle_error(error, {'method': 'resume_operation'})
            return Result.error(error)