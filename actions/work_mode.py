import json
import os
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
WORK_MODE_CFG = BASE_DIR / "config" / "work_mode.json"

def _load_config():
    if WORK_MODE_CFG.exists():
        try:
            return json.loads(WORK_MODE_CFG.read_text(encoding="utf-8"))
        except:
            return {"apps": []}
    return {"apps": []}

def _save_config(data):
    WORK_MODE_CFG.parent.mkdir(parents=True, exist_ok=True)
    WORK_MODE_CFG.write_text(json.dumps(data, indent=4), encoding="utf-8")

def work_mode(parameters: dict, player=None) -> str:
    """
    Herramienta para gestionar el Modo Trabajo ("ilum trabajo").
    Parameters:
      - action: 'start', 'add_app', 'remove_app', 'list_apps'
      - app_path: Ruta de la aplicación, URI o URL de YouTube a agregar/eliminar.
    """
    action = parameters.get("action", "")
    app_path = parameters.get("app_path", "")
    
    cfg = _load_config()
    
    if action == "start":
        if not cfg.get("apps"):
            return "El modo trabajo no tiene aplicaciones configuradas. Pídele al usuario que agregue aplicaciones."
        launched = []
        for app in cfg["apps"]:
            try:
                # If it's a URL, open with start
                if app.startswith("http") or app.startswith("www"):
                    os.system(f"start {app}")
                else:
                    os.startfile(app)
                launched.append(app)
            except Exception as e:
                pass
        return f"Modo trabajo iniciado. Se abrieron: {', '.join(launched)}"
        
    elif action == "add_app":
        if app_path and app_path not in cfg["apps"]:
            cfg["apps"].append(app_path)
            _save_config(cfg)
            return f"Agregado al modo trabajo: {app_path}"
        return "App ya existe o ruta inválida."
        
    elif action == "remove_app":
        if app_path in cfg["apps"]:
            cfg["apps"].remove(app_path)
            _save_config(cfg)
            return f"Eliminado del modo trabajo: {app_path}"
        return "App no encontrada."
        
    elif action == "list_apps":
        apps = cfg.get("apps", [])
        if not apps:
            return "No hay aplicaciones configuradas para el modo trabajo."
        return "Aplicaciones de Modo Trabajo:\n" + "\n".join(f"- {a}" for a in apps)
        
    return "Acción inválida para work_mode."
