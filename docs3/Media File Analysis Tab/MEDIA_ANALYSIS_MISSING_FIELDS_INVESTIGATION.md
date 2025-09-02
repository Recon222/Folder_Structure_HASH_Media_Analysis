# Media Analysis Missing Fields Investigation

## Executive Summary
The Media Analysis feature is not displaying all selected metadata fields in the PDF report. After deep investigation, I've identified **THREE critical issues** causing fields to disappear:

1. **PDF Report only shows 7 fields** regardless of what's selected
2. **Field filtering happens too early** in the pipeline
3. **Many metadata fields are never displayed** even when extracted

## The Problem Chain

### Issue #1: Limited PDF Report Fields
The PDF report (`media_analysis_service.py` lines 386-446) only displays these fields:
- Format
- Size  
- Duration
- Video Codec
- Resolution
- Frame Rate
- Audio (codec, sample rate, channels)

**Missing from PDF report entirely:**
- ❌ Bitrate (general)
- ❌ Creation Date
- ❌ Modification Date  
- ❌ Aspect Ratio
- ❌ Color Space
- ❌ Video Bitrate
- ❌ Audio Bitrate
- ❌ Bit Depth
- ❌ GPS Coordinates
- ❌ Location Name
- ❌ Device Make
- ❌ Device Model
- ❌ Software
- ❌ Title, Artist, Album, Comment

### Issue #2: Premature Field Filtering
The filtering happens at extraction time (`media_analysis_service.py` line 195):
```python
# Line 189-195
normalized = self.normalizer.normalize(extraction_result.value, file_path)
# Apply field filtering based on settings
filtered = self.normalizer.apply_field_filter(normalized, settings)
```

This means unchecked fields are set to `None` BEFORE reaching the report, making them permanently unavailable.

### Issue #3: UI Field Mismatch
The UI presents these field groups:
1. **General Information**: Format, Duration, File Size, Bitrate, Creation Date
2. **Video Stream**: Video Codec, Resolution, Frame Rate, Aspect Ratio, Color Space  
3. **Audio Stream**: Audio Codec, Sample Rate, Channels, Bit Depth
4. **Location Data**: GPS Coordinates, Location Name
5. **Device Information**: Device Make, Device Model, Software

But the PDF report doesn't check or display most of these!

## Root Cause Analysis

### Data Flow Breakdown
1. **FFprobe extracts** → All metadata available ✅
2. **Normalizer processes** → All fields populated ✅
3. **Filter applies** → Unchecked fields set to None ⚠️
4. **PDF generator** → Only displays 7 hardcoded fields ❌

### The Code Evidence

#### What Gets Extracted (ffprobe_wrapper.py):
```python
'-show_entries', 'format=duration,size,bit_rate,format_name,format_long_name,tags',
'-show_entries', 'stream=codec_name,codec_long_name,codec_type,width,height,'
                 'avg_frame_rate,r_frame_rate,sample_rate,channels,channel_layout,'
                 'bit_rate,bits_per_sample,display_aspect_ratio,pix_fmt,color_space,'
                 'duration,tags',
```
✅ FFprobe IS extracting all the data

#### What Gets Normalized (metadata_normalizer.py):
- ✅ Bitrate extracted (line 107)
- ✅ Creation dates extracted (lines 290-296)
- ✅ Aspect ratio extracted (line 147)
- ✅ Color space extracted (line 150)
- ✅ Device info extracted (lines 238-240)
- ✅ GPS extracted (lines 248-285)

#### What Gets Displayed (media_analysis_service.py):
```python
# Only these fields make it to PDF:
if metadata.format:
    file_detail_data.append(['  Format:', metadata.format])
file_detail_data.append(['  Size:', metadata.get_file_size_string()])
if metadata.duration:
    file_detail_data.append(['  Duration:', metadata.get_duration_string()])
if metadata.video_codec:
    file_detail_data.append(['  Video Codec:', metadata.video_codec])
if metadata.resolution:
    file_detail_data.append(['  Resolution:', metadata.get_resolution_string()])
if metadata.frame_rate:
    file_detail_data.append(['  Frame Rate:', f"{metadata.frame_rate:.1f} fps"])
# Audio line...
```

## The Solution

### Fix #1: Add All Fields to PDF Report
The PDF report needs to check and display ALL metadata fields:

```python
# After line 434 in media_analysis_service.py, ADD:

# Aspect Ratio
if metadata.aspect_ratio:
    file_detail_data.append(['  Aspect Ratio:', metadata.aspect_ratio])

# Color Space  
if metadata.color_space:
    file_detail_data.append(['  Color Space:', metadata.color_space])

# Bitrates
if metadata.bitrate:
    file_detail_data.append(['  Overall Bitrate:', f"{metadata.bitrate:,} bps"])
if metadata.video_bitrate:
    file_detail_data.append(['  Video Bitrate:', f"{metadata.video_bitrate:,} bps"])
if metadata.audio_bitrate:
    file_detail_data.append(['  Audio Bitrate:', f"{metadata.audio_bitrate:,} bps"])

# Bit Depth
if metadata.bit_depth:
    file_detail_data.append(['  Audio Bit Depth:', f"{metadata.bit_depth} bits"])

# Dates
if metadata.creation_date:
    file_detail_data.append(['  Creation Date:', metadata.creation_date.strftime("%Y-%m-%d %H:%M:%S")])
if metadata.modification_date:
    file_detail_data.append(['  Modified Date:', metadata.modification_date.strftime("%Y-%m-%d %H:%M:%S")])

# Location
if metadata.gps_latitude and metadata.gps_longitude:
    file_detail_data.append(['  GPS:', f"{metadata.gps_latitude:.6f}, {metadata.gps_longitude:.6f}"])
if metadata.location_name:
    file_detail_data.append(['  Location:', metadata.location_name])

# Device Info
if metadata.device_make:
    file_detail_data.append(['  Device Make:', metadata.device_make])
if metadata.device_model:
    file_detail_data.append(['  Device Model:', metadata.device_model])
if metadata.software:
    file_detail_data.append(['  Software:', metadata.software])

# Additional Metadata
if metadata.title:
    file_detail_data.append(['  Title:', metadata.title])
if metadata.artist:
    file_detail_data.append(['  Artist:', metadata.artist])
if metadata.album:
    file_detail_data.append(['  Album:', metadata.album])
if metadata.comment:
    file_detail_data.append(['  Comment:', metadata.comment[:100]])  # Limit length
```

### Fix #2: Respect User Settings
The field filtering in `apply_field_filter()` is working correctly - it sets unchecked fields to None. The issue is the PDF report doesn't display the fields that ARE checked.

### Fix #3: Field Name Mapping
The UI creates field keys like this (line 322 of media_analysis_tab.py):
```python
field_key = field.lower().replace(" ", "_")
```

So "Creation Date" becomes "creation_date" ✅
This mapping is correct.

## Why You're Only Seeing Basic Fields

Your current PDF shows only:
- Format: MP4
- Size: 93.99 MB
- Duration: 01:59
- Video Codec: H.265/HEVC
- Resolution: 3840x2160
- Frame Rate: 25.0 fps
- Audio: AAC @ 16000 Hz (mono)

**Because the PDF report code literally only checks for these 7 fields!**

Even though:
1. FFprobe extracted 20+ fields
2. Normalizer processed them all
3. Your UI settings preserved them
4. The MediaMetadata object contains them

They never make it to the PDF because the report generator doesn't look for them.

## Testing Confirmation

To verify the data exists, add this debug line at line 387 in media_analysis_service.py:
```python
logger.info(f"Metadata fields available: format={metadata.format}, bitrate={metadata.bitrate}, creation={metadata.creation_date}, aspect={metadata.aspect_ratio}, device={metadata.device_make}")
```

You'll see the fields ARE populated - they're just not being displayed.

## Implementation Priority

1. **High Priority**: Add missing fields to PDF report (Fix #1)
2. **Medium Priority**: Add similar fields to CSV export
3. **Low Priority**: Consider grouping fields in report by category

## Summary

The Media Analysis feature IS extracting all metadata correctly. The issue is simply that the PDF report generator only displays 7 hardcoded fields out of the 25+ available fields. The fix requires adding the missing field checks to the PDF report generation code.

**Estimated fix time: 10 minutes**
**Lines of code to add: ~50**
**Risk: Low** (display-only change)