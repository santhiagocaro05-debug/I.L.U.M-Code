# check_build.py
import sys
import os
import importlib

print("=== VERIFICACION DE COMPILACION ILUM ===\n")

critical_modules = [
    "PyQt6", "sounddevice", "vosk", "numpy", "google.genai",
    "playwright", "pyautogui", "psutil", "comtypes", "pycaw"
]

missing = []
for mod in critical_modules:
    try:
        importlib.import_module(mod)
        print(f"✅ {mod}")
    except ImportError:
        print(f"❌ {mod} - FALTA")
        missing.append(mod)

print(f"\n📦 Archivos necesarios:")
checks = [
    ("assets/jarvis_icono.ico", "Icono"),
    ("face.png", "Imagen UI"),
    ("config/api_keys.json", "Configuración API"),
    ("core/prompt.txt", "Prompt del sistema"),
]

for path, desc in checks:
    if os.path.exists(path):
        print(f"✅ {desc}: {path}")
    else:
        print(f"❌ {desc}: {path} - NO ENCONTRADO")

if missing:
    print(f"\n⚠️ Faltan {len(missing)} módulos. Ejecuta:")
    print(f"pip install {' '.join(missing)}")
else:
    print("\n✅ Todo listo para compilar!")