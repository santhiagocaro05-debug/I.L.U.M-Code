"""
Universal App Control
=====================
Abre CUALQUIER aplicación instalada en Windows usando múltiples métodos:
- Búsqueda por nombre (Win + escribir)
- Ejecución directa (exe, lnk, comando)
- URL/Protocolos (http, mailto, etc.)
- Carpetas del sistema
- Aplicaciones UWP/Store
"""

import time
import subprocess
import os
import re
from pathlib import Path
import json
from typing import Optional, List, Dict, Tuple

try:
    import pyautogui
except ImportError:
    pyautogui = None

try:
    import winreg
except ImportError:
    winreg = None

try:
    import psutil
except ImportError:
    psutil = None


# ─── CONSTANTES ─────────────────────────────────────────────────────────────
APP_ALIASES = {
    # Aplicaciones comunes
    "notepad": "notepad.exe",
    "bloc de notas": "notepad.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "outlook": "outlook.exe",
    "calculadora": "calc.exe",
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "terminal": "wt.exe",
    "explorer": "explorer.exe",
    "chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "opera": "opera.exe",
    "brave": "brave.exe",
    "spotify": "spotify.exe",
    "vscode": "code.exe",
    "visual studio": "devenv.exe",
    "vs code": "code.exe",
    "discord": "Discord.exe",
    "slack": "slack.exe",
    "telegram": "Telegram.exe",
    "whatsapp": "WhatsApp.exe",
    "notion": "Notion.exe",
    "obsidian": "Obsidian.exe",
    "obs": "obs64.exe",
    "audacity": "Audacity.exe",
    "vlc": "vlc.exe",
    "winrar": "WinRAR.exe",
    "7zip": "7zFM.exe",
    "github": "GitHub Desktop.exe",
    "git": "git-gui.exe",
    "node": "node.exe",
    "python": "python.exe",
    "anaconda": "anaconda-navigator.exe",
    "jupyter": "jupyter-notebook.exe",
    # Carpetas del sistema
    "descargas": "shell:Downloads",
    "downloads": "shell:Downloads",
    "documentos": "shell:Documents",
    "documents": "shell:Documents",
    "escritorio": "shell:Desktop",
    "desktop": "shell:Desktop",
    "imagenes": "shell:Pictures",
    "pictures": "shell:Pictures",
    "musica": "shell:Music",
    "music": "shell:Music",
    "videos": "shell:Videos",
    "videos": "shell:Videos",
    # URLs/Protocolos
    "website": "http://",
    "email": "mailto:",
}


# ─── FUNCIONES DE UTILIDAD ─────────────────────────────────────────────────
def get_installed_apps() -> Dict[str, str]:
    """
    Obtiene un diccionario de aplicaciones instaladas desde el registro.
    Retorna: {nombre: ruta_completa}
    """
    apps = {}
    
    if not winreg:
        return apps
    
    # Directorios del registro donde buscar
    registry_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths"),
    ]
    
    for hive, path in registry_paths:
        try:
            key = winreg.OpenKey(hive, path)
            index = 0
            while True:
                try:
                    app_name = winreg.EnumKey(key, index)
                    app_key = winreg.OpenKey(key, app_name)
                    try:
                        app_path, _ = winreg.QueryValueEx(app_key, "")
                        if app_path and app_path.endswith(".exe"):
                            # Limpiar nombre
                            clean_name = app_name.replace(".exe", "").lower()
                            apps[clean_name] = app_path
                    except:
                        pass
                    winreg.CloseKey(app_key)
                    index += 1
                except WindowsError:
                    break
            winreg.CloseKey(key)
        except:
            pass
    
    # Agregar alias comunes
    for alias, app in APP_ALIASES.items():
        if alias not in apps and app.endswith(".exe"):
            # Buscar si existe en las rutas encontradas
            for path in apps.values():
                if app in path.lower():
                    apps[alias] = path
                    break
    
    return apps


def find_app_path(app_name: str) -> Optional[str]:
    """
    Busca la ruta de una aplicación por su nombre.
    Usa primero la lista de instaladas, luego búsqueda en PATH.
    """
    app_name_lower = app_name.lower().strip()
    
    # 1. Verificar alias
    if app_name_lower in APP_ALIASES:
        alias = APP_ALIASES[app_name_lower]
        if alias.startswith("shell:"):
            return alias
        if alias.startswith("http://") or alias.startswith("mailto:"):
            return alias
        if alias.endswith(".exe"):
            # Buscar en apps instaladas
            installed = get_installed_apps()
            for name, path in installed.items():
                if alias.lower() in path.lower() or name == alias.lower():
                    return path
    
    # 2. Buscar en apps instaladas
    installed = get_installed_apps()
    for name, path in installed.items():
        if app_name_lower in name or app_name_lower in path.lower():
            return path
    
    # 3. Buscar en PATH
    result = find_in_path(app_name)
    if result:
        return result
    
    # 4. Buscar como nombre exacto de archivo
    if app_name.endswith('.exe'):
        return app_name
    
    return None


def find_in_path(executable: str) -> Optional[str]:
    """Busca un ejecutable en las variables de entorno PATH."""
    if not executable.endswith('.exe'):
        executable += '.exe'
    
    for path in os.environ.get('PATH', '').split(';'):
        full_path = Path(path) / executable
        if full_path.exists():
            return str(full_path)
    
    return None


def open_shell_folder(folder: str) -> bool:
    """Abre una carpeta especial usando shell:."""
    try:
        subprocess.Popen(["explorer", folder], shell=True)
        return True
    except:
        return False


def open_url(url: str) -> bool:
    """Abre una URL con el navegador predeterminado."""
    try:
        import webbrowser
        webbrowser.open(url)
        return True
    except:
        return False


def open_with_win_search(app_name: str) -> bool:
    """Abre una aplicación usando la búsqueda de Windows (Win + escribir)."""
    try:
        if not pyautogui:
            return False
        
        # Presionar Win para abrir el menú
        pyautogui.press("win")
        time.sleep(0.3)
        
        # Escribir el nombre
        pyautogui.write(app_name, interval=0.03)
        time.sleep(0.3)
        
        # Presionar Enter
        pyautogui.press("enter")
        return True
    except:
        return False


def open_uwp_app(app_name: str) -> bool:
    """Abre una aplicación UWP/Store usando el comando shell:AppsFolder."""
    try:
        # Buscar en AppsFolder
        shell_apps = Path(os.environ.get('ProgramData', '')) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs'
        for app_path in shell_apps.rglob('*.lnk'):
            if app_name.lower() in app_path.stem.lower():
                os.startfile(str(app_path))
                return True
        
        # Buscar en el menú inicio del usuario
        user_start = Path(os.environ.get('APPDATA', '')) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs'
        if user_start.exists():
            for app_path in user_start.rglob('*.lnk'):
                if app_name.lower() in app_path.stem.lower():
                    os.startfile(str(app_path))
                    return True
        
        # Intentar con explorer shell:AppsFolder
        subprocess.Popen(['explorer', 'shell:AppsFolder'], shell=True)
        time.sleep(1)
        # Buscar con la búsqueda de Windows
        return open_with_win_search(app_name)
    except:
        return False


def is_app_running(app_name: str) -> bool:
    """Verifica si una aplicación está ejecutándose."""
    if not psutil:
        return False
    
    app_name_lower = app_name.lower()
    for proc in psutil.process_iter(['name']):
        try:
            proc_name = proc.info['name'].lower()
            if app_name_lower in proc_name or proc_name in app_name_lower:
                return True
        except:
            pass
    return False


# ─── FUNCIÓN PRINCIPAL ─────────────────────────────────────────────────────
def universal_app_control(parameters: dict, player=None) -> str:
    """
    Abre CUALQUIER aplicación instalada en Windows.
    
    Args:
        parameters: Diccionario con parámetros
            - app_name: Nombre de la aplicación
            - method: Método de apertura (auto, win_search, direct, uwp, shell, url)
            - wait: Esperar a que la app se abra (segundos)
            - check_running: Verificar si ya está abierta
            - activate: Activar ventana si ya está abierta
    
    Returns:
        Mensaje de resultado
    """
    p = parameters or {}
    app_name = p.get("app_name", "").strip()
    method = p.get("method", "auto").strip().lower()
    wait_time = int(p.get("wait", 0))
    check_running = p.get("check_running", False)
    activate = p.get("activate", False)
    
    if not app_name:
        return "❌ Por favor especifica qué aplicación quieres abrir."
    
    # Si es un comando de terminal, ejecutarlo directamente
    if app_name.startswith("cmd://") or app_name.startswith("powershell://"):
        cmd = app_name.split("://", 1)[1]
        try:
            if app_name.startswith("powershell://"):
                subprocess.Popen(["powershell", "-Command", cmd], shell=True)
            else:
                subprocess.Popen(cmd, shell=True)
            return f"💻 Comando ejecutado: {cmd[:50]}..."
        except Exception as e:
            return f"❌ Error al ejecutar comando: {e}"
    
    # Verificar si la app ya está abierta
    if check_running:
        if is_app_running(app_name):
            if activate:
                try:
                    # Intentar activar la ventana
                    if pyautogui:
                        # Buscar y enfocar la ventana
                        import pygetwindow as gw
                        windows = gw.getWindowsWithTitle(app_name)
                        if windows:
                            windows[0].activate()
                            return f"🔄 {app_name} ya estaba abierta. Ventana activada."
                except:
                    pass
                return f"🔄 {app_name} ya está en ejecución."
    
    # Determinar si es una URL
    if app_name.startswith("http://") or app_name.startswith("https://") or app_name.startswith("mailto:"):
        if open_url(app_name):
            return f"🌐 Abriendo: {app_name}"
        return "❌ Error al abrir la URL."
    
    # Determinar si es una carpeta especial
    if app_name.startswith("shell:"):
        if open_shell_folder(app_name):
            return f"📂 Abriendo carpeta especial: {app_name}"
        return "❌ Error al abrir la carpeta."
    
    # ─── BÚSQUEDA DE LA APLICACIÓN ──────────────────────────────────────
    app_path = find_app_path(app_name)
    
    # ─── MÉTODOS DE APERTURA ─────────────────────────────────────────────
    success = False
    used_method = ""
    
    # Método 1: URL/Protocolo
    if not success and (method == "auto" or method == "url"):
        if app_name.startswith("http://") or app_name.startswith("https://") or app_name.startswith("mailto:"):
            success = open_url(app_name)
            used_method = "URL"
    
    # Método 2: Shell (carpetas especiales)
    if not success and (method == "auto" or method == "shell"):
        if app_name.startswith("shell:"):
            success = open_shell_folder(app_name)
            used_method = "Shell"
    
    # Método 3: Apertura directa por ruta
    if not success and (method == "auto" or method == "direct"):
        if app_path:
            try:
                os.startfile(app_path)
                success = True
                used_method = "Directo (ruta)"
            except:
                pass
    
    # Método 4: Subprocess (ejecutar comando)
    if not success and (method == "auto" or method == "subprocess"):
        try:
            # Intentar con subprocess
            if app_path:
                subprocess.Popen([app_path], shell=True)
                success = True
                used_method = "Subprocess"
            else:
                # Intentar como comando directo
                subprocess.Popen(app_name, shell=True)
                success = True
                used_method = "Subprocess (comando)"
        except:
            pass
    
    # Método 5: UWP/Store
    if not success and (method == "auto" or method == "uwp"):
        success = open_uwp_app(app_name)
        used_method = "UWP"
    
    # Método 6: Búsqueda de Windows (Win + escribir)
    if not success and (method == "auto" or method == "win_search"):
        if pyautogui:
            success = open_with_win_search(app_name)
            used_method = "Búsqueda de Windows"
    
    # ─── VERIFICACIÓN Y RESULTADO ─────────────────────────────────────────
    if success:
        # Esperar si se solicitó
        if wait_time > 0:
            time.sleep(wait_time)
        
        # Verificar si realmente se abrió
        if check_running:
            time.sleep(2)  # Dar tiempo a que se abra
            if is_app_running(app_name):
                return f"✅ {app_name} abierto correctamente (Método: {used_method})"
            else:
                return f"⚠️ Comando ejecutado, pero no se pudo verificar que {app_name} se haya abierto. (Método: {used_method})"
        
        return f"✅ Abriendo {app_name}... (Método: {used_method})"
    else:
        # Intentar un método alternativo final: búsqueda con fallback
        try:
            # Último intento: usar el comando 'start'
            subprocess.Popen(f'start "" "{app_name}"', shell=True)
            return f"⚠️ Intentando abrir {app_name} con método alternativo..."
        except:
            pass
        
        # Sugerir si la app está instalada
        installed = get_installed_apps()
        suggestions = []
        for name in installed.keys():
            if app_name.lower() in name:
                suggestions.append(name)
        
        if suggestions:
            return (
                f"❌ No pude abrir '{app_name}'. "
                f"Quizás quisiste decir: {', '.join(suggestions[:5])}.\n\n"
                "💡 Sugerencias:\n"
                "- Verifica que la aplicación esté instalada\n"
                "- Intenta con el nombre exacto (ej: 'Visual Studio Code')\n"
                "- Usa 'win_search' como método si el nombre es ambiguo"
            )
        else:
            return (
                f"❌ No pude encontrar '{app_name}' en tu sistema.\n\n"
                "💡 Sugerencias:\n"
                "- Verifica que la aplicación esté instalada\n"
                "- Usa el nombre exacto del ejecutable (ej: 'code.exe')\n"
                "- Para programas de la Tienda, usa 'uwp' como método"
            )


# ─── FUNCIONES ADICIONALES PARA LA IA ─────────────────────────────────────
def list_installed_apps(parameters: dict, player=None) -> str:
    """
    Lista las aplicaciones instaladas en el sistema.
    """
    p = parameters or {}
    filter_text = p.get("filter", "").strip().lower()
    limit = int(p.get("limit", 20))
    
    apps = get_installed_apps()
    
    if filter_text:
        filtered = {k: v for k, v in apps.items() if filter_text in k or filter_text in v.lower()}
    else:
        filtered = apps
    
    # Limitar resultados
    items = list(filtered.items())[:limit]
    
    if not items:
        return "📭 No se encontraron aplicaciones."
    
    lines = [f"📱 Aplicaciones instaladas ({len(items)} mostradas):"]
    for name, path in sorted(items):
        lines.append(f"  • {name} → {path}")
    
    if len(filtered) > limit:
        lines.append(f"\n... y {len(filtered) - limit} más.")
    
    return "\n".join(lines)


def app_info(parameters: dict, player=None) -> str:
    """
    Muestra información detallada de una aplicación.
    """
    app_name = parameters.get("app_name", "").strip()
    
    if not app_name:
        return "❌ Especifica el nombre de la aplicación."
    
    app_path = find_app_path(app_name)
    is_running = is_app_running(app_name)
    
    lines = [
        f"📊 Información de: {app_name}",
        f"  Path: {app_path or 'No encontrado'}",
        f"  Estado: {'✅ En ejecución' if is_running else '⏹️ No ejecutándose'}"
    ]
    
    # Si la app está corriendo, mostrar más info
    if is_running and psutil:
        try:
            for proc in psutil.process_iter(['name', 'pid', 'memory_percent', 'cpu_percent']):
                if app_name.lower() in proc.info['name'].lower():
                    lines.append(f"  PID: {proc.info['pid']}")
                    lines.append(f"  CPU: {proc.info['cpu_percent']:.1f}%")
                    lines.append(f"  RAM: {proc.info['memory_percent']:.1f}%")
                    break
        except:
            pass
    
    return "\n".join(lines)


# ─── INICIALIZACIÓN ──────────────────────────────────────────────────────
def init_app_control():
    """Inicializa el módulo y verifica dependencias."""
    print("[APP CONTROL] Inicializando...")
    if not pyautogui:
        print("[APP CONTROL] ⚠️ pyautogui no instalado - búsqueda de Windows desactivada")
    if not winreg:
        print("[APP CONTROL] ⚠️ winreg no disponible - detección de apps limitada")
    if not psutil:
        print("[APP CONTROL] ⚠️ psutil no instalado - monitoreo de procesos desactivado")
    
    installed = get_installed_apps()
    print(f"[APP CONTROL] {len(installed)} aplicaciones detectadas")
    return True


# Inicializar al importar
init_app_control()

if __name__ == "__main__":
    # Prueba
    print(universal_app_control({"app_name": "notepad"}))
    print(list_installed_apps({"limit": 5}))