"""
download_manager.py — Gestor de descargas e instalaciones para ILUM
============================================================
Soporta:
- Descarga de archivos desde URLs
- Instalación de software mediante Winget
- Base de datos de aplicaciones populares (Steam, Epic, etc.)
- Escaneo antivirus automático
- Detección inteligente de aplicaciones
"""

import os
import requests
import urllib.parse
from pathlib import Path
import subprocess
import shutil
import json
import time
import webbrowser
from typing import Dict, Optional, List, Tuple

# ============================================================
#  BASE DE DATOS DE APLICACIONES POPULARES
# ============================================================

# Diccionario de aplicaciones populares con sus nombres oficiales
# para Winget, URLs de descarga y categorías
POPULAR_APPS: Dict[str, Dict] = {
    # ========== JUEGOS Y PLATAFORMAS ==========
    "steam": {
        "winget": "Valve.Steam",
        "url": "https://store.steampowered.com/about/",
        "category": "games",
        "description": "Plataforma de juegos Steam"
    },
    "epic games": {
        "winget": "EpicGames.EpicGamesLauncher",
        "url": "https://www.epicgames.com/store/download",
        "category": "games",
        "description": "Launcher de Epic Games"
    },
    "rockstar games": {
        "winget": "RockstarGames.Launcher",
        "url": "https://rockstargames.com/launcher",
        "category": "games",
        "description": "Launcher de Rockstar Games"
    },
    "battlenet": {
        "winget": "Blizzard.BattleNet",
        "url": "https://www.blizzard.com/download",
        "category": "games",
        "description": "Launcher de Battle.net"
    },
    "riot games": {
        "winget": "RiotGames.LeagueOfLegends",
        "url": "https://www.riotgames.com/download",
        "category": "games",
        "description": "Launcher de Riot Games"
    },
    "gog": {
        "winget": "GOG.Galaxy",
        "url": "https://www.gog.com/galaxy",
        "category": "games",
        "description": "Launcher de GOG Galaxy"
    },
    "ubisoft connect": {
        "winget": "Ubisoft.Connect",
        "url": "https://ubisoftconnect.com/download",
        "category": "games",
        "description": "Launcher de Ubisoft Connect"
    },
    "ea app": {
        "winget": "EA.EADesktop",
        "url": "https://www.ea.com/ea-app",
        "category": "games",
        "description": "Launcher de EA App"
    },
    "minecraft": {
        "winget": "Mojang.MinecraftLauncher",
        "url": "https://www.minecraft.net/download",
        "category": "games",
        "description": "Launcher de Minecraft"
    },
    
    # ========== HERRAMIENTAS DE DESARROLLO ==========
    "visual studio code": {
        "winget": "Microsoft.VisualStudioCode",
        "url": "https://code.visualstudio.com/download",
        "category": "development",
        "description": "Editor de código VS Code"
    },
    "visual studio": {
        "winget": "Microsoft.VisualStudio.2022.Community",
        "url": "https://visualstudio.microsoft.com/downloads",
        "category": "development",
        "description": "IDE Visual Studio 2022"
    },
    "python": {
        "winget": "Python.Python.3.12",
        "url": "https://www.python.org/downloads",
        "category": "development",
        "description": "Python 3.12"
    },
    "git": {
        "winget": "Git.Git",
        "url": "https://git-scm.com/download/win",
        "category": "development",
        "description": "Git para control de versiones"
    },
    "nodejs": {
        "winget": "OpenJS.NodeJS",
        "url": "https://nodejs.org/download",
        "category": "development",
        "description": "Node.js runtime"
    },
    "docker": {
        "winget": "Docker.DockerDesktop",
        "url": "https://www.docker.com/products/docker-desktop",
        "category": "development",
        "description": "Docker Desktop"
    },
    "postman": {
        "winget": "Postman.Postman",
        "url": "https://www.postman.com/downloads",
        "category": "development",
        "description": "Postman API Client"
    },
    "github desktop": {
        "winget": "GitHub.GitHubDesktop",
        "url": "https://desktop.github.com/download",
        "category": "development",
        "description": "GitHub Desktop"
    },
    
    # ========== HERRAMIENTAS DE DISEÑO ==========
    "blender": {
        "winget": "BlenderFoundation.Blender",
        "url": "https://www.blender.org/download",
        "category": "design",
        "description": "Blender 3D"
    },
    "gimp": {
        "winget": "GIMP.GIMP",
        "url": "https://www.gimp.org/downloads",
        "category": "design",
        "description": "GIMP - Editor de imágenes"
    },
    "inkscape": {
        "winget": "Inkscape.Inkscape",
        "url": "https://inkscape.org/release",
        "category": "design",
        "description": "Inkscape - Diseño vectorial"
    },
    "krita": {
        "winget": "Krita.Krita",
        "url": "https://krita.org/download",
        "category": "design",
        "description": "Krita - Dibujo digital"
    },
    
    # ========== PRODUCTIVIDAD ==========
    "notion": {
        "winget": "Notion.Notion",
        "url": "https://www.notion.so/desktop",
        "category": "productivity",
        "description": "Notion - Notas y organización"
    },
    "obsidian": {
        "winget": "Obsidian.Obsidian",
        "url": "https://obsidian.md/download",
        "category": "productivity",
        "description": "Obsidian - Notas en Markdown"
    },
    "todoist": {
        "winget": "Todoist.Todoist",
        "url": "https://todoist.com/download",
        "category": "productivity",
        "description": "Todoist - Gestor de tareas"
    },
    "clickup": {
        "winget": "ClickUp.ClickUp",
        "url": "https://clickup.com/download",
        "category": "productivity",
        "description": "ClickUp - Gestor de proyectos"
    },
    "slack": {
        "winget": "SlackTechnologies.Slack",
        "url": "https://slack.com/downloads",
        "category": "productivity",
        "description": "Slack - Comunicación empresarial"
    },
    "teams": {
        "winget": "Microsoft.Teams",
        "url": "https://www.microsoft.com/microsoft-teams/download",
        "category": "productivity",
        "description": "Microsoft Teams"
    },
    "zoom": {
        "winget": "Zoom.Zoom",
        "url": "https://zoom.us/download",
        "category": "productivity",
        "description": "Zoom - Videoconferencias"
    },
    "discord": {
        "winget": "Discord.Discord",
        "url": "https://discord.com/download",
        "category": "productivity",
        "description": "Discord - Comunicación"
    },
    
    # ========== NAVEGADORES ==========
    "chrome": {
        "winget": "Google.Chrome",
        "url": "https://www.google.com/chrome",
        "category": "browser",
        "description": "Google Chrome"
    },
    "firefox": {
        "winget": "Mozilla.Firefox",
        "url": "https://www.mozilla.org/firefox/download",
        "category": "browser",
        "description": "Mozilla Firefox"
    },
    "edge": {
        "winget": "Microsoft.Edge",
        "url": "https://www.microsoft.com/edge/download",
        "category": "browser",
        "description": "Microsoft Edge"
    },
    "opera": {
        "winget": "Opera.Opera",
        "url": "https://www.opera.com/download",
        "category": "browser",
        "description": "Opera Browser"
    },
    "brave": {
        "winget": "Brave.Brave",
        "url": "https://brave.com/download",
        "category": "browser",
        "description": "Brave Browser"
    },
    
    # ========== UTILIDADES ==========
    "7zip": {
        "winget": "7zip.7zip",
        "url": "https://www.7-zip.org/download",
        "category": "utilities",
        "description": "7-Zip - Compresor de archivos"
    },
    "winrar": {
        "winget": "RARLab.WinRAR",
        "url": "https://www.win-rar.com/download",
        "category": "utilities",
        "description": "WinRAR - Compresor de archivos"
    },
    "vlc": {
        "winget": "VideoLAN.VLC",
        "url": "https://www.videolan.org/vlc/download",
        "category": "utilities",
        "description": "VLC Media Player"
    },
    "spotify": {
        "winget": "Spotify.Spotify",
        "url": "https://www.spotify.com/download",
        "category": "utilities",
        "description": "Spotify - Música"
    },
    "foobar2000": {
        "winget": "PeterPawlowski.foobar2000",
        "url": "https://www.foobar2000.org/download",
        "category": "utilities",
        "description": "foobar2000 - Reproductor de audio"
    },
    "notepad++": {
        "winget": "Notepad++.Notepad++",
        "url": "https://notepad-plus-plus.org/downloads",
        "category": "utilities",
        "description": "Notepad++ - Editor de texto"
    },
    "everything": {
        "winget": "voidtools.Everything",
        "url": "https://www.voidtools.com/downloads",
        "category": "utilities",
        "description": "Everything - Búsqueda de archivos"
    },
    "powertoys": {
        "winget": "Microsoft.PowerToys",
        "url": "https://github.com/microsoft/PowerToys/releases",
        "category": "utilities",
        "description": "Microsoft PowerToys"
    },
    "sharex": {
        "winget": "ShareX.ShareX",
        "url": "https://getsharex.com/download",
        "category": "utilities",
        "description": "ShareX - Capturas de pantalla"
    },
    "greenshot": {
        "winget": "Greenshot.Greenshot",
        "url": "https://getgreenshot.org/download",
        "category": "utilities",
        "description": "Greenshot - Capturas de pantalla"
    },
    "obs studio": {
        "winget": "OBSProject.OBSStudio",
        "url": "https://obsproject.com/download",
        "category": "utilities",
        "description": "OBS Studio - Grabación de pantalla"
    },
    
    # ========== SEGURIDAD ==========
    "malwarebytes": {
        "winget": "Malwarebytes.Malwarebytes",
        "url": "https://www.malwarebytes.com/download",
        "category": "security",
        "description": "Malwarebytes - Antivirus"
    },
    "bitdefender": {
        "winget": "Bitdefender.Bitdefender",
        "url": "https://www.bitdefender.com/download",
        "category": "security",
        "description": "Bitdefender - Antivirus"
    },
}

# ============================================================
#  FUNCIONES AUXILIARES
# ============================================================

def get_app_info(app_name: str) -> Optional[Dict]:
    """Busca información de una aplicación por nombre (case-insensitive)"""
    app_name_lower = app_name.lower()
    
    # 1. Exact match
    if app_name_lower in POPULAR_APPS:
        return POPULAR_APPS[app_name_lower]
    
    # 2. Partial match
    for key, info in POPULAR_APPS.items():
        if key in app_name_lower or app_name_lower in key:
            return info
        
        # Buscar por descripción
        if info.get("description", "").lower():
            if app_name_lower in info["description"].lower():
                return info
    
    return None

def list_apps_by_category(category: str = None) -> str:
    """Lista todas las aplicaciones disponibles por categoría"""
    if category:
        apps = {k: v for k, v in POPULAR_APPS.items() if v.get("category") == category}
        if not apps:
            return f"No hay aplicaciones en la categoría '{category}'"
    else:
        apps = POPULAR_APPS
    
    result = "📋 Aplicaciones disponibles en la base de datos de ILUM:\n\n"
    
    # Agrupar por categoría
    categories = {}
    for name, info in apps.items():
        cat = info.get("category", "otros")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(f"   • {name.title()} - {info.get('description', '')}")
    
    for cat, items in sorted(categories.items()):
        result += f"📁 {cat.upper()}:\n"
        result += "\n".join(items) + "\n\n"
    
    return result

def search_app(query: str) -> str:
    """Busca aplicaciones por nombre o descripción"""
    query_lower = query.lower()
    matches = []
    
    for name, info in POPULAR_APPS.items():
        if query_lower in name or query_lower in info.get("description", "").lower():
            matches.append(f"   • {name.title()} - {info.get('description', '')}")
    
    if not matches:
        return f"No se encontraron aplicaciones para '{query}'"
    
    result = f"🔍 Resultados para '{query}':\n" + "\n".join(matches)
    return result

# ============================================================
#  FUNCIONES DE INSTALACIÓN
# ============================================================

def install_with_winget(app_id: str, app_name: str, player=None) -> Tuple[bool, str]:
    """Instala una aplicación usando Winget"""
    try:
        winget_path = shutil.which("winget")
        if not winget_path:
            return False, "❌ Winget no está instalado en tu sistema. Descárgalo desde Microsoft Store."
        
        if player:
            player.write_log(f"📦 Instalando {app_name} mediante Winget...")
        
        cmd = [
            winget_path, 
            "install", 
            app_id, 
            "--silent", 
            "--accept-package-agreements", 
            "--accept-source-agreements"
        ]
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=300  # 5 minutos máximo
        )
        
        stdout_lower = result.stdout.lower()
        stderr_lower = result.stderr.lower()
        
        # Verificar éxito
        success_indicators = [
            "successfully", 
            "correctamente", 
            "installed", 
            "instalado",
            "already installed",
            "ya está instalado"
        ]
        
        for indicator in success_indicators:
            if indicator in stdout_lower or indicator in stderr_lower:
                return True, f"✅ {app_name} instalado correctamente."
        
        return False, f"⚠️ La instalación de {app_name} falló. Código: {result.returncode}"
        
    except subprocess.TimeoutExpired:
        return False, f"⏰ La instalación de {app_name} tardó demasiado. Verifica manualmente."
    except Exception as e:
        return False, f"❌ Error instalando {app_name}: {str(e)}"

def open_download_url(url: str, app_name: str, player=None) -> str:
    """Abre la URL de descarga en el navegador"""
    try:
        if player:
            player.write_log(f"🌐 Abriendo página de descarga para {app_name}...")
        
        webbrowser.open(url)
        return f"✅ He abierto la página de descarga de {app_name} en tu navegador."
    except Exception as e:
        return f"❌ Error abriendo el navegador: {str(e)}"

# ============================================================
#  FUNCIONES DE DESCARGA DE ARCHIVOS
# ============================================================

def scan_with_defender(file_path: str, player=None) -> str:
    """Escanea un archivo con Windows Defender"""
    try:
        defender_path = r"C:\ProgramData\Microsoft\Windows Defender\Platform"
        if not os.path.exists(defender_path):
            return "⚠️ No se encontró Windows Defender."
            
        platform_dirs = [
            os.path.join(defender_path, d) 
            for d in os.listdir(defender_path) 
            if os.path.isdir(os.path.join(defender_path, d))
        ]
        
        if not platform_dirs:
            return "⚠️ No se encontró el motor de escaneo."
            
        mpcmdrun = None
        for d in sorted(platform_dirs, reverse=True):
            p = os.path.join(d, "MpCmdRun.exe")
            if os.path.exists(p):
                mpcmdrun = p
                break
                
        if not mpcmdrun:
            return "⚠️ No se encontró MpCmdRun.exe."
            
        if player:
            player.write_log("🔍 Analizando archivo con Windows Defender...")
            
        result = subprocess.run(
            [mpcmdrun, "-Scan", "-ScanType", "3", "-File", file_path],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=120
        )
        
        if result.returncode == 0:
            return "✅ Archivo seguro. No se detectaron amenazas."
        elif result.returncode == 2:
            return "⚠️ ¡PELIGRO! Se detectó MALWARE. Elimina el archivo inmediatamente."
        else:
            return f"⚠️ Escaneo completado con advertencias (Código {result.returncode})."
            
    except subprocess.TimeoutExpired:
        return "⏰ El escaneo tardó demasiado. Verifica manualmente."
    except Exception as e:
        return f"❌ Error en el escaneo: {str(e)}"

def download_file(url: str, filename: str = "", player=None) -> str:
    """Descarga un archivo desde una URL"""
    try:
        downloads_folder = str(Path.home() / "Downloads")
        
        if not filename:
            parsed_url = urllib.parse.urlparse(url)
            filename = os.path.basename(parsed_url.path)
            if not filename or "." not in filename:
                filename = f"descarga_{int(time.time())}.file"
        
        save_path = os.path.join(downloads_folder, filename)
        
        if player:
            player.write_log(f"📥 Descargando {filename}...")
        
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(save_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if player and total_size > 0:
                        progress = int((downloaded / total_size) * 100)
                        if progress % 10 == 0:
                            player.write_log(f"📥 Progreso: {progress}%")
        
        # Escanear con antivirus
        scan_result = scan_with_defender(save_path, player)
        
        return f"""✅ Archivo descargado exitosamente:
📁 Ruta: {save_path}
📊 Tamaño: {downloaded / 1024 / 1024:.2f} MB
🛡️ {scan_result}"""
        
    except requests.exceptions.RequestException as e:
        return f"❌ Error descargando archivo: {str(e)}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

# ============================================================
#  FUNCIÓN PRINCIPAL
# ============================================================

def web_download(parameters: dict, player=None) -> str:
    """
    Descarga e instala aplicaciones y archivos.
    
    Acciones soportadas:
    - download: Descargar archivo desde URL
    - install: Instalar aplicación usando Winget
    - search: Buscar aplicación en la base de datos
    - list: Listar aplicaciones disponibles
    - list_categories: Listar categorías
    """
    
    action = parameters.get("action", "download").lower()
    url = parameters.get("url", "")
    filename = parameters.get("filename", "")
    app_name = parameters.get("app_name", "")
    category = parameters.get("category", "")
    query = parameters.get("query", "")
    
    # ============================================================
    #  ACCIÓN: LISTAR APLICACIONES
    # ============================================================
    
    if action == "list":
        return list_apps_by_category(category)
    
    elif action == "list_categories":
        categories = set(info.get("category", "otros") for info in POPULAR_APPS.values())
        return "📁 Categorías disponibles:\n" + "\n".join(f"   • {cat}" for cat in sorted(categories))
    
    elif action == "search":
        if not query:
            return "❌ Error: Se requiere 'query' para buscar."
        return search_app(query)
    
    # ============================================================
    #  ACCIÓN: INSTALAR APLICACIÓN
    # ============================================================
    
    elif action == "install":
        if not app_name:
            return "❌ Error: Se requiere 'app_name' para instalar."
        
        app_info = get_app_info(app_name)
        
        if not app_info:
            # Buscar aplicaciones similares
            similar = search_app(app_name)
            return f"""❌ No encontré '{app_name}' en mi base de datos.
            
{similar}

Si quieres instalar una aplicación que no está en la lista, usa:
web_download('action': 'download', 'url': 'URL')"""
        
        # Instalar con Winget
        winget_id = app_info.get("winget")
        if not winget_id:
            return f"⚠️ No tengo un instalador automático para {app_info.get('description', app_name)}.\n\n{open_download_url(app_info.get('url', ''), app_name, player)}"
        
        success, message = install_with_winget(winget_id, app_name, player)
        
        if not success:
            # Fallback: abrir URL de descarga
            url_fallback = app_info.get("url", "")
            if url_fallback:
                message += f"\n\n{open_download_url(url_fallback, app_name, player)}"
        
        return message
    
    # ============================================================
    #  ACCIÓN: DESCARGAR ARCHIVO
    # ============================================================
    
    elif action == "download":
        if not url:
            # Si no hay URL, intentar buscar la aplicación
            if app_name:
                app_info = get_app_info(app_name)
                if app_info and app_info.get("url"):
                    return open_download_url(app_info["url"], app_name, player)
                return "❌ Error: No se proporcionó URL ni se encontró la aplicación."
            return "❌ Error: Se requiere 'url' para descargar."
        
        return download_file(url, filename, player)
    
    # ============================================================
    #  ACCIÓN POR DEFECTO
    # ============================================================
    
    else:
        return f"""❌ Acción '{action}' no reconocida.

Acciones disponibles:
   • download  - Descargar archivo desde URL
   • install   - Instalar aplicación (busca en la base de datos)
   • search    - Buscar aplicación en la base de datos
   • list      - Listar aplicaciones disponibles
   • list_categories - Listar categorías

Ejemplos:
   web_download('action': 'install', 'app_name': 'steam')
   web_download('action': 'search', 'query': 'editor')
   web_download('action': 'download', 'url': 'https://...')"""

# ============================================================
#  FUNCIÓN DE ESTADO
# ============================================================

def get_download_manager_status() -> str:
    """Verifica el estado del gestor de descargas"""
    status = []
    
    # Verificar Winget
    winget_path = shutil.which("winget")
    status.append(f"✅ Winget: {'Disponible' if winget_path else 'No disponible'}")
    
    # Verificar aplicaciones en la base de datos
    status.append(f"📦 Aplicaciones en base de datos: {len(POPULAR_APPS)}")
    
    # Categorías disponibles
    categories = set(info.get("category", "otros") for info in POPULAR_APPS.values())
    status.append(f"📁 Categorías: {', '.join(sorted(categories))}")
    
    return "\n".join(status)

# ============================================================
#  TEST / DEBUG
# ============================================================

if __name__ == "__main__":
    print("=== Download Manager Test ===")
    print(get_download_manager_status())
    
    print("\n--- Buscando Steam ---")
    print(search_app("steam"))
    
    print("\n--- Listando juegos ---")
    print(list_apps_by_category("games"))