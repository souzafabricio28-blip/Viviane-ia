from __future__ import annotations

import io
import os
import wave

import numpy as np
from faster_whisper import WhisperModel

from core.settings import settings

_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        cache_dir = settings.data_dir / "hf_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("HF_HOME", str(cache_dir))
        os.environ.setdefault("XDG_CACHE_HOME", str(cache_dir))
        _model = WhisperModel(
            settings.whisper_model, device="cpu", compute_type="int8"
        )
    return _model


def transcrever_wav(wav_bytes: bytes) -> str:
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        sr = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

    model = _get_model()
    segments, _ = model.transcribe(
        audio, 
        language="pt", 
        beam_size=1,
        temperature=0.0,
        vad_filter=False,
        condition_on_previous_text=False,
        initial_prompt="oi viviane"
    )
    return " ".join(seg.text for seg in segments).strip()
