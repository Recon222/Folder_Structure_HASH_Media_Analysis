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
    QGroupBox, QComboBox, QCheckBox, QPushButton, QLabel
)

from controllers import FileController, ReportController, FolderController
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
        
        # Initialize controllers
        self.file_controller = FileController()
        self.folder_controller = FolderController()
        self.zip_controller = ZipController(self.settings)
        self.report_controller = ReportController(self.settings, self.zip_controller)
        
        # Initialize error notification system
        self.error_notification_manager = None  # Will be created after UI setup
        self.error_handler = get_error_handler()
        
        # Set up UI
        self.setWindowTitle("Folder Structure Utility")
        self.resize(1200, 800)
        
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
        
        # Hashing tab
        self.hashing_tab = HashingTab()
        self.hashing_tab.log_message.connect(self.log)
        self.tabs.addTab(self.hashing_tab, "Hashing")
        
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
        logger.debug(f"Using files_panel {id(self.files_panel)}")
        logger.debug(f"Forensic tab files_panel {id(self.forensic_tab.files_panel)}")
        files, folders = self.files_panel.get_all_items()
        logger.debug(f"Retrieved files: {files}")
        logger.debug(f"Retrieved folders: {folders}")
        
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
        calculate_hash = self.settings.get('calculate_hashes', True)
        
        # Get performance monitor if it exists
        perf_monitor = getattr(self, 'performance_monitor', None) if hasattr(self, 'performance_monitor') else None
        
        # Start file operation
        self.file_thread = self.file_controller.process_forensic_files(
            self.form_data,
            files,
            folders,
            self.output_directory,
            calculate_hash,
            perf_monitor
        )
        
        # Connect signals (nuclear migration: use unified signals)
        self.file_thread.progress_update.connect(self.update_progress_with_status)
        self.file_thread.result_ready.connect(self.on_operation_finished_result)
        
        # Disable UI and show progress
        self.process_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.operation_active = True
        
        self.file_thread.start()
        
    def update_progress(self, value):
        """Update progress bar"""
        self.progress_bar.setValue(value)
        
    def update_progress_with_status(self, percentage, message):
        """Update progress bar and log status (nuclear migration: unified signal handler)"""
        self.progress_bar.setValue(percentage)
        if message:
            self.log(message)
        
    def on_operation_finished(self, success, message, results):
        """Handle operation completion"""
        self.progress_bar.setVisible(False)
        self.process_btn.setEnabled(True)
        self.operation_active = False
        self.current_copy_speed = 0.0
        
        # Stop performance monitor if it's running
        if hasattr(self, 'performance_monitor') and self.performance_monitor:
            if hasattr(self.performance_monitor, 'stop_monitoring'):
                self.performance_monitor.stop_monitoring()
        
        # Reset status label
        if hasattr(self, 'copy_speed_label'):
            self.copy_speed_label.setText("Ready")
            self.copy_speed_label.setStyleSheet("padding: 0 10px; font-weight: bold;")
        
        if success:
            # Store results for potential PDF generation
            self.file_operation_results = results
            
            # Format completion message with performance stats
            completion_message = "Files copied successfully!"
            performance_stats = results.get('_performance_stats', {})
            
            if performance_stats:
                files_count = performance_stats.get('files_processed', 0)
                total_mb = performance_stats.get('total_size_mb', 0)
                total_time = performance_stats.get('total_time_seconds', 0)
                avg_speed = performance_stats.get('average_speed_mbps', 0)
                peak_speed = performance_stats.get('peak_speed_mbps', 0)
                mode = performance_stats.get('mode', 'unknown')
                
                stats_text = f"\n\n📊 Performance Summary:\n"
                stats_text += f"Files: {files_count}\n"
                stats_text += f"Size: {total_mb:.1f} MB\n"
                stats_text += f"Time: {total_time:.1f} seconds\n"
                stats_text += f"Average Speed: {avg_speed:.1f} MB/s\n"
                if peak_speed > avg_speed:
                    stats_text += f"Peak Speed: {peak_speed:.1f} MB/s\n"
                stats_text += f"Mode: {mode.title()}"
                
                completion_message += stats_text
            
            # Auto-generate reports based on user settings
            if self.settings.get('generate_time_offset_pdf', True) or \
               self.settings.get('generate_upload_log_pdf', True) or \
               self.settings.get('calculate_hashes', True):
                self.log("Generating documentation...")
                self.generate_reports()
            
            # Nuclear migration: Convert success dialog to non-blocking notification  
            success_error = UIError(
                f"Forensic processing completed successfully",
                user_message=completion_message,
                component="MainWindow",
                severity=ErrorSeverity.INFO
            )
            handle_error(success_error, {
                'operation': 'forensic_completion', 
                'files_processed': performance_stats.get('files_processed', 0) if performance_stats else 0,
                'performance_included': bool(performance_stats)
            })
        else:
            error = UIError(
                f"Operation failed: {message}",
                user_message=f"The operation could not be completed:\n\n{message}",
                component="MainWindow"
            )
            handle_error(error, {'operation': 'forensic_file_processing', 'severity': 'critical'})
            
        self.log(message)
    
    def on_operation_finished_result(self, result):
        """Handle operation completion using Result objects (nuclear migration)"""
        from core.result_types import Result
        
        # Convert Result object to old format for compatibility with existing code
        if result.success:
            success = True
            message = "Files copied successfully!"
            
            # Extract results from Result object
            if hasattr(result, 'value') and result.value:
                results = result.value
            else:
                results = {}
                
            # Add metadata to results if available
            if hasattr(result, 'metadata') and result.metadata:
                results.update(result.metadata)
                
        else:
            success = False
            # Get user-friendly message from error
            if result.error and hasattr(result.error, 'user_message'):
                message = result.error.user_message
            else:
                message = "Operation failed"
            results = {}
            
        # Call the existing handler with converted data
        self.on_operation_finished(success, message, results)
        
    def generate_reports(self):
        """Generate PDF reports and hash verification CSV based on user settings"""
        try:
            # Get the output directory structure
            file_dest_path = Path(list(self.file_operation_results.values())[0]['dest_path'])
            
            # Navigate to root folder (occurrence number level)
            # Current structure might be: output_base/OccurrenceNumber/Business @ Address/DateTime/
            # We want: output_base/OccurrenceNumber/Documents/Address/
            
            # Find the occurrence number folder by going up until we find the output directory
            current_path = file_dest_path.parent
            while current_path != self.output_directory and current_path.parent != self.output_directory:
                current_path = current_path.parent
            
            # current_path should now be the occurrence number folder
            occurrence_dir = current_path
            # Move Documents folder to business/location level instead of occurrence level
            business_dir = file_dest_path.parent.parent  # Go from datetime -> business level
            documents_dir = business_dir / "Documents"
            documents_dir.mkdir(parents=True, exist_ok=True)
            
            # Reports go directly into Documents folder
            reports_output_dir = documents_dir
            
            # Generate reports based on settings
            generated = self.report_controller.generate_reports(
                self.form_data,
                self.file_operation_results,
                reports_output_dir,
                generate_time_offset=self.settings.get('generate_time_offset_pdf', True),
                generate_upload_log=self.settings.get('generate_upload_log_pdf', True),
                generate_hash_csv=self.settings.get('calculate_hashes', True)
            )
            
            # Log generated reports
            if generated:
                for report_type, path in generated.items():
                    self.log(f"Generated: {path.name}")
                self.log(f"Documentation saved to: {reports_output_dir}")
                
            # Store report results for final summary
            self.reports_generated = generated
            self.reports_output_dir = reports_output_dir
            
            # Handle ZIP creation (prompt already resolved at start of process)
            try:
                if self.zip_controller.should_create_zip():
                    self.log("Creating ZIP archive(s)...")
                    original_output_dir = file_dest_path.parent
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
            # Find the occurrence folder for zipping
            current_path = base_path
            while current_path != self.output_directory and current_path.parent != self.output_directory:
                current_path = current_path.parent
            
            # current_path should now be the occurrence number folder
            occurrence_folder = current_path
            
            # Create ZIP thread using controller
            self.zip_thread = self.zip_controller.create_zip_thread(
                occurrence_folder,
                self.output_directory,
                self.form_data
            )
            
            # Connect signals (nuclear migration: use unified signals)
            self.zip_thread.progress_update.connect(self.update_progress_with_status)
            self.zip_thread.result_ready.connect(self.on_zip_finished_result)
            
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
    
    def on_zip_finished_result(self, result):
        """Handle ZIP operation completion with Result object (nuclear migration)"""
        from core.result_types import Result
        
        self.progress_bar.setVisible(False)
        
        if isinstance(result, Result):
            if result.success:
                # Extract archives from ArchiveOperationResult
                created_archives = result.value if result.value else []
                self.log(f"Created {len(created_archives)} ZIP archive(s)")
                # Store ZIP results for final summary
                self.zip_archives_created = created_archives
                # Show final completion message that includes everything
                self.show_final_completion_message()
            else:
                # Handle error result
                error_msg = result.error.user_message if result.error else "ZIP creation failed"
                self.log(f"ZIP creation failed: {error_msg}")
                # Still show completion message for consistency
                self.show_final_completion_message()
        else:
            # Fallback for unexpected result types
            self.log("ZIP operation completed with unknown result format")
            self.show_final_completion_message()

    def on_zip_finished(self, success: bool, message: str, created_archives: List[Path]):
        """Handle ZIP operation completion"""
        self.progress_bar.setVisible(False)
        
        if success and created_archives:
            self.log(f"Created {len(created_archives)} ZIP archive(s)")
            # Store ZIP results for final summary
            self.zip_archives_created = created_archives
            # Show final completion message that includes everything
            self.show_final_completion_message()
        else:
            if not success:
                # Only show error if ZIP actually failed
                self.log(f"ZIP creation failed: {message}")
            else:
                self.log("No ZIP archives created")
                # Still show completion message even if no ZIPs
                self.show_final_completion_message()
    
    def show_final_completion_message(self):
        """Show a single final completion message with all results"""
        # Build summary message
        message_parts = ["Operation Complete!\n"]
        
        # Add file copy summary
        if hasattr(self, 'file_operation_results') and self.file_operation_results:
            file_count = len([r for r in self.file_operation_results.values() 
                            if isinstance(r, dict) and 'verified' in r])
            message_parts.append(f"✓ Copied {file_count} files")
        
        # Add report summary
        if hasattr(self, 'reports_generated') and self.reports_generated:
            report_count = len(self.reports_generated)
            message_parts.append(f"✓ Generated {report_count} reports")
        
        # Add ZIP summary
        if hasattr(self, 'zip_archives_created') and self.zip_archives_created:
            zip_count = len(self.zip_archives_created)
            message_parts.append(f"✓ Created {zip_count} ZIP archive(s)")
        
        # Add output location
        if hasattr(self, 'output_directory'):
            message_parts.append(f"\nOutput location:\n{self.output_directory}")
        
        # Nuclear migration: Convert completion dialog to non-blocking notification
        success_error = UIError(
            "Processing completed successfully",
            user_message="\\n".join(message_parts),
            component="MainWindow",
            severity=ErrorSeverity.INFO
        )
        handle_error(success_error, {
            'operation': 'process_completion',
            'report_count': report_count if hasattr(self, 'report_count') else 0,
            'zip_count': len(self.zip_archives_created) if hasattr(self, 'zip_archives_created') and self.zip_archives_created else 0
        })
        
        # Clean up temporary attributes
        if hasattr(self, 'zip_archives_created'):
            delattr(self, 'zip_archives_created')
        if hasattr(self, 'reports_generated'):
            delattr(self, 'reports_generated')
        if hasattr(self, 'reports_output_dir'):
            delattr(self, 'reports_output_dir')
            
    def log(self, message):
        """Add message to log console"""
        if hasattr(self, 'log_console'):
            self.log_console.log(message)
        self.status_bar.showMessage(message, 3000)
        
        # Extract speed information from status messages for performance monitoring
        if self.operation_active and " @ " in message:
            try:
                speed_part = message.split(" @ ")[1]
                if "MB/s" in speed_part:
                    speed_str = speed_part.split("MB/s")[0].strip()
                    self.current_copy_speed = float(speed_str)
            except (ValueError, IndexError):
                # Speed parsing failed, use default speed value
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
            dialog.save_settings()
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
        
    def closeEvent(self, event):
        """Properly clean up all threads before closing
        
        This method:
        1. Identifies all running threads
        2. Asks user confirmation if threads are active
        3. Cancels threads with proper timeout handling
        4. Logs all thread lifecycle events
        """
        from core.logger import logger
        
        # Collect all active threads
        threads_to_stop = []
        
        # Check file operation thread
        if hasattr(self, 'file_thread') and self.file_thread and self.file_thread.isRunning():
            threads_to_stop.append(('File operations', self.file_thread))
            
        # Check folder operation thread
        if hasattr(self, 'folder_thread') and self.folder_thread and self.folder_thread.isRunning():
            threads_to_stop.append(('Folder operations', self.folder_thread))
            
        # Check ZIP operation thread
        if hasattr(self, 'zip_thread') and self.zip_thread and self.zip_thread.isRunning():
            threads_to_stop.append(('ZIP operations', self.zip_thread))
            
        # Check batch processor thread
        if hasattr(self, 'batch_tab') and self.batch_tab:
            # Access the batch queue widget within the batch tab
            if hasattr(self.batch_tab, 'queue_widget'):
                batch_widget = self.batch_tab.queue_widget
                if hasattr(batch_widget, 'processor_thread') and batch_widget.processor_thread:
                    if batch_widget.processor_thread.isRunning():
                        threads_to_stop.append(('Batch processing', batch_widget.processor_thread))
        
        # Check hashing operations thread
        if hasattr(self, 'hashing_tab') and self.hashing_tab:
            if self.hashing_tab.hash_controller.is_operation_running():
                current_op = self.hashing_tab.hash_controller.get_current_operation()
                if current_op:
                    threads_to_stop.append(('Hash operations', current_op))
        
        # If there are active operations, show warning and proceed with graceful shutdown
        if threads_to_stop:
            thread_names = [name for name, _ in threads_to_stop]
            
            # Nuclear migration: Auto-proceed with graceful shutdown and show warning
            warning_error = UIError(
                f"Closing application with {len(threads_to_stop)} active operation(s)",
                user_message=f"The following operations will be cancelled:\n\n• " + "\n• ".join(thread_names) + "\n\nShutting down gracefully...",
                component="MainWindow",
                severity=ErrorSeverity.WARNING
            )
            handle_error(warning_error, {'operation': 'app_exit_with_active_threads', 'thread_count': len(threads_to_stop)})
            
            # User confirmed or confirmation disabled - proceed with cleanup
            logger.info(f"Shutting down with {len(threads_to_stop)} active threads")
            
            # First, send cancel signal to all threads
            for name, thread in threads_to_stop:
                logger.info(f"Cancelling {name}")
                try:
                    if hasattr(thread, 'cancel'):
                        thread.cancel()
                    elif hasattr(thread, 'cancelled'):
                        # Some threads use a flag instead of method
                        thread.cancelled = True
                except Exception as e:
                    logger.error(f"Error cancelling {name}: {e}")
            
            # Then wait for threads with timeout
            for name, thread in threads_to_stop:
                logger.info(f"Waiting for {name} to stop...")
                try:
                    if not thread.wait(5000):  # 5 second timeout
                        logger.warning(f"{name} did not stop gracefully, terminating...")
                        thread.terminate()
                        # Give it a moment to terminate
                        if not thread.wait(1000):  # 1 more second
                            logger.error(f"{name} failed to terminate properly")
                    else:
                        logger.info(f"{name} stopped successfully")
                except Exception as e:
                    logger.error(f"Error stopping {name}: {e}")
        
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
        if hasattr(self, 'error_notification_manager') and self.error_notification_manager:
            self.error_notification_manager._update_position()
    
    
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