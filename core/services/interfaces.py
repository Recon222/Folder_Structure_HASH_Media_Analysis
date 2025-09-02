#!/usr/bin/env python3
"""
Service interfaces for dependency injection and testing
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pathlib import Path

from ..models import FormData
from ..result_types import Result, FileOperationResult, ReportGenerationResult, ArchiveOperationResult
from .success_message_data import SuccessMessageData, QueueOperationData

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

class ISuccessMessageService(ABC):
    """Interface for success message building services"""
    
    @abstractmethod
    def build_forensic_success_message(
        self,
        file_result: FileOperationResult,
        report_results: Optional[Dict[str, ReportGenerationResult]] = None,
        zip_result: Optional[ArchiveOperationResult] = None
    ) -> SuccessMessageData:
        """Build forensic operation success message"""
        pass
    
    @abstractmethod
    def build_queue_save_success_message(
        self,
        queue_data: QueueOperationData
    ) -> SuccessMessageData:
        """Build queue save success message"""
        pass
    
    @abstractmethod
    def build_queue_load_success_message(
        self,
        queue_data: QueueOperationData
    ) -> SuccessMessageData:
        """Build queue load success message"""
        pass
    
    @abstractmethod
    def build_batch_success_message(
        self,
        batch_data: Any  # BatchOperationData when implemented
    ) -> SuccessMessageData:
        """Build batch operation success message"""
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