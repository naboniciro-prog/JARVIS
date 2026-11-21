"""Graba lo que decís después de activar a Jarvis y lo pasa a texto."""

from __future__ import annotations

import logging

import numpy as np

from .microfono import BLOQUE, SR, Microfono

log = logging.getLogger("jarvis.oido")

SEG_BLOQUE = BLOQUE / SR


class ErrorReconocimiento(Exception):
    pass


def _rms(b: np.ndarray) -> float:
    f = b.astype(np.float32)
    return float(np.sqrt(np.mean(f * f)))


def grabar_frase(
    mic: Microfono,
    espera_inicio_seg: float = 6.0,
    maximo_seg: float = 12.0,
    silencio_fin_seg: float = 0.9,
    ruido_fondo: float = 300.0,
) -> bytes:
    """Espera a que empieces a hablar y corta cuando hacés silencio.

    Devuelve audio PCM int16 a 16 kHz (vacío si no dijiste nada).
    """
    umbral = max(600.0, ruido_fondo * 3.0)
    previo: list[np.ndarray] = []   # guardamos un poquito antes de que empieces
    frase: list[np.ndarray] = []
    hablando = False
    esperado = silencio = duracion = 0.0

    while True:
        b = mic.leer(timeout=1.0)
        if b is None:
            esperado += 1.0
            if not hablando and esperado > espera_inicio_seg:
                return b""
            continue
        fuerte = _rms(b) > umbral
        if not hablando:
            previo = (previo + [b])[-4:]
            esperado += SEG_BLOQUE
            if fuerte:
                hablando = True
                frase = previo[:]
            elif esperado > espera_inicio_seg:
                return b""
            continue
        frase.append(b)
        duracion += SEG_BLOQUE
        silencio = 0.0 if fuerte else silencio + SEG_BLOQUE
        if silencio >= silencio_fin_seg or duracion >= maximo_seg:
            break

    audio = np.concatenate(frase)
    if len(audio) < SR * 0.35:  # menos de 0,35 s: fue un ruido
        return b""
    return audio.astype(np.int16).tobytes()


def transcribir(audio: bytes, idioma: str = "es-AR") -> str:
    if not audio:
        return ""
    import speech_recognition as sr

    rec = sr.Recognizer()
    datos = sr.AudioData(audio, SR, 2)
    try:
        texto = rec.recognize_google(datos, language=idioma)
    except sr.UnknownValueError:
        return ""
    except sr.RequestError as e:
        raise ErrorReconocimiento(f"No me pude conectar al reconocimiento de voz: {e}") from e
    log.info("Escuché: %s", texto)
    return texto.strip()
