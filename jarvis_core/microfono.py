"""Micrófono: elige el dispositivo por nombre, convierte a 16 kHz y se reconecta solo."""

from __future__ import annotations

import logging
import queue
import threading
import time

import numpy as np

log = logging.getLogger("jarvis.microfono")

SR = 16000
BLOQUE = 1280  # 80 ms, lo que espera el detector de palabra


def _sd():
    import sounddevice as sd  # import tardío: permite testear sin placa de sonido
    return sd


def listar_dispositivos() -> list[dict]:
    sd = _sd()
    out = []
    for i, d in enumerate(sd.query_devices()):
        out.append({
            "indice": i,
            "nombre": d["name"],
            "entradas": d["max_input_channels"],
            "salidas": d["max_output_channels"],
            "sr": d["default_samplerate"],
            "api": sd.query_hostapis(d["hostapi"])["name"],
        })
    return out


def buscar_dispositivo(nombre: str, tipo: str) -> int | None:
    """Busca por parte del nombre (sin importar mayúsculas). None = predeterminado."""
    if not nombre:
        return None
    clave = "entradas" if tipo == "entrada" else "salidas"
    candidatos = [d for d in listar_dispositivos() if d[clave] > 0 and nombre.lower() in d["nombre"].lower()]
    if not candidatos:
        log.warning("No encontré el dispositivo de %s '%s'. Uso el predeterminado.", tipo, nombre)
        return None
    # preferimos MME en Windows: es el que mejor convierte frecuencias
    candidatos.sort(key=lambda d: 0 if "MME" in d["api"] else 1)
    log.info("Dispositivo de %s: %s", tipo, candidatos[0]["nombre"])
    return candidatos[0]["indice"]


def remuestrear(audio: np.ndarray, sr_origen: int, sr_destino: int) -> np.ndarray:
    if sr_origen == sr_destino or len(audio) == 0:
        return audio
    n = int(round(len(audio) * sr_destino / sr_origen))
    x_viejo = np.linspace(0.0, 1.0, num=len(audio), endpoint=False)
    x_nuevo = np.linspace(0.0, 1.0, num=n, endpoint=False)
    return np.interp(x_nuevo, x_viejo, audio.astype(np.float32))


class Microfono:
    def __init__(self, nombre: str = "") -> None:
        self.nombre = nombre
        self.cola: queue.Queue[np.ndarray] = queue.Queue(maxsize=200)
        self._silenciado = threading.Event()
        self._buffer = np.zeros(0, dtype=np.float32)
        self._stream = None
        self._sr_real = SR
        self._ultimo_audio = time.monotonic()

    # ------------------------------------------------------------------
    def abrir(self) -> None:
        sd = _sd()
        dispositivo = buscar_dispositivo(self.nombre, "entrada")
        for sr in (SR, None):
            try:
                if sr is None:
                    info = sd.query_devices(dispositivo, "input")
                    sr = int(info["default_samplerate"])
                self._stream = sd.InputStream(
                    samplerate=sr, channels=1, dtype="int16",
                    blocksize=int(BLOQUE * sr / SR), device=dispositivo,
                    callback=self._callback,
                )
                self._stream.start()
                self._sr_real = sr
                self._ultimo_audio = time.monotonic()
                log.info("Micrófono abierto a %s Hz", sr)
                return
            except Exception as e:  # noqa: BLE001
                log.warning("No pude abrir el micrófono a %s Hz: %s", sr, e)
        raise RuntimeError("No pude abrir ningún micrófono. Revisá que esté conectado.")

    def cerrar(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:  # noqa: BLE001
                pass
            self._stream = None

    def reabrir(self) -> None:
        log.warning("Reconectando el micrófono...")
        self.cerrar()
        while True:
            try:
                self.abrir()
                return
            except RuntimeError as e:
                log.error("%s Reintento en 3 segundos.", e)
                time.sleep(3)

    # ------------------------------------------------------------------
    def _callback(self, indata, frames, time_info, status) -> None:  # noqa: ARG002
        if status:
            log.debug("Estado del micrófono: %s", status)
        self._ultimo_audio = time.monotonic()
        if self._silenciado.is_set():
            return
        audio = indata[:, 0].astype(np.float32)
        audio = remuestrear(audio, self._sr_real, SR)
        self._buffer = np.concatenate([self._buffer, audio])
        while len(self._buffer) >= BLOQUE:
            trozo = np.clip(self._buffer[:BLOQUE], -32768, 32767).astype(np.int16)
            self._buffer = self._buffer[BLOQUE:]
            try:
                self.cola.put_nowait(trozo)
            except queue.Full:
                try:
                    self.cola.get_nowait()
                except queue.Empty:
                    pass
                self.cola.put_nowait(trozo)

    def leer(self, timeout: float = 0.5) -> np.ndarray | None:
        try:
            return self.cola.get(timeout=timeout)
        except queue.Empty:
            if self._stream is not None and time.monotonic() - self._ultimo_audio > 4:
                self.reabrir()  # el micrófono se desconectó o se colgó
            return None

    def vaciar(self) -> None:
        self._buffer = np.zeros(0, dtype=np.float32)
        while True:
            try:
                self.cola.get_nowait()
            except queue.Empty:
                return

    def silenciar(self) -> None:
        self._silenciado.set()

    def activar(self) -> None:
        self.vaciar()
        self._silenciado.clear()
        self.vaciar()
