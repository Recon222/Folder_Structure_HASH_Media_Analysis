#!/usr/bin/env python3
"""Test script to verify field mappings between UI and command builder"""

# Test the field key conversion logic
ui_fields_advanced_video = [
    "Profile", "Level", "Pixel Format", "Sample Aspect Ratio", 
    "Pixel Aspect Ratio", "Color Range", "Color Transfer", "Color Primaries"
]

ui_fields_frame_analysis = [
    "GOP Structure", "Keyframe Interval", "Frame Type Distribution",
    "I Frame Count", "P Frame Count", "B Frame Count"
]

print("Advanced Video Field Mappings:")
print("-" * 40)
for field in ui_fields_advanced_video:
    field_key = field.lower().replace(" ", "_")
    print(f"{field:25} -> {field_key}")

print("\nFrame Analysis Field Mappings:")
print("-" * 40)
for field in ui_fields_frame_analysis:
    field_key = field.lower().replace(" ", "_")
    print(f"{field:25} -> {field_key}")

# Now check against FFProbeCommandBuilder mappings
from core.media.ffprobe_command_builder import FFProbeCommandBuilder

builder = FFProbeCommandBuilder()

print("\nFFProbeCommandBuilder Field Mappings Available:")
print("-" * 40)

# Check which of our converted keys exist in the command builder
all_ui_keys = []
for field in ui_fields_advanced_video + ui_fields_frame_analysis:
    field_key = field.lower().replace(" ", "_")
    all_ui_keys.append((field, field_key))

for field_name, field_key in all_ui_keys:
    if field_key in builder.FIELD_MAPPINGS:
        print(f"[OK] {field_name:25} -> {field_key} (FOUND in mappings)")
    elif field_key in builder.FRAME_ANALYSIS_FIELDS:
        print(f"[OK] {field_name:25} -> {field_key} (FOUND in frame analysis)")
    else:
        print(f"[MISSING] {field_name:25} -> {field_key} (NOT FOUND)")

print("\nAll Command Builder Field Mappings:")
print("-" * 40)
for key in sorted(builder.FIELD_MAPPINGS.keys()):
    print(f"  {key}")

print("\nAll Frame Analysis Fields:")
print("-" * 40)
for key in sorted(builder.FRAME_ANALYSIS_FIELDS):
    print(f"  {key}")