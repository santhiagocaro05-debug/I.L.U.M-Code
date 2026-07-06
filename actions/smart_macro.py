import pyautogui
import time
import json
import keyboard
import threading
from pathlib import Path
import cv2
import numpy as np
from PIL import ImageGrab

class SmartMacro:
    def __init__(self):
        self.recording = False
        self.actions = []
        self.recorded_macro = []
        self.macro_file = Path("config/smart_macros.json")
        self.load_macros()
        
    def load_macros(self):
        """Carga macros guardadas"""
        if self.macro_file.exists():
            try:
                self.recorded_macro = json.loads(self.macro_file.read_text(encoding="utf-8"))
            except:
                self.recorded_macro = []
                
    def save_macros(self):
        """Guarda macros"""
        self.macro_file.write_text(json.dumps(self.recorded_macro, indent=2), encoding="utf-8")
        
    def start_recording(self):
        """Inicia grabación de macro"""
        self.recording = True
        self.actions = []
        print("🎬 Grabando macro... Presiona F12 para detener")
        
        def record_loop():
            while self.recording:
                # Capturar posición del mouse
                x, y = pyautogui.position()
                
                # Verificar clics
                for button in ['left', 'right', 'middle']:
                    if pyautogui.mouseDown(button=button):
                        self.actions.append({
                            'type': 'click',
                            'button': button,
                            'x': x,
                            'y': y,
                            'timestamp': time.time()
                        })
                        
                # Capturar teclas
                for key in keyboard.all_modifiers + keyboard.all_keys:
                    if keyboard.is_pressed(key):
                        self.actions.append({
                            'type': 'keypress',
                            'key': key,
                            'timestamp': time.time()
                        })
                        
                time.sleep(0.01)
                
        threading.Thread(target=record_loop, daemon=True).start()
        
    def stop_recording(self, name="macro"):
        """Detiene la grabación y guarda el macro"""
        self.recording = False
        
        # Normalizar tiempos
        if self.actions:
            start_time = self.actions[0]['timestamp']
            for action in self.actions:
                action['timestamp'] -= start_time
                
        macro = {
            'name': name,
            'actions': self.actions,
            'created': time.time()
        }
        
        self.recorded_macro.append(macro)
        self.save_macros()
        return f"Macro '{name}' guardado con {len(self.actions)} acciones"
        
    def play_macro(self, name, loop=False):
        """Reproduce un macro"""
        macro = None
        for m in self.recorded_macro:
            if m['name'] == name:
                macro = m
                break
                
        if not macro:
            return f"Macro '{name}' no encontrado"
            
        def play_loop():
            while True:
                for action in macro['actions']:
                    # Esperar hasta el timestamp adecuado
                    time.sleep(action['timestamp'])
                    
                    if action['type'] == 'click':
                        pyautogui.click(action['x'], action['y'], button=action['button'])
                    elif action['type'] == 'keypress':
                        pyautogui.press(action['key'])
                        
                if not loop:
                    break
                    
        threading.Thread(target=play_loop, daemon=True).start()
        return f"Reproduciendo macro '{name}'"
        
    def conditional_macro(self, condition, action):
        """Ejecuta un macro basado en una condición visual"""
        if condition == 'image_found':
            # Buscar imagen en pantalla
            image_path = action.get('image_path')
            confidence = action.get('confidence', 0.8)
            
            try:
                position = pyautogui.locateOnScreen(image_path, confidence=confidence)
                if position:
                    # Ejecutar acción
                    macro_name = action.get('macro_name')
                    if macro_name:
                        return self.play_macro(macro_name)
                    else:
                        # Realizar clic en la posición encontrada
                        x = position.left + position.width // 2
                        y = position.top + position.height // 2
                        pyautogui.click(x, y)
                        return "Condición visual cumplida. Acción ejecutada."
            except:
                return "Error en detección visual"
                
        return "Condición no cumplida"

def smart_macro(parameters: dict, player=None):
    """
    Macros avanzados para NEXUS
    
    Args:
        parameters: {
            'action': 'record' | 'play' | 'conditional' | 'stop',
            'macro_name': (opcional) nombre del macro,
            'loop': (opcional) True/False,
            'condition': (opcional) 'image_found',
            'action_def': (opcional) acción para conditional
        }
    """
    action = parameters.get('action', 'record')
    macro_name = parameters.get('macro_name', 'macro')
    loop = parameters.get('loop', False)
    
    # Singleton
    if not hasattr(smart_macro, 'instance'):
        smart_macro.instance = SmartMacro()
    
    sm = smart_macro.instance
    
    if action == 'record':
        sm.start_recording()
        return "Grabación iniciada. Presiona F12 para detener"
        
    elif action == 'stop':
        return sm.stop_recording(macro_name)
        
    elif action == 'play':
        return sm.play_macro(macro_name, loop)
        
    elif action == 'conditional':
        condition = parameters.get('condition', 'image_found')
        action_def = parameters.get('action_def', {})
        return sm.conditional_macro(condition, action_def)
        
    else:
        return "Acción no reconocida. Usa: record, stop, play, conditional"