#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main application window - coordinator only
"""

from datetime import datetime
from pathlib import Path
from typing import List
import json

from PySide6.QtCore import Qt, QDateTime, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QVBoxLayout, QWidget,
    QProgressBar, QStatusBar, QFileDialog,
    QSplitter, QHBoxLayout, QDialog, QDialogButtonBox,
    QGroupBox, QComboBox, QCheckBox, QPushButton, QLabel,
    QSizePolicy
)

from controllers import WorkflowController, ReportController, HashController
from controllers.zip_controller import ZipController
from core.models import FormData
from core.settings_manager import settings
from core.logger import logger
from core.workers import FolderStructureThread
from core.workers.zip_operations import ZipOperationThread
from ui.components import FormPanel, FilesPanel, LogConsole
from ui.components.error_notification_system import ErrorNotificationManager
from core.exceptions import UIError, ErrorSeverity
from core.error_handler import handle_error
from ui.styles import CarolinaBlueTheme
from ui.dialogs import ZipSettingsDialog, AboutDialog, UserSettingsDialog
from ui.dialogs.success_dialog import SuccessDialog
from ui.dialogs.zip_prompt import ZipPromptDialog
from ui.tabs import ForensicTab, HashingTab
from ui.tabs.batch_tab import BatchTab
from core.error_handler import get_error_handler
from core.exceptions import FSAError


class MainWindow(QMainWindow):
    """Main application window - coordinator only"""
    
    def __init__(self):
        super().__init__()
        
        # Initialize data
        self.form_data = FormData()
        self.settings = settings  # Use centralized settings manager
        self.file_operation_results = {}  # Store results for PDF generation
        self.output_directory = None
        self.last_output_directory = None
        
        # Configure services first (includes success message service integration)
        from core.services import configure_services
        
        # Initialize controllers
        self.zip_controller = ZipController(self.settings)
        
        # Configure services with dependencies
        configure_services(self.zip_controller)
        
        # Initialize new service-oriented controllers
        self.workflow_controller = WorkflowController()
        self.report_controller = ReportController(self.zip_controller)
        self.hash_controller = HashController()
        
        # Initialize error notification system
        self.error_notification_manager = None  # Will be created after UI setup
        self.error_handler = get_error_handler()
        
        # Set up UI
        self.setWindowTitle("Folder Structure Utility")
        self.resize(1200, 800)
        
        # CRITICAL FIX: Prevent content-based window resizing while allowing user resizing
        # Set minimum size but NO maximum to allow maximize button to work
        self.setMinimumSize(900, 600)  # Reasonable minimum for usability
        
        # Allow user resizing and maximize while preventing content-based expansion
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        self._setup_ui()
        self._apply_theme()
        self._load_settings()
        self._setup_error_notifications()
        
        # Current operation tracking
        self.current_copy_speed = 0.0
        self.operation_active = False
        
        # Show ready
        self.status_bar.showMessage("Ready")
        
    def _setup_ui(self):
        """Create the UI - all in one place, no complex bindings"""
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Create menu bar
        self._create_menu_bar()
        
        # Create tab widget
        self.tabs = QTabWidget()
        
        # Forensic Mode tab
        self.forensic_tab = self._create_forensic_tab()
        self.tabs.addTab(self.forensic_tab, "Forensic Mode")
        
        # Batch Processing tab
        self.batch_tab = BatchTab(self.form_data, self)
        self.batch_tab.log_message.connect(self.log)
        self.tabs.addTab(self.batch_tab, "Batch Processing")
        
        # Hashing tab with enhanced controller
        self.hashing_tab = HashingTab(self.hash_controller)
        self.hashing_tab.log_message.connect(self.log)
        self.tabs.addTab(self.hashing_tab, "Hashing")
        
        # Configure tab widget to prevent content-based expansion
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Add tabs to layout
        layout.addWidget(self.tabs)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Connect batch tab status messages
        self.batch_tab.status_message.connect(self.status_bar.showMessage)
        
        # Connect hashing tab status messages
        self.hashing_tab.status_message.connect(self.status_bar.showMessage)
        
    def _create_forensic_tab(self):
        """Create the forensic mode tab"""
        forensic_tab = ForensicTab(self.form_data)
        
        # Connect signals
        forensic_tab.process_requested.connect(self.process_forensic_files)
        forensic_tab.log_message.connect(self.log)
        forensic_tab.template_changed.connect(self._on_template_changed)
        
        # Store references we need
        self.form_panel = forensic_tab.form_panel
        self.files_panel = forensic_tab.files_panel
        self.log_console = forensic_tab.log_console
        self.process_btn = forensic_tab.process_btn
        
        return forensic_tab
        
    def _create_menu_bar(self):
        """Create the menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        load_action = QAction("Load JSON", self)
        load_action.triggered.connect(self.load_json)
        file_menu.addAction(load_action)
        
        save_action = QAction("Save JSON", self)
        save_action.triggered.connect(self.save_json)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Templates menu
        templates_menu = menubar.addMenu("Templates")
        
        import_template_action = QAction("Import Template...", self)
        import_template_action.setShortcut("Ctrl+Shift+I")
        import_template_action.triggered.connect(self._import_template)
        templates_menu.addAction(import_template_action)
        
        export_template_action = QAction("Export Current Template...", self)
        export_template_action.triggered.connect(self._export_current_template)
        templates_menu.addAction(export_template_action)
        
        templates_menu.addSeparator()
        
        manage_templates_action = QAction("Manage Templates...", self)
        manage_templates_action.setShortcut("Ctrl+Shift+M")
        manage_templates_action.triggered.connect(self._manage_templates)
        templates_menu.addAction(manage_templates_action)
        
        templates_menu.addSeparator()
        
        template_docs_action = QAction("Template Documentation", self)
        template_docs_action.triggered.connect(self._show_template_documentation)
        templates_menu.addAction(template_docs_action)

        # Settings menu
        settings_menu = menubar.addMenu("Settings")
        
        user_settings_action = QAction("User Settings", self)
        user_settings_action.triggered.connect(self.show_user_settings)
        settings_menu.addAction(user_settings_action)
        
        # Add Performance Monitor action
        performance_monitor_action = QAction("Performance Monitor", self)
        performance_monitor_action.triggered.connect(self.show_performance_monitor)
        settings_menu.addAction(performance_monitor_action)
        
        settings_menu.addSeparator()
        
        zip_settings_action = QAction("ZIP Settings", self)
        zip_settings_action.triggered.connect(self.show_zip_settings)
        settings_menu.addAction(zip_settings_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
        # Debug menu (for testing error notifications)
        debug_menu = menubar.addMenu("Debug")
        
        test_info_action = QAction("Test Info Notification", self)
        test_info_action.triggered.connect(lambda: self._test_error_notification('info'))
        debug_menu.addAction(test_info_action)
        
        test_warning_action = QAction("Test Warning Notification", self)
        test_warning_action.triggered.connect(lambda: self._test_error_notification('warning'))
        debug_menu.addAction(test_warning_action)
        
        test_error_action = QAction("Test Error Notification", self)
        test_error_action.triggered.connect(lambda: self._test_error_notification('error'))
        debug_menu.addAction(test_error_action)
        
        test_critical_action = QAction("Test Critical Notification", self)
        test_critical_action.triggered.connect(lambda: self._test_error_notification('critical'))
        debug_menu.addAction(test_critical_action)
        
    def _apply_theme(self):
        """Apply Carolina Blue theme"""
        self.setStyleSheet(CarolinaBlueTheme.get_stylesheet())
        
    def _load_settings(self):
        """Load saved settings"""
        # Settings are now loaded in User Settings dialog
        pass
            
    def process_forensic_files(self):
        """Process files using forensic folder structure"""
        # Validate form
        errors = self.form_data.validate()
        if errors:
            error = UIError(
                f"Form validation failed: {', '.join(errors)}", 
                user_message=f"Please correct the following errors:\n\n• " + "\n• ".join(errors),
                component="MainWindow"
            )
            handle_error(error, {'operation': 'form_validation', 'field_count': len(errors)})
            return
            
        # Get files
        files, folders = self.files_panel.get_all_items()
        
        if not files and not folders:
            error = UIError(
                "No files selected for processing",
                user_message="Please select files or folders to process before starting the operation.",
                component="MainWindow"
            )
            handle_error(error, {'operation': 'file_selection_validation'})
            return
            
        # Handle ZIP prompt BEFORE starting any operations
        if self.zip_controller.should_prompt_user():
            choice = ZipPromptDialog.prompt_user(self)
            self.zip_controller.set_session_choice(
                choice['create_zip'], 
                choice['remember_for_session']
            )
            
        # Ask user where to save the output
        output_dir = QFileDialog.getExistingDirectory(
            self, 
            "Select Output Location", 
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if not output_dir:
            return  # User cancelled
            
        # Store the output directory for later use
        self.output_directory = Path(output_dir)
        self.last_output_directory = self.output_directory
        
        # Get hash calculation preference
        calculate_hash = self.settings.calculate_hashes
        
        # Get performance monitor if it exists
        perf_monitor = getattr(self, 'performance_monitor', None) if hasattr(self, 'performance_monitor') else None
        
        # Start file operation using new WorkflowController
        workflow_result = self.workflow_controller.process_forensic_workflow(
            form_data=self.form_data,
            files=files,
            folders=folders,
            output_directory=self.output_directory,
            calculate_hash=calculate_hash,
            performance_monitor=perf_monitor
        )
        
        if not workflow_result.success:
            # Handle workflow setup error
            error = UIError(
                f"Workflow setup failed: {workflow_result.error.message}",
                user_message=workflow_result.error.user_message,
                component="MainWindow"
            )
            handle_error(error, {'operation': 'workflow_setup'})
            return
        
        # Extract thread from successful result
        self.file_thread = workflow_result.value
        
        # Connect signals
        self.file_thread.progress_update.connect(self.update_progress_with_status)
        self.file_thread.result_ready.connect(self.on_operation_finished)
        
        # Update forensic tab state - pass thread reference for control
        self.forensic_tab.set_processing_state(True, self.file_thread)
        
        # Disable UI and show progress
        self.process_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.operation_active = True
        
        self.file_thread.start()
        
    def update_progress(self, value):
        """Update progress bar"""
        self.progress_bar.setValue(value)
        
    def update_progress_with_status(self, percentage, message):
        """Update progress bar and log status"""
        self.progress_bar.setValue(percentage)
        if message:
            self.log(message)
        
    def on_operation_finished(self, result):
        """Handle operation completion using Result objects"""
        from core.result_types import Result, FileOperationResult
        
        self.progress_bar.setVisible(False)
        self.process_btn.setEnabled(True)
        self.operation_active = False
        self.current_copy_speed = 0.0
        
        # Reset forensic tab processing state
        self.forensic_tab.set_processing_state(False)
        
        # Stop performance monitor if it's running
        if hasattr(self, 'performance_monitor') and self.performance_monitor:
            if hasattr(self.performance_monitor, 'stop_monitoring'):
                self.performance_monitor.stop_monitoring()
        
        # Reset status label
        if hasattr(self, 'copy_speed_label'):
            self.copy_speed_label.setText("Ready")
            self.copy_speed_label.setStyleSheet("padding: 0 10px; font-weight: bold;")
        
        if result.success:
            # Store the Result object for later use in reports and success message
            self.file_operation_result = result
            # Store the value dict for report generation (contains individual file results)
            self.file_operation_results = result.value or {}
            
            # Build performance message using service
            completion_message = "Files copied successfully!"
            
            from core.services.service_registry import get_service
            from core.services.performance_formatter_service import IPerformanceFormatterService
            
            perf_service = get_service(IPerformanceFormatterService)
            
            # FileOperationResult always has files_processed attribute
            if result.files_processed > 0:
                # Build performance summary from the Result object
                summary = perf_service.build_performance_summary(result)
                completion_message += f"\n\n{summary}"
            
            self.file_operation_performance = completion_message
            
            self.log(completion_message)
            
            # Auto-generate reports based on user settings
            if self.settings.generate_time_offset_pdf or \
               self.settings.generate_upload_log_pdf or \
               self.settings.calculate_hashes:
                self.log("Generating documentation...")
                self.generate_reports()
            else:
                # No reports to generate, go directly to final completion
                if hasattr(self, 'zip_controller') and self.zip_controller:
                    try:
                        if self.zip_controller.should_create_zip():
                            # ZIP will handle final completion
                            # FileOperationResult always has dest_path attribute
                            file_dest_path = Path(self.file_operation_result.dest_path)
                            
                            original_output_dir = file_dest_path.parent
                            self.create_zip_archives(original_output_dir)
                        else:
                            # No ZIP creation, show final completion now
                            self.show_final_completion_message()
                    except (ValueError, AttributeError, KeyError) as e:
                        self.log(f"Warning: ZIP creation skipped - {e}")
                        self.show_final_completion_message()
                else:
                    # No ZIP controller, show final completion
                    self.show_final_completion_message()
        else:
            # Handle failure - FSAError objects always have user_message
            message = result.error.user_message if result.error else "Operation failed"
            
            error = UIError(
                f"Operation failed: {message}",
                user_message=f"The operation could not be completed:\n\n{message}",
                component="MainWindow"
            )
            handle_error(error, {'operation': 'forensic_file_processing', 'severity': 'critical'})
            self.log(f"Operation failed: {message}")
    
    def cleanup_operation_memory(self):
        """
        Delegate memory cleanup to WorkflowController
        
        This method simply delegates to the WorkflowController's
        cleanup_operation_resources method, which handles all the complex
        cleanup logic in the service layer.
        """
        # Collect references to clean up
        file_thread = getattr(self, 'file_thread', None)
        zip_thread = getattr(self, 'zip_thread', None)
        operation_results = getattr(self, 'file_operation_results', None)
        performance_data = getattr(self, 'file_operation_performance', None)
        
        # Use WorkflowController for cleanup
        if hasattr(self, 'workflow_controller') and self.workflow_controller:
            cleanup_result = self.workflow_controller.cleanup_operation_resources(
                file_thread=file_thread,
                zip_thread=zip_thread,
                operation_results=operation_results,
                performance_data=performance_data
            )
            
            if not cleanup_result.success:
                self.log(f"Note: Cleanup had minor issues: {cleanup_result.error.user_message}")
        
        # Clear UI-specific references
        if hasattr(self, 'file_operation_results'):
            self.file_operation_results = None
        if hasattr(self, 'file_operation_result'):
            self.file_operation_result = None
        if hasattr(self, 'file_operation_performance'):
            self.file_operation_performance = None
        if hasattr(self, 'file_thread'):
            self.file_thread = None
        if hasattr(self, 'zip_thread'):
            self.zip_thread = None
        
        self.log("Memory cleanup completed - optimized for next operation")
        
    def generate_reports(self):
        """Generate PDF reports and hash verification CSV based on user settings"""
        try:
            # Check if we have valid file operation result
            if not hasattr(self, 'file_operation_result') or not self.file_operation_result:
                self.log("Cannot generate reports - no file operation result available")
                self.show_final_completion_message()
                return
            
            # Use the new ReportController method that handles path determination
            report_result = self.report_controller.generate_reports_with_path_determination(
                form_data=self.form_data,
                file_operation_result=self.file_operation_result,  # Pass the Result object, not just the dict
                output_directory=self.output_directory,
                settings=self.settings
            )
            
            if not report_result.success:
                error = UIError(
                    f"Report generation failed: {report_result.error.message}",
                    user_message=report_result.error.user_message,
                    component="MainWindow"
                )
                handle_error(error, {'operation': 'report_generation', 'severity': 'critical'})
                self.show_final_completion_message()
                return
            
            # Extract results from the successful report generation
            report_data = report_result.value
            documents_dir = report_data.get('documents_dir')
            base_forensic_path = report_data.get('base_forensic_path')
            generated = report_data.get('reports', {})
            
            self.log(f"Documents folder location: {documents_dir}")
            
            # Reports go directly into Documents folder (for compatibility)
            reports_output_dir = documents_dir
            
            # Log generated reports and handle Result objects
            successful_reports = {}
            if generated:
                for report_type, result in generated.items():
                    # ReportController always returns ReportGenerationResult objects
                    if result.success:
                        self.log(f"Generated: {result.value.name}")
                        successful_reports[report_type] = result
                    else:
                        # Error is already logged by handle_error in PDF generation
                        self.log(f"Failed to generate {report_type}: {result.error.user_message if result.error else 'Unknown error'}")
                        
                if successful_reports:
                    self.log(f"Documentation saved to: {reports_output_dir}")
                
            # Store report results for final summary
            self.reports_generated = successful_reports
            self.reports_output_dir = reports_output_dir
            
            # Handle ZIP creation (prompt already resolved at start of process)
            try:
                if self.zip_controller.should_create_zip():
                    self.log("Creating ZIP archive(s)...")
                    # Use the base forensic path from report generation
                    original_output_dir = Path(base_forensic_path) if base_forensic_path else self.output_directory
                    self.create_zip_archives(original_output_dir)
                else:
                    # No ZIP creation, show final completion now
                    self.show_final_completion_message()
            except ValueError as e:
                # This shouldn't happen since prompt was resolved at start
                self.log(f"ZIP configuration error: {e}")
                self.show_final_completion_message()                                  
                                  
                                  
        except Exception as e:
            error = UIError(
                f"Report generation failed: {str(e)}",
                user_message="Failed to generate reports. Please check permissions and try again.",
                component="MainWindow"
            )
            handle_error(error, {'operation': 'report_generation', 'severity': 'critical'})
            
    def create_zip_archives(self, base_path: Path):
        """Create ZIP archives using ZipController"""
        try:
            # Use PathService to find occurrence folder
            occurrence_result = self.workflow_controller.path_service.find_occurrence_folder(
                base_path,
                self.output_directory
            )
            
            if not occurrence_result.success:
                error = UIError(
                    f"Failed to find occurrence folder: {occurrence_result.error.message}",
                    user_message=occurrence_result.error.user_message,
                    component="MainWindow"
                )
                handle_error(error, {'operation': 'zip_occurrence_folder', 'severity': 'critical'})
                return
            
            occurrence_folder = occurrence_result.value
            
            # Create ZIP thread using controller
            self.zip_thread = self.zip_controller.create_zip_thread(
                occurrence_folder,
                self.output_directory,
                self.form_data
            )
            
            # Connect signals
            self.zip_thread.progress_update.connect(self.update_progress_with_status)
            self.zip_thread.result_ready.connect(self.on_zip_finished)
            
            # Show progress and start
            self.progress_bar.setVisible(True)
            self.zip_thread.start()
            
        except Exception as e:
            self.progress_bar.setVisible(False)
            error = UIError(
                f"ZIP creation failed to start: {str(e)}",
                user_message="Failed to start ZIP archive creation. Please check available disk space and try again.",
                component="MainWindow"
            )
            handle_error(error, {'operation': 'zip_start', 'severity': 'critical'})
    
    def on_zip_finished(self, result):
        """Handle ZIP operation completion with Result object"""
        self.progress_bar.setVisible(False)
        
        # Result objects are always passed - no need to check type
        if result.success:
            # ArchiveOperationResult.value contains the list of created archives
            created_archives = result.value or []
            self.log(f"Created {len(created_archives)} ZIP archive(s)")
            # Store ZIP results for final summary
            self.zip_archives_created = created_archives
            # Store Result object for success message integration
            self.zip_operation_result = result
            # Show final completion message that includes everything
            self.show_final_completion_message()
        else:
            # Handle error result
            error_msg = result.error.user_message if result.error else "ZIP creation failed"
            self.log(f"ZIP creation failed: {error_msg}")
            # Store failed Result object for success message integration
            self.zip_operation_result = result
            # Still show completion message for consistency
            self.show_final_completion_message()
    
    def show_final_completion_message(self):
        """Show a single final completion message with all results using service-integrated architecture"""
        try:
            # ✅ NEW: Use WorkflowController's success message integration
            from ui.dialogs.success_dialog import SuccessDialog
            
            # Collect operation results (if available)
            file_result = getattr(self, 'file_operation_result', None)
            report_results = getattr(self, 'reports_generated', None)
            zip_result = getattr(self, 'zip_operation_result', None)
            
            # Store results in workflow controller for success message building
            self.workflow_controller.store_operation_results(
                file_result=file_result,
                report_results=report_results,
                zip_result=zip_result
            )
            
            # Use workflow controller's service-integrated success message building
            success_data = self.workflow_controller.build_success_message()
            SuccessDialog.show_success_message(success_data, self)
            
            # Clear stored results to prevent memory leaks
            self.workflow_controller.clear_stored_results()
            
        except Exception as e:
            logger.error(f"Success message integration failed: {e}")
            # Show simple error message if success dialog fails
            self.log("Operation completed successfully, but could not show detailed summary")
        
        # MEMORY LEAK FIX: Comprehensive cleanup to prevent memory accumulation
        self.cleanup_operation_memory()
    
    def _get_report_display_name(self, report_type: str) -> str:
        """Get user-friendly report display name"""
        display_names = {
            'time_offset': 'Time Offset Report',
            'upload_log': 'Technician Log', 
            'hash_csv': 'Hash Verification CSV'
        }
        return display_names.get(report_type, report_type.replace('_', ' ').title())
    
    def _on_template_changed(self, template_id: str):
        """Handle template selection changes"""
        try:
            # Update the path service with the new template
            if hasattr(self, 'workflow_controller') and self.workflow_controller:
                result = self.workflow_controller.path_service.set_current_template(template_id)
                if result.success:
                    self.log(f"Template changed to: {template_id}")
                else:
                    self.log(f"Failed to change template: {result.error.user_message}")
        except Exception as e:
            self.log(f"Error changing template: {e}")
    
    def log(self, message):
        """Add message to log console"""
        if hasattr(self, 'log_console'):
            self.log_console.log(message)
        self.status_bar.showMessage(message, 3000)
        
        # Use PerformanceFormatterService to extract speed
        if self.operation_active:
            try:
                from core.services.service_registry import get_service
                from core.services.performance_formatter_service import IPerformanceFormatterService
                
                perf_service = get_service(IPerformanceFormatterService)
                speed = perf_service.extract_speed_from_message(message)
                if speed is not None:
                    self.current_copy_speed = speed
            except:
                # Service not available or parsing failed
                pass
    
    def load_json(self):
        """Load form data from JSON"""
        file, _ = QFileDialog.getOpenFileName(self, "Load JSON", "", "JSON Files (*.json)")
        if file:
            try:
                with open(file, 'r') as f:
                    data = json.load(f)
                self.form_data = FormData.from_dict(data)
                # Update UI fields
                if hasattr(self, 'form_panel'):
                    self.form_panel.load_from_data(self.form_data)
                self.log(f"Loaded data from {Path(file).name}")
            except Exception as e:
                error = UIError(
                    f"JSON loading failed: {str(e)}",
                    user_message="Failed to load JSON file. Please check the file format and try again.",
                    component="MainWindow"
                )
                handle_error(error, {'operation': 'json_load', 'file_path': file})
                
    def save_json(self):
        """Save form data to JSON"""
        file, _ = QFileDialog.getSaveFileName(self, "Save JSON", "", "JSON Files (*.json)")
        if file:
            try:
                with open(file, 'w') as f:
                    json.dump(self.form_data.to_dict(), f, indent=2)
                self.log(f"Saved data to {Path(file).name}")
            except Exception as e:
                error = UIError(
                    f"JSON saving failed: {str(e)}",
                    user_message="Failed to save JSON file. Please check folder permissions and try again.",
                    component="MainWindow"
                )
                handle_error(error, {'operation': 'json_save', 'file_path': file})
                
    def show_user_settings(self):
        """Show user settings dialog"""
        dialog = UserSettingsDialog(self.settings, self)
        if dialog.exec() == QDialog.Accepted:
            # Settings already saved in dialog.accept() - no need to save again
            self.log("User settings saved")
    
    def show_performance_monitor(self):
        """Show performance monitor dialog"""
        from ui.dialogs.performance_monitor import PerformanceMonitorDialog
        
        # Create or show existing monitor
        if not hasattr(self, 'performance_monitor') or not self.performance_monitor:
            self.performance_monitor = PerformanceMonitorDialog(self)
        
        self.performance_monitor.show()
        self.performance_monitor.raise_()
        self.performance_monitor.activateWindow()
        
    def show_zip_settings(self):
        """Show ZIP settings dialog"""
        dialog = ZipSettingsDialog(self.settings, self)
        if dialog.exec() == QDialog.Accepted:
            dialog.save_settings()
            self.zip_controller.on_settings_changed()  # Notify controller of changes
            self.log("ZIP settings saved")
            
    def show_about(self):
        """Show about dialog"""
        dialog = AboutDialog(self)
        dialog.exec()
    
    def _import_template(self):
        """Import template via main menu"""
        try:
            from ui.dialogs.template_import_dialog import show_template_import_dialog
            if show_template_import_dialog(self):
                # Refresh forensic tab template selector after successful import
                if hasattr(self, 'forensic_tab') and hasattr(self.forensic_tab, 'template_selector'):
                    self.forensic_tab.template_selector._load_templates()
                logger.info("Template imported successfully via main menu")
        except Exception as e:
            logger.error(f"Template import error from main menu: {e}")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Import Error", f"Failed to import template:\n\n{e}")
    
    def _export_current_template(self):
        """Export current template via main menu"""
        try:
            # Get current template from forensic tab selector
            if hasattr(self, 'forensic_tab') and hasattr(self.forensic_tab, 'template_selector'):
                self.forensic_tab.template_selector._export_current_template()
            else:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(self, "Export Template", "Please select a template in the Forensic tab first.")
        except Exception as e:
            logger.error(f"Template export error from main menu: {e}")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Export Error", f"Failed to export template:\n\n{e}")
    
    def _manage_templates(self):
        """Manage templates via main menu"""
        try:
            from ui.dialogs.template_management_dialog import TemplateManagementDialog
            dialog = TemplateManagementDialog(self)
            dialog.templates_changed.connect(self._on_templates_changed)
            dialog.exec()
        except ImportError:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, 
                "Coming Soon", 
                "Advanced template management features are coming in a future update.\n\n"
                "Current available options:\n"
                "• Import Template (Ctrl+Shift+I)\n"
                "• Export Template\n"
                "• Template selector in Forensic tab"
            )
        except Exception as e:
            logger.error(f"Template management error from main menu: {e}")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Management Error", f"Failed to open template management:\n\n{e}")
    
    def _show_template_documentation(self):
        """Show template documentation"""
        from PySide6.QtWidgets import QMessageBox
        from PySide6.QtCore import Qt
        
        doc_text = """
<h3>Folder Structure Templates</h3>
<p>Templates define how your folder structures are organized for different agencies and use cases.</p>

<h4>Available Templates:</h4>
<ul>
<li><b>Default Forensic:</b> Standard law enforcement structure</li>
<li><b>RCMP Basic:</b> Royal Canadian Mounted Police format</li>
<li><b>Generic Agency:</b> Simple three-level structure</li>
</ul>

<h4>Template Features:</h4>
<ul>
<li><b>Import Templates:</b> Load custom JSON templates from files</li>
<li><b>Export Templates:</b> Save templates to share with other agencies</li>
<li><b>Conditional Patterns:</b> Templates adapt to available data</li>
<li><b>Date Formats:</b> Military (28AUG25) or ISO (2025-08-28) formatting</li>
</ul>

<h4>Available Fields:</h4>
<p>Templates can use these form fields: <code>occurrence_number</code>, <code>business_name</code>, 
<code>location_address</code>, <code>video_start_datetime</code>, <code>video_end_datetime</code>, 
<code>technician_name</code>, <code>badge_number</code>, and computed fields like <code>current_datetime</code>.</p>

<p><b>Location:</b> System templates are in <code>templates/folder_templates.json</code><br>
<b>User Templates:</b> Stored in your user data directory</p>
        """
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Template Documentation")
        msg.setTextFormat(Qt.RichText)
        msg.setText(doc_text)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec()
    
    def _on_templates_changed(self):
        """Handle templates changed signal from management dialog"""
        try:
            # Refresh forensic tab template selector
            if hasattr(self, 'forensic_tab') and hasattr(self.forensic_tab, 'template_selector'):
                self.forensic_tab.template_selector._load_templates()
            logger.info("Templates refreshed after management changes")
        except Exception as e:
            logger.error(f"Error refreshing templates: {e}")
        
    def closeEvent(self, event):
        """Properly clean up all threads before closing using ThreadManagementService"""
        from core.logger import logger
        from core.services.service_registry import get_service
        from core.services.thread_management_service import IThreadManagementService
        
        # Get thread management service
        thread_service = get_service(IThreadManagementService)
        
        # Use ThreadManagementService for clean shutdown
        app_components = {
            'main_window': self,
            'batch_tab': getattr(self, 'batch_tab', None),
            'hashing_tab': getattr(self, 'hashing_tab', None)
        }
        
        # Perform complete shutdown sequence
        shutdown_result = thread_service.shutdown_all_threads(
            app_components,
            graceful_timeout_ms=5000,
            force_terminate_stuck=True
        )
        
        if not shutdown_result.success:
            logger.error(f"Thread shutdown had issues: {shutdown_result.error.message}")
            # Show warning to user
            warning_error = UIError(
                "Some operations could not be stopped cleanly",
                user_message="Some background operations may not have stopped properly. The application will close anyway.",
                component="MainWindow",
                severity=ErrorSeverity.WARNING
            )
            handle_error(warning_error, {'operation': 'app_exit_thread_shutdown_incomplete'})
        else:
            logger.info("All threads shutdown successfully")
        
        # Clean up error notifications
        if hasattr(self, 'error_notification_manager') and self.error_notification_manager:
            self.error_handler.unregister_ui_callback(self._handle_error_notification)
            self.error_notification_manager.clear_all()
            self.error_notification_manager.close()  # Close the top-level notification window
            self.error_notification_manager = None
        
        # Save settings
        self.settings.sync()
        logger.info("Application closing normally")
        
        # Accept the close event
        event.accept()
    
    def _setup_error_notifications(self):
        """Initialize error notification system and integrate with error handler"""
        # Create notification manager
        self.error_notification_manager = ErrorNotificationManager(self)
        
        # Register with error handler for notifications
        self.error_handler.register_ui_callback(self._handle_error_notification)
        
        logger.info("Error notification system initialized")
    
    def _handle_error_notification(self, error: FSAError, context: dict):
        """
        Handle error notifications from the centralized error handler
        
        Args:
            error: The FSAError that occurred
            context: Additional context information
        """
        if self.error_notification_manager:
            self.error_notification_manager.show_error(error, context)
    
    def resizeEvent(self, event):
        """Handle window resize to maintain notification positioning"""
        super().resizeEvent(event)
        if hasattr(self, 'error_notification_manager') and self.error_notification_manager:
            self.error_notification_manager._update_position()
    
    def moveEvent(self, event):
        """Handle window move to maintain notification positioning"""
        super().moveEvent(event)
        if hasattr(self, 'error_notification_manager') and self.error_notification_manager:
            self.error_notification_manager._update_position()
    
    def showEvent(self, event):
        """Handle window show to ensure notifications are positioned correctly"""
        super().showEvent(event)
        
        # Center window on first show
        if not hasattr(self, '_window_centered'):
            self._center_on_screen()
            self._window_centered = True
            
        if hasattr(self, 'error_notification_manager') and self.error_notification_manager:
            self.error_notification_manager._update_position()
    
    
    def _center_on_screen(self):
        """Center the main window on the primary screen"""
        from PySide6.QtWidgets import QApplication
        
        try:
            # Center on primary screen (no parent for MainWindow)
            screen = QApplication.primaryScreen()
            screen_geometry = screen.availableGeometry()
            screen_center = screen_geometry.center()
            
            # Calculate position to center this window using SuccessDialog pattern
            window_rect = self.geometry()
            new_x = screen_center.x() - window_rect.width() // 2
            new_y = screen_center.y() - window_rect.height() // 2
            
            self.move(new_x, new_y)
        except Exception as e:
            # Log warning but don't fail application startup
            logger.warning(f"Failed to center window on screen: {e}")

    def _test_error_notification(self, severity: str):
        """
        Test error notification system with different severity levels
        
        Args:
            severity: Severity level to test ('info', 'warning', 'error', 'critical')
        """
        from core.exceptions import ValidationError, FileOperationError
        from core.error_handler import handle_error
        
        messages = {
            'info': "This is a test info notification. It should auto-dismiss in 5 seconds.",
            'warning': "This is a test warning notification. It should auto-dismiss in 8 seconds.",
            'error': "This is a test error notification. It will not auto-dismiss.",
            'critical': "This is a test critical notification. Requires manual dismissal."
        }
        
        contexts = {
            'info': {'operation': 'notification_test', 'severity': 'info', 'component': 'MainWindow'},
            'warning': {'operation': 'validation_test', 'severity': 'warning', 'component': 'FormPanel'},
            'error': {'operation': 'file_test', 'severity': 'error', 'component': 'FileController'},
            'critical': {'operation': 'system_test', 'severity': 'critical', 'component': 'ErrorHandler'}
        }
        
        # Create appropriate error type
        message = messages.get(severity, "Unknown test notification")
        context = contexts.get(severity, {})
        
        if severity == 'warning':
            error = ValidationError(
                {'test_field': 'Test validation error'},
                user_message=message
            )
        elif severity == 'error':
            error = FileOperationError(
                "Test file operation error",
                user_message=message
            )
        else:
            error = FSAError(
                f"Test {severity} error",
                user_message=message
            )
        
        # Send through error handler
        handle_error(error, context)
        
        logger.info(f"Test {severity} notification triggered")