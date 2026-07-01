#!/usr/bin/env python3
"""
ILUM Key Generator - Generador de claves de licencia
Uso: python keygen.py [opciones]
"""

import hashlib
import json
import os
import sys
import secrets
import string
import argparse
from datetime import datetime, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    print("Instalando requests...")
    os.system(f"{sys.executable} -m pip install requests")
    import requests

# Configuración
SUPABASE_URL = "https://vktpkyrdmgqmvpxwkwcx.supabase.co"  # Cambiar por tu URL
SUPABASE_KEY = "tu-supabase-anon-key"  

# Caracteres para generar keys
CHARSET = string.ascii_uppercase + string.digits
KEY_PREFIX = "ILUM"

class ILUMKeyGenerator:
    def __init__(self):
        self.licenses = []
        
    def generate_key(self, email: str, days_valid: int = 365) -> dict:
        """Genera una nueva clave de licencia"""
        
        # Generar ID único
        key_id = self._generate_key_id()
        
        # Generar clave en formato ILUM-XXXX-XXXX-XXXX
        key = self._format_key(key_id)
        
        # Fechas
        created_at = datetime.now()
        expires_at = created_at + timedelta(days=days_valid)
        
        license_data = {
            "key": key,
            "email": email.lower().strip(),
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "is_active": True,
            "registered_hwid": None,
            "max_activations": 1,
            "product": "ilum_ai",
            "tier": "premium"
        }
        
        return license_data
    
    def _generate_key_id(self) -> str:
        """Genera ID único para la clave"""
        # Usar secrets para seguridad criptográfica
        random_part = secrets.token_hex(8).upper()
        timestamp_part = hex(int(datetime.now().timestamp()))[2:].upper()
        combined = random_part + timestamp_part
        return combined[:16]
    
    def _format_key(self, key_id: str) -> str:
        """Formatea la clave como ILUM-XXXX-XXXX-XXXX"""
        # Tomar primeros 12 caracteres y formatear
        base = key_id[:12]
        parts = [base[i:i+4] for i in range(0, 12, 4)]
        return f"{KEY_PREFIX}-{'-'.join(parts)}"
    
    def generate_batch(self, emails: list, days_valid: int = 365) -> list:
        """Genera múltiples claves"""
        keys = []
        for email in emails:
            keys.append(self.generate_key(email, days_valid))
        return keys
    
    def save_keys(self, keys: list, filename: str = "generated_keys.json"):
        """Guarda las claves generadas en archivo"""
        output = {
            "generated_at": datetime.now().isoformat(),
            "total": len(keys),
            "keys": keys
        }
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ {len(keys)} clave(s) guardada(s) en {filename}")
        return filename
    
    def upload_to_supabase(self, keys: list, supabase_url: str, supabase_key: str) -> bool:
        """Sube las claves a Supabase (opcional)"""
        try:
            headers = {
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": "application/json"
            }
            
            for key_data in keys:
                response = requests.post(
                    f"{supabase_url}/rest/v1/licenses",
                    headers=headers,
                    json=key_data
                )
                
                if response.status_code not in (200, 201):
                    print(f"❌ Error subiendo {key_data['key']}: {response.text}")
                    return False
                else:
                    print(f"✅ Subida: {key_data['key']} -> {key_data['email']}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error de conexión: {e}")
            return False
    
    def print_key(self, key_data: dict):
        """Muestra una clave formateada"""
        print("\n" + "="*50)
        print(f"🔑 CLAVE GENERADA")
        print("="*50)
        print(f"  Key:     {key_data['key']}")
        print(f"  Email:   {key_data['email']}")
        print(f"  Creada:  {key_data['created_at'][:19]}")
        print(f"  Expira:  {key_data['expires_at'][:19]}")
        print(f"  Estado:  {'Activa' if key_data['is_active'] else 'Inactiva'}")
        print("="*50)
    
    def verify_key(self, key: str) -> dict:
        """Verifica si una clave tiene formato válido"""
        import re
        
        pattern = r'^ILUM-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$'
        
        if re.match(pattern, key):
            return {"valid": True, "message": "Formato válido"}
        else:
            return {"valid": False, "message": "Formato inválido. Debe ser ILUM-XXXX-XXXX-XXXX"}


class HWIDGenerator:
    """Generador de HWID para pruebas"""
    
    @staticmethod
    def get_current_hwid() -> str:
        """Obtiene el HWID actual del sistema"""
        try:
            import subprocess
            result = subprocess.run(
                ['wmic', 'csproduct', 'get', 'uuid'],
                capture_output=True, text=True
            )
            hwid = result.stdout.strip().split('\n')[-1].strip()
            return hwid if hwid else HWIDGenerator._generate_fallback_hwid()
        except:
            return HWIDGenerator._generate_fallback_hwid()
    
    @staticmethod
    def _generate_fallback_hwid() -> str:
        """Genera HWID de respaldo"""
        import platform
        import uuid
        
        system = platform.system()
        node = platform.node()
        combined = f"{system}-{node}-{uuid.getnode()}"
        return hashlib.sha256(combined.encode()).hexdigest()[:32].upper()


def main():
    parser = argparse.ArgumentParser(description="ILUM Key Generator")
    parser.add_argument("-e", "--email", help="Email del usuario", default="admin@ilum.local")
    parser.add_argument("-d", "--days", type=int, default=365, help="Días de validez")
    parser.add_argument("-b", "--batch", help="Archivo con lista de emails (uno por línea)")
    parser.add_argument("-o", "--output", default="generated_keys.json", help="Archivo de salida")
    parser.add_argument("-u", "--upload", action="store_true", help="Subir a Supabase")
    parser.add_argument("--url", help="Supabase URL", default=SUPABASE_URL)
    parser.add_argument("--key", help="Supabase API Key", default=SUPABASE_KEY)
    parser.add_argument("-v", "--verify", help="Verificar formato de clave")
    parser.add_argument("--hwid", action="store_true", help="Mostrar HWID actual")
    
    args = parser.parse_args()
    
    # Mostrar HWID si se solicita
    if args.hwid:
        hwid = HWIDGenerator.get_current_hwid()
        print(f"\n🖥️  HWID actual: {hwid}")
        return
    
    # Verificar formato de clave
    if args.verify:
        generator = ILUMKeyGenerator()
        result = generator.verify_key(args.verify)
        print(f"\n🔍 Verificación: {result['message']}")
        return
    
    generator = ILUMKeyGenerator()
    
    # Generar claves
    if args.batch:
        with open(args.batch, "r", encoding="utf-8") as f:
            emails = [line.strip() for line in f if line.strip()]
        keys = generator.generate_batch(emails, args.days)
    else:
        keys = [generator.generate_key(args.email, args.days)]
        generator.print_key(keys[0])
    
    # Guardar archivo
    output_file = generator.save_keys(keys, args.output)
    
    # Subir a Supabase si se solicita
    if args.upload:
        print("\n📤 Subiendo a Supabase...")
        success = generator.upload_to_supabase(keys, args.url, args.key)
        if success:
            print("✅ Todas las claves subidas exitosamente")
        else:
            print("⚠️ Algunas claves no pudieron subirse")
    
    # Mostrar resumen
    print(f"\n📊 Resumen:")
    print(f"   Claves generadas: {len(keys)}")
    print(f"   Archivo: {output_file}")
    
    # Mostrar claves en consola
    print("\n📋 CLAVES GENERADAS:")
    print("-" * 50)
    for key_data in keys:
        print(f"  {key_data['key']} -> {key_data['email']}")


def quick_generate():
    """Generación rápida desde línea de comandos"""
    generator = ILUMKeyGenerator()
    
    print("\n" + "="*50)
    print("  ILUM KEY GENERATOR - MODO RÁPIDO")
    print("="*50)
    
    email = input("Email del usuario: ").strip()
    if not email:
        email = "default@ilum.local"
    
    try:
        days = int(input("Días de validez (default 365): ") or "365")
    except:
        days = 365
    
    key_data = generator.generate_key(email, days)
    generator.print_key(key_data)
    
    # Preguntar si guardar
    save = input("\n¿Guardar en archivo? (s/N): ").strip().lower()
    if save == 's':
        filename = generator.save_keys([key_data])
        print(f"\n✅ Guardado en {filename}")
    
    # Preguntar si mostrar HWID
    show_hwid = input("¿Mostrar HWID actual? (s/N): ").strip().lower()
    if show_hwid == 's':
        hwid = HWIDGenerator.get_current_hwid()
        print(f"\n🖥️  HWID: {hwid}")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        quick_generate()
    else:
        main()