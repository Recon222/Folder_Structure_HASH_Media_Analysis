#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Performance Settings Dialog - Configure optimization settings
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QCheckBox, QRadioButton,
    QTabWidget, QWidget, QTextEdit, QProgressBar,
    QFormLayout, QSpinBox, QComboBox, QButtonGroup
)
from PySide6.QtCore import Qt, QSettings, Signal, QTimer
from PySide6.QtGui import QFont

import psutil
import platform
from pathlib import Path

# Try to import performance modules
try:
    from core.adaptive_performance import AdaptivePerformanceController, WorkloadPriority
    PERFORMANCE_AVAILABLE = True
except ImportError:
    PERFORMANCE_AVAILABLE = False


class PerformanceSettingsDialog(QDialog):
    """Dialog for configuring performance optimization settings"""
    
    settings_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Performance Settings")
        self.setModal(True)
        self.resize(600, 500)
        
        self.settings = QSettings()
        self.performance_controller = None
        
        if PERFORMANCE_AVAILABLE:
            try:
                self.performance_controller = AdaptivePerformanceController()
            except:
                pass
        
        self.setup_ui()
        self.load_settings()
        
        # Start performance monitoring
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self.update_performance_stats)
        self.monitor_timer.start(1000)  # Update every second
        
    def setup_ui(self):
        """Set up the user interface"""
        layout = QVBoxLayout(self)
        
        # Create tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Add tabs
        self.tabs.addTab(self.create_general_tab(), "General")
        self.tabs.addTab(self.create_advanced_tab(), "Advanced")
        self.tabs.addTab(self.create_monitoring_tab(), "Monitoring")
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self.apply_settings)
        button_layout.addWidget(self.apply_button)
        
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setDefault(True)
        button_layout.addWidget(self.ok_button)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
    def create_general_tab(self):
        """Create the general settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Adaptive Optimization
        adaptive_group = QGroupBox("Adaptive Optimization")
        adaptive_layout = QVBoxLayout()
        
        self.enable_adaptive = QCheckBox("Enable adaptive performance optimization")
        self.enable_adaptive.setToolTip(
            "Automatically optimize file operations based on hardware and workload"
        )
        adaptive_layout.addWidget(self.enable_adaptive)
        
        # Optimization Priority
        priority_label = QLabel("Optimization Priority:")
        adaptive_layout.addWidget(priority_label)
        
        self.priority_group = QButtonGroup()
        
        self.priority_latency = QRadioButton("Low Latency (Quick Response)")
        self.priority_latency.setToolTip(
            "Minimize response time - best for interactive use with small files"
        )
        self.priority_group.addButton(self.priority_latency, 0)
        adaptive_layout.addWidget(self.priority_latency)
        
        self.priority_throughput = QRadioButton("High Throughput (Maximum Speed)")
        self.priority_throughput.setToolTip(
            "Maximize total processing speed - best for large batch operations"
        )
        self.priority_group.addButton(self.priority_throughput, 1)
        adaptive_layout.addWidget(self.priority_throughput)
        
        self.priority_balanced = QRadioButton("Balanced (Auto-Adapt)")
        self.priority_balanced.setToolTip(
            "Automatically choose based on file characteristics"
        )
        self.priority_balanced.setChecked(True)
        self.priority_group.addButton(self.priority_balanced, 2)
        adaptive_layout.addWidget(self.priority_balanced)
        
        adaptive_group.setLayout(adaptive_layout)
        layout.addWidget(adaptive_group)
        
        # Hardware Acceleration
        hardware_group = QGroupBox("Hardware Acceleration")
        hardware_layout = QVBoxLayout()
        
        self.enable_hashwise = QCheckBox("Use HashWise for accelerated hashing")
        self.enable_hashwise.setToolTip(
            "Enable multi-threaded hash calculation (requires HashWise package)"
        )
        hardware_layout.addWidget(self.enable_hashwise)
        
        self.enable_direct_io = QCheckBox("Use Direct I/O for large files (Linux)")
        self.enable_direct_io.setToolTip(
            "Bypass system cache for files larger than 100MB"
        )
        if platform.system() != 'Linux':
            self.enable_direct_io.setEnabled(False)
        hardware_layout.addWidget(self.enable_direct_io)
        
        hardware_group.setLayout(hardware_layout)
        layout.addWidget(hardware_group)
        
        layout.addStretch()
        return widget
        
    def create_advanced_tab(self):
        """Create the advanced settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Worker Limits
        worker_group = QGroupBox("Worker Thread Limits")
        worker_layout = QFormLayout()
        
        self.max_workers = QSpinBox()
        self.max_workers.setRange(1, 64)
        self.max_workers.setValue(16)
        self.max_workers.setToolTip("Maximum number of parallel operations")
        worker_layout.addRow("Maximum Workers:", self.max_workers)
        
        self.max_workers_hdd = QSpinBox()
        self.max_workers_hdd.setRange(1, 8)
        self.max_workers_hdd.setValue(2)
        self.max_workers_hdd.setToolTip("Maximum workers for HDD operations")
        worker_layout.addRow("HDD Worker Limit:", self.max_workers_hdd)
        
        worker_group.setLayout(worker_layout)
        layout.addWidget(worker_group)
        
        # Thermal Management
        thermal_group = QGroupBox("Thermal Management")
        thermal_layout = QFormLayout()
        
        self.enable_thermal = QCheckBox("Enable thermal throttling")
        self.enable_thermal.setChecked(True)
        self.enable_thermal.setToolTip("Reduce performance when CPU temperature is high")
        thermal_layout.addRow(self.enable_thermal)
        
        self.thermal_threshold = QSpinBox()
        self.thermal_threshold.setRange(60, 100)
        self.thermal_threshold.setValue(80)
        self.thermal_threshold.setSuffix("°C")
        self.thermal_threshold.setToolTip("Temperature threshold for throttling")
        thermal_layout.addRow("Throttle Temperature:", self.thermal_threshold)
        
        thermal_group.setLayout(thermal_layout)
        layout.addWidget(thermal_group)
        
        # Buffer Sizes
        buffer_group = QGroupBox("Buffer Sizes")
        buffer_layout = QFormLayout()
        
        self.buffer_size = QComboBox()
        self.buffer_size.addItems([
            "Auto (Recommended)",
            "64 KB (Small files)",
            "256 KB",
            "1 MB",
            "4 MB",
            "16 MB (Large files)"
        ])
        self.buffer_size.setToolTip("I/O buffer size for file operations")
        buffer_layout.addRow("Buffer Size:", self.buffer_size)
        
        buffer_group.setLayout(buffer_layout)
        layout.addWidget(buffer_group)
        
        layout.addStretch()
        return widget
        
    def create_monitoring_tab(self):
        """Create the performance monitoring tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # System Info
        info_group = QGroupBox("System Information")
        info_layout = QFormLayout()
        
        # CPU Info
        cpu_count = psutil.cpu_count(logical=True)
        cpu_physical = psutil.cpu_count(logical=False)
        info_layout.addRow("CPU Cores:", QLabel(f"{cpu_physical} physical, {cpu_count} logical"))
        
        # Memory Info
        memory = psutil.virtual_memory()
        info_layout.addRow("Total Memory:", QLabel(f"{memory.total // (1024**3)} GB"))
        
        # Platform
        info_layout.addRow("Platform:", QLabel(platform.system()))
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Real-time Stats
        stats_group = QGroupBox("Real-time Performance")
        stats_layout = QFormLayout()
        
        # CPU Usage
        self.cpu_label = QLabel("0%")
        stats_layout.addRow("CPU Usage:", self.cpu_label)
        
        # Memory Usage
        self.memory_label = QLabel("0%")
        stats_layout.addRow("Memory Usage:", self.memory_label)
        
        # Temperature
        self.temp_label = QLabel("N/A")
        stats_layout.addRow("CPU Temperature:", self.temp_label)
        
        # Disk I/O
        self.disk_label = QLabel("N/A")
        stats_layout.addRow("Disk Activity:", self.disk_label)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # Performance Log
        log_group = QGroupBox("Performance Log")
        log_layout = QVBoxLayout()
        
        self.perf_log = QTextEdit()
        self.perf_log.setReadOnly(True)
        self.perf_log.setMaximumHeight(150)
        log_layout.addWidget(self.perf_log)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        layout.addStretch()
        return widget
        
    def load_settings(self):
        """Load settings from QSettings"""
        # General settings
        self.enable_adaptive.setChecked(
            self.settings.value("performance/adaptive_enabled", True, type=bool)
        )
        
        priority = self.settings.value("performance/priority", "balanced")
        if priority == "latency":
            self.priority_latency.setChecked(True)
        elif priority == "throughput":
            self.priority_throughput.setChecked(True)
        else:
            self.priority_balanced.setChecked(True)
            
        self.enable_hashwise.setChecked(
            self.settings.value("performance/hashwise_enabled", False, type=bool)
        )
        
        self.enable_direct_io.setChecked(
            self.settings.value("performance/direct_io_enabled", False, type=bool)
        )
        
        # Advanced settings
        self.max_workers.setValue(
            self.settings.value("performance/max_workers", 16, type=int)
        )
        
        self.max_workers_hdd.setValue(
            self.settings.value("performance/max_workers_hdd", 2, type=int)
        )
        
        self.enable_thermal.setChecked(
            self.settings.value("performance/thermal_enabled", True, type=bool)
        )
        
        self.thermal_threshold.setValue(
            self.settings.value("performance/thermal_threshold", 80, type=int)
        )
        
        buffer_index = self.settings.value("performance/buffer_size_index", 0, type=int)
        self.buffer_size.setCurrentIndex(buffer_index)
        
    def apply_settings(self):
        """Apply settings without closing dialog"""
        # Save general settings
        self.settings.setValue("performance/adaptive_enabled", self.enable_adaptive.isChecked())
        
        if self.priority_latency.isChecked():
            priority = "latency"
        elif self.priority_throughput.isChecked():
            priority = "throughput"
        else:
            priority = "balanced"
        self.settings.setValue("performance/priority", priority)
        
        self.settings.setValue("performance/hashwise_enabled", self.enable_hashwise.isChecked())
        self.settings.setValue("performance/direct_io_enabled", self.enable_direct_io.isChecked())
        
        # Save advanced settings
        self.settings.setValue("performance/max_workers", self.max_workers.value())
        self.settings.setValue("performance/max_workers_hdd", self.max_workers_hdd.value())
        self.settings.setValue("performance/thermal_enabled", self.enable_thermal.isChecked())
        self.settings.setValue("performance/thermal_threshold", self.thermal_threshold.value())
        self.settings.setValue("performance/buffer_size_index", self.buffer_size.currentIndex())
        
        self.settings_changed.emit()
        
        # Log the change
        self.log_performance("Settings updated")
        
    def accept(self):
        """Accept dialog and save settings"""
        self.apply_settings()
        super().accept()
        
    def update_performance_stats(self):
        """Update real-time performance statistics"""
        try:
            # CPU Usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            self.cpu_label.setText(f"{cpu_percent:.1f}%")
            
            # Memory Usage
            memory = psutil.virtual_memory()
            self.memory_label.setText(f"{memory.percent:.1f}%")
            
            # Temperature (if available)
            if self.performance_controller:
                thermal_status = self.performance_controller.thermal.get_thermal_status()
                temp = thermal_status.get('current_temp', 0)
                if temp > 0:
                    self.temp_label.setText(f"{temp:.1f}°C")
                    
            # Disk I/O
            disk_io = psutil.disk_io_counters()
            if disk_io:
                read_mb = disk_io.read_bytes / (1024 * 1024)
                write_mb = disk_io.write_bytes / (1024 * 1024)
                self.disk_label.setText(f"R: {read_mb:.1f} MB/s, W: {write_mb:.1f} MB/s")
                
        except:
            pass
            
    def log_performance(self, message):
        """Add message to performance log"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.perf_log.append(f"[{timestamp}] {message}")
        
        # Keep log size limited
        if self.perf_log.document().blockCount() > 100:
            cursor = self.perf_log.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.select(cursor.BlockUnderCursor)
            cursor.removeSelectedText()