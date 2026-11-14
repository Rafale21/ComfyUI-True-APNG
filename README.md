<p align="center">
  <img src="https://raw.githubusercontent.com/rafale21/ComfyUI-True-APNG/main/icon.apng"
       alt="ComfyUI True APNG"
       width="200">
</p>

# ComfyUI True APNG — 1.8.2

Export native ComfyUI videos and IMAGE batches as genuine animated APNG files,
with transparency, trimming, resizing, quality control and optimization.

## Changes in 1.8.2

Tolerance now uses an integer native slider from 0 to 100, in steps of 1,
like the quality control. Colors follow the ComfyUI theme. Existing decimal
values remain supported internally for compatibility with older workflows;
new adjustments use whole percentages.

Publication materials are included in `publication/`: a French step-by-step
guide, a Registry metadata template and English release notes. The updated
English extension description is in `PRESENTATION_EN.md`.

The encoder skips tolerance trials below one integer color level and avoids
re-encoding candidates identical to the exact image. This saves work without
changing the encoded result. Tooltips now consistently refer to tolerance 0
rather than the old accuracy 100 setting.

## Tolerance and trimming

- The tolerance slider now increases intuitively: **0 = exact**, **100 = up to
  100% RGB difference per channel**. Default: 0.
- Two frame counters, both defaulting to 0, remove frames from the start and end.
- Older visual workflows preserve their actual threshold: a 1.7 tolerance
  of 100 becomes 10; pre-1.7 accuracy is converted using
  `new tolerance = (100 - old accuracy) / 10`. Legacy decimal values remain supported internally.
  Trimming is preserved, or defaults to zero if previously unavailable.

## Installation

Close ComfyUI, extract the archive and place `ComfyUI-True-APNG` in
`ComfyUI/custom_nodes/`. Replace the previous folder when updating. Restart
ComfyUI and hard-refresh the frontend. Search for APNG to add either node.
Recreate an old node if its controls remain inconsistent.

Pillow and NumPy normally come with ComfyUI. If necessary, install
`requirements.txt` with ComfyUI's Python. No additional FFmpeg, Node.js or npm
installation is required for APNG encoding.

## Nodes

- **Save APNG (Video)** accepts native VIDEO and reads its source FPS. For an
  existing MP4, use Load Video first. A path string or VHS_FILENAMES is not VIDEO.
- **Save APNG (Images)** accepts an IMAGE batch and manually selected FPS.

Connect a separate ComfyUI MASK when alpha is supplied separately. Masks use
1 for transparent and 0 for opaque. A fixed mask or a full per-frame mask batch
must match the source resolution. RGBA input is supported. Backgrounds are not
removed automatically.

## Trimming

`trim_start` and `trim_end` count frames, not seconds. For example, values 2
and 3 remove the first two and last three frames. Animated masks are sliced
with their corresponding frames; fixed masks remain unchanged.

Trimming occurs before resizing and optimization. FPS stays unchanged and
duration decreases. At least two frames must remain, otherwise export is
rejected. Trimming can remove repeated frames that pause a loop; it does not
generate a seamless transition.

## Settings

| Setting | Purpose |
| --- | --- |
| filename_prefix | Name/subfolder relative to output. Default APNG/ComfyUI. No extension. |
| loop | Total plays: 0 infinite, 1 once, 2 twice. |
| trim_start / trim_end | Frames removed from each end, default 0. |
| compress_level | PNG compression effort, 0–9; default 6. Does not change pixels. |
| max_side | 0 keeps the original resolution; otherwise limit the longest side without upscaling. |
| resize_method | Directly below max_side: lanczos, lanczos_progressive, box, bicubic, bilinear, hamming, nearest. |
| quality | 100 preserves the original 8-bit pixels. Lower values quantize RGB; alpha is preserved. |
| optimize_frames | Search changed rectangles and lossless PNG compression strategies. Enabled by default. |
| optimization_tolerance | 0 exact; 50 = 50% RGB tolerance; 100 = 100%. Default 0. |
| verify_file | Check animation controls, checksums and decoded frames before publishing. Default true. |
| include_metadata | Embed workflow metadata; respects --disable-metadata. |
| preview | Animated HTML image preview on a checkerboard, with a clickable filename. Can be disabled. |
| mask | Optional static or animated transparency mask. |

Outputs are file path, exported frame count after trimming, and encoded FPS.
Files go to `output/APNG/` by default. Existing files are not overwritten.

## Optimization and quality

At tolerance 0, optimization preserves pixels exactly. Higher tolerances may
retain colors from the previous reconstructed frame, but only if the candidate
saves at least 1% of compressed frame data versus the best exact representation.
Otherwise the exact source frame is kept. Alpha always remains exact.

The RGB threshold is `255 * tolerance / 100`, rounded down for integer
8-bit differences: 25/255 at 10%, or the full 255/255 at 100%. At 100%, all
RGB differences are allowed, so colors can stay frozen when alpha is unchanged
and retaining them reduces size. Every RGB channel must
pass and alpha must be identical. Using the actual reconstructed frame as
the reference prevents unbounded drift. All frames and timings are retained.

For realistic footage and gradients, start with **quality 100, tolerance 0,
optimization on**, optionally at compression 9. Savings depend on content and
extra encoding work takes longer. Both color quantization and nonzero tolerance
can create artifacts. Try progressive Lanczos or BOX for strong downscaling;
nearest is intended for pixel art.

## Preview and workflow import

The frontend uses an animated image element, not a video player. Keep the
extension's frontend modules enabled; old cached outputs are not rewritten.

Drop an APNG with embedded metadata onto an empty area of the canvas to restore
its workflow. The adapter uses a virtual PNG File without changing the original.
On installations without the adapter, a copy renamed from .apng to .png may
be used instead. Models and input files referenced by the workflow are not
included in the animation.

## Languages and examples

Node titles, descriptions, labels and tooltips follow ComfyUI's language:
English, French, German, Spanish, Italian and Japanese. Technical messages may
retain their original language. See README_FR.md for the French guide.

Copy `examples/test_video.mp4` to `ComfyUI/input/`, then load the example workflow.
With no trimming, it produces 45 frames at 15 FPS, 256 × 256, lasting 3 seconds.
A standalone test APNG and its regeneration script are also included.

## Limitations and tests

APNG has no audio and can be much larger than MP4. Output is 8-bit RGB/RGBA,
not HDR. Native VIDEO extraction may decode the entire clip before trimming.
Changing FPS changes playback speed, without interpolation.

See VALIDATION.md. Developer checks, not required for installation:

```bash
python check_apng.py examples/test_animation.apng
python -m unittest discover -s tests -v
node tests/test_import.mjs
node tests/test_preview.mjs
node tests/test_layout.mjs
```

API clients: the public setting is now optimization_tolerance instead of
optimization_accuracy. Convert existing values with `tolerance = (100 - accuracy) / 10`. Divide 1.7 tolerance values by 10 to
preserve their actual threshold.
Visual workflows are migrated automatically.
