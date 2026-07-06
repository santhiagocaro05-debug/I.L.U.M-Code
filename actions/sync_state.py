import json
import hashlib
import threading
import time
from pathlib import Path
import requests
import socket

class SyncManager:
    def __init__(self):
        self.sync_dir = Path("sync_data")
        self.sync_dir.mkdir(exist_ok=True)
        self.peers = []
        self.peer_config = Path("config/peers.json")
        self.local_id = self.get_local_id()
        self.sync_enabled = False
        
    def get_local_id(self):
        """Obtiene ID único del dispositivo"""
        hostname = socket.gethostname()
        mac = hex(abs(hash(hostname)))[:8]
        return f"nexus_{mac}"
        
    def backup_state(self):
        """Respalda el estado actual"""
        backup = {
            'device_id': self.local_id,
            'timestamp': time.time(),
            'settings': {},
            'memory': {},
            'macros': []
        }
        
        # Respaldo de configuraciones
        config_file = Path("config/api_keys.json")
        if config_file.exists():
            backup['settings'] = json.loads(config_file.read_text(encoding='utf-8'))
            
        # Respaldo de memoria
        memory_file = Path("memory/memory.json")
        if memory_file.exists():
            backup['memory'] = json.loads(memory_file.read_text(encoding='utf-8'))
            
        # Respaldo de macros
        macro_file = Path("memory/macros.json")
        if macro_file.exists():
            backup['macros'] = json.loads(macro_file.read_text(encoding='utf-8'))
            
        # Guardar respaldo
        backup_file = self.sync_dir / f"backup_{self.local_id}_{int(time.time())}.json"
        backup_file.write_text(json.dumps(backup, indent=2), encoding='utf-8')
        
        return f"Respaldo creado: {backup_file.name}"
        
    def restore_state(self, backup_file):
        """Restaura un estado desde un backup"""
        if not backup_file.exists():
            return "Archivo de backup no encontrado"
            
        try:
            backup = json.loads(backup_file.read_text(encoding='utf-8'))
            
            # Restaurar configuraciones
            config_file = Path("config/api_keys.json")
            config_file.write_text(json.dumps(backup['settings'], indent=2), encoding='utf-8')
            
            # Restaurar memoria
            memory_file = Path("memory/memory.json")
            memory_file.write_text(json.dumps(backup['memory'], indent=2), encoding='utf-8')
            
            # Restaurar macros
            macro_file = Path("memory/macros.json")
            macro_file.write_text(json.dumps(backup['macros'], indent=2), encoding='utf-8')
            
            return f"Estado restaurado desde {backup_file.name}"
            
        except Exception as e:
            return f"Error restaurando backup: {e}"
            
    def sync_with_peer(self, peer_ip, peer_id, port=8000):
        """Sincroniza con otro dispositivo NEXUS"""
        try:
            response = requests.get(f"http://{peer_ip}:{port}/sync")
            if response.status_code == 200:
                return f"Sincronizado con {peer_id} en {peer_ip}"
            else:
                return f"Error sincronizando con {peer_id}: {response.status_code}"
                
        except Exception as e:
            return f"Error conectando con {peer_id}: {e}"

def sync_state(parameters: dict, player=None):
    """
    Sincronización multi-dispositivo para NEXUS
    
    Args:
        parameters: {
            'action': 'backup' | 'restore' | 'merge' | 'sync_peer',
            'backup_file': (opcional) nombre del backup para restaurar,
            'peer_ip': (opcional) IP del peer,
            'peer_id': (opcional) ID del peer
        }
    """
    action = parameters.get('action', 'backup')
    backup_file = parameters.get('backup_file')
    peer_ip = parameters.get('peer_ip')
    peer_id = parameters.get('peer_id', 'peer')
    
    # Singleton
    if not hasattr(sync_state, 'instance'):
        sync_state.instance = SyncManager()
    
    sm = sync_state.instance
    
    if action == 'backup':
        return sm.backup_state()
        
    elif action == 'restore':
        if not backup_file:
            return "Proporciona el archivo de backup"
        backup_path = sm.sync_dir / backup_file
        return sm.restore_state(backup_path)
        
    elif action == 'sync_peer':
        if not peer_ip:
            return "Proporciona la IP del peer"
        return sm.sync_with_peer(peer_ip, peer_id)
        
    elif action == 'merge':
        return "Función de merge en desarrollo"
        
    else:
        return "Acción no reconocida. Usa: backup, restore, sync_peer, merge"