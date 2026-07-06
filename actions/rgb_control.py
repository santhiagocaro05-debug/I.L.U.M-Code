"""
rgb_control.py — Control completo de iluminación RGB
Soporta: OpenRGB, periféricos, efectos, sincronización
"""

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    import psutil
except ImportError:
    psutil = None

# ─── CONFIGURACIÓN ──────────────────────────────────────────────────────────
RGB_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "rgb_config.json"

def _get_rgb_config() -> Dict:
    """Carga o crea la configuración RGB."""
    if RGB_CONFIG_PATH.exists():
        try:
            return json.loads(RGB_CONFIG_PATH.read_text(encoding="utf-8"))
        except:
            pass
    
    default = {
        "openrgb_path": "C:\\Program Files\\OpenRGB\\OpenRGB.exe",
        "default_color": "#00ff88",
        "default_brightness": 100,
        "devices": []
    }
    RGB_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    RGB_CONFIG_PATH.write_text(json.dumps(default, indent=2), encoding="utf-8")
    return default

def _save_rgb_config(config: Dict):
    """Guarda la configuración RGB."""
    RGB_CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")

def _is_openrgb_running() -> bool:
    """Verifica si OpenRGB está ejecutándose."""
    if not psutil:
        return False
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] and 'openrgb' in proc.info['name'].lower():
                return True
        except:
            continue
    return False

def _start_openrgb() -> bool:
    """Inicia OpenRGB si está instalado."""
    config = _get_rgb_config()
    openrgb_path = config.get("openrgb_path", "")
    
    if not openrgb_path or not os.path.exists(openrgb_path):
        return False
    
    try:
        subprocess.Popen([openrgb_path, "--server", "--noautoconnect"], 
                        creationflags=subprocess.CREATE_NO_WINDOW)
        time.sleep(2)
        return True
    except:
        return False

def _get_devices() -> List[Dict]:
    """
    Obtiene la lista de dispositivos RGB usando OpenRGB CLI.
    NOTA: Requiere OpenRGB con servidor SDK activado.
    """
    config = _get_rgb_config()
    
    # Si hay dispositivos guardados en configuración, usarlos
    if config.get("devices"):
        return config["devices"]
    
    # Intentar detectar con OpenRGB CLI
    try:
        # Usar el CLI de OpenRGB para listar dispositivos
        openrgb_path = config.get("openrgb_path", "")
        if not os.path.exists(openrgb_path):
            return []
        
        result = subprocess.run(
            [openrgb_path, "-l"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            return []
        
        # Parsear salida (formato: "ID: Nombre del dispositivo")
        devices = []
        for line in result.stdout.split('\n'):
            if ':' in line and not line.startswith(' '):
                parts = line.split(':', 1)
                if len(parts) == 2:
                    devices.append({
                        "id": parts[0].strip(),
                        "name": parts[1].strip()
                    })
        
        # Guardar dispositivos detectados
        config["devices"] = devices
        _save_rgb_config(config)
        return devices
        
    except Exception as e:
        print(f"[RGB] Error detectando dispositivos: {e}")
        return []

def _send_openrgb_command(command: List[str]) -> bool:
    """
    Envía un comando a OpenRGB via CLI.
    """
    config = _get_rgb_config()
    openrgb_path = config.get("openrgb_path", "")
    
    if not os.path.exists(openrgb_path):
        return False
    
    try:
        # Asegurar que OpenRGB está corriendo
        if not _is_openrgb_running():
            if not _start_openrgb():
                return False
        
        # Ejecutar comando
        full_cmd = [openrgb_path] + command
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
        
    except Exception as e:
        print(f"[RGB] Error ejecutando comando: {e}")
        return False

def _hex_to_rgb(hex_color: str) -> tuple:
    """Convierte color hex a RGB."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join(c*2 for c in hex_color)
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

# ─── FUNCIÓN PRINCIPAL ──────────────────────────────────────────────────────

def rgb_control(parameters: dict, player=None) -> str:
    """
    Control de iluminación RGB con soporte para OpenRGB.
    
    Acciones:
    - set_color: Cambia el color de todos los dispositivos
    - set_device_color: Cambia el color de un dispositivo específico
    - off: Apaga todas las luces RGB
    - on: Enciende todas las luces RGB
    - brightness: Ajusta el brillo (0-100)
    - effect: Aplica un efecto (rainbow, breathing, wave, etc.)
    - list: Lista dispositivos detectados
    - detect: Detecta dispositivos RGB
    - status: Estado del sistema RGB
    """
    
    action = parameters.get("action", "").lower().strip()
    color = parameters.get("color", "#00ff88")
    device = parameters.get("device", "")
    brightness = int(parameters.get("brightness", 100))
    effect = parameters.get("effect", "rainbow")
    
    # ─── MAPEO DE ACCIONES ──────────────────────────────────────────────────
    
    # 1. LISTAR DISPOSITIVOS
    if action == "list":
        devices = _get_devices()
        if not devices:
            return "⚠️ No se detectaron dispositivos RGB. Asegúrate de que OpenRGB esté instalado y ejecutándose."
        
        result = "📦 DISPOSITIVOS RGB DETECTADOS:\n" + "-" * 40 + "\n"
        for dev in devices:
            result += f"  • {dev.get('name', 'Desconocido')} (ID: {dev.get('id', '?')})\n"
        
        config = _get_rgb_config()
        result += "\n" + "-" * 40
        result += f"\n🔧 OpenRGB: {'✅ Activo' if _is_openrgb_running() else '❌ Inactivo'}"
        result += f"\n📁 Config: {RGB_CONFIG_PATH}"
        return result
    
    # 2. DETECTAR DISPOSITIVOS
    elif action == "detect":
        if player: player.write_log("🔍 Detectando dispositivos RGB...")
        
        config = _get_rgb_config()
        devices = _get_devices()
        
        if devices:
            config["devices"] = devices
            _save_rgb_config(config)
            return f"✅ Detectados {len(devices)} dispositivos RGB:\n" + "\n".join([f"  • {d['name']}" for d in devices])
        else:
            return "❌ No se detectaron dispositivos RGB. Verifica:\n1. OpenRGB está instalado\n2. OpenRGB está ejecutándose\n3. Tus dispositivos son compatibles"
    
    # 3. ESTADO
    elif action == "status":
        is_running = _is_openrgb_running()
        config = _get_rgb_config()
        devices = config.get("devices", [])
        
        return f"""
📊 ESTADO DEL SISTEMA RGB:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔌 OpenRGB: {'✅ Activo' if is_running else '❌ Inactivo'}
📦 Dispositivos: {len(devices)}
🎨 Color por defecto: {config.get('default_color', '#00ff88')}
💡 Brillo por defecto: {config.get('default_brightness', 100)}%

📋 Acciones disponibles:
  • set_color → Cambiar color global
  • set_device_color → Cambiar color de dispositivo
  • off → Apagar RGB
  • on → Encender RGB
  • brightness → Ajustar brillo
  • effect → Aplicar efecto
  • list → Listar dispositivos
  • detect → Detectar dispositivos
"""
    
    # 4. SET COLOR (GLOBAL)
    elif action in ["set_color", "color"]:
        if player: player.write_log(f"🎨 Cambiando color RGB a {color}...")
        
        try:
            r, g, b = _hex_to_rgb(color)
            
            # Usar OpenRGB CLI para cambiar color
            success = _send_openrgb_command(["-c", str(r), str(g), str(b)])
            
            if success:
                # Guardar color por defecto
                config = _get_rgb_config()
                config["default_color"] = color
                _save_rgb_config(config)
                return f"✅ Color RGB cambiado a {color}"
            else:
                return "❌ Error cambiando color. Asegúrate de que OpenRGB esté ejecutándose."
        except Exception as e:
            return f"❌ Error: {e}"
    
    # 5. SET DEVICE COLOR
    elif action == "set_device_color":
        if not device:
            return "❌ Se requiere 'device' (nombre o ID del dispositivo)"
        
        if player: player.write_log(f"🎨 Cambiando color de '{device}' a {color}...")
        
        try:
            r, g, b = _hex_to_rgb(color)
            
            # Buscar el dispositivo
            devices = _get_devices()
            target_id = None
            
            for d in devices:
                if device.lower() in d.get('name', '').lower() or device == d.get('id', ''):
                    target_id = d.get('id')
                    break
            
            if target_id is None:
                return f"❌ Dispositivo '{device}' no encontrado. Usa 'list' para ver los disponibles."
            
            success = _send_openrgb_command(["-d", str(target_id), "-c", str(r), str(g), str(b)])
            
            if success:
                return f"✅ Color de '{device}' cambiado a {color}"
            else:
                return "❌ Error cambiando color del dispositivo."
        except Exception as e:
            return f"❌ Error: {e}"
    
    # 6. APAGAR RGB
    elif action == "off":
        if player: player.write_log("🔴 Apagando luces RGB...")
        
        success = _send_openrgb_command(["-c", "0", "0", "0"])
        
        if success:
            return "✅ Luces RGB apagadas."
        else:
            return "❌ Error apagando luces RGB."
    
    # 7. ENCENDER RGB
    elif action == "on":
        if player: player.write_log("🟢 Encendiendo luces RGB...")
        
        config = _get_rgb_config()
        default_color = config.get("default_color", "#00ff88")
        r, g, b = _hex_to_rgb(default_color)
        
        success = _send_openrgb_command(["-c", str(r), str(g), str(b)])
        
        if success:
            return f"✅ Luces RGB encendidas (color: {default_color})"
        else:
            return "❌ Error encendiendo luces RGB."
    
    # 8. BRILLO
    elif action == "brightness":
        if brightness < 0 or brightness > 100:
            return "❌ El brillo debe estar entre 0 y 100."
        
        if player: player.write_log(f"💡 Ajustando brillo a {brightness}%...")
        
        # OpenRGB usa valor de 0-255 para brillo
        br_value = int(brightness * 2.55)
        success = _send_openrgb_command(["-b", str(br_value)])
        
        if success:
            config = _get_rgb_config()
            config["default_brightness"] = brightness
            _save_rgb_config(config)
            return f"✅ Brillo ajustado a {brightness}%"
        else:
            return "❌ Error ajustando brillo."
    
    # 9. EFECTOS
    elif action == "effect":
        effects = {
            "rainbow": "arco iris",
            "breathing": "respiración",
            "wave": "onda",
            "flash": "destello",
            "off": "apagado",
            "static": "estático"
        }
        
        if effect not in effects:
            return f"❌ Efecto '{effect}' no disponible. Opciones: {', '.join(effects.keys())}"
        
        if player: player.write_log(f"🎭 Aplicando efecto: {effects[effect]}...")
        
        # OpenRGB no tiene efectos por CLI directamente
        # Esto es un placeholder - se necesita API para efectos reales
        return f"⚠️ Efecto '{effect}' requiere la API de OpenRGB. Próximamente disponible.\n" + \
               "Sugerencia: Usa 'set_color' para colores personalizados."
    
    # 10. HELP
    else:
        return """
🎯 RGB CONTROL - Comandos disponibles:

🎨 Colores:
  • set_color → Cambiar color global (todos los dispositivos)
  • set_device_color → Cambiar color de un dispositivo específico
  • on → Encender RGB (recupera último color)
  • off → Apagar RGB

💡 Brillo y efectos:
  • brightness → Ajustar brillo (0-100)
  • effect → Aplicar efecto (rainbow, breathing, wave, flash, static)

📋 Gestión:
  • list → Listar dispositivos detectados
  • detect → Detectar dispositivos RGB
  • status → Estado del sistema

📝 Ejemplos:
  {"action": "set_color", "color": "#ff0000"}
  {"action": "set_device_color", "device": "teclado", "color": "#00ff88"}
  {"action": "brightness", "brightness": 50}
  {"action": "effect", "effect": "rainbow"}
  {"action": "list"}
  {"action": "status"}

🔧 REQUISITOS:
  • OpenRGB instalado (https://openrgb.org)
  • OpenRGB ejecutándose con servidor SDK activado
"""
