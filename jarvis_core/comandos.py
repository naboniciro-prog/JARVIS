"""Comandos que Jarvis resuelve al instante, sin IA."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import unicodedata
import urllib.parse
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from .memoria import Memoria

log = logging.getLogger("jarvis.comandos")

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
NUMEROS = {"un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
           "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "quince": 15, "veinte": 20,
           "treinta": 30, "cuarenta": 40, "cincuenta": 50, "media": 0.5}


def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[¿?¡!.,;:]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


@dataclass
class Resultado:
    respuesta: str
    accion: str | None = None  # "salir", "fin_conversacion"


class Sistema:
    """Acciones sobre la PC. Separado para poder probarlo sin Windows."""

    def abrir(self, objetivo: str) -> None:
        if objetivo.startswith("http"):
            webbrowser.open(objetivo)
        elif sys.platform == "win32":
            os.startfile(objetivo)  # type: ignore[attr-defined]  # noqa: S606
        else:
            subprocess.Popen(["xdg-open", objetivo])  # noqa: S603,S607

    def tecla(self, codigo: int, veces: int = 1) -> None:
        if sys.platform != "win32":
            log.info("Tecla %s x%s (sólo funciona en Windows)", hex(codigo), veces)
            return
        import ctypes
        for _ in range(veces):
            ctypes.windll.user32.keybd_event(codigo, 0, 0, 0)
            ctypes.windll.user32.keybd_event(codigo, 0, 2, 0)


VK_SUBIR, VK_BAJAR, VK_MUTE = 0xAF, 0xAE, 0xAD
VK_PLAY, VK_SIGUIENTE, VK_ANTERIOR = 0xB3, 0xB0, 0xB1


class Comandos:
    def __init__(
        self,
        config: dict,
        memoria: Memoria,
        programar_recordatorio: Callable[[float, str], None],
        sistema: Sistema | None = None,
    ) -> None:
        self.config = config
        self.memoria = memoria
        self.programar_recordatorio = programar_recordatorio
        self.sistema = sistema or Sistema()
        self._nombre = normalizar(config["nombre"])

    # ------------------------------------------------------------------
    def manejar(self, texto: str) -> Resultado | None:
        t = normalizar(texto)
        t = re.sub(rf"^(hey |oye |che )?{self._nombre}\s*", "", t).strip()  # "Jarvis, ..." -> "..."
        if not t:
            return None
        for metodo in (self._salir, self._fin, self._hora, self._fecha, self._volumen, self._musica_control,
                       self._recordatorio, self._recordar, self._olvidar, self._clima,
                       self._poner_musica, self._buscar, self._abrir):
            r = metodo(t)
            if r is not None:
                return r
        return None

    # ------------------------------------------------------------------
    def _salir(self, t: str) -> Resultado | None:
        if re.fullmatch(r"(apagate|desconectate|anda a dormir|a dormir|cerrate|salir|chau|adios)( jarvis)?", t):
            return Resultado(f"Hasta luego, {self.config['como_llamarte']}.", "salir")
        return None

    def _fin(self, t: str) -> Resultado | None:
        if re.fullmatch(r"(nada|nada mas|eso es todo|listo|gracias|muchas gracias|ok gracias|esta bien gracias|no)", t):
            return Resultado("A su disposición.", "fin_conversacion")
        return None

    def _hora(self, t: str) -> Resultado | None:
        if re.search(r"\b(que hora|la hora|hora es)\b", t):
            ahora = datetime.now()
            h, m = ahora.hour, ahora.minute
            h12 = h % 12 or 12
            hora = "Es la una" if h12 == 1 else f"Son las {h12}"
            return Resultado(f"{hora} en punto." if m == 0 else f"{hora} y {m}.")
        return None

    def _fecha(self, t: str) -> Resultado | None:
        if re.search(r"\b(que dia|que fecha|la fecha|dia es hoy|fecha es hoy)\b", t):
            hoy = datetime.now()
            return Resultado(f"Hoy es {DIAS[hoy.weekday()]} {hoy.day} de {MESES[hoy.month - 1]} de {hoy.year}.")
        return None

    def _volumen(self, t: str) -> Resultado | None:
        if re.search(r"\b(subi|sube|subir|aumenta)\b.*\bvolumen\b|\bmas (fuerte|volumen)\b", t):
            self.sistema.tecla(VK_SUBIR, 5)
            return Resultado("Listo, más fuerte.")
        if re.search(r"\b(baja|bajar)\b.*\bvolumen\b|\bmas (bajo|despacio)\b", t):
            self.sistema.tecla(VK_BAJAR, 5)
            return Resultado("Listo, más bajo.")
        if re.search(r"\b(silencia|silencio|mutea|mute)\b", t):
            self.sistema.tecla(VK_MUTE)
            return Resultado("Silenciado.")
        return None

    def _musica_control(self, t: str) -> Resultado | None:
        if re.search(r"\b(pausa|para|frena|segui|continua|reanuda)\b.*\b(musica|cancion|tema|video)\b", t):
            self.sistema.tecla(VK_PLAY)
            return Resultado("Hecho.")
        if re.search(r"\b(siguiente|proxima|pasa)\b.*\b(cancion|tema)\b|\bsiguiente\b$", t):
            self.sistema.tecla(VK_SIGUIENTE)
            return Resultado("Siguiente.")
        if re.search(r"\b(anterior)\b.*\b(cancion|tema)\b|\b(cancion|tema) anterior\b", t):
            self.sistema.tecla(VK_ANTERIOR)
            return Resultado("Anterior.")
        return None

    def _recordatorio(self, t: str) -> Resultado | None:
        m = re.search(r"\brecorda(?:me|rme)\b en (\d+|\w+) (segundos?|minutos?|horas?)(?: (?:que|de|a))? (.+)", t)
        if not m:
            m2 = re.search(r"\brecorda(?:me|rme)\b en media hora(?: (?:que|de|a))? (.+)", t)
            if not m2:
                return None
            cantidad, unidad, que = 30, "minutos", m2.group(1)
        else:
            crudo, unidad, que = m.groups()
            cantidad = float(crudo) if crudo.isdigit() else NUMEROS.get(crudo)
            if cantidad is None:
                return Resultado("No entendí en cuánto tiempo. Decime por ejemplo: recordame en diez minutos que...")
        factor = 1 if unidad.startswith("segundo") else 60 if unidad.startswith("minuto") else 3600
        self.programar_recordatorio(cantidad * factor, que)
        n = int(cantidad) if float(cantidad).is_integer() else cantidad
        return Resultado(f"Perfecto, te aviso en {n} {unidad}.")

    def _recordar(self, t: str) -> Resultado | None:
        m = re.match(r"^(recorda|acordate|anota|guarda) (que |esto )?(.+)", t)
        if m and not t.startswith(("recordame", "recordarme")):
            self.memoria.recordar(m.group(3))
            return Resultado("Anotado, no me lo olvido.")
        if re.search(r"\bque (te acordas|recordas|sabes) de mi\b", t):
            datos = self.memoria.como_texto()
            return Resultado("Todavía no me contaste nada para recordar." if not datos else
                             "Esto es lo que recuerdo: " + "; ".join(d["dato"] for d in self.memoria.datos) + ".")
        return None

    def _olvidar(self, t: str) -> Resultado | None:
        if re.search(r"\bolvida(te)? (todo|lo que te dije)\b|\bborra (la|tu) memoria\b", t):
            self.memoria.olvidar_todo()
            return Resultado("Listo, borré todo lo que tenía anotado.")
        return None

    def _clima(self, t: str) -> Resultado | None:
        if not re.search(r"\b(clima|tiempo hace|temperatura|va a llover|llueve|hace frio|hace calor)\b", t):
            return None
        ciudad = self.config.get("ciudad_clima") or "Buenos Aires"
        try:
            import requests
            url = f"https://wttr.in/{urllib.parse.quote(ciudad)}?format=j1&lang=es"
            datos = requests.get(url, timeout=6).json()
            actual = datos["current_condition"][0]
            desc = actual.get("lang_es", [{}])[0].get("value") or actual["weatherDesc"][0]["value"]
            hoy = datos["weather"][0]
            return Resultado(
                f"En {ciudad} hace {actual['temp_C']} grados, {desc.lower()}. "
                f"Hoy la mínima es de {hoy['mintempC']} y la máxima de {hoy['maxtempC']}."
            )
        except Exception as e:  # noqa: BLE001
            log.error("No pude consultar el clima: %s", e)
            return Resultado("No pude consultar el clima ahora.")

    def _poner_musica(self, t: str) -> Resultado | None:
        m = re.match(r"^(pone|pon|poneme|reproduci|reproduce|escuchar|quiero escuchar) (musica |la cancion |el tema |un tema |algo )?(de )?(.+)", t)
        if not m:
            return None
        que = m.group(4)
        self.sistema.abrir("https://www.youtube.com/results?search_query=" + urllib.parse.quote(que))
        return Resultado(f"Te busco {que} en YouTube.")

    def _buscar(self, t: str) -> Resultado | None:
        m = re.match(r"^(busca|buscar|googlea|busca en google) (en google )?(.+)", t)
        if not m:
            return None
        que = m.group(3)
        self.sistema.abrir("https://www.google.com/search?q=" + urllib.parse.quote(que))
        return Resultado(f"Busco {que}.")

    def _abrir(self, t: str) -> Resultado | None:
        m = re.match(r"^(abri|abrir|abre|abrime|ejecuta|inicia|lanza) (el |la |los |las |un |una )?(.+)", t)
        if not m:
            return None
        nombre = m.group(3).strip()
        programas = {normalizar(k): v for k, v in self.config.get("programas", {}).items()}
        paginas = {normalizar(k): v for k, v in self.config.get("paginas", {}).items()}
        for tabla in (programas, paginas):
            for clave, destino in tabla.items():
                if clave == nombre or clave in nombre.split() or nombre in clave:
                    try:
                        self.sistema.abrir(destino)
                        return Resultado(f"Abriendo {clave}.")
                    except Exception as e:  # noqa: BLE001
                        log.error("No pude abrir %s (%s): %s", clave, destino, e)
                        return Resultado(f"No pude abrir {clave}.")
        return Resultado(f"No conozco el programa {nombre}. Podés agregarlo en el archivo config.")
