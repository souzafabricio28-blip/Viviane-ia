from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import sounddevice as sd
import numpy as np

from core.settings import settings

log = logging.getLogger("Viviane.OpenWakeWord")


@dataclass
class OpenWakeWordConfig:
    keyword: str = "oi viviane"
    sensitivity: float = 0.6
    model_path: str = ""
    sample_rate: int = 16000
    chunk_duration: float = 1.5


class OpenWakeWordDetector:
    """Detector de wake word usando openwakeword (ONNX runtime)."""

    def __init__(self, config: Optional[object] = None):
        self.config = config or type('Config', (), {
            'keyword': 'oi viviane',
            'sensitivity': 0.6,
            'sample_rate': 16000,
            'chunk_duration': 1.5
        })()
        
        self._model = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable[[str], None]] = None
        self._running = False
        self._cooldown = 2.0
        self._last_detection = 0.0
        self._sample_rate = 16000
        self._chunk_duration = 1.5
        self._model = None

    def _init_model(self) -> bool:
        """Inicializa o modelo openwakeword."""
        try:
            from openwakeword import Model
            
            # Tenta carregar modelo para "oi viviane" ou usa modelo genérico
            try:
                self._model = Model(
                    wakeword_models=["hey_jarvis", "hey_alexa", "hey_google", "ok_google"],
                    inference_framework="onnx",
                    vad_threshold=0.5
                )
                log.info("Modelo openwakeword carregado (modelos padrão)")
                return True
            except Exception as e:
                log.warning(f"Modelos padrão não disponíveis: {e}")
                
            return False
            
        except ImportError:
            log.error("openwakeword não instalado")
            return False
        except Exception as e:
            log.error(f"Erro ao inicializar openwakeword: {e}")
            return False

    def start(self, callback) -> bool:
        if self._running:
            return True
        
        if not self._init_model():
            return False
        
        self._callback = callback
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        log.info(f"OpenWakeWord detector iniciado")
        return True

    def stop(self):
        self._running = False
        if hasattr(self, '_thread') and self._thread:
            self._thread.join(timeout=2.0)

    def _listen_loop(self):
        import sounddevice as sd
        
        log.info("OpenWakeWord detector iniciado")
        
        chunk_duration = 0.5  # chunks menores para resposta mais rápida
        chunk_samples = int(16000 * 0.5)
        
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
        if not self._running or not hasattr(self, '_model') or not self._model:
            return
        
        try:
            # openwakeword espera float32 normalizado
            audio_data = indata[:, 0].astype(np.float32) / 32768.0
            
            # Processa com openwakeword
            prediction = self._model.predict(audio_data)
            
            # Verifica se alguma wake word foi detectada
            for keyword, score in prediction.items():
                if score > 0.5:  # threshold
                    now = time.time()
                    if now - self._last_detection > self._cooldown:
                        self._last_detection = time.time()
                        log.info(f"Wake word detectada (openwakeword): {keyword} - score: {score}")
                        if self._callback:
                            threading.Thread(target=self._callback, args=(list(prediction.keys())[0],), daemon=True).start()
                            
        except Exception as e:
            log.error(f"Erro no callback openwakeword: {e}")

    def stop(self):
        self._running = False

    def is_running(self) -> bool:
        return self._running


class OpenWakeWordDetector:
    """Detector de wake word usando openwakeword (ONNX runtime)."""
    
    def __init__(self, config=None):
        self.config = config or type('Config', (), {
            'keyword': 'oi viviane',
            'sensitivity': 0.6,
            'sample_rate': 16000,
            'chunk_duration': 1.5
        })()
        
        self._model = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable[[str], None]] = None
        self._running = False
        self._cooldown = 2.0
        self._last_detection = 0.0
        self._sample_rate = 16000
        self._chunk_duration = 1.5
        self._model = None
        self._cooldown = 2.0
        self._last_detection = 0.0

    def _init_model(self) -> bool:
        try:
            from openwakeword import Model
            
            try:
                self._model = Model(
                    wakeword_models=["hey_jarvis", "hey_alexa", "hey_google", "ok_google"],
                    inference_framework="onnx",
                    vad_threshold=0.5
                )
                log.info("openwakeword model loaded (default models)")
                return True
            except Exception as e:
                log.warning(f"Default models not available: {e}")
                return False
        except ImportError:
            log.error("openwakeword not installed")
            return False
        except Exception as e:
            log.error(f"Error initializing openwakeword: {e}")
            return False

    def start(self, callback: Callable[[str], None]) -> bool:
        if self._running:
            return True
        
        if not self._init_model():
            return False
        
        self._callback = callback
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        log.info(f"OpenWakeWord detector started")
        return True

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def _listen_loop(self):
        import sounddevice as sd
        
        log.info("OpenWakeWord detector started")
        
        chunk_duration = 0.5
        chunk_samples = int(16000 * 0.5)
        
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
        if not self._running or not self._model:
            return
        
        try:
            # openwakeword expects float32 normalized
            audio_data = indata[:, 0].astype(np.float32) / 32768.0
            
            # Process with openwakeword
            prediction = self._model.predict(audio_data)
            
            # Check if any wake word was detected
            for keyword, score in prediction.items():
                if score > 0.5:
                    now = time.time()
                    if now - self._last_detection > self._cooldown:
                        self._last_detection = now
                        log.info(f"Wake word detected (openwakeword): {keyword} - score: {score}")
                        if self._callback:
                            threading.Thread(
                                target=self._callback, 
                                args=(list(prediction.keys())[0],), 
                                daemon=True
                            ).start()
        except Exception as e:
            log.error(f"Error in openwakeword callback: {e}")

    def stop(self):
        self._running = False

    def is_running(self) -> bool:
        return self._running