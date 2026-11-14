# ComfyUI True APNG — Version 1.8.2

Export your videos and image sequences as **genuine animated APNG files**, directly from ComfyUI.

## Two output nodes

- **Save APNG (Video)** — connects to native VIDEO outputs and automatically reads the source frame rate.
- **Save APNG (Images)** — converts an IMAGE batch into an animation with your chosen FPS.

## Features

- Animated `.apng` export with frame order and repeated frames preserved.
- Infinite looping or a custom total play count.
- RGBA transparency and optional static or animated ComfyUI masks.
- Adjustable PNG compression from 0 to 9.
- A quality setting from 1 to 100 to trade RGB color precision for smaller files. At 100, no additional color reduction is applied; alpha is preserved at every setting.
- Optional start/end frame trimming, with FPS unchanged and matching animated masks preserved.
- Optional resizing with aspect ratio preserved and seven selectable filters, including progressive downscaling and pixel averaging.
- Optional workflow metadata embedding, with a frontend adapter for dropping APNG workflows into ComfyUI.
- Lossless compression strategy search and changed-rectangle optimization with adjustable tolerance: exact at 0, or optional RGB tolerance up to 100% per channel at 100. The tolerance uses an integer slider in steps of 1%. Alpha remains exact. Lossy candidates are only accepted with at least 1% smaller compressed frame data.
- Export verification and an optional image-based animated APNG preview with a transparency checkerboard.
- Node titles, descriptions, labels and tooltips in English, French, German, Spanish, Italian and Japanese, following your ComfyUI language setting.

File size savings depend on the image content. Lower quality settings may introduce banding in gradients.

## Installation

1. Extract the archive.
2. Place `ComfyUI-True-APNG` in `ComfyUI/custom_nodes/`.
3. Restart ComfyUI and search for **APNG**.

Files are saved to `ComfyUI/output/APNG/` by default.

## Included

English and French documentation, an example workflow, a test video and an animated APNG sample.

## Requirements and format notes

Uses Pillow and NumPy, normally already available in ComfyUI. The APNG encoder does not require an additional FFmpeg installation.

APNG does not contain audio and may produce larger files than MP4. Output is 8-bit RGB/RGBA.
