"""
Vault Memory Module for ILUM
=============================
Permite guardar contraseñas, secretos y recuerdos explícitos que el usuario le pida a ILUM.
"""

import json
import os
from pathlib import Path

VAULT_FILE = Path("config/vault_memory.json")

def _load_vault() -> dict:
    if VAULT_FILE.exists():
        try:
            return json.loads(VAULT_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def _save_vault(data: dict):
    VAULT_FILE.parent.mkdir(parents=True, exist_ok=True)
    VAULT_FILE.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")

def vault(parameters: dict, player=None) -> str:
    """
    Controla la bóveda de memoria a largo plazo.
    Acciones: save, retrieve, list, delete
    """
    action = parameters.get("action", "save").lower()
    key = parameters.get("key", "").strip()
    value = parameters.get("value", "")

    data = _load_vault()

    if action == "save":
        if not key or not value:
            return "❌ Error: Necesito una clave (ej: 'contraseña de netflix') y un valor para guardar."
        data[key] = value
        _save_vault(data)
        return f"✅ Entendido. He guardado '{key}' en la bóveda de memoria segura."

    elif action == "retrieve":
        if not key:
            return "❌ Error: ¿Qué clave quieres que busque en la bóveda?"
        
        # Búsqueda difusa básica
        for k, v in data.items():
            if key.lower() in k.lower():
                return f"🔓 Encontré '{k}': {v}"
        return f"❌ No encontré nada relacionado con '{key}' en la bóveda."

    elif action == "list":
        if not data:
            return "La bóveda de memoria está vacía."
        keys = ", ".join(data.keys())
        return f"🔐 En la bóveda tengo guardado: {keys}"

    elif action == "delete":
        if key in data:
            del data[key]
            _save_vault(data)
            return f"🗑️ He eliminado '{key}' de la bóveda de memoria."
        return f"❌ No pude eliminar '{key}' porque no lo encontré."

    return "❌ Acción de bóveda no reconocida."
