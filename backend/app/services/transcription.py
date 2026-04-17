"""
Audio/Video transcription using faster-whisper.
Returns word-level timestamped segments.
"""
import logging
import tempfile
import os
from dataclasses import dataclass
from functools import lru_cache

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class TranscriptSegment:
    text: str
    start: float  # seconds
    end: float    # seconds


@lru_cache(maxsize=1)
def _get_whisper():
    from faster_whisper import WhisperModel
    logger.info("Loading Whisper model: %s on %s", settings.WHISPER_MODEL, settings.WHISPER_DEVICE)
    return WhisperModel(
        settings.WHISPER_MODEL,
        device=settings.WHISPER_DEVICE,
        compute_type=settings.WHISPER_COMPUTE_TYPE,
    )


def transcribe_bytes(audio_bytes: bytes, file_ext: str = ".mp3") -> tuple[list[TranscriptSegment], float]:
    """
    Transcribe raw audio/video bytes.
    Returns (segments, duration_seconds).
    """
    model = _get_whisper()

    with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        segments_gen, info = model.transcribe(
            tmp_path,
            word_timestamps=True,
            vad_filter=True,
        )
        segments: list[TranscriptSegment] = []
        for seg in segments_gen:
            segments.append(
                TranscriptSegment(
                    text=seg.text.strip(),
                    start=float(seg.start),
                    end=float(seg.end),
                )
            )
        return segments, float(info.duration)
    finally:
        os.unlink(tmp_path)
