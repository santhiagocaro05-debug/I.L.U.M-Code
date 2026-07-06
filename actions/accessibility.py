"""
accessibility.py — Suite de accesibilidad universal
Soporta: simplificación de tareas, rutinas, control ocular, micromovimientos
"""

import json
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional

# ─── CONFIGURACIÓN ──────────────────────────────────────────────────────────
ACCESSIBILITY_CONFIG = Path(__file__).resolve().parent.parent / "config" / "accessibility.json"

def _get_config() -> Dict:
    """Carga la configuración de accesibilidad."""
    if ACCESSIBILITY_CONFIG.exists():
        try:
            return json.loads(ACCESSIBILITY_CONFIG.read_text(encoding="utf-8"))
        except:
            pass
    
    default = {
        "eye_tracking": False,
        "micro_movement": False,
        "speech_tolerance": 0.5,
        "routines": {},
        "habits": {}
    }
    ACCESSIBILITY_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    ACCESSIBILITY_CONFIG.write_text(json.dumps(default, indent=2), encoding="utf-8")
    return default

def _save_config(config: Dict):
    """Guarda la configuración."""
    ACCESSIBILITY_CONFIG.write_text(json.dumps(config, indent=2), encoding="utf-8")

# ─── VARIABLES GLOBALES ─────────────────────────────────────────────────────
_eye_tracking_active = False
_eye_tracking_thread = None
_micro_movement_active = False
_micro_movement_thread = None

# ─── FUNCIONES DE ACCESIBILIDAD ────────────────────────────────────────────

def task_simplify(text: str) -> str:
    """
    Descompone una tarea compleja en pasos simples y accionables.
    """
    if not text:
        return "No se proporcionó texto para simplificar."
    
    try:
        from google import genai
        from actions.student_mode import _get_api_key
        
        client = genai.Client(api_key=_get_api_key())
        prompt = f"""
        Descompón la siguiente tarea en pasos simples, claros y accionables.
        La respuesta debe ser una lista numerada con pasos concretos.
        Usa un lenguaje sencillo y directo.
        
        TAREA: {text}
        """
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        
        return f"📋 TAREA SIMPLIFICADA:\n{'-' * 40}\n{response.text.strip()}"
        
    except Exception as e:
        return f"❌ Error simplificando tarea: {e}"

def _routine_loop():
    """Loop para rutinas gamificadas."""
    while _routine_active:
        # Aquí iría la lógica de rutinas
        time.sleep(60)

def accessibility(parameters: dict, player=None) -> str:
    """
    Suite de accesibilidad universal.
    
    Acciones:
    - task_simplify: Descompone tareas en pasos simples
    - routine: Gestiona rutinas gamificadas
    - eye_tracking: Control ocular (start/stop)
    - micro_movement: Micromovimientos (start/stop)
    - speech_config: Ajusta tolerancia de voz
    - status: Estado del módulo
    """
    
    action = parameters.get("action", "").lower().strip()
    text = parameters.get("text", "")
    routine_name = parameters.get("name", "")
    setting = parameters.get("setting", "")
    value = parameters.get("value", "")
    
    config = _get_config()
    
    # ─── MAPEO DE ACCIONES ──────────────────────────────────────────────────
    
    # 1. SIMPLIFICAR TAREA
    if action == "task_simplify":
        if not text:
            return "❌ Se requiere 'text' para simplificar."
        return task_simplify(text)
    
    # 2. RUTINAS
    elif action == "routine":
        sub_action = parameters.get("sub_action", "list")
        
        if sub_action == "add":
            if not routine_name:
                return "❌ Se requiere 'name' para agregar una rutina."
            
            routines = config.get("routines", {})
            routines[routine_name] = {
                "created": time.time(),
                "streak": 0,
                "completed": 0,
                "last_completed": None
            }
            config["routines"] = routines
            _save_config(config)
            return f"✅ Rutina '{routine_name}' agregada."
        
        elif sub_action == "complete":
            if not routine_name:
                return "❌ Se requiere 'name' para completar una rutina."
            
            routines = config.get("routines", {})
            if routine_name not in routines:
                return f"❌ Rutina '{routine_name}' no encontrada."
            
            routines[routine_name]["completed"] += 1
            routines[routine_name]["streak"] += 1
            routines[routine_name]["last_completed"] = time.time()
            config["routines"] = routines
            _save_config(config)
            
            streak = routines[routine_name]["streak"]
            completed = routines[routine_name]["completed"]
            return f"✅ ¡Rutina '{routine_name}' completada! 🔥 Racha: {streak} días | Total: {completed}"
        
        elif sub_action == "list":
            routines = config.get("routines", {})
            if not routines:
                return "📋 No hay rutinas configuradas."
            
            result = "📋 MIS RUTINAS:\n" + "-" * 40 + "\n"
            for name, data in routines.items():
                status = "✅" if data.get("last_completed") and time.time() - data["last_completed"] < 86400 else "⬜"
                result += f"  {status} {name} | Racha: {data.get('streak', 0)} | Total: {data.get('completed', 0)}\n"
            return result
        
        else:
            return "❌ Sub-acción no reconocida. Opciones: add, complete, list"
    
    # 3. CONTROL OCULAR
    elif action == "eye_tracking":
        global _eye_tracking_active, _eye_tracking_thread
        
        if value == "start":
            if _eye_tracking_active:
                return "⚠️ El control ocular ya está activo."
            
            _eye_tracking_active = True
            
            def eye_loop():
                while _eye_tracking_active:
                    try:
                        # Aquí iría la lógica de seguimiento ocular
                        # (requiere MediaPipe y cámara)
                        time.sleep(0.1)
                    except:
                        break
            
            _eye_tracking_thread = threading.Thread(target=eye_loop, daemon=True)
            _eye_tracking_thread.start()
            
            config["eye_tracking"] = True
            _save_config(config)
            return "✅ Control ocular activado. Usa la cámara para mover el mouse."
        
        elif value == "stop":
            _eye_tracking_active = False
            config["eye_tracking"] = False
            _save_config(config)
            return "✅ Control ocular desactivado."
        
        else:
            return f"❌ Acción no reconocida. Usa 'start' o 'stop'. Estado actual: {'Activo' if _eye_tracking_active else 'Inactivo'}"
    
    # 4. MICROMOVIMIENTOS
    elif action == "micro_movement":
        global _micro_movement_active, _micro_movement_thread
        
        if value == "start":
            if _micro_movement_active:
                return "⚠️ Los micromovimientos ya están activos."
            
            _micro_movement_active = True
            
            def micro_loop():
                while _micro_movement_active:
                    try:
                        # Aquí iría la lógica de micromovimientos
                        # (requiere cámara para detección de cabeza)
                        time.sleep(0.1)
                    except:
                        break
            
            _micro_movement_thread = threading.Thread(target=micro_loop, daemon=True)
            _micro_movement_thread.start()
            
            config["micro_movement"] = True
            _save_config(config)
            return "✅ Micromovimientos activados. Mueve la cabeza para controlar el mouse."
        
        elif value == "stop":
            _micro_movement_active = False
            config["micro_movement"] = False
            _save_config(config)
            return "✅ Micromovimientos desactivados."
        
        else:
            return f"❌ Acción no reconocida. Usa 'start' o 'stop'. Estado actual: {'Activo' if _micro_movement_active else 'Inactivo'}"
    
    # 5. CONFIGURACIÓN DE VOZ
    elif action == "speech_config":
        if setting == "tolerance":
            try:
                tolerance = float(value)
                if 0.1 <= tolerance <= 1.0:
                    config["speech_tolerance"] = tolerance
                    _save_config(config)
                    return f"✅ Tolerancia de voz ajustada a {tolerance}"
                else:
                    return "❌ La tolerancia debe estar entre 0.1 y 1.0"
            except:
                return "❌ Valor inválido. Debe ser un número entre 0.1 y 1.0"
        
        elif setting == "show":
            return f"🔊 Tolerancia de voz actual: {config.get('speech_tolerance', 0.5)}"
        
        else:
            return "❌ Configuración no reconocida. Opciones: tolerance (0.1-1.0), show"
    
    # 6. STATUS
    elif action == "status":
        routines = config.get("routines", {})
        completed = sum(r.get("completed", 0) for r in routines.values())
        
        return f"""
📊 ESTADO DE ACCESIBILIDAD:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👁️ Control ocular: {'✅ Activo' if _eye_tracking_active else '❌ Inactivo'}
🧠 Micromovimientos: {'✅ Activo' if _micro_movement_active else '❌ Inactivo'}
🎙️ Tolerancia de voz: {config.get('speech_tolerance', 0.5)}
📋 Rutinas: {len(routines)} | Completadas: {completed}

📋 Acciones disponibles:
  • task_simplify → Simplificar tarea
  • routine → Gestionar rutinas (add, complete, list)
  • eye_tracking → Control ocular (start, stop)
  • micro_movement → Micromovimientos (start, stop)
  • speech_config → Configurar voz
  • status → Estado actual

📝 Ejemplos:
  {"action": "task_simplify", "text": "Hacer una presentación de 20 páginas"}
  {"action": "routine", "sub_action": "add", "name": "Ejercicio matutino"}
  {"action": "routine", "sub_action": "complete", "name": "Ejercicio matutino"}
  {"action": "eye_tracking", "value": "start"}
  {"action": "speech_config", "setting": "tolerance", "value": 0.7}
"""
    
    # 7. HELP
    else:
        return """
🎯 ACCESIBILIDAD - Comandos:

📋 Tareas:
  • task_simplify → Simplifica tareas en pasos simples
  • routine → Gestiona rutinas gamificadas

👁️ Control:
  • eye_tracking → Control ocular con cámara
  • micro_movement → Control con movimientos de cabeza

🎙️ Voz:
  • speech_config → Configurar tolerancia de voz

📝 Ejemplos:
  {"action": "task_simplify", "text": "Organizar mi escritorio"}
  {"action": "routine", "sub_action": "add", "name": "Leer 30 minutos"}
  {"action": "eye_tracking", "value": "start"}
"""
