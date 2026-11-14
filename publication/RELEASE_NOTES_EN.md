# ComfyUI True APNG 1.8.2

Export genuine animated APNG files from native ComfyUI VIDEO outputs or IMAGE batches.

## Highlights

- Two output nodes: Save APNG (Video) and Save APNG (Images).
- RGB/RGBA export with static or animated transparency masks.
- Source FPS detection for VIDEO, manual FPS for IMAGE batches, and configurable looping.
- Start/end frame trimming and seven resizing filters.
- PNG compression level and RGB quality controls, with alpha preserved.
- Changed-rectangle optimization and lossless compression strategy selection.
- Optional RGB tolerance from 0% (exact) to 100%, with alpha kept exact.
- Workflow metadata embedding and APNG workflow import support.
- Animated APNG preview with a transparency checkerboard.
- English, French, German, Spanish, Italian and Japanese interface translations.

## Latest changes

- Tolerance now uses a native integer slider from 0 to 100 in steps of 1, matching the quality control.
- Retains the previous reduction in redundant tolerance encoding work.
- Existing decimal thresholds remain supported internally for compatibility.

## Validation

82 Python tests passed, together with JavaScript tests for APNG import, preview and workflow migration. Full graphical ComfyUI integration was not run in the automated test environment.

## Notes

APNG is an image animation format and contains no audio. Output is 8-bit RGB/RGBA. File size savings depend on the source; optional lossy RGB controls can introduce visible artifacts. Use quality 100 and tolerance 0 for exact color preservation after any requested resizing. No separate FFmpeg installation is required by the APNG encoder.
