"""
Visual Memory & Desktop Context
===============================
Guarda un registro ligero de la ventana activa para memoria a largo plazo.
"""

import json
import time
import threading
from pathlib import Path
try:
    import pygetwindow as gw
except ImportError:
    gw = None

MEMORY_FILE = Path("config/visual_memory.json")
_memory_thread = None
_running = False

def _memory_loop():
    while _running:
        try:
            if gw:
                active_window = gw.getActiveWindow()
                if active_window and active_window.title:
                    title = active_window.title.strip()
                    if title:
                        # Load existing
                        data = []
                        if MEMORY_FILE.exists():
                            try:
                                data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
                            except Exception:
                                pass
                        
                        # Add new entry if it's different from the last one
                        if not data or data[-1].get("title") != title:
                            entry = {
                                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                                "title": title
                            }
                            data.append(entry)
                            
                            # Keep only last 1000 entries (approx a few days of switching)
                            if len(data) > 1000:
                                data = data[-1000:]
                                
                            MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
                            MEMORY_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
        
        # Guardar contexto cada 30 segundos
        time.sleep(30)

def start_visual_memory():
    global _memory_thread, _running
    if not _running:
        _running = True
        _memory_thread = threading.Thread(target=_memory_loop, daemon=True)
        _memory_thread.start()

def visual_memory(parameters: dict, player=None) -> str:
    action = parameters.get("action", "search").lower()
    query = parameters.get("query", "").lower()
    
    if action == "start":
        start_visual_memory()
        return "👁️ Memoria Visual iniciada en segundo plano."
        
    elif action == "search":
        if not MEMORY_FILE.exists():
            return "❌ No hay memoria visual guardada aún."
            
        try:
            data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
            matches = []
            for item in reversed(data):
                if query in item["title"].lower():
                    matches.append(f"{item['timestamp']}: {item['title']}")
                    if len(matches) >= 5: # top 5 results
                        break
                        
            if matches:
                res = "\n".join(matches)
                return f"🧠 Esto es lo que recuerdo sobre '{query}':\n{res}"
            else:
                return f"🧠 No recuerdo haber visto nada relacionado con '{query}' recientemente."
        except Exception as e:
            return f"❌ Error leyendo la memoria visual: {e}"
            
    return "❌ Acción no reconocida en memoria visual."
