"""Conversación con IA (Claude). Responde por partes para empezar a hablar rápido."""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from typing import Iterator

from .memoria import Memoria

log = logging.getLogger("jarvis.cerebro")

MAX_TURNOS = 12  # cuánta conversación reciente recuerda

_FIN_FRASE = re.compile(r"[.!?…:;]\s+")


def partir_en_frases(trozos: Iterator[str], minimo: int = 25) -> Iterator[str]:
    """Junta el texto que llega de a pedacitos y lo entrega frase por frase.

    Las frases muy cortas ("Claro.") se juntan con la siguiente, para que la
    voz no haga pausas raras. Un punto sin espacio después ("3.5") no corta.
    """
    buffer = ""
    for trozo in trozos:
        buffer += trozo
        while True:
            corte = next((m for m in _FIN_FRASE.finditer(buffer) if m.start() + 1 >= minimo), None)
            if corte is None:
                break
            frase = buffer[:corte.start() + 1].strip()
            buffer = buffer[corte.end():]
            if frase:
                yield frase
    if buffer.strip():
        yield buffer.strip()


class Cerebro:
    def __init__(self, config: dict, memoria: Memoria) -> None:
        self.config = config
        self.memoria = memoria
        self.historial: list[dict] = []
        self._cliente = None
        if os.environ.get("ANTHROPIC_API_KEY"):
            try:
                import anthropic
                self._cliente = anthropic.Anthropic(timeout=30.0, max_retries=2)
            except Exception as e:  # noqa: BLE001
                log.error("No pude iniciar la IA: %s", e)
        else:
            log.warning("Falta ANTHROPIC_API_KEY en el archivo .env: la charla con IA está apagada.")

    @property
    def disponible(self) -> bool:
        return self._cliente is not None

    def _sistema(self) -> str:
        c = self.config
        recuerdos = self.memoria.como_texto() or "(nada todavía)"
        return (
            f"Sos {c['nombre']}, el asistente personal por voz de tu dueño, a quien le decís "
            f"'{c['como_llamarte']}'. Hablás en español rioplatense, con calidez y un toque de humor "
            "elegante, como un mayordomo inteligente.\n"
            "Todo lo que escribís se lee en voz alta, así que:\n"
            "- Respondé corto: una a tres frases, salvo que te pidan explicar algo en detalle.\n"
            "- Nada de markdown, listas, emojis, tablas ni links. Escribí los números como se dicen.\n"
            "- Si no sabés algo actual (noticias, precios), decilo con honestidad.\n"
            "- El texto del usuario viene de reconocimiento de voz y puede tener errores; "
            "interpretá la intención más probable.\n"
            f"Cosas que el usuario te pidió que recuerdes:\n{recuerdos}"
        )

    def responder(self, texto: str) -> Iterator[str]:
        """Devuelve la respuesta frase por frase."""
        if not self.disponible:
            yield ("Para charlar necesito la clave de la IA. Agregala en el archivo punto env "
                   "y reiniciame.")
            return

        import anthropic

        ahora = datetime.now().strftime("%A %d/%m/%Y %H:%M")
        mensajes = self.historial + [{"role": "user", "content": f"[{ahora}] {texto}"}]
        completo: list[str] = []

        def trozos() -> Iterator[str]:
            with self._cliente.beta.messages.stream(
                model=self.config["modelo_ia"],
                max_tokens=2048,
                system=self._sistema(),
                messages=mensajes,
                output_config={"effort": self.config.get("esfuerzo_ia", "low")},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            ) as stream:
                for t in stream.text_stream:
                    completo.append(t)
                    yield t
                final = stream.get_final_message()
                if final.stop_reason == "refusal":
                    log.warning("La IA rechazó la consulta: %s", final.stop_details)
                    if not completo:
                        yield "Prefiero no responder eso."

        try:
            yield from partir_en_frases(trozos())
        except anthropic.AuthenticationError:
            log.error("La clave de la IA es inválida o venció.")
            yield "La clave de la IA no funciona. Revisá el archivo punto env."
            return
        except anthropic.RateLimitError:
            log.error("Límite de uso de la IA alcanzado.")
            yield "Estoy recibiendo demasiados pedidos. Probá de nuevo en un ratito."
            return
        except anthropic.APIStatusError as e:
            log.error("Error de la IA (%s): %s", e.status_code, e.message)
            if e.status_code in (402, 403) or "credit" in str(e.message).lower():
                yield "Parece que se terminaron los créditos de la IA."
            else:
                yield "Tuve un problema con la IA. Probá de nuevo."
            return
        except anthropic.APIConnectionError:
            log.error("Sin conexión con la IA.")
            yield "No tengo conexión a internet en este momento."
            return

        respuesta = "".join(completo).strip()
        if respuesta:
            self.historial += [mensajes[-1], {"role": "assistant", "content": respuesta}]
            self.historial = self.historial[-MAX_TURNOS * 2:]

    def olvidar_conversacion(self) -> None:
        self.historial = []
