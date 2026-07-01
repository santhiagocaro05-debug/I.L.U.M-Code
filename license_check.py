
import sys
import os
import ctypes
import hashlib
import json
import datetime

def validate_license():
    """Verifica licencia"""
    try:
        # Obtener HWID
        import subprocess
        result = subprocess.run(['wmic', 'csproduct', 'get', 'uuid'], capture_output=True, text=True)
        hwid = result.stdout.strip().split('\n')[-1].strip()
        
        # Leer licencia
        lic_path = os.path.join(os.path.dirname(sys.executable), 'config', 'license.dat')
        if not os.path.exists(lic_path):
            return False
        
        with open(lic_path, 'rb') as f:
            lic_data = f.read()
            # Verificación simple (en producción usar RSA)
            expected = hashlib.sha256(f"{hwid}:ILUM_2025".encode()).hexdigest()
            return lic_data.decode() == expected
    except:
        return False

if not validate_license():
    ctypes.windll.user32.MessageBoxW(0, "Licencia inválida o expirada", "ILUM", 0x10)
    ctypes.windll.kernel32.ExitProcess(0)
