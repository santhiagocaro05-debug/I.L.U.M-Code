# -*- coding: utf-8 -*-
import json
import time
import uuid
import threading
from datetime import datetime
from pathlib import Path
from memory.config_manager import BASE_DIR

AUTO_DIR = BASE_DIR / "automatizaciones"
AUTO_FILE = AUTO_DIR / "tasks.json"

def _load_tasks():
    if not AUTO_FILE.exists():
        return {}
    try:
        with open(AUTO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_tasks(tasks):
    AUTO_DIR.mkdir(parents=True, exist_ok=True)
    with open(AUTO_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=4, ensure_ascii=False)

def scheduler(parameters: dict, player=None, speak=None) -> str:
    """
    Motor interno de automatizaciones. Crea, lista y administra tareas recurrentes.
    """
    action = parameters.get("action", "").lower()
    tasks = _load_tasks()

    if action == "list":
        if not tasks:
            return "No hay automatizaciones programadas en este momento."
        res = "Automatizaciones programadas guardadas:\n"
        for t_id, t in tasks.items():
            status = "Activa" if t.get("enabled", True) else "Inactiva"
            res += f"- [{t_id}] {t.get('name')} | Freq: {t.get('frequency')} | Estado: {status}\n"
        return res

    elif action == "create":
        name = parameters.get("name", "Tarea automatizada")
        frequency = parameters.get("frequency", "once")
        hour = parameters.get("hour", 0)
        minute = parameters.get("minute", 0)
        task_action = parameters.get("task_action", "notify")
        task_parameters = parameters.get("task_parameters", {})
        
        t_id = str(uuid.uuid4())[:6]
        
        tasks[t_id] = {
            "name": name,
            "frequency": frequency,
            "hour": hour,
            "minute": minute,
            "weekday": parameters.get("weekday", ""),
            "interval_minutes": parameters.get("interval_minutes", 60),
            "task_action": task_action,
            "task_parameters": task_parameters,
            "enabled": True,
            "last_run": None
        }
        _save_tasks(tasks)
        return f"Automatización '{name}' creada y guardada con éxito bajo el ID [{t_id}]."

    elif action == "delete":
        t_id = parameters.get("task_id", "")
        if t_id in tasks:
            name = tasks[t_id]['name']
            del tasks[t_id]
            _save_tasks(tasks)
            return f"Automatización '{name}' eliminada correctamente de la carpeta."
        return f"Error: No se encontró ninguna tarea con el ID {t_id}."

    elif action == "enable" or action == "disable":
        t_id = parameters.get("task_id", "")
        if t_id in tasks:
            tasks[t_id]["enabled"] = (action == "enable")
            _save_tasks(tasks)
            return f"Automatización '{tasks[t_id]['name']}' {'activada' if action == 'enable' else 'desactivada'}."
        return f"Error: No se encontró la tarea con ID {t_id}."

    elif action == "run_now":
        t_id = parameters.get("task_id", "")
        if t_id in tasks:
            _execute_task(t_id, tasks[t_id], player)
            return f"Automatización '{tasks[t_id]['name']}' iniciada manualmente."
        return f"Error: No se encontró la tarea con ID {t_id}."

    return "Acción de automatización no reconocida."

def _execute_task(t_id, task, player):
    """Ejecuta de manera asíncrona la acción de la tarea programada."""
    t_name = task.get("name", "Unknown")
    t_action = task.get("task_action", "notify")
    t_params = task.get("task_parameters", {})
    
    if player and hasattr(player, "write_log"):
        player.write_log(f"⚡ Ejecutando automatización: {t_name}")
        
    try:
        if t_action == "notify":
            if player and hasattr(player, "write_log"):
                player.write_log(f"🔔 RECORDATORIO: {t_name} - {t_params.get('message', '')}")
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except:
                pass
        elif t_action == "backup":
            import actions.backup as mod
            mod.backup(t_params, player=player)
        elif t_action == "file_controller":
            import actions.file_controller as mod
            mod.file_controller(t_params)
        elif t_action == "macros":
            import actions.macros as mod
            mod.macros(t_params, player=player)
        elif t_action == "self_prompt":
            prompt = t_params.get("prompt", "")
            silent = t_params.get("silent", False)
            if prompt and player and hasattr(player, "on_text_command") and callable(player.on_text_command):
                if silent:
                    # Instruir a Gemini que haga la tarea en silencio sin hablar
                    player.on_text_command(f"[EJECUTA ESTO EN MODO SILENCIOSO SIN HABLAR NI RESPONDER TEXTO, SOLO USA LA HERRAMIENTA]: {prompt}")
                else:
                    # Simular que el usuario lo pide normalmente
                    player.on_text_command(f"[TAREA AUTÓNOMA PROGRAMADA]: {prompt}")
        else:
            if player and hasattr(player, "write_log"):
                player.write_log(f"⚙️ Automatización completada: {t_action}")
    except Exception as e:
        if player and hasattr(player, "write_log"):
            player.write_log(f"❌ Error en automatización '{t_name}': {e}")

def _runner_loop(player):
    """Bucle infinito que comprueba las tareas pendientes cada minuto."""
    while True:
        try:
            tasks = _load_tasks()
            now = datetime.now()
            updated = False
            for t_id, task in tasks.items():
                if not task.get("enabled", True):
                    continue
                
                freq = task.get("frequency")
                last_run_str = task.get("last_run")
                last_run = datetime.fromisoformat(last_run_str) if last_run_str else None
                
                should_run = False
                
                if freq == "interval":
                    mins = task.get("interval_minutes", 60)
                    if not last_run or (now - last_run).total_seconds() >= mins * 60:
                        should_run = True
                else:
                    # daily, weekly, once
                    if now.hour == task.get("hour") and now.minute == task.get("minute"):
                        # Evitar ejecución múltiple en el mismo minuto (esperar al menos 2 mins)
                        if not last_run or (now - last_run).total_seconds() > 120:
                            if freq == "daily" or freq == "once":
                                should_run = True
                            elif freq == "weekly":
                                target_day = str(task.get("weekday", "")).lower()
                                days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                                if target_day in days and now.weekday() == days.index(target_day):
                                    should_run = True
                
                if should_run:
                    _execute_task(t_id, task, player)
                    task["last_run"] = now.isoformat()
                    updated = True
                    if freq == "once":
                        task["enabled"] = False
                        
            if updated:
                _save_tasks(tasks)
        except Exception as e:
            pass
            
        # Comprobar cada 30 segundos
        time.sleep(30)

def start_runner(player=None, speak=None) -> None:
    """Inicia el hilo en segundo plano que vigila y ejecuta las automatizaciones."""
    t = threading.Thread(target=_runner_loop, args=(player,), daemon=True)
    t.start()
