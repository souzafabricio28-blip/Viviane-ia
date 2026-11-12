from __future__ import annotations

import logging
import threading
import time
import json
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable, Optional

# Tenta importar Porcupine (requer AccessKey do Picovoice Console)
try:
    import pvporcupine
    PORCUPINE_DISPONIVEL = True
except ImportError:
    pvporcupine = None
    PORCUPINE_DISPONIVEL = False

# Tenta importar Vosk (reconhecimento offline com keyword spotting)
try:
    import vosk
    from vosk import Model, KaldiRecognizer
    VOSK_DISPONIVEL = True
except ImportError:
    vosk = None
    Model = None
    KaldiRecognizer = None
    VOSK_DISPONIVEL = False

# Tenta importar openwakeword (wake word detection baseado em ONNX)
try:
    from core.skills.openwakeword_detector import OpenWakeWordDetector
    OPENWAKEWORD_DISPONIVEL = True
except ImportError:
    OPENWAKEWORD_DISPONIVEL = False

import sounddevice as sd
import numpy as np

from core.settings import settings
from core.voice import GravadorVoz

log = logging.getLogger("Viviane.WakeWord")


@dataclass
class WakeWordConfig:
    keyword: str = "oi viviane"
    sensitivity: float = 0.6
    access_key: str = ""
    custom_keyword_path: str = ""
    model_path: str = ""
    audio_device_index: Optional[int] = None
    sample_rate: int = 16000
    frame_length: int = 512


class PorcupineWakeWordDetector:
    """Detector usando Porcupine (requer AccessKey do Picovoice Console)."""

    BUILTIN_KEYWORDS = {
        "jarvis", "computer", "hey google", "alexa", "hey siri",
        "ok google", "hey barista", "blueberry", "grapefruit",
        "americano", "pico clock", "porcupine", "terminator",
        "bumblebee", "grasshopper", "picovoice"
    }

    def __init__(self, config: WakeWordConfig):
        self.config = config
        self._porcupine = None
        self._stream = None
        self._running = False
        self._thread = None
        self._callback = None
        self._last_detection = 0.0
        self._cooldown = 2.0

    def _init_porcupine(self) -> bool:
        try:
            keyword = self.config.keyword.lower()

            if keyword in self.BUILTIN_KEYWORDS:
                if not self.config.access_key:
                    log.warning("Porcupine built-in keywords requerem AccessKey do Picovoice Console")
                    return False
                self._porcupine = pvporcupine.create(
                    access_key=self.config.access_key,
                    keywords=[keyword],
                    sensitivities=[self.config.sensitivity]
                )
                log.info(f"Porcupine wake word (built-in): {keyword}")
                return True

            elif self.config.custom_keyword_path:
                if not self.config.access_key:
                    log.error("Custom keyword requer AccessKey")
                    return False
                self._porcupine = pvporcupine.create(
                    access_key=self.config.access_key,
                    keyword_paths=[self.config.custom_keyword_path],
                    sensitivities=[self.config.sensitivity]
                )
                log.info(f"Porcupine wake word (custom): {self.config.custom_keyword_path}")
                return True

            else:
                log.error(f"Keyword '{keyword}' não suportada sem AccessKey")
                return False

        except Exception as e:
            log.error(f"Erro ao inicializar Porcupine: {e}")
            return False

    def start(self, callback: Callable[[str], None]) -> bool:
        if self._running:
            return True

        if not self._init_porcupine():
            return False

        self._callback = callback
        self._running = True

        try:
            self._stream = sd.InputStream(
                samplerate=self.config.sample_rate,
                channels=1,
                dtype='int16',
                blocksize=self.config.frame_length,
                device=self.config.audio_device_index,
                callback=self._audio_callback
            )
            self._stream.start()
            log.info(f"Porcupine wake word iniciado: '{self.config.keyword}'")
            return True
        except Exception as e:
            log.error(f"Erro ao iniciar stream Porcupine: {e}")
            self.stop()
            return False

    def stop(self):
        self._running = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._porcupine:
            try:
                self._porcupine.delete()
            except Exception:
                pass
            self._porcupine = None

    def _audio_callback(self, indata, frames, time_info, status):
        if not self._running or not self._porcupine:
            return

        try:
            pcm = indata[:, 0].astype('int16')
            keyword_index = self._porcupine.process(pcm)
            if keyword_index >= 0:
                now = time.time()
                if now - self._last_detection > self._cooldown:
                    self._last_detection = now
                    keyword = self.config.keyword
                    log.info(f"Wake word detectada: {keyword}")
                    if self._callback:
                        threading.Thread(target=self._callback, args=(keyword,), daemon=True).start()
        except Exception as e:
            log.error(f"Erro no callback Porcupine: {e}")

    def is_running(self) -> bool:
        return self._running


class VoskWakeWordDetector:
    """Detector usando Vosk (reconhecimento offline com keyword spotting)."""

    def __init__(self, config: WakeWordConfig):
        self.config = config
        self._model = None
        self._rec = None
        self._running = False
        self._thread = None
        self._callback = None
        self._cooldown = 2.0
        self._last_detection = 0.0
        import json
        self._json = json

    def _init_model(self) -> bool:
        try:
            import vosk
            model_path = self.config.model_path or "vosk_models/vosk-model-small-pt-0.3"
            self._model = vosk.Model(model_path)
            self._rec = KaldiRecognizer(self._model, 16000)
            self._rec.SetWords(True)
            log.info(f"Vosk wake word iniciado: '{self.config.keyword}'")
            return True
        except Exception as e:
            log.error(f"Erro ao inicializar Vosk: {e}")
            return False

    def start(self, callback: Callable[[str], None]) -> bool:
        if self._running:
            return True

        if not self._model:
            if not self._init_model():
                return False

        self._callback = callback
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        log.info(f"Vosk wake word iniciado: '{self.config.keyword}'")
        return True

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def _listen_loop(self):
        import sounddevice as sd

        log.info(f"Vosk wake word: escutando por '{self.config.keyword}'...")

        with sd.RawInputStream(
            samplerate=16000,
            blocksize=8000,
            dtype='int16',
            channels=1,
            callback=self._audio_callback
        ):
            while self._running:
                time.sleep(0.1)

    def _audio_callback(self, indata, frames, time_info, status):
        if not self._running or not self._rec:
            return
        try:
            # indata from RawInputStream is a numpy array when dtype is specified
            # Convert numpy array to bytes properly
            if hasattr(indata, 'tobytes'):
                audio_data = indata.tobytes()
            else:
                # Fallback for cffi buffer
                audio_data = bytes(indata)
            
            if self._rec.AcceptWaveform(audio_data):
                result = json.loads(self._rec.Result())
                text = result.get('text', '').lower().strip()
                if text:
                    self._check_wake_word(text)
            else:
                partial = json.loads(self._rec.PartialResult())
                partial_text = partial.get('partial', '').lower().strip()
                if partial_text:
                    self._check_wake_word_partial(partial_text)
        except Exception as e:
            log.error(f"Erro no callback Vosk: {e}")

    def _check_wake_word(self, text: str):
        keyword = self.config.keyword.lower()
        if keyword in text.lower():
            now = time.time()
            if now - self._last_detection > self._cooldown:
                self._last_detection = now
                log.info(f"Wake word detectada: {self.config.keyword}")
                if self._callback:
                    threading.Thread(target=self._callback, args=(self.config.keyword,), daemon=True).start()

    def _check_wake_word_partial(self, partial_text: str):
        keyword = self.config.keyword.lower()
        if keyword in partial_text.lower():
            now = time.time()
            if now - self._last_detection > self._cooldown:
                self._last_detection = time.time()
                log.info(f"Wake word detectada (parcial): {keyword}")
                if self._callback:
                    threading.Thread(target=self._callback, args=(self.config.keyword,), daemon=True).start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def is_running(self) -> bool:
        return self._running


class SimpleWakeWordDetector:
    """Detector simples usando sounddevice + transcrição Whisper (sem PyAudio)."""

    def __init__(self, config: WakeWordConfig):
        self.config = config
        self._running = False
        self._thread = None
        self._callback = None
        self._cooldown = 2.0
        self._last_detection = 0.0
        self._sensitivity = config.sensitivity
        self._sample_rate = 16000
        self._chunk_duration = 1.5

    def start(self, callback: Callable[[str], None]) -> bool:
        if self._running:
            return True

        self._callback = callback
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        log.info(f"Simple wake word iniciado: '{self.config.keyword}' (sounddevice + Google Speech)")
        return True

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def _listen_loop(self):
        """Loop contínuo usando sounddevice + transcrição."""
        import sounddevice as sd
        import tempfile
        import os
        import wave
        import numpy as np

        # Importa função de transcrição existente
        try:
            from core.transcricao import transcrever_wav
        except ImportError:
            log.error("Módulo de transcrição não disponível")
            return

        log.info(f"Simple wake word: escutando por '{self.config.keyword}'...")

        chunk_samples = int(self._sample_rate * self._chunk_duration)

        while self._running:
            try:
                # Grava chunk de áudio
                audio = sd.rec(
                    chunk_samples,
                    samplerate=self._sample_rate,
                    channels=1,
                    dtype='int16',
                    blocking=True
                )

                # Verifica nível de energia (threshold simples)
                rms = np.sqrt(np.mean(audio.astype(np.float32) ** 2))
                threshold = 150 * (1.5 - self._sensitivity)

                if rms < threshold:
                    continue  # Silêncio - ignora

                # Salva como WAV temporário
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                    temp_path = f.name

                try:
                    with wave.open(temp_path, 'wb') as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(self._sample_rate)
                        wf.writeframes(audio.tobytes())

                    # Transcreve
                    with open(temp_path, 'rb') as f:
                        wav_bytes = f.read()

                    texto = transcrever_wav(wav_bytes)

                    if texto:
                        comando_lower = texto.lower().strip()
                        keyword = self.config.keyword.lower()

                        # Fuzzy matching para lidar com erros de transcrição
                        if self._keyword_match(keyword, comando_lower):
                            now = time.time()
                            if now - self._last_detection > self._cooldown:
                                self._last_detection = now
                                log.info(f"Wake word detectada (simple): {keyword} - '{texto}'")
                                if self._callback:
                                    self._callback(self.config.keyword)
                                time.sleep(0.5)

                finally:
                    try:
                        os.unlink(temp_path)
                    except Exception:
                        pass

            except Exception as e:
                if self._running:
                    log.warning(f"Erro no loop wake word: {e}")
                    time.sleep(0.5)
    
    def _keyword_match(self, keyword: str, text: str) -> bool:
        """Verifica se a palavra-chave está no texto com correspondência ultra-flexível."""
        # Correspondência exata
        if keyword in text:
            return True
        
        # Normaliza: remove acentos, pontuação, espaços extras
        import unicodedata
        import re
        
        def normalize(s: str) -> str:
            s = unicodedata.normalize('NFD', s.lower())
            s = ''.join(c for c in s if not unicodedata.combining(c))
            s = re.sub(r'[^\w\s]', '', s)
            return re.sub(r'\s+', ' ', s).strip()
        
        norm_keyword = normalize(keyword)
        norm_text = normalize(text)
        
        # 1. Correspondência exata normalizada
        if norm_keyword in norm_text:
            return True
        
        # 2. Verifica se todas as palavras-chave estão no texto (ordem não importa)
        kw_words = norm_keyword.split()
        matches = sum(1 for kw in norm_keyword.split() if kw in norm_text)
        if matches >= max(1, len(kw_words) - 1):
            return True
        
        # 3. Verifica substrings fonéticas (mínimo 3 chars)
        for i in range(len(norm_keyword)):
            for j in range(i + 2, len(norm_keyword) + 1):
                substr = norm_keyword[i:j]
                if len(substr) >= 3 and substr in norm_text:
                    return True
        
        # 4. Correspondência fonética aproximada (difflib)
        from difflib import SequenceMatcher
        for tw in norm_text.split():
            if SequenceMatcher(None, norm_keyword, tw).ratio() > 0.6:
                return True
        
        # 5. Verifica fonemas-chave: "oi" + "vivi" + "ane" 
        key_parts = ["oi", "vivi", "viane", "vivi ane", "oi vi", "vi ane"]
        for part in key_parts:
            if len(part) >= 3 and part in norm_text:
                return True
        
        # 6. Verifica fonemas-chave individuais
        key_phonemes = ["oi", "vi", "vi", "a", "ne"]
        phoneme_matches = sum(1 for p in ["oi", "viv", "viane", "viviane"] if p in norm_text)
        if phoneme_matches >= 2:
            return True
        
        return False

    def is_running(self) -> bool:
        return self._running


class WakeWordManager:
    """Gerenciador unificado de wake word."""

    def __init__(self):
        self.detector = None
        self._config_path = settings.data_dir / "wake_word_config.json"
        self._load_config()
        self._activation_callback: Optional[Callable] = None

    def _load_config(self):
        # Carrega do arquivo local (para compatibilidade), mas prioriza .env
        try:
            import json
            if self._config_path.exists():
                data = json.loads(self._config_path.read_text())
                self.current_keyword = data.get("keyword", settings.wake_word)
                self.sensitivity = data.get("sensitivity", settings.wake_word_sensitivity)
                self.enabled = data.get("enabled", True)
                self.engine = data.get("engine", settings.wake_word_engine)
                self.access_key = data.get("access_key", "")
            else:
                self.current_keyword = settings.wake_word
                self.sensitivity = settings.wake_word_sensitivity
                self.enabled = True
                self.engine = settings.wake_word_engine
                self.access_key = ""
        except Exception:
            self.current_keyword = settings.wake_word
            self.sensitivity = settings.wake_word_sensitivity
            self.enabled = True
            self.engine = settings.wake_word_engine
            self.access_key = ""

    def _save_config(self):
        try:
            import json
            data = {
                "keyword": self.current_keyword,
                "sensitivity": self.sensitivity,
                "enabled": self.enabled,
                "engine": self.engine,
                "access_key": self.access_key,
            }
            self._config_path.write_text(json.dumps(data, indent=2))
        except Exception as e:
            log.warning(f"Erro ao salvar config wake word: {e}")

    def set_keyword(self, keyword: str) -> bool:
        keyword = keyword.lower().strip()
        was_running = self.detector and self.detector.is_running()
        if was_running:
            self.stop()

        self.current_keyword = keyword
        self._save_config()

        if was_running and self.enabled:
            self.start()

        return True

    def set_engine(self, engine: str) -> bool:
        if engine not in ("simple", "porcupine", "vosk", "openwakeword"):
            return False
        if engine == "porcupine" and not PORCUPINE_DISPONIVEL:
            log.error("Porcupine não instalado")
            return False

        was_running = self.detector and self.detector.is_running()
        if was_running:
            self.stop()

        self.engine = engine
        self._save_config()

        if was_running and self.enabled:
            self.start()
        return True

    def set_access_key(self, key: str):
        self.access_key = key
        self._save_config()
        if self.detector and self.detector.is_running():
            self.restart()

    def set_sensitivity(self, sensitivity: float):
        self.sensitivity = max(0.0, min(1.0, sensitivity))
        self._save_config()
        if self.detector and self.detector.is_running():
            self.restart()

    def set_enabled(self, enabled: bool):
        self.enabled = enabled
        self._save_config()
        if enabled:
            self.start()
        else:
            self.stop()

    def start(self):
        if not self.enabled:
            return
        if self.detector and self.detector.is_running():
            return

        config = WakeWordConfig(
            keyword=self.current_keyword,
            sensitivity=self.sensitivity,
            access_key=self.access_key,
        )

        if self.engine == "porcupine":
            if not PORCUPINE_DISPONIVEL:
                log.error("Porcupine não disponível, usando engine simple")
                self.engine = "simple"
                self._save_config()
            elif not self.access_key:
                log.warning("Porcupine requer AccessKey, usando engine simple")
                self.engine = "simple"
                self._save_config()

        if self.engine == "porcupine":
            self.detector = PorcupineWakeWordDetector(config)
        elif self.engine == "vosk":
            if not VOSK_DISPONIVEL:
                log.error("Vosk não disponível, usando engine simple")
                self.engine = "simple"
                self._save_config()
            else:
                self.detector = VoskWakeWordDetector(config)
        elif self.engine == "openwakeword":
            if not OPENWAKEWORD_DISPONIVEL:
                log.error("openwakeword não disponível, usando engine simple")
                self.engine = "simple"
                self._save_config()
            else:
                self.detector = OpenWakeWordDetector(config)
        else:
            self.detector = SimpleWakeWordDetector(config)

        self.detector.start(self._on_wake_word)

    def stop(self):
        if self.detector:
            self.detector.stop()
            self.detector = None

    def restart(self):
        self.stop()
        self.start()

    def _on_wake_word(self, keyword: str):
        log.info(f"Wake word '{keyword}' ativada!")
        if self._activation_callback:
            try:
                self._activation_callback(keyword)
            except Exception as e:
                log.error(f"Erro no callback de ativação: {e}")

    def set_activation_callback(self, callback: Callable):
        self._activation_callback = callback

    def get_status(self) -> dict:
        return {
            "enabled": self.enabled,
            "keyword": self.current_keyword,
            "sensitivity": self.sensitivity,
            "engine": self.engine,
            "running": self.detector.is_running() if self.detector else False,
        }


# Instância global
wake_word_manager = WakeWordManager()