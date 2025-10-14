# Slate Date/Time Bug - Root Cause Analysis

**Date:** 2025-01-10
**Status:** 🔴 CRITICAL BUG IDENTIFIED
**Severity:** HIGH - Incorrect forensic timestamps in gap slates

---

## Executive Summary

Gap slates are displaying **incorrect dates and times** (December instead of May) due to a **critical mismatch** between batch splitting and single-pass rendering code paths. The bug was introduced in commit `4f5f8c7` when fixing batch rendering continuity.

### The Problem

- **Working Commit** (`2970209`): Slates show correct May dates
- **Broken Commit** (`4f5f8c7`): Slates show incorrect December dates
- **Current State** (`94ad0a0`): Still broken

---

## Root Cause: Two Different Datetime Objects

The bug occurs because **batch splitting** and **single-pass rendering** use **different methods** to calculate `earliest_dt`, resulting in different datetime values being passed to `_segments_from_intervals()`.

### Critical Code Paths

#### Path 1: Single-Pass Rendering (CORRECT)

```python
# In _render_single_pass() -> calls builder.build_command()

# ffmpeg_timeline_builder.py line 209
norm_clips, earliest_dt = self._normalize_clip_times(clips, timeline_is_absolute=True)

# _normalize_clip_times() line 274-275
t0 = min(s for _, s, _, _, _, _ in parsed)  # Unix timestamp from ISO8601 parsing
earliest_dt = datetime.fromtimestamp(t0)    # ✅ CONVERTS TO DATETIME
```

**Flow:**
1. Parse ISO8601 strings → Unix timestamps (`start_dt.timestamp()`)
2. Find earliest timestamp: `t0 = min(timestamps)`
3. **Convert back to datetime**: `earliest_dt = datetime.fromtimestamp(t0)`
4. Pass `earliest_dt` to `_segments_from_intervals()`
5. Gap slates use: `gap_start_dt = earliest_dt + timedelta(seconds=t0)`

**Result:** ✅ Correct dates (May 2025)

---

#### Path 2: Batch Splitting (BROKEN)

```python
# In _render_in_batches() -> calls _split_clips_into_batches()

# multicam_renderer_service.py line 345
norm_clips, timeline_t0 = builder._normalize_clip_times(clips, absolute=True)

# multicam_renderer_service.py line 347
segments = builder._segments_from_intervals(intervals, settings, timeline_t0)
```

**The Problem:**

The variable is named `timeline_t0` **but it's actually a datetime object**, not a Unix timestamp!

```python
# _normalize_clip_times() returns a datetime, not a float!
def _normalize_clip_times(...) -> Tuple[List[_NClip], Optional[datetime]]:
    ...
    earliest_dt = datetime.fromtimestamp(t0)  # Returns datetime object
    return norm_clips, earliest_dt  # ← This is a datetime!
```

**But the batch splitting code treats it like a Unix timestamp:**

```python
# Line 345 - receives datetime but assigns to poorly-named variable
norm_clips, timeline_t0 = builder._normalize_clip_times(clips, absolute=True)
                ^^^^^^^ - This is actually a datetime object, not a float!

# Line 347 - passes datetime where datetime is expected (seems fine)
segments = builder._segments_from_intervals(intervals, settings, timeline_t0)
```

**Flow:**
1. Parse ISO8601 strings → Unix timestamps
2. Find earliest timestamp: `t0 = min(timestamps)`
3. Convert to datetime: `earliest_dt = datetime.fromtimestamp(t0)`
4. Return `earliest_dt` **but assign to confusingly-named variable `timeline_t0`**
5. Pass to `_segments_from_intervals()` as `timeline_t0`
6. **Gap slates use datetime arithmetic... but WHY IS IT WRONG?**

---

## The ACTUAL Bug: Batch Clip Reconstruction

The bug isn't in the datetime conversion - it's in **how batch clips are reconstructed**!

### The Smoking Gun

```python
# multicam_renderer_service.py line 263
result = self._render_single_pass(batch_clips, batch_settings, None)
                                  ^^^^^^^^^^^
```

**What are `batch_clips`?**

```python
# Line 390 - batch_clips are _NClip objects (normalized clips)
batch_list = sorted(current_batch_clips, key=lambda c: (c.start, c.cam_id))
                    ^^^^^^^^^^^^^^^^^^^^ - These are _NClip objects!
batches.append(batch_list)
```

**But `_render_single_pass()` expects `Clip` objects with ISO8601 strings!**

```python
# Line 129 in _render_single_pass()
command, filter_script_path = self.builder.build_command(
    clips=clips,  # ← Expects List[Clip] with start/end as ISO8601 strings!
    settings=settings,
    output_path=output_path,
    timeline_is_absolute=True
)
```

### The Problem Chain

1. **Batch splitting** operates on `_NClip` objects (normalized, internal representation)
2. **Batch clips** have:
   - `start` and `end` as **floats** (normalized seconds from t0)
   - `start_iso` and `end_iso` as **Optional[str]** (preserved ISO8601 strings)

3. **`_render_single_pass()`** receives these `_NClip` objects
4. **`build_command()`** expects `Clip` objects with `start`/`end` as **ISO8601 strings**
5. **Type mismatch!** `build_command()` receives `_NClip` where it expects `Clip`

---

## The Actual Error Flow

```python
# Step 1: Batch splitting creates _NClip objects
batch_clips = [
    _NClip(
        path=Path("A02_20250521175603.mp4"),
        start=0.0,      # Normalized float (seconds from t0)
        end=30.5,       # Normalized float
        cam_id="A02",
        start_iso="2025-05-21T17:56:03",  # Preserved ISO8601
        end_iso="2025-05-21T17:56:33.5"   # Preserved ISO8601
    ),
    ...
]

# Step 2: Passed to _render_single_pass() which expects Clip objects
result = self._render_single_pass(batch_clips, batch_settings, None)

# Step 3: build_command() receives _NClip where it expects Clip
command, filter_script_path = self.builder.build_command(
    clips=clips,  # These are actually _NClip objects!
    ...
)

# Step 4: _normalize_clip_times() tries to parse the clips
for c in clips:  # c is a _NClip, not a Clip!
    if isinstance(c.start, str) and isinstance(c.end, str):
        # ❌ FAILS! c.start is a float (0.0), not a string!
        ...
    else:
        # ✅ Takes this branch (float branch)
        s = float(c.start)  # 0.0
        e = float(c.end)    # 30.5
        parsed.append((c.path, s, e, c.cam_id, None, None))
                                                ^^^^ ^^^^
        # ⚠️ ISO8601 strings set to None! start_iso/end_iso ignored!

# Step 5: Normalization uses float values
t0 = min(s for _, s, _, _, _, _ in parsed)  # 0.0 (not a real timestamp!)
earliest_dt = datetime.fromtimestamp(t0)    # datetime(1970, 1, 1, 0:00:00) ❌

# Step 6: Gap slate calculation
gap_start_dt = earliest_dt + timedelta(seconds=t0)  # 1970-01-01 + 0 seconds
gap_end_dt = earliest_dt + timedelta(seconds=t1)    # 1970-01-01 + 30 seconds

# Result: December dates (system timezone conversion from epoch?)
```

---

## Why December and Not January 1970?

The December dates are likely due to **timezone conversion**:

```python
datetime.fromtimestamp(0.0)  # Interprets as UTC epoch
# On a system in EST (UTC-5), this might display as December 31, 1969, 19:00:00
# On a system in PST (UTC-8), this might display as December 31, 1969, 16:00:00
```

The slate might be showing system time zone offset from Unix epoch zero.

---

## The Fix: Use start_iso/end_iso from _NClip

### Problem

`_NClip` objects preserve the original ISO8601 strings in `start_iso`/`end_iso` fields, **but the batch splitting code ignores them** when passing to `_render_single_pass()`.

### Solution

**Option 1: Convert _NClip back to Clip before rendering**

```python
# In _render_in_batches(), before calling _render_single_pass()

def _nclip_to_clip(nclip: _NClip) -> Clip:
    """Convert normalized clip back to Clip for rendering."""
    return Clip(
        path=nclip.path,
        start=nclip.start_iso if nclip.start_iso else nclip.start,
        end=nclip.end_iso if nclip.end_iso else nclip.end,
        cam_id=nclip.cam_id
    )

# Before line 263:
batch_clips_converted = [_nclip_to_clip(c) for c in batch_clips]
result = self._render_single_pass(batch_clips_converted, batch_settings, None)
```

**Option 2: Make _render_single_pass() accept both types**

```python
def _render_single_pass(
    self,
    clips: Union[List[Clip], List[_NClip]],  # Accept both
    settings: RenderSettings,
    progress_callback: Optional[Callable[[int, str], None]] = None
) -> Result[Path]:
    # Convert _NClip to Clip if needed
    if clips and isinstance(clips[0], _NClip):
        clips = [self._nclip_to_clip(c) for c in clips]

    # Rest of the method unchanged
    ...
```

**Option 3: Fix _normalize_clip_times() to check for _NClip type**

```python
def _normalize_clip_times(self, clips: List[Union[Clip, _NClip]], absolute: bool):
    """Accept both Clip and _NClip objects."""

    for c in clips:
        # Check if this is already a normalized clip
        if isinstance(c, _NClip):
            # Use preserved ISO8601 strings if available
            if c.start_iso and c.end_iso:
                start_dt = datetime.fromisoformat(c.start_iso)
                end_dt = datetime.fromisoformat(c.end_iso)
                s = start_dt.timestamp()
                e = end_dt.timestamp()
                parsed.append((c.path, s, e, c.cam_id, c.start_iso, c.end_iso))
            else:
                # Fallback to float values (relative mode)
                ...
        else:
            # Handle regular Clip objects (current logic)
            ...
```

---

## Recommended Fix: Option 1 (Cleanest)

**Option 1 is the cleanest** because it maintains separation of concerns:

- `_NClip` = internal representation for timeline calculations
- `Clip` = external representation for rendering
- **Convert between them explicitly** at the boundary

### Implementation Plan

1. **Add conversion method to MulticamRendererService**
   ```python
   def _nclips_to_clips(self, nclips: List[_NClip]) -> List[Clip]:
       """Convert normalized clips back to Clip objects for rendering."""
       clips = []
       for nc in nclips:
           clip = Clip(
               path=nc.path,
               start=nc.start_iso if nc.start_iso else nc.start,
               end=nc.end_iso if nc.end_iso else nc.end,
               cam_id=nc.cam_id
           )
           clips.append(clip)
       return clips
   ```

2. **Update batch rendering to convert before rendering**
   ```python
   # In _render_in_batches(), replace line 263:

   # OLD:
   result = self._render_single_pass(batch_clips, batch_settings, None)

   # NEW:
   batch_clips_converted = self._nclips_to_clips(batch_clips)
   result = self._render_single_pass(batch_clips_converted, batch_settings, None)
   ```

3. **Add type hints for clarity**
   ```python
   def _split_clips_into_batches(
       self,
       clips: List[Clip],  # Input: regular Clips
       settings: RenderSettings
   ) -> List[List[_NClip]]:  # Output: normalized _NClips
       """Split clips into batches (returns _NClip objects)."""
       ...
   ```

---

## Testing Plan

### Test Case 1: Single Video (No Batching)

**Input:**
- 1 video: `A02_20250521175603.mp4`
- Date: May 21, 2025
- Time: 17:56:03

**Expected Slate:**
- "GAP: Tue 21 May 17:56:03 → ..."

**Test:**
```bash
# Disable batching
use_batch_rendering = False
```

---

### Test Case 2: Multiple Videos (With Batching)

**Input:**
- 10 videos from May 21, 2025
- Batch size: 5 (forces 2 batches)

**Expected Slates:**
- All slates show May 21, 2025 dates
- No December dates

**Test:**
```bash
# Enable batching
use_batch_rendering = True
batch_size = 5
```

---

### Test Case 3: Verify ISO8601 Preservation

**Input:**
- Videos with different dates (May 21, May 22, May 23)

**Expected:**
- Each gap slate shows correct date for its position
- Dates increase chronologically

---

## Verification Steps

1. **Add logging to _nclips_to_clips()**
   ```python
   self.logger.debug(
       f"Converting _NClip: start={nc.start} (float), "
       f"start_iso={nc.start_iso} (string) → using {clip.start}"
   )
   ```

2. **Log in _normalize_clip_times()**
   ```python
   self.logger.debug(
       f"Parsing clip: start type={type(c.start)}, "
       f"value={c.start}, is_iso={isinstance(c.start, str)}"
   )
   ```

3. **Log earliest_dt in _segments_from_intervals()**
   ```python
   if earliest_dt is not None:
       self.logger.debug(
           f"Gap slate calculation: earliest_dt={earliest_dt.isoformat()}, "
           f"gap at t0={t0}, gap_start_dt={(earliest_dt + timedelta(seconds=t0)).isoformat()}"
       )
   ```

---

## Why This Bug is Subtle

1. **Variable naming confusion**: `timeline_t0` suggests Unix timestamp but is actually datetime
2. **Type flexibility**: Python allows passing `_NClip` where `Clip` expected (duck typing)
3. **Silent fallback**: `_normalize_clip_times()` silently treats floats as relative time
4. **ISO8601 preservation added later**: The `start_iso`/`end_iso` fields exist but aren't used in batch path
5. **Works in single-pass mode**: Only breaks when batching enabled

---

## Related Issues

- **Commit 2970209**: Working slates (used Unix timestamps throughout)
- **Commit 4f5f8c7**: Broken slates (introduced _NClip → Clip type confusion)
- **Commit 94ad0a0**: Still broken (ISO8601 preservation doesn't help batch path)

---

## Conclusion

The slate date bug is caused by **passing normalized internal _NClip objects to rendering methods that expect external Clip objects**. The `_NClip` objects have float `start`/`end` fields (normalized seconds from t0) instead of ISO8601 strings, causing `_normalize_clip_times()` to treat them as relative time and calculate datetime from Unix epoch zero.

**Fix:** Convert `_NClip` → `Clip` before rendering by using the preserved `start_iso`/`end_iso` fields.

**Estimated effort:** 15 minutes (add conversion method + call it before batch rendering)

**Risk:** Low (isolated change, existing tests should catch regressions)

---

**Document End**
