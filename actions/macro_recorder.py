# -*- coding: utf-8 -*-
"""
macro_recorder.py — Sistema de grabación y reproducción de macros físicos de teclado y ratón para ILUM.
Utiliza las librerías `keyboard` y `mouse` para registrar eventos a nivel del sistema operativo.
"""
import time
import json
import keyboard
import mouse
import threading
import winsound
import difflib
import numpy as np
import sounddevice as sd
from pathlib import Path
from memory.config_manager import BASE_DIR
import actions.direct_input as direct_input
import ctypes

class DisableMouseAcceleration:
    """Desactiva temporalmente la Aceleración de Puntero (Enhance Pointer Precision) de Windows para asegurar 1:1 en macros 3D."""
    def __init__(self):
        self.original_params = (ctypes.c_int * 3)()
        self.changed = False
        
    def __enter__(self):
        try:
            ctypes.windll.user32.SystemParametersInfoW(0x0003, 0, self.original_params, 0)
            if self.original_params[2] == 1:
                new_params = (ctypes.c_int * 3)(self.original_params[0], self.original_params[1], 0)
                ctypes.windll.user32.SystemParametersInfoW(0x0004, 0, new_params, 0x01 | 0x02)
                self.changed = True
        except: pass
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.changed:
            try:
                ctypes.windll.user32.SystemParametersInfoW(0x0004, 0, self.original_params, 0x01 | 0x02)
            except: pass

def play_beep(freq=800, duration=0.15):
    try:
        # Usar winsound (bloqueante) garantiza que el sonido se escuche por completo
        winsound.Beep(int(freq), int(duration * 1000))
    except:
        pass

MACROS_FILE = BASE_DIR / "config" / "macros.json"
GLOBAL_STOP_MACRO = False

def record_macro_until_esc(macro_name: str):
    """
    Graba eventos de teclado y ratón hasta que se presiona la tecla ESC.
    Guarda los eventos en config/macros.json.
    """
    print(f"[MACRO] Iniciando grabación de '{macro_name}' en 3 segundos...")
    for _ in range(30):
        time.sleep(0.1)
        if keyboard.is_pressed("esc"):
            print("[MACRO] Grabación cancelada antes de iniciar.")
            return

    play_beep(1000, 0.3) # Sonido agradable de inicio
    print(f"[MACRO] ¡GRABANDO! Presiona ESC para detener.")
    
    events = []
    start_time = time.time()
    
    # Listas para guardar eventos temporalmente
    keyboard_events = []
    mouse_events = []
    
    # Callback del teclado
    def on_keyboard_event(e):
        if e.name == "esc":
            return
        keyboard_events.append({
            "type": "keyboard",
            "time": e.time - start_time,
            "event_type": e.event_type, # 'down' o 'up'
            "name": e.name,
            "scan_code": e.scan_code
        })
        
    from actions.raw_mouse import RawMouseCapture
    raw_mouse_capture = RawMouseCapture()
    raw_mouse_capture.start()
    
    # Callback del ratón
    def on_mouse_event(e):
        event_dict = {
            "type": "mouse",
            "time": e.time - start_time
        }
        if isinstance(e, mouse.MoveEvent):
            dx, dy = raw_mouse_capture.get_and_reset_deltas()
            if dx == 0 and dy == 0:
                return # Ignorar eventos inyectados o sin movimiento físico (ej. SetCursorPos del juego)
                
            event_dict["event_type"] = "move"
            event_dict["x"] = e.x
            event_dict["y"] = e.y
            event_dict["dx"] = dx
            event_dict["dy"] = dy
        elif isinstance(e, mouse.ButtonEvent):
            event_dict["event_type"] = e.event_type # 'up', 'down', 'double'
            event_dict["button"] = e.button
        elif isinstance(e, mouse.WheelEvent):
            event_dict["event_type"] = "wheel"
            event_dict["delta"] = e.delta
        else:
            return
        mouse_events.append(event_dict)

    keyboard.hook(on_keyboard_event)
    mouse.hook(on_mouse_event)
    
    # Esperar hasta que se presione ESC (non-blocking) y deshabilitar aceleración
    with DisableMouseAcceleration():
        while True:
            try:
                if keyboard.is_pressed("esc"):
                    break
            except:
                pass
            time.sleep(0.05)
            
    raw_mouse_capture.stop()
    keyboard.unhook(on_keyboard_event)
    mouse.unhook(on_mouse_event)
    print(f"[MACRO] Grabación detenida.")
    
    # Combinar y ordenar eventos cronológicamente
    all_events = keyboard_events + mouse_events
    all_events.sort(key=lambda x: x["time"])
    
    # Guardar en archivo
    MACROS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if MACROS_FILE.exists():
        try:
            with open(MACROS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
            
    data[macro_name] = all_events
    
    with open(MACROS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
        
    play_beep(800, 0.15)
    print(f"[MACRO] Macro '{macro_name}' guardado con {len(all_events)} eventos.")
    return macro_name

def play_macro(macro_name: str, loop: bool = False, times: int = 1):
    """
    Reproduce un macro grabado previamente por nombre usando difflib para búsqueda exacta/aproximada.
    """
    global GLOBAL_STOP_MACRO
    GLOBAL_STOP_MACRO = False

    if not MACROS_FILE.exists():
        print("[MACRO] No hay macros guardados.")
        return False, "No hay macros guardados."
        
    try:
        with open(MACROS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[MACRO] Error leyendo archivo de macros: {e}")
        return False, f"Error leyendo archivo de macros: {e}"
        
    # Búsqueda difusa (Fuzzy Matching)
    best_match = macro_name
    events = data.get(macro_name)
    
    if not events:
        matches = difflib.get_close_matches(macro_name, data.keys(), n=1, cutoff=0.4)
        if matches:
            best_match = matches[0]
            events = data.get(best_match)
        else:
            print(f"[MACRO] El macro '{macro_name}' no existe y no se encontró similitud.")
            return False, f"El macro '{macro_name}' no existe."
            
    print(f"[MACRO] Reproduciendo macro '{best_match}' ({len(events)} eventos)...")
    play_beep(1000, 0.15)
    
    # Para poder cancelar la reproducción local
    stop_playback = False
    playback_start_time = time.time()
    def check_stop():
        nonlocal stop_playback
        if time.time() - playback_start_time > 0.5:  # Ignorar si se presiona en los primeros 0.5s
            stop_playback = True
    
    cb = keyboard.add_hotkey("esc", check_stop)
    
    def _playback_thread():
        nonlocal stop_playback
        run_count = 0
        with DisableMouseAcceleration():
            while True:
                start_time = time.perf_counter()
                last_x, last_y = None, None
                
                for event in events:
                    if stop_playback or GLOBAL_STOP_MACRO or keyboard.is_pressed("esc"):
                        if time.time() - playback_start_time > 0.5:
                            print("[MACRO] Reproducción cancelada por el usuario.")
                            stop_playback = True
                            break
                        
                    # High-precision wait loop
                    target_time = start_time + event["time"]
                    while True:
                        now = time.perf_counter()
                        wait_time = target_time - now
                        if wait_time <= 0:
                            break
                        if wait_time > 0.005:
                            time.sleep(0.001)
                        
                    if event["type"] == "keyboard":
                        try:
                            if event["event_type"] == "down":
                                direct_input.press_key_raw(event["scan_code"])
                            elif event["event_type"] == "up":
                                direct_input.release_key_raw(event["scan_code"])
                        except Exception as e:
                            print(f"[MACRO] Error tecla {event}: {e}")
                            
                    elif event["type"] == "mouse":
                        try:
                            if event["event_type"] == "move":
                                if "dx" in event and "dy" in event:
                                    direct_input.mouse_move_raw(int(event["dx"]), int(event["dy"]))
                                else:
                                    ex, ey = event["x"], event["y"]
                                    if last_x is not None and last_y is not None:
                                        dx = ex - last_x
                                        dy = ey - last_y
                                        direct_input.mouse_move_raw(int(dx), int(dy))
                                    else:
                                        mouse.move(ex, ey)
                                    last_x, last_y = ex, ey
                            elif event["event_type"] == "down":
                                direct_input.mouse_down_raw(event.get("button", "left"))
                            elif event["event_type"] == "up":
                                direct_input.mouse_up_raw(event.get("button", "left"))
                            elif event["event_type"] == "double":
                                direct_input.mouse_click(event.get("button", "left"))
                                direct_input.mouse_click(event.get("button", "left"))
                            elif event["event_type"] == "wheel":
                                direct_input.mouse_wheel_raw(event["delta"])
                        except Exception as e:
                            print(f"[MACRO] Error ratón {event}: {e}")
                            
                if stop_playback or GLOBAL_STOP_MACRO:
                    break
                
                run_count += 1
                is_loop = str(loop).lower() == "true"
                if not is_loop and run_count >= times:
                    break

        try:
            keyboard.remove_hotkey(cb)
        except: pass
        
        play_beep(600, 0.20)
        print(f"[MACRO] Reproducción finalizada.")

    threading.Thread(target=_playback_thread, daemon=True).start()
    return True, best_match

def delete_macro(macro_name: str):
    """Elimina un macro guardado usando difflib para búsqueda exacta/aproximada."""
    if not MACROS_FILE.exists():
        return False, "No hay macros guardados."
        
    try:
        with open(MACROS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return False, f"Error leyendo archivo de macros: {e}"
        
    best_match = macro_name
    if macro_name not in data:
        matches = difflib.get_close_matches(macro_name, data.keys(), n=1, cutoff=0.4)
        if matches:
            best_match = matches[0]
        else:
            return False, f"El macro '{macro_name}' no existe y no se encontró similitud."
            
    del data[best_match]
    
    with open(MACROS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
        
    print(f"[MACRO] Macro '{best_match}' eliminado.")
    return True, best_match
