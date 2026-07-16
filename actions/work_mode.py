import json
import os
import glob as globmod
import subprocess
import webbrowser
import logging
import time
import psutil
import ctypes
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime

# Configuración de logging
LOG_FILE = Path(__file__).resolve().parent.parent / "logs" / "work_mode.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
WORK_MODE_CFG = BASE_DIR / "config" / "work_mode.json"

# Mapeo de nombres comunes a ejecutables conocidos
COMMON_APPS = {
    "chrome": ["C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"],
    "vscode": ["C:\\Program Files\\Microsoft VS Code\\Code.exe", "C:\\Users\\{user}\\AppData\\Local\\Programs\\Microsoft VS Code\\Code.exe"],
    "discord": ["C:\\Users\\{user}\\AppData\\Local\\Discord\\app-*\\Discord.exe"],
    "spotify": ["C:\\Users\\{user}\\AppData\\Local\\Spotify\\Spotify.exe"],
    "steam": ["C:\\Program Files (x86)\\Steam\\Steam.exe"],
    "obs": ["C:\\Program Files\\obs-studio\\bin\\64bit\\obs64.exe"],
    "docker": ["C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe"],
    "terminal": ["wt.exe", "cmd.exe"],
    "notion": ["C:\\Users\\{user}\\AppData\\Local\\Programs\\Notion\\Notion.exe"],
    "figma": ["C:\\Users\\{user}\\AppData\\Local\\Figma\\Figma.exe"],
    "slack": ["C:\\Users\\{user}\\AppData\\Local\\slack\\slack.exe"],
    "telegram": ["C:\\Users\\{user}\\AppData\\Roaming\\Telegram Desktop\\Telegram.exe"],
    "whatsapp": ["C:\\Users\\{user}\\AppData\\Local\\WhatsApp\\WhatsApp.exe"],
    "excel": ["C:\\Program Files\\Microsoft Office\\root\\Office16\\EXCEL.EXE"],
    "word": ["C:\\Program Files\\Microsoft Office\\root\\Office16\\WINWORD.EXE"],
    "powerpoint": ["C:\\Program Files\\Microsoft Office\\root\\Office16\\POWERPNT.EXE"],
    "outlook": ["C:\\Program Files\\Microsoft Office\\root\\Office16\\OUTLOOK.EXE"],
    "teams": ["C:\\Users\\{user}\\AppData\\Local\\Microsoft\\Teams\\current\\Teams.exe",
              "C:\\Program Files\\WindowsApps\\MSTeams_*\\ms-teams.exe"],
    "zoom": ["C:\\Users\\{user}\\AppData\\Roaming\\Zoom\\bin\\Zoom.exe"],
    "anydesk": ["C:\\Program Files (x86)\\AnyDesk\\AnyDesk.exe"],
    "photoshop": ["C:\\Program Files\\Adobe\\Adobe Photoshop 2024\\Photoshop.exe"],
    "premiere": ["C:\\Program Files\\Adobe\\Adobe Premiere Pro 2024\\Premiere Pro.exe"],
    "aftereffects": ["C:\\Program Files\\Adobe\\Adobe After Effects 2024\\Support Files\\AfterFX.exe"],
    "davinci": ["C:\\Program Files\\Blackmagic Design\\DaVinci Resolve\\Resolve.exe"],
    "blender": ["C:\\Program Files\\Blender Foundation\\Blender*\\blender.exe"],
    "postman": ["C:\\Users\\{user}\\AppData\\Local\\Postman\\Postman.exe"],
}

# Procesos que NUNCA deben incluirse en un snapshot ni en cierres automáticos
IGNORED_PROCESSES = {
    "explorer.exe", "svchost.exe", "dwm.exe", "ctfmon.exe", "runtimebroker.exe",
    "searchindexer.exe", "searchapp.exe", "shellexperiencehost.exe",
    "startmenuexperiencehost.exe", "textinputhost.exe", "backgroundtaskhost.exe",
    "applicationframehost.exe", "conhost.exe", "wmiprvse.exe", "python.exe",
    "pythonw.exe", "cmd.exe", "powershell.exe", "wininit.exe", "winlogon.exe",
    "csrss.exe", "smss.exe", "services.exe", "lsass.exe", "fontdrvhost.exe",
    "sihost.exe", "taskhostw.exe", "audiodg.exe", "nexus-ai-hud.exe",
    "nexus.exe", "nexus-code-free.exe",
}

# ─────────────────────────────────────────────────────────────────────────
#  Plantillas por profesión — arrancar un perfil útil en un solo paso
# ─────────────────────────────────────────────────────────────────────────

PROFESSION_TEMPLATES = {
    "programador": {
        "description": "Entorno de desarrollo de software",
        "apps": [
            {"name": "VS Code", "type": "exe", "path": "vscode"},
            {"name": "Terminal", "type": "exe", "path": "terminal"},
            {"name": "Docker Desktop", "type": "exe", "path": "docker"},
            {"name": "Postman", "type": "exe", "path": "postman"},
            {"name": "GitHub", "type": "url", "path": "https://github.com"},
        ],
    },
    "diseñador": {
        "description": "Diseño gráfico y UI/UX",
        "apps": [
            {"name": "Figma", "type": "exe", "path": "figma"},
            {"name": "Photoshop", "type": "exe", "path": "photoshop"},
            {"name": "Pinterest (Referencias)", "type": "url", "path": "https://pinterest.com"},
        ],
    },
    "editor_video": {
        "description": "Edición de video / postproducción",
        "apps": [
            {"name": "Premiere Pro", "type": "exe", "path": "premiere"},
            {"name": "After Effects", "type": "exe", "path": "aftereffects"},
            {"name": "DaVinci Resolve", "type": "exe", "path": "davinci"},
        ],
    },
    "streamer": {
        "description": "Streaming y creación de contenido en vivo",
        "apps": [
            {"name": "OBS Studio", "type": "exe", "path": "obs"},
            {"name": "Discord", "type": "exe", "path": "discord"},
            {"name": "Spotify", "type": "exe", "path": "spotify"},
        ],
    },
    "oficina": {
        "description": "Trabajo administrativo / oficina",
        "apps": [
            {"name": "Outlook", "type": "exe", "path": "outlook"},
            {"name": "Excel", "type": "exe", "path": "excel"},
            {"name": "Word", "type": "exe", "path": "word"},
            {"name": "Teams", "type": "exe", "path": "teams"},
        ],
    },
    "soporte_tecnico": {
        "description": "Soporte técnico / mesa de ayuda",
        "apps": [
            {"name": "AnyDesk", "type": "exe", "path": "anydesk"},
            {"name": "Slack", "type": "exe", "path": "slack"},
            {"name": "Correo", "type": "url", "path": "https://mail.google.com"},
        ],
    },
    "marketing": {
        "description": "Marketing digital y redes sociales",
        "apps": [
            {"name": "Canva", "type": "url", "path": "https://canva.com"},
            {"name": "Meta Business Suite", "type": "url", "path": "https://business.facebook.com"},
            {"name": "Analytics", "type": "url", "path": "https://analytics.google.com"},
        ],
    },
    "musica_audio": {
        "description": "Producción musical / audio",
        "apps": [
            {"name": "Spotify", "type": "exe", "path": "spotify"},
        ],
    },
}


class WorkModeManager:
    """Gestor profesional del Modo Trabajo con perfiles y funcionalidades avanzadas"""

    def __init__(self):
        self.config_path = WORK_MODE_CFG
        self.config = self._load_config()
        self.progress = []
        self.current_profile = None

    def _load_config(self) -> Dict:
        default_config = {
            "profiles": {},
            "active_profile": None,
            "settings": {
                "auto_discover": True,
                "close_others": False,
                "default_delay": 1,
            },
        }
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                if "profiles" not in data:
                    data["profiles"] = {}
                if "settings" not in data:
                    data["settings"] = default_config["settings"]
                if "active_profile" not in data:
                    data["active_profile"] = None
                return data
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.error(f"Error al cargar configuración: {e}")
                return default_config
        return default_config

    def _save_config(self) -> bool:
        try:
            if self.config_path.exists():
                backup_path = self.config_path.with_suffix('.json.bak')
                self.config_path.replace(backup_path)
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(
                json.dumps(self.config, indent=4, ensure_ascii=False),
                encoding="utf-8"
            )
            logger.info("Configuración guardada exitosamente")
            return True
        except (IOError, OSError) as e:
            logger.error(f"Error al guardar configuración: {e}")
            return False

    # ── Búsqueda de aplicaciones ────────────────────────────────────────

    def _find_app_path(self, app_name: str) -> Optional[str]:
        """Busca automáticamente la ruta de una aplicación por nombre."""
        app_name_lower = app_name.lower()
        user_home = os.path.expanduser("~")

        if app_name_lower in COMMON_APPS:
            for path_pattern in COMMON_APPS[app_name_lower]:
                path_pattern = path_pattern.replace("{user}", os.path.basename(user_home))
                if "*" in path_pattern:
                    # Fix: glob.glob resuelve comodines correctamente sin trocear el string a mano.
                    matches = [m for m in globmod.glob(path_pattern) if os.path.isfile(m)]
                    if matches:
                        matches.sort(key=lambda p: os.path.getmtime(p), reverse=True)
                        return matches[0]
                elif os.path.exists(path_pattern):
                    return path_pattern

        for path in os.environ.get("PATH", "").split(os.pathsep):
            exe_path = Path(path) / f"{app_name}.exe"
            if exe_path.exists():
                return str(exe_path)

        common_dirs = [
            "C:\\Program Files",
            "C:\\Program Files (x86)",
            os.path.join(user_home, "AppData", "Local"),
            os.path.join(user_home, "AppData", "Roaming"),
        ]
        for dir_path in common_dirs:
            search_path = Path(dir_path)
            if not search_path.exists():
                continue
            try:
                for exe_path in search_path.rglob(f"{app_name}.exe"):
                    if exe_path.is_file():
                        return str(exe_path)
                for folder_path in search_path.glob(f"*{app_name}*"):
                    if folder_path.is_dir():
                        for exe in folder_path.rglob("*.exe"):
                            if exe.is_file():
                                return str(exe)
            except (PermissionError, OSError):
                continue

        logger.warning(f"No se encontró la aplicación: {app_name}")
        return None

    def _resolve_app_path(self, app: Dict) -> Optional[str]:
        app_type = app.get("type", "exe")
        path = app.get("path", "")
        name = app.get("name", "")
        if app_type == "exe":
            if not path or not os.path.exists(path):
                if self.config.get("settings", {}).get("auto_discover", True):
                    found_path = self._find_app_path(name or path)
                    if found_path:
                        return found_path
            return path if os.path.exists(path) else None
        return path

    # ── Apertura / cierre de aplicaciones ────────────────────────────────

    def _open_app(self, app: Dict) -> bool:
        """Abre una aplicación con soporte para múltiples tipos."""
        app_type = app.get("type", "exe")
        path = app.get("path", "")
        name = app.get("name", path)
        args = app.get("args", [])
        run_as_admin = app.get("run_as_admin", False)
        delay = app.get("delay", 0)
        wait = app.get("wait", False)

        self._log_progress(f"Abriendo {name}...", "info")

        try:
            if delay > 0:
                time.sleep(delay)

            if app_type == "exe":
                resolved_path = self._resolve_app_path(app)
                if not resolved_path:
                    self._log_progress(f"[X] No se encontró: {name}", "error")
                    return False
                cmd = [resolved_path] + args
                if run_as_admin and os.name == 'nt':
                    try:
                        ctypes.windll.shell32.ShellExecuteW(
                            None, "runas", resolved_path, " ".join(args), None, 1
                        )
                        self._log_progress(f"[OK] {name} (admin)", "success")
                        return True
                    except Exception as e:
                        logger.error(f"Error al ejecutar como admin {name}: {e}")
                if wait:
                    subprocess.run(cmd, shell=False, capture_output=True)
                else:
                    subprocess.Popen(cmd, shell=False)
                self._log_progress(f"[OK] {name}", "success")
                return True

            elif app_type == "url":
                webbrowser.open(path)
                self._log_progress(f"[OK] {name} (URL)", "success")
                return True

            elif app_type == "browser_tabs":
                # Abre varias URLs de un tirón en la misma ventana del navegador.
                urls = app.get("urls", [])
                if not urls:
                    self._log_progress(f"[X] {name}: no se indicaron URLs", "error")
                    return False
                browser_path = self._find_app_path("chrome")
                if browser_path:
                    subprocess.Popen([browser_path] + urls)
                else:
                    webbrowser.open(urls[0])
                    for u in urls[1:]:
                        webbrowser.open_new_tab(u)
                self._log_progress(f"[OK] {name} ({len(urls)} pestañas)", "success")
                return True

            elif app_type == "folder":
                if os.name == 'nt':
                    os.startfile(path)
                else:
                    subprocess.Popen(['xdg-open', path] if os.name == 'posix' else ['open', path])
                self._log_progress(f"[OK] {name} (carpeta)", "success")
                return True

            elif app_type == "file":
                # Abre un archivo/documento específico (Excel, Word, un .sln, un proyecto, etc.)
                if not path or not os.path.exists(path):
                    self._log_progress(f"[X] Archivo no encontrado: {path}", "error")
                    return False
                if os.name == 'nt':
                    if args:
                        # abrir con una app específica (ej. VS Code + carpeta de proyecto)
                        opener = self._find_app_path(args[0]) or args[0]
                        subprocess.Popen([opener, path])
                    else:
                        os.startfile(path)
                else:
                    subprocess.Popen(['xdg-open', path])
                self._log_progress(f"[OK] {name} (archivo)", "success")
                return True

            elif app_type == "cmd":
                subprocess.Popen(path, shell=True)
                self._log_progress(f"[OK] {name} (CMD)", "success")
                return True

            elif app_type == "powershell":
                subprocess.Popen(["powershell", "-NoExit", "-Command", path])
                self._log_progress(f"[OK] {name} (PowerShell)", "success")
                return True

            elif app_type == "uri":
                os.system(f"start {path}")
                self._log_progress(f"[OK] {name} (URI)", "success")
                return True

            elif app_type == "wait":
                time.sleep(app.get("seconds", 1))
                self._log_progress(f"[..] Espera de {app.get('seconds', 1)}s", "info")
                return True

            else:
                logger.warning(f"Tipo de aplicación no soportado: {app_type}")
                return False

        except Exception as e:
            logger.error(f"Error al abrir {name}: {e}")
            self._log_progress(f"[X] Error: {name}", "error")
            return False

    def _log_progress(self, message: str, level: str = "info"):
        self.progress.append({"message": message, "level": level, "time": datetime.now()})
        if level == "error":
            logger.error(message)
        else:
            logger.info(message)

    def _is_app_running(self, app_name: str) -> bool:
        try:
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] and app_name.lower() in proc.info['name'].lower():
                    return True
            return False
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def _close_app(self, app_name: str) -> bool:
        try:
            closed = False
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'] and app_name.lower() in proc.info['name'].lower():
                        proc.terminate()
                        closed = True
                        self._log_progress(f"Cerrando {app_name}...", "info")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            time.sleep(1)
            return closed
        except Exception as e:
            logger.error(f"Error al cerrar {app_name}: {e}")
            return False

    # ── Perfiles ─────────────────────────────────────────────────────────

    def start_profile(self, profile_name: str) -> str:
        self.progress = []
        self.current_profile = profile_name

        if profile_name not in self.config.get("profiles", {}):
            return f"[X] Perfil '{profile_name}' no encontrado"

        profile = self.config["profiles"][profile_name]
        apps = profile.get("apps", [])

        if not apps:
            return f"[!] El perfil '{profile_name}' no tiene aplicaciones configuradas"

        self._log_progress(f"Iniciando perfil: {profile_name}", "info")

        # Cerrar distracciones/apps indicadas antes de empezar (opt-in explícito)
        close_before = profile.get("settings", {}).get("close_before_start", [])
        if close_before:
            self._log_progress(f"Cerrando {len(close_before)} apps antes de iniciar...", "info")
            for app_name in close_before:
                self._close_app(app_name)

        self._log_progress(f"{len(apps)} aplicaciones para abrir", "info")
        self._log_progress("=" * 40, "info")

        launched, failed = [], []
        for app in apps:
            if self._open_app(app):
                launched.append(app.get("name", app.get("path")))
            else:
                failed.append(app.get("name", app.get("path")))

        self.config["active_profile"] = profile_name
        self._save_config()
        self._log_progress("=" * 40, "info")

        if not failed:
            return (f"Perfil '{profile_name}' iniciado correctamente.\n"
                     f"Abiertas: {len(launched)} aplicaciones -> {', '.join(launched)}\n"
                     f"Para cerrar todas: \"ilum cierra {profile_name}\"")
        else:
            return (f"Perfil '{profile_name}' iniciado con errores.\n"
                     f"Abiertas: {len(launched)} | Fallaron: {len(failed)} -> {', '.join(failed)}\n"
                     f"Revisa los logs en: {LOG_FILE}")

    def stop_profile(self, profile_name: str) -> str:
        if profile_name not in self.config.get("profiles", {}):
            return f"[X] Perfil '{profile_name}' no encontrado"

        apps = self.config["profiles"][profile_name].get("apps", [])
        if not apps:
            return f"[!] El perfil '{profile_name}' no tiene aplicaciones"

        self._log_progress(f"Deteniendo perfil: {profile_name}", "info")
        closed, failed = [], []
        for app in apps:
            app_name = app.get("name", app.get("path"))
            if app.get("type") not in ("exe",):
                continue
            if self._close_app(app_name):
                closed.append(app_name)
            else:
                failed.append(app_name)

        if self.config.get("active_profile") == profile_name:
            self.config["active_profile"] = None
            self._save_config()

        if not failed:
            return f"Perfil '{profile_name}' detenido correctamente.\nCerradas: {', '.join(closed) or 'ninguna (ya estaban cerradas)'}"
        return f"Problemas al detener:\nCerradas: {', '.join(closed)}\nFallaron: {', '.join(failed)}"

    def add_to_profile(self, profile_name: str, app_data: Dict) -> str:
        if profile_name not in self.config.get("profiles", {}):
            return f"[X] Perfil '{profile_name}' no encontrado"

        if "name" not in app_data:
            app_data["name"] = app_data.get("path", "Sin nombre")

        # Evitar duplicados exactos por nombre
        existing = self.config["profiles"][profile_name].get("apps", [])
        if any(a.get("name", "").lower() == app_data["name"].lower() for a in existing):
            return f"[!] '{app_data['name']}' ya está en el perfil '{profile_name}'"

        if app_data.get("type") == "exe" and app_data.get("path"):
            if not os.path.exists(app_data["path"]):
                resolved = self._find_app_path(app_data["name"])
                if resolved:
                    app_data["path"] = resolved

        self.config["profiles"][profile_name].setdefault("apps", []).append(app_data)
        if self._save_config():
            return f"Aplicación agregada al perfil '{profile_name}': {app_data['name']}"
        return "[X] Error al guardar la configuración"

    def remove_from_profile(self, profile_name: str, app_name: str) -> str:
        if profile_name not in self.config.get("profiles", {}):
            return f"[X] Perfil '{profile_name}' no encontrado"

        apps = self.config["profiles"][profile_name].get("apps", [])
        removed = []
        for app in apps[:]:
            if app.get("name") == app_name or app.get("path") == app_name:
                apps.remove(app)
                removed.append(app.get("name", app.get("path")))

        if removed:
            self._save_config()
            return f"Eliminado del perfil '{profile_name}': {', '.join(removed)}"
        return f"[X] Aplicación no encontrada en el perfil '{profile_name}'"

    def edit_app_in_profile(self, profile_name: str, app_name: str, new_data: Dict) -> str:
        """Actualiza los campos de una app existente sin tener que borrarla y re-agregarla."""
        if profile_name not in self.config.get("profiles", {}):
            return f"[X] Perfil '{profile_name}' no encontrado"
        apps = self.config["profiles"][profile_name].get("apps", [])
        for app in apps:
            if app.get("name") == app_name or app.get("path") == app_name:
                app.update(new_data)
                self._save_config()
                return f"'{app_name}' actualizado en el perfil '{profile_name}'"
        return f"[X] No se encontró '{app_name}' en el perfil '{profile_name}'"

    def rename_profile(self, old_name: str, new_name: str) -> str:
        profiles = self.config.get("profiles", {})
        if old_name not in profiles:
            return f"[X] Perfil '{old_name}' no encontrado"
        if new_name in profiles:
            return f"[!] Ya existe un perfil llamado '{new_name}'"
        profiles[new_name] = profiles.pop(old_name)
        if self.config.get("active_profile") == old_name:
            self.config["active_profile"] = new_name
        self._save_config()
        return f"Perfil '{old_name}' renombrado a '{new_name}'"

    def duplicate_profile(self, source_name: str, new_name: str) -> str:
        profiles = self.config.get("profiles", {})
        if source_name not in profiles:
            return f"[X] Perfil '{source_name}' no encontrado"
        if new_name in profiles:
            return f"[!] Ya existe un perfil llamado '{new_name}'"
        import copy
        profiles[new_name] = copy.deepcopy(profiles[source_name])
        self._save_config()
        return f"Perfil '{source_name}' duplicado como '{new_name}'"

    def list_profiles(self) -> str:
        profiles = self.config.get("profiles", {})
        if not profiles:
            return "No hay perfiles configurados. Usa 'templates' para ver plantillas listas por profesión."

        response = "Perfiles disponibles:\n" + "=" * 40 + "\n"
        for name, profile in profiles.items():
            apps_count = len(profile.get("apps", []))
            active = " (ACTIVO)" if self.config.get("active_profile") == name else ""
            response += f"\n- {name}{active}\n"
            response += f"  Apps: {apps_count}"
            if profile.get("description"):
                response += f" | {profile['description']}"
            response += "\n"
            if apps_count > 0:
                names = [a.get("name", a.get("path")) for a in profile.get("apps", [])[:3]]
                response += "  " + ", ".join(names)
                if apps_count > 3:
                    response += f" (+{apps_count - 3} más)"
                response += "\n"
        response += "\n" + "=" * 40
        response += "\nUsa: 'ilum activa [perfil]' para iniciarlo"
        return response

    def list_templates(self) -> str:
        response = "Plantillas disponibles por profesión:\n" + "=" * 40 + "\n"
        for key, tpl in PROFESSION_TEMPLATES.items():
            apps = ", ".join(a["name"] for a in tpl["apps"])
            response += f"\n- {key}: {tpl['description']}\n  Apps: {apps}\n"
        response += "\n" + "=" * 40
        response += "\nUsa: {\"action\": \"create_from_template\", \"template\": \"programador\", \"profile_name\": \"Mi Trabajo\"}"
        return response

    def create_profile_from_template(self, template_key: str, profile_name: str) -> str:
        template_key = template_key.lower().strip()
        if template_key not in PROFESSION_TEMPLATES:
            return f"[X] Plantilla '{template_key}' no existe. Usa 'templates' para ver las disponibles."
        if profile_name in self.config.get("profiles", {}):
            return f"[!] Ya existe un perfil llamado '{profile_name}'"

        tpl = PROFESSION_TEMPLATES[template_key]
        import copy
        self.config["profiles"][profile_name] = {
            "description": tpl["description"],
            "apps": copy.deepcopy(tpl["apps"]),
            "settings": {"close_before_start": [], "default_delay": 1},
        }
        self._save_config()
        return f"Perfil '{profile_name}' creado desde la plantilla '{template_key}' con {len(tpl['apps'])} apps."

    def snapshot_running_apps(self) -> List[Dict]:
        """Detecta las apps de usuario abiertas actualmente (para guardarlas como perfil)."""
        seen = set()
        apps = []
        for proc in psutil.process_iter(['name', 'exe']):
            try:
                name = proc.info['name']
                exe = proc.info['exe']
                if not name or not exe:
                    continue
                key = name.lower()
                if key in IGNORED_PROCESSES or key in seen:
                    continue
                seen.add(key)
                apps.append({"name": Path(exe).stem, "type": "exe", "path": exe})
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return apps

    def create_profile_from_snapshot(self, profile_name: str, description: str = "") -> str:
        if profile_name in self.config.get("profiles", {}):
            return f"[!] Ya existe un perfil llamado '{profile_name}'"
        apps = self.snapshot_running_apps()
        if not apps:
            return "No se detectaron aplicaciones de usuario abiertas para guardar."
        self.config["profiles"][profile_name] = {
            "description": description or "Creado desde snapshot de apps abiertas",
            "apps": apps,
            "settings": {"close_before_start": [], "default_delay": 1},
        }
        self._save_config()
        names = ", ".join(a["name"] for a in apps[:8])
        extra = f" (+{len(apps) - 8} más)" if len(apps) > 8 else ""
        return f"Perfil '{profile_name}' creado con {len(apps)} apps detectadas: {names}{extra}"

    def create_profile(self, profile_name: str, description: str = "") -> str:
        if profile_name in self.config.get("profiles", {}):
            return f"[!] El perfil '{profile_name}' ya existe"
        self.config["profiles"][profile_name] = {
            "description": description,
            "apps": [],
            "settings": {"close_before_start": [], "default_delay": 1},
        }
        if self._save_config():
            return f"Perfil '{profile_name}' creado exitosamente"
        return "[X] Error al crear perfil"

    def delete_profile(self, profile_name: str) -> str:
        if profile_name not in self.config.get("profiles", {}):
            return f"[X] Perfil '{profile_name}' no encontrado"
        if self.config.get("active_profile") == profile_name:
            self.config["active_profile"] = None
        del self.config["profiles"][profile_name]
        if self._save_config():
            return f"Perfil '{profile_name}' eliminado"
        return "[X] Error al eliminar perfil"

    def get_status(self) -> str:
        active = self.config.get("active_profile")
        profiles = len(self.config.get("profiles", {}))
        response = "Estado del Modo Trabajo:\n" + "=" * 40 + "\n"
        response += f"Perfil activo: {active or 'Ninguno'}\n"
        response += f"Perfiles totales: {profiles}\n"
        if active and active in self.config.get("profiles", {}):
            apps = self.config["profiles"][active].get("apps", [])
            response += f"Apps en perfil activo: {len(apps)}\n"
            running = [a.get("name", a.get("path")) for a in apps if self._is_app_running(a.get("name", a.get("path", "")))]
            if running:
                response += f"En ejecución: {', '.join(running)}\n"
        response += "=" * 40
        return response


def work_mode(parameters: dict, player=None) -> str:
    """
    Herramienta profesional para gestionar el Modo Trabajo con perfiles, válida
    para cualquier tipo de trabajo (oficina, programación, diseño, edición de
    video, streaming, soporte técnico, marketing, música, etc.)

    Acciones:
    - start / activate: Inicia un perfil (profile_name)
    - stop: Detiene un perfil (profile_name)
    - list / profiles: Lista todos los perfiles
    - templates: Lista las plantillas por profesión disponibles
    - create_from_template: Crea un perfil desde una plantilla (template, profile_name)
    - snapshot: Crea un perfil a partir de las apps abiertas ahora mismo (profile_name)
    - create: Crea un perfil vacío (profile_name)
    - delete: Elimina un perfil (profile_name)
    - rename: Renombra un perfil (profile_name, new_name)
    - duplicate: Duplica un perfil (profile_name, new_name)
    - add: Agrega app a perfil (profile_name, app_data)
    - remove: Elimina app de perfil (profile_name, app_name)
    - edit: Edita una app existente (profile_name, app_name, app_data)
    - status: Muestra el estado actual

    Tipos de app_data.type soportados:
      exe, url, browser_tabs (con "urls": [...]), folder, file (documento o
      proyecto específico, opcionalmente con "args": ["vscode"] para abrirlo
      con una app concreta), cmd, powershell, uri, wait.
    """
    action = parameters.get("action", "").lower().strip()
    profile_name = parameters.get("profile_name", "").strip()
    new_name = parameters.get("new_name", "").strip()
    app_data = parameters.get("app_data", {})
    app_name = parameters.get("app_name", "").strip()
    template = parameters.get("template", "").strip()
    description = parameters.get("description", "")

    manager = WorkModeManager()

    actions = {
        "start": lambda: manager.start_profile(profile_name) if profile_name else "[X] Se requiere 'profile_name'",
        "activate": lambda: manager.start_profile(profile_name) if profile_name else "[X] Se requiere 'profile_name'",
        "stop": lambda: manager.stop_profile(profile_name) if profile_name else "[X] Se requiere 'profile_name'",
        "list": lambda: manager.list_profiles(),
        "profiles": lambda: manager.list_profiles(),
        "templates": lambda: manager.list_templates(),
        "create_from_template": lambda: manager.create_profile_from_template(template, profile_name) if template and profile_name else "[X] Se requiere 'template' y 'profile_name'",
        "snapshot": lambda: manager.create_profile_from_snapshot(profile_name, description) if profile_name else "[X] Se requiere 'profile_name'",
        "create": lambda: manager.create_profile(profile_name, description) if profile_name else "[X] Se requiere 'profile_name'",
        "delete": lambda: manager.delete_profile(profile_name) if profile_name else "[X] Se requiere 'profile_name'",
        "rename": lambda: manager.rename_profile(profile_name, new_name) if profile_name and new_name else "[X] Se requiere 'profile_name' y 'new_name'",
        "duplicate": lambda: manager.duplicate_profile(profile_name, new_name) if profile_name and new_name else "[X] Se requiere 'profile_name' y 'new_name'",
        "add": lambda: manager.add_to_profile(profile_name, app_data) if profile_name and app_data else "[X] Se requiere 'profile_name' y 'app_data'",
        "remove": lambda: manager.remove_from_profile(profile_name, app_name) if profile_name and app_name else "[X] Se requiere 'profile_name' y 'app_name'",
        "edit": lambda: manager.edit_app_in_profile(profile_name, app_name, app_data) if profile_name and app_name and app_data else "[X] Se requiere 'profile_name', 'app_name' y 'app_data'",
        "status": lambda: manager.get_status(),
        "info": lambda: manager.get_status(),
    }

    if action not in actions:
        return f"""Acción inválida: '{action}'

Acciones disponibles:
{', '.join(sorted(set(actions.keys())))}

Ejemplos:
1. Ver plantillas por profesión:
   {{"action": "templates"}}

2. Crear perfil desde plantilla (para CUALQUIER tipo de trabajo):
   {{"action": "create_from_template", "template": "programador", "profile_name": "Mi Trabajo"}}

3. Guardar lo que tienes abierto ahora como perfil:
   {{"action": "snapshot", "profile_name": "Jornada de hoy"}}

4. Crear perfil vacío y agregar apps a mano:
   {{"action": "create", "profile_name": "Trabajo"}}
   {{"action": "add", "profile_name": "Trabajo", "app_data": {{
       "name": "Chrome (Pestañas)", "type": "browser_tabs",
       "urls": ["https://gmail.com", "https://calendar.google.com"]
   }}}}

5. Iniciar perfil:
   {{"action": "start", "profile_name": "Trabajo"}}

6. Detener perfil:
   {{"action": "stop", "profile_name": "Trabajo"}}

7. Estado actual:
   {{"action": "status"}}

Tipos de app_data.type soportados:
- exe: Ejecutables
- url: Página web (una sola)
- browser_tabs: Varias URLs en pestañas de una vez ("urls": [...])
- folder: Carpetas
- file: Documento/proyecto específico (opcional "args": ["vscode"])
- cmd / powershell: Comandos
- uri: URIs especiales
- wait: Pausa entre apps
"""

    return actions[action]()