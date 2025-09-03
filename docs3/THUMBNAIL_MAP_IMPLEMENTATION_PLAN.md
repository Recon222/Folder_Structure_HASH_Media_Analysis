# Thumbnail Display in Map Popups - Implementation Plan

## Current State Analysis

### ✅ What's Already Implemented:
1. **UI Checkbox**: `extract_thumbnails_check` in Media Analysis tab
2. **Settings Assignment**: UI sets `settings.extract_thumbnails = self.extract_thumbnails_check.isChecked()`
3. **Binary Extraction Flag**: Command builder checks `extract_binary` flag and adds `-b` to ExifTool command
4. **Map Popup Structure**: Popups display filename, time, device, coordinates, altitude, speed, direction

### ❌ What's Missing (Currently Placeholder):
1. **ExifToolSettings Model**: No `extract_thumbnails` field - only has `extract_binary`
2. **Thumbnail Data Storage**: ExifToolMetadata model has no field for thumbnail data
3. **Thumbnail Extraction**: ExifTool `-b` flag extracts ALL binary data, not specifically thumbnails
4. **Thumbnail Processing**: No code to extract/encode thumbnails from ExifTool output
5. **Map Display**: No thumbnail display logic in map popups

## Implementation Plan

### Phase 1: Fix Settings Pipeline
1. **Update ExifToolSettings model** (`core/exiftool/exiftool_models.py`):
   - Add `extract_thumbnails: bool = False` field
   - Map this to control thumbnail-specific extraction

2. **Fix UI Settings Mapping** (`ui/tabs/media_analysis_tab.py`):
   - Change from non-existent field names to actual model fields
   - Map `extract_thumbnails_check` to `settings.extract_thumbnails`
   - Map `include_binary_check` to `settings.extract_binary`

### Phase 2: Thumbnail Extraction
1. **Update Command Builder** (`core/exiftool/exiftool_command_builder.py`):
   - When `extract_thumbnails=True`, add specific thumbnail tags:
     - `-ThumbnailImage` (JPEG thumbnail)
     - `-PreviewImage` (larger preview)
     - `-JpgFromRaw` (JPEG from RAW files)
   - Use `-b` flag only for these specific tags to avoid extracting ALL binary data

2. **Update ExifToolMetadata Model** (`core/exiftool/exiftool_models.py`):
   - Add `thumbnail_base64: Optional[str] = None` field
   - Store base64-encoded thumbnail for web display

3. **Update Normalizer** (`core/exiftool/exiftool_normalizer.py`):
   - Extract thumbnail data from ExifTool JSON output
   - Handle base64 encoding of thumbnail binary data
   - Prefer ThumbnailImage > PreviewImage > JpgFromRaw

### Phase 3: Map Display Integration
1. **Update Marker Data** (`ui/components/geo/geo_visualization_widget.py`):
   - In `_metadata_to_marker()`, add thumbnail to marker dict:
     ```python
     if metadata.thumbnail_base64:
         marker['thumbnail'] = metadata.thumbnail_base64
     ```

2. **Update Map Template** (`ui/components/geo/map_template.py`):
   - Modify popup HTML generation to include thumbnail at top:
     ```javascript
     if (data.thumbnail) {
         popupHtml += `<img src="data:image/jpeg;base64,${data.thumbnail}" 
                       style="max-width:200px; max-height:150px; margin-bottom:10px;">`;
     }
     ```

### Phase 4: Performance Optimization
1. **Selective Extraction**: Only extract thumbnails when checkbox is checked
2. **Size Limits**: Limit thumbnail size to reduce memory usage
3. **Lazy Loading**: Consider loading thumbnails on-demand for large datasets
4. **Caching**: Cache extracted thumbnails to avoid re-extraction

## Technical Details

### ExifTool Command for Thumbnails
```bash
# Extract specific thumbnail fields in base64
exiftool -json -ThumbnailImage -PreviewImage -JpgFromRaw -b FILE

# The -b flag makes ExifTool output binary data as base64 in JSON mode
```

### Data Flow
1. User checks "Extract embedded thumbnails"
2. ExifToolSettings gets `extract_thumbnails=True`
3. Command builder adds thumbnail-specific tags to command
4. ExifTool extracts and base64-encodes thumbnail data
5. Normalizer stores base64 thumbnail in ExifToolMetadata
6. Map widget adds thumbnail to marker data
7. JavaScript displays thumbnail in popup

## Considerations
- **Privacy**: Thumbnails may contain GPS/metadata - respect privacy settings
- **File Size**: Base64 encoding increases size by ~33%
- **Performance**: Large numbers of thumbnails can slow map rendering
- **Fallback**: Handle files without thumbnails gracefully
- **Format Support**: Not all files have embedded thumbnails

## Testing Strategy
1. Test with JPEG files (usually have thumbnails)
2. Test with RAW files (may have JPEG previews)
3. Test with video files (may have poster frames)
4. Test with files lacking thumbnails
5. Verify memory usage with many thumbnails
6. Test privacy settings still work with thumbnails