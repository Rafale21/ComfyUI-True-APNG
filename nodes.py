"""V1 node definitions, supported by both current and older ComfyUI."""

from __future__ import annotations

import json
import logging
import math
import mimetypes
import os
import tempfile

import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo

import folder_paths

from .apng_encoder import frame_delay, verify_apng, write_apng

logger = logging.getLogger(__name__)
mimetypes.add_type("image/apng", ".apng")


def _numpy(value):
    # Transfer one frame at a time; do not copy the entire video to the CPU.
    if hasattr(value, "detach"):
        value = value.detach().cpu().float().numpy()
    return np.asarray(value)


def _interrupt():
    from comfy.model_management import throw_exception_if_processing_interrupted
    throw_exception_if_processing_interrupted()


def _metadata(enabled, prompt, extra_pnginfo):
    from comfy.cli_args import args
    if not enabled or getattr(args, "disable_metadata", False):
        return None
    info = PngInfo()
    if prompt is not None:
        info.add_text("prompt", json.dumps(prompt, ensure_ascii=True))
    for key, value in (extra_pnginfo or {}).items():
        info.add_text(str(key), json.dumps(value, ensure_ascii=True))
    return info


def _batch_shape(images):
    shape = tuple(images.shape)
    if len(shape) != 4 or shape[-1] not in (1, 3, 4) or min(shape[1:3]) < 1:
        raise ValueError("Images attendues au format ComfyUI [nombre, hauteur, largeur, canaux].")
    if shape[0] < 2:
        raise ValueError("Il faut au moins 2 images pour créer une animation APNG.")
    return shape


def _mask_info(mask, count, height, width):
    if mask is None:
        return None
    shape = tuple(mask.shape)
    if len(shape) == 2:
        if shape != (height, width):
            raise ValueError("Le masque doit avoir la même résolution que les images.")
        return 0  # A single two-dimensional mask.
    if len(shape) != 3 or shape[0] not in (1, count) or shape[1:] != (height, width):
        raise ValueError("Masque attendu : [1 ou nombre d'images, hauteur, largeur].")
    return shape[0]


def _output_size(width, height, max_side):
    if not isinstance(max_side, int) or not 0 <= max_side <= 16384:
        raise ValueError("max_side doit être compris entre 0 et 16384.")
    if max_side == 0 or max(width, height) <= max_side:
        return width, height
    ratio = max_side / max(width, height)
    return max(1, round(width * ratio)), max(1, round(height * ratio))


def _quantize_rgb(image, quality):
    """Uniform, temporally stable RGB quantization; never quantize alpha."""
    if quality == 100:
        return image
    levels = max(2, round(2 ** (1 + 7 * quality / 100)))
    values = np.arange(256, dtype=np.float32)
    lookup = np.rint(np.rint(values * (levels - 1) / 255) * 255 / (levels - 1)).astype(np.uint8)
    pixels = np.array(image, copy=True)
    pixels[..., :3] = lookup[pixels[..., :3]]
    return Image.fromarray(pixels)


RESIZE_METHODS = {
    "lanczos": Image.Resampling.LANCZOS,
    "lanczos_progressive": Image.Resampling.LANCZOS,
    "box": Image.Resampling.BOX,
    "bicubic": Image.Resampling.BICUBIC,
    "bilinear": Image.Resampling.BILINEAR,
    "hamming": Image.Resampling.HAMMING,
    "nearest": Image.Resampling.NEAREST,
}


def _resize_image(image, size, resize_method):
    if resize_method not in RESIZE_METHODS:
        raise ValueError("Unknown resize_method: " + str(resize_method))
    if image.size == size:
        return image
    if resize_method == "lanczos_progressive":
        # Average in half-size steps before the final Lanczos pass.
        # Pillow handles RGBA filtering in premultiplied-alpha space.
        while image.width > 2 * size[0] or image.height > 2 * size[1]:
            intermediate = (max(size[0], image.width // 2), max(size[1], image.height // 2))
            image = image.resize(intermediate, Image.Resampling.BOX)
    return image.resize(size, RESIZE_METHODS[resize_method])


def _pil_frames(images, mask, mask_count, size, quality=100, resize_method="lanczos", optimize_frames=True, optimization_tolerance=0, preview=True, trim_start=0, trim_end=0):
    for index in range(images.shape[0]):
        _interrupt()
        array = _numpy(images[index])
        if not np.issubdtype(array.dtype, np.number) or not np.isfinite(array).all():
            raise ValueError(f"L'image {index + 1} contient des pixels invalides.")
        if array.dtype == np.uint8:
            pixels = array
        else:
            pixels = np.rint(np.clip(array, 0, 1) * 255).astype(np.uint8)
        if pixels.shape[-1] == 1:
            pixels = np.repeat(pixels, 3, axis=-1)
        image = Image.fromarray(pixels)
        if mask is not None:
            current = mask if mask_count == 0 else mask[0 if mask_count == 1 else index]
            mask_array = _numpy(current)
            if not np.isfinite(mask_array).all():
                raise ValueError(f"Le masque {index + 1} contient des valeurs invalides.")
            # ComfyUI masks use 1 for transparent, 0 for opaque.
            alpha = 1.0 - np.clip(mask_array, 0, 1)
            if image.mode == "RGBA":
                alpha = alpha * (pixels[..., 3].astype(np.float32) / 255.0)
            image = image.convert("RGBA")
            image.putalpha(Image.fromarray(np.rint(alpha * 255).astype(np.uint8)))
        if image.size != size:
            image = _resize_image(image, size, resize_method)
        yield _quantize_rgb(image, quality)


def _reserve_filename(filename_prefix, width, height):
    output_dir = folder_paths.get_output_directory()
    full_dir, filename, counter, subfolder, _ = folder_paths.get_save_image_path(
        filename_prefix, output_dir, width, height,
    )
    os.makedirs(full_dir, exist_ok=True)
    filename = filename.replace("%batch_num%", "0")
    while True:
        basename = f"{filename}_{counter:05}_.apng"
        path = os.path.join(full_dir, basename)
        try:
            # Avoid replacing another export, including simultaneous queues.
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666)
        except FileExistsError:
            counter += 1
            continue
        os.close(fd)
        return path, basename, subfolder


def _export(images, fps, filename_prefix, loop, compress_level, max_side,
            verify_file, include_metadata, mask, prompt, extra_pnginfo, quality=100, resize_method="lanczos", optimize_frames=True, optimization_tolerance=0, preview=True, trim_start=0, trim_end=0):
    from comfy.utils import ProgressBar

    if not isinstance(quality, int) or not 1 <= quality <= 100:
        raise ValueError("quality doit être un entier compris entre 1 et 100.")
    if resize_method not in RESIZE_METHODS:
        raise ValueError("Unknown resize_method: " + str(resize_method))
    if (not isinstance(optimization_tolerance, (int, float))
            or not math.isfinite(optimization_tolerance)
            or not 0 <= optimization_tolerance <= 100):
        raise ValueError("optimization_tolerance must be a finite number from 0 to 100.")
    for name, value in (("trim_start", trim_start), ("trim_end", trim_end)):
        if not isinstance(value, int) or not 0 <= value <= 1000000:
            raise ValueError(name + " must be an integer from 0 to 1000000.")
    count, height, width, _ = _batch_shape(images)
    mask_count = _mask_info(mask, count, height, width)
    remaining = count - trim_start - trim_end
    if remaining < 2:
        raise ValueError(f"Trimming leaves {remaining} frames; keep at least two.")
    if trim_start or trim_end:
        stop = count - trim_end
        images = images[trim_start:stop]
        if mask is not None and mask_count not in (None, 0, 1):
            mask = mask[trim_start:stop]
            mask_count = remaining
    count = remaining
    size = _output_size(width, height, max_side)
    delay = frame_delay(fps)
    if not isinstance(loop, int) or not 0 <= loop <= 0xFFFFFFFF:
        raise ValueError("loop doit être un entier positif ou nul (0 = infini).")
    if not isinstance(compress_level, int) or not 0 <= compress_level <= 9:
        raise ValueError("compress_level doit être compris entre 0 et 9.")
    if not isinstance(filename_prefix, str) or not filename_prefix.strip():
        raise ValueError("Le préfixe du fichier ne peut pas être vide.")
    metadata = _metadata(include_metadata, prompt, extra_pnginfo)
    progress = ProgressBar(count * (2 if verify_file else 1))

    def encoding_progress(done, total):
        _interrupt()
        progress.update_absolute(done)

    def verifying_progress(done, total):
        _interrupt()
        progress.update_absolute(count + min(done, count))

    _interrupt()
    path, basename, subfolder = _reserve_filename(filename_prefix, *size)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".true_apng_", suffix=".tmp",
            dir=os.path.dirname(path), delete=False,
        ) as stream:
            temporary_path = stream.name
            write_apng(
                stream,
                _pil_frames(images, mask, mask_count, size, quality, resize_method),
                count, fps, loop, compress_level, metadata, encoding_progress, optimize_frames,
                optimization_tolerance=optimization_tolerance,
            )
        if verify_file:
            verify_apng(
                temporary_path, count, loop, delay,
                decode=True, on_frame=verifying_progress,
            )
        _interrupt()
        os.replace(temporary_path, path)
        temporary_path = None
    except BaseException:
        # Cancellation and export errors must not leave a broken final file.
        for candidate in (temporary_path, path):
            if candidate:
                try:
                    os.unlink(candidate)
                except OSError:
                    logger.warning("Impossible de retirer le fichier incomplet %s", candidate)
        raise
    progress.update_absolute(count * (2 if verify_file else 1))
    encoded_fps = float(1 / delay)
    logger.info(
        "[True APNG] %s | %d images | %dx%d | %.8g FPS | loop=%d | verified=%s",
        path, count, *size, encoded_fps, loop, verify_file,
    )
    return {
        "ui": {
            "true_apng_preview": [{"filename": basename, "subfolder": subfolder, "type": "output"}] if preview else [],
        },
        "result": (os.path.abspath(path), count, encoded_fps),
    }


def _common_inputs():
    return {
        "filename_prefix": ("STRING", {
            "default": "APNG/ComfyUI",
            "tooltip": "Path relative to output; subfolders are allowed.",
        }),
        "loop": ("INT", {
            "default": 0, "min": 0, "max": 0xFFFFFFFF,
            "tooltip": "Total plays: 0 = infinite, 1 = once, 2 = twice.",
        }),
    }


def _optional_inputs():
    return {
        "trim_start": ("INT", {
            "default": 0, "min": 0, "max": 1000000, "step": 1,
            "tooltip": "Remove this many frames from the start before resizing and optimization. Must leave at least two frames together with trim_end.",
        }),
        "trim_end": ("INT", {
            "default": 0, "min": 0, "max": 1000000, "step": 1,
            "tooltip": "Remove this many frames from the end before resizing and optimization. Must leave at least two frames together with trim_start.",
        }),
        "compress_level": ("INT", {
            "default": 6, "min": 0, "max": 9,
            "tooltip": "Lossless PNG compression: 0 is faster/larger; 9 is slower/smaller.",
        }),
        "max_side": ("INT", {
            "default": 0, "min": 0, "max": 16384,
            "tooltip": "0 = original size. Otherwise limit the longest side, preserving aspect ratio without upscaling.",
        }),
        "resize_method": (list(RESIZE_METHODS), {
            "default": "lanczos",
            "tooltip": "Downscaling filter. lanczos: existing sharp filter; lanczos_progressive: staged averaging then Lanczos; box: pixel averaging; bicubic/bilinear/hamming: alternatives; nearest: hard pixel edges. Used only when max_side reduces size.",
        }),
        "verify_file": ("BOOLEAN", {
            "default": True,
            "tooltip": "Check animation structure and decode every frame before publishing the file.",
        }),
        "include_metadata": ("BOOLEAN", {
            "default": True,
            "tooltip": "Embed workflow metadata; also respects --disable-metadata.",
        }),
        "mask": ("MASK", {
        "tooltip": "Optional ComfyUI mask: 1 = transparent, 0 = opaque. One mask or one per frame.",
    }), "quality": ("INT", {
        "default": 100, "min": 1, "max": 100, "step": 1,
        "tooltip": "100 keeps the original pixels. Lower values reduce RGB precision; gradients may show banding. Alpha is preserved.",
    }), "optimize_frames": ("BOOLEAN", {
        "default": True,
        "tooltip": "Try changed rectangles and multiple lossless PNG compression strategies. At tolerance 0 all pixels stay exact. Extra encoding work may take longer.",
    }), "optimization_tolerance": ("INT", {
        "default": 0, "min": 0, "max": 100, "step": 1,
        "tooltip": "0 = exact. 100 = RGB tolerance up to 100% per channel, only accepted with at least 1% smaller frame data. Alpha stays exact. Requires optimize_frames.",
    }), "preview": ("BOOLEAN", {
        "default": True,
        "tooltip": "Show an animated APNG image preview, not a video player. Disable to hide the preview.",
    })}


class _APNGOutput:
    CATEGORY = "image/animation/True APNG"
    RETURN_TYPES = ("STRING", "INT", "FLOAT")
    RETURN_NAMES = ("file_path", "frame_count", "fps")
    FUNCTION = "save"
    OUTPUT_NODE = True


class TrueAPNGSaveVideo(_APNGOutput):
    DESCRIPTION = (
        "Export native ComfyUI VIDEO as animated APNG. "
        "Automatic FPS, looping and transparency. APNG does not contain audio."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video": ("VIDEO",),
                "fps_mode": (["source", "manual"], {
                    "default": "source",
                    "tooltip": "source uses the video frame rate; manual uses Manual FPS.",
                }),
                "manual_fps": ("FLOAT", {"default": 24.0, "min": 0.01, "max": 1000.0, "step": 0.01}),
                **_common_inputs(),
            },
            "optional": _optional_inputs(),
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    def save(self, video, fps_mode="source", manual_fps=24.0,
             filename_prefix="APNG/ComfyUI", loop=0, compress_level=6,
             max_side=0, verify_file=True, include_metadata=True,
             mask=None, prompt=None, extra_pnginfo=None, quality=100, resize_method="lanczos", optimize_frames=True, optimization_tolerance=0, preview=True, trim_start=0, trim_end=0):
        if fps_mode not in ("source", "manual"):
            raise ValueError("fps_mode doit être source ou manual.")
        if not callable(getattr(video, "get_components", None)):
            raise ValueError(
                "Entrée VIDEO ComfyUI attendue. Pour une sortie IMAGE, utilisez Save APNG (Images). "
                "Pour un MP4, utilisez d'abord Load Video.",
            )
        _interrupt()
        components = video.get_components()
        images = getattr(components, "images", None)
        if images is None:
            raise ValueError("La vidéo ne contient aucune image exploitable.")
        fps = getattr(components, "frame_rate", None) if fps_mode == "source" else manual_fps
        if fps is None:
            raise ValueError("Cadence de la vidéo indisponible : choisissez fps_mode = manual.")
        return _export(
            images, fps, filename_prefix, loop, compress_level, max_side,
            verify_file, include_metadata, mask, prompt, extra_pnginfo, quality, resize_method, optimize_frames, optimization_tolerance, preview, trim_start, trim_end,
        )


class TrueAPNGSaveImages(_APNGOutput):
    DESCRIPTION = (
        "Export an IMAGE batch as animated APNG in frame order. "
        "Set FPS to the desired playback rate."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "fps": ("FLOAT", {"default": 24.0, "min": 0.01, "max": 1000.0, "step": 0.01}),
                **_common_inputs(),
            },
            "optional": _optional_inputs(),
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    def save(self, images, fps=24.0, filename_prefix="APNG/ComfyUI", loop=0,
             compress_level=6, max_side=0, verify_file=True, include_metadata=True,
             mask=None, prompt=None, extra_pnginfo=None, quality=100, resize_method="lanczos", optimize_frames=True, optimization_tolerance=0, preview=True, trim_start=0, trim_end=0):
        return _export(
            images, fps, filename_prefix, loop, compress_level, max_side,
            verify_file, include_metadata, mask, prompt, extra_pnginfo, quality, resize_method, optimize_frames, optimization_tolerance, preview, trim_start, trim_end,
        )


NODE_CLASS_MAPPINGS = {
    "TrueAPNGSaveVideo": TrueAPNGSaveVideo,
    "TrueAPNGSaveImages": TrueAPNGSaveImages,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TrueAPNGSaveVideo": "Save APNG (Video)",
    "TrueAPNGSaveImages": "Save APNG (Images)",
}
