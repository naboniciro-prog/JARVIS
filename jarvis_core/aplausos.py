"""Detector de aplausos robusto.

Un aplauso es un sonido muy corto y muy fuerte que sube de golpe y se apaga
enseguida. La voz, la música o un golpe largo duran más, así que se descartan.
El umbral se adapta solo al ruido del ambiente (antes era fijo y por eso
dejaba de funcionar cuando cambiaba el ruido de la habitación).
"""

from __future__ import annotations

import numpy as np

SUBTRAMA_SEG = 0.010          # analizamos de a 10 ms
VENTANA_DECAIMIENTO_SEG = 0.10  # un aplauso se apaga en ~100 ms
MAX_SUBTRAMAS_FUERTES = 3       # más de 30 ms fuerte = no es aplauso
NIVEL_MINIMO = 2500.0           # en escala int16 (0..32767)
RELACION_RUIDO = 7.0            # cuántas veces más fuerte que el ruido de fondo


class DetectorAplausos:
    def __init__(
        self,
        sample_rate: int = 16000,
        cantidad: int = 2,
        sensibilidad: float = 1.0,
        separacion_minima_seg: float = 0.12,
        separacion_maxima_seg: float = 0.9,
    ) -> None:
        self.sr = sample_rate
        self.cantidad = max(1, int(cantidad))
        self.sensibilidad = max(0.2, float(sensibilidad))
        self.sep_min = separacion_minima_seg
        self.sep_max = separacion_maxima_seg
        self.n_sub = int(self.sr * SUBTRAMA_SEG)
        self.n_decay = int(VENTANA_DECAIMIENTO_SEG / SUBTRAMA_SEG)
        self.reset()

    # ------------------------------------------------------------------
    def reset(self) -> None:
        self.t = 0.0
        self.ruido = 300.0
        self._resto = np.zeros(0, dtype=np.float32)
        self._prev_rms = 0.0
        self._candidato: dict | None = None
        self._aplausos: list[float] = []
        self._bloqueado_hasta = 0.0

    @property
    def umbral(self) -> float:
        return max(NIVEL_MINIMO, self.ruido * RELACION_RUIDO) / self.sensibilidad

    # ------------------------------------------------------------------
    def procesar(self, bloque: np.ndarray) -> bool:
        """Recibe audio int16 mono. Devuelve True si se completó el patrón."""
        datos = np.concatenate([self._resto, bloque.astype(np.float32).ravel()])
        n = len(datos) // self.n_sub
        self._resto = datos[n * self.n_sub:]
        disparo = False
        for i in range(n):
            sub = datos[i * self.n_sub:(i + 1) * self.n_sub]
            rms = float(np.sqrt(np.mean(sub * sub)))
            if self._paso(rms):
                disparo = True
            self.t += SUBTRAMA_SEG
        return disparo

    def _paso(self, rms: float) -> bool:
        umbral = self.umbral
        disparo = False

        if self._candidato is not None:
            c = self._candidato
            c["restantes"] -= 1
            if rms > c["pico"] * 0.5:
                c["fuertes"] += 1
            if c["restantes"] <= 0:
                self._candidato = None
                if c["fuertes"] <= MAX_SUBTRAMAS_FUERTES:
                    disparo = self._registrar(c["t"])
                else:
                    self._aplausos.clear()  # era voz o música
        elif rms > umbral and self._prev_rms < umbral * 0.6 and self.t >= self._bloqueado_hasta:
            # subida brusca: posible aplauso, vemos si se apaga rápido
            self._candidato = {"t": self.t, "pico": rms, "fuertes": 0, "restantes": self.n_decay}

        if self._candidato is None:
            # aprendemos el ruido de fondo: rápido con sonidos normales y muy
            # despacio con sonidos fuertes y continuos (música, tele)
            velocidad = 0.02 if rms < umbral else 0.002
            self.ruido += velocidad * (max(rms, 50.0) - self.ruido)

        if self._aplausos and self.t - self._aplausos[-1] > self.sep_max and self._candidato is None:
            self._aplausos.clear()

        self._prev_rms = rms
        return disparo

    def _registrar(self, t: float) -> bool:
        if self._aplausos:
            dif = t - self._aplausos[-1]
            if dif < self.sep_min:
                return False
            if dif > self.sep_max:
                self._aplausos.clear()
        self._aplausos.append(t)
        if len(self._aplausos) >= self.cantidad:
            self._aplausos.clear()
            self._bloqueado_hasta = t + 1.0
            return True
        return False
