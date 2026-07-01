"""
Auto Healer (Hotpatching para ILUM EXE)
=======================================
Permite sanar herramientas en tiempo de ejecución descargando parches
sin necesidad de recompilar el archivo ejecutable.
"""

import os
import sys
import importlib.util
from pathlib import Path
import traceback

HOTPATCH_DIR = Path("config/hotpatches")

def apply_hotpatch(module_name: str, player=None):
    """
    Intenta cargar un módulo desde la carpeta de hotpatches.
    Retorna la función parcheada si tiene éxito, None si no.
    """
    try:
        patch_file = HOTPATCH_DIR / f"{module_name}.py"
        if not patch_file.exists():
            return None
            
        spec = importlib.util.spec_from_file_location(f"hotpatch_{module_name}", str(patch_file))
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # Retorna la función principal que tiene el mismo nombre que el módulo
            if hasattr(module, module_name):
                if player:
                    player.write_log(f"🧬 [AUTO-HEALER] Parche aplicado a {module_name} exitosamente.")
                return getattr(module, module_name)
    except Exception as e:
        if player:
            player.write_log(f"⚠️ [AUTO-HEALER] Falló la carga del parche para {module_name}: {e}")
    return None

def auto_healer(parameters: dict, player=None) -> str:
    action = parameters.get("action", "report_error").lower()
    
    if action == "report_error":
        module_name = parameters.get("module_name", "")
        error_trace = parameters.get("error_trace", "")
        
        HOTPATCH_DIR.mkdir(parents=True, exist_ok=True)
        
        if player:
            player.write_log(f"🧬 [AUTO-HEALER] Registrando falla en el módulo '{module_name}'.")
            player.write_log(f"🧬 Para arreglarlo permanentemente, pega el nuevo código de Python en config/hotpatches/{module_name}.py y la próxima ejecución se sanará sola.")
            
        # Aquí se conectaría la IA en una versión futura para escribir el archivo directamente.
        # Por ahora, simplemente creamos la carpeta y reportamos.
        return f"🧬 Error en {module_name} reportado al sistema inmune de ILUM."
        
    return "❌ Acción de sanación no reconocida."
