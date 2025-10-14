"""
Concatenate settings widget.

Provides form UI for configuring video concatenation parameters.
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit, QCheckBox,
    QPushButton, QLabel, QListWidget, QFileDialog
)
from PySide6.QtCore import Qt

from ..models.concatenate_settings import (
    ConcatenateSettings,
    ConcatenationMode,
    TransitionType,
    SlatePosition
)
from ..core import (
    get_all_video_codecs,
    get_all_audio_codecs,
    get_all_formats,
    PIXEL_FORMATS,
)


class ConcatenateSettingsWidget(QWidget):
    """
    Widget for configuring concatenate settings.
    
    Provides form UI for ConcatenateSettings parameters organized into
    logical sections. Pure UI component with no business logic.
    """
    
    def __init__(self, parent=None):
        """
        Initialize concatenate settings widget.
        
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
        
        # === Mode Selection ===
        mode_group = self._create_mode_group()
        layout.addWidget(mode_group)
        
        # === Output Configuration ===
        output_group = self._create_output_group()
        layout.addWidget(output_group)
        
        # === Target Specs (for transcode mode) ===
        specs_group = self._create_specs_group()
        layout.addWidget(specs_group)
        self.specs_group = specs_group  # Keep reference for enabling/disabling
        
        # === Transition & Slate Options ===
        transition_group = self._create_transition_group()
        layout.addWidget(transition_group)
        
        # === Advanced Options ===
        advanced_group = self._create_advanced_group()
        layout.addWidget(advanced_group)
        
        layout.addStretch()
    
    def _create_mode_group(self) -> QGroupBox:
        """Create concatenation mode selection section."""
        group = QGroupBox("Concatenation Mode")
        layout = QFormLayout(group)
        
        # Mode selection
        self.mode_combo = QComboBox()
        for mode in ConcatenationMode:
            self.mode_combo.addItem(mode.value)
        self.mode_combo.setCurrentText("auto")
        layout.addRow("Mode:", self.mode_combo)
        
        # Mode descriptions
        mode_description = QLabel(
            "<b>Auto:</b> Automatically detect if mux or transcode is needed<br>"
            "<b>Mux:</b> Fast copy mode (no re-encoding) - requires identical specs<br>"
            "<b>Transcode:</b> Re-encode to normalize all clips to matching specs"
        )
        mode_description.setWordWrap(True)
        mode_description.setStyleSheet("color: gray; font-size: 10px;")
        layout.addRow("", mode_description)
        
        # Spec matching options
        self.require_exact_match_check = QCheckBox("Require exact spec match for mux mode")
        layout.addRow("", self.require_exact_match_check)
        
        self.allow_minor_diff_check = QCheckBox("Allow minor differences (for auto mode)")
        self.allow_minor_diff_check.setChecked(True)
        layout.addRow("", self.allow_minor_diff_check)
        
        return group
    
    def _create_output_group(self) -> QGroupBox:
        """Create output configuration section."""
        group = QGroupBox("Output Configuration")
        layout = QFormLayout(group)
        
        # Output format
        self.format_combo = QComboBox()
        self.format_combo.addItems(get_all_formats())
        self.format_combo.setCurrentText("mp4")
        layout.addRow("Output Format:", self.format_combo)
        
        # Overwrite existing
        self.overwrite_check = QCheckBox("Overwrite existing file")
        layout.addRow("", self.overwrite_check)
        
        return group
    
    def _create_specs_group(self) -> QGroupBox:
        """Create target specs section (for transcode mode)."""
        group = QGroupBox("Target Specifications (Transcode Mode)")
        layout = QFormLayout(group)
        
        # Video codec
        self.target_codec_combo = QComboBox()
        self.target_codec_combo.addItems(get_all_video_codecs())
        layout.addRow("Video Codec:", self.target_codec_combo)
        
        # Resolution
        res_layout = QHBoxLayout()
        
        self.target_width_spin = QSpinBox()
        self.target_width_spin.setRange(0, 7680)
        self.target_width_spin.setValue(0)
        self.target_width_spin.setSpecialValueText("(auto - max)")
        self.target_width_spin.setSuffix(" px")
        res_layout.addWidget(QLabel("Width:"))
        res_layout.addWidget(self.target_width_spin)
        
        res_layout.addWidget(QLabel("×"))
        
        self.target_height_spin = QSpinBox()
        self.target_height_spin.setRange(0, 4320)
        self.target_height_spin.setValue(0)
        self.target_height_spin.setSpecialValueText("(auto - max)")
        self.target_height_spin.setSuffix(" px")
        res_layout.addWidget(QLabel("Height:"))
        res_layout.addWidget(self.target_height_spin)
        
        layout.addRow("Resolution:", res_layout)
        
        # Frame rate
        self.target_fps_spin = QDoubleSpinBox()
        self.target_fps_spin.setRange(0, 240)
        self.target_fps_spin.setValue(0)
        self.target_fps_spin.setSpecialValueText("(auto - common)")
        self.target_fps_spin.setDecimals(3)
        self.target_fps_spin.setSuffix(" fps")
        layout.addRow("Target FPS:", self.target_fps_spin)
        
        # Pixel format
        self.target_pixel_format_combo = QComboBox()
        self.target_pixel_format_combo.addItems(PIXEL_FORMATS)
        self.target_pixel_format_combo.setCurrentText("yuv420p")
        layout.addRow("Pixel Format:", self.target_pixel_format_combo)
        
        # Quality settings
        self.crf_spin = QSpinBox()
        self.crf_spin.setRange(0, 51)
        self.crf_spin.setValue(18)
        self.crf_spin.setToolTip("0 = lossless, 51 = worst. 18 recommended for forensic.")
        layout.addRow("CRF:", self.crf_spin)
        
        self.preset_combo = QComboBox()
        self.preset_combo.addItems([
            "ultrafast", "superfast", "veryfast", "faster", "fast",
            "medium", "slow", "slower", "veryslow"
        ])
        self.preset_combo.setCurrentText("medium")
        layout.addRow("Encoding Preset:", self.preset_combo)
        
        # Audio settings
        self.audio_codec_combo = QComboBox()
        self.audio_codec_combo.addItems(get_all_audio_codecs())
        self.audio_codec_combo.setCurrentText("aac")
        layout.addRow("Audio Codec:", self.audio_codec_combo)
        
        self.audio_bitrate_combo = QComboBox()
        self.audio_bitrate_combo.addItems(["128k", "192k", "256k", "320k"])
        self.audio_bitrate_combo.setCurrentText("192k")
        layout.addRow("Audio Bitrate:", self.audio_bitrate_combo)
        
        self.audio_samplerate_combo = QComboBox()
        self.audio_samplerate_combo.addItems(["44100", "48000", "96000"])
        self.audio_samplerate_combo.setCurrentText("48000")
        layout.addRow("Sample Rate:", self.audio_samplerate_combo)
        
        self.normalize_audio_check = QCheckBox("Normalize audio levels across clips")
        layout.addRow("", self.normalize_audio_check)
        
        return group
    
    def _create_transition_group(self) -> QGroupBox:
        """Create transition and slate options section."""
        group = QGroupBox("Transitions & Slates")
        layout = QFormLayout(group)
        
        # Transition type
        self.transition_type_combo = QComboBox()
        for trans_type in TransitionType:
            self.transition_type_combo.addItem(trans_type.value)
        self.transition_type_combo.setCurrentText("none")
        layout.addRow("Transition Type:", self.transition_type_combo)
        
        # Transition duration
        self.transition_duration_spin = QDoubleSpinBox()
        self.transition_duration_spin.setRange(0, 10)
        self.transition_duration_spin.setValue(0.5)
        self.transition_duration_spin.setDecimals(1)
        self.transition_duration_spin.setSuffix(" seconds")
        layout.addRow("Transition Duration:", self.transition_duration_spin)
        
        # Slate position
        self.slate_position_combo = QComboBox()
        for slate_pos in SlatePosition:
            self.slate_position_combo.addItem(slate_pos.value)
        self.slate_position_combo.setCurrentText("gaps_only")
        layout.addRow("Slate Position:", self.slate_position_combo)
        
        # Slate duration
        self.slate_duration_spin = QDoubleSpinBox()
        self.slate_duration_spin.setRange(0, 10)
        self.slate_duration_spin.setValue(2.0)
        self.slate_duration_spin.setDecimals(1)
        self.slate_duration_spin.setSuffix(" seconds")
        layout.addRow("Slate Duration:", self.slate_duration_spin)
        
        # Slate text template
        self.slate_text_edit = QLineEdit("Gap: {duration}")
        layout.addRow("Slate Text Template:", self.slate_text_edit)
        
        # Slate colors
        self.slate_bg_color_combo = QComboBox()
        self.slate_bg_color_combo.addItems(["black", "white", "gray", "red", "blue"])
        layout.addRow("Slate Background:", self.slate_bg_color_combo)
        
        self.slate_text_color_combo = QComboBox()
        self.slate_text_color_combo.addItems(["white", "black", "yellow", "red"])
        layout.addRow("Slate Text Color:", self.slate_text_color_combo)
        
        # Slate font size
        self.slate_font_size_spin = QSpinBox()
        self.slate_font_size_spin.setRange(12, 144)
        self.slate_font_size_spin.setValue(48)
        layout.addRow("Slate Font Size:", self.slate_font_size_spin)
        
        return group
    
    def _create_advanced_group(self) -> QGroupBox:
        """Create advanced options section."""
        group = QGroupBox("Advanced Options")
        layout = QFormLayout(group)
        
        # Hardware acceleration
        self.hw_encoder_check = QCheckBox("Use hardware encoder")
        layout.addRow("", self.hw_encoder_check)
        
        self.hw_decoder_check = QCheckBox("Use hardware decoder")
        layout.addRow("", self.hw_decoder_check)
        
        # GPU selection
        self.gpu_index_spin = QSpinBox()
        self.gpu_index_spin.setRange(0, 8)
        self.gpu_index_spin.setValue(0)
        layout.addRow("GPU Index:", self.gpu_index_spin)
        
        # Metadata
        self.preserve_metadata_check = QCheckBox("Preserve metadata")
        self.preserve_metadata_check.setChecked(True)
        layout.addRow("", self.preserve_metadata_check)
        
        self.preserve_chapters_check = QCheckBox("Preserve chapters")
        self.preserve_chapters_check.setChecked(True)
        layout.addRow("", self.preserve_chapters_check)
        
        # Two-pass encoding
        self.two_pass_check = QCheckBox("Two-pass encoding (slower, better quality)")
        layout.addRow("", self.two_pass_check)
        
        # Input order
        self.maintain_order_check = QCheckBox("Maintain input file order")
        self.maintain_order_check.setChecked(True)
        layout.addRow("", self.maintain_order_check)
        
        # Intermediate files
        self.keep_intermediate_check = QCheckBox("Keep intermediate files (for debugging)")
        layout.addRow("", self.keep_intermediate_check)
        
        return group
    
    def _connect_signals(self):
        """Connect UI signals for dynamic updates."""
        # Enable/disable target specs based on mode
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
    
    def _load_defaults(self):
        """Load default values."""
        # Set default codec
        if "libx264" in get_all_video_codecs():
            self.target_codec_combo.setCurrentText("libx264")
        
        # Trigger mode change to update UI
        self._on_mode_changed(self.mode_combo.currentText())
    
    def _on_mode_changed(self, mode: str):
        """Handle concatenation mode change."""
        # Enable/disable target specs based on mode
        # In auto/mux mode, specs are less relevant
        # In transcode mode, specs are critical
        is_transcode = (mode == "transcode")
        self.specs_group.setEnabled(is_transcode)
    
    # === Public Interface ===
    
    def get_settings(self, input_files: list[Path], output_file: Path) -> ConcatenateSettings:
        """
        Generate ConcatenateSettings object from current form values.
        
        Args:
            input_files: List of input file paths (from main tab)
            output_file: Output file path (from main tab)
        
        Returns:
            ConcatenateSettings object with all configured parameters
        """
        # Parse concatenation mode
        mode_text = self.mode_combo.currentText()
        concat_mode = ConcatenationMode(mode_text)
        
        # Parse transition type
        transition_text = self.transition_type_combo.currentText()
        transition_type = TransitionType(transition_text)
        
        # Parse slate position
        slate_text = self.slate_position_combo.currentText()
        slate_position = SlatePosition(slate_text)
        
        # Parse target resolution (0 = auto)
        target_width = self.target_width_spin.value() if self.target_width_spin.value() > 0 else None
        target_height = self.target_height_spin.value() if self.target_height_spin.value() > 0 else None
        
        # Parse target FPS (0 = auto)
        target_fps = self.target_fps_spin.value() if self.target_fps_spin.value() > 0 else None
        
        return ConcatenateSettings(
            concatenation_mode=concat_mode,
            input_files=input_files,
            maintain_input_order=self.maintain_order_check.isChecked(),
            output_file=output_file,
            output_format=self.format_combo.currentText(),
            overwrite_existing=self.overwrite_check.isChecked(),
            target_codec=self.target_codec_combo.currentText(),
            target_width=target_width,
            target_height=target_height,
            target_fps=target_fps,
            target_pixel_format=self.target_pixel_format_combo.currentText(),
            crf=self.crf_spin.value(),
            preset=self.preset_combo.currentText(),
            audio_codec=self.audio_codec_combo.currentText(),
            audio_bitrate=self.audio_bitrate_combo.currentText(),
            audio_sample_rate=int(self.audio_samplerate_combo.currentText()),
            normalize_audio=self.normalize_audio_check.isChecked(),
            transition_type=transition_type,
            transition_duration=self.transition_duration_spin.value(),
            slate_position=slate_position,
            slate_duration=self.slate_duration_spin.value(),
            slate_text_template=self.slate_text_edit.text(),
            slate_background_color=self.slate_bg_color_combo.currentText(),
            slate_text_color=self.slate_text_color_combo.currentText(),
            slate_font_size=self.slate_font_size_spin.value(),
            use_hardware_encoder=self.hw_encoder_check.isChecked(),
            use_hardware_decoder=self.hw_decoder_check.isChecked(),
            gpu_index=self.gpu_index_spin.value(),
            preserve_metadata=self.preserve_metadata_check.isChecked(),
            preserve_chapters=self.preserve_chapters_check.isChecked(),
            two_pass_encoding=self.two_pass_check.isChecked(),
            require_exact_match=self.require_exact_match_check.isChecked(),
            allow_minor_differences=self.allow_minor_diff_check.isChecked(),
            create_intermediate_files=self.keep_intermediate_check.isChecked(),
        )
