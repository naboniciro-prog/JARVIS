"""Programa principal de Jarvis."""

from __future__ import annotations

import logging
import logging.handlers
import queue
import random
import signal
import sys
import threading

from .aplausos import DetectorAplausos
from .cerebro import Cerebro
from .comandos import Comandos
from .config import RAIZ, cargar_config
from .memoria import Memoria
from .microfono import Microfono
from .oido import ErrorReconocimiento, grabar_frase, transcribir
from .palabra import DetectorPalabra
from .voz import Voz

log = logging.getLogger("jarvis")

SALUDOS = ["¿Sí, {u}?", "Dígame, {u}.", "A sus órdenes.", "¿En qué te ayudo?", "Te escucho."]


def configurar_logs() -> None:
    carpeta = RAIZ / "logs"
    carpeta.mkdir(exist_ok=True)
    archivo = logging.handlers.RotatingFileHandler(
        carpeta / "jarvis.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    archivo.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    consola = logging.StreamHandler(sys.stdout)
    consola.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))
    logging.basicConfig(level=logging.INFO, handlers=[archivo, consola])


class Jarvis:
    def __init__(self) -> None:
        self.config = c = cargar_config()
        self.recordatorios: queue.Queue[str] = queue.Queue()
        self.corriendo = True

        self.mic = Microfono(c["microfono"])
        self.voz = Voz(c["voz"], c["velocidad_voz"], c["volumen_voz"], c["parlante"],
                       al_empezar=self.mic.silenciar, al_terminar=self.mic.activar)
        self.memoria = Memoria()
        self.cerebro = Cerebro(c, self.memoria)
        self.comandos = Comandos(c, self.memoria, self._programar_recordatorio)

        self.palabra = DetectorPalabra(c["sensibilidad_palabra"]) if c["activar_con_palabra"] else None
        a = c["aplausos"]
        self.aplausos = DetectorAplausos(
            cantidad=a["cantidad"], sensibilidad=a["sensibilidad"],
            separacion_minima_seg=a["separacion_minima_seg"],
            separacion_maxima_seg=a["separacion_maxima_seg"],
        ) if c["activar_con_aplausos"] else None

    # ------------------------------------------------------------------
    def _programar_recordatorio(self, segundos: float, que: str) -> None:
        t = threading.Timer(segundos, lambda: self.recordatorios.put(que))
        t.daemon = True
        t.start()
        log.info("Recordatorio en %.0f s: %s", segundos, que)

    def _decir_recordatorios(self) -> None:
        while not self.recordatorios.empty():
            que = self.recordatorios.get()
            self.voz.pitido(1046)
            self.voz.decir(f"{self.config['como_llamarte'].capitalize()}, te recuerdo: {que}.")

    # ------------------------------------------------------------------
    def iniciar(self) -> None:
        c = self.config
        self.mic.abrir()
        formas = []
        if self.palabra and self.palabra.disponible:
            formas.append("decí 'Hey Jarvis'")
        if self.aplausos:
            formas.append(f"aplaudí {c['aplausos']['cantidad']} veces")
        if not formas:
            log.error("No hay ninguna forma de activarme. Revisá config.json.")
            return
        log.info("=" * 60)
        log.info("%s listo. Para llamarlo: %s.", c["nombre"], " o ".join(formas))
        log.info("Para cerrarlo: decile 'apagate' o apretá Ctrl+C.")
        log.info("=" * 60)
        self.voz.decir(f"{c['nombre']} en línea. A sus órdenes, {c['como_llamarte']}.")

        while self.corriendo:
            self._decir_recordatorios()
            bloque = self.mic.leer(timeout=0.5)
            if bloque is None:
                continue
            por_palabra = self.palabra.procesar(bloque) if self.palabra else False
            por_aplauso = self.aplausos.procesar(bloque) if self.aplausos else False
            if por_palabra or por_aplauso:
                log.info("Activado por %s", "palabra" if por_palabra else "aplausos")
                try:
                    self._conversar(saludar=por_aplauso)
                except Exception:  # noqa: BLE001
                    log.exception("Error inesperado durante la conversación")
                    self.voz.decir("Perdón, tuve un error. Ya estoy listo de nuevo.")
                self._reiniciar_detectores()
        log.info("Jarvis apagado.")

    def _reiniciar_detectores(self) -> None:
        if self.palabra:
            self.palabra.reset()
        if self.aplausos:
            ruido = self.aplausos.ruido
            self.aplausos.reset()
            self.aplausos.ruido = ruido
        self.mic.vaciar()

    def _conversar(self, saludar: bool) -> None:
        c = self.config
        if saludar:
            self.voz.decir(random.choice(SALUDOS).format(u=c["como_llamarte"]))
        else:
            self.voz.pitido()
        ruido = self.aplausos.ruido if self.aplausos else 300.0
        espera = 7.0
        intentos_fallidos = 0

        while self.corriendo:
            audio = grabar_frase(self.mic, espera_inicio_seg=espera,
                                 maximo_seg=c["segundos_maximos_frase"], ruido_fondo=ruido)
            if not audio:
                log.info("No dijiste nada; vuelvo a esperar.")
                return
            try:
                texto = transcribir(audio, c["idioma_reconocimiento"])
            except ErrorReconocimiento as e:
                log.error("%s", e)
                self.voz.decir("No tengo conexión para entenderte. Revisá internet.")
                return
            if not texto:
                intentos_fallidos += 1
                if intentos_fallidos >= 2:
                    return
                self.voz.decir("No te entendí bien, ¿me lo repetís?")
                continue
            intentos_fallidos = 0
            print(f"\n  Vos: {texto}")

            resultado = self.comandos.manejar(texto)
            if resultado is not None:
                print(f"  {c['nombre']}: {resultado.respuesta}\n")
                self.voz.decir(resultado.respuesta)
                if resultado.accion == "salir":
                    self.corriendo = False
                    return
                if resultado.accion == "fin_conversacion":
                    return
            else:
                dicho = self.voz.decir_por_partes(self.cerebro.responder(texto))
                print(f"  {c['nombre']}: {dicho}\n")

            if not c["modo_conversacion"]:
                return
            espera = float(c["segundos_espera_conversacion"])  # seguí hablando sin volver a llamarlo


def main() -> None:
    configurar_logs()
    jarvis = Jarvis()

    def _cortar(*_):
        log.info("Cerrando...")
        jarvis.corriendo = False
    signal.signal(signal.SIGINT, _cortar)

    try:
        jarvis.iniciar()
    except KeyboardInterrupt:
        pass
    except Exception:  # noqa: BLE001
        log.exception("Jarvis se cerró por un error. Mirá logs/jarvis.log")
        raise
    finally:
        jarvis.mic.cerrar()


if __name__ == "__main__":
    main()
