#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main application window - coordinator only
"""

from datetime import datetime
from pathlib import Path
from typing import List
import json

from PySide6.QtCore import Qt, QSettings, QDateTime, QTimer
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
from core.workers import FolderStructureThread
from core.workers.zip_operations import ZipOperationThread
from ui.components import FormPanel, FilesPanel, LogConsole
from ui.styles import CarolinaBlueTheme
from ui.custom_template_widget import CustomTemplateWidget
from ui.dialogs import ZipSettingsDialog, AboutDialog, UserSettingsDialog
try:
    from ui.dialogs.performance_settings_safe import PerformanceSettingsDialog
    PERFORMANCE_UI_AVAILABLE = True
except ImportError:
    PERFORMANCE_UI_AVAILABLE = False
from ui.tabs import ForensicTab
from ui.tabs.batch_tab import BatchTab
from utils.zip_utils import ZipSettings


class MainWindow(QMainWindow):
    """Main application window - coordinator only"""
    
    def __init__(self):
        super().__init__()
        
        # Initialize data
        self.form_data = FormData()
        self.settings = QSettings('FolderStructureUtility', 'Settings')
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
        
        # Initialize performance monitoring
        self.setup_performance_monitoring()
        
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
        
        # Custom Mode tab - using the existing widget
        self.custom_template_widget = CustomTemplateWidget(
            self.settings, 
            self.form_data,
            self
        )
        
        # Connect signals
        self.custom_template_widget.create_tab_requested.connect(self.create_custom_tab)
        self.custom_template_widget.process_requested.connect(self.process_custom_structure)
        
        self.tabs.addTab(self.custom_template_widget, "Custom Mode")
        
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
        
        # Add performance indicators to status bar
        self.setup_status_bar_monitoring()
        
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
        
        zip_settings_action = QAction("ZIP Settings", self)
        zip_settings_action.triggered.connect(self.show_zip_settings)
        settings_menu.addAction(zip_settings_action)
        
        if PERFORMANCE_UI_AVAILABLE:
            performance_action = QAction("Performance Settings", self)
            performance_action.triggered.connect(self.show_performance_settings)
            settings_menu.addAction(performance_action)
        
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
        # Load technician info
        tech_name = self.settings.value('technician_name', '')
        badge_number = self.settings.value('badge_number', '')
        
        if hasattr(self, 'form_panel'):
            self.form_panel.tech_name.setText(tech_name)
            self.form_panel.badge_number.setText(badge_number)
            
    def process_forensic_files(self):
        """Process files using forensic folder structure"""
        # Validate form
        errors = self.form_data.validate()
        if errors:
            QMessageBox.warning(self, "Validation Error", "\n".join(errors))
            return
            
        # Get files
        files, folders = self.files_panel.get_all_items()
        
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
        calculate_hash = self.settings.value('calculate_hashes', True, type=bool)
        
        # Start file operation
        self.file_thread = self.file_controller.process_forensic_files(
            self.form_data,
            files,
            folders,
            self.output_directory,
            calculate_hash
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
        
    def process_custom_structure(self, template_levels: List[str]):
        """Process files with a custom template structure"""
        # Validate form
        errors = self.form_data.validate()
        if errors:
            QMessageBox.warning(self, "Validation Error", "\n".join(errors))
            return
            
        # Get files
        files, folders = self.files_panel.get_all_items()
        
        if not files and not folders:
            QMessageBox.warning(self, "No Files", "Please select files or folders to process")
            return
            
        # Ask for output location
        output_dir = QFileDialog.getExistingDirectory(
            self, 
            "Select Output Location", 
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if not output_dir:
            return
            
        self.output_directory = Path(output_dir)
        self.last_output_directory = self.output_directory
        
        # Get hash calculation preference
        calculate_hash = self.settings.value('calculate_hashes', True, type=bool)
        
        # Process files
        self.file_thread = self.file_controller.process_custom_files(
            self.form_data,
            template_levels,
            files,
            folders,
            self.output_directory,
            calculate_hash
        )
        
        # Connect signals
        self.file_thread.progress.connect(self.update_progress)
        self.file_thread.status.connect(self.log)
        self.file_thread.finished.connect(self.on_operation_finished)
        
        self.process_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.operation_active = True
        
        self.file_thread.start()
        
    def create_custom_tab(self, name: str, template_levels: List[str]):
        """Create a new tab with a custom template"""
        # Create a widget for the new tab
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        
        # Show the template structure
        info_group = QGroupBox(f"Template: {name}")
        info_layout = QVBoxLayout()
        
        from PySide6.QtWidgets import QTextEdit
        structure_text = QTextEdit()
        structure_text.setReadOnly(True)
        structure_text.setMaximumHeight(100)
        
        # Display the structure
        preview_lines = []
        for i, level in enumerate(template_levels):
            indent = "  " * i
            preview_lines.append(f"{indent}📁 {level}")
        structure_text.setPlainText("\n".join(preview_lines))
        
        info_layout.addWidget(structure_text)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Add file selection
        files_panel = FilesPanel()
        files_panel.log_message.connect(self.log)
        layout.addWidget(files_panel)
        
        # Process button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        from PySide6.QtWidgets import QPushButton
        process_btn = QPushButton(f"Process with {name} Structure")
        process_btn.clicked.connect(lambda: self._process_custom_tab(template_levels, files_panel))
        btn_layout.addWidget(process_btn)
        layout.addLayout(btn_layout)
        
        # Add the new tab
        self.tabs.addTab(tab_widget, name)
        
        # Switch to the new tab
        self.tabs.setCurrentWidget(tab_widget)
        
        QMessageBox.information(self, "Tab Created", 
                              f"New tab '{name}' has been created!\n\n"
                              "You can now use this template directly from its own tab.")
                              
    def _process_custom_tab(self, template_levels: List[str], files_panel: FilesPanel):
        """Process files from a custom tab"""
        # Get files from the specific files panel
        files, folders = files_panel.get_all_items()
        
        # Validate
        errors = self.form_data.validate()
        if errors:
            QMessageBox.warning(self, "Validation Error", "\n".join(errors))
            return
            
        if not files and not folders:
            QMessageBox.warning(self, "No Files", "Please select files or folders to process")
            return
            
        # Ask for output location
        output_dir = QFileDialog.getExistingDirectory(
            self, 
            "Select Output Location", 
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if not output_dir:
            return
            
        self.output_directory = Path(output_dir)
        self.last_output_directory = self.output_directory
        
        # Get hash calculation preference
        calculate_hash = self.settings.value('calculate_hashes', True, type=bool)
        
        # Process files
        self.file_thread = self.file_controller.process_custom_files(
            self.form_data,
            template_levels,
            files,
            folders,
            self.output_directory,
            calculate_hash
        )
        
        # Connect signals
        self.file_thread.progress.connect(self.update_progress)
        self.file_thread.status.connect(self.log)
        self.file_thread.finished.connect(self.on_operation_finished)
        
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
            
            # Ask user if they want to generate reports
            reply = QMessageBox.question(self, "Generate Reports?",
                                       completion_message + "\n\nWould you like to generate PDF reports?",
                                       QMessageBox.Yes | QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                self.generate_reports()
            else:
                QMessageBox.information(self, "Success", message)
        else:
            QMessageBox.critical(self, "Error", message)
            
        self.log(message)
        
    def generate_reports(self):
        """Generate PDF reports and hash verification CSV"""
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
            
            # Generate reports
            generated = self.report_controller.generate_reports(
                self.form_data,
                self.file_operation_results,
                reports_output_dir
            )
            
            # Log generated reports
            for report_type, path in generated.items():
                self.log(f"Generated: {path.name}")
                
            # Ask about ZIP creation
            if self.report_controller.should_create_zip():
                reply = QMessageBox.question(self, "Create ZIP Archive?",
                                           "Would you like to create ZIP archive(s)?",
                                           QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    # Pass the original file location for ZIP creation
                    original_output_dir = file_dest_path.parent
                    self.create_zip_archives(original_output_dir)
                    
            QMessageBox.information(self, "Reports Generated", 
                                  f"Reports have been saved to:\n{reports_output_dir}")                                  
                                  
                                  
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate reports: {str(e)}")
            
    def create_zip_archives(self, base_path: Path):
        """Create ZIP archives using thread"""
        try:
            # Create settings
            settings = ZipSettings()
            settings.compression_level = self.settings.value('zip_compression_level', zipfile.ZIP_STORED)
            settings.create_at_root = self.settings.value('zip_at_root', True, type=bool)
            settings.create_at_location = self.settings.value('zip_at_location', False, type=bool)
            settings.create_at_datetime = self.settings.value('zip_at_datetime', False, type=bool)
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
            zip_names = [z.name for z in created_archives]
            QMessageBox.information(
                self, 
                "ZIP Archives Created",
                f"Created {len(created_archives)} ZIP archive(s) in:\n{self.output_directory}\n\n"
                f"Files:\n" + "\n".join(zip_names)
            )
        else:
            if not success:
                QMessageBox.critical(self, "ZIP Error", message)
            else:
                self.log("No ZIP archives created")
            
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
                    # Update the label immediately
                    if hasattr(self, 'copy_speed_label'):
                        self.copy_speed_label.setText(f"{self.current_copy_speed:.1f} MB/s")
                        self.copy_speed_label.setStyleSheet("padding: 0 10px; font-weight: bold; color: green;")
                        print(f"[DEBUG] Updated speed to: {self.current_copy_speed:.1f} MB/s")
            except (ValueError, IndexError) as e:
                print(f"[DEBUG] Error parsing speed: {e}")
        
        # Also update when we see "Copying:" messages
        if self.operation_active and "Copying:" in message:
            if hasattr(self, 'copy_speed_label'):
                self.copy_speed_label.setText("Processing...")
                self.copy_speed_label.setStyleSheet("padding: 0 10px; font-weight: bold; color: blue;")
        
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
        
    def show_zip_settings(self):
        """Show ZIP settings dialog"""
        dialog = ZipSettingsDialog(self.settings, self)
        if dialog.exec() == QDialog.Accepted:
            dialog.save_settings()
            self.log("ZIP settings saved")
            
    def show_performance_settings(self):
        """Show performance settings dialog"""
        if PERFORMANCE_UI_AVAILABLE:
            dialog = PerformanceSettingsDialog(self)
            dialog.settings_changed.connect(self.on_performance_settings_changed)
            dialog.exec()
        else:
            QMessageBox.information(
                self, "Performance Settings", 
                "Performance optimization modules are not available.\n"
                "Install required dependencies to enable this feature."
            )
            
    def on_performance_settings_changed(self):
        """Handle performance settings changes"""
        self.log("Performance settings updated")
        
        # Update performance mode indicator
        try:
            adaptive_enabled = self.settings.value("performance/adaptive_enabled", True, type=bool)
            if hasattr(self, 'performance_label'):
                if adaptive_enabled:
                    self.performance_label.setText("Adaptive Mode")
                else:
                    self.performance_label.setText("Standard Mode")
        except:
            pass
        
    def show_about(self):
        """Show about dialog"""
        dialog = AboutDialog(self)
        dialog.exec()
        
    def closeEvent(self, event):
        """Save settings on close and ensure threads are stopped"""
        # Stop any running threads
        if hasattr(self, 'zip_thread') and self.zip_thread.isRunning():
            self.zip_thread.cancel()
            self.zip_thread.wait()  # Wait for thread to finish
            
        if hasattr(self, 'file_thread') and self.file_thread.isRunning():
            self.file_thread.cancel()
            self.file_thread.wait()
            
        if hasattr(self, 'folder_thread') and self.folder_thread.isRunning():
            self.folder_thread.cancel()
            self.folder_thread.wait()
        
        # Save settings
        if hasattr(self, 'form_panel'):
            self.settings.setValue('technician_name', self.form_panel.tech_name.text())
            self.settings.setValue('badge_number', self.form_panel.badge_number.text())
        event.accept()
        
    def setup_status_bar_monitoring(self):
        """Set up performance monitoring in status bar"""
        # Create mode indicator
        self.performance_label = QLabel("Standard Mode")
        self.performance_label.setStyleSheet("padding: 0 10px;")
        
        # Add separator
        sep = QLabel("|")
        sep.setStyleSheet("color: gray; padding: 0 5px;")
        
        # Copy speed indicator
        self.copy_speed_label = QLabel("Ready")
        self.copy_speed_label.setStyleSheet("padding: 0 10px; font-weight: bold;")
        
        # Add to status bar
        self.status_bar.addPermanentWidget(self.performance_label)
        self.status_bar.addPermanentWidget(sep)
        self.status_bar.addPermanentWidget(self.copy_speed_label)
            
    def setup_performance_monitoring(self):
        """Initialize performance monitoring timer"""
        try:
            import psutil
            from collections import deque
            
            # Initialize CPU sampling buffer for smooth averaging
            self.cpu_samples = deque(maxlen=5)
            
            # Check if adaptive mode is enabled
            adaptive_enabled = self.settings.value("performance/adaptive_enabled", True, type=bool)
            if hasattr(self, 'performance_label'):
                if adaptive_enabled:
                    self.performance_label.setText("Adaptive Mode")
                else:
                    self.performance_label.setText("Standard Mode")
            
            # Start monitoring timer
            self.performance_timer = QTimer()
            self.performance_timer.timeout.connect(self.update_performance_status)
            self.performance_timer.start(2000)  # Update every 2 seconds
            
        except (ImportError, AttributeError):
            # Monitoring not available
            pass
            
    def update_performance_status(self):
        """Update performance indicators in status bar"""
        try:
            import psutil
            
            # Non-blocking CPU check
            cpu_percent = psutil.cpu_percent(interval=0)
            if not hasattr(self, 'cpu_samples'):
                from collections import deque
                self.cpu_samples = deque(maxlen=5)
            
            self.cpu_samples.append(cpu_percent)
            avg_cpu = sum(self.cpu_samples) / len(self.cpu_samples) if self.cpu_samples else 0
            
            if hasattr(self, 'cpu_label'):
                self.cpu_label.setText(f"CPU: {avg_cpu:.0f}%")
                
                # Color code based on usage
                if avg_cpu > 80:
                    self.cpu_label.setStyleSheet("color: red;")
                elif avg_cpu > 60:
                    self.cpu_label.setStyleSheet("color: orange;")
                else:
                    self.cpu_label.setStyleSheet("")
            
            # Update memory usage
            memory = psutil.virtual_memory()
            if hasattr(self, 'memory_label'):
                self.memory_label.setText(f"RAM: {memory.percent:.0f}%")
                
                if memory.percent > 85:
                    self.memory_label.setStyleSheet("color: red;")
                elif memory.percent > 70:
                    self.memory_label.setStyleSheet("color: orange;")
                else:
                    self.memory_label.setStyleSheet("")
            
            # Don't update copy speed here - it's updated in log() method
                
        except (ImportError, AttributeError):
            pass