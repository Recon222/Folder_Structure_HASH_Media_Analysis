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
    QProgressBar, QStatusBar, QFileDialog, QMessageBox,
    QSplitter, QHBoxLayout, QDialog, QDialogButtonBox,
    QGroupBox, QComboBox, QCheckBox, QPushButton, QLabel
)
import zipfile

from controllers import FileController, ReportController, FolderController
from core.models import FormData
from core.settings_manager import settings
from core.logger import logger
from core.workers import FolderStructureThread
from core.workers.zip_operations import ZipOperationThread
from ui.components import FormPanel, FilesPanel, LogConsole
from ui.styles import CarolinaBlueTheme
from ui.dialogs import ZipSettingsDialog, AboutDialog, UserSettingsDialog
from ui.tabs import ForensicTab
from ui.tabs.batch_tab import BatchTab
from utils.zip_utils import ZipSettings


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
        self.report_controller = ReportController(self.settings)
        self.folder_controller = FolderController()
        
        # Set up UI
        self.setWindowTitle("Folder Structure Utility")
        self.resize(1200, 800)
        
        self._setup_ui()
        self._apply_theme()
        self._load_settings()
        
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
            QMessageBox.warning(self, "Validation Error", "\n".join(errors))
            return
            
        # Get files
        logger.debug(f"Using files_panel {id(self.files_panel)}")
        logger.debug(f"Forensic tab files_panel {id(self.forensic_tab.files_panel)}")
        files, folders = self.files_panel.get_all_items()
        logger.debug(f"Retrieved files: {files}")
        logger.debug(f"Retrieved folders: {folders}")
        
        if not files and not folders:
            QMessageBox.warning(self, "No Files", "Please select files or folders to process")
            return
            
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
        
        # Connect signals
        self.file_thread.progress.connect(self.update_progress)
        self.file_thread.status.connect(self.log)
        self.file_thread.finished.connect(self.on_operation_finished)
        
        # Disable UI and show progress
        self.process_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.operation_active = True
        
        self.file_thread.start()
        
    def update_progress(self, value):
        """Update progress bar"""
        self.progress_bar.setValue(value)
        
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
            
            QMessageBox.information(self, "Success", completion_message)
        else:
            QMessageBox.critical(self, "Error", message)
            
        self.log(message)
        
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
            documents_dir = occurrence_dir / "Documents"
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
            
            # Check if we should create ZIP based on settings (NO PROMPTS)
            if self.report_controller.should_create_zip():
                # Automatically create ZIP if enabled in settings
                self.log("Creating ZIP archive(s)...")
                original_output_dir = file_dest_path.parent
                self.create_zip_archives(original_output_dir)
            else:
                # No ZIP creation, show final completion now
                self.show_final_completion_message()                                  
                                  
                                  
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate reports: {str(e)}")
            
    def create_zip_archives(self, base_path: Path):
        """Create ZIP archives using thread"""
        try:
            # Create settings
            settings = ZipSettings()
            settings.compression_level = self.settings.get('zip_compression_level', zipfile.ZIP_STORED)
            settings.create_at_root = self.settings.get('zip_at_root', True)
            settings.create_at_location = self.settings.get('zip_at_location', False)
            settings.create_at_datetime = self.settings.get('zip_at_datetime', False)
            settings.output_path = self.output_directory
            
            # Find the occurrence folder for zipping
            current_path = base_path
            while current_path != self.output_directory and current_path.parent != self.output_directory:
                current_path = current_path.parent
            
            # current_path should now be the occurrence number folder
            occurrence_folder = current_path
            
            # Create and start thread
            self.zip_thread = ZipOperationThread(
                occurrence_folder,  # Zip the occurrence folder
                self.output_directory,
                settings,
                self.form_data
            )
            
            # Connect signals
            self.zip_thread.progress.connect(self.progress_bar.setValue)
            self.zip_thread.status.connect(self.log)
            self.zip_thread.finished.connect(self.on_zip_finished)
            
            # Show progress and start
            self.progress_bar.setVisible(True)
            self.zip_thread.start()
            
        except Exception as e:
            self.progress_bar.setVisible(False)
            QMessageBox.critical(self, "ZIP Error", f"Failed to start ZIP: {str(e)}")
    
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
        
        # Show the single completion dialog
        QMessageBox.information(
            self,
            "Process Complete",
            "\n".join(message_parts)
        )
        
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
        
        # Debug: Print all messages during operation
        if self.operation_active:
            print(f"[DEBUG] Operation message: {message}")
            
        # Extract speed information from status messages
        if self.operation_active and " @ " in message:
            try:
                speed_part = message.split(" @ ")[1]
                if "MB/s" in speed_part:
                    speed_str = speed_part.split("MB/s")[0].strip()
                    self.current_copy_speed = float(speed_str)
                    print(f"[DEBUG] Updated speed to: {self.current_copy_speed:.1f} MB/s")
            except (ValueError, IndexError) as e:
                print(f"[DEBUG] Error parsing speed: {e}")
        
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
                QMessageBox.critical(self, "Error", f"Failed to load JSON: {str(e)}")
                
    def save_json(self):
        """Save form data to JSON"""
        file, _ = QFileDialog.getSaveFileName(self, "Save JSON", "", "JSON Files (*.json)")
        if file:
            try:
                with open(file, 'w') as f:
                    json.dump(self.form_data.to_dict(), f, indent=2)
                self.log(f"Saved data to {Path(file).name}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save JSON: {str(e)}")
                
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
        
        # If there are active operations, ask user for confirmation
        if threads_to_stop:
            # Check if user wants confirmation (from settings)
            if self.settings.get('CONFIRM_EXIT', True):
                thread_names = [name for name, _ in threads_to_stop]
                message = (
                    f"The following operations are still running:\n"
                    f"• {chr(10).join('• ' + name for name in thread_names)}\n\n"
                    f"Do you want to cancel them and exit?"
                )
                
                reply = QMessageBox.question(
                    self,
                    "Active Operations",
                    message,
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No  # Default to No for safety
                )
                
                if reply == QMessageBox.No:
                    event.ignore()
                    return
            
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
        
        # Save settings
        self.settings.sync()
        logger.info("Application closing normally")
        
        # Accept the close event
        event.accept()