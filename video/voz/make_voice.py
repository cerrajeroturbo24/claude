"""Genera la voz en off en español y la mezcla con el vídeo.

Uso: python3 make_voice.py <modelo.onnx> <voces.bin> <video.mp4> <salida.mp4> [voz]
"""
import subprocess
import sys

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

MODEL, VOICES, VIDEO, OUT = sys.argv[1:5]
VOICE = sys.argv[5] if len(sys.argv) > 5 else "em_alex"
SR = 24000
TOTAL = 31.4

# (segundo de inicio, frase) sincronizado con las escenas de make_video.py
LINES = [
    (0.4, "Planet Web Diseño."),
    (3.0, "¿Quieres que tu negocio salga el primero en Google?"),
    (6.2, "Mira este caso real. Buscas: cerrajero Carabanchel, y la web que hicimos sale la primera."),
    (11.7, "Webs pensadas para que tu teléfono no pare de sonar."),
    (15.9, "Diseño profesional, rápido, y perfecto en el móvil."),
    (20.1, "Web, SEO local y ficha de Google. Desde cuatrocientos euros más IVA."),
    (24.1, "Diseñado en Madrid, para toda España."),
    (27.4, "Pide tu presupuesto sin compromiso, en serviciosplanet punto es."),
]

kokoro = Kokoro(MODEL, VOICES)
track = np.zeros(int(TOTAL * SR), dtype=np.float32)
for i, (start, text) in enumerate(LINES):
    end = LINES[i + 1][0] - 0.15 if i + 1 < len(LINES) else TOTAL - 0.3
    speed = 1.05
    while True:
        audio, sr = kokoro.create(text, voice=VOICE, speed=speed, lang="es")
        if len(audio) / sr <= end - start or speed >= 1.4:
            break
        speed += 0.05
    print(f"{start:5.1f}s  {len(audio) / sr:4.2f}s  x{speed:.2f}  {text}")
    a = int(start * SR)
    seg = audio[: len(track) - a]
    track[a:a + len(seg)] += seg

sf.write("voz.wav", track, SR)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", VIDEO, "-i", "voz.wav",
                "-af", "loudnorm=I=-16:TP=-1.5", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-shortest", OUT], check=True)
print("OK", OUT)
