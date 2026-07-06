"""
Desktop Control Module
======================
Control completo del escritorio de Windows: wallpaper, organización, limpieza,
archivos, carpetas, atajos, y más.
"""

import os
import shutil
import subprocess
import time
import json
import ctypes
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import threading
import re

try:
    import pyautogui
    import pygetwindow as gw
except ImportError:
    pyautogui = None
    gw = None

try:
    import psutil
except ImportError:
    psutil = None

try:
    import winreg
except ImportError:
    winreg = None

# ─── CONFIGURACIÓN ─────────────────────────────────────────────────────────
CONFIG_DIR = Path("config")
DESKTOP_CONFIG_PATH = CONFIG_DIR / "desktop_config.json"
DESKTOP_BACKUP_DIR = Path("config/desktop_backups")
DESKTOP_BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# ─── CONSTANTES ────────────────────────────────────────────────────────────
USER_HOME = Path(os.environ.get('USERPROFILE', 'C:/Users/Usuario'))
DESKTOP_PATH = USER_HOME / "Desktop"
DOWNLOADS_PATH = USER_HOME / "Downloads"
DOCUMENTS_PATH = USER_HOME / "Documents"
PICTURES_PATH = USER_HOME / "Pictures"
MUSIC_PATH = USER_HOME / "Music"
VIDEOS_PATH = USER_HOME / "Videos"

FILE_CATEGORIES = {
    "images": {
        "extensions": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".ico", ".webp", ".tiff"],
        "folder": "Imágenes"
    },
    "documents": {
        "extensions": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".xls", ".xlsx", ".ppt", ".pptx", ".csv"],
        "folder": "Documentos"
    },
    "compressed": {
        "extensions": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"],
        "folder": "Comprimidos"
    },
    "installers": {
        "extensions": [".exe", ".msi", ".setup", ".dmg", ".deb"],
        "folder": "Instaladores"
    },
    "audio": {
        "extensions": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a"],
        "folder": "Música"
    },
    "video": {
        "extensions": [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v"],
        "folder": "Videos"
    },
    "code": {
        "extensions": [".py", ".js", ".html", ".css", ".java", ".cpp", ".c", ".go", ".rs", ".php", ".rb", ".swift"],
        "folder": "Código"
    },
    "shortcuts": {
        "extensions": [".lnk"],
        "folder": "Accesos Directos"
    }
}

# ─── FUNCIONES DE UTILIDAD ────────────────────────────────────────────────
def get_screen_resolution() -> Tuple[int, int]:
    """Obtiene la resolución de la pantalla."""
    try:
        user32 = ctypes.windll.user32
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    except:
        return 1920, 1080

def get_desktop_icons_position() -> Dict[str, Tuple[int, int]]:
    """Obtiene la posición de los iconos del escritorio."""
    # Implementación simplificada - en producción usaría la API de Windows
    return {}

def set_wallpaper_with_api(image_path: str) -> bool:
    """Establece el fondo de pantalla usando la API de Windows."""
    try:
        # Convertir a ruta absoluta
        path = Path(image_path).resolve()
        if not path.exists():
            return False
        
        # Usar la API de Windows para cambiar el wallpaper
        ctypes.windll.user32.SystemParametersInfoW(0x0014, 0, str(path), 0x0001)
        return True
    except Exception as e:
        print(f"[Desktop] Error cambiando wallpaper: {e}")
        return False

def set_wallpaper_with_powershell(image_path: str) -> bool:
    """Establece el fondo de pantalla usando PowerShell."""
    try:
        path = Path(image_path).resolve()
        if not path.exists():
            return False
        
        script = f"""
        $code = @'
        using System;
        using System.Runtime.InteropServices;
        public class Wallpaper {{
            [DllImport("user32.dll", CharSet = CharSet.Auto)]
            public static extern int SystemParametersInfo(int uAction, int uParam, string lpvParam, int fuWinIni);
            public static void SetWallpaper(string path) {{
                SystemParametersInfo(20, 0, path, 0x0001);
            }}
        }}
        '@
        Add-Type -TypeDefinition $code -Language CSharp
        [Wallpaper]::SetWallpaper("{path}")
        """
        subprocess.run(["powershell", "-Command", script], capture_output=True, timeout=10)
        return True
    except Exception as e:
        print(f"[Desktop] Error PowerShell: {e}")
        return False


# ─── GESTOR DE ESCRITORIO ─────────────────────────────────────────────────
class DesktopManager:
    """Gestor completo del escritorio."""
    
    def __init__(self):
        self.config = self._load_config()
        self._lock = threading.Lock()
    
    def _load_config(self) -> Dict:
        """Carga la configuración del escritorio."""
        if DESKTOP_CONFIG_PATH.exists():
            try:
                return json.loads(DESKTOP_CONFIG_PATH.read_text(encoding="utf-8"))
            except:
                return {}
        return {
            "auto_organize": False,
            "wallpaper_history": [],
            "organize_by_type": True,
            "remove_empty_folders": False,
            "desktop_cleanup_enabled": False,
            "cleanup_days": 7
        }
    
    def _save_config(self):
        """Guarda la configuración."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        DESKTOP_CONFIG_PATH.write_text(
            json.dumps(self.config, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    
    # ─── WALLPAPER ─────────────────────────────────────────────────────────
    def set_wallpaper(self, image_path: str) -> str:
        """Cambia el fondo de pantalla."""
        path = Path(image_path)
        
        if not path.exists():
            return f"❌ Archivo no encontrado: {image_path}"
        
        # Verificar que es una imagen
        valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp'}
        if path.suffix.lower() not in valid_extensions:
            return f"❌ Formato no soportado: {path.suffix}"
        
        # Intentar con API primero
        if set_wallpaper_with_api(str(path)):
            # Guardar en historial
            self.config["wallpaper_history"].append({
                "path": str(path),
                "date": datetime.now().isoformat()
            })
            if len(self.config["wallpaper_history"]) > 10:
                self.config["wallpaper_history"] = self.config["wallpaper_history"][-10:]
            self._save_config()
            
            return f"✅ Fondo de pantalla cambiado: {path.name}"
        
        # Fallback con PowerShell
        if set_wallpaper_with_powershell(str(path)):
            self.config["wallpaper_history"].append({
                "path": str(path),
                "date": datetime.now().isoformat()
            })
            self._save_config()
            return f"✅ Fondo de pantalla cambiado (PowerShell): {path.name}"
        
        return "❌ Error al cambiar el fondo de pantalla"
    
    def get_wallpaper_history(self) -> str:
        """Obtiene el historial de fondos de pantalla."""
        history = self.config.get("wallpaper_history", [])
        if not history:
            return "📭 No hay historial de fondos de pantalla."
        
        lines = ["🖼️ HISTORIAL DE FONDOS", "━" * 40]
        for i, entry in enumerate(reversed(history), 1):
            lines.append(f"{i}. {Path(entry['path']).name}")
            lines.append(f"   📅 {entry['date'][:16].replace('T', ' ')}")
        
        return "\n".join(lines)
    
    # ─── ORGANIZAR ────────────────────────────────────────────────────────
    def organize_desktop(self, by_type: bool = True, by_date: bool = False) -> str:
        """
        Organiza el escritorio.
        
        Args:
            by_type: Organizar por tipo de archivo
            by_date: Organizar por fecha de modificación
        """
        try:
            if not DESKTOP_PATH.exists():
                return "❌ Carpeta de escritorio no encontrada."
            
            files_moved = 0
            folders_created = set()
            errors = []
            
            # Obtener archivos del escritorio
            items = [f for f in DESKTOP_PATH.iterdir() if f.is_file()]
            
            if by_type:
                for file_path in items:
                    try:
                        # Determinar categoría
                        ext = file_path.suffix.lower()
                        category = "otros"
                        folder_name = "Otros"
                        
                        for cat_name, cat_info in FILE_CATEGORIES.items():
                            if ext in cat_info["extensions"]:
                                category = cat_name
                                folder_name = cat_info["folder"]
                                break
                        
                        # Crear carpeta si no existe
                        target_folder = DESKTOP_PATH / folder_name
                        if target_folder not in folders_created:
                            target_folder.mkdir(exist_ok=True)
                            folders_created.add(target_folder)
                        
                        # Mover archivo
                        target_path = target_folder / file_path.name
                        
                        # Si ya existe, añadir número
                        counter = 1
                        while target_path.exists():
                            stem = file_path.stem
                            target_path = target_folder / f"{stem}_{counter}{file_path.suffix}"
                            counter += 1
                        
                        shutil.move(str(file_path), str(target_path))
                        files_moved += 1
                        
                    except Exception as e:
                        errors.append(f"{file_path.name}: {e}")
                
                result = f"✅ Escritorio organizado: {files_moved} archivos movidos"
                if errors:
                    result += f"\n⚠️ Errores: {len(errors)}"
                
                return result
            
            elif by_date:
                # Organizar por fecha
                for file_path in items:
                    try:
                        mod_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                        date_str = mod_time.strftime("%Y-%m")
                        target_folder = DESKTOP_PATH / date_str
                        
                        if target_folder not in folders_created:
                            target_folder.mkdir(exist_ok=True)
                            folders_created.add(target_folder)
                        
                        target_path = target_folder / file_path.name
                        if target_path.exists():
                            target_path = target_folder / f"{mod_time.strftime('%Y%m%d_%H%M%S')}_{file_path.name}"
                        
                        shutil.move(str(file_path), str(target_path))
                        files_moved += 1
                        
                    except Exception as e:
                        errors.append(f"{file_path.name}: {e}")
                
                return f"✅ Escritorio organizado por fecha: {files_moved} archivos movidos"
            
            return "⚠️ Selecciona un método de organización"
            
        except Exception as e:
            return f"❌ Error organizando el escritorio: {e}"
    
    # ─── LIMPIEZA ──────────────────────────────────────────────────────────
    def clean_desktop(self, days: int = 7) -> str:
        """
        Limpia el escritorio moviendo archivos antiguos.
        
        Args:
            days: Días de antigüedad para mover archivos
        """
        try:
            if not DESKTOP_PATH.exists():
                return "❌ Carpeta de escritorio no encontrada."
            
            cutoff = time.time() - (days * 24 * 60 * 60)
            files_moved = 0
            errors = []
            
            # Crear carpeta de archivos antiguos
            old_folder = DESKTOP_PATH / f"Antiguos_{datetime.now().strftime('%Y%m%d')}"
            old_folder.mkdir(exist_ok=True)
            
            for item in DESKTOP_PATH.iterdir():
                if item.is_file():
                    try:
                        if item.stat().st_mtime < cutoff:
                            target_path = old_folder / item.name
                            if target_path.exists():
                                target_path = old_folder / f"{datetime.now().strftime('%H%M%S')}_{item.name}"
                            shutil.move(str(item), str(target_path))
                            files_moved += 1
                    except Exception as e:
                        errors.append(f"{item.name}: {e}")
            
            result = f"✅ Limpieza completada: {files_moved} archivos movidos a {old_folder.name}"
            if errors:
                result += f"\n⚠️ Errores: {len(errors)}"
            
            return result
            
        except Exception as e:
            return f"❌ Error limpiando el escritorio: {e}"
    
    # ─── ESTADÍSTICAS ──────────────────────────────────────────────────────
    def get_desktop_stats(self) -> str:
        """Obtiene estadísticas del escritorio."""
        try:
            if not DESKTOP_PATH.exists():
                return "❌ Carpeta de escritorio no encontrada."
            
            total_items = 0
            total_files = 0
            total_folders = 0
            total_size = 0
            file_types = {}
            
            for item in DESKTOP_PATH.rglob("*"):
                if item.is_file():
                    total_files += 1
                    total_size += item.stat().st_size
                    ext = item.suffix.lower()
                    file_types[ext] = file_types.get(ext, 0) + 1
                elif item.is_dir():
                    total_folders += 1
                total_items += 1
            
            # Calcular tamaño legible
            size_str = self._format_size(total_size)
            
            lines = [
                "📊 ESTADÍSTICAS DEL ESCRITORIO",
                "━" * 40,
                f"📂 Total elementos: {total_items}",
                f"📄 Archivos: {total_files}",
                f"📁 Carpetas: {total_folders}",
                f"💾 Tamaño total: {size_str}",
                "",
                "📋 Tipos de archivo:"
            ]
            
            # Mostrar top tipos
            sorted_types = sorted(file_types.items(), key=lambda x: x[1], reverse=True)[:10]
            for ext, count in sorted_types:
                lines.append(f"  • {ext or 'Sin extensión'}: {count}")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"❌ Error obteniendo estadísticas: {e}"
    
    def _format_size(self, size: int) -> str:
        """Formatea el tamaño de archivo."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
    
    # ─── ATEJOS ────────────────────────────────────────────────────────────
    def create_shortcut(self, target: str, name: str = None, location: str = "desktop") -> str:
        """Crea un acceso directo."""
        try:
            target_path = Path(target)
            if not target_path.exists():
                return f"❌ El destino no existe: {target}"
            
            # Determinar ubicación
            if location.lower() == "desktop":
                location_path = DESKTOP_PATH
            elif location.lower() == "startup":
                location_path = Path(os.environ.get('APPDATA', '')) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs' / 'Startup'
            else:
                location_path = Path(location)
            
            if not location_path.exists():
                location_path.mkdir(parents=True, exist_ok=True)
            
            # Nombre del acceso directo
            if not name:
                name = target_path.stem
            
            shortcut_path = location_path / f"{name}.lnk"
            
            # Usar PowerShell para crear el acceso directo
            script = f"""
            $WScriptShell = New-Object -ComObject WScript.Shell
            $Shortcut = $WScriptShell.CreateShortcut("{shortcut_path}")
            $Shortcut.TargetPath = "{target_path}"
            $Shortcut.Save()
            """
            subprocess.run(["powershell", "-Command", script], capture_output=True, timeout=10)
            
            return f"✅ Acceso directo creado: {shortcut_path.name}"
            
        except Exception as e:
            return f"❌ Error creando acceso directo: {e}"
    
    # ─── ARCHIVOS ──────────────────────────────────────────────────────────
    def find_file(self, name: str, location: str = "desktop") -> str:
        """Busca un archivo en el escritorio."""
        try:
            if location.lower() == "desktop":
                search_path = DESKTOP_PATH
            elif location.lower() == "downloads":
                search_path = DOWNLOADS_PATH
            elif location.lower() == "documents":
                search_path = DOCUMENTS_PATH
            elif location.lower() == "home":
                search_path = USER_HOME
            else:
                search_path = Path(location)
            
            if not search_path.exists():
                return f"❌ Ubicación no encontrada: {location}"
            
            # Buscar archivo
            found = []
            for item in search_path.rglob("*"):
                if name.lower() in item.name.lower():
                    if item.is_file():
                        found.append(item)
            
            if not found:
                return f"🔍 No se encontró '{name}' en {location}"
            
            lines = [f"🔍 Resultados para '{name}' en {location}:", "━" * 40]
            for i, item in enumerate(found[:10], 1):
                size = self._format_size(item.stat().st_size) if item.is_file() else "Carpeta"
                mod_time = datetime.fromtimestamp(item.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                lines.append(f"{i}. 📄 {item.name}")
                lines.append(f"   📂 {item.parent}")
                lines.append(f"   📦 {size} | 📅 {mod_time}")
            
            if len(found) > 10:
                lines.append(f"   ... y {len(found) - 10} más")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"❌ Error buscando archivo: {e}"


# ─── INSTANCIA GLOBAL ────────────────────────────────────────────────────
_manager: Optional[DesktopManager] = None

def get_manager() -> DesktopManager:
    """Obtiene la instancia del gestor de escritorio."""
    global _manager
    if _manager is None:
        _manager = DesktopManager()
    return _manager


# ─── FUNCIÓN PRINCIPAL ────────────────────────────────────────────────────
def desktop_control(parameters: Dict, player=None) -> str:
    """
    Controla el escritorio de Windows.
    
    Args:
        parameters: Diccionario con parámetros
            - action: wallpaper | wallpaper_url | organize | clean | stats | 
                      find | create_shortcut | history | config
            - path: Ruta de archivo para wallpaper
            - mode: by_type | by_date para organizar
            - days: Días para limpieza
            - name: Nombre para buscar archivos
            - location: Ubicación para buscar (desktop, downloads, documents)
            - target: Destino para acceso directo
            - shortcut_name: Nombre del acceso directo
    
    Returns:
        Mensaje de resultado
    """
    p = parameters or {}
    action = p.get("action", "").strip().lower()
    path = p.get("path", "").strip()
    mode = p.get("mode", "by_type").strip().lower()
    days = int(p.get("days", 7))
    name = p.get("name", "").strip()
    location = p.get("location", "desktop").strip()
    target = p.get("target", "").strip()
    shortcut_name = p.get("shortcut_name", "").strip()
    
    manager = get_manager()
    
    # ─── WALLPAPER ──────────────────────────────────────────────────────
    if action == "wallpaper":
        if not path:
            return "❌ Especifica la ruta de la imagen (path='...')"
        
        return manager.set_wallpaper(path)
    
    # ─── WALLPAPER URL ──────────────────────────────────────────────────
    elif action == "wallpaper_url":
        url = p.get("url", "").strip()
        if not url:
            return "❌ Especifica la URL de la imagen (url='...')"
        
        # Descargar imagen
        try:
            import requests
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                # Guardar imagen temporalmente
                temp_path = DESKTOP_BACKUP_DIR / "temp_wallpaper.jpg"
                temp_path.write_bytes(response.content)
                
                # Establecer como wallpaper
                return manager.set_wallpaper(str(temp_path))
            else:
                return f"❌ Error descargando imagen: {response.status_code}"
        except Exception as e:
            return f"❌ Error descargando: {e}"
    
    # ─── HISTORIAL ──────────────────────────────────────────────────────
    elif action == "history":
        return manager.get_wallpaper_history()
    
    # ─── ORGANIZAR ──────────────────────────────────────────────────────
    elif action == "organize":
        by_type = mode == "by_type"
        by_date = mode == "by_date"
        
        if not by_type and not by_date:
            by_type = True
        
        return manager.organize_desktop(by_type, by_date)
    
    # ─── LIMPIAR ────────────────────────────────────────────────────────
    elif action == "clean":
        return manager.clean_desktop(days)
    
    # ─── ESTADÍSTICAS ──────────────────────────────────────────────────
    elif action == "stats":
        return manager.get_desktop_stats()
    
    # ─── BUSCAR ────────────────────────────────────────────────────────
    elif action == "find":
        if not name:
            return "❌ Especifica el nombre del archivo (name='...')"
        
        return manager.find_file(name, location)
    
    # ─── CREAR ACCESO DIRECTO ─────────────────────────────────────────
    elif action == "create_shortcut":
        if not target:
            return "❌ Especifica el destino del acceso directo (target='...')"
        
        return manager.create_shortcut(target, shortcut_name, location)
    
    # ─── CONFIGURACIÓN ─────────────────────────────────────────────────
    elif action == "config":
        config = manager.config
        lines = [
            "⚙️ CONFIGURACIÓN DEL ESCRITORIO",
            "━" * 40,
            f"  • Organización automática: {'✅' if config.get('auto_organize') else '❌'}",
            f"  • Organizar por tipo: {'✅' if config.get('organize_by_type') else '❌'}",
            f"  • Limpieza automática: {'✅' if config.get('desktop_cleanup_enabled') else '❌'}",
            f"  • Días de limpieza: {config.get('cleanup_days', 7)}",
            f"  • Eliminar carpetas vacías: {'✅' if config.get('remove_empty_folders') else '❌'}",
            "",
            "💡 Para cambiar: {'action':'config','set':True,'key':'auto_organize','value':True}"
        ]
        
        # Cambiar configuración
        if p.get("set"):
            key = p.get("key")
            value = p.get("value")
            if key and value is not None:
                if isinstance(value, str) and value.lower() in ["true", "false"]:
                    value = value.lower() == "true"
                config[key] = value
                manager._save_config()
                return f"✅ Configuración actualizada: {key} = {value}"
        
        return "\n".join(lines)
    
    # ─── AYUDA ──────────────────────────────────────────────────────────
    else:
        return (
            "📖 COMANDOS DE ESCRITORIO\n"
            "━" * 50 + "\n\n"
            "🖼️ Cambiar fondo de pantalla:\n"
            "  {'action':'wallpaper','path':'C:/imagen.jpg'}\n"
            "  {'action':'wallpaper_url','url':'https://...'}\n\n"
            "📋 Historial de fondos:\n"
            "  {'action':'history'}\n\n"
            "📂 Organizar escritorio:\n"
            "  {'action':'organize','mode':'by_type'} (por tipo)\n"
            "  {'action':'organize','mode':'by_date'} (por fecha)\n\n"
            "🧹 Limpiar escritorio:\n"
            "  {'action':'clean','days':7} (mueve archivos de más de 7 días)\n\n"
            "📊 Estadísticas:\n"
            "  {'action':'stats'}\n\n"
            "🔍 Buscar archivo:\n"
            "  {'action':'find','name':'documento.pdf','location':'desktop'}\n\n"
            "🔗 Crear acceso directo:\n"
            "  {'action':'create_shortcut','target':'C:/programa.exe','shortcut_name':'Mi Programa'}\n\n"
            "⚙️ Configuración:\n"
            "  {'action':'config'}\n"
            "  {'action':'config','set':True,'key':'auto_organize','value':True}\n\n"
            "📌 Ubicaciones disponibles:\n"
            "  • desktop - Escritorio\n"
            "  • downloads - Descargas\n"
            "  • documents - Documentos\n"
            "  • home - Usuario"
        )


# ─── INICIALIZACIÓN ──────────────────────────────────────────────────────
def init_desktop():
    """Inicializa el módulo de escritorio."""
    print("[Desktop] Inicializando...")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DESKTOP_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"[Desktop] 📂 Escritorio: {DESKTOP_PATH}")
    print("[Desktop] ✅ Listo")
    return True