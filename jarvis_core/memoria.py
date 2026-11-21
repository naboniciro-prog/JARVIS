"""Memoria permanente: cosas que le pedís a Jarvis que recuerde."""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from pathlib import Path

from .config import RAIZ

log = logging.getLogger("jarvis.memoria")


class Memoria:
    def __init__(self, ruta: Path = RAIZ / "datos" / "memoria.json") -> None:
        self.ruta = ruta
        self._lock = threading.Lock()
        self.datos: list[dict] = []
        if ruta.exists():
            try:
                self.datos = json.loads(ruta.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                log.error("No pude leer la memoria (%s). Empiezo vacía.", e)

    def recordar(self, dato: str) -> None:
        with self._lock:
            self.datos.append({"dato": dato.strip(), "fecha": datetime.now().strftime("%Y-%m-%d")})
            self._guardar()

    def olvidar_todo(self) -> None:
        with self._lock:
            self.datos = []
            self._guardar()

    def _guardar(self) -> None:
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.ruta.write_text(json.dumps(self.datos, ensure_ascii=False, indent=2), encoding="utf-8")

    def como_texto(self) -> str:
        return "\n".join(f"- {d['dato']} (guardado el {d['fecha']})" for d in self.datos)
