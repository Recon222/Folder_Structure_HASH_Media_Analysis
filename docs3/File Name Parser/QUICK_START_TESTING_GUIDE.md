# Timeline Feature - Quick Start Testing Guide

**For:** Testing the newly implemented Timeline Video Generation feature
**Date:** 2025-10-07

---

## Prerequisites

### 1. FFmpeg/FFprobe Setup
Your custom FFmpeg binaries should be in one of these locations:
```
✓ bin/ffmpeg.exe and bin/ffprobe.exe (in project root)
✓ System PATH
```

**Verify:**
```bash
ffmpeg -version
ffprobe -version
```

### 2. Test Video Files
You'll need video files with SMPTE-compatible filenames. Examples:
```
✓ Camera_20250107_143025.mp4  (embedded time)
✓ NVR_Ch01_20250107_143025.dav  (Dahua format)
✓ video_161048.mp4  (compact HHMMSS)
```

**Recommended test setup:**
```
test_videos/
├── video1_143000.mp4  (14:30:00)
├── video2_143100.mp4  (14:31:00)  ← Adjacent
├── video3_143500.mp4  (14:35:00)  ← 4-minute gap!
└── video4_144000.mp4  (14:40:00)  ← 5-minute gap!
```

---

## Testing Workflow

### Step 1: Launch Application
```bash
.venv/Scripts/python.exe main.py
```

### Step 2: Navigate to File Name Parser Tab
Click on **"File Name Parser"** tab in main window

### Step 3: Add Video Files

**Option A: Add Files**
1. Click `📄 Add Files`
2. Select your test videos
3. Files appear in list

**Option B: Add Folder**
1. Click `📂 Add Folder`
2. Select folder containing videos
3. All videos in folder added

**Expected:**
```
📁 Video Files to Process
  🎥 video1_143000.mp4
  🎥 video2_143100.mp4
  🎥 video3_143500.mp4
  🎥 video4_144000.mp4

Total: 4 files
```

### Step 4: Parse Filenames

1. **Pattern:** Leave as "Auto-detect" (or select specific pattern)
2. **Frame Rate:** Check "Auto-detect frame rate" (recommended)
3. **Time Offset:** Leave unchecked (unless needed)
4. **Output Settings:** Select "Save to local subdirectory"
5. Click `🔍 Parse Filenames`

**Expected Console Output:**
```
[INFO] Processing file1.mp4...
✓ Matched pattern: "Embedded Time"
✓ SMPTE: 14:30:00:00
[INFO] Processing file2.mp4...
✓ Matched pattern: "Embedded Time"
✓ SMPTE: 14:31:00:00
...
[SUCCESS] Processing complete: 4 successful, 0 failed

📊 Processing Statistics
Total: 4
Success: 4
Failed: 0
Files/Sec: 8.2
```

### Step 5: Configure Timeline Settings

**Now the Timeline panel should be visible:**

```
🎬 Timeline Video Generation
───────────────────────────

ℹ️  Generate seamless timeline videos with automatic
    gap detection and SMPTE timecode slates

Output Directory:  (Not selected)      [📂 Browse]
Output Filename:   timeline.mp4

Timeline FPS:      30.00 fps
Min Gap Duration:  5.0 seconds
Output Resolution: 1920x1080 (1080p)
```

**Configure:**
1. **Output Directory:** Click `📂 Browse`, select output folder
2. **Output Filename:** Change to `test_timeline.mp4` (or keep default)
3. **Timeline FPS:** Keep 30.0 (or match your videos)
4. **Min Gap Duration:** Keep 5.0 (or adjust for your test)
5. **Resolution:** Select desired output resolution

### Step 6: Generate Timeline Video

1. Click `🎬 Generate Timeline Video`

**Expected Progress:**
```
Progress Bar:
[█████░░░░░░░░░░░░] 5%  - Validating videos and extracting metadata...
[███████░░░░░░░░░] 15%  - Calculating timeline and detecting gaps...
[█████████░░░░░░░] 20%  - Starting timeline render...
[███████████░░░░░] 32%  - Analyzing video codecs...
[████████████░░░░] 35%  - Preparing timeline segments...
[█████████████░░░] 50%  - Segments prepared
[████████████████] 65%  - Concatenating timeline segments...
[████████████████] 100% - Timeline render complete
```

**Console Output:**
```
[INFO] Starting timeline rendering workflow...
[INFO] Output: D:/output/test_timeline.mp4
[INFO] Resolution: 1920x1080 @ 30.00fps
[SUCCESS] Validated 4 video files
[SUCCESS] Timeline calculated: 6 segments, 2 gaps detected
[INFO]   Gap 1: 14:31:00:00 → 14:35:00:00 (240.0s)
[INFO]   Gap 2: 14:35:00:00 → 14:40:00:00 (300.0s)
[INFO] Timeline rendering in progress...
[SUCCESS] ✓ Timeline video generated successfully!
[SUCCESS]   Output: D:/output/test_timeline.mp4
```

**Success Dialog:**
```
┌─────────────────────────────────────┐
│   Timeline Complete! 🎉              │
├─────────────────────────────────────┤
│                                     │
│ Timeline video generated            │
│ successfully!                       │
│                                     │
│ Location: D:/output/test_timeline  │
│                          .mp4       │
│                                     │
│ The video includes:                 │
│ • Chronological video segments     │
│ • Gap slates showing missing       │
│   coverage                          │
│ • SMPTE timecode information       │
│                                     │
│           [OK]                      │
└─────────────────────────────────────┘
```

---

## Verification

### 1. Check Output File

**Location:** Your selected output directory
**Expected:** `test_timeline.mp4` (or your chosen name)

**File Size:** Approximately sum of input videos + gap slates
- Input videos: 100MB total
- Gap slates: ~5MB each
- Expected output: ~110MB

### 2. Play Timeline Video

**What to Look For:**

```
Timeline Structure:
┌─────────────────────────────────────────┐
│ video1_143000.mp4  (1 minute)           │
├─────────────────────────────────────────┤
│ video2_143100.mp4  (1 minute)           │
├─────────────────────────────────────────┤
│ GAP SLATE (5 seconds)                   │
│ "NO COVERAGE"                           │
│ "Gap Duration: 4m 0s"                   │
│ "Start: 14:31:00  |  End: 14:35:00"     │
├─────────────────────────────────────────┤
│ video3_143500.mp4  (1 minute)           │
├─────────────────────────────────────────┤
│ GAP SLATE (5 seconds)                   │
│ "NO COVERAGE"                           │
│ "Gap Duration: 5m 0s"                   │
│ "Start: 14:35:00  |  End: 14:40:00"     │
├─────────────────────────────────────────┤
│ video4_144000.mp4  (1 minute)           │
└─────────────────────────────────────────┘
```

**Check:**
- ✓ Video plays smoothly (no stuttering)
- ✓ Gap slates appear at correct positions
- ✓ Timecode information is accurate
- ✓ Resolution matches selected output
- ✓ No audio dropouts

### 3. Verify Codec Handling

**Test Case 1: Homogeneous Videos (No Mismatch)**
- All videos: h264, 1920x1080, 30fps
- Expected console: "Codec analysis: 1 codec(s), 1 resolution(s), 1 FPS value(s) - Normalization needed: False"
- Expected: Fast rendering (~30 seconds)

**Test Case 2: Mixed Codecs**
- Mix: h264 + hevc videos
- Expected console: "Codec mismatch detected - normalizing to: h264 1920x1080 @ 30.0fps"
- Expected progress: "Normalizing video 1/4...", "Normalizing video 2/4...", etc.
- Expected: Slower rendering (~2-3 minutes due to normalization)

---

## Common Issues & Solutions

### Issue 1: "FFprobe not available"
**Cause:** FFmpeg/FFprobe not found
**Solution:**
1. Check bin/ directory for ffmpeg.exe and ffprobe.exe
2. Add to system PATH
3. Restart application

### Issue 2: "No SMPTE timecode found"
**Cause:** Filename doesn't match any pattern
**Solution:**
1. Check filename format matches expected patterns
2. Try manual pattern selection (not auto-detect)
3. Use pattern generator to create custom pattern

### Issue 3: "Validation failed"
**Cause:** Video file corrupted or unsupported format
**Solution:**
1. Check video plays in VLC/media player
2. Verify video has valid video stream (not just audio)
3. Re-encode with FFmpeg if necessary

### Issue 4: "Timeline calculation failed"
**Cause:** Invalid timecodes or frame rates
**Solution:**
1. Check parsing results have valid SMPTE timecodes
2. Verify frame rates detected correctly
3. Try manual FPS selection instead of auto-detect

### Issue 5: Progress stuck at 65%
**Cause:** FFmpeg concatenation taking time
**Solution:**
- Wait patiently (large files take time)
- Check FFmpeg process in Task Manager
- Monitor temp directory for file growth

### Issue 6: "Failed to render timeline video"
**Cause:** Various FFmpeg errors
**Solution:**
1. Check console log for FFmpeg stderr output
2. Verify write permissions on output directory
3. Ensure sufficient disk space
4. Check video codec compatibility

---

## Advanced Testing

### Test Scenario 1: Large Dataset
```
Files: 40 videos, 30 minutes total
Expected time:
  - Parsing: ~30 seconds
  - Timeline (no mismatch): ~1 minute
  - Timeline (with mismatch): ~5-8 minutes
```

### Test Scenario 2: Different Frame Rates
```
Files: Mix of 29.97fps and 30fps videos
Expected: Time-based algorithm handles correctly
Result: Seamless timeline at target FPS
```

### Test Scenario 3: Different Resolutions
```
Files: 720p + 1080p + 4K mixed
Expected: All normalized to highest or most common
Result: Consistent resolution throughout timeline
```

### Test Scenario 4: No Gaps
```
Files: Sequential videos with no time gaps
Expected: No gap slates generated
Result: Pure concatenation of videos
```

### Test Scenario 5: Many Small Gaps
```
Files: Videos with 10+ gaps under min threshold
Expected: Gaps ignored (below 5.0s threshold)
Result: Adjacent videos concatenated
```

---

## Performance Benchmarks

### Expected Timing (Intel i7, SSD)

**Parsing Phase:**
- 10 files: ~5 seconds
- 40 files: ~15 seconds
- 100 files: ~30 seconds

**Timeline Rendering (No Normalization):**
- 10 files, no gaps: ~20 seconds
- 40 files, 5 gaps: ~40 seconds
- 100 files, 10 gaps: ~90 seconds

**Timeline Rendering (With Normalization):**
- 10 files: ~90 seconds
- 40 files: ~4 minutes
- 100 files: ~10 minutes

**Note:** GPU acceleration (if enabled in your FFmpeg) will be significantly faster

---

## Success Criteria

### ✅ Basic Functionality
- [ ] Files can be added and listed
- [ ] Parsing extracts SMPTE timecodes
- [ ] Timeline panel appears after parsing
- [ ] Output directory can be selected
- [ ] Timeline settings can be configured
- [ ] Timeline video generates successfully
- [ ] Output file plays correctly

### ✅ Advanced Features
- [ ] Gap detection works correctly
- [ ] Gap slates show accurate timecode information
- [ ] Codec mismatch detection works
- [ ] Video normalization triggered when needed
- [ ] Progress tracking updates smoothly
- [ ] Cancellation works (flag set)
- [ ] Error messages are user-friendly

### ✅ Edge Cases
- [ ] Single video (no gaps) works
- [ ] All adjacent videos (no gaps) works
- [ ] Mixed frame rates handled correctly
- [ ] Mixed codecs normalized properly
- [ ] Large files process without crashing
- [ ] Unicode filenames supported

---

## Reporting Issues

If you encounter issues, collect:

1. **Console Log** - Copy full console output
2. **Error Messages** - Screenshot of any error dialogs
3. **File Details** - Video codec, resolution, FPS
4. **System Info** - Windows version, Python version
5. **FFmpeg Version** - Output of `ffmpeg -version`

**Create issue with:**
```
Title: [Timeline] Brief description

Environment:
- OS: Windows 10/11
- Python: 3.x.x
- FFmpeg: Your version

Steps to Reproduce:
1. Add 4 videos with...
2. Parse filenames using...
3. Click Generate Timeline...
4. Error occurs at...

Expected: Timeline video generated
Actual: Error message "..."

Console Output:
[Paste console log here]
```

---

## Next Steps After Testing

Once testing confirms everything works:

1. **Commit Changes:**
   ```bash
   git add filename_parser/
   git commit -m "feat: Add timeline video generation with Adobe-styled UI

   - Auto-detect codec mismatches with conditional normalization
   - Beautiful Adobe-styled timeline panel
   - Complete workflow integration
   - Progress tracking and error handling
   "
   ```

2. **Merge to Main:**
   ```bash
   git checkout main
   git merge File-Name-Parser
   ```

3. **Celebrate!** 🎉
   You now have a production-ready timeline video generation feature!

---

**Testing prepared by:** Claude (Sonnet 4.5)
**Date:** 2025-10-07
**Feature Status:** ✅ Ready for Testing

*Happy testing! Report any issues and we'll fix them together.* 🚀
