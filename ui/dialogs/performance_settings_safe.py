#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Performance Settings Dialog - Configure optimization settings with safe defaults
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QCheckBox, QRadioButton,
    QTabWidget, QWidget, QTextEdit, QProgressBar,
    QFormLayout, QSpinBox, QComboBox, QButtonGroup,
    QFrame, QScrollArea
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
    """Dialog for configuring performance optimization settings with user-friendly controls"""
    
    settings_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Performance Settings")
        self.setModal(True)
        self.resize(700, 600)
        
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
        scroll = QScrollArea()
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Master Control
        master_group = QGroupBox("🎛️ Performance System Control")
        master_layout = QVBoxLayout()
        
        self.enable_adaptive = QCheckBox("Enable Advanced Performance System")
        self.enable_adaptive.setToolTip(
            "Master switch for all performance optimizations.\n"
            "RECOMMENDED: Leave OFF unless you need maximum performance\n"
            "and are willing to accept potential compatibility issues."
        )
        self.enable_adaptive.setChecked(False)  # Default OFF for safety
        master_layout.addWidget(self.enable_adaptive)
        
        # Safety warning
        warning_frame = QFrame()
        warning_frame.setFrameStyle(QFrame.Box)
        warning_frame.setStyleSheet("background-color: #fff3cd; border: 1px solid #856404; border-radius: 4px; padding: 8px;")
        warning_layout = QVBoxLayout(warning_frame)
        warning_label = QLabel("⚠️ CAUTION: Advanced optimizations may cause issues on some systems!")
        warning_label.setWordWrap(True)
        warning_label.setStyleSheet("color: #856404; font-weight: bold;")
        warning_layout.addWidget(warning_label)
        
        safety_label = QLabel("Most users should keep these settings OFF. Only enable if you:\n"
                             "• Need maximum performance for large file operations\n"
                             "• Are comfortable troubleshooting potential issues\n"
                             "• Have tested the features on your specific hardware")
        safety_label.setWordWrap(True)
        safety_label.setStyleSheet("color: #856404;")
        warning_layout.addWidget(safety_label)
        master_layout.addWidget(warning_frame)
        
        master_group.setLayout(master_layout)
        layout.addWidget(master_group)
        
        # Safe Features (always available)
        safe_group = QGroupBox("✅ Safe Performance Features")
        safe_layout = QVBoxLayout()
        
        self.enable_parallel = QCheckBox("Parallel File Processing (Recommended)")
        self.enable_parallel.setToolTip("Process multiple files simultaneously - generally safe and provides significant speedup")
        self.enable_parallel.setChecked(True)  # This one is generally safe
        safe_layout.addWidget(self.enable_parallel)
        
        self.max_workers_safe = QSpinBox()
        self.max_workers_safe.setRange(1, 16)
        self.max_workers_safe.setValue(4)
        self.max_workers_safe.setToolTip("Number of parallel operations (4 is safe for most systems)")
        safe_worker_layout = QHBoxLayout()
        safe_worker_layout.addWidget(QLabel("Max Parallel Operations:"))
        safe_worker_layout.addWidget(self.max_workers_safe)
        safe_worker_layout.addStretch()
        safe_layout.addLayout(safe_worker_layout)
        
        safe_group.setLayout(safe_layout)
        layout.addWidget(safe_group)
        
        # Advanced Features (potentially risky)
        advanced_group = QGroupBox("⚡ Advanced Features (Use with caution)")
        advanced_layout = QVBoxLayout()
        
        self.enable_hardware_detection = QCheckBox("Hardware Detection & Optimization")
        self.enable_hardware_detection.setToolTip("Automatically detect SSD/HDD and adjust parallelism")
        self.enable_hardware_detection.setChecked(False)
        advanced_layout.addWidget(self.enable_hardware_detection)
        
        self.enable_thermal = QCheckBox("CPU Thermal Monitoring")
        self.enable_thermal.setToolTip("Monitor CPU temperature and reduce performance when overheating")
        self.enable_thermal.setChecked(False)
        advanced_layout.addWidget(self.enable_thermal)
        
        self.enable_numa = QCheckBox("NUMA Optimization (Servers only)")
        self.enable_numa.setToolTip("Optimize for multi-socket systems (most users should leave OFF)")
        self.enable_numa.setChecked(False)
        advanced_layout.addWidget(self.enable_numa)
        
        self.enable_learning = QCheckBox("Performance Learning System")
        self.enable_learning.setToolTip("Learn from past operations to improve future performance")
        self.enable_learning.setChecked(False)
        advanced_layout.addWidget(self.enable_learning)
        
        self.enable_direct_io = QCheckBox("Direct I/O for Large Files (Linux only)")
        self.enable_direct_io.setToolTip("Bypass system cache for files >100MB (experimental)")
        self.enable_direct_io.setChecked(False)
        if platform.system() != 'Linux':
            self.enable_direct_io.setEnabled(False)
        advanced_layout.addWidget(self.enable_direct_io)
        
        advanced_group.setLayout(advanced_layout)
        layout.addWidget(advanced_group)
        
        # Optimization Priority
        priority_group = QGroupBox("🎯 Optimization Priority")
        priority_layout = QVBoxLayout()
        
        self.priority_group = QButtonGroup()
        
        self.priority_balanced = QRadioButton("Balanced (Recommended)")
        self.priority_balanced.setToolTip("Automatically choose based on file characteristics")
        self.priority_balanced.setChecked(True)
        self.priority_group.addButton(self.priority_balanced, 0)
        priority_layout.addWidget(self.priority_balanced)
        
        self.priority_latency = QRadioButton("Low Latency (Quick Response)")
        self.priority_latency.setToolTip("Minimize response time - best for interactive use")
        self.priority_group.addButton(self.priority_latency, 1)
        priority_layout.addWidget(self.priority_latency)
        
        self.priority_throughput = QRadioButton("High Throughput (Maximum Speed)")
        self.priority_throughput.setToolTip("Maximize total processing speed - best for large batches")
        self.priority_group.addButton(self.priority_throughput, 2)
        priority_layout.addWidget(self.priority_throughput)
        
        priority_group.setLayout(priority_layout)
        layout.addWidget(priority_group)
        
        layout.addStretch()
        scroll.setWidget(widget)
        scroll.setWidgetResizable(True)
        return scroll
        
    def create_advanced_tab(self):
        """Create the advanced settings tab"""
        scroll = QScrollArea()
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Worker Limits
        worker_group = QGroupBox("🔧 Worker Thread Limits")
        worker_layout = QFormLayout()
        
        self.max_workers = QSpinBox()
        self.max_workers.setRange(1, 64)
        self.max_workers.setValue(16)
        self.max_workers.setToolTip("Maximum number of parallel operations (advanced users only)")
        worker_layout.addRow("Maximum Workers:", self.max_workers)
        
        self.max_workers_hdd = QSpinBox()
        self.max_workers_hdd.setRange(1, 8)
        self.max_workers_hdd.setValue(2)
        self.max_workers_hdd.setToolTip("Maximum workers for HDD operations (prevent seek thrashing)")
        worker_layout.addRow("HDD Worker Limit:", self.max_workers_hdd)
        
        worker_group.setLayout(worker_layout)
        layout.addWidget(worker_group)
        
        # Thermal Management
        thermal_group = QGroupBox("🌡️ Thermal Management")
        thermal_layout = QFormLayout()
        
        self.thermal_threshold = QSpinBox()
        self.thermal_threshold.setRange(60, 100)
        self.thermal_threshold.setValue(80)
        self.thermal_threshold.setSuffix("°C")
        self.thermal_threshold.setToolTip("Temperature threshold for performance throttling")
        thermal_layout.addRow("Throttle Temperature:", self.thermal_threshold)
        
        thermal_group.setLayout(thermal_layout)
        layout.addWidget(thermal_group)
        
        # Buffer Sizes
        buffer_group = QGroupBox("💾 Buffer Sizes")
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
        
        # Reset to Safe Defaults
        reset_group = QGroupBox("🔄 Reset Options")
        reset_layout = QVBoxLayout()
        
        reset_safe_btn = QPushButton("Reset to Safe Defaults")
        reset_safe_btn.setToolTip("Reset all settings to safe, conservative values")
        reset_safe_btn.clicked.connect(self.reset_to_safe_defaults)
        reset_layout.addWidget(reset_safe_btn)
        
        reset_performance_btn = QPushButton("Reset to Maximum Performance")
        reset_performance_btn.setToolTip("Enable all optimizations for maximum speed (risky)")
        reset_performance_btn.clicked.connect(self.reset_to_max_performance)
        reset_layout.addWidget(reset_performance_btn)
        
        reset_group.setLayout(reset_layout)
        layout.addWidget(reset_group)
        
        layout.addStretch()
        scroll.setWidget(widget)
        scroll.setWidgetResizable(True)
        return scroll
        
    def create_monitoring_tab(self):
        """Create the performance monitoring tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # System Info
        info_group = QGroupBox("💻 System Information")
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
        
        # Performance System Status
        status_text = "Available" if PERFORMANCE_AVAILABLE else "Not Available (missing dependencies)"
        status_label = QLabel(status_text)
        status_label.setStyleSheet("color: green;" if PERFORMANCE_AVAILABLE else "color: red;")
        info_layout.addRow("Performance System:", status_label)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Real-time Stats
        stats_group = QGroupBox("📊 Real-time Performance")
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
        
        # Current Mode
        self.mode_label = QLabel("Standard Mode")
        stats_layout.addRow("Current Mode:", self.mode_label)
        
        # Copy Speed (when active)
        self.copy_speed_label = QLabel("Idle")
        self.copy_speed_label.setStyleSheet("font-weight: bold;")
        stats_layout.addRow("Copy Speed:", self.copy_speed_label)
        
        # Additional copy stats
        self.files_progress_label = QLabel("No operation")
        stats_layout.addRow("Progress:", self.files_progress_label)
        
        self.data_transferred_label = QLabel("0 MB")
        stats_layout.addRow("Data Transferred:", self.data_transferred_label)
        
        self.eta_label = QLabel("N/A")
        stats_layout.addRow("Time Remaining:", self.eta_label)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # Performance Log
        log_group = QGroupBox("📝 Performance Log")
        log_layout = QVBoxLayout()
        
        self.perf_log = QTextEdit()
        self.perf_log.setReadOnly(True)
        self.perf_log.setMaximumHeight(150)
        self.perf_log.append("[System] Performance monitoring started")
        log_layout.addWidget(self.perf_log)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        layout.addStretch()
        return widget
        
    def reset_to_safe_defaults(self):
        """Reset all settings to safe, conservative values"""
        self.enable_adaptive.setChecked(False)
        self.enable_parallel.setChecked(True)
        self.max_workers_safe.setValue(4)
        self.enable_hardware_detection.setChecked(False)
        self.enable_thermal.setChecked(False)
        self.enable_numa.setChecked(False)
        self.enable_learning.setChecked(False)
        self.enable_direct_io.setChecked(False)
        self.priority_balanced.setChecked(True)
        self.max_workers.setValue(8)
        self.max_workers_hdd.setValue(2)
        self.thermal_threshold.setValue(80)
        self.buffer_size.setCurrentIndex(0)  # Auto
        self.log_performance("Settings reset to safe defaults")
        
    def reset_to_max_performance(self):
        """Reset to maximum performance settings (potentially risky)"""
        self.enable_adaptive.setChecked(True)
        self.enable_parallel.setChecked(True)
        self.max_workers_safe.setValue(8)
        self.enable_hardware_detection.setChecked(True)
        self.enable_thermal.setChecked(True)
        self.enable_numa.setChecked(True)
        self.enable_learning.setChecked(True)
        if platform.system() == 'Linux':
            self.enable_direct_io.setChecked(True)
        self.priority_throughput.setChecked(True)
        self.max_workers.setValue(32)
        self.max_workers_hdd.setValue(2)
        self.thermal_threshold.setValue(85)
        self.buffer_size.setCurrentIndex(0)  # Auto
        self.log_performance("Settings configured for maximum performance")
        
    def load_settings(self):
        """Load settings from QSettings"""
        # General settings
        self.enable_adaptive.setChecked(
            self.settings.value("performance/adaptive_enabled", False, type=bool)
        )
        
        self.enable_parallel.setChecked(
            self.settings.value("performance/parallel_enabled", True, type=bool)
        )
        
        self.max_workers_safe.setValue(
            self.settings.value("performance/max_workers_safe", 4, type=int)
        )
        
        self.enable_hardware_detection.setChecked(
            self.settings.value("performance/hardware_detection", False, type=bool)
        )
        
        self.enable_thermal.setChecked(
            self.settings.value("performance/thermal_enabled", False, type=bool)
        )
        
        self.enable_numa.setChecked(
            self.settings.value("performance/numa_enabled", False, type=bool)
        )
        
        self.enable_learning.setChecked(
            self.settings.value("performance/learning_enabled", False, type=bool)
        )
        
        self.enable_direct_io.setChecked(
            self.settings.value("performance/direct_io_enabled", False, type=bool)
        )
        
        priority = self.settings.value("performance/priority", "balanced")
        if priority == "latency":
            self.priority_latency.setChecked(True)
        elif priority == "throughput":
            self.priority_throughput.setChecked(True)
        else:
            self.priority_balanced.setChecked(True)
            
        # Advanced settings
        self.max_workers.setValue(
            self.settings.value("performance/max_workers", 16, type=int)
        )
        
        self.max_workers_hdd.setValue(
            self.settings.value("performance/max_workers_hdd", 2, type=int)
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
        self.settings.setValue("performance/parallel_enabled", self.enable_parallel.isChecked())
        self.settings.setValue("performance/max_workers_safe", self.max_workers_safe.value())
        self.settings.setValue("performance/hardware_detection", self.enable_hardware_detection.isChecked())
        self.settings.setValue("performance/thermal_enabled", self.enable_thermal.isChecked())
        self.settings.setValue("performance/numa_enabled", self.enable_numa.isChecked())
        self.settings.setValue("performance/learning_enabled", self.enable_learning.isChecked())
        self.settings.setValue("performance/direct_io_enabled", self.enable_direct_io.isChecked())
        
        if self.priority_latency.isChecked():
            priority = "latency"
        elif self.priority_throughput.isChecked():
            priority = "throughput"
        else:
            priority = "balanced"
        self.settings.setValue("performance/priority", priority)
        
        # Save advanced settings
        self.settings.setValue("performance/max_workers", self.max_workers.value())
        self.settings.setValue("performance/max_workers_hdd", self.max_workers_hdd.value())
        self.settings.setValue("performance/thermal_threshold", self.thermal_threshold.value())
        self.settings.setValue("performance/buffer_size_index", self.buffer_size.currentIndex())
        
        self.settings_changed.emit()
        
        # Log the change
        mode = "Adaptive" if self.enable_adaptive.isChecked() else "Standard"
        self.log_performance(f"Settings applied - Mode: {mode}")
        
        # Update mode indicator
        if hasattr(self, 'mode_label'):
            self.mode_label.setText(f"{mode} Mode")
        
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
            
            # Color coding
            if cpu_percent > 80:
                self.cpu_label.setStyleSheet("color: red; font-weight: bold;")
            elif cpu_percent > 60:
                self.cpu_label.setStyleSheet("color: orange; font-weight: bold;")
            else:
                self.cpu_label.setStyleSheet("color: green;")
            
            # Memory Usage
            memory = psutil.virtual_memory()
            self.memory_label.setText(f"{memory.percent:.1f}%")
            
            if memory.percent > 85:
                self.memory_label.setStyleSheet("color: red; font-weight: bold;")
            elif memory.percent > 70:
                self.memory_label.setStyleSheet("color: orange; font-weight: bold;")
            else:
                self.memory_label.setStyleSheet("color: green;")
            
            # Temperature (if available)
            if self.performance_controller:
                try:
                    thermal_status = self.performance_controller.thermal.get_thermal_status()
                    temp = thermal_status.get('current_temp', 0)
                    if temp > 0:
                        self.temp_label.setText(f"{temp:.1f}°C")
                        if temp > 85:
                            self.temp_label.setStyleSheet("color: red; font-weight: bold;")
                        elif temp > 75:
                            self.temp_label.setStyleSheet("color: orange; font-weight: bold;")
                        else:
                            self.temp_label.setStyleSheet("color: green;")
                    else:
                        self.temp_label.setText("N/A")
                        self.temp_label.setStyleSheet("")
                except:
                    self.temp_label.setText("N/A")
                    self.temp_label.setStyleSheet("")
            
            # Update copy operation stats from main window
            if self.parent() and hasattr(self.parent(), 'operation_active'):
                main_window = self.parent()
                
                if main_window.operation_active:
                    # Copy speed
                    if main_window.current_copy_speed > 0:
                        speed_text = f"{main_window.current_copy_speed:.1f} MB/s"
                        self.copy_speed_label.setText(speed_text)
                        
                        # Color code based on speed
                        if main_window.current_copy_speed > 100:
                            self.copy_speed_label.setStyleSheet("color: green; font-weight: bold;")
                        elif main_window.current_copy_speed > 50:
                            self.copy_speed_label.setStyleSheet("color: orange; font-weight: bold;")
                        else:
                            self.copy_speed_label.setStyleSheet("color: blue; font-weight: bold;")
                    else:
                        self.copy_speed_label.setText("Starting...")
                        self.copy_speed_label.setStyleSheet("font-weight: bold;")
                    
                    # Get latest status message for detailed info
                    status_text = main_window.status_bar.currentMessage()
                    if status_text:
                        # Extract progress info
                        if "(" in status_text and "/" in status_text:
                            try:
                                # Extract file progress (e.g., "(5/12)")
                                progress_match = status_text.split("(")[1].split(")")[0]
                                if "/" in progress_match:
                                    self.files_progress_label.setText(progress_match + " files")
                            except:
                                pass
                        
                        # Extract data transferred (e.g., "(45.2/120.5 MB)")
                        if "MB)" in status_text:
                            try:
                                mb_part = status_text.split("(")[2].split("MB)")[0]
                                self.data_transferred_label.setText(mb_part + " MB")
                            except:
                                pass
                        
                        # Extract ETA (e.g., "(ETA: 2.1m)")
                        if "ETA:" in status_text:
                            try:
                                eta_part = status_text.split("ETA:")[1].split(")")[0].strip()
                                self.eta_label.setText(eta_part)
                            except:
                                pass
                else:
                    # No active operation
                    self.copy_speed_label.setText("Idle")
                    self.copy_speed_label.setStyleSheet("font-weight: bold;")
                    self.files_progress_label.setText("No operation")
                    self.data_transferred_label.setText("0 MB")
                    self.eta_label.setText("N/A")
                    
        except Exception as e:
            self.log_performance(f"Error updating stats: {e}")
            
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