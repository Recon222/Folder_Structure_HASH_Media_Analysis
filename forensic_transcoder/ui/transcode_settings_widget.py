"""
Transcode settings widget.

Provides form UI for configuring all video transcoding parameters.
"""

from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit, QCheckBox,
    QPushButton, QLabel, QFileDialog
)
from PyQt6.QtCore import Qt

from ..models.transcode_settings import (
    TranscodeSettings,
    QualityPreset,
    FPSMethod,
    ScalingAlgorithm
)
from ..core import (
    get_all_video_codecs,
    get_all_audio_codecs,
    get_all_formats,
    get_hardware_codecs,
    get_software_codecs,
    get_available_presets,
    get_available_profiles,
    get_available_tune_options,
    PIXEL_FORMATS,
    get_all_preset_names,
    get_preset_description,
)


class TranscodeSettingsWidget(QWidget):
    """
    Widget for configuring transcode settings.
    
    Provides comprehensive form UI for all TranscodeSettings parameters
    organized into logical sections. Pure UI component with no business logic.
    """
    
    def __init__(self, parent=None):
        """
        Initialize transcode settings widget.
        
        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)
        self._init_ui()
        self._connect_signals()
        self._load_defaults()
    
    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # === Output Configuration ===
        output_group = self._create_output_group()
        layout.addWidget(output_group)
        
        # === Video Codec & Quality ===
        video_group = self._create_video_group()
        layout.addWidget(video_group)
        
        # === Resolution & Frame Rate ===
        resolution_group = self._create_resolution_group()
        layout.addWidget(resolution_group)
        
        # === Audio Settings ===
        audio_group = self._create_audio_group()
        layout.addWidget(audio_group)
        
        # === Advanced Options ===
        advanced_group = self._create_advanced_group()
        layout.addWidget(advanced_group)
        
        layout.addStretch()
    
    def _create_output_group(self) -> QGroupBox:
        """Create output configuration section."""
        group = QGroupBox("Output Configuration")
        layout = QFormLayout(group)
        
        # Output format
        self.format_combo = QComboBox()
        self.format_combo.addItems(get_all_formats())
        layout.addRow("Format:", self.format_combo)
        
        # Output directory
        output_dir_layout = QHBoxLayout()
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText("Same as input (leave blank)")
        output_dir_layout.addWidget(self.output_dir_edit)
        
        self.browse_dir_btn = QPushButton("Browse...")
        self.browse_dir_btn.clicked.connect(self._on_browse_output_dir)
        output_dir_layout.addWidget(self.browse_dir_btn)
        layout.addRow("Output Directory:", output_dir_layout)
        
        # Filename pattern
        self.filename_pattern_edit = QLineEdit("{original_name}_transcoded.{ext}")
        layout.addRow("Filename Pattern:", self.filename_pattern_edit)
        
        # Overwrite existing
        self.overwrite_check = QCheckBox("Overwrite existing files")
        layout.addRow("", self.overwrite_check)
        
        return group
    
    def _create_video_group(self) -> QGroupBox:
        """Create video codec and quality section."""
        group = QGroupBox("Video Codec & Quality")
        layout = QFormLayout(group)
        
        # Codec selection with hardware/software filter
        codec_layout = QHBoxLayout()
        self.codec_combo = QComboBox()
        codec_layout.addWidget(self.codec_combo, 1)
        
        self.hw_only_check = QCheckBox("Hardware only")
        self.hw_only_check.toggled.connect(self._on_codec_filter_changed)
        codec_layout.addWidget(self.hw_only_check)
        
        layout.addRow("Video Codec:", codec_layout)
        
        # Quality preset
        self.quality_preset_combo = QComboBox()
        for preset_name in get_all_preset_names():
            self.quality_preset_combo.addItem(preset_name)
        self.quality_preset_combo.addItem("custom")
        layout.addRow("Quality Preset:", self.quality_preset_combo)
        
        # Preset description label
        self.preset_description_label = QLabel()
        self.preset_description_label.setWordWrap(True)
        self.preset_description_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addRow("", self.preset_description_label)
        
        # CRF (Constant Rate Factor)
        self.crf_spin = QSpinBox()
        self.crf_spin.setRange(0, 51)
        self.crf_spin.setValue(18)
        self.crf_spin.setToolTip("0 = lossless, 51 = worst quality. 18-23 recommended.")
        layout.addRow("CRF:", self.crf_spin)
        
        # Encoding preset
        self.preset_combo = QComboBox()
        layout.addRow("Encoding Preset:", self.preset_combo)
        
        # Tune option
        self.tune_combo = QComboBox()
        self.tune_combo.addItem("(none)")
        layout.addRow("Tune:", self.tune_combo)
        
        # Profile
        self.profile_combo = QComboBox()
        self.profile_combo.addItem("(auto)")
        layout.addRow("Profile:", self.profile_combo)
        
        # Hardware acceleration
        self.hw_encoder_check = QCheckBox("Use hardware encoder")
        layout.addRow("", self.hw_encoder_check)
        
        self.hw_decoder_check = QCheckBox("Use hardware decoder")
        layout.addRow("", self.hw_decoder_check)
        
        return group
    
    def _create_resolution_group(self) -> QGroupBox:
        """Create resolution and frame rate section."""
        group = QGroupBox("Resolution & Frame Rate")
        layout = QFormLayout(group)
        
        # Resolution
        res_layout = QHBoxLayout()
        
        self.width_spin = QSpinBox()
        self.width_spin.setRange(0, 7680)
        self.width_spin.setValue(0)
        self.width_spin.setSpecialValueText("(source)")
        self.width_spin.setSuffix(" px")
        res_layout.addWidget(QLabel("Width:"))
        res_layout.addWidget(self.width_spin)
        
        res_layout.addWidget(QLabel("×"))
        
        self.height_spin = QSpinBox()
        self.height_spin.setRange(0, 4320)
        self.height_spin.setValue(0)
        self.height_spin.setSpecialValueText("(source)")
        self.height_spin.setSuffix(" px")
        res_layout.addWidget(QLabel("Height:"))
        res_layout.addWidget(self.height_spin)
        
        layout.addRow("Resolution:", res_layout)
        
        # Maintain aspect ratio
        self.maintain_aspect_check = QCheckBox("Maintain aspect ratio")
        self.maintain_aspect_check.setChecked(True)
        layout.addRow("", self.maintain_aspect_check)
        
        # Scaling algorithm
        self.scaling_algo_combo = QComboBox()
        for algo in ScalingAlgorithm:
            self.scaling_algo_combo.addItem(algo.value)
        self.scaling_algo_combo.setCurrentText("lanczos")
        layout.addRow("Scaling Algorithm:", self.scaling_algo_combo)
        
        # Frame rate
        fps_layout = QHBoxLayout()
        self.fps_spin = QDoubleSpinBox()
        self.fps_spin.setRange(0, 240)
        self.fps_spin.setValue(0)
        self.fps_spin.setSpecialValueText("(source)")
        self.fps_spin.setDecimals(3)
        self.fps_spin.setSuffix(" fps")
        fps_layout.addWidget(self.fps_spin)
        
        layout.addRow("Target FPS:", fps_layout)
        
        # FPS method
        self.fps_method_combo = QComboBox()
        for method in FPSMethod:
            self.fps_method_combo.addItem(method.value)
        self.fps_method_combo.setCurrentText("auto")
        layout.addRow("FPS Method:", self.fps_method_combo)
        
        # Analyze VFR
        self.analyze_vfr_check = QCheckBox("Analyze for variable frame rate")
        self.analyze_vfr_check.setChecked(True)
        layout.addRow("", self.analyze_vfr_check)
        
        # Deinterlace
        self.deinterlace_check = QCheckBox("Deinterlace")
        layout.addRow("", self.deinterlace_check)
        
        return group
    
    def _create_audio_group(self) -> QGroupBox:
        """Create audio settings section."""
        group = QGroupBox("Audio Settings")
        layout = QFormLayout(group)
        
        # Audio codec
        self.audio_codec_combo = QComboBox()
        self.audio_codec_combo.addItem("copy")
        self.audio_codec_combo.addItems(get_all_audio_codecs())
        layout.addRow("Audio Codec:", self.audio_codec_combo)
        
        # Audio bitrate
        self.audio_bitrate_combo = QComboBox()
        self.audio_bitrate_combo.addItems([
            "(auto)", "96k", "128k", "192k", "256k", "320k"
        ])
        layout.addRow("Audio Bitrate:", self.audio_bitrate_combo)
        
        # Sample rate
        self.audio_samplerate_combo = QComboBox()
        self.audio_samplerate_combo.addItems([
            "(auto)", "44100", "48000", "96000"
        ])
        layout.addRow("Sample Rate:", self.audio_samplerate_combo)
        
        # Channels
        self.audio_channels_combo = QComboBox()
        self.audio_channels_combo.addItems([
            "(auto)", "1 (mono)", "2 (stereo)", "6 (5.1)"
        ])
        layout.addRow("Channels:", self.audio_channels_combo)
        
        return group
    
    def _create_advanced_group(self) -> QGroupBox:
        """Create advanced options section."""
        group = QGroupBox("Advanced Options")
        layout = QFormLayout(group)
        
        # Pixel format
        self.pixel_format_combo = QComboBox()
        self.pixel_format_combo.addItem("(auto)")
        self.pixel_format_combo.addItems(PIXEL_FORMATS)
        layout.addRow("Pixel Format:", self.pixel_format_combo)
        
        # Two-pass encoding
        self.two_pass_check = QCheckBox("Two-pass encoding (slower, better quality)")
        layout.addRow("", self.two_pass_check)
        
        # Metadata
        self.preserve_metadata_check = QCheckBox("Preserve metadata")
        self.preserve_metadata_check.setChecked(True)
        layout.addRow("", self.preserve_metadata_check)
        
        self.preserve_timestamps_check = QCheckBox("Preserve timestamps")
        self.preserve_timestamps_check.setChecked(True)
        layout.addRow("", self.preserve_timestamps_check)
        
        # Subtitles
        self.copy_subtitles_check = QCheckBox("Copy subtitles")
        self.copy_subtitles_check.setChecked(True)
        layout.addRow("", self.copy_subtitles_check)
        
        # Batch processing
        self.max_parallel_spin = QSpinBox()
        self.max_parallel_spin.setRange(1, 16)
        self.max_parallel_spin.setValue(4)
        layout.addRow("Max Parallel Jobs:", self.max_parallel_spin)
        
        return group
    
    def _connect_signals(self):
        """Connect UI signals for dynamic updates."""
        # Update codec-specific options when codec changes
        self.codec_combo.currentTextChanged.connect(self._on_codec_changed)
        
        # Update custom settings visibility when preset changes
        self.quality_preset_combo.currentTextChanged.connect(self._on_preset_changed)
    
    def _load_defaults(self):
        """Load default values and populate dropdowns."""
        # Populate codec list
        self._populate_codec_list()
        
        # Set default codec
        if "libx264" in get_all_video_codecs():
            self.codec_combo.setCurrentText("libx264")
        
        # Trigger codec change to populate dependent fields
        self._on_codec_changed(self.codec_combo.currentText())
        
        # Trigger preset change to show description
        self._on_preset_changed(self.quality_preset_combo.currentText())
    
    def _populate_codec_list(self):
        """Populate codec dropdown based on filter."""
        self.codec_combo.clear()
        
        if self.hw_only_check.isChecked():
            codecs = get_hardware_codecs()
        else:
            codecs = get_all_video_codecs()
        
        self.codec_combo.addItems(codecs)
    
    def _on_codec_filter_changed(self, checked: bool):
        """Handle hardware-only filter toggle."""
        current = self.codec_combo.currentText()
        self._populate_codec_list()
        
        # Try to restore previous selection
        index = self.codec_combo.findText(current)
        if index >= 0:
            self.codec_combo.setCurrentIndex(index)
    
    def _on_codec_changed(self, codec: str):
        """Handle codec selection change."""
        if not codec:
            return
        
        # Update encoding presets
        self.preset_combo.clear()
        presets = get_available_presets(codec)
        if presets:
            self.preset_combo.addItems(presets)
        else:
            self.preset_combo.addItem("(none)")
        
        # Update profiles
        self.profile_combo.clear()
        self.profile_combo.addItem("(auto)")
        profiles = get_available_profiles(codec)
        if profiles:
            self.profile_combo.addItems(profiles)
        
        # Update tune options
        self.tune_combo.clear()
        self.tune_combo.addItem("(none)")
        tune_options = get_available_tune_options(codec)
        if tune_options:
            self.tune_combo.addItems(tune_options)
    
    def _on_preset_changed(self, preset_name: str):
        """Handle quality preset change."""
        if not preset_name or preset_name == "custom":
            self.preset_description_label.setText("Custom settings - configure manually")
            return
        
        try:
            # Get preset enum
            preset = QualityPreset(preset_name)
            description = get_preset_description(preset)
            self.preset_description_label.setText(description)
        except (ValueError, KeyError):
            self.preset_description_label.setText("")
    
    def _on_browse_output_dir(self):
        """Handle output directory browse button."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory"
        )
        
        if directory:
            self.output_dir_edit.setText(directory)
    
    # === Public Interface ===
    
    def get_settings(self) -> TranscodeSettings:
        """
        Generate TranscodeSettings object from current form values.
        
        Returns:
            TranscodeSettings object with all configured parameters
        """
        # Parse output directory
        output_dir = None
        if self.output_dir_edit.text().strip():
            output_dir = Path(self.output_dir_edit.text().strip())
        
        # Parse quality preset
        preset_text = self.quality_preset_combo.currentText()
        quality_preset = QualityPreset(preset_text) if preset_text != "custom" else QualityPreset.CUSTOM
        
        # Parse FPS method
        fps_method_text = self.fps_method_combo.currentText()
        fps_method = FPSMethod(fps_method_text)
        
        # Parse scaling algorithm
        scaling_text = self.scaling_algo_combo.currentText()
        scaling_algo = ScalingAlgorithm(scaling_text)
        
        # Parse resolution (0 = source)
        width = self.width_spin.value() if self.width_spin.value() > 0 else None
        height = self.height_spin.value() if self.height_spin.value() > 0 else None
        
        # Parse FPS (0 = source)
        target_fps = self.fps_spin.value() if self.fps_spin.value() > 0 else None
        
        # Parse audio bitrate
        audio_bitrate = None
        if self.audio_bitrate_combo.currentText() not in ["(auto)", ""]:
            audio_bitrate = self.audio_bitrate_combo.currentText()
        
        # Parse audio sample rate
        audio_samplerate = None
        if self.audio_samplerate_combo.currentText() not in ["(auto)", ""]:
            audio_samplerate = int(self.audio_samplerate_combo.currentText())
        
        # Parse audio channels
        audio_channels = None
        channels_text = self.audio_channels_combo.currentText()
        if channels_text not in ["(auto)", ""]:
            audio_channels = int(channels_text.split()[0])
        
        # Parse pixel format
        pixel_format = None
        if self.pixel_format_combo.currentText() != "(auto)":
            pixel_format = self.pixel_format_combo.currentText()
        
        # Parse codec preset
        preset = None
        if self.preset_combo.currentText() != "(none)":
            preset = self.preset_combo.currentText()
        
        # Parse tune
        tune = None
        if self.tune_combo.currentText() != "(none)":
            tune = self.tune_combo.currentText()
        
        # Parse profile
        profile = None
        if self.profile_combo.currentText() != "(auto)":
            profile = self.profile_combo.currentText()
        
        return TranscodeSettings(
            output_format=self.format_combo.currentText(),
            output_directory=output_dir,
            output_filename_pattern=self.filename_pattern_edit.text(),
            overwrite_existing=self.overwrite_check.isChecked(),
            video_codec=self.codec_combo.currentText(),
            quality_preset=quality_preset,
            crf=self.crf_spin.value(),
            preset=preset,
            tune=tune,
            profile=profile,
            output_width=width,
            output_height=height,
            scaling_algorithm=scaling_algo,
            maintain_aspect_ratio=self.maintain_aspect_check.isChecked(),
            target_fps=target_fps,
            fps_method=fps_method,
            analyze_vfr=self.analyze_vfr_check.isChecked(),
            audio_codec=self.audio_codec_combo.currentText(),
            audio_bitrate=audio_bitrate,
            audio_sample_rate=audio_samplerate,
            audio_channels=audio_channels,
            use_hardware_encoder=self.hw_encoder_check.isChecked(),
            use_hardware_decoder=self.hw_decoder_check.isChecked(),
            pixel_format=pixel_format,
            preserve_metadata=self.preserve_metadata_check.isChecked(),
            preserve_timestamps=self.preserve_timestamps_check.isChecked(),
            copy_subtitles=self.copy_subtitles_check.isChecked(),
            deinterlace=self.deinterlace_check.isChecked(),
            max_parallel_jobs=self.max_parallel_spin.value(),
            two_pass_encoding=self.two_pass_check.isChecked(),
        )
