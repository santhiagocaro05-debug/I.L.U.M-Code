import threading
import time
import json
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import socket
import os

class NASServer:
    def __init__(self):
        self.server = None
        self.port = 8000
        self.running = False
        self.shared_dirs = []
        self.server_thread = None
        
    def start_server(self, port=8000, directory=None):
        """Inicia el servidor de archivos"""
        if self.running:
            return "Servidor ya está en ejecución"
            
        self.port = port
        
        # Directorio compartido
        if not directory:
            directory = str(Path.home() / "Documents")
            
        os.chdir(directory)
        
        def run_server():
            try:
                self.server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
                self.running = True
                self.server.serve_forever()
            except Exception as e:
                print(f"Error en servidor NAS: {e}")
                
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        
        # Obtener IP local
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        
        return f"Servidor NAS iniciado en {ip}:{port} - Compartiendo {directory}"
        
    def stop_server(self):
        """Detiene el servidor"""
        if not self.running:
            return "Servidor no está en ejecución"
            
        self.running = False
        if self.server:
            self.server.shutdown()
            self.server = None
            
        return "Servidor NAS detenido"
        
    def share_folder(self, folder_path):
        """Comparte una carpeta específica"""
        if not os.path.exists(folder_path):
            return f"La carpeta {folder_path} no existe"
            
        self.shared_dirs.append(folder_path)
        
        # Guardar configuración
        config_file = Path("config/nas_config.json")
        config = {}
        if config_file.exists():
            config = json.loads(config_file.read_text(encoding='utf-8'))
            
        config['shared_dirs'] = self.shared_dirs
        config_file.write_text(json.dumps(config, indent=2), encoding='utf-8')
        
        return f"Carpeta compartida: {folder_path}"

def file_server(parameters: dict, player=None):
    """
    Servidor NAS virtual para NEXUS
    
    Args:
        parameters: {
            'action': 'start' | 'stop' | 'share_folder',
            'port': (opcional) puerto para el servidor,
            'directory': (opcional) directorio a compartir,
            'folder_path': (opcional) carpeta específica
        }
    """
    action = parameters.get('action', 'start')
    port = parameters.get('port', 8000)
    directory = parameters.get('directory')
    folder_path = parameters.get('folder_path')
    
    # Singleton
    if not hasattr(file_server, 'instance'):
        file_server.instance = NASServer()
    
    server = file_server.instance
    
    if action == 'start':
        return server.start_server(port, directory)
        
    elif action == 'stop':
        return server.stop_server()
        
    elif action == 'share_folder':
        if not folder_path:
            return "Proporciona la ruta de la carpeta"
        return server.share_folder(folder_path)
        
    else:
        return "Acción no reconocida. Usa: start, stop, share_folder"