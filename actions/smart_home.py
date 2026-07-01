# -*- coding: utf-8 -*-
"""
smart_home.py — Control de dispositivos inteligentes vía BLE (bleak) y Home Assistant.
Se basa en la configuración en `config/smart_home.json`:
{
  "devices": [
    {"name": "Luz Sala", "address": "AA:BB:CC:DD:EE:FF", "service_uuid": "0000180f-0000-1000-8000-00805f9b34fb", "characteristic_uuid": "00002a19-0000-1000-8000-00805f9b34fb"}
  ],
  "home_assistant": {"url": "http://192.168.1.100:8123", "token": "YOUR_LONG_LIVED_ACCESS_TOKEN"}
}

El módulo expone tres funciones principales:
- `discover_devices()` – busca dispositivos BLE cercanos (útil para añadir nuevos).
- `toggle_device(name: str, turn_on: bool)` – enciende/apaga el dispositivo mediante su característica.
- `call_home_assistant_service(service: str, entity_id: str, **data)` – llama a un servicio de HA vía REST.
"""

import asyncio
import json
from pathlib import Path

# BLE via bleak (async)
try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    BleakClient = None
    BleakScanner = None

import requests

CONFIG_PATH = Path("config/smart_home.json")

def load_config():
    if not CONFIG_PATH.exists():
        return {"devices": [], "home_assistant": {"url": "", "token": ""}}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[SmartHome] Error cargando configuración: {e}")
        return {"devices": [], "home_assistant": {"url": "", "token": ""}}

_config_cache = None

def get_config():
    global _config_cache
    if _config_cache is None:
        _config_cache = load_config()
    return _config_cache

# ---------------------------------------------------------------------------
# BLE Helpers
# ---------------------------------------------------------------------------
async def discover_devices(timeout: float = 5.0):
    """Escanea dispositivos BLE cercanos y devuelve una lista de dicts con nombre y dirección."""
    if BleakScanner is None:
        print("[SmartHome] bleak no está instalado, no se pueden escanear dispositivos BLE.")
        return []
    devices = await BleakScanner.discover(timeout=timeout)
    return [{"name": d.name or "<unknown>", "address": d.address} for d in devices]

async def _write_characteristic(address: str, char_uuid: str, value: bytes):
    async with BleakClient(address) as client:
        if not client.is_connected:
            raise RuntimeError(f"No se pudo conectar a {address}")
        await client.write_gatt_char(char_uuid, value, response=True)

def toggle_device(name: str, turn_on: bool) -> str:
    cfg = get_config()
    device = next((d for d in cfg.get("devices", []) if d.get("name") == name), None)
    if not device:
        return f"[SmartHome] Dispositivo '{name}' no encontrado en configuración."
    address = device.get("address")
    char_uuid = device.get("characteristic_uuid")
    if not address or not char_uuid:
        return f"[SmartHome] Configuración incompleta para '{name}'."
    value = b"\x01" if turn_on else b"\x00"
    try:
        asyncio.run(_write_characteristic(address, char_uuid, value))
        return f"[SmartHome] {'Encendido' if turn_on else 'Apagado'} '{name}'."
    except Exception as e:
        return f"[SmartHome] Error al togglear '{name}': {e}"

# ---------------------------------------------------------------------------
# Home Assistant integration (REST)
# ---------------------------------------------------------------------------
def call_home_assistant_service(service: str, entity_id: str, **data) -> str:
    cfg = get_config()
    ha_cfg = cfg.get("home_assistant", {})
    url = ha_cfg.get("url")
    token = ha_cfg.get("token")
    if not url or not token:
        return "[SmartHome] Home Assistant no está configurado."
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"entity_id": entity_id, **data}
    service_url = f"{url.rstrip('/')}/api/services/{service.replace('.', '/') }"
    try:
        resp = requests.post(service_url, headers=headers, json=payload, timeout=5)
        if resp.status_code == 200:
            return f"[SmartHome] Servicio '{service}' ejecutado para {entity_id}."
        else:
            return f"[SmartHome] Error {resp.status_code}: {resp.text}"
    except Exception as e:
        return f"[SmartHome] Excepción al llamar al servicio: {e}"

def smart_home(parameters: dict, player=None) -> str:
    """Interface used by ILUM para controlar dispositivos.
    `parameters` puede contener:
    - `action`: "toggle" | "ha_service"
    - `device`: nombre del dispositivo (para toggle)
    - `state`: bool (True=encender, False=apagar)
    - `service`: servicio HA (ej. "light.toggle")
    - `entity_id`: entidad HA
    """
    action = parameters.get("action")
    if action == "toggle":
        name = parameters.get("device")
        state = parameters.get("state", True)
        return toggle_device(name, bool(state))
    elif action == "ha_service":
        service = parameters.get("service")
        entity_id = parameters.get("entity_id")
        extra = {k: v for k, v in parameters.items() if k not in {"action", "service", "entity_id"}}
        return call_home_assistant_service(service, entity_id, **extra)
    else:
        return "[SmartHome] Acción no soportada."
