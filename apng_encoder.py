"""Small, streaming APNG writer. Pillow compresses each PNG frame.

The APNG container uses full frames or changed rectangles, SOURCE blending
and NONE disposal.
Identical frames are deliberately retained. No ffmpeg executable is required.
See https://www.w3.org/TR/png-3/ for the APNG chunk definitions.
"""

from __future__ import annotations

import io
import math
import struct
import zlib
from fractions import Fraction

from PIL import Image, ImageChops

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_UINT32 = 0xFFFFFFFF


def frame_delay(fps):
    """Return an APNG-representable delay, retaining rational source rates."""
    try:
        rate = fps if isinstance(fps, Fraction) else Fraction(str(fps))
        if not math.isfinite(float(rate)) or not Fraction(1, 100) <= rate <= 1000:
            raise ValueError
    except (ValueError, TypeError, ZeroDivisionError, OverflowError) as exc:
        raise ValueError("Les FPS doivent être compris entre 0,01 et 1000.") from exc
    delay = (1 / rate).limit_denominator(65535)
    if not 1 <= delay.numerator <= 65535:
        raise ValueError("Cette cadence ne peut pas être représentée en APNG.")
    return delay


def _write_chunk(stream, kind, data):
    stream.write(struct.pack(">I", len(data)))
    stream.write(kind)
    stream.write(data)
    crc = zlib.crc32(data, zlib.crc32(kind)) & MAX_UINT32
    stream.write(struct.pack(">I", crc))


def _read_chunks(stream):
    if stream.read(8) != PNG_SIGNATURE:
        raise ValueError("Signature PNG invalide.")
    while True:
        header = stream.read(8)
        if len(header) != 8:
            raise ValueError("Fichier PNG tronqué : en-tête manquant.")
        length, kind = struct.unpack(">I4s", header)
        if length > 0x7FFFFFFF:
            raise ValueError("Bloc PNG trop long.")
        data = stream.read(length)
        crc_bytes = stream.read(4)
        if len(data) != length or len(crc_bytes) != 4:
            raise ValueError("Fichier PNG tronqué : bloc incomplet.")
        actual_crc = zlib.crc32(data, zlib.crc32(kind)) & MAX_UINT32
        if actual_crc != struct.unpack(">I", crc_bytes)[0]:
            raise ValueError(f"CRC PNG invalide dans {kind!r}.")
        yield kind, data
        if kind == b"IEND":
            if data or stream.read(1):
                raise ValueError("Fin de fichier PNG invalide.")
            return


def write_apng(
    stream,
    frames,
    frame_count,
    fps,
    loop=0,
    compress_level=6,
    pnginfo=None,
    on_frame=None,
    optimize_frames=False,
    optimization_accuracy=100,
    optimization_tolerance=None,
):
    """Write all frames to an open binary stream; return the encoded delay.

    A previous frame and candidate compressed frames may be buffered. The caller owns stream lifetime
    and atomic publication. on_frame(completed, total) may cancel by raising.
    """
    if not 2 <= frame_count <= MAX_UINT32:
        raise ValueError("Une animation APNG nécessite au moins 2 images.")
    if not isinstance(loop, int) or not 0 <= loop <= MAX_UINT32:
        raise ValueError("Le nombre de lectures doit être un entier positif ou nul.")
    if not isinstance(compress_level, int) or not 0 <= compress_level <= 9:
        raise ValueError("Le niveau de compression doit être compris entre 0 et 9.")
    if not isinstance(optimization_accuracy, int) or not 0 <= optimization_accuracy <= 100:
        raise ValueError("optimization_accuracy must be an integer from 0 to 100.")
    if optimization_tolerance is None:
        # Retain the legacy encoder API; public nodes use a direct percent.
        tolerance = (100 - optimization_accuracy) / 10
    else:
        if (not isinstance(optimization_tolerance, (int, float))
                or not math.isfinite(optimization_tolerance)
                or not 0 <= optimization_tolerance <= 100):
            raise ValueError("optimization_tolerance must be a finite number from 0 to 100.")
        tolerance = optimization_tolerance
    delay = frame_delay(fps)
    sequence = 0
    expected_header = None
    completed = 0
    size = None
    previous = None
    threshold = 255 * tolerance / 100

    def encode(image, metadata=None):
        with io.BytesIO() as buffer:
            image.save(buffer, format="PNG", compress_level=compress_level, pnginfo=metadata)
            buffer.seek(0)
            chunks = list(_read_chunks(buffer))
        if optimize_frames and compress_level > 0:
            original = b"".join(data for kind, data in chunks if kind == b"IDAT")
            filtered_rows = zlib.decompress(original)
            best = original
            for strategy in (zlib.Z_DEFAULT_STRATEGY, zlib.Z_FILTERED, zlib.Z_RLE):
                compressor = zlib.compressobj(compress_level, zlib.DEFLATED, 15, 9, strategy)
                candidate = compressor.compress(filtered_rows) + compressor.flush()
                if len(candidate) < len(best):
                    best = candidate
            if best is not original:
                rebuilt = []
                written = False
                for kind, data in chunks:
                    if kind == b"IDAT":
                        if not written:
                            rebuilt.extend((b"IDAT", best[i:i + 65536]) for i in range(0, len(best), 65536))
                            written = True
                    else:
                        rebuilt.append((kind, data))
                chunks = rebuilt
        return chunks

    def data_cost(chunks):
        return sum(len(data) + 16 for kind, data in chunks if kind == b"IDAT")

    for index, image in enumerate(frames):
        if index >= frame_count:
            raise ValueError("Trop d'images fournies à l'encodeur APNG.")
        if image.mode not in ("RGB", "RGBA"):
            raise ValueError("L'encodeur attend des images RGB ou RGBA 8 bits.")
        if on_frame:
            on_frame(index, frame_count)
        # Build the best exact candidate first. A lossy candidate is never
        # selected merely because a tolerance was requested.
        chunks = encode(image, pnginfo if index == 0 else None)
        header = chunks[0][1]
        if chunks[0][0] != b"IHDR":
            raise ValueError("L'en-tête PNG IHDR est manquant.")
        if index == 0:
            expected_header = header
            size = image.size
            stream.write(PNG_SIGNATURE)
            for kind, data in chunks:
                if kind == b"IDAT":
                    break
                if kind in (b"acTL", b"fcTL", b"fdAT", b"IEND"):
                    raise ValueError("Un bloc inattendu a été fourni par l'encodeur PNG.")
                _write_chunk(stream, kind, data)
                if kind == b"IHDR":
                    # Before large workflow metadata, so demuxers detect APNG.
                    _write_chunk(stream, b"acTL", struct.pack(">II", frame_count, loop))
        elif header != expected_header:
            raise ValueError("Toutes les images doivent avoir la même taille et le même mode.")


        def best_layout(candidate_image, candidate_chunks):
            box = (0, 0, candidate_image.width, candidate_image.height)
            if optimize_frames and previous is not None:
                boxes = [b for channel in ImageChops.difference(candidate_image, previous).split()
                         if (b := channel.getbbox()) is not None]
                changed = ((min(b[0] for b in boxes), min(b[1] for b in boxes),
                            max(b[2] for b in boxes), max(b[3] for b in boxes))
                           if boxes else (0, 0, 1, 1))
                if changed != box:
                    cropped = encode(candidate_image.crop(changed))
                    if data_cost(cropped) < data_cost(candidate_chunks):
                        return cropped, changed
            return candidate_chunks, box

        chunks, box = best_layout(image, chunks)
        if optimize_frames and previous is not None and threshold >= 1:
            diff = ImageChops.difference(image, previous)
            channels = diff.split()
            rgb_max = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]), channels[2])
            keep = rgb_max.point([255 if value <= threshold else 0 for value in range(256)])
            if image.mode == "RGBA":
                alpha_equal = channels[3].point([255] + [0] * 255)
                keep = ImageChops.multiply(keep, alpha_equal)
            tolerant_image = Image.composite(previous, image, keep)
            # Avoid a second PNG encoding when retaining pixels changed nothing.
            changed_by_tolerance = any(channel.getbbox() is not None
                                       for channel in ImageChops.difference(tolerant_image, image).split())
            if changed_by_tolerance:
                tolerant_chunks, tolerant_box = best_layout(tolerant_image, encode(tolerant_image))
                # Require at least a 1% reduction over the best exact representation.
                # The reference for the next frame is the image actually selected.
                if data_cost(tolerant_chunks) <= data_cost(chunks) * 0.99:
                    image, chunks, box = tolerant_image, tolerant_chunks, tolerant_box

        # SOURCE replaces the changed rectangle, including pixels that become
        # fully transparent. NONE disposal retains everything outside it.
        control = struct.pack(
            ">IIIIIHHBB",
            sequence, box[2] - box[0], box[3] - box[1], box[0], box[1],
            delay.numerator, delay.denominator, 0, 0,
        )
        _write_chunk(stream, b"fcTL", control)
        sequence += 1
        has_data = False
        for kind, data in chunks:
            if kind != b"IDAT":
                continue
            has_data = True
            if index == 0:
                _write_chunk(stream, b"IDAT", data)
            else:
                _write_chunk(stream, b"fdAT", struct.pack(">I", sequence) + data)
                sequence += 1
        if not has_data:
            raise ValueError("Une image PNG ne contient aucune donnée.")
        completed = index + 1
        if optimize_frames:
            previous = image.copy()
        if on_frame:
            on_frame(completed, frame_count)
    if completed != frame_count:
        raise ValueError(f"Images manquantes : {completed} reçues sur {frame_count}.")
    _write_chunk(stream, b"IEND", b"")
    return delay


def verify_apng(path, expected_frames=None, expected_loop=None, expected_delay=None,
                decode=True, on_frame=None):
    """Check CRCs, animation controls, sequence numbers and decoded frames."""
    controls = []
    animation = None
    sequence = 0
    size = None
    frame_has_data = False
    seen_idat = False
    with open(path, "rb") as stream:
        for kind, data in _read_chunks(stream):
            if on_frame:
                # Structure scanning checks cancellation but does not advance
                # decoding progress before the frames have actually loaded.
                on_frame(0, expected_frames or 0)
            if size is None and kind != b"IHDR":
                raise ValueError("IHDR doit être le premier bloc PNG.")
            if kind == b"IHDR":
                if size is not None or len(data) != 13:
                    raise ValueError("En-tête IHDR invalide.")
                width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", data)
                if not width or not height or depth != 8 or color not in (2, 6):
                    raise ValueError("Format d'image APNG inattendu.")
                if (compression, filtering, interlace) != (0, 0, 0):
                    raise ValueError("Méthode de compression PNG inattendue.")
                size = (width, height)
            elif kind == b"acTL":
                if animation is not None or controls or seen_idat or len(data) != 8:
                    raise ValueError("Contrôle d'animation acTL invalide.")
                animation = struct.unpack(">II", data)
            elif kind == b"fcTL":
                if animation is None or len(data) != 26 or (controls and not frame_has_data):
                    raise ValueError("Contrôle d'image fcTL invalide.")
                seq, width, height, x, y, num, den, disposal, blend = struct.unpack(">IIIIIHHBB", data)
                if seq != sequence:
                    raise ValueError("Ordre des images APNG invalide.")
                sequence += 1
                if (not width or not height or x + width > size[0] or y + height > size[1]
                        or (disposal, blend) != (0, 0)
                        or (not controls and (width, height, x, y) != (*size, 0, 0))):
                    raise ValueError("Dimensions ou composition APNG inattendues.")
                if num == 0 or den == 0:
                    raise ValueError("Durée d'image APNG invalide.")
                delay = Fraction(num, den)
                if expected_delay is not None and delay != expected_delay:
                    raise ValueError("La cadence APNG ne correspond pas à la cadence demandée.")
                controls.append(delay)
                frame_has_data = False
            elif kind == b"IDAT":
                if len(controls) != 1 or not data:
                    raise ValueError("Données de première image APNG invalides.")
                seen_idat = frame_has_data = True
            elif kind == b"fdAT":
                if len(controls) < 2 or not seen_idat or len(data) <= 4:
                    raise ValueError("Données d'image APNG invalides.")
                if struct.unpack(">I", data[:4])[0] != sequence:
                    raise ValueError("Ordre des données APNG invalide.")
                sequence += 1
                frame_has_data = True
    if animation is None or len(controls) < 2 or not frame_has_data:
        raise ValueError("Le fichier ne contient pas une animation APNG complète.")
    count, loop = animation
    if count != len(controls) or (expected_frames is not None and count != expected_frames):
        raise ValueError("Le nombre d'images APNG ne correspond pas aux images fournies.")
    if expected_loop is not None and loop != expected_loop:
        raise ValueError("Le nombre de lectures APNG est incorrect.")
    if decode:
        with Image.open(path) as image:
            if not image.is_animated or image.n_frames != count or image.size != size:
                raise ValueError("Le décodeur ne reconnaît pas l'animation APNG.")
            for index in range(count):
                if on_frame:
                    on_frame(index, count)
                image.seek(index)
                image.load()
            if on_frame:
                on_frame(count, count)
    return {
        "frames": count,
        "loop": loop,
        "size": size,
        "duration": sum(controls, Fraction(0)),
        "fps": 1 / controls[0],
    }
