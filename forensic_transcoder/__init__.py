"""
Forensic Video Transcoder.

A professional video transcoding and concatenation tool for forensic analysts.

INDEPENDENT PLUGIN MODULE:
- No external dependencies on main application
- Self-contained binary management (FFmpeg/FFprobe detection)
- Complete SOA architecture with controllers, services, workers
- PySide6-based UI components

Integration:
    from forensic_transcoder import ForensicTranscoderTab

    transcoder_tab = ForensicTranscoderTab()
    transcoder_tab.log_message.connect(self.handle_log_message)
    tab_widget.addTab(transcoder_tab, "Transcoder")
"""

from .ui.forensic_transcoder_tab import ForensicTranscoderTab

__version__ = '1.0.0'

__all__ = [
    'ForensicTranscoderTab',
]
