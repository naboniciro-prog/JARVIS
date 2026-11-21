"""Voz de Jarvis.

Arreglo de la voz "gangosa": el audio se decodifica directamente a la
frecuencia exacta del parlante y en mono, así nunca se reproduce a una
velocidad o calidad equivocada. Usa la voz neural de Microsoft (Edge TTS),
que suena mucho más natural; si no hay internet, cae a la voz de Windows.
"""

from __future__ import annotations

import asyncio
import logging
import queue
import re
import threading
from typing import Callable, Iterable

import numpy as np

log = logging.getLogger("jarvis.voz")

_EMOJIS = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")


def limpiar_texto(texto: str) -> str:
    """Saca markdown, emojis y símbolos que la voz leería en voz alta."""
    t = re.sub(r"```.*?```", " ", texto, flags=re.S)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)   # [texto](link) -> texto
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"[*_#`>|~]+", "", t)
    t = _EMOJIS.sub("", t)
    t = re.sub(r"^\s*[-•]\s+", "", t, flags=re.M)
    return re.sub(r"\s+", " ", t).strip()


def _sd():
    import sounddevice as sd
    return sd


class Voz:
    def __init__(
        self,
        voz: str = "es-AR-TomasNeural",
        velocidad: str = "+5%",
        volumen: str = "+0%",
        parlante: str = "",
        al_empezar: Callable[[], None] | None = None,
        al_terminar: Callable[[], None] | None = None,
    ) -> None:
        self.voz = voz
        self.velocidad = velocidad
        self.volumen = volumen
        self.al_empezar = al_empezar or (lambda: None)
        self.al_terminar = al_terminar or (lambda: None)
        self._dispositivo = None
        self._sr_salida = 48000
        self._pyttsx3 = None
        self._nombre_parlante = parlante
        self._configurar_salida()

    def _configurar_salida(self) -> None:
        try:
            from .microfono import buscar_dispositivo
            sd = _sd()
            self._dispositivo = buscar_dispositivo(self._nombre_parlante, "salida")
            info = sd.query_devices(self._dispositivo, "output")
            self._sr_salida = int(info["default_samplerate"])
            log.info("Parlante: %s a %s Hz", info["name"], self._sr_salida)
        except Exception as e:  # noqa: BLE001
            log.warning("No pude consultar el parlante (%s). Uso 48000 Hz.", e)

    # ------------------------------------------------------------------
    def _sintetizar_edge(self, texto: str) -> np.ndarray:
        import edge_tts
        import miniaudio

        async def _bajar() -> bytes:
            com = edge_tts.Communicate(texto, self.voz, rate=self.velocidad, volume=self.volumen)
            partes = []
            async for trozo in com.stream():
                if trozo["type"] == "audio":
                    partes.append(trozo["data"])
            return b"".join(partes)

        mp3 = asyncio.run(_bajar())
        if not mp3:
            raise RuntimeError("Edge TTS no devolvió audio")
        dec = miniaudio.decode(
            mp3, output_format=miniaudio.SampleFormat.SIGNED16,
            nchannels=1, sample_rate=self._sr_salida,
        )
        return np.frombuffer(dec.samples, dtype=np.int16)

    def _reproducir(self, audio: np.ndarray) -> None:
        sd = _sd()
        # 80 ms de silencio al principio: evita que se coma la primera sílaba
        relleno = np.zeros(int(self._sr_salida * 0.08), dtype=np.int16)
        sd.play(np.concatenate([relleno, audio]), samplerate=self._sr_salida, device=self._dispositivo, blocking=True)

    def _hablar_windows(self, texto: str) -> None:
        if self._pyttsx3 is None:
            import pyttsx3
            self._pyttsx3 = pyttsx3.init()
            for v in self._pyttsx3.getProperty("voices"):
                if "spanish" in v.name.lower() or "español" in v.name.lower() or "es" in str(v.languages).lower():
                    self._pyttsx3.setProperty("voice", v.id)
                    break
            self._pyttsx3.setProperty("rate", 175)
        self._pyttsx3.say(texto)
        self._pyttsx3.runAndWait()

    def _decir_uno(self, texto: str, audio: np.ndarray | None) -> None:
        if audio is not None:
            self._reproducir(audio)
        else:
            self._hablar_windows(texto)

    def _preparar(self, texto: str) -> np.ndarray | None:
        try:
            return self._sintetizar_edge(texto)
        except Exception as e:  # noqa: BLE001
            log.warning("Voz neural no disponible (%s). Uso la voz de Windows.", e)
            return None

    # ------------------------------------------------------------------
    def decir(self, texto: str) -> None:
        self.decir_por_partes([texto])

    def decir_por_partes(self, frases: Iterable[str]) -> str:
        """Habla cada frase apenas está lista, mientras prepara la siguiente.

        Devuelve todo lo que dijo.
        """
        listas: queue.Queue = queue.Queue(maxsize=3)
        dicho: list[str] = []

        def productor() -> None:
            try:
                for frase in frases:
                    limpia = limpiar_texto(frase)
                    if limpia:
                        dicho.append(limpia)
                        listas.put((limpia, self._preparar(limpia)))
            except Exception as e:  # noqa: BLE001
                log.exception("Error preparando la respuesta: %s", e)
                listas.put(("Perdón, tuve un problema y no puedo responder ahora.", None))
            finally:
                listas.put(None)

        hilo = threading.Thread(target=productor, daemon=True)
        hilo.start()
        self.al_empezar()
        try:
            while True:
                item = listas.get()
                if item is None:
                    break
                try:
                    self._decir_uno(*item)
                except Exception as e:  # noqa: BLE001
                    log.error("No pude reproducir el audio: %s", e)
        finally:
            self.al_terminar()
        return " ".join(dicho)

    def pitido(self, frecuencia: float = 880.0, duracion: float = 0.12) -> None:
        """Sonido corto para avisar que te está escuchando."""
        try:
            t = np.arange(int(self._sr_salida * duracion)) / self._sr_salida
            envolvente = np.minimum(1.0, np.minimum(t, duracion - t) * 40)
            tono = (np.sin(2 * np.pi * frecuencia * t) * envolvente * 9000).astype(np.int16)
            self.al_empezar()  # que el micrófono no grabe el pitido
            try:
                _sd().play(tono, samplerate=self._sr_salida, device=self._dispositivo, blocking=True)
            finally:
                self.al_terminar()
        except Exception as e:  # noqa: BLE001
            log.debug("No pude hacer el pitido: %s", e)
