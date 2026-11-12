from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from core.settings import settings


@dataclass
class FaceMatch:
    name: str
    confidence: float
    bbox: tuple[int, int, int, int] | None = None


class ReconhecimentoFacial:
    """Reconhecimento facial leve com OpenCV (Haar cascade + LBPH quando disponivel)."""

    def __init__(self) -> None:
        self.data_dir = settings.data_dir / "faces"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "faces.json"
        self.cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        self.cascade = cv2.CascadeClassifier(str(self.cascade_path))
        self._labels: dict[int, str] = {}
        self._names: dict[str, int] = {}
        self._model = None
        self._trained = False
        self._load_db()

    def _load_db(self) -> None:
        if self.db_path.exists():
            try:
                data = json.loads(self.db_path.read_text(encoding="utf-8"))
                self._labels = {int(k): v for k, v in data.get("labels", {}).items()}
                self._names = {k: int(v) for k, v in data.get("names", {}).items()}
            except Exception:
                self._labels, self._names = {}, {}
        self._init_model()

    def _save_db(self) -> None:
        self.db_path.write_text(
            json.dumps({"labels": self._labels, "names": self._names}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _init_model(self) -> None:
        self._model = None
        self._trained = False
        if hasattr(cv2, "face") and hasattr(cv2.face, "LBPHFaceRecognizer_create"):
            try:
                self._model = cv2.face.LBPHFaceRecognizer_create()
                self._try_train()
            except Exception:
                self._model = None

    def _try_train(self) -> None:
        if self._model is None:
            return
        images, labels = [], []
        for img_path in self.data_dir.glob("*.png"):
            name = img_path.stem.rsplit("_", 1)[0]
            if name not in self._names:
                continue
            img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue
            img = cv2.resize(img, (200, 200))
            images.append(img)
            labels.append(self._names[name])
        if images and labels:
            self._model.train(images, np.array(labels))
            self._trained = True

    def disponivel(self) -> bool:
        return bool(self.cascade and not self.cascade.empty())

    def status(self) -> dict:
        pessoas = sorted(self._names.keys())
        amostras = len(list(self.data_dir.glob("*.png")))
        return {
            "disponivel": self.disponivel(),
            "lbph": self._model is not None and self._trained,
            "pessoas_cadastradas": pessoas,
            "amostras": amostras,
        }

    def cadastrar(self, nome: str, camera_index: int = 0, amostras: int = 12) -> str:
        nome = (nome or "").strip()
        if not nome:
            return "Informe um nome para cadastrar o rosto."
        if not self.disponivel():
            return "Detector facial indisponivel (Haar cascade nao carregado)."
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            return "Nao foi possivel acessar a webcam."
        label_id = self._names.get(nome)
        if label_id is None:
            label_id = (max(self._names.values()) + 1) if self._names else 1
            self._names[nome] = label_id
            self._labels[label_id] = nome
        capturadas = 0
        inicio = time.time()
        try:
            while capturadas < amostras and time.time() - inicio < 20:
                ok, frame = cap.read()
                if not ok:
                    continue
                dets = self.detectar(frame)
                if not dets:
                    continue
                x, y, w, h = max(dets, key=lambda b: b[2] * b[3])
                face_img = cv2.cvtColor(frame[y:y+h, x:x+w], cv2.COLOR_BGR2GRAY)
                face_img = cv2.resize(face_img, (200, 200))
                path = self.data_dir / f"{nome}_{int(time.time()*1000)}_{capturadas}.png"
                cv2.imwrite(str(path), face_img)
                capturadas += 1
                time.sleep(0.15)
        finally:
            cap.release()
        self._save_db()
        self._try_train()
        if capturadas == 0:
            return f"Nenhum rosto detectado para cadastrar {nome}."
        return f"Cadastro facial concluido: {nome} ({capturadas} amostras)."

    def detectar(self, frame_bgr):
        if frame_bgr is None or not self.disponivel():
            return []
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        faces = self.cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(60, 60))
        return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]

    def reconhecer(self, camera_index: int = 0) -> FaceMatch | None:
        if not self.disponivel():
            return None
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            return None
        try:
            for _ in range(15):
                ok, frame = cap.read()
                if not ok:
                    continue
                dets = self.detectar(frame)
                if not dets:
                    continue
                x, y, w, h = max(dets, key=lambda b: b[2] * b[3])
                gray = cv2.cvtColor(frame[y:y+h, x:x+w], cv2.COLOR_BGR2GRAY)
                gray = cv2.resize(gray, (200, 200))
                if self._model is not None and self._trained:
                    label, conf = self._model.predict(gray)
                    name = self._labels.get(int(label), "desconhecido")
                    score = max(0.0, min(1.0, 1.0 - (float(conf) / 120.0)))
                    if score >= 0.45:
                        return FaceMatch(name=name, confidence=score, bbox=(x, y, w, h))
                return FaceMatch(name="desconhecido", confidence=0.0, bbox=(x, y, w, h))
        finally:
            cap.release()
        return None

    def identificar_camera(self, camera_index: int = 0) -> str:
        st = self.status()
        if not st["disponivel"]:
            return "Reconhecimento facial indisponivel neste ambiente (OpenCV/Haar cascade)."
        if not st["pessoas_cadastradas"]:
            return "Nenhuma pessoa cadastrada. Use: cadastrar rosto <nome>."
        match = self.reconhecer(camera_index=camera_index)
        if not match:
            return "Nenhum rosto detectado na camera."
        if match.name == "desconhecido":
            return "Rosto detectado, mas nao reconhecido. Cadastre esta pessoa para identificacao."
        return f"Rosto reconhecido: {match.name} (confianca {match.confidence:.0%})."
