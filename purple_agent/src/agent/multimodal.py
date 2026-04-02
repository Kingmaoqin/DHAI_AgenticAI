"""Multimodal input conversion utilities.

Converts A2A Part types (text, image, video, PDF, text files) into
a unified list of google.genai.types.Part objects that can be fed
to any LLM via Google ADK or litellm.
"""

import base64
import io
import logging
import os
import tempfile

import cv2
import numpy as np
from a2a.types import FilePart, FileWithBytes, FileWithUri, Part, TextPart
from google.genai import types
from PIL import Image
from pypdf import PdfReader

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def convert_parts(parts: list[Part]) -> list[types.Part]:
    """Convert a list of A2A Parts into google.genai Parts."""
    result: list[types.Part] = []
    for part in parts:
        converted = _convert_one(part)
        if isinstance(converted, list):
            result.extend(converted)
        else:
            result.append(converted)
    return result


# ---------------------------------------------------------------------------
# Internal dispatch
# ---------------------------------------------------------------------------

def _convert_one(part: Part) -> types.Part | list[types.Part]:
    unwrapped = part.root

    if isinstance(unwrapped, TextPart):
        logger.info("Text input: %s", unwrapped.text[:120])
        return types.Part(text=unwrapped.text)

    if isinstance(unwrapped, FilePart):
        if isinstance(unwrapped.file, FileWithUri):
            raise ValueError(f"FileWithUri not supported: {unwrapped.file}")
        if isinstance(unwrapped.file, FileWithBytes):
            return _convert_file(unwrapped.file)
        raise ValueError(f"Unknown file wrapper: {type(unwrapped.file)}")

    raise ValueError(f"Unknown part type: {type(unwrapped)}")


def _convert_file(f: FileWithBytes) -> types.Part | list[types.Part]:
    data = f.bytes
    mime = f.mime_type or ""
    name = f.name or "unknown"
    logger.info("File input: %s  size=%d  mime=%s", name, len(data) if data else 0, mime)

    # --- video ---
    if mime.startswith("video/") or name.endswith(".mp4"):
        return _process_video(data, name)

    # --- image ---
    if mime.startswith("image/"):
        return _process_image(data, name)

    # --- PDF ---
    if mime == "application/pdf" or name.endswith(".pdf"):
        return _process_pdf(data, name)

    # --- plain text ---
    if mime.startswith("text/") or name.endswith(".txt"):
        return _process_text(data, name)

    # --- fallback: inline blob ---
    raw = _ensure_bytes(data)
    return types.Part(
        inline_data=types.Blob(display_name=name, data=raw, mime_type=mime)
    )


# ---------------------------------------------------------------------------
# Format-specific processors
# ---------------------------------------------------------------------------

def _process_image(data, name: str) -> types.Part:
    raw = _ensure_bytes(data)
    img = Image.open(io.BytesIO(raw))
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return types.Part(
        inline_data=types.Blob(
            display_name=name, data=buf.getvalue(), mime_type="image/jpeg"
        )
    )


def _process_pdf(data, name: str) -> types.Part:
    raw = _ensure_bytes(data)
    reader = PdfReader(io.BytesIO(raw))
    text = ""
    for i, page in enumerate(reader.pages, 1):
        page_text = page.extract_text()
        if page_text:
            text += f"--- Page {i} ---\n{page_text}\n\n"
    return types.Part(text=f"Content of {name}:\n\n{text.strip()}")


def _process_text(data, name: str) -> types.Part:
    raw = _ensure_bytes(data)
    content = raw.decode("utf-8", errors="replace")
    return types.Part(text=f"Content of {name}:\n\n{content}")


def _process_video(
    data, name: str, seconds_per_frame: int = 1, max_frames: int = 30
) -> list[types.Part]:
    raw = _ensure_bytes(data)

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(raw)
        tmp_path = tmp.name

    try:
        cap = cv2.VideoCapture(tmp_path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        skip = max(int(fps * seconds_per_frame), int(total / (max_frames - 1)))

        frames: list[bytes] = []
        idx = 0
        while idx < total and len(frames) < max_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok:
                break
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            if img.mode in ("RGBA", "LA"):
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG")
            frames.append(buf.getvalue())
            idx += skip

        actual_spf = skip / fps if fps > 0 else seconds_per_frame
        cap.release()

        parts: list[types.Part] = [
            types.Part(
                text=(
                    f"Video file: {name}\n"
                    f"Processed into {len(frames)} frames "
                    f"(~{actual_spf:.1f}s intervals).\n"
                    "You MUST use these frames to analyze the video content."
                )
            )
        ]
        for i, fb in enumerate(frames):
            ts = _seconds_to_hhmmss(i * actual_spf)
            parts.append(types.Part(text=f"Frame at {ts}"))
            parts.append(
                types.Part(
                    inline_data=types.Blob(
                        display_name=f"{name}_frame_{i}",
                        data=fb,
                        mime_type="image/jpeg",
                    )
                )
            )
        return parts
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_bytes(data) -> bytes:
    if isinstance(data, bytes):
        return data
    if isinstance(data, str):
        if data.startswith("data:"):
            data = data.split(",", 1)[1]
        data = data.replace(" ", "").replace("\n", "").replace("\r", "")
        return base64.b64decode(data)
    raise ValueError(f"Cannot convert {type(data)} to bytes")


def _seconds_to_hhmmss(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02}:{m:02}:{s:02}"
