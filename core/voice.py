from __future__ import annotations

import io
import logging
import math
import os
import random
import re
import subprocess
import sys
import tempfile
import threading
import time
import wave

import numpy as np

from core.amplitude import set_amplitude, reset as reset_amplitude
from core.settings import settings

log = logging.getLogger("Viviane")

_tts_lock = threading.Lock()
_stop_event = threading.Event()

_current_proc = None
_proc_lock = threading.Lock()

RATE = 16000
CHUNK = 1024
DURATION = 8


def _gerar_envelope(duracao: float, passos: int = 25) -> list[float]:
    envelope = []
    atk = max(1, int(passos * 0.12))
    dec = max(2, int(passos * 0.2))
    sustain = max(0, passos - atk - dec)
    for i in range(passos):
        if i < atk:
            t = i / atk
            env = t * 0.8 + 0.15
        elif i < atk + sustain:
            env = 0.7 + 0.25 * math.sin(i * 0.8) * 0.3
        else:
            t = (i - atk - sustain) / max(dec - 1, 1)
            env = (1 - min(t, 1.0)) * 0.8 + 0.05
        envelope.append(max(0.05, min(1.0, env)))
    return envelope


def _falar_via_powershell(texto: str) -> None:
    global _current_proc
    texto_limpo = texto.replace("'", "''")
    voz_config = settings.tts_voice
    ps_script = (
        "Add-Type -AssemblyName System.Speech; "
        "$v = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$vozSel = $null; "
        "foreach ($voz in $v.GetInstalledVoices()) { "
        '  $nome = $voz.VoiceInfo.Name; '
        f'  if ($nome -eq "{voz_config}") {{ $vozSel = $nome; break }} '
        "} "
        'if (-not $vozSel) { '
        "  foreach ($voz in $v.GetInstalledVoices()) { "
        '    $nome = $voz.VoiceInfo.Name; '
        '    if ($nome -match "Antonio|Daniel|Brazil|Portuguese") { $vozSel = $nome; break } '
        "  } "
        "} "
        'if ($vozSel) { $v.SelectVoice($vozSel) }; '
        "$v.Speak('" + texto_limpo + "')"
    )
    proc = subprocess.Popen(
        ["powershell", "-NoProfile", "-Command", ps_script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    with _proc_lock:
        _current_proc = proc

    while proc.poll() is None:
        if _stop_event.is_set():
            proc.kill()
            break
        time.sleep(0.1)

    with _proc_lock:
        if _current_proc is proc:
            _current_proc = None


def _tocar_com_amplitude(texto: str, engine: str = "") -> None:
    duracao = max(0.5, len(texto) * 0.06)
    envelope = _gerar_envelope(duracao)
    intervalo = duracao / len(envelope)

    def _amplitude_thread():
        for amp in envelope:
            set_amplitude(amp)
            time.sleep(intervalo)
        reset_amplitude()

    t_amp = threading.Thread(target=_amplitude_thread, daemon=True)
    t_amp.start()

    if engine == "edge":
        _falar_via_edge(texto)
    else:
        _falar_via_powershell(texto)


def _falar_via_edge(texto: str) -> None:
    """Gera audio com edge-tts CLI e reproduz via winmm PlaySound (Windows)."""
    import sys as _sys

    if _sys.platform != "win32":
        gerar_tts_bytes(texto)
        return

    import ctypes
    import soundfile as sf
    from ctypes import wintypes

    tmp_mp3 = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_mp3.close()
    tmp_wav.close()
    try:
        mp3_path = _gerar_mp3_edge(texto, tmp_mp3.name)
        if not mp3_path:
            return

        data, sr = sf.read(tmp_mp3.name)
        if data.size == 0:
            return
        sf.write(tmp_wav.name, data, sr)

        import winsound
        winsound.PlaySound(tmp_wav.name, winsound.SND_FILENAME)
    finally:
        try:
            os.unlink(tmp_mp3.name)
        except Exception:
            pass
        try:
            os.unlink(tmp_wav.name)
        except Exception:
            pass


def _gerar_mp3_edge(texto: str, saida: str | None = None) -> str | None:
    """Gera MP3 via edge-tts. Retorna o caminho do arquivo (None em falha)."""
    import subprocess as _subprocess
    import sys as _sys

    tmp_mp3 = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_mp3.close()
    destino = saida or tmp_mp3.name
    try:
        edge_tts_path = os.path.join(os.path.dirname(_sys.executable), "Scripts", "edge-tts.exe")
        if not os.path.exists(edge_tts_path):
            edge_tts_path = os.path.join(os.path.dirname(_sys.executable), "Scripts", "edge-tts")
        if not os.path.exists(edge_tts_path):
            edge_tts_path = "edge-tts"

        proc = _subprocess.run(
            [edge_tts_path, "--voice", settings.tts_voice,
             "--rate", settings.tts_rate,
             "--pitch", settings.tts_pitch,
             "--text", texto,
             "--write-media", destino],
            capture_output=True, timeout=30,
        )
        if proc.returncode != 0 or not os.path.exists(destino) or os.path.getsize(destino) == 0:
            if saida is None:
                try:
                    os.unlink(destino)
                except Exception:
                    pass
            return None
        return destino
    except Exception:
        if saida is None:
            try:
                os.unlink(destino)
            except Exception:
                pass
        return None


def gerar_tts_bytes(texto: str) -> bytes | None:
    """Gera MP3 via edge-tts e retorna os bytes. Usado pela web (navegador toca)."""
    if not texto:
        return None
    texto = _limpar_texto_tts(texto)
    caminho = _gerar_mp3_edge(texto)
    if not caminho:
        return None
    try:
        with open(caminho, "rb") as f:
            return f.read()
    finally:
        try:
            os.unlink(caminho)
        except Exception:
            pass


def _limpar_texto_tts(texto: str) -> str:
    t = texto
    t = re.sub(r'\*+', '', t)
    t = re.sub(r'_+', '', t)
    t = re.sub(r'`+', '', t)
    t = re.sub(r'#+', '', t)
    t = re.sub(r'~~', '', t)
    t = re.sub(r'\|+', '', t)
    t = re.sub(r'\[.*?\]\(.*?\)', '', t)
    t = re.sub(r'https?://\S+', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def falar(texto: str) -> None:
    if not texto:
        return
    texto = _limpar_texto_tts(texto)
    with _tts_lock:
        try:
            _stop_event.clear()
            engine = settings.tts_engine
            _tocar_com_amplitude(texto, engine)
        except Exception as e:
            import traceback
            try:
                with open("", "a", encoding="utf-8") as f:
                    f.write(f"Error speaking: {e}\n{traceback.format_exc()}\n")
            except Exception:
                pass
            raise


def parar_fala() -> None:
    _stop_event.set()
    with _proc_lock:
        if _current_proc is not None and _current_proc.poll() is None:
            try:
                _current_proc.kill()
            except Exception:
                pass
    reset_amplitude()


def falar_confirmacao() -> None:
    frases = [
        "Fechou.",
        "Já foi.",
        "Beleza.",
        "Tá feito.",
        "Ok.",
        "Pronto.",
    ]
    falar(random.choice(frases))


def _debug(msg: str) -> None:
    log.debug("voice: %s", msg)


def _falar_fallback(texto: str) -> None:
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.say(texto)
        engine.runAndWait()
    except Exception:
        print(f"  Falha total no TTS: {texto}")


def _bip_pronto() -> None:
    try:
        import ctypes
        ctypes.windll.winmm.Beep(440, 100)
    except Exception:
        pass


class GravadorVoz:
    def __init__(self, timeout: float = 8.0):
        self.timeout = timeout
        self.device_index = None
        self.energy_threshold = 50
        self._sd = None
        self._calibrar_ambiente()

    def _sounddevice(self):
        if self._sd is None:
            import sounddevice
            self._sd = sounddevice
        return self._sd

    def _calibrar_ambiente(self) -> None:
        try:
            sd = self._sounddevice()
            audio_teste = sd.rec(
                int(1.0 * RATE),
                samplerate=RATE,
                channels=1,
                dtype=np.int16,
                blocking=True,
                device=self.device_index,
            )
            ruido = np.max(np.abs(audio_teste))
            self.energy_threshold = max(50, int(ruido * 1.2))
            print(f"  Calibração: ruído ambiente={ruido}, threshold={self.energy_threshold}")
        except Exception:
            self.energy_threshold = 50

    def _gravar_audio(self) -> np.ndarray | None:
        try:
            sd = self._sounddevice()
            audio = sd.rec(
                int(self.timeout * RATE),
                samplerate=RATE,
                channels=1,
                dtype=np.int16,
                blocking=True,
                device=self.device_index,
            )
            return audio
        except Exception as exc:
            print(f"  Erro ao gravar: {exc}")
            return None

    def _audio_para_wav(self, audio: np.ndarray) -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(RATE)
            wf.writeframes(audio.tobytes())
        return buffer.getvalue()

    def ouvir_comando(self) -> str | None:
        _bip_pronto()
        print("  Ouvindo... (fale algo)")
        audio_np = self._gravar_audio()
        if audio_np is None:
            return None

        nivel = np.max(np.abs(audio_np))
        if nivel < self.energy_threshold:
            print(f"  Silencio detectado (nível {nivel} < {self.energy_threshold})")
            return None

        wav_bytes = self._audio_para_wav(audio_np)
        import speech_recognition as sr

        recognizer = sr.Recognizer()

        try:
            audio = sr.AudioData(wav_bytes, RATE, 2)
            texto = recognizer.recognize_google(audio, language=settings.language)
            print(f"  Você disse: {texto}")
            return texto
        except sr.UnknownValueError:
            print("  Não entendi")
            return None
        except sr.RequestError as exc:
            print(f"  Erro no servidor: {exc}")
            return None
