import os
import shutil
import subprocess
from pathlib import Path
import psutil

class SystemCleaner:
    def __init__(self):
        self.cleaned_space = 0
        
    def clean_temp_files(self):
        """Limpia archivos temporales"""
        total_cleaned = 0
        
        # Directorios temporales
        temp_dirs = [
            Path(os.environ['TEMP']),
            Path(os.environ['TMP']),
            Path("C:/Windows/Temp"),
            Path.home() / "AppData/Local/Temp"
        ]
        
        for temp_dir in temp_dirs:
            if temp_dir.exists():
                try:
                    for file in temp_dir.iterdir():
                        try:
                            if file.is_file():
                                size = file.stat().st_size
                                file.unlink()
                                total_cleaned += size
                            elif file.is_dir():
                                shutil.rmtree(file, ignore_errors=True)
                        except:
                            continue
                except:
                    pass
                    
        self.cleaned_space = total_cleaned / (1024**2)  # MB
        return f"Archivos temporales limpiados. Liberados: {self.cleaned_space:.2f} MB"
        
    def empty_recycle_bin(self):
        """Vacía la papelera de reciclaje"""
        try:
            import winshell
            winshell.recycle_bin().empty(confirm=False, show_progress=False)
            return "Papelera de reciclaje vaciada"
        except:
            return "No se pudo vaciar la papelera"
            
    def clean_browser_cache(self):
        """Limpia caché del navegador"""
        # Chrome
        chrome_cache = Path(os.environ['LOCALAPPDATA']) / "Google/Chrome/User Data/Default/Cache"
        if chrome_cache.exists():
            try:
                shutil.rmtree(chrome_cache, ignore_errors=True)
            except:
                pass
                
        # Edge
        edge_cache = Path(os.environ['LOCALAPPDATA']) / "Microsoft/Edge/User Data/Default/Cache"
        if edge_cache.exists():
            try:
                shutil.rmtree(edge_cache, ignore_errors=True)
            except:
                pass
                
        return "Caché del navegador limpiada"
        
    def clean_all(self):
        """Limpia todo"""
        results = []
        results.append(self.clean_temp_files())
        results.append(self.empty_recycle_bin())
        results.append(self.clean_browser_cache())
        return "\n".join(results)

def cleanup_system(parameters: dict, player=None):
    """
    Limpieza de sistema para NEXUS
    
    Args:
        parameters: {
            'action': 'temp_files' | 'recycle_bin' | 'browser_cache' | 'all'
        }
    """
    action = parameters.get('action', 'all')
    
    # Singleton
    if not hasattr(cleanup_system, 'instance'):
        cleanup_system.instance = SystemCleaner()
    
    cleaner = cleanup_system.instance
    
    if action == 'temp_files':
        return cleaner.clean_temp_files()
        
    elif action == 'recycle_bin':
        return cleaner.empty_recycle_bin()
        
    elif action == 'browser_cache':
        return cleaner.clean_browser_cache()
        
    elif action == 'all':
        return cleaner.clean_all()
        
    else:
        return "Acción no reconocida. Usa: temp_files, recycle_bin, browser_cache, all"