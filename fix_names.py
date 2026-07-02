import re
from pathlib import Path

def fix_all_names():
    """Cambia TODAS las referencias ILUM → NEXUS en los archivos necesarios."""
    
    # Archivos que SÍ deben cambiarse
    files_to_fix = ["ui.py", "main.py", "login.py"]
    
    total_changes = 0
    
    for filename in files_to_fix:
        file_path = Path(filename)
        if not file_path.exists():
            print(f"⚠️ {filename} no encontrado, saltando...")
            continue
            
        content = file_path.read_text(encoding="utf-8")
        original = content
        
        # Reemplazos específicos para cada archivo
        replacements = [
            # Métodos de UI (ui.py)
            (r'def clear_ilum_response\(', 'def clear_nexus_response('),
            (r'def stream_ilum_chunk\(', 'def stream_nexus_chunk('),
            (r'def _clear_ilum_memory\(', 'def _clear_nexus_memory('),
            (r'\.clear_ilum_response\(', '.clear_nexus_response('),
            (r'\.stream_ilum_chunk\(', '.stream_nexus_chunk('),
            (r'\._clear_ilum_memory\(', '._clear_nexus_memory('),
            
            # Nombres de clase y variables
            (r'IlumUI', 'NexusUI'),
            (r'IlumLive', 'NexusLive'),
            (r'ILUM', 'NEXUS'),
            (r'Ilum', 'Nexus'),
            (r'ilum', 'nexus'),
            
            # Nombres de archivos y rutas
            (r'ilum\.log', 'nexus.log'),
            (r'ILUM_AI_SINGLE_INSTANCE_MUTEX', 'NEXUS_AI_SINGLE_INSTANCE_MUTEX'),
            (r'ILUM_AES_TOKEN', 'NEXUS_AES_TOKEN'),
            (r'ILUM_DRM_V2', 'NEXUS_DRM_V2'),
            
            # Strings de UI
            (r'"ILUM ACCESS"', '"NEXUS ACCESS"'),
            (r"'ILUM ACCESS'", "'NEXUS ACCESS'"),
            (r'"ILUM"', '"NEXUS"'),
            (r"'ILUM'", "'NEXUS'"),
            
            # Títulos de ventanas
            (r'ILUM-AI-HUD', 'NEXUS-AI-HUD'),
            
            # Nombres de herramientas en tool declarations (main.py)
            (r'"shutdown_ilum"', '"shutdown_nexus"'),
            (r'"ilum_ui_control"', '"nexus_ui_control"'),
            (r'"_ilum_ui_control"', '"_nexus_ui_control"'),
            
            # Nombres de funciones
            (r'_get_ilum_voice', '_get_nexus_voice'),
            (r'NEXUS_VOICES', 'NEXUS_VOICES'),  # Ya está bien
            (r'ILUM_VOICES', 'NEXUS_VOICES'),  # Si quedó alguno
            
            # Mensajes de log
            (r'\[ILUM\]', '[NEXUS]'),
            (r'SYS: ILUM', 'SYS: NEXUS'),
        ]
        
        for old, new in replacements:
            content = re.sub(old, new, content)
        
        if content != original:
            file_path.write_text(content, encoding="utf-8")
            changes = len(re.findall(r'def (clear|stream|_clear)_nexus', content))  # Cuenta cambios
            print(f"✅ {filename} actualizado")
            total_changes += 1
        else:
            print(f"⏭️ {filename} sin cambios necesarios")
    
    print(f"\n🎉 ¡{total_changes} archivos actualizados!")
    
    # Verificar si quedaron referencias a ILUM
    print("\n🔍 Verificando referencias restantes a 'ilum'...")
    for filename in files_to_fix:
        file_path = Path(filename)
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            # Buscar referencias a ilum (case insensitive)
            matches = re.findall(r'(?i)ilum', content)
            if matches:
                print(f"⚠️ {filename}: {len(matches)} referencias a 'ilum' encontradas")
            else:
                print(f"✅ {filename}: limpio")

if __name__ == "__main__":
    fix_all_names()