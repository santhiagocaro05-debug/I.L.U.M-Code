# -*- coding: utf-8 -*-
"""
open_app.py — Intelligent heuristic application finder and launcher for ILUM.
VERSIÓN ULTRA MEJORADA - Abre CUALQUIER aplicación
"""

import os
import subprocess
import webbrowser
import traceback
import shutil
import winreg
from typing import Optional, List, Dict
import ctypes
import sys

class SuperAppLauncher:
    """Launcher universal de aplicaciones - Abre TODO"""
    
    def __init__(self):
        self.app_cache = {}  # Cache para búsquedas rápidas
        self.store_apps = {}  # Apps de Microsoft Store
        
    def find_app_windows_store(self, app_name: str) -> Optional[str]:
        """Busca aplicaciones de Microsoft Store"""
        try:
            # Usar shell:AppsFolder (donde viven las apps de Store)
            shell_folder = "shell:AppsFolder"
            
            # Listar apps con PowerShell (rápido)
            cmd = f'powershell -command "Get-StartApps | Where-Object {{ $_.Name -like \\"*{app_name}*\\" }} | Select-Object -First 1 -ExpandProperty AppId"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.stdout.strip():
                app_id = result.stdout.strip()
                return f"shell:AppsFolder\\{app_id}"
        except:
            pass
        return None
    
    def find_app_registry(self, app_name: str) -> Optional[str]:
        """Busca en el registro de Windows (MUY RÁPIDO)"""
        app_name_lower = app_name.lower()
        
        # Claves del registro donde están las apps instaladas
        reg_paths = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths",
            r"SOFTWARE\RegisteredApplications"
        ]
        
        for reg_path in reg_paths:
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path)
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        if app_name_lower in subkey_name.lower():
                            # Obtener ruta del ejecutable
                            app_key = winreg.OpenKey(key, subkey_name)
                            try:
                                path, _ = winreg.QueryValueEx(app_key, "")
                                if os.path.exists(path):
                                    return path
                            except:
                                pass
                            winreg.CloseKey(app_key)
                        i += 1
                    except OSError:
                        break
                winreg.CloseKey(key)
            except:
                continue
        return None
    
    def find_app_where(self, app_name: str) -> Optional[str]:
        """Usa el comando WHERE de Windows (rápido para ejecutables en PATH)"""
        try:
            result = subprocess.run(
                f'where {app_name}.exe', 
                shell=True, 
                capture_output=True, 
                text=True,
                timeout=2
            )
            if result.stdout.strip():
                return result.stdout.strip().split('\n')[0]
        except:
            pass
        return None
    
    def find_app_start_menu(self, app_name: str) -> Optional[str]:
        """Búsqueda optimizada en el menú inicio (MUY RÁPIDA)"""
        app_name_lower = app_name.lower()
        
        start_menu_dirs = [
            os.path.join(os.environ.get("ProgramData", "C:\\ProgramData"), 
                        "Microsoft\\Windows\\Start Menu\\Programs"),
            os.path.join(os.environ.get("APPDATA", ""), 
                        "Microsoft\\Windows\\Start Menu\\Programs"),
            os.path.join(os.path.expanduser("~"), "Desktop"),
            os.path.join(os.environ.get("ALLUSERSPROFILE", ""), 
                        "Microsoft\\Windows\\Start Menu\\Programs")
        ]
        
        # Primero buscar coincidencia EXACTA (más rápido)
        for base_dir in start_menu_dirs:
            if not base_dir or not os.path.exists(base_dir):
                continue
            
            # Buscar solo .lnk y .exe en nivel superficial
            try:
                for file in os.listdir(base_dir):
                    if file.lower().endswith(('.lnk', '.exe')):
                        name_no_ext = os.path.splitext(file)[0].lower()
                        if name_no_ext == app_name_lower:
                            return os.path.join(base_dir, file)
            except:
                pass
            
            # Búsqueda recursiva limitada (solo 2 niveles)
            try:
                for root, dirs, files in os.walk(base_dir):
                    depth = root.count(os.sep) - base_dir.count(os.sep)
                    if depth > 2:  # Limitar profundidad para velocidad
                        dirs.clear()
                        continue
                    
                    for file in files:
                        if file.lower().endswith(('.lnk', '.exe')):
                            name_no_ext = os.path.splitext(file)[0].lower()
                            if name_no_ext == app_name_lower:
                                return os.path.join(root, file)
            except:
                continue
        
        # Si no exacta, buscar coincidencia parcial (más lento pero necesario)
        for base_dir in start_menu_dirs:
            if not base_dir or not os.path.exists(base_dir):
                continue
            try:
                for root, dirs, files in os.walk(base_dir):
                    depth = root.count(os.sep) - base_dir.count(os.sep)
                    if depth > 2:
                        dirs.clear()
                        continue
                    
                    for file in files:
                        if file.lower().endswith(('.lnk', '.exe')):
                            name_no_ext = os.path.splitext(file)[0].lower()
                            if app_name_lower in name_no_ext:
                                return os.path.join(root, file)
            except:
                continue
        
        return None
    
    def find_app_program_files(self, app_name: str) -> Optional[str]:
        """Búsqueda inteligente en Program Files"""
        app_name_lower = app_name.lower()
        
        search_dirs = [
            os.environ.get("ProgramFiles", "C:\\Program Files"),
            os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
            os.environ.get("LocalAppData", "") + "\\Programs",
            "C:\\Windows\\System32"
        ]
        
        # Lista de palabras a evitar para acelerar búsqueda
        excluded = ['uninstall', 'installer', 'setup', 'redist', 
                   'vc_redist', 'dotnet', 'windows kits', 'microsoft sdks']
        
        for base_dir in search_dirs:
            if not base_dir or not os.path.exists(base_dir):
                continue
            
            try:
                # Búsqueda rápida: solo 1 nivel de profundidad primero
                for item in os.listdir(base_dir):
                    item_path = os.path.join(base_dir, item)
                    if os.path.isdir(item_path):
                        # Buscar .exe en la carpeta principal
                        try:
                            for file in os.listdir(item_path):
                                if file.lower().endswith('.exe'):
                                    name_no_ext = os.path.splitext(file)[0].lower()
                                    if name_no_ext == app_name_lower or app_name_lower in name_no_ext:
                                        # Verificar que no sea un instalador
                                        if not any(ex in name_no_ext for ex in excluded):
                                            return os.path.join(item_path, file)
                        except:
                            pass
            except:
                continue
        
        # Si no se encuentra, búsqueda más profunda pero limitada
        for base_dir in search_dirs:
            if not base_dir or not os.path.exists(base_dir):
                continue
            
            try:
                for root, dirs, files in os.walk(base_dir):
                    # Limitar profundidad
                    depth = root.count(os.sep) - base_dir.count(os.sep)
                    if depth > 3:
                        dirs.clear()
                        continue
                    
                    # Filtrar directorios excluidos
                    dirs[:] = [d for d in dirs if d.lower() not in excluded]
                    
                    for file in files:
                        if file.lower().endswith('.exe'):
                            name_no_ext = os.path.splitext(file)[0].lower()
                            if name_no_ext == app_name_lower or app_name_lower in name_no_ext:
                                if not any(ex in name_no_ext for ex in excluded):
                                    return os.path.join(root, file)
            except:
                continue
        
        return None
    
    def launch_with_priority(self, path: str) -> bool:
        """Lanza la aplicación con prioridad normal"""
        try:
            # Método 1: os.startfile (mejor para .lnk y asociaciones)
            os.startfile(path)
            return True
        except:
            try:
                # Método 2: subprocess con shell
                if path.startswith("shell:"):
                    subprocess.Popen(f'explorer "{path}"', shell=True)
                else:
                    subprocess.Popen(f'start "" "{path}"', shell=True)
                return True
            except:
                try:
                    # Método 3: ejecución directa
                    subprocess.Popen([path], shell=False)
                    return True
                except:
                    return False
    
    def launch_universal(self, app_name: str) -> Dict:
        """Intenta lanzar la aplicación usando múltiples estrategias"""
        app_name = app_name.strip()
        app_lower = app_name.lower()
        
        # 1. Verificar cache
        if app_lower in self.app_cache:
            cached_path = self.app_cache[app_lower]
            if os.path.exists(cached_path):
                if self.launch_with_priority(cached_path):
                    return {"success": True, "path": cached_path, "method": "cache"}
        
        # 2. Si es URL
        if app_lower.startswith(('http://', 'https://')):
            webbrowser.open(app_name)
            return {"success": True, "path": app_name, "method": "url"}
        
        # 3. Si es ruta de archivo o carpeta
        if os.path.exists(app_name):
            os.startfile(app_name)
            return {"success": True, "path": app_name, "method": "direct_path"}
        
        # 4. Carpetas virtuales del sistema
        virtual_folders = {
            "desktop": "Desktop", "escritorio": "Desktop",
            "downloads": "Downloads", "descargas": "Downloads",
            "documents": "Documents", "documentos": "Documents",
            "pictures": "Pictures", "imagenes": "Pictures",
            "music": "Music", "musica": "Music",
            "videos": "Videos"
        }
        
        if app_lower in virtual_folders:
            folder_path = os.path.join(os.path.expanduser("~"), virtual_folders[app_lower])
            if os.path.exists(folder_path):
                os.startfile(folder_path)
                return {"success": True, "path": folder_path, "method": "virtual_folder"}
        
        # 5. Comandos del sistema
        system_commands = {
            "notepad": "notepad.exe", "bloc de notas": "notepad.exe",
            "calc": "calc.exe", "calculadora": "calc.exe",
            "cmd": "cmd.exe", "terminal": "powershell.exe",
            "powershell": "powershell.exe", "paint": "mspaint.exe",
            "taskmgr": "taskmgr.exe", "administrador de tareas": "taskmgr.exe",
            "explorer": "explorer.exe", "explorador": "explorer.exe",
            "regedit": "regedit.exe", "editor de registro": "regedit.exe",
            "control": "control.exe", "panel de control": "control.exe"
        }
        
        if app_lower in system_commands:
            cmd = system_commands[app_lower]
            subprocess.Popen(cmd, shell=True)
            return {"success": True, "path": cmd, "method": "system_command"}
        
        # 6. Buscar en menú inicio (más rápido)
        start_menu_path = self.find_app_start_menu(app_name)
        if start_menu_path:
            if self.launch_with_priority(start_menu_path):
                self.app_cache[app_lower] = start_menu_path
                return {"success": True, "path": start_menu_path, "method": "start_menu"}
        
        # 7. Buscar en registro de Windows
        registry_path = self.find_app_registry(app_name)
        if registry_path:
            if self.launch_with_priority(registry_path):
                self.app_cache[app_lower] = registry_path
                return {"success": True, "path": registry_path, "method": "registry"}
        
        # 8. Buscar en Program Files
        program_files_path = self.find_app_program_files(app_name)
        if program_files_path:
            if self.launch_with_priority(program_files_path):
                self.app_cache[app_lower] = program_files_path
                return {"success": True, "path": program_files_path, "method": "program_files"}
        
        # 9. Usar comando WHERE (PATH)
        where_path = self.find_app_where(app_name)
        if where_path:
            if self.launch_with_priority(where_path):
                self.app_cache[app_lower] = where_path
                return {"success": True, "path": where_path, "method": "where_command"}
        
        # 10. Apps de Microsoft Store
        store_path = self.find_app_windows_store(app_name)
        if store_path:
            if self.launch_with_priority(store_path):
                self.app_cache[app_lower] = store_path
                return {"success": True, "path": store_path, "method": "windows_store"}
        
        # 11. Último recurso: intentar ejecutar directamente
        try:
            subprocess.Popen(app_name, shell=True)
            return {"success": True, "path": app_name, "method": "direct_execution"}
        except:
            pass
        
        return {"success": False, "path": None, "method": None}

# Función principal (compatible con tu sistema)
def open_app(parameters: dict, response=None, player=None) -> str:
    """
    Abre CUALQUIER aplicación, juego, URL o archivo.
    
    Parámetros:
    - app_name: Nombre de la app, URL, o ruta (requerido)
    - force: True/False - Forzar búsqueda aunque esté en cache
    - method: "auto", "start_menu", "registry", "program_files" - Método específico
    """
    app_name = parameters.get("app_name", "").strip()
    
    if not app_name:
        return "❌ Error: Necesito el nombre de la aplicación o URL (parámetro 'app_name')"
    
    # Opciones adicionales
    force = parameters.get("force", False)
    
    # Crear launcher
    launcher = SuperAppLauncher()
    
    # Si force es True, limpiar cache para este app
    if force and app_name.lower() in launcher.app_cache:
        del launcher.app_cache[app_name.lower()]
    
    # Intentar lanzar
    result = launcher.launch_universal(app_name)
    
    if result["success"]:
        method_names = {
            "cache": "⚡ caché (rápido)",
            "url": "🌐 navegador web",
            "direct_path": "📁 ruta directa",
            "virtual_folder": "📂 carpeta del sistema",
            "system_command": "🖥️ comando del sistema",
            "start_menu": "⭐ menú inicio",
            "registry": "📋 registro de Windows",
            "program_files": "💿 Program Files",
            "where_command": "🔍 variable PATH",
            "windows_store": "🏪 Microsoft Store",
            "direct_execution": "🎯 ejecución directa"
        }
        
        method_text = method_names.get(result["method"], result["method"])
        
        msg = f"✅ Abriendo '{app_name}' ({method_text})"
        
        if player:
            player.write_log(f"🚀 {msg} | Ruta: {result['path']}")
        
        return msg
    else:
        msg = f"❌ No pude encontrar o abrir '{app_name}'. Verifica el nombre o la ruta."
        
        # Sugerencias útiles
        if " " in app_name and not app_name.endswith(('.exe', '.lnk')):
            msg += f"\n💡 Sugerencia: Prueba con el nombre exacto (ej: '{app_name.lower().replace(' ', '')}')"
        
        if player:
            player.write_log(f"⚠️ {msg}")
        
        return msg

# Funciones adicionales útiles
def list_installed_apps() -> str:
    """Lista aplicaciones instaladas (útil para debugging)"""
    try:
        result = subprocess.run(
            'powershell -command "Get-StartApps | Select-Object -First 20 Name"',
            shell=True, capture_output=True, text=True, timeout=5
        )
        return f"📱 Apps instaladas:\n{result.stdout}"
    except:
        return "No se pudieron listar las apps"

def open_app_advanced(app_name: str, method: str = "auto") -> str:
    """
    Versión avanzada con método específico
    
    Métodos disponibles:
    - "auto": Detección automática
    - "start_menu": Solo menú inicio
    - "registry": Solo registro
    - "program_files": Solo Program Files
    - "store": Solo Microsoft Store
    """
    launcher = SuperAppLauncher()
    
    if method == "start_menu":
        path = launcher.find_app_start_menu(app_name)
    elif method == "registry":
        path = launcher.find_app_registry(app_name)
    elif method == "program_files":
        path = launcher.find_app_program_files(app_name)
    elif method == "store":
        path = launcher.find_app_windows_store(app_name)
    else:
        result = launcher.launch_universal(app_name)
        return f"Método {result.get('method', 'desconocido')}: {result.get('path', 'No encontrado')}"
    
    if path:
        launcher.launch_with_priority(path)
        return f"✅ Abierto con método {method}: {path}"
    else:
        return f"❌ No encontrado con método {method}"

# Prueba rápida
if __name__ == "__main__":
    # Probar con diferentes apps
    test_apps = ["notepad", "calculadora", "spotify", "discord", "chrome", "minecraft"]
    
    print("🧪 Probando SuperAppLauncher...\n")
    for app in test_apps:
        result = open_app({"app_name": app})
        print(f"📱 {app}: {result}")