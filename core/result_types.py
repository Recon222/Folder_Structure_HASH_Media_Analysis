#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Result objects system for Folder Structure Application

This module provides rich result objects that replace boolean returns throughout
the application, providing type safety and comprehensive error context.
"""

from typing import TypeVar, Generic, Optional, List, Dict, Any, Union
from dataclasses import dataclass, field
from pathlib import Path

from .exceptions import FSAError

# Type variable for generic result values
T = TypeVar('T')


@dataclass
class Result(Generic[T]):
    """
    Universal result object that replaces boolean returns
    
    Provides type-safe error handling with rich context information
    and support for warnings and metadata.
    """
    success: bool
    value: Optional[T] = None
    error: Optional[FSAError] = None
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def success(cls, value: T, warnings: Optional[List[str]] = None, **metadata) -> 'Result[T]':
        """
        Create a successful result
        
        Args:
            value: The successful result value
            warnings: Optional list of warnings
            **metadata: Additional metadata to store
            
        Returns:
            Result object indicating success
        """
        return cls(
            success=True, 
            value=value, 
            warnings=warnings or [], 
            metadata=metadata
        )
    
    @classmethod
    def error(cls, error: FSAError, warnings: Optional[List[str]] = None) -> 'Result[T]':
        """
        Create an error result
        
        Args:
            error: The error that occurred
            warnings: Optional list of warnings that occurred before the error
            
        Returns:
            Result object indicating failure
        """
        return cls(
            success=False, 
            error=error, 
            warnings=warnings or []
        )
    
    @classmethod
    def from_bool(cls, success: bool, value: Optional[T] = None, 
                  error_message: str = "Operation failed") -> 'Result[T]':
        """
        Convert boolean result to Result object (for migration)
        
        Args:
            success: Whether operation succeeded
            value: Value if successful
            error_message: Error message if failed
            
        Returns:
            Result object
        """
        if success:
            return cls.success(value)
        else:
            from .exceptions import FSAError
            error = FSAError(error_message)
            return cls.error(error)
    
    def unwrap(self) -> T:
        """
        Get value or raise error
        
        Returns:
            The result value if successful
            
        Raises:
            FSAError: If the result indicates failure
        """
        if not self.success:
            raise self.error
        return self.value
    
    def unwrap_or(self, default: T) -> T:
        """
        Get value or return default
        
        Args:
            default: Default value to return if failed
            
        Returns:
            The result value if successful, otherwise the default
        """
        return self.value if self.success else default
    
    def unwrap_or_else(self, func) -> T:
        """
        Get value or compute default from function
        
        Args:
            func: Function to call if failed, receives the error
            
        Returns:
            The result value if successful, otherwise result of func(error)
        """
        return self.value if self.success else func(self.error)
    
    def map(self, func) -> 'Result':
        """
        Transform the value if successful
        
        Args:
            func: Function to apply to the value
            
        Returns:
            New Result with transformed value, or original error
        """
        if self.success:
            try:
                new_value = func(self.value)
                return Result.success(new_value, self.warnings, **self.metadata)
            except Exception as e:
                from .exceptions import FSAError
                if isinstance(e, FSAError):
                    return Result.error(e, self.warnings)
                else:
                    error = FSAError(f"Mapping function failed: {e}")
                    return Result.error(error, self.warnings)
        else:
            return self
    
    def and_then(self, func) -> 'Result':
        """
        Chain operations that return Results
        
        Args:
            func: Function that takes value and returns a Result
            
        Returns:
            New Result from the function, or original error
        """
        if self.success:
            return func(self.value)
        else:
            return self
    
    def has_warnings(self) -> bool:
        """Check if result has warnings"""
        return len(self.warnings) > 0
    
    def add_warning(self, warning: str) -> 'Result[T]':
        """Add a warning to this result"""
        self.warnings.append(warning)
        return self
    
    def add_metadata(self, key: str, value: Any) -> 'Result[T]':
        """Add metadata to this result"""
        self.metadata[key] = value
        return self


# Specialized result types for common operations

@dataclass 
class FileOperationResult(Result[Dict[str, Any]]):
    """
    File operation results with performance and processing data
    
    Used for file copying, moving, and hash calculation operations.
    """
    files_processed: int = 0
    bytes_processed: int = 0
    duration_seconds: float = 0.0
    average_speed_mbps: float = 0.0
    performance_metrics: Optional['PerformanceMetrics'] = None
    
    @classmethod
    def create(cls, results_dict: Dict[str, Any], files_processed: int = 0, 
               bytes_processed: int = 0, **kwargs) -> 'FileOperationResult':
        """
        Create FileOperationResult from operation results
        
        Args:
            results_dict: Raw results from file operations
            files_processed: Number of files processed
            bytes_processed: Total bytes processed
            **kwargs: Additional arguments
            
        Returns:
            FileOperationResult instance
        """
        # Extract performance stats if available
        performance_stats = results_dict.get('_performance_stats', {})
        
        return cls(
            success=True,
            value=results_dict,
            files_processed=files_processed,
            bytes_processed=bytes_processed,
            duration_seconds=performance_stats.get('total_time', 0.0),
            average_speed_mbps=performance_stats.get('average_speed_mbps', 0.0),
            performance_metrics=performance_stats.get('metrics'),
            **kwargs
        )


@dataclass
class ValidationResult(Result[None]):
    """
    Validation results with field-specific errors
    
    Used for form validation and data integrity checks.
    """
    field_errors: Dict[str, str] = field(default_factory=dict)
    
    @property
    def has_errors(self) -> bool:
        """Check if validation has errors"""
        return bool(self.field_errors) or not self.success
    
    @classmethod
    def create_valid(cls, warnings: Optional[List[str]] = None) -> 'ValidationResult':
        """Create a valid validation result"""
        return cls(success=True, warnings=warnings or [])
    
    @classmethod  
    def create_invalid(cls, field_errors: Dict[str, str], 
                      warnings: Optional[List[str]] = None) -> 'ValidationResult':
        """Create an invalid validation result"""
        from .exceptions import ValidationError
        error = ValidationError(field_errors)
        return cls(
            success=False,
            error=error,
            field_errors=field_errors,
            warnings=warnings or []
        )
    
    def add_field_error(self, field: str, message: str) -> 'ValidationResult':
        """Add a field-specific error"""
        self.field_errors[field] = message
        if self.success:
            # Convert to error result
            from .exceptions import ValidationError
            self.error = ValidationError(self.field_errors)
            self.success = False
        return self


@dataclass
class BatchOperationResult(Result[List[Dict[str, Any]]]):
    """
    Batch operation results with success/failure tracking
    
    Used for batch processing operations that handle multiple items.
    """
    total_items: int = 0
    successful_items: int = 0
    failed_items: int = 0
    item_results: List[Dict[str, Any]] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage"""
        if self.total_items == 0:
            return 100.0
        return (self.successful_items / self.total_items) * 100
    
    @classmethod
    def create(cls, item_results: List[Dict[str, Any]], **kwargs) -> 'BatchOperationResult':
        """
        Create BatchOperationResult from individual item results
        
        Args:
            item_results: List of results for individual items
            **kwargs: Additional arguments
            
        Returns:
            BatchOperationResult instance
        """
        total = len(item_results)
        successful = sum(1 for result in item_results if result.get('success', False))
        failed = total - successful
        
        # Determine overall success (could be configurable threshold)
        overall_success = failed == 0
        
        return cls(
            success=overall_success,
            value=item_results,
            total_items=total,
            successful_items=successful,
            failed_items=failed,
            item_results=item_results,
            **kwargs
        )


@dataclass
class ReportGenerationResult(Result[Path]):
    """
    Report generation results with output information
    
    Used for PDF generation and other report creation operations.
    """
    output_path: Optional[Path] = None
    report_type: Optional[str] = None
    page_count: int = 0
    file_size_bytes: int = 0
    
    @classmethod
    def create_successful(cls, output_path: Path, report_type: str = None, 
                         **kwargs) -> 'ReportGenerationResult':
        """Create successful report generation result"""
        file_size = 0
        try:
            if output_path.exists():
                file_size = output_path.stat().st_size
        except:
            pass  # File size is optional information
        
        return cls(
            success=True,
            value=output_path,
            output_path=output_path,
            report_type=report_type,
            file_size_bytes=file_size,
            **kwargs
        )


@dataclass
class HashOperationResult(Result[Dict[str, Dict[str, Any]]]):
    """
    Hash operation results with verification information
    
    Used for hash calculation and verification operations.
    """
    files_hashed: int = 0
    verification_failures: int = 0
    hash_algorithm: str = "SHA-256"
    processing_time: float = 0.0
    
    @classmethod
    def create(cls, hash_results: Dict[str, Dict[str, Any]], 
               hash_algorithm: str = "SHA-256", **kwargs) -> 'HashOperationResult':
        """Create hash operation result from raw results"""
        files_hashed = len(hash_results)
        verification_failures = sum(
            1 for result in hash_results.values() 
            if isinstance(result, dict) and not result.get('verified', True)
        )
        
        overall_success = verification_failures == 0
        
        return cls(
            success=overall_success,
            value=hash_results,
            files_hashed=files_hashed,
            verification_failures=verification_failures,
            hash_algorithm=hash_algorithm,
            **kwargs
        )


# Utility functions for common result operations

def combine_results(results: List[Result[T]]) -> Result[List[T]]:
    """
    Combine multiple results into a single result
    
    Args:
        results: List of Result objects to combine
        
    Returns:
        Result containing list of successful values, or first error encountered
    """
    successful_values = []
    all_warnings = []
    
    for result in results:
        if result.success:
            successful_values.append(result.value)
        else:
            # Return first error encountered
            return Result.error(result.error, all_warnings + result.warnings)
        
        all_warnings.extend(result.warnings)
    
    return Result.success(successful_values, all_warnings)


def first_success(results: List[Result[T]]) -> Result[T]:
    """
    Return the first successful result, or the last error if all fail
    
    Args:
        results: List of Result objects to try
        
    Returns:
        First successful result, or last error if all fail
    """
    last_error = None
    all_warnings = []
    
    for result in results:
        if result.success:
            return result
        else:
            last_error = result
            all_warnings.extend(result.warnings)
    
    if last_error:
        last_error.warnings.extend(all_warnings)
        return last_error
    else:
        from .exceptions import FSAError
        error = FSAError("No results provided")
        return Result.error(error)