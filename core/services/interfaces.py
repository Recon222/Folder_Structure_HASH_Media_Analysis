#!/usr/bin/env python3
"""
Service interfaces for dependency injection and testing
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Callable, ContextManager
from pathlib import Path
from enum import Enum

from ..models import FormData
from ..result_types import Result, FileOperationResult, ReportGenerationResult, ArchiveOperationResult
from .success_message_data import SuccessMessageData, QueueOperationData


class ResourceType(Enum):
    """Types of resources that can be tracked"""
    MEMORY = "memory"
    FILE_HANDLE = "file_handle"
    THREAD = "thread"
    QOBJECT = "qobject"
    THUMBNAIL = "thumbnail"
    MAP = "map"
    WORKER = "worker"
    CUSTOM = "custom"


class ComponentState(Enum):
    """Lifecycle states for components"""
    LOADED = "loaded"
    INITIALIZED = "initialized"
    ACTIVE = "active"
    PAUSED = "paused"
    CLEANING = "cleaning"
    DESTROYED = "destroyed"

class IService(ABC):
    """Base interface for all services"""
    pass

class IPathService(IService):
    """Interface for path building and validation services"""
    
    @abstractmethod
    def build_forensic_path(self, form_data: FormData, base_path: Path) -> Result[Path]:
        """Build forensic folder structure path"""
        pass
    
    @abstractmethod
    def validate_output_path(self, path: Path, base: Path) -> Result[Path]:
        """Validate output path security"""
        pass
    
    @abstractmethod
    def sanitize_path_component(self, component: str) -> str:
        """Sanitize individual path component"""
        pass
    
    @abstractmethod
    def get_available_templates(self) -> List[Dict[str, str]]:
        """Get list of available templates"""
        pass
    
    @abstractmethod
    def set_current_template(self, template_id: str) -> Result[None]:
        """Set active template"""
        pass
    
    @abstractmethod
    def get_current_template_id(self) -> str:
        """Get current template ID"""
        pass
    
    @abstractmethod
    def reload_templates(self) -> Result[None]:
        """Reload templates from storage"""
        pass
    
    @abstractmethod
    def build_archive_name(self, form_data: FormData) -> Result[str]:
        """Build archive name using current template"""
        pass
    
    @abstractmethod
    def import_template(self, file_path: Path) -> Result[Dict[str, Any]]:
        """Import template from JSON file"""
        pass
        
    @abstractmethod
    def export_template(self, template_id: str, file_path: Path) -> Result[None]:
        """Export template to JSON file"""
        pass
        
    @abstractmethod
    def get_template_info(self, template_id: str) -> Result[Dict[str, Any]]:
        """Get detailed template information"""
        pass
        
    @abstractmethod
    def validate_template_file(self, file_path: Path) -> Result[List[Dict[str, Any]]]:
        """Validate template file and return validation issues"""
        pass
    
    @abstractmethod
    def delete_user_template(self, template_id: str) -> Result[None]:
        """Delete user-imported template"""
        pass
    
    @abstractmethod
    def get_template_sources(self) -> List[Dict[str, str]]:
        """Get available templates grouped by source"""
        pass


class ICopyVerifyService(IService):
    """Interface for copy and verify operations service"""
    
    @abstractmethod
    def validate_copy_operation(
        self, 
        source_items: List[Path], 
        destination: Path
    ) -> Result[None]:
        """Validate copy operation parameters"""
        pass
    
    @abstractmethod
    def validate_destination_security(
        self,
        destination: Path,
        source_items: List[Path]
    ) -> Result[None]:
        """Validate destination path security and prevent path traversal"""
        pass
    
    @abstractmethod
    def prepare_copy_operation(
        self,
        source_items: List[Path],
        destination: Path,
        preserve_structure: bool
    ) -> Result[List[tuple]]:
        """Prepare file list for copy operation"""
        pass
    
    @abstractmethod
    def process_operation_results(
        self,
        results: Dict[str, Any],
        calculate_hash: bool
    ) -> Result[SuccessMessageData]:
        """Process operation results and build success message data"""
        pass
    
    @abstractmethod
    def generate_csv_report(
        self,
        results: Dict[str, Any],
        csv_path: Path,
        calculate_hash: bool
    ) -> Result[Path]:
        """Generate CSV report from operation results"""
        pass
    
    @abstractmethod
    def export_results_to_csv(
        self,
        results: Dict[str, Any],
        csv_path: Path
    ) -> Result[Path]:
        """Export existing results to CSV file"""
        pass

class IFileOperationService(IService):
    """Interface for file operation services"""
    
    @abstractmethod
    def copy_files(self, files: List[Path], destination: Path, 
                  calculate_hash: bool = True) -> FileOperationResult:
        """Copy files to destination"""
        pass
    
    @abstractmethod
    def copy_folders(self, folders: List[Path], destination: Path,
                    calculate_hash: bool = True) -> FileOperationResult:
        """Copy folders to destination"""
        pass

class IReportService(ABC):
    """Interface for report generation services"""
    
    @abstractmethod
    def generate_time_offset_report(self, form_data: FormData, 
                                   output_path: Path) -> ReportGenerationResult:
        """Generate time offset report"""
        pass
    
    @abstractmethod
    def generate_technician_log(self, form_data: FormData,
                               output_path: Path) -> ReportGenerationResult:
        """Generate technician log"""
        pass
    
    @abstractmethod
    def generate_hash_csv(self, file_results: Dict[str, Any],
                         output_path: Path) -> ReportGenerationResult:
        """Generate hash verification CSV"""
        pass

class IArchiveService(ABC):
    """Interface for archive creation services"""
    
    @abstractmethod
    def create_archives(self, source_path: Path, output_path: Path,
                       form_data: FormData = None) -> Result[List[Path]]:
        """Create ZIP archives"""
        pass
    
    @abstractmethod
    def should_create_archives(self) -> bool:
        """Check if archives should be created"""
        pass

class IValidationService(ABC):
    """Interface for validation services"""
    
    @abstractmethod
    def validate_form_data(self, form_data: FormData) -> Result[None]:
        """Validate form data"""
        pass
    
    @abstractmethod
    def validate_file_paths(self, paths: List[Path]) -> Result[List[Path]]:
        """Validate file paths"""
        pass


class IMediaAnalysisService(IService):
    """Interface for media analysis operations"""
    
    @abstractmethod
    def validate_media_files(self, paths: List[Path]) -> Result[List[Path]]:
        """
        Validate and filter media files from provided paths
        
        Args:
            paths: List of file/folder paths to validate
            
        Returns:
            Result containing list of valid file paths or error
        """
        pass
    
    @abstractmethod
    def analyze_media_files(
        self, 
        files: List[Path],
        settings: Any,  # MediaAnalysisSettings
        progress_callback: Optional[callable] = None
    ) -> Result[Any]:  # Result[MediaAnalysisResult]
        """
        Analyze media files and extract metadata
        
        Args:
            files: List of media file paths to analyze
            settings: Analysis settings and field preferences
            progress_callback: Optional callback for progress updates
            
        Returns:
            Result containing MediaAnalysisResult or error
        """
        pass
    
    @abstractmethod
    def generate_analysis_report(
        self,
        results: Any,  # MediaAnalysisResult
        output_path: Path,
        form_data: Optional[FormData] = None
    ) -> Result[Path]:
        """
        Generate PDF report from analysis results
        
        Args:
            results: Media analysis results to report
            output_path: Path where report should be saved
            form_data: Optional form data for case information
            
        Returns:
            Result containing report path or error
        """
        pass
    
    @abstractmethod
    def export_to_csv(
        self,
        results: Any,  # MediaAnalysisResult
        output_path: Path
    ) -> Result[Path]:
        """
        Export analysis results to CSV format
        
        Args:
            results: Media analysis results to export
            output_path: Path where CSV should be saved
            
        Returns:
            Result containing CSV path or error
        """
        pass
    
    @abstractmethod
    def get_ffprobe_status(self) -> Dict[str, Any]:
        """
        Get FFprobe availability and version status
        
        Returns:
            Dictionary with ffprobe status information
        """
        pass
    
    @abstractmethod
    def analyze_with_exiftool(
        self,
        files: List[Path],
        settings: Any,  # ExifToolSettings
        progress_callback: Optional[callable] = None
    ) -> Result[Any]:  # Result[ExifToolAnalysisResult]
        """
        Analyze files with ExifTool for forensic metadata extraction
        
        Args:
            files: List of files to analyze
            settings: ExifTool extraction settings
            progress_callback: Optional callback for progress updates
            
        Returns:
            Result containing ExifToolAnalysisResult or error
        """
        pass
    
    @abstractmethod
    def get_exiftool_status(self) -> Dict[str, Any]:
        """
        Get ExifTool availability and version status
        
        Returns:
            Dictionary with exiftool status information
        """
        pass
    
    @abstractmethod
    def generate_exiftool_report(
        self,
        results: Any,  # ExifToolAnalysisResult
        output_path: Path,
        form_data: Optional[FormData] = None
    ) -> Result[Path]:
        """
        Generate PDF report from ExifTool analysis results
        
        Args:
            results: ExifTool analysis results
            output_path: Path where report should be saved
            form_data: Optional form data for case information
            
        Returns:
            Result containing report path or error
        """
        pass
    
    @abstractmethod
    def export_exiftool_to_csv(
        self,
        results: Any,  # ExifToolAnalysisResult
        output_path: Path
    ) -> Result[Path]:
        """
        Export ExifTool results to CSV format
        
        Args:
            results: ExifTool analysis results
            output_path: Path where CSV should be saved
            
        Returns:
            Result containing CSV path or error
        """
        pass
    
    @abstractmethod
    def export_to_kml(
        self,
        results: Any,  # ExifToolAnalysisResult
        output_path: Path
    ) -> Result[Path]:
        """
        Export GPS locations to KML format for Google Earth
        
        Args:
            results: ExifTool analysis results with GPS data
            output_path: Path where KML should be saved
            
        Returns:
            Result containing KML path or error
        """
        pass


class IResourceManagementService(IService):
    """Interface for centralized resource management in plugin architecture"""
    
    @abstractmethod
    def register_component(self, component: Any, component_id: str, 
                         component_type: str = "plugin") -> None:
        """
        Register a component for resource tracking
        
        Args:
            component: The component instance to register
            component_id: Unique identifier for the component
            component_type: Type of component (plugin, tab, service, etc.)
        """
        pass
    
    @abstractmethod
    def unregister_component(self, component: Any) -> None:
        """
        Unregister a component and cleanup all its resources
        
        Args:
            component: The component to unregister
        """
        pass
    
    @abstractmethod
    def track_resource(self, component: Any, resource_type: ResourceType,
                      resource: Any, size_bytes: Optional[int] = None,
                      metadata: Optional[Dict] = None) -> str:
        """
        Track a resource with optional size and metadata
        
        Args:
            component: Component that owns the resource
            resource_type: Type of resource being tracked
            resource: The actual resource object
            size_bytes: Optional size in bytes for memory tracking
            metadata: Optional metadata about the resource
            
        Returns:
            Unique resource ID for later release
        """
        pass
    
    @abstractmethod
    def release_resource(self, component: Any, resource_id: str) -> bool:
        """
        Release a specific tracked resource
        
        Args:
            component: Component that owns the resource
            resource_id: ID of resource to release
            
        Returns:
            True if resource was released, False if not found
        """
        pass
    
    @abstractmethod
    def register_cleanup(self, component: Any, callback: Callable,
                        priority: int = 0) -> None:
        """
        Register a cleanup callback for component
        
        Args:
            component: Component to register callback for
            callback: Function to call during cleanup
            priority: Higher priority callbacks run first
        """
        pass
    
    @abstractmethod
    def managed_resource(self, component: Any, 
                        resource_type: ResourceType) -> ContextManager:
        """
        Context manager for automatic resource cleanup
        
        Args:
            component: Component that will own the resource
            resource_type: Type of resource being managed
            
        Returns:
            Context manager that handles resource lifecycle
        """
        pass
    
    @abstractmethod
    def cleanup_component(self, component: Any, force: bool = False) -> None:
        """
        Clean up all resources for a component
        
        Args:
            component: Component to clean up
            force: If True, force cleanup even on errors
        """
        pass
    
    @abstractmethod
    def get_memory_usage(self) -> Dict[str, int]:
        """
        Get memory usage by component
        
        Returns:
            Dictionary mapping component_id to bytes used
        """
        pass
    
    @abstractmethod
    def get_resource_count(self, component: Any = None) -> Dict[str, int]:
        """
        Get resource count by type
        
        Args:
            component: Optional component to filter by
            
        Returns:
            Dictionary mapping resource type to count
        """
        pass
    
    @abstractmethod
    def set_component_state(self, component: Any, state: ComponentState) -> None:
        """
        Update component lifecycle state
        
        Args:
            component: Component to update
            state: New state
        """
        pass
    
    @abstractmethod
    def get_component_state(self, component: Any) -> Optional[ComponentState]:
        """
        Get current component state
        
        Args:
            component: Component to check
            
        Returns:
            Current state or None if not registered
        """
        pass
    
    @abstractmethod
    def set_memory_limit(self, component_id: str, limit_bytes: int) -> None:
        """
        Set memory limit for a component
        
        Args:
            component_id: Component identifier
            limit_bytes: Maximum memory in bytes
        """
        pass
    
    @abstractmethod
    def set_global_memory_limit(self, limit_bytes: int) -> None:
        """
        Set global memory limit for all components
        
        Args:
            limit_bytes: Maximum total memory in bytes
        """
        pass
    
    @abstractmethod
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get resource management statistics
        
        Returns:
            Dictionary with statistics about resource usage
        """
        pass