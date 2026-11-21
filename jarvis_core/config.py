"""Carga de configuración: config.json (ajustes) + .env (claves secretas)."""

from __future__ import annotations

import copy
import json
import logging
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVO_CONFIG = RAIZ / "config.json"
ARCHIVO_ENV = RAIZ / ".env"

log = logging.getLogger("jarvis.config")

DEFAULTS: dict = {
    "nombre": "Jarvis",
    "como_llamarte": "señor",
    "idioma_reconocimiento": "es-AR",
    "voz": "es-AR-TomasNeural",
    "velocidad_voz": "+5%",
    "volumen_voz": "+0%",
    "microfono": "",
    "parlante": "",
    "activar_con_palabra": True,
    "sensibilidad_palabra": 0.5,
    "activar_con_aplausos": True,
    "aplausos": {
        "cantidad": 2,
        "sensibilidad": 1.0,
        "separacion_minima_seg": 0.12,
        "separacion_maxima_seg": 0.9,
    },
    "modo_conversacion": True,
    "segundos_espera_conversacion": 6,
    "segundos_maximos_frase": 12,
    "ciudad_clima": "Buenos Aires",
    "modelo_ia": "claude-opus-5-5",
    "esfuerzo_ia": "low",
    "programas": {
        "chrome": "chrome",
        "navegador": "chrome",
        "spotify": "spotify:",
        "bloc de notas": "notepad",
        "calculadora": "calc",
        "explorador": "explorer",
        "archivos": "explorer",
        "word": "winword",
        "excel": "excel",
        "configuracion": "ms-settings:",
    },
    "paginas": {
        "youtube": "https://www.youtube.com",
        "google": "https://www.google.com",
        "whatsapp": "https://web.whatsapp.com",
        "gmail": "https://mail.google.com",
        "netflix": "https://www.netflix.com",
    },
}


def _mezclar(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _mezclar(out[k], v)
        else:
            out[k] = v
    return out


def cargar_env(ruta: Path = ARCHIVO_ENV) -> None:
    """Lee el .env sin pisar variables que ya existan en el sistema."""
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        clave, valor = clave.strip(), valor.strip().strip('"').strip("'")
        if valor and clave not in os.environ:
            os.environ[clave] = valor


def cargar_config(ruta: Path = ARCHIVO_CONFIG) -> dict:
    cargar_env()
    datos: dict = {}
    if ruta.exists():
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            log.error("config.json tiene un error (línea %s): %s. Uso valores por defecto.", e.lineno, e.msg)
    return _mezclar(DEFAULTS, datos)
