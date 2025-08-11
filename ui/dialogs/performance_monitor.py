#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Real-time Performance Monitor Dialog
Shows live metrics during file operations with detailed reporting
"""

import time
from datetime import datetime
from typing import Optional, List, Tuple
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QProgressBar, QTextEdit, QPushButton, QSplitter,
    QTabWidget, QWidget, QGridLayout, QDialogButtonBox,
    QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QThread
from PySide6.QtGui import QPalette, QTextCursor, QFont

from core.buffered_file_ops import PerformanceMetrics
from core.settings_manager import SettingsManager


class MetricsCollector(QThread):
    """Thread to collect and emit performance metrics"""
    metrics_updated = Signal(PerformanceMetrics)
    
    def __init__(self):
        super().__init__()
        self.current_metrics: Optional[PerformanceMetrics] = None
        self.active = False
        
    def set_metrics(self, metrics: PerformanceMetrics):
        """Update current metrics object"""
        self.current_metrics = metrics
        
    def run(self):
        """Emit metrics updates every 100ms"""
        self.active = True
        while self.active:
            if self.current_metrics:
                self.metrics_updated.emit(self.current_metrics)
            self.msleep(100)  # Update 10 times per second
            
    def stop(self):
        """Stop the metrics collection"""
        self.active = False


class PerformanceMonitorDialog(QDialog):
    """Real-time performance monitoring dialog"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = SettingsManager()
        self.metrics_collector = MetricsCollector()
        self.current_metrics: Optional[PerformanceMetrics] = None
        self.operation_history: List[PerformanceMetrics] = []
        
        self.setWindowTitle("Performance Monitor")
        self.setModal(False)  # Non-modal so user can continue working
        self.setMinimumSize(800, 600)
        
        self._create_ui()
        self._setup_connections()
        
    def _create_ui(self):
        """Create the monitoring UI"""
        layout = QVBoxLayout()
        
        # Create tab widget for different views
        self.tabs = QTabWidget()
        
        # Real-time tab
        self._create_realtime_tab()
        
        # Statistics tab
        self._create_statistics_tab()
        
        # History tab
        self._create_history_tab()
        
        layout.addWidget(self.tabs)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.start_monitor_btn = QPushButton("Start Monitoring")
        self.start_monitor_btn.clicked.connect(self.start_monitoring)
        button_layout.addWidget(self.start_monitor_btn)
        
        self.stop_monitor_btn = QPushButton("Stop Monitoring")
        self.stop_monitor_btn.clicked.connect(self.stop_monitoring)
        self.stop_monitor_btn.setEnabled(False)
        button_layout.addWidget(self.stop_monitor_btn)
        
        self.generate_report_btn = QPushButton("Generate Report")
        self.generate_report_btn.clicked.connect(self.generate_report)
        button_layout.addWidget(self.generate_report_btn)
        
        button_layout.addStretch()
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
    def _create_realtime_tab(self):
        """Create real-time monitoring tab"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Current operation info
        info_group = QGroupBox("Current Operation")
        info_layout = QGridLayout()
        
        # Labels for metrics
        self.operation_label = QLabel("Status: Idle")
        info_layout.addWidget(self.operation_label, 0, 0, 1, 2)
        
        info_layout.addWidget(QLabel("Files:"), 1, 0)
        self.files_label = QLabel("0 / 0")
        info_layout.addWidget(self.files_label, 1, 1)
        
        info_layout.addWidget(QLabel("Folders:"), 2, 0)
        self.folders_label = QLabel("0 / 0")
        info_layout.addWidget(self.folders_label, 2, 1)
        
        info_layout.addWidget(QLabel("Data:"), 3, 0)
        self.data_label = QLabel("0 MB / 0 MB")
        info_layout.addWidget(self.data_label, 3, 1)
        
        info_layout.addWidget(QLabel("Buffer:"), 4, 0)
        self.buffer_label = QLabel("0 KB")
        info_layout.addWidget(self.buffer_label, 4, 1)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Speed metrics
        speed_group = QGroupBox("Transfer Speed")
        speed_layout = QGridLayout()
        
        speed_layout.addWidget(QLabel("Current:"), 0, 0)
        self.current_speed_label = QLabel("0.0 MB/s")
        self.current_speed_label.setFont(QFont("Arial", 12, QFont.Bold))
        speed_layout.addWidget(self.current_speed_label, 0, 1)
        
        speed_layout.addWidget(QLabel("Average:"), 1, 0)
        self.avg_speed_label = QLabel("0.0 MB/s")
        speed_layout.addWidget(self.avg_speed_label, 1, 1)
        
        speed_layout.addWidget(QLabel("Peak:"), 2, 0)
        self.peak_speed_label = QLabel("0.0 MB/s")
        speed_layout.addWidget(self.peak_speed_label, 2, 1)
        
        # Progress bar for current operation
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        speed_layout.addWidget(self.progress_bar, 3, 0, 1, 2)
        
        speed_group.setLayout(speed_layout)
        layout.addWidget(speed_group)
        
        # Live log
        log_group = QGroupBox("Live Activity")
        log_layout = QVBoxLayout()
        
        self.live_log = QTextEdit()
        self.live_log.setReadOnly(True)
        self.live_log.setMaximumHeight(200)
        self.live_log.setFont(QFont("Courier", 9))
        log_layout.addWidget(self.live_log)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Real-time")
        
    def _create_statistics_tab(self):
        """Create statistics tab"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # File size distribution
        dist_group = QGroupBox("File Size Distribution")
        dist_layout = QGridLayout()
        
        dist_layout.addWidget(QLabel("Small (<1MB):"), 0, 0)
        self.small_files_label = QLabel("0")
        dist_layout.addWidget(self.small_files_label, 0, 1)
        
        dist_layout.addWidget(QLabel("Medium (1-100MB):"), 1, 0)
        self.medium_files_label = QLabel("0")
        dist_layout.addWidget(self.medium_files_label, 1, 1)
        
        dist_layout.addWidget(QLabel("Large (>100MB):"), 2, 0)
        self.large_files_label = QLabel("0")
        dist_layout.addWidget(self.large_files_label, 2, 1)
        
        dist_group.setLayout(dist_layout)
        layout.addWidget(dist_group)
        
        # Performance comparison
        comp_group = QGroupBox("Performance Comparison")
        comp_layout = QVBoxLayout()
        
        self.comparison_text = QTextEdit()
        self.comparison_text.setReadOnly(True)
        self.comparison_text.setPlainText(
            "Performance comparison will appear here after operations complete.\n\n"
            "Toggle between buffered and non-buffered modes in Settings → Performance\n"
            "to see the performance difference."
        )
        comp_layout.addWidget(self.comparison_text)
        
        comp_group.setLayout(comp_layout)
        layout.addWidget(comp_group)
        
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Statistics")
        
    def _create_history_tab(self):
        """Create history tab"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # History list
        history_group = QGroupBox("Operation History")
        history_layout = QVBoxLayout()
        
        self.history_text = QTextEdit()
        self.history_text.setReadOnly(True)
        self.history_text.setPlainText("No operations recorded yet.")
        history_layout.addWidget(self.history_text)
        
        # Clear history button
        clear_btn = QPushButton("Clear History")
        clear_btn.clicked.connect(self.clear_history)
        history_layout.addWidget(clear_btn)
        
        history_group.setLayout(history_layout)
        layout.addWidget(history_group)
        
        tab.setLayout(layout)
        self.tabs.addTab(tab, "History")
        
    def _setup_connections(self):
        """Setup signal connections"""
        self.metrics_collector.metrics_updated.connect(self.update_metrics)
        
    def start_monitoring(self):
        """Start performance monitoring"""
        self.start_monitor_btn.setEnabled(False)
        self.stop_monitor_btn.setEnabled(True)
        
        self.live_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Monitoring started")
        self.operation_label.setText("Status: Monitoring...")
        
        # Start metrics collector thread
        if not self.metrics_collector.isRunning():
            self.metrics_collector.start()
        
    def stop_monitoring(self):
        """Stop performance monitoring"""
        self.start_monitor_btn.setEnabled(True)
        self.stop_monitor_btn.setEnabled(False)
        
        self.live_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Monitoring stopped")
        self.operation_label.setText("Status: Idle")
        
        # Stop metrics collector
        self.metrics_collector.stop()
        
        # Save current metrics to history if available
        if self.current_metrics:
            self.operation_history.append(self.current_metrics)
            self.update_history()
    
    def set_metrics_source(self, metrics: PerformanceMetrics):
        """Set the metrics object to monitor"""
        self.current_metrics = metrics
        self.metrics_collector.set_metrics(metrics)
        
        # Auto-start monitoring when metrics are set
        if not self.metrics_collector.isRunning():
            self.start_monitoring()
    
    @Slot(PerformanceMetrics)
    def update_metrics(self, metrics: PerformanceMetrics):
        """Update UI with latest metrics"""
        # Update operation info
        self.files_label.setText(f"{metrics.files_processed} / {metrics.total_files}")
        
        # Update folders info if available
        if hasattr(metrics, 'directories_created') and hasattr(metrics, 'total_directories'):
            self.folders_label.setText(f"{metrics.directories_created} / {metrics.total_directories}")
        else:
            self.folders_label.setText("N/A")
        
        # Update data info
        copied_mb = metrics.bytes_copied / (1024 * 1024)
        total_mb = metrics.total_bytes / (1024 * 1024)
        self.data_label.setText(f"{copied_mb:.1f} MB / {total_mb:.1f} MB")
        
        # Update buffer info
        buffer_kb = metrics.buffer_size_used / 1024
        self.buffer_label.setText(f"{buffer_kb:.0f} KB")
        
        # Update speed metrics
        self.current_speed_label.setText(f"{metrics.current_speed_mbps:.1f} MB/s")
        self.avg_speed_label.setText(f"{metrics.average_speed_mbps:.1f} MB/s")
        self.peak_speed_label.setText(f"{metrics.peak_speed_mbps:.1f} MB/s")
        
        # Update progress bar
        if metrics.total_bytes > 0:
            progress = int((metrics.bytes_copied / metrics.total_bytes) * 100)
            self.progress_bar.setValue(progress)
        
        # Update file distribution
        self.small_files_label.setText(str(metrics.small_files_count))
        self.medium_files_label.setText(str(metrics.medium_files_count))
        self.large_files_label.setText(str(metrics.large_files_count))
        
        # Add speed sample to log (throttled)
        if hasattr(self, '_last_log_time'):
            if time.time() - self._last_log_time < 1.0:
                return
        self._last_log_time = time.time()
        
        if metrics.current_speed_mbps > 0:
            log_msg = f"[{datetime.now().strftime('%H:%M:%S')}] "
            log_msg += f"Speed: {metrics.current_speed_mbps:.1f} MB/s | "
            log_msg += f"Files: {metrics.files_processed}/{metrics.total_files}"
            # Add directory info if available
            if hasattr(metrics, 'total_directories') and metrics.total_directories > 0:
                log_msg += f" | Folders: {metrics.directories_created}/{metrics.total_directories}"
            self.live_log.append(log_msg)
            
            # Auto-scroll to bottom
            cursor = self.live_log.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.live_log.setTextCursor(cursor)
    
    def update_history(self):
        """Update history tab with completed operations"""
        if not self.operation_history:
            return
        
        history_text = "=== Operation History ===\n\n"
        
        for idx, metrics in enumerate(self.operation_history, 1):
            duration = metrics.end_time - metrics.start_time if metrics.end_time > 0 else 0
            history_text += f"Operation #{idx}\n"
            history_text += f"  Type: {metrics.operation_type}\n"
            history_text += f"  Files: {metrics.files_processed}/{metrics.total_files}\n"
            history_text += f"  Data: {metrics.bytes_copied/(1024*1024):.1f} MB\n"
            history_text += f"  Duration: {duration:.1f} seconds\n"
            history_text += f"  Avg Speed: {metrics.average_speed_mbps:.1f} MB/s\n"
            history_text += f"  Peak Speed: {metrics.peak_speed_mbps:.1f} MB/s\n"
            if metrics.errors:
                history_text += f"  Errors: {len(metrics.errors)}\n"
            history_text += "\n"
        
        self.history_text.setPlainText(history_text)
    
    def clear_history(self):
        """Clear operation history"""
        self.operation_history.clear()
        self.history_text.setPlainText("No operations recorded yet.")
        self.live_log.clear()
    
    def generate_report(self):
        """Generate performance report"""
        if not self.current_metrics and not self.operation_history:
            QMessageBox.information(self, "No Data", 
                                  "No performance data available to generate report.")
            return
        
        # Ask user where to save report
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Performance Report", 
            f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt);;All Files (*.*)"
        )
        
        if not file_path:
            return
        
        # Generate report content
        report = self._generate_report_content()
        
        # Save report
        try:
            Path(file_path).write_text(report)
            QMessageBox.information(self, "Report Saved", 
                                  f"Performance report saved to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", 
                               f"Failed to save report:\n{str(e)}")
    
    def _generate_report_content(self) -> str:
        """Generate detailed performance report content"""
        report = "=" * 60 + "\n"
        report += "PERFORMANCE REPORT\n"
        report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += "=" * 60 + "\n\n"
        
        # System configuration
        report += "CONFIGURATION\n"
        report += "-" * 40 + "\n"
        report += f"Buffered Operations: {'Enabled' if self.settings.use_buffered_operations else 'Disabled'}\n"
        report += f"Buffer Size: {self.settings.copy_buffer_size // 1024} KB\n"
        report += f"Hash Calculation: {'Enabled' if self.settings.calculate_hashes else 'Disabled'}\n"
        report += "\n"
        
        # Current operation (if active)
        if self.current_metrics:
            report += "CURRENT OPERATION\n"
            report += "-" * 40 + "\n"
            report += self._format_metrics(self.current_metrics)
            report += "\n"
        
        # Historical operations
        if self.operation_history:
            report += "OPERATION HISTORY\n"
            report += "-" * 40 + "\n"
            for idx, metrics in enumerate(self.operation_history, 1):
                report += f"\nOperation #{idx}:\n"
                report += self._format_metrics(metrics)
            report += "\n"
        
        # Performance summary
        if self.operation_history:
            report += "PERFORMANCE SUMMARY\n"
            report += "-" * 40 + "\n"
            
            total_bytes = sum(m.bytes_copied for m in self.operation_history)
            total_files = sum(m.files_processed for m in self.operation_history)
            avg_speed = sum(m.average_speed_mbps for m in self.operation_history) / len(self.operation_history)
            peak_speed = max(m.peak_speed_mbps for m in self.operation_history)
            
            report += f"Total Files Processed: {total_files}\n"
            report += f"Total Data Transferred: {total_bytes/(1024*1024):.1f} MB\n"
            report += f"Average Speed: {avg_speed:.1f} MB/s\n"
            report += f"Peak Speed: {peak_speed:.1f} MB/s\n"
        
        report += "\n" + "=" * 60 + "\n"
        report += "END OF REPORT\n"
        
        return report
    
    def _format_metrics(self, metrics: PerformanceMetrics) -> str:
        """Format metrics for report"""
        duration = metrics.end_time - metrics.start_time if metrics.end_time > 0 else 0
        
        text = f"  Operation Type: {metrics.operation_type}\n"
        text += f"  Files: {metrics.files_processed}/{metrics.total_files}\n"
        text += f"  Data Transferred: {metrics.bytes_copied/(1024*1024):.1f} MB\n"
        text += f"  Duration: {duration:.1f} seconds\n"
        text += f"  Buffer Size: {metrics.buffer_size_used/1024:.0f} KB\n"
        text += f"  Average Speed: {metrics.average_speed_mbps:.1f} MB/s\n"
        text += f"  Peak Speed: {metrics.peak_speed_mbps:.1f} MB/s\n"
        text += f"  File Distribution:\n"
        text += f"    Small (<1MB): {metrics.small_files_count}\n"
        text += f"    Medium (1-100MB): {metrics.medium_files_count}\n"
        text += f"    Large (>100MB): {metrics.large_files_count}\n"
        
        if metrics.errors:
            text += f"  Errors: {len(metrics.errors)}\n"
            for error in metrics.errors[:5]:  # Show first 5 errors
                text += f"    - {error}\n"
        
        return text
    
    def closeEvent(self, event):
        """Handle dialog close"""
        # Stop monitoring if active
        if self.metrics_collector.isRunning():
            self.metrics_collector.stop()
            self.metrics_collector.wait()
        
        event.accept()