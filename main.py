import os
import sys
import time
import json
import asyncio
import base64
import traceback
import queue
import logging
from datetime import datetime
from pathlib import Path
import warnings
import gc

# --- Optimizaciones de RAM y Procesos de Chromium ---
# Limita QWebEngine para usar menos RAM y procesos (ahorra ~150-300MB)
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--renderer-process-limit=1 --js-flags=--max_old_space_size=128 --disable-gpu-memory-buffer-video-frames"
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

import threading
_sleep_timer = None
_sleep_duration = 0
_is_sleeping = False
def is_sleeping():
    return _is_sleeping

import sounddevice as sd
# Token de sesión DRM global para control de integridad
_session_drm_token = None
_verified_license_key = ""

# Load config early to determine GPU acceleration settings
_gpu_enabled = False
try:
    if getattr(sys, "frozen", False):
        _base_dir = Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent))
    else:
        _base_dir = Path(__file__).resolve().parent
    _cfg_path = _base_dir / "config" / "api_keys.json"
    if _cfg_path.exists():
        _cfg = json.loads(_cfg_path.read_text(encoding="utf-8"))
        _gpu_enabled = _cfg.get("gpu_acceleration", False)
except Exception:
    pass

if _gpu_enabled:
    # GPU / High Performance Mode: sustain rendering workload on GPU VRAM, maximize space size
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
        "--ignore-gpu-blocklist "
        "--enable-gpu-rasterization "
        "--enable-zero-copy "
        "--num-raster-threads=4 "
        "--renderer-process-limit=1 "
        "--disable-site-isolation-trials "
        "--js-flags=--max-old-space-size=256"
    )
    # Enable hardware acceleration backends for Qt
    os.environ["QSG_RHI_BACKEND"] = "d3d11" # Force Direct3D 11 for hardware rendering on Windows
    os.environ["QSG_INFO"] = "1"
    print("[NEXUS] GPU Acceleration is ENABLED. Offloading RAM rendering workload to GPU.")
else:
    # Balanced low-RAM mode: Keep GPU hardware compositing enabled so glowing CSS effects and drop-shadows are rendered beautifully, but limit renderer processes and JS space size.
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
        "--enable-low-end-device-mode "
        "--renderer-process-limit=1 "
        "--disable-site-isolation-trials "
        "--js-flags=--max-old-space-size=64 "
        "--disable-gpu-shader-disk-cache "
        "--disable-dev-shm-usage "
        "--disable-extensions "
        "--disable-sync "
        "--mute-audio"
    )
    print("[NEXUS] Using Balanced Low RAM GPU-Composited mode for beautiful fluid rendering.")

import asyncio
from concurrent.futures import ThreadPoolExecutor
from beta_config import is_pro_tool, check_daily_limit, increment_calls, pro_tool_message, daily_limit_message
import re
import threading
import json
import sys
try:
    import pygetwindow as gw
except ImportError:
    gw = None
from PyQt6.QtCore import QMetaObject, Qt

# --- Pygame for MP3 sounds ---
import pygame
try:
    pygame.mixer.init()
except Exception:
    pass

_playing_sounds = []

def play_mp3_sound(sound_name: str):
    """Play an mp3 sound from the assets folder asynchronously."""
    global _playing_sounds
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        # Resolve base_path using _MEIPASS for PyInstaller compatibility
        if getattr(sys, 'frozen', False):
            base_path = os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(sys.executable)), "assets")
        else:
            base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
            
        file_path = os.path.join(base_path, f"{sound_name}.mp3")
        if os.path.exists(file_path):
            if sound_name == "meditacion":
                pygame.mixer.music.load(file_path)
                pygame.mixer.music.play(loops=-1)
            else:
                s = pygame.mixer.Sound(file_path)
                s.set_volume(1.0)
                s.play()
                _playing_sounds.append(s)
                # Cleanup list occasionally to prevent memory leak
                if len(_playing_sounds) > 10:
                    _playing_sounds.pop(0)
            print(f"[NEXUS] Reproduciendo sonido: {sound_name}")
        else:
            print(f"[NEXUS] Archivo de sonido no encontrado: {file_path}")
    except Exception as e:
        print(f"Error playing {sound_name}: {e}")

import traceback
from pathlib import Path

# ── Dedicated thread pool for tool execution — prevents starvation ────────────
_TOOL_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="nexus-tool")

try:
    from zoneinfo import ZoneInfo as _ZoneInfo
    _BA_TZ = _ZoneInfo("America/Lima")
except Exception:
    from datetime import timezone as _tz, timedelta as _td
    _BA_TZ = _tz(_td(hours=-5))


def _load_tz():
    """Load timezone from api_keys.json config."""
    global _BA_TZ
    try:
        cfg = json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
        tz_name = cfg.get("timezone", "")
        if tz_name:
            try:
                _BA_TZ = _ZoneInfo(tz_name)
                print(f"[TZ] Timezone loaded: {tz_name}")
            except Exception as e:
                print(f"[TZ] Failed to load '{tz_name}': {e}")
                # Fallback: try to find a common alias or partial match
                import zoneinfo as _zi
                available = _zi.available_timezones()
                # Try case-insensitive match
                tz_lower = tz_name.lower()
                for known in available:
                    if known.lower() == tz_lower:
                        _BA_TZ = _ZoneInfo(known)
                        print(f"[TZ] Matched '{tz_name}' → '{known}'")
                        break
                else:
                    # Try partial match (e.g., "Buenos_Aires" → "America/Argentina/Buenos_Aires")
                    parts = tz_name.replace("\\", "/").split("/")
                    short = parts[-1].lower() if parts else ""
                    for known in available:
                        if known.lower().endswith("/" + short):
                            _BA_TZ = _ZoneInfo(known)
                            print(f"[TZ] Partial match '{tz_name}' → '{known}'")
                            break
                    else:
                        from datetime import datetime as _dt
                        _BA_TZ = _dt.now().astimezone().tzinfo
                        print(f"[TZ] Falling back to system timezone: {_BA_TZ}")
    except Exception as e:
        print(f"[TZ] Error reading config: {e}")

import numpy as np # descargar numpy xd
import sounddevice as sd
from google import genai
from google.genai import types
from ui import NexusUI

def _patch_settings_ui():
    pass

_patch_settings_ui()

from memory.memory_manager import (
    load_memory, update_memory, format_memory_for_prompt,
)

try:
    from actions.file_processor import file_processor
except ImportError:
    file_processor = None
try:
    from actions.flight_finder     import flight_finder
except ImportError:
    flight_finder = None
try:
    from actions.open_app          import open_app
except ImportError:
    open_app = None
try:
    from actions.macros            import macros
except ImportError:
    macros = None
try:
    from actions.close_app         import close_app
except ImportError:
    close_app = None
try:
    from actions.weather_report    import weather_action
except ImportError:
    weather_action = None
try:
    from actions.send_message      import send_message
except ImportError:
    send_message = None
try:
    from actions.reminder          import reminder
except ImportError:
    reminder = None
try:
    from actions.computer_settings import computer_settings
except ImportError:
    computer_settings = None
try:
    from actions.screen_vision import screen_vision
except ImportError:
    screen_vision = None

try:
    from actions.youtube_downloader import download_youtube
except ImportError:
    download_youtube = None
    
try:
    from actions.download_manager import web_download
except ImportError:
    web_download = None

try:
    from actions.file_converter import convert_file
except ImportError:
    convert_file = None

try:
    from actions.student_mode import (
        activar_modo_estudiante, student_paraphrase, 
        student_verify_apa, student_pdf_to_word, student_quality_report
    )
except ImportError:
    activar_modo_estudiante = None
    student_paraphrase = None
    student_verify_apa = None
    student_pdf_to_word = None
    student_quality_report = None

try:
    from actions.youtube_video     import youtube_video
except ImportError:
    youtube_video = None
try:
    from actions.desktop           import desktop_control
except ImportError:
    desktop_control = None
try:
    from actions.browser_control   import browser_control
except ImportError:
    browser_control = None
try:
    from actions.visual_click import visual_click
except ImportError:
    visual_click = None
try:
    from actions.file_controller   import file_controller
except ImportError:
    file_controller = None

try:
    from actions.code_helper import code_helper
except ImportError:
    code_helper = None

try:
    from actions.dev_agent         import dev_agent
except ImportError:
    dev_agent = None
try:
    from actions.web_search        import web_search as web_search_action
except ImportError:
    web_search_action = None
try:
    from actions.computer_control  import computer_control
except ImportError:
    computer_control = None
try:
    from actions.game_updater      import game_updater
except ImportError:
    game_updater = None
try:
    from actions.google_calendar   import google_calendar
except ImportError:
    google_calendar = None
try:
    from actions.spotify_control   import spotify_control
except ImportError:
    spotify_control = None
try:
    from actions.rgb_control       import rgb_control
except ImportError:
    rgb_control = None
try:
    from actions.scheduler         import scheduler, start_runner
except ImportError:
    scheduler = None; start_runner = None
try:
    from actions.google_drive      import google_drive
except ImportError:
    google_drive = None
try:
    from actions.gmail_control     import gmail_control
except ImportError:
    gmail_control = None
try:
    from actions.google_maps       import google_maps
except ImportError:
    google_maps = None
try:
    from actions.rules_engine      import rules_engine, start_rules_runner, check_phrase_triggers, _run_action as _rules_run_action
except ImportError:
    rules_engine = None; start_rules_runner = None; check_phrase_triggers = None; _rules_run_action = None
try:
    from actions.social_media      import social_media
except ImportError:
    social_media = None
try:
    from actions.whatsapp          import whatsapp
except ImportError:
    whatsapp = None
try:
    from actions.instagram         import instagram
except ImportError:
    instagram = None
try:
    from actions.vault             import vault
except ImportError:
    vault = None
try:
    from actions.delivery_apps     import delivery_apps
except ImportError:
    delivery_apps = None
try:
    from actions.holographic_translator import holographic_translator
except ImportError:
    holographic_translator = None
try:
    from actions.game_companion import game_companion
except ImportError:
    game_companion = None
try:
    from actions.auto_healer import auto_healer, apply_hotpatch
except ImportError:
    auto_healer = None; apply_hotpatch = None
try:
    from actions.visual_memory import visual_memory, start_visual_memory
except ImportError:
    visual_memory = None; start_visual_memory = None
try:
    from actions.universal_app_control import universal_app_control
except ImportError:
    universal_app_control = None
try:
    from actions.ride_apps         import ride_apps
except ImportError:
    ride_apps = None
try:
    from actions.discord_control   import discord_control
except ImportError:
    discord_control = None
try:
    from actions.youtube_control   import youtube_control
except ImportError:
    youtube_control = None
try:
    from actions.blind_reader      import blind_reader
except ImportError:
    blind_reader = None
try:
    from actions.playwright_agent  import playwright_agent
except ImportError:
    playwright_agent = None
try:
    from actions.user_profile      import user_profile, record_action
except ImportError:
    user_profile = None; record_action = None
try:
    from actions.goals             import goals
except ImportError:
    goals = None
try:
    from actions.git_control       import git_control
except ImportError:
    git_control = None
try:
    from actions.codebase          import codebase
except ImportError:
    codebase = None
try:
    from actions.knowledge_base    import knowledge_base
except ImportError:
    knowledge_base = None
try:
    from actions.windows_settings  import windows_settings
except ImportError:
    windows_settings = None
try:
    from actions.document_creator  import document_creator
except ImportError:
    document_creator = None
try:
    from actions.document_manager  import document_manager
except ImportError:
    document_manager = None
try:
    from actions.web_navigation    import web_navigation
except ImportError:
    web_navigation = None
try:
    from actions.image_generation  import image_generation
except ImportError:
    image_generation = None
try:
    from actions.smart_home        import smart_home
except ImportError:
    smart_home = None
try:
    from actions.daily_tools       import meeting_assistant, smart_inbox, finance_reader, personal_shopper, powerpoint_generator, speech_coach
except ImportError:
    meeting_assistant = smart_inbox = finance_reader = personal_shopper = powerpoint_generator = speech_coach = None
try:
    from actions.system_monitor    import system_monitor
except ImportError:
    system_monitor = None
try:
    from actions.tiktok_analyzer   import tiktok_analyzer
except ImportError:
    tiktok_analyzer = None
try:
    from actions.arca_invoice      import arca_invoice
except ImportError:
    arca_invoice = None
try:
    from actions.terminal_agent    import terminal_agent
except ImportError:
    terminal_agent = None
try:
    from actions.native_ui         import native_ui
except ImportError:
    native_ui = None
try:
    from actions.accessibility          import accessibility, eye_tracking, micro_movement, task_simplify, routine_gamify
except ImportError:
    accessibility = None
    eye_tracking = None
    micro_movement = None
    task_simplify = None
    routine_gamify = None
try:
    from actions.screen_reader          import screen_reader
except ImportError:
    screen_reader = None
try:
    from actions.accessibility_overlay  import accessibility_overlay
except ImportError:
    accessibility_overlay = None
try:
    from actions.morning_brief     import morning_brief, already_briefed_today, mark_briefed
except ImportError:
    morning_brief = None; already_briefed_today = None; mark_briefed = None
try:
    from actions.vision_guardian   import vision_guardian, start as _start_vision_guardian
except ImportError:
    vision_guardian = None; _start_vision_guardian = None
try:
    from actions.openrouter_agent  import openrouter_agent
except ImportError:
    openrouter_agent = None



def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent))
    return Path(__file__).resolve().parent

def get_runtime_dir():
    """Carpeta junto al .exe (escribible). En desarrollo es igual a BASE_DIR."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR        = get_base_dir()
RUNTIME_DIR     = get_runtime_dir()
API_CONFIG_PATH = RUNTIME_DIR / "config" / "api_keys.json"
PROMPT_PATH     = BASE_DIR / "core" / "prompt.txt"
LOG_PATH        = RUNTIME_DIR / "nexus.log"

# ── Redirect output to log file (pythonw.exe has no console) ─
try:
    import io as _io
    _log_fh = open(LOG_PATH, "w", encoding="utf-8", buffering=1)

    class _TeeStream:
        def __init__(self, *streams):
            self._streams = [s for s in streams if s is not None]
        def write(self, data):
            for s in self._streams:
                try: s.write(data)
                except Exception: pass
        def flush(self):
            for s in self._streams:
                try: s.flush()
                except Exception: pass
        @property
        def encoding(self): return "utf-8"
        def fileno(self): raise _io.UnsupportedOperation("fileno")

    sys.stdout = _TeeStream(sys.stdout, _log_fh)
    sys.stderr = _TeeStream(sys.stderr, _log_fh)
except Exception:
    pass

# ── Suppress console windows from all child subprocesses ─────────────────────
# Disabled global Popen patch to allow interactive GUI applications (cmd, notepad, etc.) to show on screen.
# Background CLI tasks already use CREATE_NO_WINDOW explicitly in actions/terminal_agent.py.

LIVE_MODEL          = "models/gemini-2.5-flash-native-audio-preview-12-2025"
CHANNELS            = 1
SEND_SAMPLE_RATE    = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE          = 256      # 16ms chunks — mic input (keep small for low latency)
PLAY_CHUNK_SIZE     = 480      # 20ms chunks — playback (smaller = lower latency)

_cached_api_key: str | None = None

def _get_api_key() -> str:
    global _cached_api_key
    if _cached_api_key:
        return _cached_api_key
    with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
        _cached_api_key = json.load(f)["gemini_api_key"]
    return _cached_api_key


NEXUS_VOICES = {
    "Aoede":  ("Femenina", "Cálida y sofisticada — ideal para asistente IA"),
    "Kore":   ("Femenina", "Suave y precisa"),
    "Leda":   ("Femenina", "Natural y fluida"),
    "Zephyr": ("Femenina", "Dinámica y expresiva"),
    "Charon": ("Masculina", "Profunda y seria — voz original de NEXUS"),
    "Puck":   ("Masculina", "Ágil y versátil"),
    "Fenrir": ("Masculina", "Grave y autoritaria"),
    "Orus":   ("Masculina", "Clásica y equilibrada"),
}

def _get_nexus_voice() -> str:
    try:
        cfg = json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
        return cfg.get("nexus_voice", "Aoede")
    except Exception:
        return "Aoede"


_cached_prompt = None

def _load_system_prompt() -> str:
    global _cached_prompt
    if _cached_prompt is not None:
        return _cached_prompt

    try:
        prompt_text = PROMPT_PATH.read_text(encoding="utf-8")
        
        # Load active personality dynamically
        try:
            pers_path = BASE_DIR / "config" / "personalities.json"
            if pers_path.exists():
                pers_data = json.loads(pers_path.read_text(encoding="utf-8"))
                active_key = pers_data.get("active", "actual")
                active_pers = pers_data.get("personalities", {}).get(active_key)
                if active_pers:
                    if active_key != "actual":
                        # CRITICAL SYSTEM OVERRIDE: Prepend at the absolute top of the system prompt
                        override_top = (
                            f"# CRITICAL SYSTEM INSTRUCTION OVERRIDE: ACTIVE PERSONALITY = {active_pers['name'].upper()}\n"
                            f"Ignora cualquier instrucción posterior en este prompt sobre actuar como 'británico seco', 'sarcástico' o usar respuestas secas de NEXUS clásico si contradicen tu personalidad activa.\n"
                            f"Tu personalidad, tono de voz y actitud para esta sesión son: {active_pers['prompt']}\n"
                            f"Asegúrate de que cada una de tus respuestas y comentarios refleje al 100% esta personalidad activa. No uses el humor original seco ni las frases cortas del NEXUS tradicional.\n"
                            f"============================================================\n\n"
                        )
                        prompt_text = override_top + prompt_text
                        
                        # Append confirmation directive at the bottom
                        prompt_text += (
                            f"\n\n## DIRECTIVA DE PERSONALIDAD OBLIGATORIA ({active_pers['name'].upper()})\n"
                            f"REGLA DE ORO: Tienes prohibido actuar como el NEXUS clásico (británico seco/sarcástico). Debes adoptar estrictamente este rol: {active_pers['prompt']}\n"
                            f"Adapta tus comentarios de humor, explicaciones y respuestas a esta personalidad activa en todo momento."
                        )
                    else:
                        prompt_text += f"\n\n## DIRECTIVA DE PERSONALIDAD ({active_pers['name'].upper()})\n{active_pers['prompt']}\nPor favor, adapta tus respuestas, comentarios y estilo estrictamente a esta personalidad."
        except Exception as e:
            print(f"[PERSONALITY] Error loading personality prompt: {e}")

        try:
            cfg = json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
            user_name = cfg.get("user_name", "Señor").strip()
            ai_name = cfg.get("ai_name", "I.L.U.M.").strip()
            if user_name:
                prompt_text += f"\n\n## PERSONALIZACIÓN DEL USUARIO\nEl nombre del usuario es '{user_name}'. Dirígete a él como '{user_name}' (o variantes cortas respetuosas como 'señor {user_name}') de manera leal y natural en cada interacción, a menos que él te pida explícitamente cambiar su nombre."
            if ai_name and ai_name.upper() != "NEXUS":
                prompt_text += f"\n\n## DIRECTIVA DE IDENTIDAD (IMPORTANTE)\nTu nombre ha sido reasignado oficialmente a '{ai_name}'. Eres el ecosistema inteligente {ai_name}, y debes presentarte y referirte a ti mismo exclusivamente como {ai_name}, NO como NEXUS."
        except Exception:
            pass
        return prompt_text
    except Exception:
        ai_name = "I.L.U.M."
        try:
            cfg = json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
            ai_name = cfg.get("ai_name", "I.L.U.M.").strip()
        except Exception:
            pass
            
        return (
            f"You are {ai_name}, an advanced AI assistant. "
            "Be concise, direct, and always use the provided tools to complete tasks. "
            "Never simulate or guess results — always call the appropriate tool."
        )

_CTRL_RE = re.compile(r"<ctrl\d+>", re.IGNORECASE)

def _clean_transcript(text: str) -> str:    
    text = _CTRL_RE.sub("", text)
    text = re.sub(r"[\x00-\x08\x0b-\x1f]", "", text)
    return text  # Retener espacios para correcta concatenación de chunks

TOOL_DECLARATIONS = [
    {
        "name": "auto_pilot",
        "description": "Piloto automático autónomo. Úsalo cuando el usuario te pida que juegues, dibujes, edites o interactúes con la pantalla por él de forma continua. Tomas el control del mouse y evalúas la pantalla en bucle.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "start (iniciar bucle) | stop (detener bucle)"
                },
                "goal": {
                    "type": "STRING",
                    "description": "El objetivo final (ej. 'dibuja una casa', 'juega', 'completa el nivel'). Requerido si action es start."
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "proactive_routine",
        "description": "Inicia rutinas matutinas o diarias. Úsalo cuando el usuario te pida que revises sus tareas matutinas, agenda, etc.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "morning (rutina matutina)"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "inventory_manager",
        "description": "Gestión de bases de datos de inventario para empresas. Permite añadir/quitar productos, consultar stock y calcular el valor total.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "add | remove | delete_product | query | calculate_value"
                },
                "inventory_name": {
                    "type": "STRING",
                    "description": "Nombre de la base de datos de la empresa o inventario."
                },
                "product": {
                    "type": "STRING",
                    "description": "Nombre del producto (opcional para query o calculate_value)."
                },
                "quantity": {
                    "type": "INTEGER",
                    "description": "Cantidad a sumar o restar."
                },
                "price": {
                    "type": "NUMBER",
                    "description": "Precio unitario del producto."
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "game_control",
        "description": "Pausa el juego actual automáticamente (presionando Esc) y devuelve el nombre del juego. Úsalo ÚNICAMENTE cuando el usuario pida explícitamente pausar o suspender el juego. Para ver qué juego está jugando o pedir consejos, usa screen_vision.",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_current_time",
        "description": "Devuelve la fecha y hora actual EXACTA del sistema local. Úsalo siempre que el usuario pregunte la hora o fecha, o para verificar si es momento de ejecutar una acción.",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "camera_bus",
        "description": (
            "Controla el subsistema de pilotaje y navegación gestual por cámara de NEXUS. "
            "Permite activar, desactivar o alternar el control gestual del mouse usando la webcam en segundo plano."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "enable (activar/conectar cámara gestual) | disable (desactivar/apagar cámara gestual) | toggle (alternar estado)"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "nexus_ui_control",
        "description": (
            "Control total sobre la ventana principal y los widgets de la interfaz de NEXUS. "
            "Permite minimizar/restaurar la ventana principal, o abrir, cerrar, alternar la visibilidad de cualquier widget del dashboard.\n"
            "Widgets disponibles: weather (clima), spotify (música), system (sistema), "
            "notes (notas), todo (tareas), maps (mapas), image (imágenes), camera (cámara)."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "minimize (minimizar ventana) | restore (restaurar ventana) | show (mostrar widget) | hide (ocultar widget) | hide_all (ocultar todos los widgets) | toggle (alternar widget)"
                },
                "widget": {
                    "type": "STRING",
                    "description": "Nombre del widget (solo para show/hide/toggle): weather | spotify | system | notes | todo | maps | image | camera"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "open_app",
        "description": (
            "Opens any application on the computer. "
            "Use this whenever the user asks to open, launch, or start any app, "
            "website, or program. Always call this tool — never just say you opened it."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {
                    "type": "STRING",
                    "description": "Exact name of the application (e.g. 'WhatsApp', 'Chrome', 'Spotify')"
                }
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "close_app",
        "description": (
            "Closes any running application on the computer by its name. "
            "Use this whenever the user asks to close, terminate, or stop any app, "
            "program, or process. Always call this tool."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {
                    "type": "STRING",
                    "description": "Name of the application or process to close (e.g. 'Chrome', 'Spotify', 'Discord')"
                }
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "macros",
        "description": (
            "Ejecuta macros de teclado y mouse, simula pulsaciones de teclas complejas o secuencias de automatización directamente en la PC.\n"
            "Úsalo cuando el usuario te pida explícitamente ejecutar un macro, teclear algo directamente, o realizar una secuencia de acciones de teclado/mouse."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "execute_macro (ejecutar un macro por nombre) | delete_macro (eliminar un macro por nombre) | record_macro (iniciar grabación de ratón y teclado) | stop_record (detener grabación actual) | stop_macro (detener macro o bucle en ejecución) | type_text (teclear un texto) | press_key (presionar tecla/atajo) | custom_sequence (secuencia personalizada) | hold_key (mantener tecla) | mouse_macro (clic/mover ratón)"
                },
                "macro_name": {
                    "type": "STRING",
                    "description": "Nombre del macro a ejecutar o grabar. Si es grabar, elige un nombre corto."
                },
                "text": {
                    "type": "STRING",
                    "description": "Texto a teclear directamente (para action='type_text')"
                },
                "key": {
                    "type": "STRING",
                    "description": "Tecla o atajo a presionar, ej: 'ctrl+alt+delete', 'win+d', 'enter' (para action='press_key' o 'hold_key')"
                },
                "sequence": {
                    "type": "STRING",
                    "description": "Secuencia de macro personalizada separada por comas, ej: 'open:notepad.exe, wait:1.0, type:hola mundo, press:enter'"
                },
                "duration": {
                    "type": "NUMBER",
                    "description": "Duración en segundos para hold_key o mouse_macro."
                },
                "mouse_action": {
                    "type": "STRING",
                    "description": "Acción de ratón ('click' o 'move') para action='mouse_macro'."
                },
                "x": {"type": "INTEGER", "description": "Coordenada X del ratón"},
                "y": {"type": "INTEGER", "description": "Coordenada Y del ratón"},
                "button": {"type": "STRING", "description": "Botón del ratón: 'left', 'right', 'middle'"},
                "times": {"type": "INTEGER", "description": "Número de veces a presionar la tecla o repetir la acción (por defecto 1)"},
                "loop": {"type": "BOOLEAN", "description": "Establece a true para ejecutar el macro de manera continua (bucle infinito) hasta que se envíe stop_macro."}
            },
            "required": ["action"]
        }
    },
    {
        "name": "file_converter",
        "description": "Convierte archivos multimedia (audio/video) usando FFmpeg.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "input_path":    {"type": "STRING", "description": "Ruta absoluta del archivo original a convertir."},
                "output_format": {"type": "STRING", "description": "Extensión deseada (ej: mp3, wav, mp4, avi)."}
            },
            "required": ["input_path", "output_format"]
        }
    },
    {
        "name": "web_download",
        "description": "Descarga un archivo desde una URL directamente a la carpeta Downloads.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "url":      {"type": "STRING", "description": "URL directa del archivo a descargar"},
                "filename": {"type": "STRING", "description": "Nombre opcional del archivo (ej: imagen.png). Si está vacío se infiere de la URL."},
            },
            "required": ["url"]
        }
    },
    {
        "name": "web_search",
        "description": "Searches the web for any information.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query":  {"type": "STRING", "description": "Search query"},
                "mode":   {"type": "STRING", "description": "search (default) or compare"},
                "items":  {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Items to compare"},
                "aspect": {"type": "STRING", "description": "price | specs | reviews"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "weather_report",
        "description": "Gives the weather report to user",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "city": {"type": "STRING", "description": "City name"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "whatsapp",
        "description": (
            "Integración completa con WhatsApp. "
            "SIEMPRE usar para CUALQUIER pedido de WhatsApp: enviar mensajes, "
            "enviar imágenes/archivos, leer conversaciones, ver mensajes sin leer, "
            "guardar/listar contactos con su número de teléfono. "
            "Para enviar, primero verificar si el contacto está guardado con su teléfono. "
            "Si no está, pedir el número al usuario o usar add_contact primero."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":    {"type": "STRING",  "description": "send | send_image | read | unread | add_contact | list_contacts | delete_contact | post_story"},
                "receiver":  {"type": "STRING",  "description": "Nombre del contacto o número de teléfono con código de país (ej: 5491155551234)"},
                "message":   {"type": "STRING",  "description": "Texto del mensaje a enviar"},
                "image_path":{"type": "STRING",  "description": "Ruta de la imagen para send_image"},
                "caption":   {"type": "STRING",  "description": "Descripción de la imagen (opcional)"},
                "count":     {"type": "INTEGER", "description": "Cantidad de mensajes a leer (default: 10)"},
                "name":      {"type": "STRING",  "description": "Nombre del contacto para add_contact/delete_contact"},
                "phone":     {"type": "STRING",  "description": "Número de teléfono con código de país (ej: 5491155551234) para add_contact"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "send_message",
        "description": "Sends a text message via Telegram, Discord, Signal or other messaging platform. For WhatsApp, use the 'whatsapp' tool instead.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "receiver":     {"type": "STRING", "description": "Recipient contact name"},
                "message_text": {"type": "STRING", "description": "The message to send"},
                "platform":     {"type": "STRING", "description": "Platform: Telegram, Discord, Signal, Messenger (NOT WhatsApp — use whatsapp tool)"}
            },
            "required": ["receiver", "message_text", "platform"]
        }
    },
    {
        "name": "reminder",
        "description": "Sets a timed reminder using Task Scheduler.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "date":    {"type": "STRING", "description": "Date in YYYY-MM-DD format"},
                "time":    {"type": "STRING", "description": "Time in HH:MM format (24h)"},
                "message": {"type": "STRING", "description": "Reminder message text"}
            },
            "required": ["date", "time", "message"]
        }
    },

    {
        "name": "instagram",
        "description": "Automatización de Instagram para iniciar sesión y subir historias.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "login | post_story"},
                "username": {"type": "STRING", "description": "Usuario de Instagram (si se solicita login)"},
                "password": {"type": "STRING", "description": "Contraseña de Instagram (si se solicita login)"},
                "image_path": {"type": "STRING", "description": "Ruta de la imagen (si action es post_story)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "vault",
        "description": "Bóveda de memoria segura. Permite guardar, buscar, listar o eliminar contraseñas, secretos, recuerdos a largo plazo y datos.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "save | retrieve | list | delete"},
                "key": {"type": "STRING", "description": "Nombre del dato o contraseña (ej. 'clave netflix')"},
                "value": {"type": "STRING", "description": "El valor o contraseña a guardar (solo para 'save')"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "delivery_apps",
        "description": "Busca comida o restaurantes en apps de delivery (Rappi, Uber Eats, PedidosYa).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app": {"type": "STRING", "description": "rappi | uber eats | pedidosya"},
                "query": {"type": "STRING", "description": "Comida o restaurante a buscar"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "ride_apps",
        "description": "Pide viajes en apps de transporte (Uber, DiDi, Cabify).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app": {"type": "STRING", "description": "uber | didi | cabify"},
                "destination": {"type": "STRING", "description": "Dirección o lugar de destino"}
            },
            "required": ["destination"]
        }
    },
    {
        "name": "social_media",
        "description": "Búsqueda de perfiles y videos en TikTok, Instagram, FB, y descarga de videos sin marca de agua.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "search_profile | search_video | download_video"},
                "platform": {"type": "STRING", "description": "tiktok | instagram | facebook"},
                "query": {"type": "STRING", "description": "Usuario o tema de búsqueda"},
                "url": {"type": "STRING", "description": "URL del video para descargar"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "descargar_youtube",
        "description": "Descarga un video o musica de YouTube.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "url": { "type": "STRING", "description": "URL del video. Opcional: si está vacío, NEXUS lo extraerá automáticamente del navegador activo." },
                "opcion": { "type": "STRING", "description": "'1' para Video, '2' para Solo Audio (MP3)." },
                "calidad": { "type": "STRING", "description": "Para video: '1' (144p) a '6' (Maxima calidad)." }
            },
            "required": ["opcion"]
        }
    },
    {
        "name": "holographic_translator",
        "description": "Muestra subtítulos traducidos flotantes en la pantalla.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "start"},
                "text": {"type": "STRING", "description": "Texto inicial del holograma"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "game_companion",
        "description": "Analiza tu partida en vivo y te da un consejo táctico corto por voz.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "analyze"},
                "game_name": {"type": "STRING", "description": "Nombre del juego (ej: LoL, Valorant)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "auto_healer",
        "description": "Reporta un error para la sanación autónoma y auto-parcheo del código.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "report_error"},
                "module_name": {"type": "STRING", "description": "Nombre de la herramienta que falló"},
                "error_trace": {"type": "STRING", "description": "El mensaje de error"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "visual_memory",
        "description": "Busca contexto histórico en la memoria visual de tu PC.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "search"},
                "query": {"type": "STRING", "description": "Qué estás buscando recordar"}
            },
            "required": ["action", "query"]
        }
    },
    {
        "name": "universal_app_control",
        "description": "Abre CUALQUIER aplicación instalada en la computadora (Photoshop, Word, etc).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {"type": "STRING", "description": "Nombre de la aplicación a abrir"}
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "discord_control",
        "description": "Busca un usuario o canal en Discord y le envía un mensaje real.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "send"},
                "receiver": {"type": "STRING", "description": "Nombre del canal o usuario en Discord"},
                "message": {"type": "STRING", "description": "El mensaje a enviar"}
            },
            "required": ["action", "receiver", "message"]
        }
    },
    {
        "name": "youtube_control",
        "description": "Controla YouTube en la web (abrir, buscar, play_video, play_pause, next, mute, fullscreen).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Acción a realizar: open, search, play_video, play_pause, next, mute, fullscreen"},
                "query": {"type": "STRING", "description": "Qué buscar o reproducir si la acción es 'search' o 'play_video'"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "blind_reader",
        "description": "Lee el contenido visual de la pantalla en voz alta para personas ciegas usando OCR.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "read"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "playwright_agent",
        "description": "Navegador autónomo avanzado de nivel empresarial. Úsalo para iniciar sesión, llenar formularios invisibles, descargar archivos o interactuar con el DOM de forma 100% autónoma. Pasa código Python puro usando la API sincrónica de Playwright.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "code": {
                    "type": "STRING", 
                    "description": "Código Python válido usando las variables 'page' y 'browser' de Playwright. Ej: page.goto('url')\npage.fill('#user', 'admin')\nresult_data = 'Hecho'"
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "activar_modo_estudiante",
        "description": (
            "Abre la ventana de herramientas del Modo Estudiante (parafraseo, PDF, APA 7, DOX). "
            "Usa esta herramienta ÚNICAMENTE cuando el usuario pida de forma explícita el 'Modo Estudiante' o herramientas académicas. "
            "NO la llames para 'modo asistente', 'asistente' ni para interactuar de forma normal conmigo."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "student_paraphrase",
        "description": (
            "Parafrasea un texto académico o el contenido de un archivo del sistema para evitar detectores de IA. "
            "Actualiza la pestaña Ghost en el Modo Estudiante de forma interactiva."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "text": {"type": "STRING", "description": "Texto plano largo que deseas parafrasear."},
                "file_path": {"type": "STRING", "description": "Ruta completa opcional de un archivo (.txt, .docx, .pdf) a parafrasear."}
            },
            "required": []
        }
    },
    {
        "name": "student_verify_apa",
        "description": (
            "Revisa y formatea citas o textos académicos con la norma APA 7ma Edición. "
            "Actualiza el panel de Normas APA 7 en el Modo Estudiante de forma interactiva."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "text": {"type": "STRING", "description": "Citas, bibliografía o texto académico a verificar."},
                "file_path": {"type": "STRING", "description": "Ruta completa opcional de un archivo para verificar."}
            },
            "required": []
        }
    },
    {
        "name": "student_pdf_to_word",
        "description": (
            "Convierte de manera asíncrona un archivo PDF del sistema a un documento Word (.docx) y muestra el estado en pantalla."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "pdf_path": {"type": "STRING", "description": "Ruta completa del archivo PDF a convertir."},
                "docx_path": {"type": "STRING", "description": "Ruta completa opcional de destino para guardar el archivo Word (.docx)."}
            },
            "required": ["pdf_path"]
        }
    },
    {
        "name": "student_quality_report",
        "description": (
            "Genera un reporte de calidad académica y rigor estructural muy completo y detallado en formato HTML sobre un documento (.txt, .docx, .pdf) del sistema. "
            "Actualiza el visor de Calidad Académica de forma interactiva."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file_path": {"type": "STRING", "description": "Ruta completa del archivo académico a evaluar."}
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "youtube_video",
        "description": (
            "Controls YouTube. Use for: playing videos, summarizing a video's content, "
            "getting video info, or showing trending videos."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "play | summarize | get_info | trending (default: play)"},
                "query":  {"type": "STRING", "description": "Search query for play action"},
                "save":   {"type": "BOOLEAN", "description": "Save summary to Notepad (summarize only)"},
                "region": {"type": "STRING", "description": "Country code for trending e.g. TR, US"},
                "url":    {"type": "STRING", "description": "Video URL for get_info action"},
            },
            "required": []
        }
    },
    {
        "name": "screen_process",
        "description": (
            "Captures and analyzes the screen or webcam image. "
            "MUST be called when user asks what is on screen, what you see, "
            "analyze my screen, look at camera, etc. "
            "You have NO visual ability without this tool. "
            "After calling this tool, stay SILENT — the vision module speaks directly."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "angle": {"type": "STRING", "description": "'screen' to capture display, 'camera' for webcam. Default: 'screen'"},
                "text":  {"type": "STRING", "description": "The question or instruction about the captured image"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "computer_settings",
        "description": (
            "Controls the computer: volume, brightness, window management, keyboard shortcuts, "
            "typing text on screen, closing apps, fullscreen, dark mode, WiFi, restart, shutdown, "
            "scrolling, tab management, zoom, screenshots, lock screen, refresh/reload page. "
            "Use for ANY single computer control command. NEVER route to agent_task. "
            "IMPORTANT: to type text, MUST use action='type' and value='<text>'. "
            "IMPORTANT: to minimize windows, MUST use action='minimize'."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "The action to perform"},
                "description": {"type": "STRING", "description": "Natural language description of what to do"},
                "value":       {"type": "STRING", "description": "Optional value: volume level, text to type, etc."}
            },
            "required": []
        }
    },
    {
        "name": "browser_control",
        "description": (
            "Controla el navegador activo del usuario (Chrome, Edge, Firefox, etc.) sin abrir uno nuevo. "
            "Usa esta herramienta cuando el usuario te pida interactuar con la web. "
            "Acciones soportadas: navegar a una URL, buscar en Google, abrir o cerrar pestañas, y scrollear."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "Acciones permitidas: go_to | search | search_app | new_tab | close_tab | scroll"},
                "url":         {"type": "STRING", "description": "URL para las acciones go_to o new_tab"},
                "query":       {"type": "STRING", "description": "Término de búsqueda para las acciones search o search_app"},
                "app_name":    {"type": "STRING", "description": "Nombre de la app (Rappi, Uber, TikTok, Instagram, etc) para search_app"},
                "direction":   {"type": "STRING", "description": "Dirección de scroll: up | down (solo para scroll)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "visual_click",
        "description": "Utiliza Visión Espacial para encontrar las coordenadas matemáticas de un elemento en la pantalla y hacer clic en él físicamente.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "element_description": {"type": "STRING", "description": "Descripción clara de lo que quieres cliquear (ej: 'botón de enviar', 'ícono de la papelera')."}
            },
            "required": ["element_description"]
        }
    },
    {
        "name": "sleep_mode",
        "description": "Entra en modo suspensión. Desactiva el micrófono para la IA hasta que el usuario diga su nombre (la palabra de activación) localmente.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "file_controller",
        "description": (
            "Manages files and folders: list, create, delete (to recycle bin), move, copy, rename, read, write, find, disk usage. "
            "Use action=find with name + path to locate files by name in any directory (desktop, downloads, etc.). "
            "After finding a file, pass the returned path to another tool to act on it."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "list | create_file | create_folder | delete (mueve a papelera) | move | copy | rename | read | write | edit | find | largest | disk_usage | organize_desktop | info"},
                "path":        {"type": "STRING", "description": "File/folder path or shortcut: desktop, downloads, documents, home"},
                "destination": {"type": "STRING", "description": "Destination path for move/copy"},
                "new_name":    {"type": "STRING", "description": "New name for rename"},
                "content":     {"type": "STRING", "description": "Content for create_file/write"},
                "name":        {"type": "STRING", "description": "File name to search for"},
                "extension":   {"type": "STRING", "description": "File extension to search (e.g. .pdf)"},
                "count":       {"type": "INTEGER", "description": "Number of results for largest"},
                "old_text":    {"type": "STRING",  "description": "Texto a reemplazar (para edit)"},
                "new_text":    {"type": "STRING",  "description": "Nuevo texto o contenido (para edit)"},
                "mode":        {"type": "STRING",  "description": "replace | append | prepend | overwrite (para edit)"},
                "confirm":     {"type": "BOOLEAN", "description": "true para confirmar eliminaciones"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "desktop_control",
        "description": (
            "Controls the desktop: wallpaper, organize, clean, list, stats. "
            "When the user says to use a file from a directory (e.g. 'el archivo X del escritorio'), "
            "use search_name + search_path to auto-find the file before applying the action."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "wallpaper | wallpaper_url | organize | clean | list | stats | task"},
                "path":        {"type": "STRING", "description": "Image path for wallpaper"},
                "url":         {"type": "STRING", "description": "Image URL for wallpaper_url"},
                "mode":        {"type": "STRING", "description": "by_type or by_date for organize"},
                "task":        {"type": "STRING", "description": "Natural language desktop task"},
                "search_name": {"type": "STRING", "description": "Filename to search for in a directory (auto-finds full path)"},
                "search_path": {"type": "STRING", "description": "Directory to search: desktop, downloads, documents, pictures, home (default: desktop)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "code_helper",
        "description": "Writes, edits, explains, runs, or builds code files.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "write | edit | explain | run | build | auto (default: auto)"},
                "description": {"type": "STRING", "description": "What the code should do or what change to make"},
                "language":    {"type": "STRING", "description": "Programming language (default: python)"},
                "output_path": {"type": "STRING", "description": "Where to save the file"},
                "file_path":   {"type": "STRING", "description": "Path to existing file for edit/explain/run/build"},
                "code":        {"type": "STRING", "description": "Raw code string for explain"},
                "args":        {"type": "STRING", "description": "CLI arguments for run/build"},
                "timeout":     {"type": "INTEGER", "description": "Execution timeout in seconds (default: 30)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "dev_agent",
        "description": "Builds complete multi-file projects from scratch: plans, writes files, installs deps, opens VSCode, runs and fixes errors.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "description":  {"type": "STRING", "description": "What the project should do"},
                "language":     {"type": "STRING", "description": "Programming language (default: python)"},
                "project_name": {"type": "STRING", "description": "Optional project folder name"},
                "timeout":      {"type": "INTEGER", "description": "Run timeout in seconds (default: 30)"},
            },
            "required": ["description"]
        }
    },
    {
        "name": "agent_task",
        "description": (
            "Executes complex multi-step tasks requiring multiple different tools. "
            "Examples: 'research X and save to file', 'find and organize files'. "
            "DO NOT use for single commands. NEVER use for Steam/Epic — use game_updater."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "goal":     {"type": "STRING", "description": "Complete description of what to accomplish"},
                "priority": {"type": "STRING", "description": "low | normal | high (default: normal)"}
            },
            "required": ["goal"]
        }
    },
    {
        "name": "computer_control",
        "description": "Direct computer control: type, click, hotkeys, scroll, move mouse, screenshots, find elements on screen.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "type | smart_type | click | double_click | right_click | hotkey | press | scroll | move | copy | paste | screenshot | wait | clear_field | focus_window | screen_find | screen_click | random_data | user_data"},
                "text":        {"type": "STRING", "description": "Text to type or paste"},
                "x":           {"type": "INTEGER", "description": "X coordinate"},
                "y":           {"type": "INTEGER", "description": "Y coordinate"},
                "keys":        {"type": "STRING", "description": "Key combination e.g. 'ctrl+c'"},
                "key":         {"type": "STRING", "description": "Single key e.g. 'enter'"},
                "direction":   {"type": "STRING", "description": "up | down | left | right"},
                "amount":      {"type": "INTEGER", "description": "Scroll amount (default: 3)"},
                "seconds":     {"type": "NUMBER",  "description": "Seconds to wait"},
                "title":       {"type": "STRING",  "description": "Window title for focus_window"},
                "description": {"type": "STRING",  "description": "Element description for screen_find/screen_click"},
                "type":        {"type": "STRING",  "description": "Data type for random_data"},
                "field":       {"type": "STRING",  "description": "Field for user_data: name|email|city"},
                "clear_first": {"type": "BOOLEAN", "description": "Clear field before typing (default: true)"},
                "path":        {"type": "STRING",  "description": "Save path for screenshot"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "game_updater",
        "description": (
            "THE ONLY tool for ANY Steam or Epic Games request. "
            "Use for: installing, downloading, updating games, listing installed games, "
            "checking download status, scheduling updates. "
            "ALWAYS call directly for any Steam/Epic/game request. "
            "NEVER use agent_task, browser_control, or web_search for Steam/Epic."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":    {"type": "STRING",  "description": "update | install | list | download_status | schedule | cancel_schedule | schedule_status (default: update)"},
                "platform":  {"type": "STRING",  "description": "steam | epic | both (default: both)"},
                "game_name": {"type": "STRING",  "description": "Game name (partial match supported)"},
                "app_id":    {"type": "STRING",  "description": "Steam AppID for install (optional)"},
                "hour":      {"type": "INTEGER", "description": "Hour for scheduled update 0-23 (default: 3)"},
                "minute":    {"type": "INTEGER", "description": "Minute for scheduled update 0-59 (default: 0)"},
                "shutdown_when_done": {"type": "BOOLEAN", "description": "Shut down PC when download finishes"},
            },
            "required": []
        }
    },
    {
        "name": "flight_finder",
        "description": "Searches Google Flights and speaks the best options.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "origin":      {"type": "STRING",  "description": "Departure city or airport code"},
                "destination": {"type": "STRING",  "description": "Arrival city or airport code"},
                "date":        {"type": "STRING",  "description": "Departure date (any format)"},
                "return_date": {"type": "STRING",  "description": "Return date for round trips"},
                "passengers":  {"type": "INTEGER", "description": "Number of passengers (default: 1)"},
                "cabin":       {"type": "STRING",  "description": "economy | premium | business | first"},
                "save":        {"type": "BOOLEAN", "description": "Save results to Notepad"},
            },
            "required": ["origin", "destination", "date"]
        }
    },
    {
        "name": "shutdown_nexus",
        "description": (
            "Shuts down the assistant completely. "
            "Call this when the user expresses intent to end the conversation, "
            "close the assistant, say goodbye, or stop NEXUS. "
            "The user can say this in ANY language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        }
    },
    {
    "name": "file_processor",
    "description": (
        "Processes any file that the user has uploaded or dropped onto the interface. "
        "Use this when the user refers to an uploaded file and wants an action on it. "
        "Supports: images (describe/ocr/resize/compress/convert), "
        "PDFs (summarize/extract_text/to_word), "
        "Word docs & text files (summarize/fix/reformat/translate), "
        "CSV/Excel (analyze/stats/filter/sort/convert), "
        "JSON/XML (validate/format/analyze), "
        "code files (explain/review/fix/optimize/run/document/test), "
        "audio (transcribe/trim/convert/info), "
        "video (trim/extract_audio/extract_frame/compress/transcribe/info), "
        "archives (list/extract), "
        "presentations (summarize/extract_text). "
        "ALWAYS call this tool when a file has been uploaded and the user gives a command about it. "
        "If the user's command is ambiguous, pick the most logical action for that file type."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "file_path": {
                "type": "STRING",
                "description": "Full path to the uploaded file. Leave empty to use the currently uploaded file."
            },
            "action": {
                "type": "STRING",
                "description": (
                    "What to do with the file. Examples by type:\n"
                    "image: describe | ocr | resize | compress | convert | info\n"
                    "pdf: summarize | extract_text | to_word | info\n"
                    "docx/txt: summarize | fix | reformat | translate_hint | word_count | to_bullet\n"
                    "csv/excel: analyze | stats | filter | sort | convert | info\n"
                    "json: validate | format | analyze | to_csv\n"
                    "code: explain | review | fix | optimize | run | document | test\n"
                    "audio: transcribe | trim | convert | info\n"
                    "video: trim | extract_audio | extract_frame | compress | transcribe | info | convert\n"
                    "archive: list | extract\n"
                    "pptx: summarize | extract_text | analyze"
                )
            },
            "instruction": {
                "type": "STRING",
                "description": "Free-form instruction if action doesn't cover it. E.g. 'translate this to Turkish', 'find all email addresses'"
            },
            "format": {
                "type": "STRING",
                "description": "Target format for conversion. E.g. 'mp3', 'pdf', 'csv', 'png'"
            },
            "width":     {"type": "INTEGER", "description": "Target width for image resize"},
            "height":    {"type": "INTEGER", "description": "Target height for image resize"},
            "scale":     {"type": "NUMBER",  "description": "Scale factor for image resize (e.g. 0.5)"},
            "quality":   {"type": "INTEGER", "description": "Quality 1-100 for image/video compress"},
            "start":     {"type": "STRING",  "description": "Start time for trim: seconds or HH:MM:SS"},
            "end":       {"type": "STRING",  "description": "End time for trim: seconds or HH:MM:SS"},
            "timestamp": {"type": "STRING",  "description": "Timestamp for video frame extraction HH:MM:SS"},
            "column":    {"type": "STRING",  "description": "Column name for CSV filter/sort"},
            "value":     {"type": "STRING",  "description": "Filter value for CSV filter"},
            "condition": {"type": "STRING",  "description": "Filter condition: equals|contains|gt|lt"},
            "ascending": {"type": "BOOLEAN", "description": "Sort order for CSV sort (default: true)"},
            "save":      {"type": "BOOLEAN", "description": "Save result to file (default: true)"},
            "destination": {"type": "STRING", "description": "Output folder for archive extract"},
        },
        "required": []
    }
},
    {
        "name": "google_calendar",
        "description": (
            "Manages the user's Google Calendar: create, list, edit, or delete events. "
            "Use for ANY request about calendar events, appointments, reminders with dates, "
            "scheduling meetings, or checking what's coming up. "
            "ALWAYS call this tool for calendar requests — never simulate. "
            "For 'list': shows upcoming events. "
            "For 'create': needs summary and start (end defaults to +1h). "
            "For 'edit'/'delete': needs event_id (get it from 'list' first)."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING",  "description": "list | create | edit | delete"},
                "summary":     {"type": "STRING",  "description": "Event title/name"},
                "start":       {"type": "STRING",  "description": "Start date/time: ISO, YYYY-MM-DD HH:MM, or DD/MM/YYYY HH:MM"},
                "end":         {"type": "STRING",  "description": "End date/time (optional — defaults to start + 1 hour)"},
                "description": {"type": "STRING",  "description": "Event notes or description"},
                "location":    {"type": "STRING",  "description": "Event location"},
                "event_id":    {"type": "STRING",  "description": "Event ID (first 8 chars from list) for edit/delete"},
                "days_ahead":  {"type": "INTEGER", "description": "Days to look ahead for list (default: 7)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "spotify_control",
        "description": (
            "Control total de Spotify: reproducir, pausar, siguiente, anterior, volumen, "
            "buscar canciones/artistas/álbumes/playlists, aleatorio, repetir, ver qué suena, "
            "guardar canciones, ver dispositivos. "
            "SIEMPRE llamar esta herramienta para CUALQUIER pedido relacionado con Spotify o música."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "play | pause | resume | next | previous | volume | shuffle | repeat | current | search | like | devices | playlist"},
                "query":  {"type": "STRING", "description": "Búsqueda para play/search: canción, artista, álbum o playlist"},
                "type":   {"type": "STRING", "description": "track | album | playlist | artist (default: track)"},
                "value":  {"type": "STRING", "description": "Valor para volume (0-100), shuffle (true/false), repeat (off/track/context)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "rgb_control",
        "description": (
            "Controla las luces RGB de periféricos y componentes de la PC (teclado, mouse, GPU, RAM, etc.). "
            "Requiere OpenRGB corriendo con servidor SDK activado. "
            "Usar para: cambiar color, apagar, brillo, efectos, arco iris."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":     {"type": "STRING", "description": "set_color | off | brightness | effect | rainbow | list"},
                "color":      {"type": "STRING", "description": "Color: nombre (rojo, azul, verde, blanco…) o hex #RRGGBB"},
                "brightness": {"type": "INTEGER", "description": "Brillo 0-100 (default: 100)"},
                "device":     {"type": "STRING", "description": "Filtro por nombre de dispositivo (opcional, aplica a todos si se omite)"},
                "effect":     {"type": "STRING", "description": "Nombre del efecto para la acción effect"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "scheduler",
        "description": (
            "Crea, lista, elimina o ejecuta automatizaciones programadas (tareas recurrentes). "
            "Ejemplos: backup diario, notificaciones, scripts automáticos. "
            "Usar para CUALQUIER pedido de 'todos los días a las X', 'cada semana', 'automatizar'."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":           {"type": "STRING",  "description": "list | create | delete | enable | disable | run_now"},
                "name":             {"type": "STRING",  "description": "Nombre descriptivo de la tarea"},
                "frequency":        {"type": "STRING",  "description": "daily | weekly | interval | once"},
                "hour":             {"type": "INTEGER", "description": "Hora de ejecución (0-23)"},
                "minute":           {"type": "INTEGER", "description": "Minuto de ejecución (0-59)"},
                "weekday":          {"type": "STRING",  "description": "Día de la semana para frequency=weekly"},
                "interval_minutes": {"type": "INTEGER", "description": "Intervalo en minutos para frequency=interval"},
                "task_action":      {"type": "STRING",  "description": "backup | file_controller | notify | custom_script | browser_control"},
                "task_parameters":  {"type": "OBJECT",  "description": "Parámetros de la tarea (source, destination para backup, etc.)"},
                "task_id":          {"type": "STRING",  "description": "ID de la tarea (primeros 6 chars) para delete/enable/disable/run_now"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "google_drive",
        "description": (
            "Gestiona Google Drive: listar archivos, buscar, subir, descargar, crear carpetas, eliminar, compartir. "
            "SIEMPRE usar para cualquier pedido sobre Google Drive."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "list | search | upload | download | create_folder | delete | share | info"},
                "folder_id":   {"type": "STRING", "description": "ID de la carpeta (default: root)"},
                "file_id":     {"type": "STRING", "description": "ID del archivo para download/delete/share/info"},
                "path":        {"type": "STRING", "description": "Ruta local para upload"},
                "name":        {"type": "STRING", "description": "Nombre de la nueva carpeta"},
                "query":       {"type": "STRING", "description": "Término de búsqueda"},
                "destination": {"type": "STRING", "description": "Carpeta local de destino para download"},
                "email":       {"type": "STRING", "description": "Email para compartir"},
                "role":        {"type": "STRING", "description": "reader | writer | commenter"},
                "confirm":     {"type": "BOOLEAN", "description": "true para confirmar eliminación"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "gmail_control",
        "description": (
            "Gestiona Gmail: leer bandeja, leer correo, enviar, responder, buscar, archivar, eliminar. "
            "SIEMPRE usar para cualquier pedido sobre correo electrónico o Gmail."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":     {"type": "STRING",  "description": "inbox | read | send | reply | search | archive | delete | mark_read | labels"},
                "count":      {"type": "INTEGER", "description": "Cantidad de correos a listar/buscar (default: 5)"},
                "message_id": {"type": "STRING",  "description": "ID del mensaje para read/reply/archive/delete/mark_read"},
                "to":         {"type": "STRING",  "description": "Destinatario para send"},
                "subject":    {"type": "STRING",  "description": "Asunto para send"},
                "body":       {"type": "STRING",  "description": "Cuerpo del correo para send/reply"},
                "query":      {"type": "STRING",  "description": "Búsqueda Gmail para search (ej: 'from:juan', 'subject:factura')"},
                "confirm":    {"type": "BOOLEAN", "description": "true para confirmar eliminación"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "google_maps",
        "description": (
            "Muestra rutas de navegación y mapas interactivos. "
            "Usar para: cómo llegar a un lugar, cuánto tarda, indicaciones paso a paso, "
            "buscar una dirección en el mapa. Abre mapa NEXUS en Chrome con la ruta marcada. "
            "SIEMPRE llamar para cualquier pedido de navegación, rutas o mapas."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "directions | search | earth"},
                "origin":      {"type": "STRING", "description": "Punto de partida (dirección, ciudad, lugar)"},
                "destination": {"type": "STRING", "description": "Destino (dirección, ciudad, lugar)"},
                "mode":        {"type": "STRING", "description": "car (auto) | walk (caminando) | bike (bicicleta). Default: car"},
                "query":       {"type": "STRING", "description": "Lugar a buscar en el mapa (para action=search)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "rules_engine",
        "description": (
            "Motor de automatizaciones y alertas inteligentes. "
            "USAR SIEMPRE cuando el usuario pida: 'cuando diga X hacé Y', 'cada vez que diga X', "
            "'si digo X abrí/poné/hacé Y', 'quiero que cuando diga X...'. "
            "Soporta: phrase triggers (frase → acción), time triggers (hora → acción), alertas. "
            "Listar, crear, eliminar, habilitar/deshabilitar automaciones. "
            "CONDITION types: phrase (frase del usuario), time (hora del día), file_exists, always. "
            "ACTION types: open_app, spotify_play, browser, smart_home, composite (múltiples), notify, speak, run_script."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":     {"type": "STRING", "description": "list | list_phrases | create | delete | enable | disable | trigger | alert"},
                "name":       {"type": "STRING", "description": "Nombre de la automatización"},
                "rule_id":    {"type": "STRING", "description": "ID de la regla para delete/enable/disable/trigger"},
                "condition":  {
                    "type": "OBJECT",
                    "description": (
                        "Condición. phrase: {type:phrase, trigger:'texto exacto', match:contains|exact|startswith}. "
                        "time: {type:time, hour:8, minute:0, days:[monday,...]}. "
                        "file_exists: {type:file_exists, path:'...'}. always: {type:always}"
                    )
                },
                "action_def": {
                    "type": "OBJECT",
                    "description": (
                        "Acción a ejecutar. "
                        "open_app: {type:open_app, app_name:'Spotify'}. "
                        "spotify_play: {type:spotify_play, query:'Back in Black AC/DC'}. "
                        "browser: {type:browser, url:'https://...'}. "
                        "smart_home: {type:smart_home, device:'living', action:'on'}. "
                        "composite: {type:composite, actions:[{...},{...}]}. "
                        "notify: {type:notify, message:'...'}. speak: {type:speak, message:'...'}. "
                        "run_script: {type:run_script, command:'...'}."
                    )
                },
                "message":    {"type": "STRING", "description": "Mensaje para action=alert"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "user_profile",
        "description": (
            "Perfil dinámico del usuario — hábitos, preferencias, historial de uso. "
            "Ver perfil, configurar preferencias, ver hábitos aprendidos, guardar notas personales. "
            "NEXUS aprende automáticamente los patrones del usuario."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "view | set_preference | set_name | add_note | notes | habits | reset"},
                "key":    {"type": "STRING", "description": "Clave de preferencia (ej: idioma, tema, ciudad)"},
                "value":  {"type": "STRING", "description": "Valor de la preferencia"},
                "name":   {"type": "STRING", "description": "Nombre del usuario"},
                "note":   {"type": "STRING", "description": "Nota personal a guardar"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "goals",
        "description": (
            "Sistema de objetivos persistentes a largo plazo. "
            "Crear metas, trackear progreso, marcar pasos completados. "
            "Usar para: metas personales, proyectos, hábitos, objetivos con deadline. "
            "SIEMPRE usar para pedidos de 'quiero lograr X', 'mi objetivo es', 'meta de'."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING",  "description": "list | create | update_progress | complete | complete_step | add_step | delete | detail"},
                "goal_id":     {"type": "STRING",  "description": "ID del objetivo para update/complete/delete/detail"},
                "title":       {"type": "STRING",  "description": "Título del objetivo"},
                "description": {"type": "STRING",  "description": "Descripción detallada"},
                "deadline":    {"type": "STRING",  "description": "Fecha límite ISO (YYYY-MM-DD)"},
                "progress":    {"type": "INTEGER", "description": "Progreso 0-100"},
                "steps":       {"type": "ARRAY",   "items": {"type": "STRING"}, "description": "Lista de pasos del objetivo"},
                "step":        {"type": "STRING",  "description": "Texto del nuevo paso (add_step)"},
                "step_index":  {"type": "INTEGER", "description": "Índice del paso a completar (0-based)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "git_control",
        "description": (
            "Integración completa con Git: status, log, diff, commit automático, "
            "branches, pull, push, stash, análisis de cambios. "
            "Usar para CUALQUIER pedido relacionado con Git o control de versiones."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING",  "description": "status | log | diff | commit | add | branches | branch_create | checkout | pull | push | stash | analyze"},
                "repo_path":   {"type": "STRING",  "description": "Ruta al repositorio Git"},
                "message":     {"type": "STRING",  "description": "Mensaje del commit"},
                "branch_name": {"type": "STRING",  "description": "Nombre de la rama"},
                "remote":      {"type": "STRING",  "description": "Remote (default: origin)"},
                "n":           {"type": "INTEGER", "description": "Número de commits para log"},
                "file":        {"type": "STRING",  "description": "Archivo específico para diff"},
                "staged":      {"type": "BOOLEAN", "description": "Mostrar diff staged"},
                "add_all":     {"type": "BOOLEAN", "description": "Agregar todos los archivos antes del commit (default: true)"},
                "files":       {"type": "ARRAY",   "items": {"type": "STRING"}, "description": "Archivos para add"},
                "sub":         {"type": "STRING",  "description": "Subcomando para stash: push|pop|list"},
            },
            "required": ["action", "repo_path"]
        }
    },
    {
        "name": "codebase",
        "description": (
            "Indexación y búsqueda inteligente de proyectos de código. "
            "Indexar proyectos, buscar en archivos, encontrar símbolos (funciones/clases), "
            "generar documentación automática, búsqueda avanzada de código. "
            "Usar para: 'buscar en mi proyecto', 'dónde está la función X', 'generar docs', 'indexar mi código'."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":    {"type": "STRING", "description": "index | list | info | search | find_symbol | generate_docs | remove"},
                "path":      {"type": "STRING", "description": "Ruta del proyecto a indexar"},
                "name":      {"type": "STRING", "description": "Nombre del proyecto (default: nombre de carpeta)"},
                "project":   {"type": "STRING", "description": "Nombre del proyecto para info/search/find_symbol"},
                "query":     {"type": "STRING", "description": "Texto a buscar en el código"},
                "symbol":    {"type": "STRING", "description": "Nombre de función/clase a buscar"},
                "file_path": {"type": "STRING", "description": "Ruta del archivo para generate_docs"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "knowledge_base",
        "description": (
            "Segundo cerebro / base de conocimiento personal. "
            "Guardar notas, ideas, snippets de código, referencias, hechos, preguntas. "
            "Buscar en el conocimiento guardado, exportar. "
            "Usar para: 'recordá que...', 'guardá esta idea', 'anotá este código', 'buscar en mis notas'."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":   {"type": "STRING", "description": "add/save/store | search/find | list | get/read/view | update | delete | stats | export"},
                "title":    {"type": "STRING", "description": "Título de la entrada"},
                "content":  {"type": "STRING", "description": "Contenido o texto a guardar"},
                "type":     {"type": "STRING", "description": "note | idea | snippet | reference | fact | task | question"},
                "tags":     {"type": "STRING", "description": "Tags separados por coma (ej: python, nexus, idea)"},
                "query":    {"type": "STRING", "description": "Búsqueda en la base de conocimiento"},
                "entry_id": {"type": "STRING", "description": "ID de la entrada para get/update/delete"},
                "path":     {"type": "STRING", "description": "Ruta para exportar (action=export)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "social_media",
        "description": (
            "Controla redes sociales: Twitter/X, Instagram, TikTok y LinkedIn. "
            "Twitter: publicar tweets, ver timeline, buscar, like, retweet, ver perfil. "
            "Instagram: publicar fotos, subir historias, enviar DMs, ver feed, like, comentar. "
            "TikTok: subir videos, ver perfil/stats, tendencias. "
            "LinkedIn: publicar posts, ver perfil, ver feed, enviar mensajes. "
            "SIEMPRE usar para cualquier pedido de redes sociales. "
            "Para WhatsApp usar la herramienta 'whatsapp'. "
            "Usá action=setup para ver cómo configurar las credenciales."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "platform": {"type": "STRING", "description": "twitter | instagram | tiktok | linkedin | setup"},
                "action":   {"type": "STRING", "description": (
                    "Twitter: tweet, delete_tweet, like, retweet, timeline, search_tweets, my_tweets, profile | "
                    "Instagram: post/upload_photo, story, send_dm, feed, profile, like, comment | "
                    "TikTok: upload/publicar, profile/perfil, trending | "
                    "LinkedIn: post/publicar, profile/perfil, send_message/mensaje, feed"
                )},
                "text":       {"type": "STRING", "description": "Texto del tweet/post/comentario/mensaje"},
                "content":    {"type": "STRING", "description": "Contenido del post (LinkedIn/TikTok)"},
                "tweet_id":   {"type": "STRING", "description": "ID del tweet para like/retweet/delete"},
                "media_id":   {"type": "STRING", "description": "ID del post de Instagram para like/comment"},
                "username":   {"type": "STRING", "description": "Usuario para DM/perfil (Instagram, TikTok, LinkedIn)"},
                "receiver":   {"type": "STRING", "description": "Destinatario del DM de Instagram"},
                "image_path": {"type": "STRING", "description": "Ruta imagen para Instagram/LinkedIn"},
                "video_path": {"type": "STRING", "description": "Ruta del video para TikTok"},
                "caption":    {"type": "STRING", "description": "Descripción/caption de la foto o video"},
                "query":      {"type": "STRING", "description": "Búsqueda de tweets"},
                "count":      {"type": "INTEGER", "description": "Cantidad de resultados (default: 5)"},
            },
            "required": ["platform", "action"]
        }
    },
    {
        "name": "windows_settings",
        "description": (
            "Control TOTAL de configuraciones de Windows. "
            "Usar para CUALQUIER pedido relacionado con configuración del sistema. "
            "Categorías disponibles:\n"
            "• display: brillo, resolución, frecuencia, escala, modo oscuro/noche, HDR, orientación, monitores\n"
            "• audio: volumen, mute, dispositivos de audio/micrófono, mezclador\n"
            "• network: WiFi (listar/conectar/desconectar/on/off), IP, DNS, flush_dns, modo avión, Bluetooth, proxy\n"
            "• power: plan energía, suspender, hibernar, batería, timeouts, inicio rápido\n"
            "• system: info del sistema, nombre PC, fecha/hora, zona horaria, reiniciar, apagar, bloquear, variables de entorno\n"
            "• personalization: fondo de pantalla, tema, transparencia, barra de tareas, protector de pantalla\n"
            "• apps: listar apps, desinstalar, apps de inicio, aplicaciones predeterminadas\n"
            "• security: Windows Defender, firewall, UAC, BitLocker, usuarios del sistema\n"
            "• input: velocidad mouse, doble clic, scroll, botones, velocidad teclado, idioma\n"
            "• storage: discos, espacio, limpieza de archivos temporales, papelera, defrag, chkdsk\n"
            "• services: listar/iniciar/detener/reiniciar servicios de Windows, procesos, kill\n"
            "• privacy: cámara/micrófono privacidad, ubicación, telemetría, notificaciones, portapapeles\n"
            "• registry: leer, escribir, eliminar claves del registro, exportar\n"
            "• accessibility: lupa, narrador, alto contraste, teclado en pantalla\n"
            "• open_settings: abrir panel específico de Configuración de Windows\n"
            "SIEMPRE llamar para cualquier pedido de configuración, ajuste o control del sistema Windows."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": (
                        "La acción a realizar. Ejemplos por categoría:\n"
                        "display: get_brightness | set_brightness | get_resolution | set_resolution | "
                        "set_refresh_rate | get_scaling | set_scaling | night_light_on | night_light_off | "
                        "hdr_on | hdr_off | set_orientation | list_monitors | open\n"
                        "audio: get_volume | set_volume | mute | unmute | toggle_mute | list_devices | "
                        "set_device | get_mic_volume | set_mic_volume | open\n"
                        "network: list_wifi | connect_wifi | disconnect_wifi | wifi_on | wifi_off | "
                        "get_ip | set_dns | flush_dns | airplane_on | airplane_off | "
                        "bluetooth_on | bluetooth_off | set_proxy | disable_proxy | open\n"
                        "power: get_plan | set_plan | list_plans | sleep | hibernate | battery_status | "
                        "set_sleep_timeout | set_screen_timeout | fast_startup_on | fast_startup_off | open\n"
                        "system: info | get_hostname | set_hostname | get_datetime | set_datetime | "
                        "set_timezone | restart | shutdown | lock | get_env | set_env | delete_env | open\n"
                        "personalization: set_wallpaper | get_wallpaper | dark_mode | light_mode | "
                        "transparency_on | transparency_off | taskbar_position | screensaver | open\n"
                        "apps: list | uninstall | startup_apps | set_default | open\n"
                        "security: defender_scan | defender_status | firewall_on | firewall_off | "
                        "firewall_status | uac_level | bitlocker_status | list_users | add_user | open\n"
                        "input: get_mouse_speed | set_mouse_speed | swap_buttons | get_keyboard_speed | "
                        "set_keyboard_speed | list_languages | add_language | open\n"
                        "storage: list_drives | disk_usage | cleanup | empty_trash | clean_temp | "
                        "defrag | chkdsk | open\n"
                        "services: list | start | stop | restart | status | list_processes | kill_process | open\n"
                        "privacy: camera_on | camera_off | mic_on | mic_off | location_on | location_off | "
                        "telemetry_level | notifications_on | notifications_off | clipboard_history_on | "
                        "clipboard_history_off | open\n"
                        "registry: read | write | delete | export\n"
                        "accessibility: magnifier_on | magnifier_off | narrator_on | narrator_off | "
                        "high_contrast_on | high_contrast_off | osk_on | open\n"
                        "open_settings: <nombre del panel, ej: display, sound, wifi, bluetooth, apps>"
                    )
                },
                "value":    {"type": "STRING",  "description": "Valor para la acción (ej: 80 para brillo, 'Dark' para tema, SSID para wifi, etc.)"},
                "value2":   {"type": "STRING",  "description": "Segundo valor cuando se necesitan dos parámetros (ej: contraseña de WiFi, valor de registro)"},
                "name":     {"type": "STRING",  "description": "Nombre del servicio, proceso, usuario, app, o variable de entorno"},
                "hive":     {"type": "STRING",  "description": "Para registry: HKLM | HKCU | HKCR | HKU | HKCC"},
                "key":      {"type": "STRING",  "description": "Para registry: ruta de la clave del registro"},
                "reg_name": {"type": "STRING",  "description": "Para registry: nombre del valor del registro"},
                "reg_type": {"type": "STRING",  "description": "Para registry: REG_SZ | REG_DWORD | REG_BINARY | REG_EXPAND_SZ"},
                "path":     {"type": "STRING",  "description": "Ruta de archivo (para wallpaper, export registry, etc.)"},
                "monitor":  {"type": "INTEGER", "description": "Índice del monitor (0, 1, 2…)"},
                "width":    {"type": "INTEGER", "description": "Ancho de resolución"},
                "height":   {"type": "INTEGER", "description": "Alto de resolución"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "save_memory",
        "description": (
            "Save an important personal fact about the user to long-term memory. "
            "Call this silently whenever the user reveals something worth remembering: "
            "name, age, city, job, preferences, hobbies, relationships, projects, or future plans. "
            "Do NOT call for: weather, reminders, searches, or one-time commands. "
            "Do NOT announce that you are saving — just call it silently. "
            "Values must be in English regardless of the conversation language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": (
                        "identity — name, age, birthday, city, job, language, nationality | "
                        "preferences — favorite food/color/music/film/game/sport, hobbies | "
                        "projects — active projects, goals, things being built | "
                        "relationships — friends, family, partner, colleagues | "
                        "wishes — future plans, things to buy, travel dreams | "
                        "notes — habits, schedule, anything else worth remembering"
                    )
                },
                "key":   {"type": "STRING", "description": "Short snake_case key (e.g. name, favorite_food, sister_name)"},
                "value": {"type": "STRING", "description": "Concise value in English (e.g. Fatih, pizza, older sister)"},
            },
            "required": ["category", "key", "value"]
        }
    },
    {
        "name": "forget_memory",
        "description": (
            "Delete an important personal fact from long-term memory. "
            "Call this ONLY AFTER you have asked the user for confirmation and they agreed. "
            "Be extremely specific and delete only the requested key."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": "Category of the memory (identity, preferences, projects, relationships, wishes, notes)"
                },
                "key": {"type": "STRING", "description": "Short snake_case key to delete"}
            },
            "required": ["category", "key"]
        }
    },
    {
        "name": "image_generation",
        "description": (
            "Genera imágenes con inteligencia artificial a partir de una descripción en texto. "
            "Usa Pollinations.ai (gratis, open-source, sin API key) o Gemini. "
            "SIEMPRE llamar cuando el usuario pide 'generame una imagen', 'crea una foto de', "
            "'dibujame', 'haceme una imagen', 'quiero una foto de', o 'mostrame', etc. "
            "Después de generar, la imagen se muestra automáticamente en el widget de NEXUS."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "prompt":       {"type": "STRING",  "description": "Descripción detallada de la imagen a generar"},
                "count":        {"type": "INTEGER", "description": "Cantidad de imágenes (1-4, default: 1)"},
                "aspect_ratio": {"type": "STRING",  "description": "Relación de aspecto: 1:1 | 4:3 | 3:4 | 16:9 | 9:16 (default: 1:1)"},
                "save_path":    {"type": "STRING",  "description": "Carpeta de guardado (default: ~/Pictures/NEXUS_Generadas)"},
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "smart_home",
        "description": (
            "Controla las luces y dispositivos inteligentes del hogar. "
            "Soporta Tuya/Smart Life, Philips Hue, LIFX y Yeelight. "
            "SIEMPRE llamar para: encender/apagar luces, cambiar color, brillo, temperatura de color, "
            "activar escenas, consultar estado. "
            "Si no hay dispositivos configurados, usar action=setup para ver instrucciones."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING",  "description": "on | off | toggle | color | brightness | temperature | scene | status | list | setup"},
                "device":      {"type": "STRING",  "description": "Nombre o sala del dispositivo (ej: 'sala', 'cuarto', 'lampara principal'). Omitir = todos."},
                "color":       {"type": "STRING",  "description": "Color: nombre (rojo, azul, blanco, cálido…) o hex #RRGGBB"},
                "value":       {"type": "INTEGER", "description": "Valor numérico para brightness (1-100) o temperatura Kelvin (1700-9000)"},
                "brightness":  {"type": "INTEGER", "description": "Brillo 1-100 (alternativa a value)"},
                "scene":       {"type": "STRING",  "description": "Nombre de la escena: relajar, leer, trabajar, noche, fiesta"},
                "protocol":    {"type": "STRING",  "description": "tuya | hue | lifx | yeelight. Omitir = usa el configurado por defecto."},
                "group":       {"type": "STRING",  "description": "Nombre del grupo/sala en Philips Hue"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "meeting_assistant",
        "description": "Se conecta a reuniones para tomar notas y extraer tareas.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "start | summarize"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "smart_inbox",
        "description": "Lee, resume y redacta borradores de correo electrónico.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "summarize | draft"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "finance_reader",
        "description": "Lee tickets, recibos y facturas y los exporta a Excel.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "scan_ticket"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "personal_shopper",
        "description": "Usa navegación oculta para buscar el mejor precio de un producto en tiendas en línea.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "El producto a buscar y comparar"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "powerpoint_generator",
        "description": "Genera una presentación .pptx con títulos y viñetas estructurados.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "topic": {"type": "STRING", "description": "El tema o documento base para la presentación"}
            },
            "required": ["topic"]
        }
    },
    {
        "name": "speech_coach",
        "description": "Analiza la voz del usuario para dar feedback sobre muletillas y velocidad de oratoria.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING"}
            }
        }
    },
    {
        "name": "system_monitor",
        "description": (
            "Monitorea el rendimiento del sistema en tiempo real: CPU, RAM, GPU, discos, "
            "red, temperatura, batería, procesos activos, uptime. "
            "Usar para: '¿cómo está la PC?', 'qué proceso consume más', 'temperatura del CPU', "
            "'cuánta RAM libre tengo', 'matar proceso X', 'resumen de rendimiento'."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":   {"type": "STRING",  "description": "cpu | ram | disk | network | gpu | temperature | battery | uptime | processes | kill | report"},
                "sort_by":  {"type": "STRING",  "description": "Para processes: cpu (default) | ram"},
                "count":    {"type": "INTEGER", "description": "Para processes: cantidad a mostrar (default: 10)"},
                "name":     {"type": "STRING",  "description": "Para kill: nombre o PID del proceso"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "document_creator",
        "description": (
            "Creates Word documents (.docx) or Excel spreadsheets (.xlsx) locally, "
            "OR Google Docs / Google Sheets in the cloud. "
            "Use when the user asks to create a document, report, letter, table, spreadsheet, "
            "budget, list, or any file with structured content. "
            "For documents: provide title and content (use ## for headings, - for bullet lists). "
            "For spreadsheets: provide title and sheets with headers and rows. "
            "Always call this tool — never just say you created it."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": (
                        "word — create a local .docx Word file | "
                        "excel — create a local .xlsx Excel file | "
                        "google_doc — create a Google Doc in the cloud | "
                        "google_sheet — create a Google Sheet in the cloud"
                    )
                },
                "title": {
                    "type": "STRING",
                    "description": "Title or filename of the document/spreadsheet"
                },
                "content": {
                    "type": "STRING",
                    "description": (
                        "For word / google_doc: full text content. "
                        "Use ## Section for main headings, # SubSection for sub-headings, "
                        "- item for bullet points, blank line between paragraphs."
                    )
                },
                "sheets": {
                    "type": "ARRAY",
                    "description": (
                        "For excel / google_sheet: list of sheet objects. "
                        "Each object has: name (string), headers (array of strings), "
                        "rows (array of arrays with cell values)."
                    ),
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "name":    {"type": "STRING", "description": "Sheet tab name"},
                            "headers": {"type": "ARRAY",  "items": {"type": "STRING"}, "description": "Column headers"},
                            "rows":    {"type": "ARRAY",  "items": {"type": "ARRAY", "items": {"type": "STRING"}}, "description": "Data rows"}
                        }
                    }
                },
                "save_path": {
                    "type": "STRING",
                    "description": "Optional: full file path to save locally (e.g. C:/Users/User/Desktop/report.docx). Defaults to ~/Documents/"
                }
            },
            "required": ["action", "title"]
        }
    },
    {
        "name": "tiktok_analyzer",
        "description": (
            "Analiza un perfil público de TikTok dado su URL. "
            "Extrae el nombre, bio, seguidores, y para cada video reciente: "
            "vistas, likes, comentarios y guardados. "
            "Siempre usar cuando el usuario pida analizar un perfil de TikTok "
            "o consultar estadísticas de videos de TikTok."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "profile_url": {"type": "STRING", "description": "URL completa del perfil de TikTok (ej: https://www.tiktok.com/@usuario)"},
                "max_videos":  {"type": "INTEGER", "description": "Cantidad máxima de videos a analizar (default: 8)"},
            },
            "required": ["profile_url"]
        }
    },
    {
        "name": "arca_invoice",
        "description": (
            "Genera comprobantes digitales electrónicos válidos ante ARCA (ex AFIP). "
            "Para Argentina. Soporta Factura A, B, C, Nota de Crédito, Nota de Débito. "
            "Puede operar offline (comprobante local) o conectarse con ARCA si hay certificado. "
            "SIEMPRE usar cuando el usuario pida: 'generame una factura', 'haceme un comprobante', "
            "'necesito una factura A/B/C', 'emití una nota de crédito', o similar. "
            "Usar action='listar' para mostrar los tipos disponibles."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":         {"type": "STRING", "description": "generar | listar | historial"},
                "tipo":           {"type": "INTEGER", "description": "1=Factura A, 5=Factura C (default), 6=Factura B, 3=NC A, 8=NC B, etc. Usá action=listar para ver todos."},
                "razon_social":   {"type": "STRING", "description": "Razón social del receptor (obligatorio para Factura A/B)"},
                "cuit_receptor":  {"type": "STRING", "description": "CUIT del receptor (obligatorio para Factura A/B)"},
                "domicilio":      {"type": "STRING", "description": "Domicilio del receptor (opcional)"},
                "detalle":        {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"descripcion": {"type": "STRING"}, "precio": {"type": "NUMBER"}, "cantidad": {"type": "INTEGER"}}}, "description": "Lista de productos/servicios: [{'descripcion':'...', 'precio':0.0, 'cantidad':1}]"},
                "importe_neto":   {"type": "NUMBER", "description": "Importe neto gravado (se calcula del detalle si no se especifica)"},
                "importe_iva":    {"type": "NUMBER", "description": "Importe de IVA (se calcula al 21% si no se especifica)"},
                "iva_pct":        {"type": "NUMBER", "description": "Porcentaje de IVA (default: 21.0). 0 para exento."},
                "fecha":          {"type": "STRING", "description": "Fecha del comprobante YYYY-MM-DD (default: hoy)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "accessibility",
        "description": (
            "Modulo de accesibilidad universal. "
            "Incluye: task_simplify (descomponer tareas complejas en pasos simples), "
            "emotional (regulacion emocional y analisis de tono de voz), "
            "routine (rutinas diarias gamificadas con racha y progreso), "
            "eye_tracking (control por seguimiento ocular con webcam), "
            "micro_movement (navegacion por movimientos de cabeza), "
            "speech_config (ajustar tolerancia del reconocimiento de voz). "
            "Usar cuando el usuario pida: 'simplificame esto', 'ayudame con mi rutina', "
            "'necesito organizarme', 'activar seguimiento ocular', 'ajusta la tolerancia de voz', "
            "'ejercicio de respiracion', 'complete mi tarea', 'agregar rutina'. "
            "SIEMPRE ofrecer alternativas multimodales."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": (
                        "task_simplify — descomponer texto en pasos simples | "
                        "emotional — intervencion emocional | "
                        "routine — gestion de rutinas gamificadas | "
                        "eye_tracking — control ocular | "
                        "micro_movement — micromovimientos | "
                        "speech_config — tolerancia de voz | "
                        "feedback — feedback visual/haptico | "
                        "config — ver o cambiar configuracion"
                    )
                },
                "text":     {"type": "STRING", "description": "Texto a simplificar (para task_simplify)"},
                "format":   {"type": "STRING", "description": "Formato: steps (default) | summary | explain"},
                "name":     {"type": "STRING", "description": "Nombre de rutina (para routine add/complete)"},
                "setting":  {"type": "STRING", "description": "Clave de configuracion a ver o cambiar"},
                "value":    {"type": "STRING", "description": "Valor para la configuracion"},
                "level":    {"type": "NUMBER", "description": "Nivel de tolerancia (0.1-1.0) o sensibilidad"},
                "stress_level": {"type": "NUMBER", "description": "Nivel de estres estimado (0.0-1.0)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "screen_vision",
        "description": (
            "NEXUS puede VER la pantalla del usuario. Captura lo que está en el monitor "
            "y usa IA (Gemini Vision) para describirlo, responder preguntas, leer texto, "
            "o dar ayuda contextual basada en lo que se está mostrando.\n"
            "SIEMPRE usar cuando el usuario diga: '¿qué estoy viendo?', '¿qué hay en mi pantalla?', "
            "'¿qué dice ahí?', 'ayúdame con esto' (señalando la pantalla), 'leé lo que hay en pantalla', "
            "'¿podés ver mi pantalla?', 'describí lo que tengo abierto', etc."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "describe=describir qué hay en pantalla | question=responder pregunta sobre la pantalla | help=dar ayuda contextual | read=leer todo el texto visible"
                },
                "question": {
                    "type": "STRING",
                    "description": "Pregunta o tarea específica sobre lo que se ve en pantalla (para action=question/help)"
                },
                "monitor": {
                    "type": "INTEGER",
                    "description": "0=toda la pantalla (default), 1=monitor principal, 2=segundo monitor"
                },
            },
            "required": ["action"]
        }
    },

    {
        "name": "morning_brief",
        "description": (
            "Genera el informe matutino inteligente de NEXUS. "
            "Incluye saludo personalizado, hora, fecha, clima actual, objetivos activos y consejo del día. "
            "Usar cuando el usuario pida: 'informe del día', 'brief matutino', 'qué hay hoy', "
            "'resumen del día', 'buenos días NEXUS', o al iniciar el día."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "force": {
                    "type": "boolean",
                    "description": "Si True, genera el informe aunque ya se haya dado hoy."
                }
            },
            "required": []
        }
    },
    {
        "name": "vision_guardian",
        "description": (
            "Controla el Guardian de Visión Ambiental de NEXUS — monitoreo proactivo de pantalla. "
            "Analiza la pantalla periódicamente con IA y ofrece ayuda contextual cuando detecta algo relevante. "
            "Usar cuando el usuario diga: 'activa el guardian', 'desactiva el guardian', "
            "'vigila mi pantalla', 'deja de vigilar', 'analiza mi pantalla ahora', "
            "'estado del guardian', 'cambia el intervalo'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["status", "enable", "disable", "check_now", "set_interval"],
                    "description": "Acción: status | enable | disable | check_now | set_interval"
                },
                "seconds": {
                    "type": "integer",
                    "description": "Para set_interval: segundos entre análisis (30-600)"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "accessibility_overlay",
        "description": (
            "Muestra, oculta o alterna la barra flotante de accesibilidad NEXUS sobre el escritorio. "
            "USAR cuando el usuario diga: 'mostrar barra de accesibilidad', 'abrir panel de accesibilidad', "
            "'activar barra para ciegos', 'cerrar barra', 'ocultar barra de accesibilidad', "
            "'alternar barra', 'barra de accesibilidad'."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "show — mostrar | hide — cerrar | toggle — alternar | status — estado actual"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "openrouter_agent",
        "description": (
            "Delega una tarea intelectualmente compleja, de análisis o redacción larga a OpenRouter "
            "(un motor de texto alternativo). "
            "Usar cuando el usuario pida: 'usa openrouter para esto', 'consulta a claude', 'usa otro modelo', "
            "'analiza este código largo', 'redacta un ensayo', o cuando percibas que la tarea es puramente de texto avanzado."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "El prompt o instrucción completa para el agente de OpenRouter"
                },
                "model": {
                    "type": "STRING",
                    "description": "Opcional. Modelo a usar, por defecto google/gemini-2.5-flash"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "terminal_agent",
        "description": (
            "Ejecuta CUALQUIER comando en la terminal de Windows (PowerShell o CMD). "
            "USAR LIBREMENTE como recurso general para CUALQUIER tarea del sistema operativo: "
            "instalar/desinstalar programas (winget, choco, pip), consultar información del sistema, "
            "ejecutar scripts, manejar archivos y carpetas, configurar redes, descargar archivos, "
            "compilar código, matar procesos, gestionar servicios, y CUALQUIER otra operación. "
            "Si no sabés cómo hacer algo con las herramientas existentes, SIEMPRE intentá resolverlo "
            "con un comando de terminal antes de decir que no podés. "
            "Es tu recurso de último recurso universal."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "command": {
                    "type": "STRING",
                    "description": "El comando exacto a ejecutar"
                },
                "shell": {
                    "type": "STRING",
                    "description": "Shell a usar: powershell (default) o cmd"
                },
                "timeout": {
                    "type": "INTEGER",
                    "description": "Timeout en segundos (default: 120, max: 600)"
                },
                "working_directory": {
                    "type": "STRING",
                    "description": "Directorio de trabajo para el comando (opcional)"
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "native_ui",
        "description": (
            "Automatización de Interfaz Nativa de Windows (UI Automation). "
            "USAR para listar, enfocar, escribir o hacer clic en ventanas de forma 100% precisa, saltándose la visión. "
            "Esto EVITA errores de cuota (Error 429) y permite simulación exacta de teclado/mouse."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "Acción a realizar: list_windows | focus_window | type_in_window | click_center"
                },
                "window_title": {
                    "type": "STRING",
                    "description": "El nombre (o parte del nombre) de la ventana destino. (Ej: 'WhatsApp', 'Chrome')"
                },
                "text": {
                    "type": "STRING",
                    "description": "El texto a escribir (solo si action es type_in_window)"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "tool_creator",
        "description": (
            "Permite a NEXUS programar e instalar sus propias herramientas. "
            "ÚSALO SIEMPRE que el usuario te pida que aprendas a hacer algo nuevo, o si necesitas una funcionalidad que no tienes preinstalada. "
            "Escribirás el código Python y se instalará automáticamente."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "tool_name": {
                    "type": "STRING",
                    "description": "Nombre de la herramienta en snake_case"
                },
                "description": {
                    "type": "STRING",
                    "description": "Descripción clara de la herramienta y para qué sirve"
                },
                "parameters_schema": {
                    "type": "STRING",
                    "description": "El bloque de 'properties' del JSON schema en formato string válido. Ej: '{\"accion\": {\"type\": \"STRING\"}}'"
                },
                "python_code": {
                    "type": "STRING",
                    "description": "Código Python con la función def <tool_name>(parameters: dict, player=None, speak=None) -> str:"
                }
            },
            "required": ["tool_name", "description", "parameters_schema", "python_code"]
        }
    },
    {
        "name": "proactive_automation",
        "description": (
            "Gestiona reglas complejas basadas en el uso y hábitos del sistema operativo "
            "para optimizar el rendimiento y automatizar recordatorios proactivos."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "add_rule (añadir regla) | list_rules (listar) | delete_rule (eliminar) | trigger_check (evaluar reglas activas)"
                },
                "rule_name": {
                    "type": "STRING",
                    "description": "Nombre identificativo de la regla de automatización"
                },
                "trigger": {
                    "type": "STRING",
                    "description": "Disparador: cpu_high | ram_high | time_of_day | app_open"
                },
                "trigger_value": {
                    "type": "STRING",
                    "description": "Valor del disparador (ej. '85' para 85% cpu, '22:00' para hora, 'chrome.exe' para app)"
                },
                "action_to_take": {
                    "type": "STRING",
                    "description": "Acción a ejecutar (ej. 'optimize_ram', 'mute_system', 'run_script')"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "unified_communications",
        "description": (
            "Gestión unificada de comunicaciones. Permite leer, enviar y organizar mensajes "
            "y notificaciones en WhatsApp, Telegram, Discord y Gmail desde esta única interfaz."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "platform": {
                    "type": "STRING",
                    "description": "Plataforma de comunicación: whatsapp | telegram | discord | gmail"
                },
                "action": {
                    "type": "STRING",
                    "description": "send_message (enviar mensaje)"
                },
                "recipient": {
                    "type": "STRING",
                    "description": "Destinatario: número telefónico para WhatsApp, ID de chat o token para Telegram, Webhook URL para Discord, o email para Gmail"
                },
                "message": {
                    "type": "STRING",
                    "description": "Contenido del mensaje a enviar"
                },
                "subject": {
                    "type": "STRING",
                    "description": "Asunto del correo (solo aplica para Gmail)"
                },
                "token": {
                    "type": "STRING",
                    "description": "Token de Bot opcional para Telegram"
                }
            },
            "required": ["platform", "action", "recipient", "message"]
        }
    },
    {
        "name": "smart_file_organizer",
        "description": (
            "Análisis y organización inteligente de archivos. Clasifica por categorías, "
            "detecta duplicados reales mediante hash MD5 y analiza espacio disponible en disco."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "organize (clasificar por tipo) | find_duplicates (buscar duplicados MD5) | disk_space (analizar espacio)"
                },
                "directory": {
                    "type": "STRING",
                    "description": "Ruta absoluta del directorio a analizar. Por defecto usa la carpeta Descargas."
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "contextual_control",
        "description": (
            "Control contextual de entorno. Ajusta dinámicamente volumen, brillo, plan de energía "
            "y estado de Focus Assist (No Molestar) basándose en la ventana activa o comandos manuales."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "adjust_context (auto-ajustar por ventana activa) | set_volume (fijar volumen) | set_brightness (fijar brillo) | set_power_plan (energía) | set_dnd (no molestar)"
                },
                "volume": {
                    "type": "INTEGER",
                    "description": "Nivel de volumen maestro (0-100)"
                },
                "brightness": {
                    "type": "INTEGER",
                    "description": "Nivel de brillo de la pantalla (0-100)"
                },
                "power_plan": {
                    "type": "STRING",
                    "description": "Plan de energía de Windows: balanced | high_performance | power_saver"
                },
                "state": {
                    "type": "STRING",
                    "description": "Estado de No Molestar (Focus Assist): on | off | alarms"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "auto_programmer",
        "description": (
            "Suite de desarrollo y auto-programación autónoma avanzada. Permite a NEXUS escribir "
            "código Python para nuevas herramientas, validar sintaxis con py_compile, correr tests sintácticos "
            "en un sandbox con traceback detallado, corregir errores e inyectar plugins en caliente."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "create_tool (crear/actualizar) | fix_tool (corregir error) | test_tool (probar en sandbox) | list_tools (listar creadas)"
                },
                "tool_name": {
                    "type": "STRING",
                    "description": "Nombre de la herramienta en snake_case"
                },
                "description": {
                    "type": "STRING",
                    "description": "Descripción clara de la herramienta y su uso"
                },
                "parameters_schema": {
                    "type": "STRING",
                    "description": "JSON de propiedades de parámetros. Ej: '{\"param\": {\"type\": \"STRING\"}}'"
                },
                "python_code": {
                    "type": "STRING",
                    "description": "Código Python con la función def <tool_name>(parameters: dict, player=None) -> str:"
                },
                "test_parameters": {
                    "type": "OBJECT",
                    "description": "Parámetros mock de prueba para evaluar la ejecución de la función en el sandbox"
                }
            },
            "required": ["action", "tool_name"]
        }
    },
    {
        "name": "self_edit",
        "description": (
            "Auto-edición de código: NEXUS puede leer, modificar, crear y gestionar sus propios archivos de código fuente. "
            "Crea backups automáticos antes de cada cambio. "
            "USAR cuando el usuario pida: 'editá tu código', 'cambiá tu prompt', 'agregá esta función', "
            "'modificá tu comportamiento', 'mejorate', 'aprendé a hacer X editando tu código', "
            "o cuando NEXUS necesite auto-mejorarse, corregir bugs propios o agregar capacidades. "
            "Puede editar: main.py, core/prompt.txt, actions/*.py, config/*, o cualquier archivo del proyecto."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": (
                        "read_file — leer un archivo del proyecto | "
                        "edit_file — buscar y reemplazar texto en un archivo (requiere target y replacement) | "
                        "append_file — agregar contenido al final de un archivo | "
                        "create_file — crear o sobrescribir un archivo | "
                        "list_files — listar archivos de un directorio | "
                        "list_backups — ver backups disponibles | "
                        "restore_backup — restaurar un backup anterior"
                    )
                },
                "file": {
                    "type": "STRING",
                    "description": "Ruta del archivo relativa al proyecto (ej: 'main.py', 'actions/terminal_agent.py', 'core/prompt.txt')"
                },
                "target": {
                    "type": "STRING",
                    "description": "Para edit_file: el texto EXACTO a buscar (incluyendo espacios e indentación)"
                },
                "replacement": {
                    "type": "STRING",
                    "description": "Para edit_file: el texto que reemplazará al target"
                },
                "content": {
                    "type": "STRING",
                    "description": "Para append_file/create_file: el contenido a escribir"
                },
                "directory": {
                    "type": "STRING",
                    "description": "Para list_files: directorio a listar (default: raíz del proyecto)"
                },
                "backup_name": {
                    "type": "STRING",
                    "description": "Para restore_backup: nombre del archivo .bak a restaurar"
                }
            },
            "required": ["action"]
        }
    },
]

# Cargar herramientas dinámicas creadas por tool_creator
try:
    _custom_tools_path = BASE_DIR / "actions" / "custom_tools.json"
    if _custom_tools_path.exists():
        _custom_tools = json.loads(_custom_tools_path.read_text(encoding="utf-8"))
        if isinstance(_custom_tools, list):
            for _t in _custom_tools:
                if _t.get("name") not in [td["name"] for td in TOOL_DECLARATIONS]:
                    TOOL_DECLARATIONS.append(_t)
except Exception as _e:
    pass

class NexusLive:

    def __init__(self, ui: NexusUI):
        # ── CONTROL DE INTEGRIDAD DRM EN CALIENTE ───────────────────────────
        from hashlib import sha256
        import drm_manager
        import sys
        global _session_drm_token
        
        _main_mod = sys.modules.get("main") or sys.modules.get("__main__")
        _key_to_check = getattr(_main_mod, "_verified_license_key", "")
        if not _key_to_check:
            _lic_file = Path(__file__).resolve().parent / "config" / "license.json"
            if _lic_file.exists():
                try:
                    _key_to_check = json.loads(_lic_file.read_text(encoding="utf-8")).get("license_key", "")
                except:
                    pass
        
        expected_token = sha256(f"{_key_to_check}:{drm_manager.get_hwid()}:NEXUS_AI_SECURE_SALT_2026".encode()).hexdigest() if _key_to_check else ""
        if not expected_token or _session_drm_token != expected_token:
            print("[DRM Security] Violación de integridad del inicio de sesión. Bloqueado.")
            os._exit(0)
        # ────────────────────────────────────────────────────────────────────

        self.ui             = ui
        self.session        = None
        self.is_sleeping    = False
        # Cargar sensibilidad del micrófono (puerta de ruido) de la configuración
        cfg_keys = {}
        if API_CONFIG_PATH.exists():
            try:
                cfg_keys = json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass
        self.noise_gate_threshold = float(cfg_keys.get("mic_sensitivity", 0.003))
        self.last_speech_time     = 0.0
        self.update_wake_words(cfg_keys)

        # ── Fish Audio (clonación de voz en la nube) — opcional ─────────────
        self._fish_audio_enabled = cfg_keys.get("fish_audio_enabled", False)
        self._fish_api_key       = cfg_keys.get("fish_api_key", "")
        self._fish_voice_id      = cfg_keys.get("fish_voice_id", "")
        if self._fish_audio_enabled and self._fish_api_key and self._fish_voice_id:
            print(f"[NEXUS] 🐟 Fish Audio habilitado (Voice ID: {self._fish_voice_id[:8]}...)")
        # ────────────────────────────────────────────────────────────────────

        # ── Clonación de Voz Local (XTTS-v2) — opcional ──────────────────────
        self._local_tts_enabled = cfg_keys.get("local_tts_enabled", False)
        self._local_tts = None
        if self._local_tts_enabled:
            print("[NEXUS] 🎙️ Clonación de Voz Local (XTTS-v2) habilitada. Inicializando motor...")
            try:
                from tts_engine import get_engine
                self._local_tts = get_engine()
            except Exception as e:
                print(f"[NEXUS] Error cargando tts_engine: {e}")
        # ────────────────────────────────────────────────────────────────────

        self.vosk_recognizer = None
        self.vosk_interrupt_recognizer = None  # Segundo reconocedor Vosk para validar interrupciones por voz real
        try:
            import vosk
            vosk.SetLogLevel(-1)
            vosk_path = BASE_DIR / "config" / "vosk_model"
            if not vosk_path.exists():
                vosk_path = Path("config/vosk_model")
            if vosk_path.exists():
                model = vosk.Model(str(vosk_path))
                self.vosk_recognizer = vosk.KaldiRecognizer(model, 16000)
                
                spk_path = BASE_DIR / "config" / "vosk-model-spk-0.4"
                if not spk_path.exists():
                    spk_path = Path("config/vosk-model-spk-0.4")
                    
                if spk_path.exists():
                    spk_model = vosk.SpkModel(str(spk_path))
                    self.vosk_interrupt_recognizer = vosk.KaldiRecognizer(model, 16000, spk_model)
                    print("[NEXUS] Modelo Vosk + Speaker ID biométrico cargados.")
                else:
                    self.vosk_interrupt_recognizer = vosk.KaldiRecognizer(model, 16000)
                    print("[NEXUS] Modelo Vosk cargado (sin biometría).")
            else:
                print(f"[NEXUS] No se encontró el modelo Vosk en {vosk_path}")
        except Exception as e:
            print(f"[NEXUS] No se pudo cargar Vosk: {e}")
        self.audio_in_queue = None
        # Iniciar scheduler y motor de reglas en background al arrancar NEXUS
        start_runner(player=ui, speak=None)
        start_rules_runner(player=ui, speak=None)
        self._load_speaker_profile()
        self.registering_voice = False
        self.out_queue      = None
        self._loop          = None
        self._is_speaking   = False
        self._speaking_lock = threading.Lock()
        
        self.last_activity = time.time()
        self._meditation_playing = False
        threading.Thread(target=self._meditation_loop, daemon=True).start()
        threading.Thread(target=self._antivirus_watcher_loop, daemon=True).start()
        self._tts_speak_lock: asyncio.Lock | None = None
        self._fish_speak_lock: asyncio.Lock | None = None
        self.active_tts_tasks_count = 0
        self._stop_requested = threading.Event()
        self._audio_out_stream = None
        self.ui.on_text_command = self._on_text_command
        self.ui.on_stop_command = self._on_stop_pressed
        self.ui.on_config_saved = self._apply_config
        self._turn_done_event: asyncio.Event | None = None
        self._api_1011_tool: str | None = None   # tracks tool name when 1011 hits
        self._reconnect_event: asyncio.Event | None = None
        self._first_connect = True  # flag for auto morning brief + guardian start

    def _inject_text(self, text: str):
        """Thread-safe injection of a text message into the current live session."""
        if self._loop and self.session and not self._is_speaking:
            self._stop_requested.clear()
            asyncio.run_coroutine_threadsafe(
                self.session.send_client_content(
                    turns={"parts": [{"text": text}]},
                    turn_complete=True
                ),
                self._loop
            )

    def _apply_config(self, cfg: dict):
        """Called from UI thread when user saves settings. Triggers session reconnect."""
        global _cached_api_key
        _cached_api_key = None  # Invalidate cached key so new one is loaded on reconnect
        
        # Actualizar dinámicamente la puerta de ruido sin reiniciar
        self.noise_gate_threshold = float(cfg.get("mic_sensitivity", 0.003))
        
        # ── Recargar configuración de Fish Audio ────────────────────────────
        self._fish_audio_enabled = cfg.get("fish_audio_enabled", False)
        self._fish_api_key       = cfg.get("fish_api_key", "")
        self._fish_voice_id      = cfg.get("fish_voice_id", "")
        if self._fish_audio_enabled:
            print(f"[NEXUS] 🐟 Fish Audio {'activado' if self._fish_api_key else 'activado pero sin API Key'}")
        # ────────────────────────────────────────────────────────────────────
        
        # ── Recargar configuración de Voz Local XTTS-v2 ──────────────────
        self._local_tts_enabled = cfg.get("local_tts_enabled", False)
        if self._local_tts_enabled and self._local_tts is None:
            print("[NEXUS] 🎙️ Clonación de Voz Local (XTTS-v2) activada. Inicializando motor...")
            try:
                from tts_engine import get_engine
                self._local_tts = get_engine()
            except Exception as e:
                print(f"[NEXUS] Error cargando tts_engine: {e}")
        # ────────────────────────────────────────────────────────────────────
        
        self.update_wake_words(cfg)
        print("[NEXUS] ⚙️ Config actualizada — reconectando sesión...")
        self.ui.write_log("SYS: Aplicando nueva configuración...")
        if self._reconnect_event and self._loop:
            self._loop.call_soon_threadsafe(self._reconnect_event.set)

    def _antivirus_watcher_loop(self):
        """Monitors the Downloads folder for newly completed files and scans them."""
        import os
        import time
        from pathlib import Path
        import actions.download_manager as dm
        downloads_dir = Path.home() / "Downloads"
        
        # Keep track of files we've already seen
        try:
            if not downloads_dir.exists():
                return
            known_files = set(f.name for f in downloads_dir.iterdir() if f.is_file())
        except Exception:
            known_files = set()
            
        pending_files = {} # Dict of {filename: last_size} to check if download is finished
        
        while True:
            time.sleep(5)
            try:
                current_files = set()
                for f in downloads_dir.iterdir():
                    if not f.is_file(): continue
                    current_files.add(f.name)
                    
                    if f.name not in known_files:
                        # Skip temporary download extensions
                        if f.name.endswith(".tmp") or f.name.endswith(".crdownload") or f.name.endswith(".part"):
                            continue
                            
                        # It's a new file. Wait until size stops changing to ensure it's fully downloaded.
                        try:
                            size = f.stat().st_size
                        except Exception:
                            continue
                            
                        if size == 0:
                            continue
                            
                        if f.name not in pending_files:
                            pending_files[f.name] = size
                        else:
                            if pending_files[f.name] == size:
                                # File size stabilized, it's ready to scan!
                                del pending_files[f.name]
                                known_files.add(f.name)
                                
                                # Scan the file using Defender
                                scan_result = dm.scan_with_defender(str(f))
                                if "MALWARE" in scan_result.upper() or "PELIGRO" in scan_result.upper():
                                    self.ui.write_log(f"🛡️ [ANTIVIRUS] {scan_result}")
                                    # Speak the warning out loud
                                    self.speak("¡Advertencia crítica! El sistema antivirus en segundo plano acaba de detectar malware en tu última descarga. Elimina el archivo inmediatamente.")
                                else:
                                    # Just log it silently
                                    self.ui.write_log(f"🛡️ [ANTIVIRUS] {f.name} escaneado y limpio.")
                            else:
                                pending_files[f.name] = size
                
                # Clean up known files that were deleted to save memory
                known_files.intersection_update(current_files)
                # Clean up pending files that were deleted
                pending_keys = list(pending_files.keys())
                for k in pending_keys:
                    if k not in current_files:
                        del pending_files[k]
                        
            except Exception as e:
                pass # Fail silently so the thread doesn't crash

    def _meditation_loop(self):
        """Loop to check inactivity and play meditation sound."""
        while True:
            time.sleep(10)
            if time.time() - getattr(self, 'last_activity', time.time()) > 300: # 5 minutos (300 segundos)
                if not getattr(self, '_meditation_playing', False):
                    print("[NEXUS] Iniciando estado de meditación...")
                    play_mp3_sound("meditacion")
                    self._meditation_playing = True
            else:
                if getattr(self, '_meditation_playing', False):
                    self._meditation_playing = False
                    try:
                        import pygame
                        pygame.mixer.music.stop()
                        pygame.mixer.stop()
                    except:
                        pass

    def update_wake_words(self, cfg: dict):
        ai_name = cfg.get("ai_name", "").strip().lower()
        base_wake = ["despierta", "sal del modo suspensión", "salir del modo suspensión"]
        
        words = list(base_wake)
        if ai_name:
            ai_name_clean = ai_name.replace("¡", "").replace("!", "").strip()
            if ai_name_clean and ai_name_clean not in words:
                words.append(ai_name_clean)
                
                # Add basic phonetic variations
                if len(ai_name_clean) > 3:
                    words.append(ai_name_clean[:-1])
                    words.append(ai_name_clean[1:])
                    if ai_name_clean.endswith('a') or ai_name_clean.endswith('s'):
                        words.append(ai_name_clean[:-1])
                        
        self.wake_words = list(set(words))
        
    def _load_speaker_profile(self):
        import json
        from pathlib import Path
        spk_path = Path("memory/speaker_profile.json")
        self.master_speaker_vector = None
        if spk_path.exists():
            try:
                data = json.loads(spk_path.read_text("utf-8"))
                self.master_speaker_vector = data.get("vector")
                print(f"[NEXUS] Perfil biométrico de voz maestro cargado.")
            except Exception as e:
                print(f"[NEXUS] Error leyendo perfil biométrico: {e}")

    def _is_unauthorized_speaker(self, current_vector):
        if not self.master_speaker_vector or not current_vector:
            return False
        import numpy as np
        a = np.array(self.master_speaker_vector)
        b = np.array(current_vector)
        similarity = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
        # Threshold (0.6 is a common strictness for Vosk SpkModel, usually same speaker is >0.7)
        return similarity < 0.65

    async def _watch_reconnect(self):
        """Task that triggers a graceful reconnect when config changes."""
        if self._reconnect_event:
            await self._reconnect_event.wait()
            raise RuntimeError("Config changed — reconnect requested")

    def _on_text_command(self, text: str):
        # Handle SYS_TOGGLE_SUSPEND BEFORE session check — suspension is a local operation
        if text == "SYS_TOGGLE_SUSPEND":
            if getattr(self, "is_sleeping", False):
                self.is_sleeping = False
                self.ui.set_state("LISTENING")
                self.ui.write_log("SYS: 🟢 ¡Despierto!")
                self.ui.update_suspend_button(False)
                try:
                    import winsound
                    import os
                    audio_path = os.path.join(os.path.dirname(__file__), "SuspenderNexus.wav")
                    winsound.PlaySound(audio_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                except: pass
            else:
                self.is_sleeping = True
                self.ui.write_log("SYS: 💤 Entrando en suspensión local.")
                self.ui.set_state("MUTED")
                self.ui.update_suspend_button(True)
                try:
                    import winsound
                    import os
                    audio_path = os.path.join(os.path.dirname(__file__), "SuspenderNexus.wav")
                    winsound.PlaySound(audio_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                except: pass
                if getattr(self, "audio_in_queue", None):
                    while not self.audio_in_queue.empty():
                        try: self.audio_in_queue.get_nowait()
                        except: break
                self.set_speaking(False)
            return
            
        if text == "SYS_REGISTER_VOICE":
            self.registering_voice = True
            self.ui.write_log("SYS: 🎤 Hable ahora para registrar su voz (unos 3-5 segundos).")
            return

        if not self._loop or not self.session:
            return

        if text == "SYS_UNAUTHORIZED_SPEAKER":
            text = "[SYS: El hablante actual es DESCONOCIDO. Rechaza la orden educadamente indicando que solo sirves a tu señor.]"

        if getattr(self, "is_sleeping", False):
            # Check if text contains wake word or despierta
            text_lower = text.lower()
            wake_words = getattr(self, "wake_words", ["despierta", "sal del modo suspensión", "salir del modo suspensión"])
            if any(w in text_lower for w in wake_words):
                self.is_sleeping = False
                self.ui.set_state("LISTENING")
                self.ui.write_log("SYS: 🟢 ¡Despierto por comando de texto!")
                # Play sound
                try:
                    import winsound
                    import os
                    audio_path = os.path.join(os.path.dirname(__file__), "SuspenderNexus.wav")
                    winsound.PlaySound(audio_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                except: pass
            else:
                assigned_name = "NEXUS"
                try:
                    import json, os
                    if os.path.exists("config/api_keys.json"):
                        with open("config/api_keys.json", "r", encoding="utf-8") as f:
                            assigned_name = json.load(f).get("ai_name", "NEXUS").strip() or "NEXUS"
                except: pass
                self.ui.write_log(f"SYS: 💤 {assigned_name.capitalize()} está en modo suspensión. Di '{assigned_name}' o escribe 'despierta' para despertarlo.")
                return

        # Audio file: process with Gemini Vision (not the realtime audio session)
        if text.startswith("[AUDIO_FILE]"):
            m = re.search(r'path=([^\s|]+)', text)
            if m:
                asyncio.run_coroutine_threadsafe(
                    self._process_audio_file(m.group(1)), self._loop
                )
            return

        # Check phrase triggers — if one fires, don't also send to Gemini
        if self._fire_phrase_triggers(text):
            return
        self._stop_requested.clear()
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    async def _process_audio_file(self, path: str):
        """Transcribe and analyze an audio file via Gemini (separate from realtime session)."""
        try:
            p = Path(path)
            if not p.exists():
                self.ui.write_log(f"❌ Archivo no encontrado: {path}")
                return

            self.ui.set_state("THINKING")
            self.ui.write_log(f"🎵 Procesando audio: {p.name}…")

            data = p.read_bytes()
            ext  = p.suffix.lower().lstrip(".")
            mime_map = {
                "mp3": "audio/mpeg", "wav": "audio/wav", "m4a": "audio/mp4",
                "ogg": "audio/ogg",  "flac": "audio/flac", "aac": "audio/aac",
                "wma": "audio/x-ms-wma", "opus": "audio/opus", "webm": "audio/webm",
            }
            mime = mime_map.get(ext, "audio/mpeg")

            loop = asyncio.get_event_loop()

            def _analyze():
                client = genai.Client(api_key=_get_api_key())
                resp = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=[
                        types.Content(parts=[
                            types.Part(text=(
                                f"El usuario adjuntó un archivo de audio: '{p.name}'.\n"
                                "1. Transcribí el contenido del audio.\n"
                                "2. Si es música, identificá la canción/artista si podés.\n"
                                "3. Describí brevemente qué contiene.\n"
                                "Respondé en español."
                            )),
                            types.Part(
                                inline_data=types.Blob(data=data, mime_type=mime)
                            ),
                        ])
                    ],
                )
                return resp.text.strip()

            result = await loop.run_in_executor(_TOOL_EXECUTOR, _analyze)
            self.ui.write_log(f"NEXUS: {result}")

            # Feed result back into the realtime session so NEXUS can speak it
            if self.session:
                await self.session.send_client_content(
                    turns={"parts": [{"text": f"[RESULTADO AUDIO '{p.name}']\n{result}"}]},
                    turn_complete=True
                )

        except Exception as e:
            traceback.print_exc()
            self.ui.write_log(f"❌ Error procesando audio: {e}")
        finally:
            if not self.ui.muted:
                self.ui.set_state("LISTENING")

    def _fire_phrase_triggers(self, user_text: str) -> bool:
        """
        Check phrase-based automations. Returns True if any trigger fired
        (caller should skip sending the text to Gemini in that case).
        """
        text_lower = user_text.lower()

        # ── Suspensión Rápida (Micrófono) ─────────────────────────────────────
        if any(w in text_lower for w in ["suspenderse", "suspender", "silenciar micrófono", "apagar micrófono", "no escuches más", "descansa"]):
            self.is_sleeping = True
            self.ui.write_log("SYS: Entrando en suspensión local por comando de voz. Esperando palabra de activación...")
            self.ui.set_state("MUTED")
            return True
            # Clear audio queue and stop speaking
            if self.audio_in_queue:
                while not self.audio_in_queue.empty():
                    try: self.audio_in_queue.get_nowait()
                    except: break
            self.set_speaking(False)
            return True

        # ── Accessibility quick triggers ──────────────────────────────────────
        if any(p in text_lower for p in ["activar seguimiento ocular", "iniciar eye tracking",
                                          "activar control ocular", "encender seguimiento de ojos"]):
            if eye_tracking:
                result = eye_tracking({"action": "start"})
            else:
                self.ui.write_log("⚠️ Módulo de accesibilidad no disponible.")
            self.ui.write_log("⚡ " + result)
            return True

        if any(p in text_lower for p in ["detener seguimiento ocular", "apagar eye tracking",
                                          "desactivar control ocular"]):
            if eye_tracking:
                result = eye_tracking({"action": "stop"})
            else:
                self.ui.write_log("⚠️ Módulo de accesibilidad no disponible.")
            self.ui.write_log("⚡ " + result)
            return True

        if any(p in text_lower for p in ["activar detector de movimientos", "iniciar movimiento",
                                          "activar micromovimientos", "encender control por cabeza"]):
            if micro_movement:
                result = micro_movement({"action": "start"})
            else:
                self.ui.write_log("⚠️ Módulo de accesibilidad no disponible.")
            self.ui.write_log("⚡ " + result)
            return True

        if any(p in text_lower for p in ["detener detector de movimientos", "apagar micromovimientos"]):
            if micro_movement:
                result = micro_movement({"action": "stop"})
            else:
                self.ui.write_log("⚠️ Módulo de accesibilidad no disponible.")
            self.ui.write_log("⚡ " + result)
            return True

        if any(p in text_lower for p in ["simplifica", "simplificar", "dividir en pasos"]):
            for phrase in ["simplifica ", "simplificar ", "dividir en pasos "]:
                if phrase in text_lower:
                    task_text = user_text[len(phrase):].strip()
                    if task_text:
                        if task_simplify:
                            result = task_simplify(task_text)
                        else:
                            self.ui.write_log("⚠️ Módulo de accesibilidad no disponible.")
                        self.ui.write_log("⚡ [Simplificado]\n" + result[:300])
                        return True

        if "agregar rutina" in text_lower or "nueva rutina" in text_lower:
            for phrase in ["agregar rutina ", "nueva rutina "]:
                if phrase in text_lower:
                    routine_name = user_text[len(phrase):].strip()
                    if routine_name:
                        if routine_gamify:
                            result = routine_gamify({"action": "add", "name": routine_name})
                        else:
                            self.ui.write_log("⚠️ Módulo de accesibilidad no disponible.")
                        self.ui.write_log("⚡ " + result)
                        return True

        if "completar rutina" in text_lower or "terminar rutina" in text_lower:
            for phrase in ["completar rutina ", "terminar rutina "]:
                if phrase in text_lower:
                    routine_name = user_text[len(phrase):].strip()
                    if routine_name:
                        if routine_gamify:
                            result = routine_gamify({"action": "complete", "name": routine_name})
                        else:
                            self.ui.write_log("⚠️ Módulo de accesibilidad no disponible.")
                        self.ui.write_log("⚡ " + result)
                        return True

        if "mis rutinas" in text_lower or "ver rutinas" in text_lower or "listar rutinas" in text_lower:
            if routine_gamify:
                result = routine_gamify({"action": "list"})
            else:
                self.ui.write_log("⚠️ Módulo de accesibilidad no disponible.")
            self.ui.write_log("⚡ [Rutinas]\n" + result)
            return True

        # ── User-defined phrase automations ───────────────────────────────────
        try:
            triggered = check_phrase_triggers(user_text)
            if triggered:
                for rule in triggered:
                    action = rule.get("action", {})
                    name   = rule.get("name", "?")
                    self.ui.write_log(f"⚡ Automatización: {name}")
                    threading.Thread(
                        target=_rules_run_action, args=(action,), daemon=True
                    ).start()
                return True  # phrase fired → don't also send to Gemini
        except Exception as e:
            print(f"[NEXUS] phrase trigger error: {e}")

        return False

    def set_speaking(self, value: bool):
        with self._speaking_lock:
            self._is_speaking = value
        if value:
            self.ui.set_state("SPEAKING")
        elif getattr(self, "is_sleeping", False):
            self.ui.set_state("MUTED")
        elif not getattr(self.ui, "muted", False):
            self.ui.set_state("LISTENING")

    def speak(self, text: str):
        if not self._loop or not self.session:
            return
        self._stop_requested.clear()
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def speak_error(self, tool_name: str, error: str):
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} — {short}")
        self.speak(f"I'm afraid {tool_name} ran into a problem, sir. {short}")

    def _on_stop_pressed(self):
        """Llamado desde el hilo de la UI al presionar DETENER o ESC."""
        self._stop_requested.set()
        self.active_tts_tasks_count = 0
        self.set_speaking(False)
        self.ui.write_log("SYS: ⛔ Respuesta detenida.")

        if getattr(self, "_loop", None):
            asyncio.run_coroutine_threadsafe(self._drain_audio_queue(), self._loop)
            asyncio.run_coroutine_threadsafe(self._send_server_interrupt(), self._loop)

    async def _send_server_interrupt(self):
        """No enviamos payload vacío porque la API de Gemini lanza un error 400 y desconecta la sesión. 
           En su lugar, simplemente ignoramos los chunks de audio entrantes en _receive_from_server hasta el turn_complete."""
        pass

    async def _drain_audio_queue(self):
        """Vacía la cola de audio para cortar la reproducción de inmediato."""
        if self.audio_in_queue:
            while not self.audio_in_queue.empty():
                try:
                    self.audio_in_queue.get_nowait()
                except Exception:
                    break
        self.set_speaking(False)
        if not self.ui.muted:
            self.ui.set_state("LISTENING")

    def _build_config(self) -> types.LiveConnectConfig:
        from datetime import datetime

        memory     = load_memory()
        mem_str    = format_memory_for_prompt(memory)
        sys_prompt = _load_system_prompt()

        # Refresh timezone from config each reconnect
        _load_tz()
        now = datetime.now(_BA_TZ)
        
        # Format date explicitly in Spanish to prevent LLM hallucinations
        dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        time_str = f"{dias[now.weekday()]}, {now.day} de {meses[now.month - 1]} de {now.year} — {now.strftime('%I:%M:%S %p')}"
        
        utc_off  = now.strftime("%z")
        tz_name  = str(_BA_TZ)
        time_ctx = (
            f"[CONNECTION DATE & TIME]\n"
            f"At the start of this session, the time was: {time_str}\n"
            f"Timezone: {tz_name} (UTC{utc_off})\n"
            f"CRITICAL: Time passes during the session. If the user asks for the current time or date, DO NOT rely on this timestamp. You MUST use the `get_current_time` tool to get the real time.\n\n"
        )

        parts = [time_ctx]
        if mem_str:
            parts.append(mem_str)
        parts.append(sys_prompt)
        
        if getattr(self.ui, "current_file", None):
            parts.append(f"\n[ACTIVE FILE CONTEXT]\nThe user has dropped or activated a file: '{self.ui.current_file}'. If they refer to 'the file' or 'this document', they mean this one.")


        # Build SpeechConfig
        _voice_name = _get_nexus_voice()
        valid_gemini_voices = {"Aoede", "Puck", "Charon", "Kore", "Fenrir", "Zephyr", "Leda", "Orus"}
        if _voice_name not in valid_gemini_voices:
            _voice_name = "Aoede" # Fallback to prevent API errors with unsupported voices

        _speech_cfg = None
        try:
            _speech_cfg = types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=_voice_name
                    )
                )
            )
        except Exception:
            _speech_cfg = None

        # ── Fish Audio: siempre usamos AUDIO modality (mismo modelo native-audio) ──
        # Cuando Fish Audio está activo, descartamos el audio de Gemini en _receive_audio()
        # y usamos la transcripción de salida para sintetizar con Fish Audio.
        _use_fish = (
            self._fish_audio_enabled
            and self._fish_api_key
            and self._fish_voice_id
        )
        if _use_fish:
            print("[NEXUS] 🐟 Fish Audio activo — audio Gemini será descartado, voz clonada activa")

        cfg_kwargs: dict = dict(
            response_modalities=["AUDIO"],
            output_audio_transcription=types.AudioTranscriptionConfig(),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            system_instruction="\n".join(parts),
            tools=[{"function_declarations": TOOL_DECLARATIONS}],
        )
        if _speech_cfg:
            cfg_kwargs["speech_config"] = _speech_cfg

        # Speaking rate: try output_audio_config (newer SDK versions)
        try:
            cfg_kwargs["output_audio_config"] = types.OutputAudioConfig(
                audio_encoding="LINEAR16",
                speaking_rate=1.15,   # 15% faster — crisp, natural pace
            )
        except Exception:
            pass

        # Temperature directly on LiveConnectConfig (not via deprecated generation_config)
        # Low value = consistent voice tone across reconnects
        try:
            cfg_kwargs["temperature"] = 0.2
        except Exception:
            pass

        # Try typed objects first; fall back to raw dict (SDK version resilience)
        _vad_applied = False
        try:
            cfg_kwargs["realtime_input_config"] = types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    start_of_speech_sensitivity="START_SENSITIVITY_HIGH",
                    end_of_speech_sensitivity="END_SENSITIVITY_HIGH",
                    prefix_padding_ms=60,
                    silence_duration_ms=350,
                )
            )
            _vad_applied = True
            print("[NEXUS] VAD config aplicado (typed)")
        except Exception:
            pass

        if not _vad_applied:
            try:
                cfg_kwargs["realtime_input_config"] = {
                    "automatic_activity_detection": {
                        "start_of_speech_sensitivity": "START_SENSITIVITY_HIGH",
                        "end_of_speech_sensitivity": "END_SENSITIVITY_HIGH",
                        "prefix_padding_ms": 100,
                        "silence_duration_ms": 500,
                    }
                }
                print("[NEXUS] VAD config aplicado (dict)")
            except Exception:
                print("[NEXUS] VAD config no aplicado")

        # ── Context compression: prevent session degradation over time ────────
        try:
            cfg_kwargs["context_window_compression"] = types.ContextWindowCompressionConfig(
                trigger_tokens=12000,
                sliding_window=types.SlidingWindow(target_tokens=6000),
            )
        except Exception:
            pass

        # ── Thinking budget: disable model reasoning for lowest latency ─────────
        # Set directly on LiveConnectConfig (generation_config field is deprecated)
        try:
            cfg_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
        except Exception:
            pass

        return types.LiveConnectConfig(**cfg_kwargs)

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        self.last_activity = time.time()
        name = fc.name
        args = dict(fc.args or {})

        print(f"[NEXUS] 🔧 {name}  {args}")
        self.ui.set_state("THINKING")

        # Futuristic execution sound (assets/sound.mp3)
        play_mp3_sound("sound")

        try:
            if name == "shutdown_nexus":
                self.ui.write_log("SYS: Apagando NEXUS...")
                # Must quit from Qt main thread — signals are thread-safe
                self.ui._win._shutdown_sig.emit()
                return types.FunctionResponse(
                    id=fc.id, name=name,
                    response={"result": "Apagando NEXUS. ¡Hasta luego, señor!"}
                )

            if name == "get_current_time":
                from datetime import datetime
                now = datetime.now()
                dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
                meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
                time_str = f"{dias[now.weekday()]}, {now.day} de {meses[now.month - 1]} de {now.year} — {now.strftime('%I:%M:%S %p')}"
                return types.FunctionResponse(
                    id=fc.id, name=name,
                    response={"result": f"La fecha y hora exacta actual es: {time_str}"}
                )
    
            if name == "save_memory":
                category = args.get("category", "notes")
                key      = args.get("key", "")
                value    = args.get("value", "")
                if key and value:
                    update_memory({category: {key: {"value": value}}})
                    print(f"[Memory] 💾 save_memory: {category}/{key} = {value}")
                if not self.ui.muted:
                    self.ui.set_state("LISTENING")
                return types.FunctionResponse(
                    id=fc.id, name=name,
                    response={"result": "Memory saved."}
                )
    
            if name == "forget_memory":
                category = args.get("category", "")
                key      = args.get("key", "")
                if category and key:
                    from memory.memory_manager import forget
                    forget(category, key)
                    print(f"[Memory] 🗑️ forget_memory: {category}/{key}")
                if not self.ui.muted:
                    self.ui.set_state("LISTENING")
                return types.FunctionResponse(
                    id=fc.id, name=name,
                    response={"result": "Memory deleted."}
                )
    
            loop   = asyncio.get_event_loop()
            result = "Done."
    
            try:
                if name == "open_app":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: open_app(parameters=args, response=None, player=self.ui))
                    result = r or f"Opened {args.get('app_name')}."
    
                elif name == "close_app":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: close_app(parameters=args, response=None, player=self.ui))
                    result = r or f"Closed {args.get('app_name')}."
    
                elif name == "game_control":
                    from actions.game_control import game_control
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: game_control(parameters=args, player=self.ui))
                    result = r or "Juego pausado y verificado."
    
                elif name == "auto_pilot":
                    from actions.auto_pilot import auto_pilot
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: auto_pilot(parameters=args, player=self.ui, speak=self.speak))
                    result = r or "Auto pilot command received."
    
                elif name == "proactive_routine":
                    from actions.proactive_routine import proactive_routine
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: proactive_routine(parameters=args, player=self.ui, speak=self.speak))
                    result = r or "Rutina matutina iniciada."
    
                elif name == "inventory_manager":
                    from actions.inventory_manager import inventory_manager
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: inventory_manager(parameters=args, player=self.ui))
                    result = r or "Inventario actualizado."
    
                elif name == "macros":
                    # Provide real-time recording via macro_recorder directly if action is record_macro
                    if args.get("action") == "record_macro":
                        m_name = args.get("macro_name", "macro_voz")
                        
                        def record_thread():
                            try:
                                from actions.macro_recorder import record_macro_until_esc
                                record_macro_until_esc(m_name)
                                from PyQt6.QtCore import QTimer
                                QTimer.singleShot(0, lambda: self.ui.write_log(f"SYS: ✅ Macro '{m_name}' guardado correctamente."))
                                QTimer.singleShot(0, lambda: getattr(self.ui._win, "update_macros_list_if_open", lambda: None)())
                            except Exception as e:
                                from PyQt6.QtCore import QTimer
                                QTimer.singleShot(0, lambda: self.ui.write_log(f"SYS: ❌ Error grabando macro: {e}"))
                        
                        threading.Thread(target=record_thread, daemon=True).start()
                        result = f"Grabación iniciada en tiempo real. Presiona ESC para terminar el macro '{m_name}'."
                    elif args.get("action") == "stop_record":
                        import keyboard
                        keyboard.send("esc")
                        self.ui.write_log("SYS: Grabación finalizada. El macro ha sido guardado exitosamente.")
                        threading.Thread(target=lambda: self.speak("Grabación finalizada. El macro ha sido guardado exitosamente."), daemon=True).start()
                        result = "Grabación detenida mediante ESC y macro guardado."
                    elif args.get("action") == "execute_macro" and args.get("macro_name"):
                        m_name = args.get("macro_name")
                        from actions.macro_recorder import MACROS_FILE, play_macro
                        import json
                        exists_in_file = False
                        if MACROS_FILE.exists():
                            try:
                                with open(MACROS_FILE, "r", encoding="utf-8") as f:
                                    data = json.load(f)
                                    if m_name in data: exists_in_file = True
                            except: pass
                        if exists_in_file:
                            r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: play_macro(m_name))
                            result = f"Macro guardado '{m_name}' reproducido exitosamente." if r else f"Fallo al reproducir macro '{m_name}'."
                        else:
                            r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: macros(parameters=args, player=self.ui))
                            result = r or f"Macro {args.get('action')} ejecutado."
                    else:
                        r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: macros(parameters=args, player=self.ui))
                        result = r or f"Macro {args.get('action')} ejecutado."
    
                elif name == "sleep_mode":
                    # Ensure sleep mode acts exactly like the UI button toggle
                    self._on_text_command("SYS_TOGGLE_SUSPEND")
                    # Immediately empty the audio in queue to stop any playing/queued audio
                    if self.audio_in_queue:
                        while not self.audio_in_queue.empty():
                            try:
                                self.audio_in_queue.get_nowait()
                            except Exception:
                                break
                    self.set_speaking(False)
                    result = "Entrando en suspensión absoluta. Cortando transmisión a la nube hasta ser despertado localmente."
    
                elif name == "weather_report":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: weather_action(parameters=args, player=self.ui))
                    result = r or "Weather delivered."
    
                elif name == "browser_control":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: browser_control(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "visual_click":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: visual_click(parameters=args, player=self.ui))
                    result = r or "Done."
    
    
    
                elif name == "file_controller":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: file_controller(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "send_message":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: send_message(parameters=args, response=None, player=self.ui, session_memory=None))
                    result = r or f"Message sent to {args.get('receiver')}."
    
                elif name == "reminder":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: reminder(parameters=args, response=None, player=self.ui))
                    result = r or "Reminder set."
    
    
                elif name == "descargar_youtube":
                    if download_youtube:
                        r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: download_youtube(parameters=args, player=self.ui))
                        result = r or "Descarga iniciada."
                    else:
                        result = "Herramienta de descarga de YouTube no disponible."
    
                elif name == "activar_modo_estudiante":
                    if activar_modo_estudiante:
                        r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: activar_modo_estudiante(parameters=args, player=self.ui))
                        result = r or "Modo estudiante activado."
                    else:
                        result = "Herramienta de modo estudiante no disponible."
    
                elif name == "student_paraphrase":
                    if student_paraphrase:
                        r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: student_paraphrase(parameters=args, player=self.ui))
                        result = r or "Parafraseo completado."
                    else:
                        result = "Herramienta de parafraseo no disponible."
    
                elif name == "student_verify_apa":
                    if student_verify_apa:
                        r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: student_verify_apa(parameters=args, player=self.ui))
                        result = r or "Verificación APA 7 completada."
                    else:
                        result = "Herramienta de APA 7 no disponible."
    
                elif name == "student_pdf_to_word":
                    if student_pdf_to_word:
                        r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: student_pdf_to_word(parameters=args, player=self.ui))
                        result = r or "Conversión de PDF iniciada."
                    else:
                        result = "Herramienta de conversión PDF no disponible."
    
                elif name == "student_quality_report":
                    if student_quality_report:
                        r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: student_quality_report(parameters=args, player=self.ui))
                        result = r or "Reporte de calidad completado."
                    else:
                        result = "Herramienta de reporte de calidad no disponible."
    
                elif name == "youtube_video":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: youtube_video(parameters=args, response=None, player=self.ui))
                    result = r or "Done."
    
                elif name == "screen_process" or name == "screen_vision":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: screen_vision(parameters=args, player=self.ui))
                    result = r or "No pude analizar la imagen/pantalla."
    
                elif name == "computer_settings":
                    action = args.get("action", "")
                    if action == "volume":
                        val = args.get("value", "")
                        try:
                            import pyautogui
                            # Si es un número absoluto (ej: '50')
                            if str(val).isdigit():
                                target = int(val)
                                try:
                                    from ctypes import cast, POINTER
                                    from comtypes import CoInitialize, CoUninitialize
                                    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                                    CoInitialize()
                                    devices = AudioUtilities.GetSpeakers()
                                    interface = devices.Activate(IAudioEndpointVolume._iid_, 1, None)
                                    volume_ctrl = cast(interface, POINTER(IAudioEndpointVolume))
                                    # Rango 0.0 a 1.0
                                    scalar_vol = max(0.0, min(1.0, target / 100.0))
                                    volume_ctrl.SetMasterVolumeLevelScalar(scalar_vol, None)
                                    CoUninitialize()
                                    result = f"Volumen ajustado al {target}%."
                                except Exception as e:
                                    result = f"Error ajustando volumen absoluto: {e}"
                            else:
                                # Comando relativo: up, down, mute
                                if "up" in val.lower() or "subir" in val.lower():
                                    pyautogui.press("volumeup", presses=5)
                                    result = "Volumen subido."
                                elif "down" in val.lower() or "bajar" in val.lower():
                                    pyautogui.press("volumedown", presses=5)
                                    result = "Volumen bajado."
                                elif "mute" in val.lower() or "silenciar" in val.lower():
                                    pyautogui.press("volumemute")
                                    result = "Volumen silenciado."
                                else:
                                    result = f"Acción de volumen no reconocida: {val}"
                        except Exception as ve:
                            result = f"Error en control de volumen: {ve}"
                    else:
                        if action in ["window_minimize", "minimize"]:
                            if gw:
                                try:
                                    window = gw.getActiveWindow()
                                    if window: window.minimize()
                                    result = "Ventana minimizada."
                                except Exception as e:
                                    result = f"Error al minimizar: {e}"
                            else:
                                result = "Librería pygetwindow no disponible."
                        elif action in ["window_maximize", "maximize"]:
                            if gw:
                                try:
                                    window = gw.getActiveWindow()
                                    if window: window.maximize()
                                    result = "Ventana maximizada."
                                except Exception as e:
                                    result = f"Error al maximizar: {e}"
                            else:
                                result = "Librería pygetwindow no disponible."
                        else:
                            r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: computer_settings(parameters=args, response=None, player=self.ui))
                            result = r or "Done."
    
                elif name == "desktop_control":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: desktop_control(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "code_helper":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: code_helper(parameters=args, player=self.ui, speak=self.speak))
                    result = r or "Done."
    
                elif name == "dev_agent":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: dev_agent(parameters=args, player=self.ui, speak=self.speak))
                    result = r or "Done."
    
                elif name == "agent_task":
                    from agent.task_queue import get_queue, TaskPriority
                    priority_map = {"low": TaskPriority.LOW, "normal": TaskPriority.NORMAL, "high": TaskPriority.HIGH}
                    priority = priority_map.get(args.get("priority", "normal").lower(), TaskPriority.NORMAL)
                    task_id  = get_queue().submit(goal=args.get("goal", ""), priority=priority, speak=self.speak)
                    result   = f"Task started (ID: {task_id})."
    
                elif name == "web_download":
                    if web_download:
                        r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: web_download(parameters=args, player=self.ui))
                    else:
                        r = "Módulo web_download no disponible."
                    result = r or "Done."
                elif name == "file_converter":
                    if convert_file:
                        r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: convert_file(input_path=args.get("input_path", ""), output_format=args.get("output_format", ""), player=self.ui))
                    else:
                        r = "Módulo file_converter no disponible."
                    result = r or "Done."
                elif name == "web_search":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: web_search_action(parameters=args, player=self.ui))
                    result = r or "Done."
                elif name == "file_processor":
                    if not args.get("file_path") and self.ui.current_file:
                        args["file_path"] = self.ui.current_file
                    r = await loop.run_in_executor(
                        _TOOL_EXECUTOR,
                        lambda: file_processor(parameters=args, player=self.ui, speak=self.speak)
                    )
                    result = r or "Done."
    
                elif name == "computer_control":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: computer_control(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "game_updater":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: game_updater(parameters=args, player=self.ui, speak=self.speak))
                    result = r or "Done."
    
                elif name == "flight_finder":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: flight_finder(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "google_calendar":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: google_calendar(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "spotify_control":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: spotify_control(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "rgb_control":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: rgb_control(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "scheduler":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: scheduler(parameters=args, player=self.ui, speak=self.speak))
                    result = r or "Done."
    
                elif name == "google_drive":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: google_drive(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "google_maps":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: google_maps(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "gmail_control":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: gmail_control(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "rules_engine":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: rules_engine(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "user_profile":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: user_profile(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "goals":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: goals(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "git_control":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: git_control(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "codebase":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: codebase(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "knowledge_base":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: knowledge_base(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "whatsapp":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: whatsapp(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "instagram":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: instagram(parameters=args, player=self.ui))
                    result = r or "Done."

                elif name == "vault":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: vault(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "delivery_apps":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: delivery_apps(parameters=args, player=self.ui))
                    result = r or "Done."

                elif name == "ride_apps":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: ride_apps(parameters=args, player=self.ui))
                    result = r or "Done."

                elif name == "social_media":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: social_media(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "universal_app_control":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: universal_app_control(parameters=args, player=self.ui))
                    result = r or "Done."

                elif name == "visual_memory":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: visual_memory(parameters=args, player=self.ui))
                    result = r or "Done."

                elif name == "auto_healer":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: auto_healer(parameters=args, player=self.ui))
                    result = r or "Done."

                elif name == "game_companion":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: game_companion(parameters=args, player=self.ui))
                    result = r or "Done."

                elif name == "holographic_translator":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: holographic_translator(parameters=args, player=self.ui))
                    result = r or "Done."

                elif name == "discord_control":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: discord_control(parameters=args, player=self.ui))
                    result = r or "Done."

                elif name == "youtube_control":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: youtube_control(parameters=args, player=self.ui))
                    result = r or "Done."

                elif name == "blind_reader":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: blind_reader(parameters=args, player=self.ui))
                    result = r or "Done."

                elif name == "playwright_agent":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: playwright_agent(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "windows_settings":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: windows_settings(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "document_creator":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: document_creator(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "image_generation":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: image_generation(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "smart_home":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: smart_home(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "meeting_assistant":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: meeting_assistant(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "smart_inbox":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: smart_inbox(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "finance_reader":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: finance_reader(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "personal_shopper":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: personal_shopper(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "powerpoint_generator":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: powerpoint_generator(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "speech_coach":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: speech_coach(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "system_monitor":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: system_monitor(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "tiktok_analyzer":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: tiktok_analyzer(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "arca_invoice":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: arca_invoice(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "accessibility":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: accessibility(parameters=args, player=self.ui))
                    result = r or "Done."
    
    
    
                elif name == "morning_brief":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: morning_brief(parameters=args, player=self.ui))
                    result = r or "Aquí está tu informe del día."
    
                elif name == "vision_guardian":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: vision_guardian(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "screen_reader":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: screen_reader(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "accessibility_overlay":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: accessibility_overlay(parameters=args, player=self.ui))
                    result = r or "Done."
    
                elif name == "openrouter_agent":
                    if openrouter_agent:
                        # Se delega la tarea a OpenRouter
                        self.ui.write_log("🤖 Delegando tarea a OpenRouter...")
                        r = await loop.run_in_executor(
                            _TOOL_EXECUTOR, 
                            lambda: openrouter_agent(
                                query=args.get("query", ""),
                                model=args.get("model", "google/gemini-2.5-flash")
                            )
                        )
                        result = r or "Error al procesar con OpenRouter."
                    else:
                        result = "Módulo openrouter_agent no encontrado."
    
                elif name == "terminal_agent":
                    if terminal_agent:
                        self.ui.write_log("⚠️ Ejecutando en Terminal...")
                        r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: terminal_agent(parameters=args, player=self.ui))
                        result = r or "Comando ejecutado."
                    else:
                        result = "Módulo terminal_agent no encontrado."
    
                elif name == "native_ui":
                    if native_ui:
                        self.ui.write_log("💻 UI Nativa en acción...")
                        r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: native_ui(parameters=args, player=self.ui))
                        result = r or "Acción de UI completada."
                    else:
                        result = "Módulo native_ui no encontrado."
    
                elif name == "nexus_ui_control":
                    action_ui = args.get("action", "").lower()
                    widget_name = args.get("widget", "").lower()
                    if action_ui == "minimize":
                        try:
                            if hasattr(self.ui, "_win") and hasattr(self.ui._win, "showMinimized"):
                                from PyQt6.QtCore import QTimer
                                QTimer.singleShot(0, self.ui._win.showMinimized)
                            elif hasattr(self.ui, "root") and hasattr(self.ui.root, "iconify"):
                                self.ui.root.after(0, self.ui.root.iconify)
                            result = "Interfaz de usuario minimizada."
                        except Exception as ui_e:
                            result = f"Error al minimizar: {ui_e}"
                    elif action_ui == "restore":
                        try:
                            if hasattr(self.ui, "_win") and hasattr(self.ui._win, "showNormal"):
                                from PyQt6.QtCore import QTimer
                                QTimer.singleShot(0, self.ui._win.showNormal)
                                QTimer.singleShot(0, self.ui._win.activateWindow)
                            elif hasattr(self.ui, "root") and hasattr(self.ui.root, "deiconify"):
                                def _restore():
                                    self.ui.root.deiconify()
                                    self.ui.root.attributes("-topmost", True)
                                    self.ui.root.attributes("-topmost", False)
                                self.ui.root.after(0, _restore)
                            result = "Interfaz de usuario restaurada."
                        except Exception as ui_e:
                            result = f"Error al restaurar: {ui_e}"
                    elif action_ui == "hide_all":
                        self.ui.write_log("__hide__")
                        result = "Todos los widgets ocultados."
                    elif action_ui in ("show", "hide", "toggle"):
                        if widget_name == "main_window" or not widget_name:
                            if action_ui == "show":
                                try:
                                    if hasattr(self.ui, "_win") and hasattr(self.ui._win, "showNormal"):
                                        from PyQt6.QtCore import QTimer
                                        QTimer.singleShot(0, self.ui._win.showNormal)
                                        QTimer.singleShot(0, self.ui._win.activateWindow)
                                    elif hasattr(self.ui, "root") and hasattr(self.ui.root, "deiconify"):
                                        def _restore():
                                            self.ui.root.deiconify()
                                            self.ui.root.attributes("-topmost", True)
                                            self.ui.root.attributes("-topmost", False)
                                        self.ui.root.after(0, _restore)
                                    result = "Interfaz de usuario restaurada."
                                except Exception as ui_e:
                                    result = f"Error al restaurar: {ui_e}"
                            else:
                                self.ui.write_log("__hide__")
                                result = "Todos los widgets ocultados."
                        else:
                            cmd = "__widget_show__" if action_ui in ("show", "toggle") else "__widget_close__"
                            self.ui.write_log(f"{cmd}:{widget_name}")
                            result = f"Widget '{widget_name}' {'mostrado' if 'show' in cmd else 'ocultado'}."
                    else:
                        result = f"Acción de UI desconocida: {action_ui}"
    
                else:
                    # Intento de cargar herramienta dinámica (tool_creator u otras)
                    import importlib
                    import inspect
                    try:
                        module = importlib.import_module(f"actions.{name}")
                        func = getattr(module, name)
                        sig = inspect.signature(func)
                        kwargs = {"parameters": args, "player": self.ui}
                        if "speak" in sig.parameters: kwargs["speak"] = self.speak
                        r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: func(**kwargs))
                        result = r or f"Herramienta {name} ejecutada."
                    except Exception as dyn_e:
                        result = f"Unknown tool: {name}. (Dynamic load failed: {dyn_e})"
    
            except Exception as e:
                result = f"Tool '{name}' failed: {e}"
                traceback.print_exc()
                self.speak_error(name, e)
    
        except Exception as e:
            play_mp3_sound("error")
            err_msg = traceback.format_exc()
            print(f"[NEXUS] Error ejecutando {name}:\n{err_msg}")
            result = f"Error ejecutando {name}: {str(e)}"
            self.ui.write_log(f"❌ Error en {name}")

        # Record action for habit learning (fire-and-forget, non-blocking)
        if record_action:
            threading.Thread(target=lambda: record_action(name, args), daemon=True).start()

        if not self.ui.muted:
            self.ui.set_state("LISTENING")

        pass

        print(f"[NEXUS] 📤 {name} → {str(result)[:80]}")
        return types.FunctionResponse(
            id=fc.id, name=name,
            response={"result": result}
        )

    async def _send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            await self.session.send_realtime_input(media=msg)

    async def _listen_audio(self):
        print("[NEXUS] 🎤 Mic iniciado")
        loop = asyncio.get_event_loop()

        def callback(indata, frames, time_info, status):
            # Si el usuario hace clic en el botón de la interfaz para desmutear, salir de suspensión
            if getattr(self, "is_sleeping", False) and not self.ui.muted:
                self.is_sleeping = False
                
            if getattr(self, "is_sleeping", False):
                if getattr(self, "vosk_recognizer", None):
                    audio_data = indata.tobytes()
                    is_final = self.vosk_recognizer.AcceptWaveform(audio_data)
                    
                    # ── Instant wakeup using PartialResult ───────────────────
                    partial_res = json.loads(self.vosk_recognizer.PartialResult())
                    partial_text = partial_res.get("partial", "").lower()
                    
                    # Prevent Vosk buffer saturation/stagnation by periodically resetting on continuous noise
                    if len(partial_text) > 150:
                        self.vosk_recognizer.Reset()
                        partial_text = ""
                    
                    text = ""
                    if is_final:
                        res = json.loads(self.vosk_recognizer.Result())
                        text = res.get("text", "").lower()
                        
                    wake_words = getattr(self, "wake_words", ["despierta", "sal del modo suspensión"])
                                  
                    should_wake = False
                    partial_stripped = partial_text.replace(" ", "")
                    text_stripped = text.replace(" ", "")
                    
                    for w in wake_words:
                        w_clean = w.replace(" ", "")
                        if w in partial_text or (text and w in text) or (w_clean and w_clean in partial_stripped) or (text_stripped and w_clean in text_stripped):
                            should_wake = True
                            break
                            
                    if should_wake:
                        self.vosk_recognizer.Reset()
                        # Use local command to wake up properly syncing UI
                        self._on_text_command("SYS_TOGGLE_SUSPEND")
                        self.ui.muted = False
                        
                        return

            with self._speaking_lock:
                nexus_speaking = self._is_speaking
            if not nexus_speaking and not self.ui.muted:
                # Calculate RMS audio level for sphere visualization
                rms = 0.0
                try:
                    rms = float(np.sqrt(np.mean(indata.astype(np.float32) ** 2))) / 32768.0
                    self.ui.set_audio_level(min(1.0, rms * 18))
                except Exception:
                    pass

                # Filtro de Puerta de Ruido Adaptativo (VAD local dinámico en tiempo real)
                import time
                now = time.time()
                threshold = getattr(self, "noise_gate_threshold", 0.003)
                
                # Inicializar y actualizar el piso de ruido dinámico (rolling minimum)
                if not hasattr(self, "_noise_floor_samples"):
                    self._noise_floor_samples = []
                    self._last_noise_floor_update = now
                
                # Tomar muestra cada 100ms
                if now - getattr(self, "_last_noise_floor_update", 0.0) > 0.1:
                    self._noise_floor_samples.append(rms)
                    self._last_noise_floor_update = now
                    # Mantener últimas 50 muestras (~5 segundos)
                    if len(self._noise_floor_samples) > 50:
                        self._noise_floor_samples.pop(0)
                    
                    # El ruido base ambiental es el mínimo RMS de los últimos 5s
                    self._ambient_noise_floor = min(self._noise_floor_samples)
                
                ambient_floor = getattr(self, "_ambient_noise_floor", 0.001)
                # Si el usuario configura una sensibilidad alta (umbral muy bajo < 0.001), respetamos su umbral exacto
                # De lo contrario, usamos un multiplicador dinámico optimizado capado a 0.004 para que el ruido de juegos/música
                # no bloquee la voz del usuario.
                if threshold < 0.0012:
                    dynamic_threshold = threshold
                else:
                    dynamic_threshold = min(max(threshold, ambient_floor * 1.15), 0.004)
                
                if rms > dynamic_threshold:
                    self.last_speech_time = now

                # Si estamos dentro del tiempo de resaca (hangover) de 0.8s, transmitir el paquete
                if now - getattr(self, "last_speech_time", 0.0) < 0.8:
                    data = indata.tobytes()
                    if getattr(self, "vosk_interrupt_recognizer", None):
                        try:
                            if self.vosk_interrupt_recognizer.AcceptWaveform(data):
                                res = json.loads(self.vosk_interrupt_recognizer.Result())
                                current_vec = res.get("spk")
                                if current_vec:
                                    if getattr(self, "registering_voice", False):
                                        from pathlib import Path
                                        Path("memory").mkdir(exist_ok=True)
                                        Path("memory/speaker_profile.json").write_text(json.dumps({"vector": current_vec}), "utf-8")
                                        self.master_speaker_vector = current_vec
                                        self.registering_voice = False
                                        self.ui.write_log("SYS: ✅ ¡Perfil de voz registrado exitosamente!")
                                        import winsound
                                        import os
                                        try: winsound.PlaySound(os.path.join(os.path.dirname(__file__), "NexusInicioRAV.wav"), winsound.SND_FILENAME | winsound.SND_ASYNC)
                                        except: pass
                                    elif self._is_unauthorized_speaker(current_vec):
                                        self.ui.write_log("SYS: 🛑 Intruso detectado. Bloqueando comando.")
                                        self._on_text_command("SYS_UNAUTHORIZED_SPEAKER")
                                        self.vosk_interrupt_recognizer.Reset()
                        except Exception:
                            pass

                    def _safe_put(q, item):
                        try:
                            q.put_nowait(item)
                        except Exception:
                            pass
                    loop.call_soon_threadsafe(
                        _safe_put, self.out_queue, {"data": data, "mime_type": "audio/pcm"}
                    )
                else:
                    # Enviar un paquete vacío de "keep-alive" cada 10 segundos de silencio para mantener el WebSocket vivo
                    if now - getattr(self, "last_keepalive_time", 0.0) >= 10.0:
                        self.last_keepalive_time = now
                        data = bytes(CHUNK_SIZE * 2) # Datos en cero (silencio)
                        def _safe_put(q, item):
                            try:
                                q.put_nowait(item)
                            except Exception:
                                pass
                        loop.call_soon_threadsafe(
                            _safe_put, self.out_queue, {"data": data, "mime_type": "audio/pcm"}
                        )
            elif nexus_speaking:
                try:
                    rms = float(np.sqrt(np.mean(indata.astype(np.float32) ** 2))) / 32768.0
                    self.ui.set_audio_level(min(1.0, rms * 15))
                    
                    # Interrupción por voz INTELIGENTE: solo interrumpir si se detectan PALABRAS reales,
                    # no ruidos ambientales (motos, perros, música, ventiladores, etc.)
                    threshold = getattr(self, "noise_gate_threshold", 0.003)
                    interrupt_threshold = max(0.025, threshold * 4.0)  # Ligeramente más estricto
                    
                    if rms > interrupt_threshold:
                        self._interrupt_frames = getattr(self, "_interrupt_frames", 0) + 1
                        
                        # Usar Vosk para validar que el audio contiene palabras reales
                        _vosk_speech_detected = False
                        partial_text = ""
                        if getattr(self, "vosk_interrupt_recognizer", None):
                            audio_data = indata.tobytes()
                            self.vosk_interrupt_recognizer.AcceptWaveform(audio_data)
                            partial_res = json.loads(self.vosk_interrupt_recognizer.PartialResult())
                            partial_text = partial_res.get("partial", "").strip()
                            
                            # Requerimos al menos 3 caracteres (palabras reales y no ruidos cortos)
                            if len(partial_text) >= 3:
                                _vosk_speech_detected = True
                            # Si detecta comandos de parada explícitos, interrumpe de inmediato
                            if any(w in partial_text.lower() for w in ["para", "nexus", "stop", "espera", "silencio"]):
                                _vosk_speech_detected = True
                                
                            # Evitar saturación del buffer de Vosk
                            if len(partial_text) > 150:
                                self.vosk_interrupt_recognizer.Reset()
                        else:
                            # Sin Vosk disponible: fallback al método anterior (solo RMS)
                            _vosk_speech_detected = True
                        
                        if self._interrupt_frames >= 5 and _vosk_speech_detected:  # ~100ms de voz + palabras reales
                            if not self._stop_requested.is_set():
                                self._stop_requested.set()
                                print(f"[NEXUS] 🎤 ¡Interrupción por voz detectada! (RMS: {rms:.4f} > {interrupt_threshold:.4f}, Palabras: '{partial_text[:30]}')")
                                # Resetear el reconocedor de interrupción para la próxima vez
                                if getattr(self, "vosk_interrupt_recognizer", None):
                                    self.vosk_interrupt_recognizer.Reset()
                                from PyQt6.QtCore import QTimer
                                QTimer.singleShot(0, self._on_stop_pressed)
                    else:
                        self._interrupt_frames = 0
                        # Resetear Vosk cuando hay silencio para limpiar el buffer
                        if getattr(self, "vosk_interrupt_recognizer", None) and getattr(self, "_interrupt_frames", 0) == 0:
                            try:
                                self.vosk_interrupt_recognizer.Reset()
                            except Exception:
                                pass
                except Exception:
                    pass

        while True:
            try:
                mic_device_idx = None
                import json
                from memory.config_manager import BASE_DIR
                api_cfg_path = BASE_DIR / "config" / "api_keys.json"
                if api_cfg_path.exists():
                    try:
                        c = json.loads(api_cfg_path.read_text(encoding="utf-8"))
                        d = c.get("mic_device", "")
                        if d != "":
                            mic_device_idx = int(d)
                    except Exception:
                        pass
                with sd.InputStream(
                    device=mic_device_idx,
                    samplerate=SEND_SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype="int16",
                    blocksize=CHUNK_SIZE,
                    callback=callback,
                ):
                    print("[NEXUS] 🎤 Mic stream open")
                    while True:
                        await asyncio.sleep(0.01)  # 10ms — máxima responsividad del mic
            except Exception as e:
                print(f"[NEXUS] ❌ Micrófono desconectado o buffer overflow: {e}. Reiniciando en 1 segundo...")
                await asyncio.sleep(1.0)

    async def _synthesize_fish_chunk(self, text: str):
        """Sintetiza un fragmento de texto con Fish Audio y lo inyecta en audio_in_queue."""
        if not text.strip() or self._stop_requested.is_set():
            return
        if self._fish_speak_lock is None:
            self._fish_speak_lock = asyncio.Lock()
        
        self.active_tts_tasks_count = getattr(self, "active_tts_tasks_count", 0) + 1
        try:
            async with self._fish_speak_lock:
                if self._stop_requested.is_set():
                    return
                try:
                    from voice.fish_tts import synthesize_speech, FISH_CHUNK_BYTES
                    loop = asyncio.get_event_loop()
                    pcm_data = await loop.run_in_executor(
                        None,
                        lambda: synthesize_speech(
                            text=text,
                            voice_id=self._fish_voice_id,
                            api_key=self._fish_api_key,
                            stop_event=self._stop_requested,
                        )
                    )
                    if not pcm_data or self._stop_requested.is_set():
                        return
                    # Trocear el audio PCM en chunks y alimentar el pipeline de reproducción
                    offset = 0
                    while offset < len(pcm_data):
                        if self._stop_requested.is_set():
                            break
                        end = min(offset + FISH_CHUNK_BYTES, len(pcm_data))
                        self.audio_in_queue.put_nowait(pcm_data[offset:end])
                        offset = end
                except Exception as e:
                    err_msg = str(e)
                    print(f"[NEXUS] ❌ Fish Audio synthesis error: {err_msg}")
                    if "Insufficient Balance" in err_msg:
                        self.ui.write_log("SYS: ERROR EN VOZ CLONADA (SALDO INSUFICIENTE). REVIRTIENDO A VOZ NATIVA DEL SISTEMA.")
                        self._fish_audio_enabled = False
                    elif "Unauthorized" in err_msg:
                        self.ui.write_log("SYS: ERROR EN VOZ CLONADA (API KEY NO AUTORIZADA). REVIRTIENDO A VOZ NATIVA DEL SISTEMA.")
                        self._fish_audio_enabled = False
        finally:
            self.active_tts_tasks_count = max(0, getattr(self, "active_tts_tasks_count", 1) - 1)

    async def _speak_local_chunk_async(self, text: str):
        """Sintetiza y reproduce un fragmento con el motor de voz local XTTS-v2."""
        if not text.strip() or self._stop_requested.is_set():
            return
        if self._tts_speak_lock is None:
            self._tts_speak_lock = asyncio.Lock()
        
        self.active_tts_tasks_count = getattr(self, "active_tts_tasks_count", 0) + 1
        try:
            async with self._tts_speak_lock:
                if self._stop_requested.is_set():
                    return
                try:
                    self.set_speaking(True)
                    from tts_engine import get_engine
                    engine = get_engine()
                    loop = asyncio.get_running_loop()
                    
                    def run_synthesis():
                        try:
                            # Genera chunks de audio PCM int16 a 24000Hz (XTTS o Edge Fallback)
                            chunks_generator = engine.generate_tts_chunks(text)
                            for chunk_bytes in chunks_generator:
                                if self._stop_requested.is_set():
                                    break
                                try:
                                    loop.call_soon_threadsafe(self.audio_in_queue.put_nowait, chunk_bytes)
                                except Exception:
                                    break
                        except Exception as e:
                            print(f"[NEXUS] Exception in local synthesis thread: {e}")
                    
                    await loop.run_in_executor(None, run_synthesis)
                    
                except Exception as e:
                    print(f"[NEXUS] ❌ Error en síntesis de voz local: {e}")
        finally:
            self.active_tts_tasks_count = max(0, getattr(self, "active_tts_tasks_count", 1) - 1)

    async def _receive_audio(self):
        print("[NEXUS] 👂 Recv iniciado")
        out_buf, in_buf = [], []
        _first_chunk   = True
        _last_tool     = None   # track which tool was executing when error hit
        _fish_text_buf = ""     # buffer de texto para Fish Audio
        _local_text_buf = ""    # buffer de texto para XTTS local

        # Determinar si Fish Audio o Voz Local están activos para esta sesión
        _use_fish = (
            self._fish_audio_enabled
            and self._fish_api_key
            and self._fish_voice_id
        )
        _use_local_tts = self._local_tts_enabled

        if _use_fish:
            print("[NEXUS] 🐟 Recv: descartando audio Gemini, usando transcripción → Fish Audio")
        elif _use_local_tts:
            print("[NEXUS] 🎙️ Recv: descartando audio Gemini, usando transcripción → Voz Local (XTTS-v2)")

        try:
            while True:
                async for response in self.session.receive():

                    # Audio de Gemini: solo pasar a reproducción si ni Fish ni Local están activos
                    if response.data:
                        if not self._stop_requested.is_set() and not getattr(self, "is_sleeping", False):
                            if not _use_fish and not _use_local_tts:
                                self.audio_in_queue.put_nowait(response.data)

                    if response.server_content:
                        sc = response.server_content

                        # Transcripción de salida de Gemini (funciona en ambos modos)
                        if sc.output_transcription and sc.output_transcription.text:
                            txt = _clean_transcript(sc.output_transcription.text)
                            if txt:
                                out_buf.append(txt)
                                if _first_chunk:
                                    self.ui.clear_nexus_response()
                                    _first_chunk = False
                                self.ui.stream_nexus_chunk(txt)

                                # Fish Audio: acumular texto y sintetizar en fronteras de frase
                                if _use_fish:
                                    _fish_text_buf += txt
                                    if any(c in txt for c in '.!?\n'):
                                        _chunk_to_speak = _fish_text_buf.strip()
                                        _fish_text_buf = ""
                                        if _chunk_to_speak and not self._stop_requested.is_set():
                                            asyncio.create_task(self._synthesize_fish_chunk(_chunk_to_speak))
                                # Voz Local XTTS-v2: acumular texto y sintetizar en fronteras de frase
                                elif _use_local_tts:
                                    _local_text_buf += txt
                                    if any(c in txt for c in '.!?\n'):
                                        _chunk_to_speak = _local_text_buf.strip()
                                        _local_text_buf = ""
                                        if _chunk_to_speak and not self._stop_requested.is_set():
                                            asyncio.create_task(self._speak_local_chunk_async(_chunk_to_speak))

                        if sc.input_transcription and sc.input_transcription.text:
                            txt = _clean_transcript(sc.input_transcription.text)
                            if txt:
                                in_buf.append(txt)

                        if sc.turn_complete:
                            # Sintetizar texto restante en los buffers
                            if _use_fish and _fish_text_buf.strip() and not self._stop_requested.is_set():
                                asyncio.create_task(self._synthesize_fish_chunk(_fish_text_buf.strip()))
                                _fish_text_buf = ""
                            elif _use_local_tts and _local_text_buf.strip() and not self._stop_requested.is_set():
                                asyncio.create_task(self._speak_local_chunk_async(_local_text_buf.strip()))
                                _local_text_buf = ""
                            self._stop_requested.clear()
                            if self._turn_done_event:
                                self._turn_done_event.set()
                            full_in = " ".join(in_buf).strip()
                            if full_in:
                                self.ui.write_log(f"Tú: {full_in}")
                                self._fire_phrase_triggers(full_in)
                            in_buf = []
                            out_buf = []
                            _first_chunk = True

                    if response.tool_call:
                        self.ui.clear_nexus_response()
                        _first_chunk = True
                        fcs = response.tool_call.function_calls
                        for fc in fcs:
                            print(f"[NEXUS] 📞 {fc.name}")
                            _last_tool = fc.name
                        # Execute all tool calls in parallel when there are multiple
                        if len(fcs) > 1:
                            tasks = [asyncio.create_task(self._execute_tool(fc)) for fc in fcs]
                            fn_responses = list(await asyncio.gather(*tasks))
                        else:
                            fn_responses = [await self._execute_tool(fcs[0])]
                        try:
                            await self.session.send_tool_response(
                                function_responses=fn_responses
                            )
                            _last_tool = None  # only clear AFTER successful send
                        except Exception as tool_err:
                            print(f"[NEXUS] ❌ send_tool_response failed: {tool_err}")
                            raise
        except Exception as e:
            msg  = str(e)
            code = getattr(e, "status_code", 0) or getattr(e, "code", 0) or 0
            # Detect 1011 (internal server error) regardless of exception type
            if code == 1011 or "1011" in msg or "Internal error" in msg:
                tool_info = f" durante '{_last_tool}'" if _last_tool else ""
                print(f"[NEXUS] ⚡ API 1011{tool_info} — reconectando...")
                self._api_1011_tool = _last_tool
            else:
                print(f"[NEXUS] ❌ Recv: {e}")
                traceback.print_exc()
            raise

    async def _play_audio(self):
        print("[NEXUS] 🔊 Play iniciado")

        stream = sd.RawOutputStream(
            samplerate=RECEIVE_SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=PLAY_CHUNK_SIZE,
        )
        self._audio_out_stream = stream
        stream.start()

        # Jitter buffer: accumulate a few chunks before playback to prevent underruns
        _jitter_buf: list[bytes] = []
        _JITTER_TARGET = 1  # ~20ms — start playback ASAP for low latency

        try:
            while True:
                if self._stop_requested.is_set():
                    _jitter_buf.clear()
                    while not self.audio_in_queue.empty():
                        try:
                            self.audio_in_queue.get_nowait()
                        except Exception:
                            break
                    self.set_speaking(False)
                    await asyncio.sleep(0.01)
                    continue

                try:
                    chunk = await asyncio.wait_for(
                        self.audio_in_queue.get(),
                        timeout=0.05   # 50ms — faster turn-complete detection
                    )
                except asyncio.TimeoutError:
                    if self._stop_requested.is_set():
                        _jitter_buf.clear()
                        self.set_speaking(False)
                        continue
                    # Must check turn_done + empty BEFORE jitter guard,
                    # otherwise 1-2 stuck chunks in jitter_buf prevent
                    # ever reaching the turn_done check → infinite SPEAKING loop.
                    if (
                        self._turn_done_event
                        and self._turn_done_event.is_set()
                        and self.audio_in_queue.empty()
                        and getattr(self, "active_tts_tasks_count", 0) == 0
                    ):
                        # Drain remaining jitter buffer before stopping
                        for buffered in _jitter_buf:
                            if self._stop_requested.is_set():
                                break
                            try:
                                await asyncio.to_thread(stream.write, buffered)
                            except Exception as write_err:
                                print(f"[NEXUS] Stream write ignored: {write_err}")
                        _jitter_buf.clear()
                        self.set_speaking(False)
                        self._turn_done_event.clear()
                    continue

                if self._stop_requested.is_set():
                    _jitter_buf.clear()
                    self.set_speaking(False)
                    continue

                self.set_speaking(True)
                _jitter_buf.append(chunk)

                # Once we have enough chunks buffered, drain them to the output stream
                if len(_jitter_buf) >= _JITTER_TARGET:
                    if self._stop_requested.is_set():
                        _jitter_buf.clear()
                    else:
                        for buffered in _jitter_buf:
                            if self._stop_requested.is_set():
                                break
                            try:
                                await asyncio.to_thread(stream.write, buffered)
                            except Exception as write_err:
                                print(f"[NEXUS] Stream write ignored: {write_err}")
                        _jitter_buf.clear()
        except Exception as e:
            print(f"[NEXUS] ❌ Play: {e}")
            raise
        finally:
            self.set_speaking(False)
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
            self._audio_out_stream = None

    async def run(self):
        # ── VERIFICACIÓN DE INTEGRIDAD EN CALIENTE (LOOP ASÍNCRONO) ────────
        from hashlib import sha256
        import drm_manager
        import sys
        global _session_drm_token
        
        _main_mod = sys.modules.get("main") or sys.modules.get("__main__")
        _key_to_check = getattr(_main_mod, "_verified_license_key", "")
        if not _key_to_check:
            _lic_file = Path(__file__).resolve().parent / "config" / "license.json"
            if _lic_file.exists():
                try:
                    _key_to_check = json.loads(_lic_file.read_text(encoding="utf-8")).get("license_key", "")
                except:
                    pass
        
        expected_token = sha256(f"{_key_to_check}:{drm_manager.get_hwid()}:NEXUS_AI_SECURE_SALT_2026".encode()).hexdigest() if _key_to_check else ""
        if not expected_token or _session_drm_token != expected_token:
            print("[DRM Security] Violación de integridad del loop de IA. Bloqueado.")
            os._exit(0)
        # ──────────────────────────────────────────────────────────────────

        client = genai.Client(
            api_key=_get_api_key(),
            http_options={"api_version": "v1beta"}
        )

        reconnect_delay   = 1.0
        consecutive_fails = 0

        while True:
            try:
                print("[NEXUS] 🔌 Conectando...")
                self.ui.set_state("THINKING")
                config = self._build_config()

                async with (
                    client.aio.live.connect(model=LIVE_MODEL, config=config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session          = session
                    self._loop            = asyncio.get_event_loop()
                    self.audio_in_queue   = asyncio.Queue()
                    self.out_queue        = asyncio.Queue(maxsize=5)  # buffer moderado — evita drops durante ráfagas de mic
                    self._turn_done_event = asyncio.Event()
                    self._reconnect_event = asyncio.Event()

                    print("[NEXUS] ✅ Conectado.")
                    if getattr(self, "is_sleeping", False):
                        self.ui.set_state("MUTED")
                        self.ui.write_log("SYS: NEXUS en línea (Suspendido).")
                    else:
                        self.ui.set_state("LISTENING")
                        self.ui.write_log("SYS: NEXUS en línea.")
                    reconnect_delay   = 1.0   # reset backoff on successful connection
                    consecutive_fails = 0
                    self._api_1011_tool = None   # clear 1011 tool tracker

                    # ── First-connect extras ──────────────────────────────────
                    if self._first_connect:
                        self._first_connect = False
                        
                        threading.Thread(target=lambda: self.speak("Sistemas en línea. A sus órdenes."), daemon=True).start()
                        
                        # Start Vision Guardian if enabled
                        try:
                            _start_vision_guardian(
                                inject_fn=self._inject_text,
                                speaking_fn=lambda: self._is_speaking,
                            )
                        except Exception as _vge:
                            print(f"[NEXUS] VisionGuardian init error: {_vge}")
                        # Auto morning brief (6am–12pm, once per day)
                        _hour = __import__("datetime").datetime.now().hour
                        if 6 <= _hour < 12 and not already_briefed_today():
                            async def _auto_brief():
                                await asyncio.sleep(1)  # let session settle
                                _load_tz()
                                now_b = __import__("datetime").datetime.now(_BA_TZ)
                                current_time = now_b.strftime("%I:%M %p")
                                current_date = now_b.strftime("%A, %d de %B de %Y")
                                await self.session.send_client_content(
                                    turns={"parts": [{"text": f"[AUTO] Son exactamente las {current_time} del {current_date}. Dame el informe matutino del día."}]},
                                    turn_complete=True
                                )
                                from actions.morning_brief import mark_briefed
                                mark_briefed()
                            tg.create_task(_auto_brief())

                    tg.create_task(self._send_realtime())
                    tg.create_task(self._listen_audio())
                    tg.create_task(self._receive_audio())
                    tg.create_task(self._play_audio())
                    tg.create_task(self._watch_reconnect())

            except Exception as e:
                exceptions = e.exceptions if isinstance(e, ExceptionGroup) else [e]

                is_handshake_timeout = False
                is_config_reconnect  = False
                for exc in exceptions:
                    msg = str(exc)
                    if "Config changed" in msg:
                        # Intentional reconnect triggered by config change — fast, no backoff
                        is_config_reconnect = True
                        consecutive_fails = 0
                    elif "timed out during opening handshake" in msg or (
                        isinstance(exc, TimeoutError) and "handshake" in msg
                    ):
                        # Timeout de WebSocket al conectar — error de red transitorio.
                        # NO incrementar consecutive_fails: sólo reintento rápido.
                        is_handshake_timeout = True
                        print(f"[NEXUS] ⏱️ Timeout al conectar — reintentando en 1s...")
                    elif "1011" in msg or "Internal error" in msg:
                        tool_hint = self._api_1011_tool or ""
                        print(f"[NEXUS] ⚡ API 1011{tool_hint and ' durante '+tool_hint} — reconectando...")
                        consecutive_fails += 1
                        if consecutive_fails >= 4:
                            self.ui.write_log(
                                "SYS: ⚠️ Error 1011 repetido. Esperando para no saturar la API...\n"
                                "SYS: Si persiste más de 2 min, reiniciá NEXUS."
                            )
                        elif tool_hint:
                            self.ui.write_log(f"SYS: Error de servidor al ejecutar '{tool_hint}'. Reconectando...")
                        else:
                            self.ui.write_log("SYS: Error de servidor 1011. Reconectando...")
                    elif "1008" in msg or "policy violation" in msg.lower() or "not found for API version" in msg:
                        # Model not available / wrong API version — log clearly, retry with same model
                        print(f"[NEXUS] ⚠️ Modelo no disponible en esta versión de API: {msg[:120]}")
                        self.ui.write_log("SYS: ⚠️ Modelo no disponible. Reintentando...")
                        consecutive_fails += 1
                    elif "1000" in msg or "going away" in msg.lower():
                        # Cierre normal de la sesión (expiró ~15 min) — silencioso
                        print(f"[NEXUS] 🔄 Sesión expirada — reconectando...")
                        consecutive_fails = 0   # reset: no es un fallo
                    else:
                        print(f"[NEXUS] ⚠️ {exc}")
                        traceback.print_exc()
                        consecutive_fails += 1

                if is_config_reconnect:
                    self.set_speaking(False)
                    self.ui.set_state("THINKING")
                    await asyncio.sleep(0.5)
                    continue

                if is_handshake_timeout:
                    # Timeout en handshake → reintento fijo de 1s, sin backoff
                    self.set_speaking(False)
                    self.ui.set_state("THINKING")
                    await asyncio.sleep(1.0)
                    continue

            self.set_speaking(False)
            self.ui.set_state("THINKING")

            # Exponential backoff con jitter para evitar thundering herd
            # Reducido el retraso de reconexión máximo a 10s (antes 90s) para volver en línea al instante
            if consecutive_fails > 1:
                max_delay = 10.0 if consecutive_fails >= 5 else 6.0
                reconnect_delay = min(reconnect_delay * 2, max_delay)
            elif consecutive_fails == 0:
                reconnect_delay = 1.0

            import random as _rnd
            jitter = _rnd.uniform(0, reconnect_delay * 0.25)
            total  = reconnect_delay + jitter
            print(f"[NEXUS] 🔄 Reconectando en {total:.1f}s...")
            await asyncio.sleep(total)

def main():
    global _verified_license_key, _session_drm_token

    import sys
    # ── Single Instance Lock ──────────────────────────────────────────────────
    import ctypes
    _single_instance_mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "NEXUS_AI_SINGLE_INSTANCE_MUTEX")
    if ctypes.windll.kernel32.GetLastError() == 183: # ERROR_ALREADY_EXISTS
        print("[NEXUS] Ya hay una instancia en ejecución. Cerrando.")
        try:
            hwnd = ctypes.windll.user32.FindWindowW(None, "NEXUS-AI-HUD")
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception as e:
            print(f"[NEXUS] Error al restaurar la ventana activa: {e}")
        sys.exit(0)

    # ── Admin validation ──────────────────────────────────────────────────────
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        is_admin = False
    if not is_admin:
        print("[NEXUS] ⚠️ ADVERTENCIA: No se está ejecutando con privilegios de Administrador.")
        print("[NEXUS] ⚠️ Algunas funciones de control del PC o de terminal podrían fallar.")
        print("[NEXUS] ⚠️ Se recomienda iniciar NEXUS mediante 'Iniciar NEXUS Beta.vbs'.")

    # ── License check ─────────────────────────────────────────────────────────
    # ──────────────────────────────────────────────────────────────────────────

    # Load timezone from config
    _load_tz()

    def _ensure_both_api_keys():
        cfg = {}
        if API_CONFIG_PATH.exists():
            try:
                cfg = json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass
        
        gemini = cfg.get("gemini_api_key", "").strip()
        openrouter = cfg.get("openrouter_api_key", "").strip()
        ai_provider = cfg.get("ai_provider", "gemini").strip()
        
        # If Ollama is the active provider, or if we have at least one cloud key set, we are safe to start
        if ai_provider == "ollama" or gemini or openrouter:
            return
            
        from PyQt6.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
        from PyQt6.QtCore import Qt, QTimer
        
        # We need an app instance before dialogs
        app = QApplication.instance() or QApplication(sys.argv)
        
        dialog = QDialog()
        dialog.setWindowTitle("Configuración Inicial de NEXUS")
        dialog.resize(450, 250)
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        layout = QVBoxLayout(dialog)
        
        lbl_info = QLabel("¡Bienvenido a NEXUS!\n\nPor favor, ingresa tus API keys o selecciona Ollama en la configuración.\nEstas se guardarán localmente y de forma segura.")
        lbl_info.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(lbl_info)
        
        lbl_gemini = QLabel("Gemini API Key:")
        layout.addWidget(lbl_gemini)
        inp_gemini = QLineEdit()
        inp_gemini.setText(gemini)
        inp_gemini.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(inp_gemini)
        
        lbl_openrouter = QLabel("OpenRouter API Key (Opcional):")
        layout.addWidget(lbl_openrouter)
        inp_openrouter = QLineEdit()
        inp_openrouter.setText(openrouter)
        inp_openrouter.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(inp_openrouter)
        
        btn_save = QPushButton("Guardar y Continuar")
        btn_save.setStyleSheet("background-color: #0078D7; color: white; border: 1.5px solid #0078D7; font-weight: bold; padding: 8px; border-radius: 4px;")
        layout.addWidget(btn_save)
        
        def on_save():
            g = inp_gemini.text().strip()
            o = inp_openrouter.text().strip()
            if not g and not o:
                QMessageBox.warning(dialog, "Error", "Debe proporcionar al menos una API Key de Gemini.")
                return
            cfg["gemini_api_key"] = g
            cfg["openrouter_api_key"] = o
            API_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            API_CONFIG_PATH.write_text(json.dumps(cfg, indent=4), encoding="utf-8")
            dialog.accept()
            
        btn_save.clicked.connect(on_save)
        
        def focus_dialog():
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()

        QTimer.singleShot(0, focus_dialog)
        result = dialog.exec()
        if result != QDialog.DialogCode.Accepted:
            sys.exit(0)

    _ensure_both_api_keys()

    # Smart User Name Verification for First-Time Setup
    def _ensure_user_name():
        cfg = {}
        if API_CONFIG_PATH.exists():
            try:
                cfg = json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass
        
        user_name = cfg.get("user_name", "").strip()
        if user_name:
            return

        cfg["user_name"] = "Señor"
        API_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        API_CONFIG_PATH.write_text(json.dumps(cfg, indent=4), encoding="utf-8")
        return
             
        from PyQt6.QtWidgets import QApplication, QInputDialog
        # We need app instance before dialogs
        app = QApplication.instance() or QApplication(sys.argv)
        
        name, ok = QInputDialog.getText(
            None, 
            "Configuración Inicial - NEXUS", 
            "¿Cómo desea que lo llame, señor?", 
            text="Señor"
        )
        if ok and name.strip():
            cfg["user_name"] = name.strip()
        else:
            cfg["user_name"] = "Señor"
            
        API_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        API_CONFIG_PATH.write_text(json.dumps(cfg, indent=4), encoding="utf-8")

    _ensure_user_name()
    
    # --- ANTI-DEBUGGING ---
    import ctypes
    import sys
    if sys.platform == "win32" and ctypes.windll.kernel32.IsDebuggerPresent():
        sys.exit(1)
        
    
    # --- DYNAMIC FONT REGISTRATION ---
    from PyQt6.QtWidgets import QApplication
    import sys
    
    # --- RAM OPTIMIZATION FLAGS (Chromium WebEngine) ---
    sys.argv.extend([
        "--disable-gpu", 
        "--renderer-process-limit=1",
        "--single-process",
        "--js-flags=--max-old-space-size=64",
        "--disable-plugins",
        "--disable-extensions"
    ])
    
    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    # --- LICENSING INTERCEPTOR ---
    import drm_manager
    from pathlib import Path
    from hashlib import sha256
    
    _license_file = Path(__file__).resolve().parent / "config" / "license.json"
    _local_key = ""
    if _license_file.exists():
        try:
            _lic_data = json.loads(_license_file.read_text(encoding="utf-8"))
            _local_key = _lic_data.get("license_key", "")
        except:
            pass
            
    _is_licensed = False
    if _local_key:
        _res = drm_manager.validate_license(_local_key)
        if _res.get("success"):
            _is_licensed = True
            _verified_license_key = _local_key
            _session_drm_token = sha256(f"{_local_key}:{drm_manager.get_hwid()}:NEXUS_AI_SECURE_SALT_2026".encode()).hexdigest()
            
            # --- AUTO-UPDATE CHECK FOR SILENT STARTUP ---
            try:
                _update_check = drm_manager.check_for_updates("1.0.4")
                if _update_check.get("update_available"):
                    _url = _update_check.get("url")
                    _target = "ui.py"
                    if _url.endswith(".py"):
                        _target = _url.split("/")[-1]
                    print(f"[DRM Update] Descargando actualización silenciosa de {_target}...")
                    drm_manager.download_and_apply_patch(_url, _target)
                    print("[DRM Update] Actualización silenciosa aplicada con éxito.")
            except Exception as _ue:
                print(f"[DRM Update] Error al comprobar actualización silenciosa: {_ue}")
            
    if not _is_licensed:
        from login import LoginWindow
        _login_success = False
        _verified_key_temp = ""
        _aes_token_temp = ""
        
        class _LauncherSignal:
            def on_login_success(self, verified_key, aes_token=""):
                nonlocal _login_success, _verified_key_temp, _aes_token_temp
                _login_success = True
                _verified_key_temp = verified_key
                _aes_token_temp = aes_token
                
        _launcher = _LauncherSignal()
        _login_win = LoginWindow(parent_launcher=_launcher)
        _login_win.exec() # Block using dialog event loop
        
        if not _login_success or not _verified_key_temp or not _aes_token_temp:
            import os
            os._exit(0)
            
        # Generar token de sesión tras login exitoso vinculado al AES TOKEN
        _verified_license_key = _verified_key_temp
        _session_drm_token = sha256(f"{_verified_key_temp}:{drm_manager.get_hwid()}:NEXUS_AI_SECURE_SALT_2026".encode()).hexdigest()
    
    from PyQt6.QtGui import QFontDatabase
    from memory.config_manager import BASE_DIR
    import glob
    import os
    
    loaded_custom_fonts = []
    for ext in ["*.ttf", "*.otf"]:
        for font_file in BASE_DIR.glob(ext):
            font_id = QFontDatabase.addApplicationFont(str(font_file))
            if font_id != -1:
                family = QFontDatabase.applicationFontFamilies(font_id)[0]
                loaded_custom_fonts.append(family)

    ui = NexusUI("face.png")
    ui.loaded_custom_fonts = loaded_custom_fonts

    # --- START BACKGROUND LICENSE GUARDIAN ---
    try:
        def _start_license_guardian(ui_instance):
            from PyQt6.QtCore import QTimer
            import drm_manager
            import json
            from hashlib import sha256
            
            def _check_bg():
                global _session_drm_token
                import sys
                _main_mod = sys.modules.get("main") or sys.modules.get("__main__")
                _key = getattr(_main_mod, "_verified_license_key", "")
                if not _key:
                    _chk_file = Path(__file__).resolve().parent / "config" / "license.json"
                    if _chk_file.exists():
                        try:
                            _chk_data = json.loads(_chk_file.read_text(encoding="utf-8"))
                            _key = _chk_data.get("license_key", "")
                        except:
                            pass
                
                _valid = False
                _msg = "Clave de licencia no encontrada."
                _days_remaining = None
                if _key:
                    _res = drm_manager.validate_license(_key)
                    _valid = _res.get("success", False)
                    _msg = _res.get("message", "Licencia inválida.")
                    _days_remaining = _res.get("days_remaining")
                    
                if _valid:
                    # Renovar/Actualizar token de sesión DRM en caliente
                    _session_drm_token = sha256(f"{_key}:{drm_manager.get_hwid()}:NEXUS_AI_SECURE_SALT_2026".encode()).hexdigest()

                    # Refrescar days_remaining en el archivo local de licencia para que Ajustes lo muestre al día
                    if _days_remaining is not None:
                        try:
                            _lic_file = Path(__file__).resolve().parent / "config" / "license.json"
                            if _lic_file.exists():
                                _lic_data = json.loads(_lic_file.read_text(encoding="utf-8"))
                                _lic_data["days_remaining"] = _days_remaining
                                _lic_data["created_at"] = _res.get("created_at", _lic_data.get("created_at"))
                                _lic_file.write_text(json.dumps(_lic_data, indent=4), encoding="utf-8")
                        except Exception as _lw_err:
                            print(f"[DRM Guardian] No se pudo refrescar license.json: {_lw_err}")
                else:
                    _session_drm_token = None
                    print(f"[DRM Guardian] Licencia INVALIDADA: {_msg}")
                    from PyQt6.QtWidgets import QMessageBox
                    _msg_box = QMessageBox(ui_instance._win)
                    _msg_box.setWindowTitle(" NEXUS Security")
                    _msg_box.setText(f"La licencia de NEXUS ha sido revocada o inhabilitada:\n\n{_msg}")
                    _msg_box.setIcon(QMessageBox.Icon.Critical)
                    _msg_box.exec()
                    import os
                    os._exit(0)

            # Check 5 seconds after startup, then every 5 minutes (300,000ms)
            QTimer.singleShot(5000, _check_bg)
            _timer = QTimer(ui_instance._win)
            _timer.timeout.connect(_check_bg)
            _timer.start(300000)
            
        if hasattr(ui, "_win"):
            _start_license_guardian(ui)
    except Exception as _ge:
        print(f"[DRM Guardian] Error initializing licensing background loop: {_ge}")

    # --- UI COSMETICS PATCH ---
    try:
        if hasattr(ui, "_win"):
            # Aumentar transparencia (Glassmorphism)
            ui._win.setWindowOpacity(0.85)
            # Reemplazar textos "Beta" y "Gratuito"
            from PyQt6.QtWidgets import QLabel
            for label in ui._win.findChildren(QLabel):
                text_lower = label.text().lower()
                if "beta" in text_lower or "gratuita" in text_lower or "gratuito" in text_lower or "premium" in text_lower:
                    try:
                        # Ocultar el contenedor completo del banner (incluye el botón PRO)
                        label.parentWidget().hide()
                    except:
                        label.hide()

            # 2. Add keyboard shortcut & Global Hotkey (INS / Insert key) to wake up NEXUS
            from PyQt6.QtGui import QKeySequence, QShortcut
            from PyQt6.QtCore import Qt, QTimer

            def on_shortcut_triggered():
                # Wake up / unmute NEXUS
                if hasattr(ui, "_win"):
                    # Si está muteado, desmutearlo para que escuche
                    if getattr(ui, "muted", False):
                        if hasattr(ui._win, "_toggle_mute"):
                            ui._win._toggle_mute()
                            ui.write_log("SYS: 🎤 Micrófono ACTIVADO vía atajo INS.")
                    else:
                        # Si ya está activo, mostrar/restaurar la ventana principal y enfocarla
                        if hasattr(ui._win, "showNormal"):
                            ui._win.showNormal()
                            ui._win.activateWindow()
                            ui.write_log("SYS: 🔔 NEXUS en foco vía atajo INS.")
                        
                        # Cambiar estado visual a escuchando
                        try:
                            ui.set_state("LISTENING")
                        except:
                            pass

            # A. PyQt Window Shortcut (for local window events)
            local_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Insert), ui._win)
            local_shortcut.activated.connect(on_shortcut_triggered)

            # B. Win32 Native Global Hotkey Hook (for background capture)
            def setup_global_hotkey():
                import threading
                import ctypes
                import ctypes.wintypes

                def hotkey_thread():
                    user32 = ctypes.windll.user32
                    # MOD_NOREPEAT = 0x4000
                    # VK_INSERT = 0x2D
                    try:
                        if not user32.RegisterHotKey(None, 99, 0x0000, 0x2D):
                            print("[HOTKEY] Error registering global Insert hotkey.")
                            return
                    except Exception as e:
                        print(f"[HOTKEY] Exception registering global hotkey: {e}")
                        return

                    try:
                        msg = ctypes.wintypes.MSG()
                        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                            if msg.message == 0x0312: # WM_HOTKEY
                                if msg.wParam == 99:
                                    # Thread-safely trigger UI callback inside PyQt event loop
                                    QTimer.singleShot(0, on_shortcut_triggered)
                            user32.TranslateMessage(ctypes.byref(msg))
                            user32.DispatchMessageW(ctypes.byref(msg))
                    finally:
                        user32.UnregisterHotKey(None, 99)

                threading.Thread(target=hotkey_thread, daemon=True).start()

            setup_global_hotkey()
            print("[PATCH] Avengers: Age of Ultron golden aesthetics & Insert global hotkey loaded successfully!")

    except Exception as e:
        print(f"[PATCH] Cosmetics & Shortcut patch failed: {e}")

    def runner():
        ui.wait_for_api_key()
        nexus = NexusLive(ui)
        try:
            asyncio.run(nexus.run())
        except KeyboardInterrupt:
            print("\n🔴 Apagando...")

    threading.Thread(target=runner, daemon=True).start()
    ui.root.mainloop()

    # Terminación forzada a nivel de sistema operativo para liberar handles de cámara,
    # micrófono, sockets y el mutex de instancia única al instante sin esperas ni deadlocks
    import os
    os._exit(0)

if __name__ == "__main__":
    main()  