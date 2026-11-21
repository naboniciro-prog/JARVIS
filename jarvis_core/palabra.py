"""Detector local de la palabra de activación "Hey Jarvis" (openWakeWord).

Corre en tu PC, sin internet y sin gastar API. Es mucho más confiable que
mandar todo lo que oye el micrófono a reconocimiento de voz.
"""

from __future__ import annotations

import logging
import time

import numpy as np

log = logging.getLogger("jarvis.palabra")


class DetectorPalabra:
    def __init__(self, sensibilidad: float = 0.5) -> None:
        self.umbral = min(0.95, max(0.1, float(sensibilidad)))
        self._modelo = None
        self._espera_hasta = 0.0
        try:
            import openwakeword
            from openwakeword.model import Model
            try:
                self._modelo = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
            except Exception:  # noqa: BLE001  (modelos no descargados todavía)
                openwakeword.utils.download_models(model_names=["hey_jarvis"])
                self._modelo = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
            log.info("Palabra de activación lista: 'Hey Jarvis' (umbral %.2f)", self.umbral)
        except Exception as e:  # noqa: BLE001
            log.error("No pude cargar la palabra de activación (%s). Funcionan sólo los aplausos.", e)

    @property
    def disponible(self) -> bool:
        return self._modelo is not None

    def procesar(self, bloque: np.ndarray) -> bool:
        if self._modelo is None:
            return False
        puntajes = self._modelo.predict(bloque)
        puntaje = max(puntajes.values()) if puntajes else 0.0
        if puntaje >= self.umbral and time.monotonic() >= self._espera_hasta:
            log.info("Escuché 'Hey Jarvis' (confianza %.2f)", puntaje)
            self._espera_hasta = time.monotonic() + 1.5
            self.reset()
            return True
        return False

    def reset(self) -> None:
        if self._modelo is not None:
            self._modelo.reset()
