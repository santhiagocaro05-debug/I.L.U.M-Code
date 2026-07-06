# -*- coding: utf-8 -*-
"""
smart_home.py — Control de dispositivos inteligentes: luces/enchufes BLE,
TVs (Android TV / Google TV / Fire TV) y celulares Android, además de
Home Assistant (Hue, Tuya, LIFX, Yeelight reales vía integración HA).

Configuración persistente en `config/smart_home.json`:
{
  "devices": [
    {"name": "Luz Sala", "type": "ble_light", "address": "AA:BB:CC:DD:EE:FF",
     "service_uuid": "...", "characteristic_uuid": "..."}
  ],
  "tvs": [
    {"name": "TV Sala", "type": "android_tv", "address": "192.168.1.50:5555"}
  ],
  "phones": [
    {"name": "Mi Celular", "type": "android_phone", "address": "192.168.1.55:5555"}
  ],
  "home_assistant": {"url": "http://192.168.1.100:8123", "token": "YOUR_TOKEN"}
}

NOTA IMPORTANTE sobre "Bluetooth":
- Para luces/enchufes BLE genéricos usamos Bluetooth Low Energy real (bleak):
  escaneo, emparejamiento/conexión y escritura de características GATT.
- Para TVs Android/Google TV y celulares Android, el control real y confiable
  NO se hace sobre el perfil clásico de Bluetooth (Windows no expone AVRCP/HID
  de forma programable de manera simple), sino vía ADB (Android Debug Bridge),
  que es el estándar de la industria para "mandar" un Android TV o teléfono
  Android desde una PC — funciona por red local, no requiere cables.
  Se necesita tener 'adb.exe' en el PATH o en config/platform-tools/.
"""

import asyncio
import json
import shutil
import subprocess
from pathlib import Path

try:
    from bleak import BleakClient, BleakScanner
    HAS_BLEAK = True
except ImportError:
    BleakClient = None
    BleakScanner = None
    HAS_BLEAK = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    requests = None
    HAS_REQUESTS = False

# ── Resolución de rutas compatible con exe compilado ────────────────────────
try:
    from memory.config_manager import BASE_DIR
except Exception:
    import sys
    BASE_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent

CONFIG_PATH = BASE_DIR / "config" / "smart_home.json"

DEFAULT_CFG = {
    "devices": [],
    "tvs": [],
    "phones": [],
    "home_assistant": {"url": "", "token": ""},
}


# ═══════════════════════════════════════════════════════════════════════════
#  Configuración
# ═══════════════════════════════════════════════════════════════════════════

def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return dict(DEFAULT_CFG)
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        for k, v in DEFAULT_CFG.items():
            data.setdefault(k, v)
        return data
    except Exception as e:
        print(f"[SmartHome] Error cargando configuración: {e}")
        return dict(DEFAULT_CFG)


def save_config(cfg: dict) -> bool:
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception as e:
        print(f"[SmartHome] Error guardando configuración: {e}")
        return False


def _find(cfg: dict, key: str, name: str):
    name_lower = (name or "").strip().lower()
    for item in cfg.get(key, []):
        if item.get("name", "").strip().lower() == name_lower:
            return item
    return None


# ═══════════════════════════════════════════════════════════════════════════
#  BLE — luces / enchufes inteligentes
# ═══════════════════════════════════════════════════════════════════════════

async def _ble_scan(timeout: float = 6.0) -> list:
    if not HAS_BLEAK:
        return []
    found = await BleakScanner.discover(timeout=timeout)
    return [{"name": d.name or "<sin nombre>", "address": d.address, "rssi": getattr(d, "rssi", None)} for d in found]


async def _ble_write(address: str, char_uuid: str, value: bytes, timeout: float = 8.0):
    async with BleakClient(address, timeout=timeout) as client:
        if not client.is_connected:
            raise RuntimeError("No se pudo establecer conexión BLE.")
        await client.write_gatt_char(char_uuid, value, response=True)


def ble_scan_devices() -> str:
    if not HAS_BLEAK:
        return "Bluetooth LE no disponible: instalá la librería 'bleak' (pip install bleak)."
    try:
        found = asyncio.run(_ble_scan())
    except Exception as e:
        return f"Error escaneando Bluetooth: {e}"
    if not found:
        return "No se encontraron dispositivos Bluetooth cercanos. Asegurate de que el Bluetooth esté encendido."
    lines = [f"- {d['name']}  ({d['address']})" for d in found]
    return "Dispositivos Bluetooth encontrados:\n" + "\n".join(lines) + \
           "\n\nPara agregarlo usá action='pair' con device=<nombre> y address=<dirección>."


def ble_pair_device(name: str, address: str, characteristic_uuid: str = "", service_uuid: str = "") -> str:
    if not name or not address:
        return "Se necesita nombre y dirección MAC del dispositivo."
    cfg = load_config()
    if _find(cfg, "devices", name):
        return f"Ya existe un dispositivo BLE llamado '{name}'."
    cfg["devices"].append({
        "name": name,
        "type": "ble_light",
        "address": address,
        "characteristic_uuid": characteristic_uuid,
        "service_uuid": service_uuid,
    })
    if not save_config(cfg):
        return "Error guardando el dispositivo en la configuración."
    return f"Dispositivo '{name}' vinculado correctamente ({address})."


def ble_toggle(name: str, turn_on: bool) -> str:
    if not HAS_BLEAK:
        return "Bluetooth LE no disponible: instalá la librería 'bleak' (pip install bleak)."
    cfg = load_config()
    device = _find(cfg, "devices", name)
    if not device:
        return f"Dispositivo BLE '{name}' no encontrado. Usá action='pair' primero."
    address = device.get("address")
    char_uuid = device.get("characteristic_uuid")
    if not address or not char_uuid:
        return f"Falta 'characteristic_uuid' en la configuración de '{name}'. Consultá la app del fabricante."
    value = b"\x01" if turn_on else b"\x00"
    try:
        asyncio.run(_ble_write(address, char_uuid, value))
        return f"{'Encendido' if turn_on else 'Apagado'} '{name}' vía Bluetooth."
    except Exception as e:
        return f"Error controlando '{name}' por Bluetooth: {e}"


def ble_set_color(name: str, r: int, g: int, b: int) -> str:
    """Soporta el protocolo genérico de muchas tiras LED BLE (Govee/MagicLight-like):
    payload 0x56 R G B 0x00 0xF0 0xAA sobre la característica configurada."""
    if not HAS_BLEAK:
        return "Bluetooth LE no disponible: instalá la librería 'bleak' (pip install bleak)."
    cfg = load_config()
    device = _find(cfg, "devices", name)
    if not device:
        return f"Dispositivo BLE '{name}' no encontrado."
    address = device.get("address")
    char_uuid = device.get("characteristic_uuid")
    if not address or not char_uuid:
        return f"Falta 'characteristic_uuid' en la configuración de '{name}'."
    payload = bytes([0x56, max(0, min(r, 255)), max(0, min(g, 255)), max(0, min(b, 255)), 0x00, 0xF0, 0xAA])
    try:
        asyncio.run(_ble_write(address, char_uuid, payload))
        return f"Color de '{name}' cambiado a RGB({r},{g},{b})."
    except Exception as e:
        return f"Error cambiando color de '{name}': {e}"


def ble_set_brightness(name: str, percent: int) -> str:
    if not HAS_BLEAK:
        return "Bluetooth LE no disponible: instalá la librería 'bleak' (pip install bleak)."
    cfg = load_config()
    device = _find(cfg, "devices", name)
    if not device:
        return f"Dispositivo BLE '{name}' no encontrado."
    address = device.get("address")
    char_uuid = device.get("characteristic_uuid")
    if not address or not char_uuid:
        return f"Falta 'characteristic_uuid' en la configuración de '{name}'."
    percent = max(1, min(int(percent), 100))
    level = int(percent * 255 / 100)
    payload = bytes([0x53, level])  # protocolo genérico de brillo (varía según fabricante)
    try:
        asyncio.run(_ble_write(address, char_uuid, payload))
        return f"Brillo de '{name}' ajustado al {percent}%."
    except Exception as e:
        return f"Error ajustando brillo de '{name}': {e}"


# ═══════════════════════════════════════════════════════════════════════════
#  ADB — control de TVs Android / Google TV / Fire TV y celulares Android
# ═══════════════════════════════════════════════════════════════════════════

def _adb_path():
    exe = shutil.which("adb")
    if exe:
        return exe
    local = BASE_DIR / "config" / "platform-tools" / "adb.exe"
    if local.exists():
        return str(local)
    return None


def _adb_run(address: str, *args, timeout: int = 10):
    adb = _adb_path()
    if not adb:
        return False, ("No se encontró 'adb'. Descargá Android Platform Tools y colocá adb.exe "
                        "en el PATH o en config/platform-tools/.")
    flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    try:
        subprocess.run([adb, "connect", address], capture_output=True, timeout=8, creationflags=flags)
        result = subprocess.run(
            [adb, "-s", address, *args],
            capture_output=True, text=True, timeout=timeout, creationflags=flags,
        )
        out = (result.stdout or "").strip() or (result.stderr or "").strip()
        return result.returncode == 0, out
    except subprocess.TimeoutExpired:
        return False, "Tiempo de espera agotado conectando por ADB."
    except Exception as e:
        return False, str(e)


ANDROID_KEYS = {
    "power": "KEYCODE_POWER", "home": "KEYCODE_HOME", "back": "KEYCODE_BACK",
    "up": "KEYCODE_DPAD_UP", "down": "KEYCODE_DPAD_DOWN",
    "left": "KEYCODE_DPAD_LEFT", "right": "KEYCODE_DPAD_RIGHT",
    "select": "KEYCODE_DPAD_CENTER", "ok": "KEYCODE_DPAD_CENTER",
    "play_pause": "KEYCODE_MEDIA_PLAY_PAUSE", "next": "KEYCODE_MEDIA_NEXT",
    "previous": "KEYCODE_MEDIA_PREVIOUS", "mute": "KEYCODE_VOLUME_MUTE",
    "volume_up": "KEYCODE_VOLUME_UP", "volume_down": "KEYCODE_VOLUME_DOWN",
    "menu": "KEYCODE_MENU",
}


def _resolve_target(cfg: dict, category: str, name: str):
    return _find(cfg, category, name)


def tv_power(name: str) -> str:
    cfg = load_config()
    tv = _resolve_target(cfg, "tvs", name)
    if not tv:
        return f"TV '{name}' no encontrada. Agregala primero con action='pair_tv'."
    ok, out = _adb_run(tv["address"], "shell", "input", "keyevent", ANDROID_KEYS["power"])
    return f"TV '{name}': comando de encendido/apagado enviado." if ok else f"Error controlando TV '{name}': {out}"


def tv_key(name: str, key: str) -> str:
    cfg = load_config()
    tv = _resolve_target(cfg, "tvs", name)
    if not tv:
        return f"TV '{name}' no encontrada."
    keycode = ANDROID_KEYS.get((key or "").strip().lower())
    if not keycode:
        return f"Tecla '{key}' no reconocida. Opciones: {', '.join(ANDROID_KEYS.keys())}."
    ok, out = _adb_run(tv["address"], "shell", "input", "keyevent", keycode)
    return f"TV '{name}': tecla '{key}' enviada." if ok else f"Error enviando tecla a '{name}': {out}"


def tv_volume(name: str, direction: str, steps: int = 1) -> str:
    cfg = load_config()
    tv = _resolve_target(cfg, "tvs", name)
    if not tv:
        return f"TV '{name}' no encontrada."
    keycode = ANDROID_KEYS["volume_up"] if direction == "up" else ANDROID_KEYS["volume_down"]
    for _ in range(max(1, steps)):
        ok, out = _adb_run(tv["address"], "shell", "input", "keyevent", keycode)
        if not ok:
            return f"Error ajustando volumen de '{name}': {out}"
    return f"Volumen de '{name}' ajustado ({direction}, x{steps})."


def tv_launch_app(name: str, package: str) -> str:
    cfg = load_config()
    tv = _resolve_target(cfg, "tvs", name)
    if not tv:
        return f"TV '{name}' no encontrada."
    ok, out = _adb_run(tv["address"], "shell", "monkey", "-p", package,
                        "-c", "android.intent.category.LAUNCHER", "1")
    return f"App '{package}' abierta en '{name}'." if ok else f"Error abriendo app en '{name}': {out}"


def add_tv(name: str, address: str) -> str:
    if not name or not address:
        return "Se necesita nombre y dirección IP:puerto de la TV (ej. 192.168.1.50:5555)."
    cfg = load_config()
    if _find(cfg, "tvs", name):
        return f"Ya existe una TV llamada '{name}'."
    cfg["tvs"].append({"name": name, "type": "android_tv", "address": address})
    if not save_config(cfg):
        return "Error guardando la TV."
    ok, out = _adb_run(address, "shell", "echo", "ok")
    status = "Conexión verificada." if ok else f"Guardada, pero no se pudo verificar la conexión: {out}"
    return f"TV '{name}' agregada ({address}). {status}"


def phone_action(name: str, action: str, value: str = "") -> str:
    cfg = load_config()
    phone = _resolve_target(cfg, "phones", name)
    if not phone:
        return f"Celular '{name}' no encontrado. Agregalo con action='pair_phone'."
    address = phone["address"]
    if action == "screen_on":
        ok, out = _adb_run(address, "shell", "input", "keyevent", "KEYCODE_WAKEUP")
        return f"Pantalla de '{name}' encendida." if ok else f"Error: {out}"
    if action == "screen_off":
        ok, out = _adb_run(address, "shell", "input", "keyevent", "KEYCODE_POWER")
        return f"Pantalla de '{name}' apagada." if ok else f"Error: {out}"
    if action == "volume_up":
        ok, out = _adb_run(address, "shell", "input", "keyevent", "KEYCODE_VOLUME_UP")
        return f"Volumen de '{name}' subido." if ok else f"Error: {out}"
    if action == "volume_down":
        ok, out = _adb_run(address, "shell", "input", "keyevent", "KEYCODE_VOLUME_DOWN")
        return f"Volumen de '{name}' bajado." if ok else f"Error: {out}"
    if action == "find":  # hace vibrar/sonar para encontrarlo
        ok, out = _adb_run(address, "shell", "media", "volume", "--stream", "3", "--set", "15")
        return f"Buscando '{name}' (volumen al máximo)." if ok else f"Error: {out}"
    if action == "open_app" and value:
        ok, out = _adb_run(address, "shell", "monkey", "-p", value,
                            "-c", "android.intent.category.LAUNCHER", "1")
        return f"App '{value}' abierta en '{name}'." if ok else f"Error: {out}"
    return f"Acción de celular no soportada: '{action}'."


def add_phone(name: str, address: str) -> str:
    if not name or not address:
        return "Se necesita nombre y dirección IP:puerto del celular (activá depuración ADB por WiFi)."
    cfg = load_config()
    if _find(cfg, "phones", name):
        return f"Ya existe un celular llamado '{name}'."
    cfg["phones"].append({"name": name, "type": "android_phone", "address": address})
    if not save_config(cfg):
        return "Error guardando el celular."
    ok, out = _adb_run(address, "shell", "echo", "ok")
    status = "Conexión verificada." if ok else f"Guardado, pero no se pudo verificar la conexión: {out}"
    return f"Celular '{name}' agregado ({address}). {status}"


# ═══════════════════════════════════════════════════════════════════════════
#  Home Assistant (Hue, Tuya, LIFX, Yeelight reales vía integración HA)
# ═══════════════════════════════════════════════════════════════════════════

def call_home_assistant_service(service: str, entity_id: str, **data) -> str:
    if not HAS_REQUESTS:
        return "Falta la librería 'requests' para usar Home Assistant."
    cfg = load_config()
    ha_cfg = cfg.get("home_assistant", {})
    url = ha_cfg.get("url")
    token = ha_cfg.get("token")
    if not url or not token:
        return ("Home Assistant no está configurado. Agregá 'url' y 'token' en "
                "config/smart_home.json bajo 'home_assistant'.")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"entity_id": entity_id, **data}
    service_url = f"{url.rstrip('/')}/api/services/{service.replace('.', '/')}"
    try:
        resp = requests.post(service_url, headers=headers, json=payload, timeout=6)
        if resp.status_code == 200:
            return f"Servicio '{service}' ejecutado para {entity_id}."
        return f"Home Assistant respondió {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return f"Error al llamar a Home Assistant: {e}"


# ═══════════════════════════════════════════════════════════════════════════
#  Listado / estado
# ═══════════════════════════════════════════════════════════════════════════

def list_all() -> str:
    cfg = load_config()
    parts = []
    if cfg["devices"]:
        parts.append("Luces/Enchufes BLE:\n" + "\n".join(f"  - {d['name']} ({d['address']})" for d in cfg["devices"]))
    if cfg["tvs"]:
        parts.append("TVs:\n" + "\n".join(f"  - {t['name']} ({t['address']})" for t in cfg["tvs"]))
    if cfg["phones"]:
        parts.append("Celulares:\n" + "\n".join(f"  - {p['name']} ({p['address']})" for p in cfg["phones"]))
    if not parts:
        return "No hay dispositivos configurados todavía. Usá action='scan' o 'pair'/'pair_tv'/'pair_phone'."
    return "\n\n".join(parts)


def setup_help() -> str:
    return (
        "Configuración de Smart Home:\n"
        "• Luces/enchufes Bluetooth: action='scan' para buscar, luego action='pair' con "
        "device=<nombre>, address=<MAC>, characteristic_uuid=<UUID de la app del fabricante>.\n"
        "• TVs Android/Google TV: activá 'Depuración por red' en la TV, luego action='pair_tv' "
        "con device=<nombre>, address=<IP:puerto, normalmente 5555>.\n"
        "• Celulares Android: activá 'Depuración por Wi-Fi' en Opciones de desarrollador, luego "
        "action='pair_phone' con device=<nombre>, address=<IP:puerto>.\n"
        "• Home Assistant (Hue/Tuya/LIFX/Yeelight): completá 'url' y 'token' en "
        "config/smart_home.json, luego action='ha_service'."
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Interfaz principal usada por NEXUS
# ═══════════════════════════════════════════════════════════════════════════

def smart_home(parameters: dict, player=None) -> str:
    p = parameters or {}
    action = (p.get("action") or "").strip().lower()
    name = p.get("device") or p.get("name") or ""

    # ── Descubrimiento y emparejamiento ────────────────────────────────
    if action == "scan":
        return ble_scan_devices()
    if action == "pair":
        return ble_pair_device(name, p.get("address", ""), p.get("characteristic_uuid", ""), p.get("service_uuid", ""))
    if action == "pair_tv":
        return add_tv(name, p.get("address", ""))
    if action == "pair_phone":
        return add_phone(name, p.get("address", ""))
    if action in ("list", "status"):
        return list_all()
    if action == "setup":
        return setup_help()

    # ── Luces / enchufes BLE ────────────────────────────────────────────
    if action in ("on", "toggle_on"):
        return ble_toggle(name, True)
    if action in ("off", "toggle_off"):
        return ble_toggle(name, False)
    if action == "toggle":
        state = p.get("state")
        return ble_toggle(name, bool(state) if state is not None else True)
    if action == "color":
        color = (p.get("color") or "").strip()
        rgb = _color_name_to_rgb(color)
        if not rgb:
            return f"No reconozco el color '{color}'. Usá un nombre común o formato #RRGGBB."
        return ble_set_color(name, *rgb)
    if action == "brightness":
        val = p.get("value", p.get("brightness", 100))
        try:
            return ble_set_brightness(name, int(val))
        except Exception:
            return "Valor de brillo inválido."

    # ── TVs ──────────────────────────────────────────────────────────
    if action == "tv_power":
        return tv_power(name)
    if action == "tv_key":
        return tv_key(name, p.get("key", ""))
    if action == "tv_volume":
        direction = "up" if str(p.get("direction", "up")).lower() in ("up", "subir") else "down"
        return tv_volume(name, direction, int(p.get("steps", 1)))
    if action == "tv_app":
        return tv_launch_app(name, p.get("package", ""))

    # ── Celulares ────────────────────────────────────────────────────
    if action in ("phone_screen_on", "phone_screen_off", "phone_volume_up", "phone_volume_down",
                  "phone_find", "phone_open_app"):
        mapped = {
            "phone_screen_on": "screen_on", "phone_screen_off": "screen_off",
            "phone_volume_up": "volume_up", "phone_volume_down": "volume_down",
            "phone_find": "find", "phone_open_app": "open_app",
        }[action]
        return phone_action(name, mapped, p.get("package", ""))

    # ── Home Assistant (compatibilidad con integraciones reales) ──────
    if action == "ha_service":
        service = p.get("service")
        entity_id = p.get("entity_id")
        extra = {k: v for k, v in p.items() if k not in {"action", "service", "entity_id", "device"}}
        if not service or not entity_id:
            return "Se necesita 'service' y 'entity_id' para llamar a Home Assistant."
        return call_home_assistant_service(service, entity_id, **extra)

    return (
        f"Acción no soportada: '{action}'. Usá action='setup' para ver cómo configurar dispositivos, "
        "o alguna de: scan, pair, pair_tv, pair_phone, list, on, off, color, brightness, "
        "tv_power, tv_key, tv_volume, tv_app, phone_screen_on/off, phone_volume_up/down, "
        "phone_find, phone_open_app, ha_service."
    )


_COLOR_NAMES = {
    "rojo": (255, 0, 0), "red": (255, 0, 0),
    "verde": (0, 255, 0), "green": (0, 255, 0),
    "azul": (0, 0, 255), "blue": (0, 0, 255),
    "blanco": (255, 255, 255), "white": (255, 255, 255),
    "cálido": (255, 180, 80), "calido": (255, 180, 80), "warm": (255, 180, 80),
    "amarillo": (255, 255, 0), "yellow": (255, 255, 0),
    "naranja": (255, 140, 0), "orange": (255, 140, 0),
    "morado": (160, 32, 240), "purple": (160, 32, 240), "violeta": (160, 32, 240),
    "rosa": (255, 105, 180), "pink": (255, 105, 180),
    "cyan": (0, 255, 255), "celeste": (0, 255, 255),
}


def _color_name_to_rgb(color: str):
    if not color:
        return None
    color = color.strip().lower()
    if color.startswith("#") and len(color) == 7:
        try:
            return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))
        except Exception:
            return None
    return _COLOR_NAMES.get(color)