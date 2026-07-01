# -*- coding: utf-8 -*-
"""
game_control.py — Módulo para detección y control de juegos para ILUM.
Versión mejorada con múltiples funciones
"""
import pygetwindow as gw
import keyboard
import time
import psutil  # pip install psutil
import os
import winreg
from typing import Dict, List, Tuple
import subprocess

class GameController:
    def __init__(self):
        self.supported_games = self._load_game_profiles()
        self.last_game = None
        self.game_processes = {}
    
    def _load_game_profiles(self) -> Dict:
        """Perfiles de pausa para diferentes juegos"""
        return {
            "Cyberpunk 2077": {"pause_key": "esc", "method": "keypress"},
            "The Witcher 3": {"pause_key": "esc", "method": "keypress"},
            "Elden Ring": {"pause_key": "esc", "method": "keypress", "wait": 0.1},
            "Red Dead Redemption 2": {"pause_key": "esc", "method": "keypress"},
            "DOOM Eternal": {"pause_key": "escape", "method": "keypress"},
            "Minecraft": {"pause_key": "esc", "method": "keypress"},
            "League of Legends": {"pause_key": "esc", "method": "keypress"},
            "Valorant": {"pause_key": "escape", "method": "keypress"},
            "GTA V": {"pause_key": "escape", "method": "keypress"},
            "Fortnite": {"pause_key": "escape", "method": "keypress"},
        }
    
    def get_active_game(self) -> Dict:
        """Detecta el juego activo con más información"""
        try:
            active = gw.getActiveWindow()
            if not active:
                return None
            
            title = active.title.strip()
            
            # Método alternativo: buscar proceso
            foreground_proc = self._get_foreground_process()
            
            return {
                "title": title,
                "process": foreground_proc,
                "is_fullscreen": self._is_fullscreen(active),
                "window_rect": (active.left, active.top, active.right, active.bottom)
            }
        except Exception as e:
            print(f"Error detectando juego: {e}")
            return None
    
    def _get_foreground_process(self) -> Dict:
        """Obtiene el proceso en primer plano"""
        try:
            import ctypes
            from ctypes import wintypes
            
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            
            hwnd = user32.GetForegroundWindow()
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            
            process = psutil.Process(pid.value)
            return {
                "name": process.name(),
                "exe": process.exe(),
                "pid": pid.value
            }
        except Exception as e:
            return None
    
    def _is_fullscreen(self, window) -> bool:
        """Detecta si está en pantalla completa"""
        try:
            import win32api
            screen_width = win32api.GetSystemMetrics(0)
            screen_height = win32api.GetSystemMetrics(1)
            
            width = window.right - window.left
            height = window.bottom - window.top
            
            return width >= screen_width - 10 and height >= screen_height - 10
        except:
            return False
    
    def smart_pause(self, game_info: Dict) -> str:
        """Pausa inteligente según el juego"""
        if not game_info:
            return "No se pudo detectar el juego"
        
        title = game_info['title']
        process = game_info.get('process', {})
        
        # Buscar perfil del juego
        game_profile = None
        for game_name, profile in self.supported_games.items():
            if game_name.lower() in title.lower():
                game_profile = profile
                break
        
        # Si no hay perfil, usar configuración por defecto
        if not game_profile:
            game_profile = {"pause_key": "esc", "method": "keypress"}
        
        # Ejecutar pausa según método
        result = self._execute_pause(game_profile)
        
        # Guardar último juego
        self.last_game = title
        
        return f"🎮 Juego '{title}' pausado. {result}"
    
    def _execute_pause(self, profile: Dict) -> str:
        """Ejecuta diferentes métodos de pausa"""
        method = profile.get("method", "keypress")
        pause_key = profile.get("pause_key", "esc")
        
        if method == "keypress":
            keyboard.press(pause_key)
            time.sleep(profile.get("wait", 0.05))
            keyboard.release(pause_key)
            return f"Tecla {pause_key} presionada"
        
        elif method == "alt_tab":
            # Alternativa: cambiar al juego y luego pausar
            keyboard.press('alt')
            keyboard.press('tab')
            time.sleep(0.1)
            keyboard.release('tab')
            keyboard.release('alt')
            time.sleep(0.2)
            keyboard.press(pause_key)
            time.sleep(0.05)
            keyboard.release(pause_key)
            return f"Alt+Tab y {pause_key}"
        
        elif method == "win_key":
            keyboard.press('windows')
            time.sleep(0.05)
            keyboard.release('windows')
            return "Tecla Windows presionada"
        
        return "Método de pausa no reconocido"
    
    def minimize_game(self) -> str:
        """Minimiza el juego actual"""
        try:
            active = gw.getActiveWindow()
            if active:
                active.minimize()
                return "✅ Juego minimizado"
            return "No se pudo minimizar el juego"
        except Exception as e:
            return f"Error minimizando: {e}"
    
    def mute_game_volume(self) -> str:
        """Silencia el volumen del juego usando Windows"""
        try:
            import ctypes
            from ctypes import POINTER, cast
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            
            volume.SetMute(1, None)
            return "🔇 Juego silenciado"
        except:
            # Fallback: tecla de silencio
            keyboard.press('volumemute')
            time.sleep(0.05)
            keyboard.release('volumemute')
            return "🔇 Silencio activado"
    
    def lower_game_volume(self, level: int = 30) -> str:
        """Reduce el volumen del juego al nivel especificado (0-100)"""
        try:
            import ctypes
            from ctypes import POINTER, cast
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            
            # Convertir a rango 0-1
            new_level = level / 100.0
            volume.SetMasterVolumeLevelScalar(new_level, None)
            return f"🔉 Volumen reducido al {level}%"
        except:
            return "No se pudo ajustar el volumen"
    
    def take_break_reminder(self, game_title: str) -> str:
        """Sugiere tomar un descanso después de cierto tiempo"""
        # Aquí podrías implementar un temporizador
        return f"💡 Recuerda tomar un descanso cada hora mientras juegas {game_title}"
    
    def capture_game_screenshot(self) -> str:
        """Captura screenshot del juego"""
        try:
            import pyautogui
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"game_screenshot_{timestamp}.png"
            pyautogui.screenshot(filename)
            return f"📸 Screenshot guardado como {filename}"
        except Exception as e:
            return f"Error capturando screenshot: {e}"
    
    def record_game_time(self, game_title: str) -> Dict:
        """Registra tiempo de juego para estadísticas"""
        stats_file = "game_stats.json"
        
        try:
            import json
            from datetime import datetime
            
            if os.path.exists(stats_file):
                with open(stats_file, 'r') as f:
                    stats = json.load(f)
            else:
                stats = {}
            
            if game_title not in stats:
                stats[game_title] = {"total_minutes": 0, "sessions": []}
            
            # Registrar sesión
            stats[game_title]["sessions"].append({
                "start": datetime.now().isoformat(),
                "end": None
            })
            
            with open(stats_file, 'w') as f:
                json.dump(stats, f, indent=2)
            
            return stats
        except:
            return {}
    
    def close_game_process(self, game_name: str = None) -> str:
        """Cierra el proceso del juego"""
        try:
            if not game_name:
                # Detectar automáticamente
                game_info = self.get_active_game()
                if game_info and game_info.get('process'):
                    process_name = game_info['process'].get('name')
                    os.system(f'taskkill /f /im {process_name}')
                    return f"✅ Juego {process_name} cerrado"
            
            os.system(f'taskkill /f /im {game_name}')
            return f"✅ Juego {game_name} cerrado"
        except Exception as e:
            return f"Error cerrando juego: {e}"

# Función principal mejorada
def game_control(parameters: dict, player=None) -> str:
    """
    Control avanzado de juegos con múltiples funciones
    
    Parámetros soportados:
    - action: "pause", "minimize", "mute", "lower_volume", "screenshot", "close"
    - volume_level: 0-100 (para lower_volume)
    """
    controller = GameController()
    
    # Determinar acción
    action = parameters.get("action", "pause")
    
    # Detectar juego actual
    game_info = controller.get_active_game()
    
    if not game_info or not game_info.get('title'):
        return "No se pudo detectar ningún juego activo"
    
    game_title = game_info['title']
    
    # Registrar estadísticas de juego
    if action == "pause":
        controller.record_game_time(game_title)
    
    # Ejecutar acción solicitada
    if action == "pause":
        result = controller.smart_pause(game_info)
        
        # Agregar recordatorio de descanso
        result += "\n" + controller.take_break_reminder(game_title)
        
    elif action == "minimize":
        result = controller.minimize_game()
        
    elif action == "mute":
        result = controller.mute_game_volume()
        
    elif action == "lower_volume":
        volume_level = parameters.get("volume_level", 30)
        result = controller.lower_game_volume(volume_level)
        
    elif action == "screenshot":
        result = controller.capture_game_screenshot()
        
    elif action == "close":
        result = controller.close_game_process()
        
    else:
        result = f"Acción '{action}' no soportada"
    
    # Logging
    if player:
        player.write_log(f"🎮 {action.upper()} en {game_title}: {result}")
    
    return f"🎮 Juego: {game_title}\n{result}"

# Función para obtener estadísticas de juego
def get_game_stats() -> str:
    """Devuelve estadísticas de tiempo de juego"""
    try:
        import json
        if not os.path.exists("game_stats.json"):
            return "No hay estadísticas de juego aún"
        
        with open("game_stats.json", 'r') as f:
            stats = json.load(f)
        
        result = "📊 ESTADÍSTICAS DE JUEGO:\n"
        for game, data in stats.items():
            minutes = data.get("total_minutes", 0)
            hours = minutes // 60
            mins = minutes % 60
            sessions = len(data.get("sessions", []))
            result += f"\n🎮 {game}: {hours}h {mins}m ({sessions} sesiones)"
        
        return result
    except:
        return "Error cargando estadísticas"