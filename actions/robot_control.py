import requests
import json
import time
from pathlib import Path
import threading

class RobotController:
    def __init__(self):
        self.robots = {}
        self.load_robots()
        
    def load_robots(self):
        """Carga los robots configurados"""
        config_file = Path("config/robots.json")
        if config_file.exists():
            try:
                self.robots = json.loads(config_file.read_text(encoding="utf-8"))
            except:
                pass
                
    def save_robots(self):
        """Guarda la configuración de robots"""
        config_file = Path("config/robots.json")
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(json.dumps(self.robots, indent=2), encoding="utf-8")
        
    def add_robot(self, robot_type, name, config):
        """Añade un nuevo robot"""
        self.robots[name] = {
            'type': robot_type,
            'config': config,
            'status': 'disconnected'
        }
        self.save_robots()
        return f"Robot {name} añadido"
        
    def connect_robot(self, name):
        """Conecta a un robot"""
        if name not in self.robots:
            return f"Robot {name} no encontrado"
            
        robot = self.robots[name]
        robot['status'] = 'connected'
        return f"Conectado a {name}"
        
    def control_roomba(self, config, action):
        """Controla un robot Roomba"""
        # Ejemplo de integración con Roomba
        ip = config.get('ip')
        if not ip:
            return "IP no configurada"
            
        endpoint = f"http://{ip}/api/v1/{action}"
        
        try:
            response = requests.post(endpoint, timeout=5)
            return f"Comando {action} enviado a Roomba"
        except:
            return "Error conectando con Roomba"
            
    def control_xiaomi(self, config, action):
        """Controla un robot Xiaomi"""
        # Integración con Xiaomi Mi Home
        token = config.get('token')
        device_id = config.get('device_id')
        
        if not token or not device_id:
            return "Token o Device ID no configurados"
            
        # Aquí iría la lógica específica de Xiaomi
        return f"Comando {action} enviado a Xiaomi"
        
    def execute_action(self, robot_name, action):
        """Ejecuta una acción en un robot específico"""
        if robot_name not in self.robots:
            return f"Robot {robot_name} no encontrado"
            
        robot = self.robots[robot_name]
        robot_type = robot['type']
        config = robot['config']
        
        if robot_type == 'roomba':
            return self.control_roomba(config, action)
        elif robot_type == 'xiaomi':
            return self.control_xiaomi(config, action)
        else:
            return f"Tipo de robot no soportado: {robot_type}"

def robot_control(parameters: dict, player=None):
    """
    Control de robots físicos para NEXUS
    
    Args:
        parameters: {
            'action': 'start_cleaning' | 'dock' | 'schedule' | 'add_robot',
            'robot_name': (opcional) nombre del robot,
            'robot_type': (opcional) roomba | xiaomi,
            'config': (opcional) configuración del robot
        }
    """
    action = parameters.get('action', 'start_cleaning')
    robot_name = parameters.get('robot_name', 'default')
    
    # Singleton
    if not hasattr(robot_control, 'instance'):
        robot_control.instance = RobotController()
    
    controller = robot_control.instance
    
    if action == 'add_robot':
        robot_type = parameters.get('robot_type')
        config = parameters.get('config', {})
        if not robot_type:
            return "Especifica el tipo de robot"
        return controller.add_robot(robot_type, robot_name, config)
        
    elif action == 'connect':
        return controller.connect_robot(robot_name)
        
    elif action in ['start_cleaning', 'dock', 'schedule']:
        return controller.execute_action(robot_name, action)
        
    else:
        return "Acción no reconocida. Usa: start_cleaning, dock, schedule, add_robot"