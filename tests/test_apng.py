"""Functional export tests, with a minimal ComfyUI host double.

Run from the extension directory: python -m unittest discover -s tests -v
Pillow is also used as an independent decoder of the assembled APNG container.
"""

import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zlib
from fractions import Fraction

import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from apng_encoder import PNG_SIGNATURE, frame_delay, verify_apng, write_apng


def chunks(data):
    offset = 8
    while offset < len(data):
        length, kind = struct.unpack(">I4s", data[offset:offset + 8])
        yield kind, data[offset + 8:offset + 8 + length]
        offset += length + 12


class EncoderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "animation.apng"

    def save(self, frames, fps=24, loop=0, **kwargs):
        with self.path.open("wb") as stream:
            write_apng(stream, iter(frames), len(frames), fps, loop=loop, **kwargs)
        return verify_apng(self.path, len(frames), loop, frame_delay(fps))

    def test_rgb_frames_are_lossless_and_ordered(self):
        frames = [Image.new("RGB", (21, 13), color) for color in ("red", "green", "blue")]
        info = self.save(frames, fps=15)
        self.assertEqual(info["duration"], Fraction(1, 5))
        with Image.open(self.path) as image:
            for index, original in enumerate(frames):
                image.seek(index)
                np.testing.assert_array_equal(np.asarray(image.convert("RGB")), np.asarray(original))

    def test_identical_frames_remain_separate(self):
        frames = [Image.new("RGB", (8, 8), "orange")] * 5
        info = self.save(frames, fps=Fraction(30000, 1001))
        self.assertEqual(info["frames"], 5)
        self.assertEqual(info["fps"], Fraction(30000, 1001))

    def test_optimized_rectangles_decode_identically(self):
        for mode in ("RGB", "RGBA"):
            for optimize in (False, True):
                with self.subTest(mode=mode, optimize=optimize):
                    frames = []
                    for x in (1, 9, 9, 25, 2):
                        image = Image.new(mode, (48, 32), (0, 0, 0, 0) if mode == "RGBA" else (20, 30, 40))
                        tile = Image.new(mode, (6, 6), (255, 100, 20, 127) if mode == "RGBA" else (255, 100, 20))
                        image.paste(tile, (x, 10))
                        frames.append(image)
                    self.save(frames, fps=Fraction(30000, 1001), loop=2, optimize_frames=optimize)
                    with Image.open(self.path) as decoded:
                        for index, original in enumerate(frames):
                            decoded.seek(index)
                            np.testing.assert_array_equal(np.asarray(decoded.convert(mode)), np.asarray(original))
                    if optimize:
                        sizes = [struct.unpack(">IIIIIHHBB", data)[1:3] for kind, data in chunks(self.path.read_bytes()) if kind == b"fcTL"]
                        self.assertTrue(any(w < 48 or h < 32 for w, h in sizes[1:]))

    def test_delta_detects_rgb_changes_with_unchanged_alpha(self):
        frames = [Image.new("RGBA", (32, 32), (0, 0, 0, 127)) for _ in range(2)]
        frames[1].putpixel((17, 12), (255, 20, 30, 127))
        self.save(frames, optimize_frames=True)
        with Image.open(self.path) as decoded:
            decoded.seek(1)
            np.testing.assert_array_equal(np.asarray(decoded), np.asarray(frames[1]))

    def test_identical_optimized_frames_keep_count_and_duration(self):
        frames = [Image.new("RGBA", (64, 64), (20, 40, 80, 90))] * 5
        info = self.save(frames, fps=15, optimize_frames=True)
        self.assertEqual(info["frames"], 5)
        self.assertEqual(info["duration"], Fraction(1, 3))

    def test_optimization_saves_space_on_static_textured_background(self):
        background = np.random.default_rng(66).integers(0, 256, (64, 96, 3), dtype=np.uint8)
        frames = []
        for x in (0, 5, 10, 15):
            image = Image.fromarray(background.copy())
            image.paste(Image.new("RGB", (4, 4), "red"), (x, 20))
            frames.append(image)
        self.save(frames, optimize_frames=False)
        full_size = self.path.stat().st_size
        self.save(frames, optimize_frames=True)
        self.assertLess(self.path.stat().st_size, full_size // 2)

    def test_animation_control_precedes_large_metadata(self):
        metadata = PngInfo()
        metadata.add_text("workflow", "x" * 20000)
        self.save([Image.new("RGB", (8, 8), c) for c in ("red", "blue")], pnginfo=metadata)
        kinds = [kind for kind, _ in chunks(self.path.read_bytes())]
        self.assertEqual(kinds[:2], [b"IHDR", b"acTL"])

    def test_accuracy_100_matches_exact_default_bytes(self):
        frames = [Image.new("RGB", (16, 16), (v, 80, 100)) for v in (100, 110, 130)]
        self.save(frames, optimize_frames=True)
        original = self.path.read_bytes()
        self.save(frames, optimize_frames=True, optimization_accuracy=100)
        self.assertEqual(self.path.read_bytes(), original)

    def test_accuracy_zero_threshold_boundary(self):
        frames = [Image.new("RGB", (16, 16), (100, 100, 100)) for _ in range(2)]
        frames[1].putpixel((3, 3), (125, 100, 100))
        frames[1].putpixel((12, 12), (126, 100, 100))
        self.save(frames, optimize_frames=True, optimization_accuracy=0)
        with Image.open(self.path) as decoded:
            decoded.seek(1)
            self.assertEqual(decoded.getpixel((3, 3)), (100, 100, 100))
            self.assertEqual(decoded.getpixel((12, 12)), (126, 100, 100))

    def test_accuracy_middle_uses_five_percent_threshold(self):
        frames = [Image.new("RGB", (16, 16), (100, 100, 100)) for _ in range(2)]
        frames[1].putpixel((3, 3), (112, 100, 100))
        frames[1].putpixel((12, 12), (113, 100, 100))
        self.save(frames, optimize_frames=True, optimization_accuracy=50)
        with Image.open(self.path) as decoded:
            decoded.seek(1)
            self.assertEqual(decoded.getpixel((3, 3)), (100, 100, 100))
            self.assertEqual(decoded.getpixel((12, 12)), (113, 100, 100))

    def test_slow_color_drift_never_exceeds_tolerance(self):
        frames = [Image.new("RGB", (8, 8), (80 + i, 80 + i, 80 + i)) for i in range(61)]
        self.save(frames, optimize_frames=True, optimization_accuracy=0)
        with Image.open(self.path) as decoded:
            for index, source in enumerate(frames):
                decoded.seek(index)
                error = np.abs(np.array(decoded).astype(int) - np.array(source).astype(int))
                self.assertLessEqual(error.max(), 25)
            self.assertGreater(decoded.getpixel((0, 0))[0], 80)

    def test_tolerance_never_ignores_alpha_changes(self):
        frames = [Image.new("RGBA", (16, 16), (100, 100, 100, alpha)) for alpha in (128, 129, 0, 1, 255)]
        self.save(frames, optimize_frames=True, optimization_accuracy=0)
        with Image.open(self.path) as decoded:
            for index, source in enumerate(frames):
                decoded.seek(index)
                np.testing.assert_array_equal(np.array(decoded)[..., 3], np.array(source)[..., 3])

    def test_tolerance_is_ignored_without_frame_optimization(self):
        frames = [Image.new("RGB", (16, 16), (v, v, v)) for v in (100, 105, 110)]
        self.save(frames, optimize_frames=False, optimization_accuracy=0)
        with Image.open(self.path) as decoded:
            for index, source in enumerate(frames):
                decoded.seek(index)
                np.testing.assert_array_equal(np.array(decoded), np.array(source))

    def test_tolerance_is_rejected_when_it_does_not_save_space(self):
        frames = [Image.new("RGB", (1, 1), (v, v, v)) for v in (100, 110)]
        self.save(frames, optimize_frames=True, optimization_accuracy=0)
        with Image.open(self.path) as decoded:
            decoded.seek(1)
            self.assertEqual(decoded.getpixel((0, 0)), (110, 110, 110))

    def test_direct_zero_percent_matches_exact_encoder(self):
        frames = [Image.new("RGB", (16, 16), (v, 80, 100)) for v in (10, 100, 255)]
        self.save(frames, optimize_frames=True)
        exact = self.path.read_bytes()
        self.save(frames, optimize_frames=True, optimization_tolerance=0)
        self.assertEqual(self.path.read_bytes(), exact)

    def test_subpixel_thresholds_produce_exact_output(self):
        frames = [Image.new("RGB", (16, 16), (v, 80, 100)) for v in (100, 101, 102)]
        self.save(frames, optimize_frames=True, optimization_tolerance=0)
        exact = self.path.read_bytes()
        for tolerance in (0.1, 0.2, 0.3):
            self.save(frames, optimize_frames=True, optimization_tolerance=tolerance)
            self.assertEqual(self.path.read_bytes(), exact)

    def test_direct_full_percent_allows_full_rgb_difference(self):
        frames = [Image.new("RGB", (32, 32), color) for color in ("black", "white")]
        self.save(frames, optimize_frames=True, optimization_tolerance=100)
        with Image.open(self.path) as im:
            im.seek(1)
            self.assertEqual(im.getpixel((0, 0)), (0, 0, 0))

    def test_direct_half_percent_range_has_correct_boundary(self):
        frames = [Image.new("RGB", (16, 16), (0, 0, 0)) for _ in range(2)]
        frames[1].putpixel((3, 3), (127, 0, 0))
        frames[1].putpixel((12, 12), (128, 0, 0))
        self.save(frames, optimize_frames=True, optimization_tolerance=50)
        with Image.open(self.path) as im:
            im.seek(1)
            self.assertEqual(im.getpixel((3, 3)), (0, 0, 0))
            self.assertEqual(im.getpixel((12, 12)), (128, 0, 0))

    def test_direct_full_tolerance_keeps_alpha_exact(self):
        frames = [Image.new("RGBA", (32, 32), (value, value, value, alpha)) for value, alpha in ((0, 128), (255, 129), (0, 0), (255, 255))]
        self.save(frames, optimize_frames=True, optimization_tolerance=100)
        with Image.open(self.path) as im:
            for index, source in enumerate(frames):
                im.seek(index)
                np.testing.assert_array_equal(np.array(im)[..., 3], np.array(source)[..., 3])

    def test_fractional_direct_tolerance_matches_previous_scale(self):
        frames = [Image.new("RGB", (32, 32), (v, v, v)) for v in (100, 104, 105, 110)]
        self.save(frames, optimize_frames=True, optimization_accuracy=83)
        previous = self.path.read_bytes()
        self.save(frames, optimize_frames=True, optimization_tolerance=1.7)
        self.assertEqual(self.path.read_bytes(), previous)

    def test_lossless_compression_search_never_increases_file_size(self):
        rng = np.random.default_rng(44)
        for mode in ("RGB", "RGBA"):
            frames = [Image.fromarray(rng.integers(0, 256, (40, 56, 3 if mode == "RGB" else 4), dtype=np.uint8)) for _ in range(3)]
            self.save(frames, optimize_frames=False)
            baseline = self.path.stat().st_size
            self.save(frames, optimize_frames=True)
            self.assertLessEqual(self.path.stat().st_size, baseline)
            with Image.open(self.path) as decoded:
                for index, original in enumerate(frames):
                    decoded.seek(index)
                    np.testing.assert_array_equal(np.array(decoded), np.array(original))

    def test_invalid_accuracy_is_rejected(self):
        for accuracy in (-1, 101, 2.5, "50"):
            with self.subTest(accuracy=accuracy):
                with self.assertRaisesRegex(ValueError, "optimization_accuracy"):
                    self.save([Image.new("RGB", (8, 8))] * 2, optimization_accuracy=accuracy)

    def test_rgba_source_frames_clear_previous_pixels(self):
        frames = []
        for x in (1, 6, 11):
            array = np.zeros((5, 16, 4), dtype=np.uint8)
            array[1:4, x:x + 3] = [255, 100, 20, 128]
            frames.append(Image.fromarray(array))
        self.save(frames)
        with Image.open(self.path) as image:
            for index, original in enumerate(frames):
                image.seek(index)
                np.testing.assert_array_equal(np.asarray(image.convert("RGBA")), np.asarray(original))

    def test_infinite_and_finite_play_counts(self):
        frames = [Image.new("RGB", (8, 8), c) for c in ("red", "blue")]
        for loop in (0, 1, 2, 9):
            with self.subTest(loop=loop):
                self.save(frames, loop=loop)
                with Image.open(self.path) as image:
                    self.assertEqual(image.info["loop"], loop)

    def test_metadata_survives(self):
        metadata = PngInfo()
        metadata.add_text("workflow", json.dumps({"texte": "féérique"}, ensure_ascii=False))
        self.save([Image.new("RGB", (8, 8), c) for c in ("red", "blue")], pnginfo=metadata)
        with Image.open(self.path) as image:
            self.assertEqual(json.loads(image.info["workflow"])["texte"], "féérique")

    def test_large_multichunk_frame(self):
        rng = np.random.default_rng(17)
        frames = [Image.fromarray(rng.integers(0, 256, (192, 256, 4), dtype=np.uint8)) for _ in range(3)]
        self.save(frames, compress_level=0)
        kinds = [kind for kind, _ in chunks(self.path.read_bytes())]
        self.assertGreater(kinds.count(b"fdAT"), 2)
        with Image.open(self.path) as image:
            for index, original in enumerate(frames):
                image.seek(index)
                np.testing.assert_array_equal(np.asarray(image), np.asarray(original))

    def test_compression_levels_preserve_pixels(self):
        frames = [Image.new("RGB", (10, 10), c) for c in ("red", "blue")]
        for level in (0, 6, 9):
            with self.subTest(level=level):
                self.save(frames, compress_level=level)

    def test_exact_fractional_and_integer_rates(self):
        for rate in (15, 24, 25, 30, 60, Fraction(30000, 1001), Fraction(60000, 1001), 0.01, 1000):
            with self.subTest(rate=rate):
                self.assertEqual(frame_delay(rate), 1 / Fraction(str(rate)))

    def test_approximate_rate_stays_within_apng_limits(self):
        delay = frame_delay(23.123456789)
        self.assertLessEqual(delay.denominator, 65535)
        self.assertLess(abs(float(1 / delay) - 23.123456789), 0.00001)

    def test_invalid_rates_are_rejected(self):
        for rate in (0, -1, float("nan"), float("inf"), None, "abc", 1001):
            with self.subTest(rate=rate):
                with self.assertRaises(ValueError):
                    frame_delay(rate)

    def test_one_frame_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "au moins 2"):
            write_apng(io.BytesIO(), [Image.new("RGB", (8, 8))], 1, 24)

    def test_missing_frames_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "manquantes"):
            write_apng(io.BytesIO(), [Image.new("RGB", (8, 8))], 2, 24)

    def test_extra_frames_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Trop d'images"):
            write_apng(io.BytesIO(), [Image.new("RGB", (8, 8))] * 3, 2, 24)

    def test_mismatched_size_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "même taille"):
            write_apng(io.BytesIO(), [Image.new("RGB", s) for s in ((8, 8), (9, 8))], 2, 24)

    def test_crc_damage_is_detected(self):
        self.save([Image.new("RGB", (8, 8), c) for c in ("red", "blue")])
        data = bytearray(self.path.read_bytes())
        data[20] ^= 1
        self.path.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "CRC"):
            verify_apng(self.path)

    def test_bad_sequence_is_detected_even_with_correct_crc(self):
        self.save([Image.new("RGB", (8, 8), c) for c in ("red", "blue")])
        rebuilt = bytearray(PNG_SIGNATURE)
        for kind, payload in chunks(self.path.read_bytes()):
            if kind == b"fdAT":
                payload = struct.pack(">I", 999) + payload[4:]
            rebuilt.extend(struct.pack(">I", len(payload)) + kind + payload)
            rebuilt.extend(struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))
        self.path.write_bytes(rebuilt)
        with self.assertRaisesRegex(ValueError, "Ordre"):
            verify_apng(self.path)

    def test_truncation_is_detected(self):
        self.save([Image.new("RGB", (8, 8), c) for c in ("red", "blue")])
        self.path.write_bytes(self.path.read_bytes()[:-8])
        with self.assertRaisesRegex(ValueError, "tronqué"):
            verify_apng(self.path)


class TensorDouble:
    """The exact conversion methods used on a real torch image tensor."""
    def __init__(self, array):
        self.array = array
        self.shape = array.shape

    def __getitem__(self, index):
        return TensorDouble(self.array[index])

    def detach(self):
        return self

    def cpu(self):
        return self

    def float(self):
        self.array = self.array.astype(np.float32)
        return self

    def numpy(self):
        return self.array


class NodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.host_modules = {}
        folder_paths = types.ModuleType("folder_paths")
        cls.folder_paths = folder_paths
        comfy = types.ModuleType("comfy")
        cli_args = types.ModuleType("comfy.cli_args")
        cls.args = types.SimpleNamespace(disable_metadata=False)
        cli_args.args = cls.args
        management = types.ModuleType("comfy.model_management")
        management.throw_exception_if_processing_interrupted = lambda: None
        utils = types.ModuleType("comfy.utils")

        class ProgressBar:
            def __init__(self, total):
                self.total = total

            def update_absolute(self, value):
                pass

        utils.ProgressBar = ProgressBar
        for module in (folder_paths, comfy, cli_args, management, utils):
            cls.host_modules[module.__name__] = module
        cls.module_patch = patch.dict(sys.modules, cls.host_modules)
        cls.module_patch.start()
        spec = importlib.util.spec_from_file_location(
            "true_apng_test", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)],
        )
        cls.package = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.package
        spec.loader.exec_module(cls.package)
        cls.nodes = sys.modules["true_apng_test.nodes"]

    @classmethod
    def tearDownClass(cls):
        cls.module_patch.stop()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)
        self.folder_paths.get_output_directory = lambda: str(self.output)
        def save_path(prefix, directory, width, height):
            full_prefix = Path(directory) / prefix
            full_prefix.parent.mkdir(parents=True, exist_ok=True)
            return str(full_prefix.parent), full_prefix.name, 1, str(Path(prefix).parent), prefix
        self.folder_paths.get_save_image_path = save_path
        self.args.disable_metadata = False
        self.images = np.zeros((4, 12, 20, 3), dtype=np.float32)
        self.images[1, ..., 0] = 1
        self.images[2, ..., 1] = 1
        self.images[3, ..., 2] = 1

    def save_images(self, **kwargs):
        return self.nodes.TrueAPNGSaveImages().save(self.images, **kwargs)

    def test_both_node_classes_load_and_declare_valid_inputs(self):
        self.assertEqual(len(self.package.NODE_CLASS_MAPPINGS), 2)
        for node in self.package.NODE_CLASS_MAPPINGS.values():
            schema = node.INPUT_TYPES()
            self.assertIn("required", schema)
            self.assertTrue(node.OUTPUT_NODE)
            self.assertEqual(node.RETURN_TYPES, ("STRING", "INT", "FLOAT"))

    def test_resize_method_is_directly_below_maximum_side(self):
        for cls in self.package.NODE_CLASS_MAPPINGS.values():
            schema = cls.INPUT_TYPES()
            names = list({**schema["required"], **schema["optional"]})
            self.assertEqual(names.index("resize_method"), names.index("max_side") + 1)

    def test_locale_files_cover_all_nodes_and_inputs(self):
        expected_languages = {"en", "fr", "de", "es", "it", "ja"}
        self.assertEqual({p.name for p in (ROOT / "locales").iterdir()}, expected_languages)
        for lang in expected_languages:
            data = json.loads((ROOT / "locales" / lang / "nodeDefs.json").read_text())
            self.assertEqual(set(data), set(self.package.NODE_CLASS_MAPPINGS))
            for name, cls in self.package.NODE_CLASS_MAPPINGS.items():
                schema = cls.INPUT_TYPES()
                inputs = {**schema["required"], **schema["optional"]}
                self.assertEqual(set(data[name]["inputs"]), set(inputs))
                self.assertEqual(set(data[name]["outputs"]), {"0", "1", "2"})
                self.assertTrue(data[name]["display_name"])
                self.assertTrue(data[name]["description"])
                for slot in data[name]["inputs"].values():
                    self.assertTrue(slot["name"])
                    self.assertTrue(slot["tooltip"])

    def test_english_backend_tooltips_match_english_locale(self):
        data = json.loads((ROOT / "locales/en/nodeDefs.json").read_text())
        for name, cls in self.package.NODE_CLASS_MAPPINGS.items():
            schema = cls.INPUT_TYPES()
            for key, spec in {**schema["required"], **schema["optional"]}.items():
                if len(spec) > 1 and "tooltip" in spec[1]:
                    self.assertEqual(spec[1]["tooltip"], data[name]["inputs"][key]["tooltip"])

    def test_images_export_returns_animated_ui_and_real_file(self):
        result = self.save_images(fps=15, loop=2)
        path, frames, rate = result["result"]
        self.assertTrue(Path(path).suffix == ".apng")
        self.assertEqual((frames, rate), (4, 15.0))
        self.assertEqual(len(result["ui"]["true_apng_preview"]), 1)
        self.assertNotIn("animated", result["ui"])
        self.assertNotIn("images", result["ui"])
        self.assertEqual(verify_apng(path)["loop"], 2)

    def test_torch_conversion_protocol(self):
        result = self.nodes.TrueAPNGSaveImages().save(TensorDouble(self.images))
        self.assertEqual(verify_apng(result["result"][0])["frames"], 4)

    def test_video_uses_source_fractional_fps(self):
        components = types.SimpleNamespace(images=TensorDouble(self.images), frame_rate=Fraction(30000, 1001), audio=None)
        video = types.SimpleNamespace(get_components=lambda: components)
        result = self.nodes.TrueAPNGSaveVideo().save(video)
        self.assertEqual(verify_apng(result["result"][0])["fps"], Fraction(30000, 1001))

    def test_manual_fps_overrides_video_rate(self):
        video = types.SimpleNamespace(get_components=lambda: types.SimpleNamespace(images=self.images, frame_rate=60))
        result = self.nodes.TrueAPNGSaveVideo().save(video, fps_mode="manual", manual_fps=15)
        self.assertEqual(result["result"][2], 15.0)

    def test_wrong_video_type_has_actionable_error(self):
        with self.assertRaisesRegex(ValueError, "Load Video"):
            self.nodes.TrueAPNGSaveVideo().save("movie.mp4")

    def test_resize_preserves_proportions(self):
        result = self.save_images(max_side=10)
        self.assertEqual(verify_apng(result["result"][0])["size"], (10, 6))

    def test_resize_never_upscales(self):
        result = self.save_images(max_side=100)
        self.assertEqual(verify_apng(result["result"][0])["size"], (20, 12))

    def test_resize_methods_export_rgb_and_rgba(self):
        for channels in (3, 4):
            self.images = np.random.default_rng(31).random((3, 64, 96, channels), dtype=np.float32)
            for method in self.nodes.RESIZE_METHODS:
                with self.subTest(channels=channels, method=method):
                    result = self.save_images(max_side=17, resize_method=method)
                    info = verify_apng(result["result"][0])
                    self.assertEqual(info["size"], (17, 11))
                    self.assertEqual(info["frames"], 3)

    def test_default_resize_preserves_previous_result(self):
        image = Image.fromarray(np.random.default_rng(4).integers(0, 256, (64, 96, 4), dtype=np.uint8))
        expected = image.resize((17, 11), Image.Resampling.LANCZOS)
        actual = self.nodes._resize_image(image, (17, 11), "lanczos")
        np.testing.assert_array_equal(np.asarray(actual), np.asarray(expected))

    def test_box_and_progressive_filter_checkerboard_aliasing(self):
        checker = (np.indices((128, 128)).sum(axis=0) % 2 * 255).astype(np.uint8)
        image = Image.fromarray(np.repeat(checker[..., None], 3, axis=-1))
        for method in ("box", "lanczos_progressive"):
            with self.subTest(method=method):
                pixels = np.asarray(self.nodes._resize_image(image, (8, 8), method))
                self.assertLessEqual(np.abs(pixels.astype(float) - 127.5).max(), 1)

    def test_resizing_transparency_does_not_add_color_halos(self):
        pixels = np.zeros((64, 64, 4), dtype=np.uint8)
        pixels[..., :3] = [255, 255, 255]  # Invisible white outside the subject.
        pixels[16:48, 16:48] = [255, 0, 0, 255]
        for method in self.nodes.RESIZE_METHODS:
            with self.subTest(method=method):
                resized = np.asarray(self.nodes._resize_image(Image.fromarray(pixels), (9, 9), method))
                visible = resized[..., 3] > 0
                self.assertTrue((resized[..., 3] == 0).any())
                self.assertTrue(visible.any())
                self.assertEqual(resized[..., 1:3][visible].max(), 0)

    def test_invalid_resize_method_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "resize_method"):
            self.save_images(resize_method="unknown")

    def test_video_accepts_resize_method(self):
        video = types.SimpleNamespace(get_components=lambda: types.SimpleNamespace(images=self.images, frame_rate=15))
        result = self.nodes.TrueAPNGSaveVideo().save(video, max_side=10, resize_method="box")
        self.assertEqual(verify_apng(result["result"][0])["size"], (10, 6))

    def test_single_mask_broadcasts_with_comfy_convention(self):
        mask = np.zeros((1, 12, 20), dtype=np.float32)
        mask[..., :10] = 1
        result = self.save_images(mask=mask)
        with Image.open(result["result"][0]) as image:
            for index in range(4):
                image.seek(index)
                self.assertEqual(image.getpixel((0, 0))[3], 0)
                self.assertEqual(image.getpixel((15, 0))[3], 255)

    def test_animated_masks_and_existing_alpha_combine(self):
        self.images = np.ones((4, 12, 20, 4), dtype=np.float32)
        self.images[..., 3] = 0.5
        mask = np.zeros((4, 12, 20), dtype=np.float32)
        mask[1] = 1
        result = self.save_images(mask=mask)
        with Image.open(result["result"][0]) as image:
            image.seek(0)
            self.assertEqual(image.getpixel((0, 0))[3], 128)
            image.seek(1)
            self.assertEqual(image.getpixel((0, 0))[3], 0)
            image.seek(2)
            self.assertEqual(image.getpixel((0, 0))[3], 128)

    def test_bad_mask_is_rejected_without_creating_file(self):
        with self.assertRaisesRegex(ValueError, "Masque"):
            self.save_images(mask=np.zeros((2, 12, 20)))
        self.assertEqual(list(self.output.rglob("*.apng")), [])

    def test_counter_never_overwrites_an_existing_export(self):
        first = self.save_images()["result"][0]
        first_bytes = Path(first).read_bytes()
        second = self.save_images()["result"][0]
        self.assertNotEqual(first, second)
        self.assertEqual(Path(first).read_bytes(), first_bytes)

    def test_workflow_metadata_and_global_disable(self):
        metadata = {"workflow": {"id": "test"}}
        first = self.save_images(prompt={"test": "é"}, extra_pnginfo=metadata)
        with Image.open(first["result"][0]) as image:
            self.assertEqual(json.loads(image.info["prompt"]), {"test": "é"})
            self.assertEqual(json.loads(image.info["workflow"]), {"id": "test"})
        self.args.disable_metadata = True
        second = self.save_images(prompt={"test": "é"}, extra_pnginfo=metadata)
        with Image.open(second["result"][0]) as image:
            self.assertNotIn("workflow", image.info)
            self.assertNotIn("prompt", image.info)

    def test_metadata_can_be_disabled_in_node(self):
        result = self.save_images(include_metadata=False, prompt={"test": 1})
        with Image.open(result["result"][0]) as image:
            self.assertNotIn("prompt", image.info)

    def test_failure_after_first_frame_removes_all_partial_files(self):
        self.images[1, 0, 0, 0] = float("nan")
        with self.assertRaisesRegex(ValueError, "pixels invalides"):
            self.save_images()
        self.assertEqual([path for path in self.output.rglob("*") if path.is_file()], [])

    def test_cancellation_removes_all_partial_files(self):
        calls = 0
        class Cancelled(Exception):
            pass
        def interrupt():
            nonlocal calls
            calls += 1
            if calls >= 6:
                raise Cancelled()
        with patch.object(self.nodes, "_interrupt", interrupt):
            with self.assertRaises(Cancelled):
                self.save_images()
        self.assertEqual([path for path in self.output.rglob("*") if path.is_file()], [])

    def test_verification_failure_does_not_publish_a_file(self):
        with patch.object(self.nodes, "verify_apng", side_effect=ValueError("test verifier failure")):
            with self.assertRaisesRegex(ValueError, "verifier failure"):
                self.save_images()
        self.assertEqual([path for path in self.output.rglob("*") if path.is_file()], [])

    def test_verification_can_be_skipped(self):
        with patch.object(self.nodes, "verify_apng", side_effect=AssertionError("unexpected")):
            result = self.save_images(verify_file=False)
        self.assertEqual(verify_apng(result["result"][0])["frames"], 4)

    def test_preview_can_be_disabled_without_affecting_export(self):
        result = self.save_images(preview=False)
        self.assertEqual(result["ui"]["true_apng_preview"], [])
        self.assertEqual(verify_apng(result["result"][0])["frames"], 4)

    def test_trim_both_ends_preserves_correct_frames_and_fps(self):
        result = self.save_images(trim_start=1, trim_end=1, fps=15)
        info = verify_apng(result["result"][0])
        self.assertEqual(result["result"][1:], (2, 15.0))
        self.assertEqual(info["duration"], Fraction(2, 15))
        with Image.open(result["result"][0]) as im:
            for index, source_index in enumerate((1, 2)):
                im.seek(index)
                expected = np.rint(self.images[source_index] * 255).astype(np.uint8)
                np.testing.assert_array_equal(np.asarray(im.convert("RGB")), expected)

    def test_trim_zero_preserves_default_export(self):
        first = self.save_images()["result"][0]
        second = self.save_images(trim_start=0, trim_end=0)["result"][0]
        self.assertEqual(Path(first).read_bytes(), Path(second).read_bytes())

    def test_trim_only_start_or_end(self):
        for start, end, first_index in ((1, 0, 1), (0, 1, 0)):
            result = self.save_images(trim_start=start, trim_end=end)
            self.assertEqual(result["result"][1], 3)
            with Image.open(result["result"][0]) as im:
                np.testing.assert_array_equal(np.array(im.convert("RGB")), np.rint(self.images[first_index] * 255).astype(np.uint8))

    def test_trim_slices_animated_mask_with_the_images(self):
        mask = np.zeros((4, 12, 20), dtype=np.float32)
        for index in range(4):
            mask[index] = index / 4
        result = self.save_images(mask=mask, trim_start=1, trim_end=1)
        with Image.open(result["result"][0]) as im:
            self.assertEqual(im.getpixel((0, 0))[3], 191)
            im.seek(1)
            self.assertEqual(im.getpixel((0, 0))[3], 128)

    def test_trim_preserves_fixed_mask(self):
        for mask in (np.full((1, 12, 20), 0.5), np.full((12, 20), 0.5)):
            result = self.save_images(mask=mask, trim_start=1, trim_end=1)
            with Image.open(result["result"][0]) as im:
                self.assertEqual(im.getpixel((0, 0))[3], 128)
                im.seek(1)
                self.assertEqual(im.getpixel((0, 0))[3], 128)

    def test_invalid_trim_does_not_create_output(self):
        for options in ({"trim_start": -1}, {"trim_end": 0.5}, {"trim_start": 3}, {"trim_start": 2, "trim_end": 2}, {"trim_end": 100}):
            with self.subTest(options=options):
                with self.assertRaises(ValueError):
                    self.save_images(**options)
        self.assertEqual(list(self.output.rglob("*.apng")), [])

    def test_video_trim_and_tensor_slices(self):
        video = types.SimpleNamespace(get_components=lambda: types.SimpleNamespace(images=TensorDouble(self.images), frame_rate=Fraction(30000, 1001)))
        result = self.nodes.TrueAPNGSaveVideo().save(video, trim_start=1, trim_end=1)
        info = verify_apng(result["result"][0])
        self.assertEqual(info["frames"], 2)
        self.assertEqual(info["fps"], Fraction(30000, 1001))

    def test_new_slider_defaults_to_zero_tolerance(self):
        for cls in self.package.NODE_CLASS_MAPPINGS.values():
            inputs = cls.INPUT_TYPES()["optional"]
            self.assertEqual(inputs["optimization_tolerance"][1]["default"], 0)
            self.assertEqual(inputs["trim_start"][1]["default"], 0)
            self.assertEqual(inputs["trim_end"][1]["default"], 0)
            self.assertNotIn("optimization_accuracy", inputs)

    def test_tolerance_uses_native_integer_slider_with_full_range(self):
        for cls in self.package.NODE_CLASS_MAPPINGS.values():
            kind, options = cls.INPUT_TYPES()["optional"]["optimization_tolerance"]
            self.assertEqual(kind, "INT")
            self.assertEqual(options["display"], "slider")
            self.assertEqual((options["min"], options["max"]), (0, 100))
            self.assertEqual(options["step"], 1)
            self.assertNotIn("round", options)

    def test_invalid_tolerance_is_rejected(self):
        for tolerance in (-1, 101, float("nan"), float("inf"), "50"):
            with self.assertRaisesRegex(ValueError, "optimization_tolerance"):
                self.save_images(optimization_tolerance=tolerance)

    def test_fractional_tolerance_is_accepted_by_node(self):
        result = self.save_images(optimization_tolerance=1.7)
        self.assertEqual(verify_apng(result["result"][0])["frames"], 4)

    def test_both_nodes_pass_accuracy_to_encoder(self):
        self.images = np.full((2, 12, 20, 3), 100, dtype=np.uint8)
        self.images[1] = 120
        video = types.SimpleNamespace(get_components=lambda: types.SimpleNamespace(images=self.images, frame_rate=24))
        results = [self.save_images(optimization_tolerance=100), self.nodes.TrueAPNGSaveVideo().save(video, optimization_tolerance=100)]
        for result in results:
            with Image.open(result["result"][0]) as decoded:
                decoded.seek(1)
                self.assertEqual(decoded.getpixel((0, 0)), (100, 100, 100))

    def test_quality_100_is_identical_to_default(self):
        self.images = np.random.default_rng(23).random((3, 24, 32, 4), dtype=np.float32)
        default = self.save_images()["result"][0]
        explicit = self.save_images(quality=100)["result"][0]
        self.assertEqual(Path(default).read_bytes(), Path(explicit).read_bytes())

    def test_quality_reduces_size_and_preserves_alpha_and_timing(self):
        self.images = np.random.default_rng(24).random((3, 64, 96, 4), dtype=np.float32)
        original = self.save_images(quality=100, fps=15, loop=2)["result"][0]
        reduced = self.save_images(quality=25, fps=15, loop=2)["result"][0]
        self.assertLess(Path(reduced).stat().st_size, Path(original).stat().st_size)
        info = verify_apng(reduced)
        self.assertEqual((info["frames"], info["fps"], info["loop"]), (3, 15, 2))
        with Image.open(original) as first, Image.open(reduced) as second:
            for index in range(3):
                first.seek(index)
                second.seek(index)
                a, b = np.asarray(first), np.asarray(second)
                np.testing.assert_array_equal(a[..., 3], b[..., 3])
                self.assertFalse(np.array_equal(a[..., :3], b[..., :3]))
                self.assertLessEqual(len(np.unique(b[..., :3])), 7)

    def test_quality_is_temporally_stable(self):
        image = Image.fromarray(np.random.default_rng(7).integers(0, 256, (12, 20, 3), dtype=np.uint8))
        a = self.nodes._quantize_rgb(image, 50)
        b = self.nodes._quantize_rgb(image.copy(), 50)
        np.testing.assert_array_equal(np.asarray(a), np.asarray(b))

    def test_invalid_quality_is_rejected(self):
        for quality in (0, 101, 50.5, "50"):
            with self.subTest(quality=quality):
                with self.assertRaisesRegex(ValueError, "quality"):
                    self.save_images(quality=quality)

    def test_video_quality_option(self):
        video = types.SimpleNamespace(get_components=lambda: types.SimpleNamespace(images=self.images, frame_rate=15))
        result = self.nodes.TrueAPNGSaveVideo().save(video, quality=50)
        self.assertEqual(verify_apng(result["result"][0])["frames"], 4)


if __name__ == "__main__":
    unittest.main()
