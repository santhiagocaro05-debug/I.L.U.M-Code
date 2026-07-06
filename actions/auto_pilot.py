# -*- coding: utf-8 -*-
"""
auto_pilot.py — Autonomous Screen Agent v4.0 (Vision + Actions + Gaming + Memory)
ILUM puede JUGAR por ti, TRABAJAR por ti y APRENDER de ti.

Características:
  - 20+ perfiles de juegos y apps
  - Memoria persistente (recuerda lo que hizo)
  - Detección de objetos en pantalla (OpenCV)
  - Grabación y reproducción de macros
  - Manejo de diálogos en juegos
  - Logging detallado para depuración
  - Soporte para emuladores
"""

import time
import threading
import io
import json
import re
import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

import pyautogui
import keyboard
from PIL import ImageGrab, Image

try:
    import importlib
    pytesseract = importlib.import_module('pytesseract')
    TESSERACT_AVAILABLE = True
except ImportError:
    pytesseract = None
    TESSERACT_AVAILABLE = False

# ============================================================
#  CONFIGURACIÓN DE LOGGING
# ============================================================

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

_logger = None

def get_logger() -> logging.Logger:
    """Obtiene o crea un logger para el autopiloto"""
    global _logger
    if _logger is None:
        log_file = LOG_DIR / f"autopilot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        _logger = logging.getLogger('AutoPilot')
        _logger.setLevel(logging.DEBUG)
        
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        _logger.addHandler(fh)
        
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(formatter)
        _logger.addHandler(ch)
        
        _logger.info("=== AutoPilot v4.0 Iniciado ===")
    return _logger

logger = get_logger()

# ============================================================
#  ESTADO GLOBAL
# ============================================================

_auto_pilot_running = False
_pilot_thread: Optional[threading.Thread] = None
_macro_recording = False
_macro_actions: List[Dict] = []

# ============================================================
#  SISTEMA DE MEMORIA
# ============================================================

class AutoPilotMemory:
    """Memoria persistente para el piloto automático"""
    
    def __init__(self):
        self.memory_file = Path("config/autopilot_memory.json")
        self.session_id = f"session_{int(time.time())}"
        self.data = self._load()
        logger.info(f"Memoria cargada: {len(self.data)} sesiones")
    
    def _load(self) -> dict:
        if self.memory_file.exists():
            try:
                return json.loads(self.memory_file.read_text(encoding="utf-8"))
            except:
                return {}
        return {}
    
    def _save(self):
        self.memory_file.write_text(json.dumps(self.data, indent=4), encoding="utf-8")
    
    def remember(self, key: str, value: str):
        """Guarda un recuerdo"""
        if self.session_id not in self.data:
            self.data[self.session_id] = {}
        self.data[self.session_id][key] = {
            "value": value,
            "timestamp": time.time()
        }
        self._save()
        logger.debug(f"Recordado: {key} = {value}")
    
    def recall(self, key: str) -> Optional[str]:
        """Recupera un recuerdo"""
        if self.session_id in self.data:
            entry = self.data[self.session_id].get(key)
            if entry:
                return entry["value"]
        return None
    
    def get_context(self) -> str:
        """Obtiene el contexto completo para el prompt"""
        if self.session_id not in self.data:
            return ""
        items = self.data[self.session_id].items()
        return "\n".join(f"Recordado: {k} = {v['value']}" for k, v in items)
    
    def clear_session(self):
        """Limpia la sesión actual"""
        if self.session_id in self.data:
            del self.data[self.session_id]
            self._save()
            logger.info(f"Sesión {self.session_id} eliminada")

_memory = AutoPilotMemory()

# ============================================================
#  PERFILES DE JUEGOS Y APPS (EXPANDIDO)
# ============================================================

GAME_PROFILES: Dict[str, Dict] = {
    # ─── JUEGOS POPULARES ────────────────────────────────────────────────────
    "minecraft": {
        "type": "game",
        "detection": ["minecraft"],
        "controls": {
            "forward": "w", "back": "s", "left": "a", "right": "d",
            "jump": "space", "sprint": "ctrl", "inventory": "e",
            "drop": "q", "attack": "left_click", "build": "right_click",
        },
        "play_style": "survival",
        "cycle_delay": 1.2,
        "icon": "⛏️"
    },
    "valorant": {
        "type": "game",
        "detection": ["valorant", "riot client"],
        "controls": {
            "forward": "w", "back": "s", "left": "a", "right": "d",
            "jump": "space", "crouch": "ctrl",
            "shoot": "left_click", "aim": "right_click",
            "reload": "r", "ability1": "q", "ability2": "e",
            "ability3": "c", "ultimate": "x", "spike": "4",
        },
        "play_style": "competitive",
        "cycle_delay": 0.8,
        "icon": "🎯"
    },
    "counter_strike": {
        "type": "game",
        "detection": ["counter-strike", "cs2", "csgo"],
        "controls": {
            "forward": "w", "back": "s", "left": "a", "right": "d",
            "jump": "space", "crouch": "ctrl", "walk": "shift",
            "shoot": "left_click", "aim": "right_click",
            "reload": "r", "buy": "b", "drop_weapon": "g",
            "inspect": "f", "knife": "3", "pistol": "1", "rifle": "2",
        },
        "play_style": "competitive",
        "cycle_delay": 0.6,
        "icon": "🔫"
    },
    "league_of_legends": {
        "type": "game",
        "detection": ["league of legends", "leagueoflegends"],
        "controls": {
            "move": "right_click", "attack": "a",
            "ability1": "q", "ability2": "w",
            "ability3": "e", "ability4": "r",
            "summoner1": "d", "summoner2": "f",
            "recall": "b", "shop": "p",
        },
        "play_style": "farming",
        "cycle_delay": 1.0,
        "icon": "⚔️"
    },
    "dota2": {
        "type": "game",
        "detection": ["dota 2", "dota2"],
        "controls": {
            "move": "right_click", "attack": "a",
            "ability1": "q", "ability2": "w", "ability3": "e", "ultimate": "r",
            "item1": "1", "item2": "2", "item3": "3",
            "item4": "4", "item5": "5", "item6": "6",
            "courier": "f2", "shop": "f4", "teleport": "t",
        },
        "play_style": "moba",
        "cycle_delay": 1.2,
        "icon": "🏆"
    },
    "fortnite": {
        "type": "game",
        "detection": ["fortnite"],
        "controls": {
            "forward": "w", "back": "s", "left": "a", "right": "d",
            "jump": "space", "crouch": "ctrl",
            "shoot": "left_click", "aim": "right_click",
            "reload": "r", "build_wall": "q", "build_floor": "f",
            "build_ramp": "c", "edit": "g",
        },
        "play_style": "battle_royale",
        "cycle_delay": 0.8,
        "icon": "🎮"
    },
    "warzone": {
        "type": "game",
        "detection": ["warzone", "call of duty"],
        "controls": {
            "forward": "w", "back": "s", "left": "a", "right": "d",
            "jump": "space", "crouch": "ctrl", "prone": "z",
            "shoot": "left_click", "aim": "right_click",
            "reload": "r", "sprint": "shift", "interact": "f",
            "plate": "4", "tactical": "q", "lethal": "e",
        },
        "play_style": "battle_royale",
        "cycle_delay": 0.8,
        "icon": "💥"
    },
    "gta_v": {
        "type": "game",
        "detection": ["gta v", "grand theft auto"],
        "controls": {
            "forward": "w", "back": "s", "left": "a", "right": "d",
            "sprint": "shift", "jump": "space", "crouch": "ctrl",
            "enter_vehicle": "f", "exit_vehicle": "f",
            "shoot": "left_click", "aim": "right_click",
            "reload": "r", "weapon_wheel": "tab",
            "phone": "up", "special": "e",
        },
        "play_style": "open_world",
        "cycle_delay": 1.5,
        "icon": "🚗"
    },
    "red_dead": {
        "type": "game",
        "detection": ["red dead", "rdr2"],
        "controls": {
            "forward": "w", "back": "s", "left": "a", "right": "d",
            "sprint": "shift", "jump": "space", "crouch": "ctrl",
            "shoot": "left_click", "aim": "right_click",
            "reload": "r", "interact": "e", "horse": "h",
            "menu": "tab", "dead_eye": "capslock",
        },
        "play_style": "open_world",
        "cycle_delay": 1.5,
        "icon": "🤠"
    },
    "rocket_league": {
        "type": "game",
        "detection": ["rocket league"],
        "controls": {
            "forward": "w", "back": "s", "left": "a", "right": "d",
            "jump": "space", "boost": "shift", "drift": "ctrl",
            "air_roll": "q", "ball_cam": "c",
        },
        "play_style": "sports",
        "cycle_delay": 0.8,
        "icon": "⚽"
    },
    "apex_legends": {
        "type": "game",
        "detection": ["apex legends"],
        "controls": {
            "forward": "w", "back": "s", "left": "a", "right": "d",
            "jump": "space", "crouch": "ctrl", "sprint": "shift",
            "shoot": "left_click", "aim": "right_click",
            "reload": "r", "ability": "q", "ultimate": "z",
            "interact": "e", "ping": "f",
        },
        "play_style": "battle_royale",
        "cycle_delay": 0.8,
        "icon": "🦅"
    },
    "overwatch": {
        "type": "game",
        "detection": ["overwatch"],
        "controls": {
            "forward": "w", "back": "s", "left": "a", "right": "d",
            "jump": "space", "crouch": "ctrl", "sprint": "shift",
            "shoot": "left_click", "aim": "right_click",
            "reload": "r", "ability1": "shift", "ability2": "e",
            "ultimate": "q", "melee": "v",
        },
        "play_style": "competitive",
        "cycle_delay": 0.8,
        "icon": "🔴"
    },
    "elden_ring": {
        "type": "game",
        "detection": ["elden ring"],
        "controls": {
            "forward": "w", "back": "s", "left": "a", "right": "d",
            "jump": "space", "sprint": "shift", "crouch": "ctrl",
            "attack": "left_click", "heavy": "shift+left_click",
            "guard": "right_click", "skill": "shift+right_click",
            "interact": "e", "use_item": "r",
        },
        "play_style": "souls",
        "cycle_delay": 2.0,
        "icon": "⚔️"
    },
    "cyberpunk": {
        "type": "game",
        "detection": ["cyberpunk 2077"],
        "controls": {
            "forward": "w", "back": "s", "left": "a", "right": "d",
            "sprint": "shift", "jump": "space", "crouch": "ctrl",
            "shoot": "left_click", "aim": "right_click",
            "reload": "r", "scan": "tab", "cyberware": "e",
        },
        "play_style": "rpg",
        "cycle_delay": 1.5,
        "icon": "💻"
    },
    # ─── EMULADORES ──────────────────────────────────────────────────────────
    "retroarch": {
        "type": "game",
        "detection": ["retroarch"],
        "controls": {
            "forward": "up", "back": "down", "left": "left", "right": "right",
            "jump": "z", "attack": "x", "special": "c",
            "start": "enter", "select": "shift",
        },
        "play_style": "retro",
        "cycle_delay": 1.0,
        "icon": "🕹️"
    },
    "dolphin": {
        "type": "game",
        "detection": ["dolphin emulator"],
        "controls": {
            "forward": "w", "back": "s", "left": "a", "right": "d",
            "jump": "space", "attack": "left_click",
            "a_button": "z", "b_button": "x",
        },
        "play_style": "emulator",
        "cycle_delay": 1.0,
        "icon": "🎮"
    },
    # ─── PRODUCTIVIDAD ──────────────────────────────────────────────────────
    "word": {
        "type": "productivity",
        "detection": ["microsoft word", "word -"],
        "cycle_delay": 2.5,
        "icon": "📝"
    },
    "excel": {
        "type": "productivity",
        "detection": ["microsoft excel", "excel -"],
        "cycle_delay": 2.5,
        "icon": "📊"
    },
    "powerpoint": {
        "type": "productivity",
        "detection": ["powerpoint"],
        "cycle_delay": 2.5,
        "icon": "📽️"
    },
    "outlook": {
        "type": "productivity",
        "detection": ["outlook"],
        "cycle_delay": 2.5,
        "icon": "📧"
    },
    "notepad": {
        "type": "productivity",
        "detection": ["notepad", "bloc de notas"],
        "cycle_delay": 2.0,
        "icon": "📄"
    },
    "notion": {
        "type": "productivity",
        "detection": ["notion"],
        "cycle_delay": 2.0,
        "icon": "📓"
    },
    "obsidian": {
        "type": "productivity",
        "detection": ["obsidian"],
        "cycle_delay": 2.0,
        "icon": "🗃️"
    },
    # ─── NAVEGADORES ─────────────────────────────────────────────────────────
    "chrome": {
        "type": "browser",
        "detection": ["chrome"],
        "cycle_delay": 2.0,
        "icon": "🌐"
    },
    "firefox": {
        "type": "browser",
        "detection": ["firefox"],
        "cycle_delay": 2.0,
        "icon": "🦊"
    },
    "edge": {
        "type": "browser",
        "detection": ["edge"],
        "cycle_delay": 2.0,
        "icon": "🌊"
    },
    "opera": {
        "type": "browser",
        "detection": ["opera"],
        "cycle_delay": 2.0,
        "icon": "🎭"
    },
    "brave": {
        "type": "browser",
        "detection": ["brave"],
        "cycle_delay": 2.0,
        "icon": "🦁"
    },
}

# ============================================================
#  DETECCIÓN DE APP ACTIVA
# ============================================================

def detect_current_app() -> Optional[Dict[str, Any]]:
    """Detecta la aplicación/juego en primer plano y devuelve su perfil."""
    try:
        import pygetwindow as gw
        active = gw.getActiveWindow()
        if not active:
            return None
        title = active.title.lower()
        logger.debug(f"Ventana activa: {title}")
        
        for app_name, profile in GAME_PROFILES.items():
            for keyword in profile.get("detection", []):
                if keyword.lower() in title:
                    logger.info(f"App detectada: {app_name} (coincidencia: '{keyword}')")
                    return {
                        "name": app_name,
                        "profile": profile,
                        "title": title,
                        "icon": profile.get("icon", "📱")
                    }
    except Exception as e:
        logger.error(f"Error detectando app: {e}")
    return None

# ============================================================
#  DETECCIÓN DE OBJETOS EN PANTALLA
# ============================================================

def detect_objects_on_screen(screenshot=None) -> Dict:
    """
    Detecta objetos en pantalla usando OpenCV
    Retorna dict con información detectada
    """
    try:
        import cv2
        import numpy as np
        
        if screenshot is None:
            screenshot = ImageGrab.grab()
        
        img = np.array(screenshot)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        h, w = img.shape[:2]
        
        result = {
            "enemies": [],
            "health": 0,
            "ammo": 0,
            "ui_elements": [],
            "text": ""
        }
        
        # Detectar colores específicos (ej. enemigos en rojo)
        lower_red = np.array([0, 0, 100])
        upper_red = np.array([100, 100, 255])
        red_mask = cv2.inRange(img, lower_red, upper_red)
        red_pixels = cv2.countNonZero(red_mask)
        
        if red_pixels > 1000:
            result["enemies"].append({
                "color": "red",
                "pixels": red_pixels,
                "estimated": max(1, red_pixels // 5000)
            })
        
        # Detectar UI (esquinas, bordes)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        ui_detected = cv2.countNonZero(edges) > 5000
        
        if ui_detected:
            result["ui_elements"].append("hud_detected")
        
        logger.debug(f"Detección de objetos: {len(result['enemies'])} enemigos")
        return result
        
    except ImportError:
        logger.warning("OpenCV no disponible. Instalar: pip install opencv-python")
        return {}
    except Exception as e:
        logger.error(f"Error detectando objetos: {e}")
        return {}

# ============================================================
#  DETECCIÓN DE DIÁLOGOS EN JUEGOS (VERSIÓN MEJORADA)
# ============================================================

def detect_dialogue(screenshot=None, lang: str = 'spa+eng') -> Optional[str]:
    """
    Detecta y extrae texto de diálogos en juegos usando OCR.
    
    Parámetros:
        screenshot: Imagen capturada (opcional, si es None captura la pantalla)
        lang: Idioma para OCR (default: 'spa+eng')
    
    Retorna:
        El texto detectado o None si no hay diálogo
    """
    # Verificar si Tesseract está disponible
    if not TESSERACT_AVAILABLE:
        logger.warning("Tesseract no disponible. OCR desactivado.")
        return None
    
    try:
        # Si no hay screenshot, capturar
        if screenshot is None:
            screenshot = ImageGrab.grab()
        
        # Obtener dimensiones
        h, w = screenshot.size
        
        # Área de diálogo (parte inferior de la pantalla)
        # Ajustable según el juego
        dialog_top = int(h * 0.70)    # 70% desde arriba
        dialog_bottom = int(h * 0.92) # 92% desde arriba
        
        # Recortar área de diálogo
        dialog_area = screenshot.crop((0, dialog_top, w, dialog_bottom))
        
        # Configuración optimizada para juegos
        # --psm 6: Asume un bloque de texto uniforme
        # whitelist: Solo caracteres válidos
        config = (
            '--psm 6 '  # Modo de segmentación
            '-c tessedit_char_whitelist='
            'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            'abcdefghijklmnopqrstuvwxyz'
            '0123456789'
            'áéíóúñüÁÉÍÓÚÑÜ'
            '.,!?;:()[]"\''
            ' '
        )
        
        # Ejecutar OCR
        text = pytesseract.image_to_string(
            dialog_area,
            lang=lang,
            config=config
        )
        
        # Limpiar texto
        text = text.strip()
        
        if text:
            logger.debug(f"Diálogo detectado: {text[:50]}...")
            return text
        
        return None
            
    except ImportError as e:
        logger.warning(f"pytesseract no disponible: {e}")
        return None
        
    except Exception as e:
        logger.error(f"Error detectando diálogo: {e}")
        return None

# ============================================================
#  SISTEMA DE MACROS
# ============================================================

class MacroSystem:
    """Sistema de grabación y reproducción de macros"""
    
    def __init__(self):
        self.macros_file = Path("config/autopilot_macros.json")
        self.macros = self._load()
        self.recording = False
        self.current_macro = []
        self.recording_thread = None
        
    def _load(self) -> dict:
        if self.macros_file.exists():
            try:
                return json.loads(self.macros_file.read_text(encoding="utf-8"))
            except:
                return {}
        return {}
    
    def _save(self):
        self.macros_file.write_text(json.dumps(self.macros, indent=4), encoding="utf-8")
    
    def start_recording(self):
        """Inicia la grabación de un macro"""
        self.recording = True
        self.current_macro = []
        logger.info("Grabación de macro iniciada")
        return "Grabación iniciada. Presiona F2 para detener."
    
    def stop_recording(self, name: str) -> str:
        """Detiene la grabación y guarda el macro"""
        if not self.current_macro:
            return "No se grabó ninguna acción."
        
        self.recording = False
        self.macros[name] = {
            "actions": self.current_macro,
            "created": datetime.now().isoformat(),
            "steps": len(self.current_macro)
        }
        self._save()
        logger.info(f"Macro '{name}' guardada con {len(self.current_macro)} pasos")
        return f"Macro '{name}' guardada con {len(self.current_macro)} pasos."
    
    def play_macro(self, name: str) -> str:
        """Reproduce un macro guardado"""
        if name not in self.macros:
            return f"Macro '{name}' no encontrada."
        
        actions = self.macros[name]["actions"]
        logger.info(f"Reproduciendo macro '{name}' ({len(actions)} pasos)")
        
        # Intentar importar direct_input
        try:
            import actions.direct_input as direct_input
        except:
            direct_input = None
        
        for action in actions:
            if not _auto_pilot_running:
                break
            try:
                _dispatch_action(action, direct_input)
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"Error en macro: {e}")
                return f"Error reproduciendo macro: {e}"
        
        return f"Macro '{name}' reproducida correctamente."
    
    def list_macros(self) -> str:
        """Lista las macros disponibles"""
        if not self.macros:
            return "No hay macros guardadas."
        
        result = "📋 Macros disponibles:\n"
        for name, info in self.macros.items():
            result += f"  • {name} ({info['steps']} pasos, {info['created'][:10]})\n"
        return result
    
    def delete_macro(self, name: str) -> str:
        """Elimina un macro"""
        if name not in self.macros:
            return f"Macro '{name}' no encontrada."
        
        del self.macros[name]
        self._save()
        return f"Macro '{name}' eliminada."

_macro_system = MacroSystem()

# ============================================================
#  DISPATCHER DE ACCIONES
# ============================================================

def _dispatch_action(action_obj: dict, direct_input) -> str:
    """Ejecuta una acción estructurada de forma segura."""
    t = action_obj.get("type", "")
    
    # Si está grabando macro, guardar acción
    if _macro_recording and t not in ("wait", "done", "stuck"):
        _macro_actions.append(action_obj.copy())
    
    logger.debug(f"Ejecutando acción: {t}")
    
    if t in ("click", "left_click"):
        btn = "left" if t == "left_click" else action_obj.get("button", "left")
        x, y = action_obj.get("x", 0), action_obj.get("y", 0)
        pyautogui.click(x, y, button=btn)
        return f"Click {btn} ({x},{y})"
    
    elif t == "right_click":
        x, y = action_obj.get("x", 0), action_obj.get("y", 0)
        pyautogui.click(x, y, button="right")
        return f"Click derecho ({x},{y})"
    
    elif t == "move":
        x, y = action_obj.get("x", 0), action_obj.get("y", 0)
        pyautogui.moveTo(x, y, duration=0.2)
        return f"Movido a ({x},{y})"
    
    elif t == "drag":
        pyautogui.moveTo(action_obj["x1"], action_obj["y1"])
        pyautogui.dragTo(
            action_obj["x2"], action_obj["y2"],
            duration=action_obj.get("duration", 0.5), button="left"
        )
        return f"Drag ({action_obj['x1']},{action_obj['y1']}) → ({action_obj['x2']},{action_obj['y2']})"
    
    elif t == "type":
        text = action_obj.get("text", "")
        try:
            import pyperclip
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
        except Exception:
            pyautogui.typewrite(text, interval=action_obj.get("interval", 0.05))
        return f"Escrito: {text[:50]}"
    
    elif t == "hotkey":
        keys = action_obj.get("keys", [])
        pyautogui.hotkey(*keys)
        return f"Hotkey: {'+'.join(keys)}"
    
    elif t == "key_press":
        key = action_obj.get("key", "")
        duration = action_obj.get("duration", 0.15)
        if direct_input:
            direct_input.press_key(key)
            time.sleep(duration)
            direct_input.release_key(key)
        else:
            pyautogui.press(key)
        return f"Tecla: {key} ({duration}s)"
    
    elif t == "key_hold":
        key = action_obj.get("key", "")
        if direct_input:
            direct_input.press_key_only(key)
        else:
            pyautogui.keyDown(key)
        return f"Sosteniendo: {key}"
    
    elif t == "key_release":
        key = action_obj.get("key", "")
        if direct_input:
            direct_input.release_key(key)
        else:
            pyautogui.keyUp(key)
        return f"Soltada: {key}"
    
    elif t == "scroll":
        pyautogui.scroll(
            action_obj.get("amount", 3),
            x=action_obj.get("x"), y=action_obj.get("y")
        )
        return f"Scroll {action_obj.get('amount')}"
    
    elif t == "wait":
        secs = action_obj.get("seconds", 1.0)
        time.sleep(secs)
        return f"Esperó {secs}s"
    
    else:
        return f"Acción desconocida '{t}' — omitida"

# ============================================================
#  CONSTRUCCIÓN DE PROMPTS (MEJORADA)
# ============================================================

def _build_prompt(goal: str, mode: str, history: list,
                  screen_w: int, screen_h: int,
                  app_name: str, controls: dict, play_style: str) -> str:
    
    recent = "\n".join(history[-6:]) if history else "ninguna aún"
    controls_str = json.dumps(controls, ensure_ascii=False) if controls else "{}"
    
    # Contexto de memoria
    memory_context = _memory.get_context()
    memory_line = f"\nContexto recordado:\n{memory_context}\n" if memory_context else ""
    
    # Detección de objetos (si está disponible)
    object_detection = ""
    try:
        objects = detect_objects_on_screen()
        if objects.get("enemies"):
            object_detection = f"\nEnemigos detectados: {len(objects['enemies'])}"
    except:
        pass
    
    if mode == "game":
        return f"""Eres un agente que JUEGA videojuegos de forma autónoma en Windows.
Juego: {app_name} | Estilo: {play_style} | Pantalla: {screen_w}x{screen_h}
Objetivo: {goal}
{memory_line}
Controles del juego:
{controls_str}
{object_detection}
Últimas acciones:
{recent}

Analiza la captura y decide el SIGUIENTE PASO para avanzar en el juego.
Observa: vida, munición, minimapa, enemigos, objetivos, posición del personaje.

REGLAS:
- Responde SOLO con un JSON válido, sin texto extra ni markdown.
- Movimiento/teclas del juego → type: "key_press" (usa direct_input, no pyautogui).
- Clicks de combate/interacción → type: "left_click" o "right_click" con x,y.
- Apuntar → type: "move" con coordenadas del objetivo en pantalla.
- Menús del juego → type: "click".
- Completado: {{"type":"done","reason":"..."}}
- Bloqueado: {{"type":"stuck","reason":"..."}}

Ejemplos:
{{"type":"key_press","key":"w","duration":0.6}}
{{"type":"left_click","x":960,"y":540}}
{{"type":"move","x":870,"y":420}}
{{"type":"key_press","key":"space","duration":0.1}}

JSON:"""

    else:  # desktop / browser / productivity
        return f"""Eres un asistente de escritorio autónomo en Windows.
App: {app_name} | Pantalla: {screen_w}x{screen_h}
Objetivo: {goal}
{memory_line}
Últimas acciones:
{recent}

Analiza la captura y decide el SIGUIENTE PASO para completar la tarea.
Si hay texto parcialmente escrito, continúa desde el cursor.

REGLAS:
- Responde SOLO con un JSON válido, sin texto extra ni markdown.
- Escribir texto → type: "type" (soporta tildes y ñ).
- Clicks → type: "click" con x,y exactos.
- Atajos → type: "hotkey" con lista de teclas.
- Navegar campos → type: "key_press" con key "tab"/"enter".
- Completado: {{"type":"done","reason":"..."}}
- Bloqueado: {{"type":"stuck","reason":"..."}}

Ejemplos:
{{"type":"type","text":"Estimado cliente, adjunto el informe solicitado."}}
{{"type":"click","x":760,"y":320,"button":"left"}}
{{"type":"hotkey","keys":["ctrl","s"]}}
{{"type":"key_press","key":"tab","duration":0.1}}

JSON:"""

# ============================================================
#  CAPTURA DE PANTALLA
# ============================================================

def _capture_screen(max_width: int = 1280):
    screenshot = ImageGrab.grab()
    orig_w, orig_h = screenshot.size
    screenshot.thumbnail((max_width, max_width * orig_h // orig_w))
    buf = io.BytesIO()
    screenshot.save(buf, format="JPEG", quality=85)
    return buf.getvalue(), orig_w, orig_h

# ============================================================
#  BUCLE PRINCIPAL (MEJORADO)
# ============================================================

def _auto_pilot_loop(goal: str, mode: str, player, speak):
    global _auto_pilot_running, _macro_recording, _macro_actions
    
    try:
        from google import genai
        from google.genai import types
        from memory.config_manager import load_api_keys
        import actions.direct_input as direct_input

        cfg = load_api_keys()
        api_key = cfg.get("gemini_api_key", "")
        if not api_key:
            _auto_pilot_running = False
            if speak:
                speak("Falta la API Key de Gemini para el Piloto Automático.")
            return

        client = genai.Client(api_key=api_key)
        logger.info(f"Iniciando AutoPilot: {goal} (modo: {mode})")

        # Detectar app si modo auto
        app_name = "desconocida"
        controls = {}
        play_style = "normal"
        cycle_delay = 1.5 if mode == "game" else 2.5
        app_icon = "🤖"

        app_info = detect_current_app()
        if app_info:
            app_name = app_info["name"]
            profile = app_info["profile"]
            controls = profile.get("controls", {})
            play_style = profile.get("play_style", "normal")
            cycle_delay = profile.get("cycle_delay", cycle_delay)
            app_icon = profile.get("icon", "📱")
            
            if mode == "auto":
                mode = profile.get("type", "desktop")
                if mode not in ("game", "desktop", "browser", "productivity"):
                    mode = "desktop"
                if mode in ("productivity", "browser"):
                    mode = "desktop"

        is_game = (mode == "game")
        max_iterations = 80 if is_game else 40
        MAX_STUCK = 3
        action_history = []
        stuck_count = 0
        last_error = ""

        mode_label = "🎮 JUEGO" if is_game else "💻 ESCRITORIO"
        
        if player:
            player.write_log(f"🤖 AutoPilot [{app_icon} {mode_label}] app={app_name} → {goal}")
        if speak:
            speak(f"Piloto automático activado en {app_name}. Modo {mode_label}. Presiona Escape para abortar.")

        logger.info(f"AutoPilot iniciado: {goal} en {app_name}")
        time.sleep(2)

        for iteration in range(1, max_iterations + 1):
            if not _auto_pilot_running:
                break
                
            if keyboard.is_pressed("esc"):
                if player: player.write_log("🛑 Abortado (ESC).")
                if speak: speak("Piloto automático abortado.")
                _auto_pilot_running = False
                break

            if player:
                player.write_log(f"🤖 [{mode_label}] {iteration}/{max_iterations} — {app_name}")

            # Captura
            try:
                img_data, orig_w, orig_h = _capture_screen()
            except Exception as e:
                logger.error(f"Captura fallida: {e}")
                if player: player.write_log(f"⚠️ Captura fallida: {e}")
                time.sleep(1)
                continue

            # Detectar diálogo si es juego
            dialogue = None
            if is_game:
                try:
                    screenshot = Image.open(io.BytesIO(img_data))
                    dialogue = detect_dialogue(screenshot)
                    if dialogue:
                        logger.info(f"Diálogo detectado: {dialogue[:100]}")
                        if player:
                            player.write_log(f"💬 Diálogo: {dialogue[:50]}...")
                except:
                    pass

            # Prompt
            prompt = _build_prompt(
                goal, mode, action_history,
                orig_w, orig_h, app_name, controls, play_style
            )
            
            if dialogue:
                prompt += f"\n\nDiálogo detectado en el juego: \"{dialogue}\"\nConsidera esto en tu decisión."

            # Gemini
            try:
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=[
                        types.Content(parts=[
                            types.Part(text=prompt),
                            types.Part(inline_data=types.Blob(
                                data=img_data, mime_type="image/jpeg"
                            )),
                        ])
                    ],
                    config=types.GenerateContentConfig(temperature=0.2),
                )
                raw = response.text.strip()
                logger.debug(f"Respuesta Gemini: {raw[:200]}...")
            except Exception as e:
                logger.error(f"Error Gemini: {e}")
                if player: player.write_log(f"⚠️ Error Gemini: {e}")
                time.sleep(2)
                continue

            # Parsear JSON
            clean = raw.replace("```json", "").replace("```", "").strip()
            json_match = re.search(r"\{.*\}", clean, re.DOTALL)
            if not json_match:
                logger.warning(f"Sin JSON en respuesta: {clean[:80]}")
                if player: player.write_log(f"⚠️ Sin JSON en respuesta")
                stuck_count += 1
                if stuck_count >= MAX_STUCK:
                    if player: player.write_log("❌ Demasiados errores. Abortando.")
                    break
                time.sleep(1)
                continue

            try:
                action_obj = json.loads(json_match.group())
            except json.JSONDecodeError as e:
                logger.error(f"JSON inválido: {e}")
                if player: player.write_log(f"⚠️ JSON inválido: {e}")
                stuck_count += 1
                if stuck_count >= MAX_STUCK:
                    break
                time.sleep(1)
                continue

            action_type = action_obj.get("type", "")

            # Estados terminales
            if action_type == "done":
                reason = action_obj.get("reason", "")
                _memory.remember("last_completed_task", f"{goal} - {reason}")
                if player: player.write_log(f"✅ Completado: {reason}")
                if speak: speak(f"Tarea completada. {reason}")
                _auto_pilot_running = False
                break

            if action_type == "stuck":
                reason = action_obj.get("reason", "")
                stuck_count += 1
                if player: player.write_log(f"⚠️ Atascado {stuck_count}/{MAX_STUCK}: {reason}")
                if stuck_count >= MAX_STUCK:
                    _memory.remember("stuck_reason", reason)
                    if speak: speak("Me he atascado y no puedo continuar.")
                    _auto_pilot_running = False
                    break
                time.sleep(2)
                continue

            # Ejecutar acción
            try:
                result = _dispatch_action(action_obj, direct_input)
                if player: player.write_log(f"✅ {result}")
                action_history.append(f"[{iteration}] {result}")
                stuck_count = 0
            except Exception as e:
                logger.error(f"Error ejecutando {action_obj}: {e}")
                if player: player.write_log(f"⚠️ Error: {e}")
                stuck_count += 1

            time.sleep(cycle_delay)

        if _auto_pilot_running:
            if player: player.write_log("⏰ Límite de pasos alcanzado.")
            if speak: speak("Piloto automático detenido por límite de pasos.")
        _auto_pilot_running = False

    except Exception as e:
        logger.error(f"Error crítico AutoPilot: {e}", exc_info=True)
        if player: player.write_log(f"❌ Error crítico: {e}")
        _auto_pilot_running = False

# ============================================================
#  FUNCIONES PÚBLICAS
# ============================================================

def auto_pilot(parameters: dict, player=None, speak=None) -> str:
    """
    Inicia o detiene el Piloto Automático.

    Parámetros:
        action : "start" | "stop" | "status"
        goal   : qué debe hacer (requerido para start)
        mode   : "game" | "desktop" | "auto" (default: "auto")
        macro  : "record" | "stop" | "play" | "list" | "delete"
        macro_name : nombre del macro
    """
    global _auto_pilot_running, _pilot_thread, _macro_recording, _macro_actions

    action = parameters.get("action", "start").lower()
    goal = parameters.get("goal", "").strip()
    mode = parameters.get("mode", "auto").lower()
    macro = parameters.get("macro", "")
    macro_name = parameters.get("macro_name", "")

    # ─── STATUS ──────────────────────────────────────────────────────────────
    if action == "status":
        status = "🟢 Activo" if _auto_pilot_running else "🔴 Inactivo"
        app_info = detect_current_app()
        app_name = app_info["name"] if app_info else "desconocida"
        return f"🤖 AutoPilot: {status}\nApp detectada: {app_name}\nMemoria: {len(_memory.data)} sesiones"

    # ─── MACROS ──────────────────────────────────────────────────────────────
    if macro:
        if macro == "record":
            if _macro_recording:
                return "Ya está grabando un macro."
            _macro_recording = True
            _macro_actions = []
            logger.info("Grabación de macro iniciada")
            return "🎬 Grabando macro. Presiona F2 o usa macro='stop' para detener."

        elif macro == "stop":
            if not _macro_recording:
                return "No hay ninguna grabación activa."
            if not macro_name:
                return "Proporciona 'macro_name' para guardar el macro."
            _macro_recording = False
            _macro_system.macros[macro_name] = {
                "actions": _macro_actions.copy(),
                "created": datetime.now().isoformat(),
                "steps": len(_macro_actions)
            }
            _macro_system._save()
            logger.info(f"Macro '{macro_name}' guardada con {len(_macro_actions)} pasos")
            return f"✅ Macro '{macro_name}' guardada con {len(_macro_actions)} pasos."

        elif macro == "play":
            if not macro_name:
                return "Proporciona 'macro_name' para reproducir."
            return _macro_system.play_macro(macro_name)

        elif macro == "list":
            return _macro_system.list_macros()

        elif macro == "delete":
            if not macro_name:
                return "Proporciona 'macro_name' para eliminar."
            return _macro_system.delete_macro(macro_name)

    # ─── STOP ────────────────────────────────────────────────────────────────
    if action == "stop":
        if _auto_pilot_running:
            _auto_pilot_running = False
            if player: player.write_log("🛑 Piloto detenido manualmente.")
            return "Piloto automático detenido."
        return "El piloto automático no estaba activo."

    # ─── START ──────────────────────────────────────────────────────────────
    if action == "start":
        if _auto_pilot_running:
            return "El piloto automático ya está activo. Usa action='stop' para detenerlo."
        if not goal:
            return (
                "Dime qué debo hacer. Ejemplos:\n"
                "  'juega Minecraft, consigue madera y crafea una mesa'\n"
                "  'termina de escribir el informe en Word'\n"
                "  'busca vuelos baratos a Cartagena en Chrome'"
            )
        if mode not in ("game", "desktop", "auto"):
            return "El parámetro 'mode' debe ser 'game', 'desktop' o 'auto'."

        _auto_pilot_running = True
        _pilot_thread = threading.Thread(
            target=_auto_pilot_loop,
            args=(goal, mode, player, speak),
            daemon=True,
        )
        _pilot_thread.start()

        return (
            f"🤖 Piloto Automático activado.\n"
            f"Objetivo: {goal}\n"
            f"Presiona ESC en cualquier momento para abortar."
        )

    return f"Acción '{action}' no reconocida. Usa 'start', 'stop' o 'status'."

# ============================================================
#  FUNCIONES AUXILIARES
# ============================================================

def quick_game_action(parameters: dict, player=None, speak=None) -> str:
    """
    Ejecuta una sola acción de juego al instante sin activar el autopiloto.

    Parámetros:
        action: "atacar" | "saltar" | "mover_adelante" | "inventario" | "recargar" | "habilidad1"
        game  : nombre del juego (opcional, auto-detecta si no se da)
    """
    try:
        import actions.direct_input as direct_input
    except ImportError:
        return "Error: módulo direct_input no disponible."

    action_name = parameters.get("action", "").lower()
    game_name = parameters.get("game", "").lower()

    if not game_name:
        app_info = detect_current_app()
        if not app_info or app_info["profile"].get("type") != "game":
            return "No detecté ningún juego activo. Especifica 'game' manualmente."
        game_name = app_info["name"]
        profile = app_info["profile"]
    elif game_name in GAME_PROFILES:
        profile = GAME_PROFILES[game_name]
    else:
        return f"Juego '{game_name}' no en perfiles. Disponibles: {', '.join(GAME_PROFILES.keys())}"

    controls = profile.get("controls", {})

    ACTION_MAP = {
        "atacar": controls.get("attack", controls.get("shoot", "left_click")),
        "saltar": controls.get("jump", "space"),
        "mover_adelante": controls.get("forward", "w"),
        "mover_atras": controls.get("back", "s"),
        "mover_izquierda": controls.get("left", "a"),
        "mover_derecha": controls.get("right", "d"),
        "inventario": controls.get("inventory", "e"),
        "recargar": controls.get("reload", "r"),
        "habilidad1": controls.get("ability1", "q"),
        "habilidad2": controls.get("ability2", "e"),
        "habilidad3": controls.get("ability3", "r"),
        "ultimate": controls.get("ultimate", "x"),
        "agachar": controls.get("crouch", "ctrl"),
        "sprint": controls.get("sprint", "ctrl"),
        "interactuar": controls.get("interact", "f"),
    }

    key = ACTION_MAP.get(action_name)
    if not key:
        return f"Acción '{action_name}' no reconocida. Disponibles: {', '.join(ACTION_MAP.keys())}"

    try:
        if key in ("left_click", "button1"):
            pyautogui.click(button="left")
        elif key in ("right_click", "button2", "button3"):
            pyautogui.click(button="right")
        else:
            direct_input.press_key(key)
            time.sleep(0.1)
            direct_input.release_key(key)

        msg = f"⚡ [{game_name}] {action_name} → tecla '{key}'"
        if player: player.write_log(msg)
        return msg
    except Exception as e:
        return f"Error ejecutando acción: {e}"

def auto_complete_text(parameters: dict, player=None, speak=None) -> str:
    """
    Completa texto parcial en la app activa (Word, email, formulario, etc.).
    Usa Gemini para generar la continuación y la pega con Ctrl+V.

    Parámetros:
        text    : texto parcial que ya escribiste
        context : contexto adicional (ej. "email formal para cliente")
        paste   : True/False — si True pega directamente, si False solo devuelve el texto
    """
    partial = parameters.get("text", "").strip()
    context = parameters.get("context", "")
    should_paste = parameters.get("paste", True)

    if not partial:
        return "Proporciona el texto parcial con el parámetro 'text'."

    try:
        from google import genai
        from memory.config_manager import load_api_keys

        cfg = load_api_keys()
        api_key = cfg.get("gemini_api_key", "")
        if not api_key:
            return "Falta la API Key de Gemini."

        client = genai.Client(api_key=api_key)

        context_line = f"Contexto: {context}" if context else ""
        prompt = f"""Continúa este texto de forma natural, profesional y coherente.
{context_line}
Texto hasta ahora: "{partial}"

Responde ÚNICAMENTE con la continuación (sin repetir lo que ya está escrito, sin comillas, sin explicaciones):"""

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config={"temperature": 0.4},
        )
        completion = response.text.strip()

        if should_paste:
            try:
                import pyperclip
                pyperclip.copy(completion)
                pyautogui.hotkey("ctrl", "v")
                if player: player.write_log(f"✍️ Autocompletado pegado: {completion[:60]}...")
                return f"✅ Texto pegado en la app activa."
            except Exception as e:
                return f"Texto generado pero no pude pegarlo: {e}\n\nTexto: {completion}"
        else:
            return completion

    except Exception as e:
        return f"Error en auto_complete_text: {e}"

# ============================================================
#  LISTAR JUEGOS/APPS DISPONIBLES
# ============================================================

def list_available_profiles() -> str:
    """Lista todos los perfiles de juegos y apps disponibles"""
    games = []
    productivity = []
    browsers = []
    emulators = []

    for name, profile in GAME_PROFILES.items():
        icon = profile.get("icon", "📱")
        ptype = profile.get("type", "unknown")
        if ptype == "game":
            games.append(f"  {icon} {name}")
        elif ptype in ("productivity", "desktop"):
            productivity.append(f"  {icon} {name}")
        elif ptype == "browser":
            browsers.append(f"  {icon} {name}")
        else:
            emulators.append(f"  {icon} {name}")

    result = "📋 Perfiles disponibles:\n\n"
    if games:
        result += "🎮 JUEGOS:\n" + "\n".join(sorted(games)) + "\n\n"
    if productivity:
        result += "💻 PRODUCTIVIDAD:\n" + "\n".join(sorted(productivity)) + "\n\n"
    if browsers:
        result += "🌐 NAVEGADORES:\n" + "\n".join(sorted(browsers)) + "\n\n"
    if emulators:
        result += "🕹️ EMULADORES:\n" + "\n".join(sorted(emulators)) + "\n"

    return result

# ============================================================
#  TEST
# ============================================================

if __name__ == "__main__":
    print("=== AutoPilot v4.0 Test ===\n")
    print(list_available_profiles())
    
    print("\n--- Detectando app activa ---")
    app = detect_current_app()
    if app:
        print(f"App detectada: {app['name']} {app.get('icon', '')}")
    else:
        print("No se detectó ninguna app conocida.")