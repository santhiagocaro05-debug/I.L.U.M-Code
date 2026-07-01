"""
Holographic Translator (Subtítulos en Vivo para Sordos)
=======================================================
Despliega una ventana Tkinter transparente con texto neón que transcribe en tiempo real el audio del sistema/micrófono.
"""

import subprocess
import os
import sys
from pathlib import Path

def holographic_translator(parameters: dict, player=None) -> str:
    action = parameters.get("action", "start").lower()
    
    if action == "start":
        if player: player.write_log("🌐 Iniciando Holograma de Subtítulos en Vivo...")
        
        script_code = """
import tkinter as tk
import threading
import json
import os
import sys
from pathlib import Path

try:
    import pyaudio
    import vosk
except ImportError:
    print("PyAudio or Vosk not installed.")
    sys.exit(1)

# Determinar ruta del modelo
base_dir = Path(__file__).resolve().parent.parent
model_path = base_dir / "config" / "vosk_model"

if not model_path.exists():
    print("Vosk model not found.")
    sys.exit(1)

vosk.SetLogLevel(-1)
model = vosk.Model(str(model_path))
recognizer = vosk.KaldiRecognizer(model, 16000)

root = tk.Tk()
root.title("ILUM Live Captions")
root.overrideredirect(True)
root.attributes("-topmost", True)
root.attributes("-alpha", 0.85)
root.attributes("-transparentcolor", "black")
root.configure(bg="black")

# Dimensiones y posición: centrado abajo
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
w = int(screen_width * 0.8)
h = 150
x = int((screen_width - w) / 2)
y = screen_height - 200
root.geometry(f"{w}x{h}+{x}+{y}")

label = tk.Label(
    root, 
    text="[🎙️ Escuchando...]", 
    font=("Arial", 28, "bold"), 
    fg="#00FFCC", 
    bg="black",
    wraplength=w-40,
    justify="center"
)
label.pack(expand=True, fill="both")

def audio_listen_loop():
    p = pyaudio.PyAudio()
    try:
        # Usa el dispositivo de entrada por defecto (puede ser Stereo Mix si el usuario lo configuró)
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=8000)
        stream.start_stream()
        
        while True:
            data = stream.read(4000, exception_on_overflow=False)
            if recognizer.AcceptWaveform(data):
                res = json.loads(recognizer.Result())
                text = res.get("text", "")
                if text:
                    label.config(text=text.upper())
            else:
                res = json.loads(recognizer.PartialResult())
                partial = res.get("partial", "")
                if partial:
                    label.config(text=partial.upper())
    except Exception as e:
        label.config(text=f"[Error de Audio: {e}]")
    finally:
        p.terminate()

t = threading.Thread(target=audio_listen_loop, daemon=True)
t.start()

# Atajo para cerrar la ventana con un clic
root.bind("<Button-1>", lambda e: root.destroy())

root.mainloop()
"""
        temp_file = Path(__file__).resolve().parent.parent / "config" / "holo_live.py"
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(script_code)
            
        subprocess.Popen([sys.executable, str(temp_file)])
        return "🌐 Traductor Holográfico desplegado permanentemente. Clickea el texto para cerrarlo."
        
    return "❌ Acción no reconocida para el traductor holográfico."
