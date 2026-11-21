"""Prueba de micrófono, aplausos, palabra de activación y voz.

Usalo para elegir el micrófono correcto y ver si Jarvis te escucha.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402

from jarvis_core.aplausos import DetectorAplausos  # noqa: E402
from jarvis_core.config import cargar_config  # noqa: E402
from jarvis_core.microfono import Microfono, listar_dispositivos  # noqa: E402


def mostrar_dispositivos() -> None:
    print("\n=== MICRÓFONOS ===")
    for d in listar_dispositivos():
        if d["entradas"] > 0:
            print(f"  [{d['indice']:>2}] {d['nombre']}  ({d['api']}, {int(d['sr'])} Hz)")
    print("\n=== PARLANTES ===")
    for d in listar_dispositivos():
        if d["salidas"] > 0:
            print(f"  [{d['indice']:>2}] {d['nombre']}  ({d['api']}, {int(d['sr'])} Hz)")
    print("\nPara elegir uno, copiá parte de su nombre en config.json, en \"microfono\" o \"parlante\".")
    print("Ojo: si usás audífonos Bluetooth, NO uses su micrófono (\"Manos libres\" / \"Hands-Free\"):")
    print("eso hace que la voz suene gangosa. Usá el micrófono de la PC o uno con cable.\n")


def probar_microfono(c: dict) -> None:
    from jarvis_core.palabra import DetectorPalabra

    mic = Microfono(c["microfono"])
    mic.abrir()
    a = c["aplausos"]
    aplausos = DetectorAplausos(cantidad=a["cantidad"], sensibilidad=a["sensibilidad"])
    palabra = DetectorPalabra(c["sensibilidad_palabra"])
    print("\nHablá, aplaudí o decí 'Hey Jarvis'. Ctrl+C para terminar.\n")
    try:
        while True:
            b = mic.leer()
            if b is None:
                continue
            nivel = float(np.sqrt(np.mean(b.astype(np.float32) ** 2)))
            barras = int(min(50, nivel / 300))
            extra = ""
            if aplausos.procesar(b):
                extra = "  <<< ¡APLAUSOS DETECTADOS! >>>"
            if palabra.procesar(b):
                extra = "  <<< ¡HEY JARVIS DETECTADO! >>>"
            print(f"\r  nivel {nivel:7.0f} |{'#' * barras:<50}| ruido {aplausos.ruido:5.0f}{extra:<35}",
                  end="", flush=True)
            if extra:
                print()
                time.sleep(0.3)
    except KeyboardInterrupt:
        print()
    finally:
        mic.cerrar()


def probar_voz(c: dict) -> None:
    from jarvis_core.voz import Voz

    v = Voz(c["voz"], c["velocidad_voz"], c["volumen_voz"], c["parlante"])
    v.pitido()
    v.decir(f"Hola {c['como_llamarte']}. Así suena mi voz. Si me escuchás gangoso, cambiá el parlante.")


if __name__ == "__main__":
    config = cargar_config()
    mostrar_dispositivos()
    print("1) Probar micrófono, aplausos y 'Hey Jarvis'")
    print("2) Probar la voz")
    opcion = input("Elegí 1 o 2: ").strip()
    if opcion == "2":
        probar_voz(config)
    else:
        probar_microfono(config)
    input("\nListo. Apretá Enter para cerrar.")
