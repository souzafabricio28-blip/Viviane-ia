from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import sounddevice as sd
import numpy as np

from core.settings import settings

log = logging.getLogger("Viviane.VoskWakeWord")


@dataclass
class VoskWakeWordConfig:
    keyword: str = "oi viviane"
    sensitivity: float = 0.6
    model_path: str = ""
    sample_rate: int = 16000
    chunk_duration: float = 1.5


class VoskWakeWordDetector:
    """Detector de wake word usando Vosk (reconhecimento offline com keyword spotting)."""

    def __init__(self, config: VoskWakeWordConfig):
        self.config = config
        self._model = None
        self._rec = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[callable] = None
        self._running = False
        self._cooldown = 2.0
        self._last_detection = 0.0

    def _init_model(self) -> bool:
        """Inicializa o modelo Vosk com gramática para keyword spotting."""
        try:
            from vosk import Model, KaldiRecognizer
            
            # Tenta usar modelo português se disponível
            model_path = self.config.model_path or "vosk-model-small-pt-0.3"
            
            try:
                self._model = Model(model_path)
                log.info(f"Modelo Vosk carregado: {model_path}")
            except Exception as e:
                log.warning(f"Modelo específico não encontrado, tentando modelo genérico: {e}")
                # Fallback para modelo pequeno em inglês se português não disponível
                try:
                    self._model = Model("vosk-model-small-en-us-0.15")
                    log.info("Usando modelo em inglês como fallback")
                except Exception as e2:
                    log.error(f"Erro ao carregar modelo Vosk: {e2}")
                    return False
            
            # Cria recognizer com gramática JSGF para keyword spotting
            self._rec = KaldiRecognizer(self._model, 16000)
            
            # Define gramática JSGF para detectar apenas a wake word
            keyword = self.config.keyword.lower()
            # Variações comuns da wake word
            variations = [
                keyword,
                keyword.replace(' ', ''),
                keyword.replace('viviane', 'vivi'),
                keyword.replace('oi ', ''),
                'hey ' + keyword.split()[-1],
            ]
            # Remove duplicatas
            variations = list(dict.fromkeys(variations))
            
            import json
            grammar_json = json.dumps(variations)
            self._rec.SetGrammar(grammar_json)
            log.info(f"Gramática JSON definida: {grammar_json}")
            
            log.info("Modelo Vosk inicializado com sucesso com gramática")
            return True
            
        except Exception as e:
            log.error(f"Erro ao inicializar Vosk: {e}")
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
        log.info(f"Vosk wake word iniciado: '{self.config.keyword}'")
        return True

    def stop(self):
        self._running = False
        if hasattr(self, '_thread') and self._thread:
            self._thread.join(timeout=2.0)

    def _listen_loop(self):
        import sounddevice as sd
        import json
        
        log.info(f"Vosk wake word: escutando por '{self.config.keyword}'...")
        
        sample_rate = 16000
        chunk_duration = 1.0  # chunks menores para resposta mais rápida
        chunk_samples = int(16000 * 1.0)
        
        with sd.RawInputStream(
            samplerate=sample_rate,
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
            # Converte para bytes
            audio_data = bytes(indata)
            
            # Processa com Vosk
            if self._rec.AcceptWaveform(audio_data):
                result = json.loads(self._rec.Result())
                text = result.get('text', '').lower().strip()
                
                if text:
                    log.info(f"Vosk reconheceu: {text}")
                    self._check_wake_word(text)
            else:
                # Resultado parcial para detecção mais rápida
                partial = json.loads(self._rec.PartialResult())
                partial_text = partial.get('partial', '').lower().strip()
                if partial_text:
                    self._check_wake_word_partial(partial_text)
                    
        except Exception as e:
            log.error(f"Erro no callback de áudio: {e}")

    def _check_wake_word(self, text: str):
        keyword = self.config.keyword.lower()
        if self.config.keyword.lower() in text:
            now = time.time()
            if now - self._last_detection > self._cooldown:
                self._last_detection = time.time()
                log.info(f"Wake word detectada: {self.config.keyword}")
                if self._callback:
                    threading.Thread(target=self._callback, args=(self.config.keyword,), daemon=True).start()

    def _check_wake_word_partial(self, partial_text: str):
        """Verifica wake word em resultado parcial para resposta mais rápida."""
        keyword = self.config.keyword.lower()
        if keyword in partial_text:
            now = time.time()
            if now - self._last_detection > self._cooldown:
                self._last_detection = time.time()
                log.info(f"Wake word detectada (parcial): {self.config.keyword}")
                if self._callback:
                    threading.Thread(target=self._callback, args=(self.config.keyword,), daemon=True).start()

    def stop(self):
        self._running = False

    def is_running(self) -> bool:
        return self._running