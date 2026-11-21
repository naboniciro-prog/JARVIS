import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jarvis_core.aplausos import DetectorAplausos  # noqa: E402
from jarvis_core.cerebro import partir_en_frases  # noqa: E402
from jarvis_core.comandos import Comandos  # noqa: E402
from jarvis_core.config import DEFAULTS  # noqa: E402
from jarvis_core.memoria import Memoria  # noqa: E402
from jarvis_core.microfono import remuestrear  # noqa: E402
from jarvis_core.voz import limpiar_texto  # noqa: E402

SR = 16000
rng = np.random.default_rng(0)


def ruido(seg, nivel=200):
    return rng.normal(0, nivel, int(SR * seg))


def aplauso():
    n = int(SR * 0.05)
    env = np.exp(-np.arange(n) / (SR * 0.006))
    return rng.normal(0, 14000, n) * env


def armar(*partes):
    return np.clip(np.concatenate(partes), -32768, 32767).astype(np.int16)


def correr(det, audio):
    hits = 0
    for i in range(0, len(audio), 1280):
        if det.procesar(audio[i:i + 1280]):
            hits += 1
    return hits


def test_doble_aplauso_activa():
    audio = armar(ruido(1.0), aplauso(), ruido(0.35), aplauso(), ruido(1.0))
    assert correr(DetectorAplausos(), audio) == 1


def test_un_aplauso_no_activa():
    audio = armar(ruido(1.0), aplauso(), ruido(2.0))
    assert correr(DetectorAplausos(), audio) == 0


def test_aplausos_muy_separados_no_activan():
    audio = armar(ruido(1.0), aplauso(), ruido(1.5), aplauso(), ruido(1.0))
    assert correr(DetectorAplausos(), audio) == 0


def test_voz_o_musica_fuerte_no_activa():
    t = np.arange(int(SR * 0.6)) / SR
    tono = np.sin(2 * np.pi * 220 * t) * 12000
    audio = armar(ruido(1.0), tono, ruido(0.3), tono, ruido(1.0))
    assert correr(DetectorAplausos(), audio) == 0


def test_se_adapta_a_ambiente_ruidoso():
    # mucho ruido de fondo (ventilador, tele bajita) y aplausos encima
    base = 1500
    audio = armar(ruido(2.0, base), aplauso() * 2, ruido(0.4, base), aplauso() * 2, ruido(1.0, base))
    det = DetectorAplausos()
    assert correr(det, audio) == 1
    assert det.ruido > 1000


def test_ruido_de_fondo_solo_no_activa():
    assert correr(DetectorAplausos(), armar(ruido(5.0, 800))) == 0


def test_remuestreo():
    x = np.ones(4800)
    assert len(remuestrear(x, 48000, 16000)) == 1600


def test_frases():
    trozos = ["Claro", ", señor. La capital de Fran", "cia es París. El número es 3.5 y ", "listo"]
    frases = list(partir_en_frases(iter(trozos)))
    assert frases == ["Claro, señor. La capital de Francia es París.", "El número es 3.5 y listo"]


def test_limpiar_texto():
    assert limpiar_texto("**Hola** 😀 mirá [esto](http://x.com) # ya") == "Hola mirá esto ya"


class SistemaFalso:
    def __init__(self):
        self.abiertos, self.teclas = [], []

    def abrir(self, o):
        self.abiertos.append(o)

    def tecla(self, c, veces=1):
        self.teclas.append((c, veces))


def crear_comandos(tmp_path):
    recordatorios = []
    sis = SistemaFalso()
    mem = Memoria(tmp_path / "m.json")
    cmd = Comandos(DEFAULTS, mem, lambda s, q: recordatorios.append((s, q)), sis)
    return cmd, sis, mem, recordatorios


def test_comandos(tmp_path):
    cmd, sis, mem, rec = crear_comandos(tmp_path)
    assert cmd.manejar("¿Qué hora es?").respuesta.startswith(("Son", "Es"))
    assert cmd.manejar("Jarvis, abrí Spotify").respuesta == "Abriendo spotify."
    assert sis.abiertos[-1] == "spotify:"
    assert cmd.manejar("abrí YouTube").respuesta == "Abriendo youtube."
    assert "youtube.com/results" in (cmd.manejar("poné música de Soda Stereo") and sis.abiertos[-1])
    cmd.manejar("subí el volumen")
    assert sis.teclas[-1] == (0xAF, 5)
    assert cmd.manejar("recordame en 10 minutos que saque la pizza").respuesta == "Perfecto, te aviso en 10 minutos."
    assert rec[-1] == (600, "saque la pizza")
    cmd.manejar("recordame en cinco segundos llamar a mamá")
    assert rec[-1] == (5, "llamar a mama")
    cmd.manejar("recordá que mi equipo es Boca")
    assert mem.datos[-1]["dato"] == "mi equipo es boca"
    assert cmd.manejar("apagate").accion == "salir"
    assert cmd.manejar("gracias").accion == "fin_conversacion"
    assert cmd.manejar("¿Quién fue San Martín?") is None  # va a la IA
