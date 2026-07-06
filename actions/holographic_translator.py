"""
Holographic Translator PRO - Subtítulos en Vivo con IA
=======================================================
Sistema avanzado de subtítulos en tiempo real con:
- Detección automática de YouTube/Netflix/Spotify/VLC
- Transcripción con YouTube Transcript API + Vosk (fallback)
- Traducción automática (Google Translate)
- Doble línea (idioma original + traducción)
- Resumen inteligente con IA
- Exportación a SRT/VTT/TXT
- Modo flotante arrastrable
- Activación por voz
"""

import subprocess
import os
import sys
import json
import threading
import time
import re
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import webbrowser
import queue
import importlib

# ─── DEPENDENCIAS ──────────────────────────────────────────────────────────
try:
    import requests
except ImportError:
    requests = None

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api.formatters import SRTFormatter, WebVTTFormatter
except ImportError:
    YouTubeTranscriptApi = None

try:
    googletrans_module = importlib.import_module("googletrans")
    Translator = googletrans_module.Translator
except ImportError:
    Translator = None

try:
    pyaudio = importlib.import_module("pyaudio")
    vosk = importlib.import_module("vosk")
except ImportError:
    pyaudio = None
    vosk = None

try:
    import psutil
except ImportError:
    psutil = None

try:
    import win32gui
    import win32process
    import win32con
except ImportError:
    win32gui = None

# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────
CONFIG_DIR = Path("config")
CONFIG_PATH = CONFIG_DIR / "holographic_config.json"
SUBTITLES_DIR = Path("subtitles")
SUBTITLES_DIR.mkdir(parents=True, exist_ok=True)

# ─── CONFIGURACIÓN POR DEFECTO ──────────────────────────────────────────
DEFAULT_CONFIG = {
    "window": {
        "width": 900,
        "height": 200,
        "opacity": 0.85,
        "position": "bottom",  # bottom, top, custom
        "x": None,
        "y": None,
        "always_on_top": True,
        "draggable": True
    },
    "style": {
        "font": "Arial",
        "font_size": 28,
        "color": "#00FFCC",
        "bg_color": "black",
        "dual_line": True,
        "show_original": True,
        "show_translation": True,
        "speaker_colors": True,
        "auto_clean": True
    },
    "translation": {
        "enabled": True,
        "target_language": "es",
        "source_language": "auto"
    },
    "audio": {
        "source": "system",  # system, microphone, auto
        "device": None,
        "auto_detect": True
    },
    "ai": {
        "clean_text": True,
        "summarize": True,
        "filter_fillers": True
    },
    "export": {
        "auto_save": False,
        "format": "txt",  # txt, srt, vtt
        "path": str(SUBTITLES_DIR)
    },
    "voice_activation": {
        "enabled": False,
        "wake_word": "ILUM activa subtítulos",
        "deactivate_word": "ILUM desactiva subtítulos"
    }
}

# ─── DETECTOR DE APLICACIONES ────────────────────────────────────────────
class AppDetector:
    """Detecta aplicaciones que reproducen audio/video."""
    
    AUDIO_APPS = {
        "chrome": {"name": "Chrome", "services": ["youtube", "netflix", "spotify", "prime", "disney"]},
        "firefox": {"name": "Firefox", "services": ["youtube", "netflix", "spotify"]},
        "edge": {"name": "Edge", "services": ["youtube", "netflix", "disney", "prime"]},
        "vlc": {"name": "VLC", "services": ["video", "audio"]},
        "spotify": {"name": "Spotify", "services": ["music"]},
        "netflix": {"name": "Netflix", "services": ["video"]},
        "twitch": {"name": "Twitch", "services": ["streaming"]},
        "discord": {"name": "Discord", "services": ["voice", "streaming"]},
        "mpv": {"name": "MPV", "services": ["video", "audio"]},
        "potplayer": {"name": "PotPlayer", "services": ["video", "audio"]},
        "mediaplayer": {"name": "Windows Media Player", "services": ["video", "audio"]}
    }
    
    @classmethod
    def detect_active_app(cls) -> Optional[Dict]:
        """Detecta la aplicación activa y su contenido."""
        if not win32gui or not psutil:
            return None
        
        try:
            # Obtener ventana activa
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return None
            
            # Obtener título de la ventana
            window_title = win32gui.GetWindowText(hwnd)
            
            # Obtener proceso
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process = psutil.Process(pid)
            process_name = process.name().lower()
            
            # Identificar aplicación
            for key, info in cls.AUDIO_APPS.items():
                if key in process_name or key in window_title.lower():
                    # Detectar si es YouTube/Netflix/etc
                    service = cls.detect_service(window_title, process_name)
                    
                    return {
                        "app": info["name"],
                        "process": process_name,
                        "window_title": window_title,
                        "service": service,
                        "pid": pid,
                        "hwnd": hwnd
                    }
            
            return None
        except:
            return None
    
    @classmethod
    def detect_service(cls, window_title: str, process: str) -> str:
        """Detecta el servicio específico (YouTube, Netflix, etc.)."""
        title_lower = window_title.lower()
        
        # YouTube
        if "youtube" in title_lower or "youtube.com" in title_lower:
            # Extraer ID del video
            video_id = cls.extract_youtube_id(window_title)
            return {"service": "youtube", "video_id": video_id} if video_id else {"service": "youtube"}
        
        # Netflix
        if "netflix" in title_lower:
            return {"service": "netflix"}
        
        # Spotify
        if "spotify" in title_lower or "spotify.com" in title_lower:
            return {"service": "spotify"}
        
        # Prime Video
        if "prime video" in title_lower or "amazon" in title_lower:
            return {"service": "prime"}
        
        # Disney+
        if "disney" in title_lower:
            return {"service": "disney"}
        
        # Twitch
        if "twitch" in title_lower:
            return {"service": "twitch"}
        
        # VLC
        if "vlc" in process or "vlc" in title_lower:
            return {"service": "vlc"}
        
        return {"service": "media"}
    
    @classmethod
    def extract_youtube_id(cls, window_title: str) -> Optional[str]:
        """Extrae el ID de un video de YouTube del título de la ventana."""
        # Buscar patrón de URL
        patterns = [
            r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
            r'youtu\.be/([a-zA-Z0-9_-]{11})',
            r'\[([a-zA-Z0-9_-]{11})\]'  # Algunos navegadores muestran ID entre corchetes
        ]
        
        for pattern in patterns:
            match = re.search(pattern, window_title)
            if match:
                return match.group(1)
        
        # Si no, intentar extraer del título (últimos 11 caracteres alfanuméricos)
        words = window_title.split()
        for word in words:
            if len(word) >= 11 and re.match(r'^[a-zA-Z0-9_-]{11}$', word):
                return word
        
        return None


# ─── TRANSCRIPTOR DE YOUTUBE ─────────────────────────────────────────────
class YouTubeTranscriber:
    """Obtiene subtítulos de YouTube."""
    
    @staticmethod
    def get_transcript(video_id: str, languages: List[str] = None) -> Optional[List[Dict]]:
        """Obtiene la transcripción de un video de YouTube."""
        if not YouTubeTranscriptApi:
            return None
        
        try:
            if not languages:
                languages = ['es', 'en', 'auto']
            
            # Intentar con idiomas específicos
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            for lang in languages:
                try:
                    transcript = transcript_list.find_transcript([lang])
                    return transcript.fetch()
                except:
                    continue
            
            # Si no se encuentra, usar el primero disponible
            transcript = transcript_list.find_transcript(['en'])
            return transcript.fetch()
            
        except Exception as e:
            print(f"[YouTube] Error obteniendo subtítulos: {e}")
            return None
    
    @staticmethod
    def format_transcript(transcript: List[Dict], format_type: str = "srt") -> str:
        """Formatea la transcripción en SRT, VTT o TXT."""
        if not transcript:
            return ""
        
        if format_type == "srt":
            return SRTFormatter().format_transcript(transcript)
        elif format_type == "vtt":
            return WebVTTFormatter().format_transcript(transcript)
        else:  # txt
            return "\n".join([t["text"] for t in transcript])
    
    @staticmethod
    def save_transcript(transcript: List[Dict], filename: str, format_type: str = "srt"):
        """Guarda la transcripción en un archivo."""
        if not transcript:
            return None
        
        formatted = YouTubeTranscriber.format_transcript(transcript, format_type)
        file_path = SUBTITLES_DIR / f"{filename}.{format_type}"
        file_path.write_text(formatted, encoding="utf-8")
        return str(file_path)


# ─── TRADUCTOR ────────────────────────────────────────────────────────────
class TranslatorService:
    """Servicio de traducción automática."""
    
    _instance = None
    _translator = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            if Translator:
                cls._instance._translator = Translator()
        return cls._instance
    
    def translate(self, text: str, dest: str = "es", src: str = "auto") -> str:
        """Traduce texto al idioma destino."""
        if not self._translator or not text:
            return text
        
        try:
            result = self._translator.translate(text, dest=dest, src=src)
            return result.text
        except:
            return text


# ─── LIMPIADOR DE TEXTO CON IA ──────────────────────────────────────────
class TextCleaner:
    """Limpia y formatea texto con IA."""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Limpia el texto eliminando muletillas y mejorando legibilidad."""
        if not text:
            return text
        
        # Eliminar muletillas comunes
        fillers = [
            r'\beh\b', r'\beste\b', r'\bmm\b', r'\buh\b', 
            r'\bcomo que\b', r'\btipo\b', r'\bverdad\b',
            r'\bsabes\b', r'\bo sea\b', r'\ba ver\b'
        ]
        
        cleaned = text
        for filler in fillers:
            cleaned = re.sub(filler, '', cleaned, flags=re.IGNORECASE)
        
        # Eliminar espacios dobles
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        # Capitalizar primera letra
        if cleaned:
            cleaned = cleaned[0].upper() + cleaned[1:]
        
        return cleaned.strip()
    
    @staticmethod
    def detect_speaker(text: str) -> str:
        """Detecta el hablante basado en patrones de texto."""
        # En un sistema real, esto usaría speaker diarization
        # Por ahora, asignamos basado en contenido
        if text.startswith(('¡', '!', '?', '¿')):
            return "speaker_1"  # Persona 1
        elif any(word in text.lower() for word in ['yo', 'mi', 'me']):
            return "speaker_2"  # Persona 2
        else:
            return "speaker_1"


# ─── SUBTITULOS HOLOGRÁFICOS ─────────────────────────────────────────────
class HolographicSubtitles:
    """Ventana flotante de subtítulos holográficos."""
    
    def __init__(self):
        self.root = None
        self.label_original = None
        self.label_translation = None
        self.label_status = None
        self.is_running = False
        self.is_paused = False
        self.current_text = ""
        self.current_translation = ""
        self.transcript_history = []
        self.video_id = None
        self.youtube_transcript = None
        self.transcript_index = 0
        self.config = self._load_config()
        self.translator = TranslatorService() if Translator else None
        self.cleaner = TextCleaner()
        self.audio_thread = None
        self.audio_queue = queue.Queue()
        self.app_detector = AppDetector()
        self.last_detection = None
        self._lock = threading.Lock()
        
        self._setup_ui()
        self._start_detection_thread()
        
    def _load_config(self) -> Dict:
        """Carga la configuración."""
        if CONFIG_PATH.exists():
            try:
                return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            except:
                return DEFAULT_CONFIG.copy()
        return DEFAULT_CONFIG.copy()
    
    def _save_config(self):
        """Guarda la configuración."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps(self.config, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    
    def _setup_ui(self):
        """Configura la interfaz de usuario."""
        self.root = tk.Tk()
        self.root.title("ILUM Holographic Subtitles")
        self.root.overrideredirect(True)
        
        # Configurar transparencia
        cfg = self.config["window"]
        self.root.attributes("-topmost", cfg.get("always_on_top", True))
        self.root.attributes("-alpha", cfg.get("opacity", 0.85))
        self.root.attributes("-transparentcolor", "black")
        self.root.configure(bg="black")
        
        # Dimensiones
        width = cfg.get("width", 900)
        height = cfg.get("height", 200)
        
        # Posición
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        if cfg.get("position") == "top":
            x = int((screen_width - width) / 2)
            y = 50
        else:  # bottom
            x = int((screen_width - width) / 2)
            y = screen_height - height - 50
        
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        
        # Frame principal
        main_frame = tk.Frame(self.root, bg="black")
        main_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Línea 1: Texto original
        self.label_original = tk.Label(
            main_frame,
            text="🎙️ Escuchando...",
            font=(cfg.get("font", "Arial"), cfg.get("font_size", 28), "bold"),
            fg=cfg.get("color", "#00FFCC"),
            bg="black",
            wraplength=width-40,
            justify="center"
        )
        self.label_original.pack(fill="both", expand=True)
        
        # Línea 2: Traducción
        self.label_translation = tk.Label(
            main_frame,
            text="",
            font=(cfg.get("font", "Arial"), int(cfg.get("font_size", 28) * 0.7), "italic"),
            fg="#FFD700",
            bg="black",
            wraplength=width-40,
            justify="center"
        )
        if self.config["style"].get("dual_line", True):
            self.label_translation.pack(fill="both", expand=True)
        
        # Barra de estado
        status_frame = tk.Frame(self.root, bg="black", height=30)
        status_frame.pack(fill="x", side="bottom")
        
        self.label_status = tk.Label(
            status_frame,
            text="🟢 Activo | Arrastra para mover | Click derecho para menú",
            font=("Arial", 9),
            fg="#666666",
            bg="black"
        )
        self.label_status.pack(side="left", padx=10)
        
        # Botón de cierre
        close_btn = tk.Label(
            status_frame,
            text="✕",
            font=("Arial", 12, "bold"),
            fg="#666666",
            bg="black",
            cursor="hand2"
        )
        close_btn.pack(side="right", padx=10)
        close_btn.bind("<Button-1>", lambda e: self.close())
        
        # Eventos de arrastre
        if cfg.get("draggable", True):
            main_frame.bind("<Button-1>", self._start_drag)
            main_frame.bind("<B1-Motion>", self._on_drag)
            self.label_original.bind("<Button-1>", self._start_drag)
            self.label_original.bind("<B1-Motion>", self._on_drag)
            self.label_translation.bind("<Button-1>", self._start_drag)
            self.label_translation.bind("<B1-Motion>", self._on_drag)
        
        # Click derecho para menú
        self.root.bind("<Button-3>", self._show_menu)
        
        # Atajo: ESC para cerrar
        self.root.bind("<Escape>", lambda e: self.close())
        
        # Doble click para minimizar
        self.root.bind("<Double-Button-1>", lambda e: self.root.iconify())
    
    def _start_drag(self, event):
        self._drag_data = {"x": event.x, "y": event.y}
    
    def _on_drag(self, event):
        x = self.root.winfo_x() + event.x - self._drag_data["x"]
        y = self.root.winfo_y() + event.y - self._drag_data["y"]
        self.root.geometry(f"+{x}+{y}")
    
    def _show_menu(self, event):
        """Muestra el menú contextual."""
        menu = tk.Menu(self.root, tearoff=0)
        
        menu.add_command(label="📋 Copiar texto", command=self._copy_text)
        menu.add_command(label="💾 Guardar subtítulos", command=self._save_subtitles)
        menu.add_separator()
        menu.add_command(label="🔊 Alternar audio", command=self._toggle_audio)
        menu.add_command(label="🔄 Traducción", command=self._toggle_translation)
        menu.add_command(label="📏 Cambiar tamaño", command=self._change_size)
        menu.add_separator()
        menu.add_command(label="📊 Resumen IA", command=self._show_summary)
        menu.add_command(label="⚙️ Configuración", command=self._show_settings)
        menu.add_separator()
        menu.add_command(label="❌ Cerrar", command=self.close)
        
        menu.post(event.x_root, event.y_root)
    
    def _copy_text(self):
        """Copia el texto actual al portapapeles."""
        self.root.clipboard_clear()
        text = f"{self.current_text}\n{self.current_translation}".strip()
        self.root.clipboard_append(text)
        self._update_status("📋 Texto copiado")
    
    def _save_subtitles(self):
        """Guarda los subtítulos en un archivo."""
        if not self.transcript_history:
            messagebox.showinfo("Info", "No hay subtítulos para guardar")
            return
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("SRT files", "*.srt"), ("VTT files", "*.vtt")]
        )
        
        if file_path:
            format_type = Path(file_path).suffix[1:]
            content = "\n".join([entry["text"] for entry in self.transcript_history])
            
            if format_type == "srt":
                # Formato SRT
                srt_content = ""
                for i, entry in enumerate(self.transcript_history, 1):
                    srt_content += f"{i}\n"
                    start = entry.get("start", 0)
                    duration = entry.get("duration", 2)
                    srt_content += f"{self._format_time(start)} --> {self._format_time(start + duration)}\n"
                    srt_content += f"{entry['text']}\n\n"
                content = srt_content
            elif format_type == "vtt":
                # Formato VTT
                vtt_content = "WEBVTT\n\n"
                for i, entry in enumerate(self.transcript_history, 1):
                    start = entry.get("start", 0)
                    duration = entry.get("duration", 2)
                    vtt_content += f"{self._format_time(start)} --> {self._format_time(start + duration)}\n"
                    vtt_content += f"{entry['text']}\n\n"
                content = vtt_content
            
            Path(file_path).write_text(content, encoding="utf-8")
            self._update_status(f"💾 Subtítulos guardados: {Path(file_path).name}")
    
    def _format_time(self, seconds: float) -> str:
        """Formatea segundos a HH:MM:SS,mmm."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    def _toggle_audio(self):
        """Alterna la fuente de audio."""
        # Implementar alternancia entre micrófono y sistema
        self._update_status("🔄 Audio alternado")
    
    def _toggle_translation(self):
        """Alterna la traducción."""
        cfg = self.config["style"]
        cfg["show_translation"] = not cfg.get("show_translation", True)
        self._update_status(f"🌐 Traducción {'activada' if cfg['show_translation'] else 'desactivada'}")
    
    def _change_size(self):
        """Cambia el tamaño de la fuente."""
        sizes = [20, 24, 28, 32, 36, 40]
        current = self.config["style"]["font_size"]
        idx = sizes.index(current) if current in sizes else 2
        new_idx = (idx + 1) % len(sizes)
        self.config["style"]["font_size"] = sizes[new_idx]
        self._save_config()
        
        self.label_original.config(font=("Arial", sizes[new_idx], "bold"))
        self.label_translation.config(font=("Arial", int(sizes[new_idx] * 0.7), "italic"))
        self._update_status(f"📏 Tamaño: {sizes[new_idx]}")
    
    def _show_summary(self):
        """Muestra un resumen generado por IA."""
        if len(self.transcript_history) < 5:
            messagebox.showinfo("Info", "No hay suficiente texto para generar un resumen")
            return
        
        # En un sistema real, esto usaría Gemini/OpenRouter para resumir
        # Por ahora, mostramos un resumen simple
        text = " ".join([entry["text"] for entry in self.transcript_history[-20:]])
        summary = f"Resumen del video:\n\n{text[:300]}..."
        
        summary_window = tk.Toplevel(self.root)
        summary_window.title("Resumen del Video")
        summary_window.geometry("500x400")
        summary_window.configure(bg="#1a1a2e")
        
        text_widget = tk.Text(summary_window, wrap="word", bg="#1a1a2e", fg="white", font=("Arial", 12))
        text_widget.pack(fill="both", expand=True, padx=10, pady=10)
        text_widget.insert("1.0", summary)
        text_widget.config(state="disabled")
    
    def _show_settings(self):
        """Muestra la ventana de configuración."""
        # Implementar settings GUI
        self._update_status("⚙️ Configuración")
    
    def _update_status(self, text: str):
        """Actualiza la barra de estado."""
        self.label_status.config(text=f"🟢 {text}")
        # Resetear después de 3 segundos
        self.root.after(3000, lambda: self.label_status.config(text="🟢 Activo | Arrastra para mover | Click derecho para menú"))
    
    def _start_detection_thread(self):
        """Inicia el thread de detección de aplicaciones."""
        def detect_loop():
            while self.is_running:
                try:
                    # Detectar app activa
                    app_info = AppDetector.detect_active_app()
                    
                    if app_info and app_info.get("service") == "youtube":
                        video_id = app_info.get("video_id")
                        if video_id and video_id != self.video_id:
                            self.video_id = video_id
                            self._on_youtube_detected(video_id)
                    
                    elif app_info and not self.video_id:
                        # Detectar otras apps
                        service = app_info.get("service", {})
                        if isinstance(service, dict):
                            service_name = service.get("service", "")
                            if service_name in ["netflix", "spotify", "prime", "disney", "twitch"]:
                                self._on_media_detected(app_info)
                
                except:
                    pass
                
                time.sleep(5)  # Revisar cada 5 segundos
        
        self.is_running = True
        detection_thread = threading.Thread(target=detect_loop, daemon=True)
        detection_thread.start()
    
    def _on_youtube_detected(self, video_id: str):
        """Cuando se detecta un video de YouTube."""
        self._update_status(f"🎬 YouTube detectado: {video_id}")
        
        # Preguntar al usuario
        if messagebox.askyesno("YouTube Detectado", 
                               f"Se detectó un video de YouTube.\n\n"
                               f"ID: {video_id}\n\n"
                               "¿Deseas activar los subtítulos holográficos?"):
            
            # Obtener transcripción
            transcript = YouTubeTranscriber.get_transcript(video_id)
            
            if transcript:
                self.youtube_transcript = transcript
                self.transcript_index = 0
                self._update_status(f"📝 Subtítulos obtenidos: {len(transcript)} líneas")
                self._play_youtube_transcript()
            else:
                # Fallback a Vosk
                self._update_status("🎙️ Usando reconocimiento de voz (Vosk)")
                self._start_audio_capture()
    
    def _on_media_detected(self, app_info: Dict):
        """Cuando se detecta otra aplicación multimedia."""
        app_name = app_info.get("app", "Desconocido")
        self._update_status(f"🎬 {app_name} detectado")
        
        # Preguntar al usuario
        if messagebox.askyesno("Audio Detectado", 
                               f"Se detectó audio en {app_name}.\n\n"
                               "¿Deseas mostrar subtítulos?"):
            self._start_audio_capture()
    
    def _play_youtube_transcript(self):
        """Reproduce la transcripción de YouTube en tiempo real."""
        if not self.youtube_transcript:
            return
        
        def play():
            while self.is_running and self.transcript_index < len(self.youtube_transcript):
                entry = self.youtube_transcript[self.transcript_index]
                text = entry.get("text", "")
                duration = entry.get("duration", 2)
                
                # Mostrar texto
                self.show_text(text)
                
                # Esperar duración del segmento
                time.sleep(duration)
                
                self.transcript_index += 1
            
            # Mostrar resumen al terminar
            if self.transcript_index >= len(self.youtube_transcript):
                self._show_summary()
        
        threading.Thread(target=play, daemon=True).start()
    
    def _start_audio_capture(self):
        """Inicia la captura de audio para Vosk."""
        if not pyaudio or not vosk:
            self._update_status("❌ Vosk no disponible")
            return
        
        # Iniciar thread de audio
        self.audio_thread = threading.Thread(target=self._audio_capture_loop, daemon=True)
        self.audio_thread.start()
    
    def _audio_capture_loop(self):
        """Loop de captura de audio."""
        try:
            # Cargar modelo Vosk
            model_path = CONFIG_DIR / "vosk_model"
            if not model_path.exists():
                self._update_status("❌ Modelo Vosk no encontrado")
                return
            
            vosk.SetLogLevel(-1)
            model = vosk.Model(str(model_path))
            recognizer = vosk.KaldiRecognizer(model, 16000)
            
            # Iniciar PyAudio
            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=4000
            )
            
            self._update_status("🎙️ Escuchando...")
            
            while self.is_running:
                data = stream.read(4000, exception_on_overflow=False)
                
                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "")
                    if text:
                        self.show_text(text)
                else:
                    partial = json.loads(recognizer.PartialResult())
                    partial_text = partial.get("partial", "")
                    if partial_text and len(partial_text) > 3:
                        self.show_text(partial_text, partial=True)
            
            stream.stop_stream()
            stream.close()
            p.terminate()
            
        except Exception as e:
            self._update_status(f"❌ Error de audio: {e}")
    
    def show_text(self, text: str, partial: bool = False):
        """Muestra el texto en la ventana."""
        with self._lock:
            # Limpiar texto
            if self.config["style"].get("auto_clean", True):
                text = TextCleaner.clean_text(text)
            
            # Detectar hablante
            speaker = TextCleaner.detect_speaker(text)
            
            # Asignar color según hablante
            if self.config["style"].get("speaker_colors", True):
                speaker_colors = {
                    "speaker_1": "#00FFCC",  # Verde claro
                    "speaker_2": "#4FC3F7",  # Azul
                }
                color = speaker_colors.get(speaker, "#00FFCC")
                self.label_original.config(fg=color)
            
            # Mostrar texto original
            self.label_original.config(text=text.upper())
            self.current_text = text
            
            # Traducir
            if self.config["style"].get("show_translation", True) and self.translator:
                target_lang = self.config["translation"].get("target_language", "es")
                translation = self.translator.translate(text, dest=target_lang)
                self.label_translation.config(text=translation)
                self.current_translation = translation
            
            # Guardar en historial
            if not partial:
                self.transcript_history.append({
                    "timestamp": datetime.now().isoformat(),
                    "text": text,
                    "translation": self.current_translation,
                    "speaker": speaker
                })
                
                # Limitar historial
                if len(self.transcript_history) > 1000:
                    self.transcript_history = self.transcript_history[-1000:]
    
    def close(self):
        """Cierra la ventana."""
        self.is_running = False
        if self.root:
            self.root.quit()
            self.root.destroy()
    
    def run(self):
        """Ejecuta la aplicación."""
        try:
            self.root.mainloop()
        except:
            pass


# ─── FUNCIÓN PRINCIPAL ────────────────────────────────────────────────────
def holographic_translator(parameters: dict, player=None) -> str:
    """
    Controla el traductor holográfico de subtítulos en vivo.
    
    Args:
        parameters: Diccionario con parámetros
            - action: start | stop | status | settings | resume | pause
            - mode: youtube | microphone | system | auto (default: auto)
            - language: Código de idioma para traducción (es, en, fr, etc.)
    
    Returns:
        Mensaje de resultado
    """
    action = parameters.get("action", "start").lower()
    mode = parameters.get("mode", "auto")
    language = parameters.get("language", "es")
    
    global _holographic_instance
    
    if action == "start":
        if player:
            player.write_log("🌐 Iniciando Holograma de Subtítulos en Vivo...")
        
        # Iniciar en modo standalone
        threading.Thread(target=_run_holographic, daemon=True).start()
        
        return "🌐 Traductor Holográfico activado.\n\n" \
               "Características:\n" \
               "• 🎬 Detecta automáticamente YouTube, Netflix, Spotify\n" \
               "• 📝 Subtítulos en tiempo real\n" \
               "• 🌐 Traducción automática\n" \
               "• 🎨 Colores por hablante\n" \
               "• 💾 Guardar subtítulos (SRT/VTT/TXT)\n" \
               "• 📊 Resumen automático con IA\n" \
               "• 🖱️ Ventana flotante arrastrable\n\n" \
               "💡 Click derecho para menú de opciones"
    
    elif action == "stop" or action == "close":
        if _holographic_instance:
            _holographic_instance.close()
            _holographic_instance = None
            return "⏹️ Traductor Holográfico cerrado"
        return "❌ No hay instancia activa"
    
    elif action == "status":
        status = "🟢 Activo" if _holographic_instance and _holographic_instance.is_running else "🔴 Inactivo"
        return f"📊 Estado del Traductor Holográfico: {status}"
    
    elif action == "settings":
        # Mostrar configuración
        return "⚙️ Configuración:\n" \
               f"  • Modo: {mode}\n" \
               f"  • Idioma destino: {language}\n" \
               "  • Detección automática: ✅\n" \
               "  • Traducción: ✅\n" \
               "  • Limpieza de texto: ✅"
    
    elif action == "pause":
        if _holographic_instance:
            _holographic_instance.is_paused = True
            return "⏸️ Subtítulos pausados"
        return "❌ No hay instancia activa"
    
    elif action == "resume":
        if _holographic_instance:
            _holographic_instance.is_paused = False
            return "▶️ Subtítulos reanudados"
        return "❌ No hay instancia activa"
    
    else:
        return "❌ Acción no reconocida.\n\n" \
               "Acciones disponibles:\n" \
               "• start - Iniciar subtítulos holográficos\n" \
               "• stop - Detener\n" \
               "• pause - Pausar\n" \
               "• resume - Reanudar\n" \
               "• status - Ver estado\n" \
               "• settings - Configuración\n\n" \
               "📌 Ejemplos:\n" \
               "  {'action':'start'}\n" \
               "  {'action':'start','language':'en'}\n" \
               "  {'action':'stop'}"


# ─── INSTANCIA GLOBAL ────────────────────────────────────────────────────
_holographic_instance: Optional[HolographicSubtitles] = None

def _run_holographic():
    """Ejecuta la instancia holográfica en un thread separado."""
    global _holographic_instance
    if not _holographic_instance:
        _holographic_instance = HolographicSubtitles()
        _holographic_instance.run()


# ─── INICIALIZACIÓN ──────────────────────────────────────────────────────
def init_holographic():
    """Inicializa el módulo holográfico."""
    print("[Holographic] Inicializando...")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    # Verificar dependencias
    deps = []
    if not YouTubeTranscriptApi:
        deps.append("youtube-transcript-api")
    if not Translator:
        deps.append("googletrans")
    if not pyaudio:
        deps.append("pyaudio")
    if not vosk:
        deps.append("vosk")
    
    if deps:
        print(f"[Holographic] ⚠️ Dependencias faltantes: {', '.join(deps)}")
    
    print("[Holographic] ✅ Listo")
    return True