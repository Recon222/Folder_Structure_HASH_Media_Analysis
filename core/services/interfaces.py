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

class IPathService(ABC):
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

class IFileOperationService(ABC):
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