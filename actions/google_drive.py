"""
Google Drive Module for ILUM
============================
Gestión completa de Google Drive: listar, subir, descargar, buscar, crear carpetas,
compartir, eliminar, sincronizar y más.
"""

import os
import json
import io
import time
import mimetypes
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import threading
import queue

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
    from googleapiclient.errors import HttpError
except ImportError:
    build = None
    Credentials = None
    InstalledAppFlow = None
    MediaFileUpload = None
    MediaIoBaseDownload = None
    HttpError = Exception

# ─── CONFIGURACIÓN ─────────────────────────────────────────────────────────
CONFIG_DIR = Path("config")
CREDENTIALS_FILE = CONFIG_DIR / "google_drive_credentials.json"
TOKEN_FILE = CONFIG_DIR / "google_drive_token.json"
CACHE_DIR = CONFIG_DIR / "google_drive_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Scopes necesarios
SCOPES = [
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/drive.metadata.readonly'
]

# ─── GESTOR DE GOOGLE DRIVE ──────────────────────────────────────────────
class GoogleDriveManager:
    """Gestor principal de Google Drive."""
    
    def __init__(self):
        self.service = None
        self._cache = {}
        self._cache_timestamp = {}
        self._cache_lifetime = 60  # segundos
        self._authenticate()
    
    def _authenticate(self) -> bool:
        """Autentica con Google Drive usando OAuth 2.0."""
        if not build or not Credentials or not InstalledAppFlow:
            print("[GoogleDrive] Dependencias no instaladas")
            return False
        
        creds = None
        
        # Cargar token guardado
        if TOKEN_FILE.exists():
            try:
                creds = Credentials.from_authorized_user_info(
                    json.loads(TOKEN_FILE.read_text(encoding="utf-8")),
                    SCOPES
                )
            except:
                pass
        
        # Si no hay credenciales o expiraron, renovar
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except:
                    creds = None
            
            # Si sigue sin credenciales, pedir login
            if not creds:
                if not CREDENTIALS_FILE.exists():
                    print("[GoogleDrive] ⚠️ Credenciales no encontradas")
                    print("[GoogleDrive] Por favor, coloca google_drive_credentials.json en config/")
                    return False
                
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(CREDENTIALS_FILE), SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    print(f"[GoogleDrive] Error en autenticación: {e}")
                    return False
            
            # Guardar token
            try:
                TOKEN_FILE.write_text(
                    json.dumps(json.loads(creds.to_json()), indent=2),
                    encoding="utf-8"
                )
            except:
                pass
        
        try:
            self.service = build('drive', 'v3', credentials=creds)
            print("[GoogleDrive] ✅ Autenticado correctamente")
            return True
        except Exception as e:
            print(f"[GoogleDrive] Error creando servicio: {e}")
            return False
    
    def _get_cache(self, key: str, max_age: int = None) -> Optional[Any]:
        """Obtiene un valor de la caché."""
        if max_age is None:
            max_age = self._cache_lifetime
        
        if key in self._cache:
            timestamp = self._cache_timestamp.get(key, 0)
            if time.time() - timestamp < max_age:
                return self._cache[key]
        return None
    
    def _set_cache(self, key: str, value: Any):
        """Guarda un valor en la caché."""
        self._cache[key] = value
        self._cache_timestamp[key] = time.time()
    
    def _clear_cache(self):
        """Limpia la caché."""
        self._cache = {}
        self._cache_timestamp = {}
    
    # ─── LISTAR ARCHIVOS ──────────────────────────────────────────────────
    def list_files(self, folder_id: str = "root", query: str = None, 
                   limit: int = 50, order_by: str = "modifiedTime desc") -> List[Dict]:
        """
        Lista archivos en una carpeta de Google Drive.
        
        Args:
            folder_id: ID de la carpeta (default: root)
            query: Filtro de búsqueda adicional
            limit: Límite de resultados
            order_by: Ordenamiento
        
        Returns:
            Lista de archivos
        """
        if not self.service:
            return []
        
        try:
            # Construir query
            q = f"'{folder_id}' in parents and trashed=false"
            if query:
                q += f" and ({query})"
            
            # Ejecutar búsqueda
            results = self.service.files().list(
                q=q,
                pageSize=limit,
                orderBy=order_by,
                fields="files(id, name, mimeType, size, createdTime, modifiedTime, webViewLink, parents)"
            ).execute()
            
            files = results.get('files', [])
            
            # Agregar información extra
            for file in files:
                file['size_human'] = self._format_size(file.get('size', 0))
                file['is_folder'] = file.get('mimeType') == 'application/vnd.google-apps.folder'
            
            return files
            
        except HttpError as e:
            print(f"[GoogleDrive] Error listando archivos: {e}")
            return []
    
    def _format_size(self, size: int) -> str:
        """Formatea el tamaño de archivo."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
    
    # ─── BUSCAR ARCHIVOS ──────────────────────────────────────────────────
    def search_files(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Busca archivos por nombre o contenido.
        
        Args:
            query: Término de búsqueda
            limit: Límite de resultados
        
        Returns:
            Lista de archivos encontrados
        """
        if not self.service or not query:
            return []
        
        try:
            # Buscar por nombre
            q = f"name contains '{query}' and trashed=false"
            results = self.service.files().list(
                q=q,
                pageSize=limit,
                orderBy="modifiedTime desc",
                fields="files(id, name, mimeType, size, createdTime, modifiedTime, webViewLink)"
            ).execute()
            
            files = results.get('files', [])
            
            # Agregar información extra
            for file in files:
                file['size_human'] = self._format_size(file.get('size', 0))
                file['is_folder'] = file.get('mimeType') == 'application/vnd.google-apps.folder'
            
            return files
            
        except HttpError as e:
            print(f"[GoogleDrive] Error en búsqueda: {e}")
            return []
    
    # ─── SUBIR ARCHIVO ────────────────────────────────────────────────────
    def upload_file(self, local_path: str, drive_folder_id: str = "root", 
                    name: str = None, mime_type: str = None) -> Dict:
        """
        Sube un archivo a Google Drive.
        
        Args:
            local_path: Ruta del archivo local
            drive_folder_id: ID de la carpeta destino
            name: Nombre en Drive (opcional)
            mime_type: Tipo MIME (opcional, se detecta automáticamente)
        
        Returns:
            Información del archivo subido
        """
        if not self.service:
            return {"error": "No autenticado"}
        
        path = Path(local_path)
        if not path.exists():
            return {"error": f"Archivo no encontrado: {local_path}"}
        
        try:
            # Detectar MIME type
            if not mime_type:
                mime_type, _ = mimetypes.guess_type(str(path))
                if not mime_type:
                    mime_type = 'application/octet-stream'
            
            # Preparar metadata
            file_metadata = {
                'name': name or path.name,
                'parents': [drive_folder_id]
            }
            
            # Subir archivo
            media = MediaFileUpload(str(path), mimetype=mime_type, resumable=True)
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, mimeType, size, webViewLink'
            ).execute()
            
            file['size_human'] = self._format_size(file.get('size', 0))
            file['is_folder'] = False
            
            self._clear_cache()
            return file
            
        except HttpError as e:
            return {"error": f"Error al subir: {e}"}
        except Exception as e:
            return {"error": str(e)}
    
    # ─── DESCARGAR ARCHIVO ────────────────────────────────────────────────
    def download_file(self, file_id: str, local_path: str) -> Dict:
        """
        Descarga un archivo de Google Drive.
        
        Args:
            file_id: ID del archivo en Drive
            local_path: Ruta local para guardar
        
        Returns:
            Resultado de la descarga
        """
        if not self.service:
            return {"error": "No autenticado"}
        
        try:
            # Obtener metadata del archivo
            file_metadata = self.service.files().get(
                fileId=file_id,
                fields='name, mimeType, size'
            ).execute()
            
            # Preparar descarga
            request = self.service.files().get_media(fileId=file_id)
            
            # Crear directorio si no existe
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Descargar
            fh = io.FileIO(local_path, 'wb')
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    if progress % 10 == 0:
                        print(f"[GoogleDrive] Descargando... {progress}%")
            
            return {
                "success": True,
                "file": local_path,
                "name": file_metadata.get('name'),
                "size": file_metadata.get('size', 0),
                "size_human": self._format_size(file_metadata.get('size', 0))
            }
            
        except HttpError as e:
            return {"error": f"Error al descargar: {e}"}
        except Exception as e:
            return {"error": str(e)}
    
    # ─── CREAR CARPETA ────────────────────────────────────────────────────
    def create_folder(self, name: str, parent_id: str = "root") -> Dict:
        """
        Crea una carpeta en Google Drive.
        
        Args:
            name: Nombre de la carpeta
            parent_id: ID de la carpeta padre (default: root)
        
        Returns:
            Información de la carpeta creada
        """
        if not self.service:
            return {"error": "No autenticado"}
        
        try:
            file_metadata = {
                'name': name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id]
            }
            
            folder = self.service.files().create(
                body=file_metadata,
                fields='id, name, mimeType, webViewLink'
            ).execute()
            
            folder['is_folder'] = True
            self._clear_cache()
            return folder
            
        except HttpError as e:
            return {"error": f"Error al crear carpeta: {e}"}
    
    # ─── ELIMINAR ARCHIVO ─────────────────────────────────────────────────
    def delete_file(self, file_id: str) -> Dict:
        """
        Elimina un archivo de Google Drive (lo mueve a la papelera).
        
        Args:
            file_id: ID del archivo
        
        Returns:
            Resultado de la operación
        """
        if not self.service:
            return {"error": "No autenticado"}
        
        try:
            self.service.files().delete(fileId=file_id).execute()
            self._clear_cache()
            return {"success": True, "message": "Archivo eliminado correctamente"}
            
        except HttpError as e:
            return {"error": f"Error al eliminar: {e}"}
    
    # ─── COMPARTIR ARCHIVO ────────────────────────────────────────────────
    def share_file(self, file_id: str, email: str, role: str = "reader") -> Dict:
        """
        Comparte un archivo con un usuario.
        
        Args:
            file_id: ID del archivo
            email: Email del usuario
            role: reader | writer | commenter | organizer
        
        Returns:
            Resultado de la operación
        """
        if not self.service:
            return {"error": "No autenticado"}
        
        try:
            permission = {
                'type': 'user',
                'role': role,
                'emailAddress': email
            }
            
            self.service.permissions().create(
                fileId=file_id,
                body=permission,
                sendNotificationEmail=True
            ).execute()
            
            return {"success": True, "message": f"Archivo compartido con {email}"}
            
        except HttpError as e:
            return {"error": f"Error al compartir: {e}"}
    
    # ─── OBTENER INFORMACIÓN ──────────────────────────────────────────────
    def get_file_info(self, file_id: str) -> Dict:
        """
        Obtiene información detallada de un archivo.
        
        Args:
            file_id: ID del archivo
        
        Returns:
            Información del archivo
        """
        if not self.service:
            return {"error": "No autenticado"}
        
        try:
            file = self.service.files().get(
                fileId=file_id,
                fields='id, name, mimeType, size, createdTime, modifiedTime, webViewLink, parents, description, star, viewedByMeTime'
            ).execute()
            
            file['size_human'] = self._format_size(file.get('size', 0))
            file['is_folder'] = file.get('mimeType') == 'application/vnd.google-apps.folder'
            
            return file
            
        except HttpError as e:
            return {"error": f"Error al obtener información: {e}"}
    
    # ─── SINCRONIZAR CARPETA ─────────────────────────────────────────────
    def sync_folder(self, drive_folder_id: str, local_folder: str, 
                    direction: str = "both") -> Dict:
        """
        Sincroniza una carpeta de Drive con una carpeta local.
        
        Args:
            drive_folder_id: ID de la carpeta en Drive
            local_folder: Ruta de la carpeta local
            direction: "download", "upload", "both"
        
        Returns:
            Resultado de la sincronización
        """
        if not self.service:
            return {"error": "No autenticado"}
        
        result = {
            "downloaded": 0,
            "uploaded": 0,
            "skipped": 0,
            "errors": []
        }
        
        local_path = Path(local_folder)
        local_path.mkdir(parents=True, exist_ok=True)
        
        try:
            # Obtener archivos en Drive
            drive_files = self.list_files(drive_folder_id, limit=1000)
            drive_files_by_name = {f['name']: f for f in drive_files}
            
            # Descargar archivos de Drive que no están en local
            if direction in ["download", "both"]:
                for file in drive_files:
                    if file.get('is_folder'):
                        continue
                    
                    local_file = local_path / file['name']
                    if not local_file.exists():
                        # Descargar archivo
                        result['downloaded'] += 1
                        self.download_file(file['id'], str(local_file))
                    else:
                        # Verificar si necesita actualización
                        file_size = file.get('size', 0)
                        local_size = local_file.stat().st_size
                        if file_size != local_size:
                            result['downloaded'] += 1
                            self.download_file(file['id'], str(local_file))
                        else:
                            result['skipped'] += 1
            
            # Subir archivos locales que no están en Drive
            if direction in ["upload", "both"]:
                for local_file in local_path.iterdir():
                    if local_file.is_dir():
                        continue
                    
                    if local_file.name not in drive_files_by_name:
                        result['uploaded'] += 1
                        self.upload_file(str(local_file), drive_folder_id)
            
            return result
            
        except Exception as e:
            result['errors'].append(str(e))
            return result
    
    # ─── ESTADÍSTICAS ────────────────────────────────────────────────────
    def get_stats(self) -> Dict:
        """Obtiene estadísticas de Google Drive."""
        if not self.service:
            return {"error": "No autenticado"}
        
        try:
            # Obtener total de archivos
            about = self.service.about().get(
                fields="storageQuota, user"
            ).execute()
            
            # Obtener archivos recientes
            recent = self.list_files(limit=10)
            
            stats = {
                "user": about.get('user', {}),
                "storage": about.get('storageQuota', {}),
                "total_files": len(self.search_files("", 1000)),
                "recent_files": recent
            }
            
            return stats
            
        except HttpError as e:
            return {"error": str(e)}


# ─── INSTANCIA GLOBAL ────────────────────────────────────────────────────
_drive_manager: Optional[GoogleDriveManager] = None

def get_drive_manager() -> GoogleDriveManager:
    """Obtiene la instancia del gestor de Google Drive."""
    global _drive_manager
    if _drive_manager is None:
        _drive_manager = GoogleDriveManager()
    return _drive_manager


# ─── FUNCIÓN PRINCIPAL ────────────────────────────────────────────────────
def google_drive(parameters: dict, player=None) -> str:
    """
    Controla Google Drive.
    
    Args:
        parameters: Diccionario con parámetros
            - action: list | search | upload | download | create_folder | delete | share | info | sync | stats
            - file_id: ID del archivo
            - folder_id: ID de la carpeta
            - name: Nombre (para crear carpeta o buscar)
            - path: Ruta local (para upload/download)
            - query: Término de búsqueda
            - limit: Límite de resultados
            - email: Email para compartir
            - role: reader | writer | commenter
    
    Returns:
        Mensaje de resultado
    """
    p = parameters or {}
    action = p.get("action", "list").strip().lower()
    file_id = p.get("file_id", "").strip()
    folder_id = p.get("folder_id", "root").strip()
    name = p.get("name", "").strip()
    path = p.get("path", "").strip()
    query = p.get("query", "").strip()
    limit = int(p.get("limit", 20))
    email = p.get("email", "").strip()
    role = p.get("role", "reader").strip()
    
    drive = get_drive_manager()
    
    if not drive.service:
        return (
            "❌ No se pudo autenticar con Google Drive.\n\n"
            "💡 Para configurar:\n"
            "1. Ve a Google Cloud Console\n"
            "2. Crea un proyecto y habilita Drive API\n"
            "3. Descarga credentials.json\n"
            "4. Colócalo en: config/google_drive_credentials.json"
        )
    
    # ─── LISTAR ──────────────────────────────────────────────────────────
    if action == "list":
        files = drive.list_files(folder_id, limit=limit)
        
        if not files:
            return "📭 La carpeta está vacía"
        
        lines = [
            f"📂 Archivos en carpeta ({len(files)} mostrados):",
            "━━━━━━━━━━━━━━━━━━━━━━━━━"
        ]
        
        for file in files:
            icon = "📁" if file.get('is_folder') else "📄"
            modified = file.get('modifiedTime', '')[:16].replace('T', ' ')
            size = file.get('size_human', 'N/A')
            lines.append(f"{icon} {file['name']}")
            lines.append(f"  📅 {modified} | 📦 {size} | 🆔 {file['id'][:8]}...")
        
        return "\n".join(lines)
    
    # ─── BUSCAR ──────────────────────────────────────────────────────────
    elif action == "search":
        if not query:
            return "❌ Especifica un término de búsqueda (query='...')"
        
        files = drive.search_files(query, limit)
        
        if not files:
            return f"🔍 No se encontraron archivos para '{query}'"
        
        lines = [
            f"🔍 Resultados para '{query}' ({len(files)} encontrados):",
            "━━━━━━━━━━━━━━━━━━━━━━━━━"
        ]
        
        for file in files:
            icon = "📁" if file.get('is_folder') else "📄"
            size = file.get('size_human', 'N/A')
            lines.append(f"{icon} {file['name']} ({size})")
            lines.append(f"  🆔 {file['id']}")
        
        return "\n".join(lines)
    
    # ─── SUBIR ──────────────────────────────────────────────────────────
    elif action == "upload":
        if not path:
            return "❌ Especifica la ruta del archivo (path='...')"
        
        result = drive.upload_file(path, folder_id, name)
        
        if "error" in result:
            return f"❌ Error al subir: {result['error']}"
        
        return (
            f"✅ Archivo subido: {result.get('name')}\n"
            f"  🆔 {result.get('id')}\n"
            f"  📦 {result.get('size_human')}"
        )
    
    # ─── DESCARGAR ──────────────────────────────────────────────────────
    elif action == "download":
        if not file_id:
            return "❌ Especifica el ID del archivo (file_id='...')"
        
        if not path:
            # Usar nombre del archivo
            info = drive.get_file_info(file_id)
            if "error" in info:
                return f"❌ {info['error']}"
            path = f"downloads/{info.get('name', 'archivo')}"
        
        result = drive.download_file(file_id, path)
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        return (
            f"✅ Archivo descargado: {result.get('name')}\n"
            f"  📂 {result.get('file')}\n"
            f"  📦 {result.get('size_human')}"
        )
    
    # ─── CREAR CARPETA ──────────────────────────────────────────────────
    elif action == "create_folder":
        if not name:
            return "❌ Especifica el nombre de la carpeta (name='...')"
        
        result = drive.create_folder(name, folder_id)
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        return (
            f"✅ Carpeta creada: {result.get('name')}\n"
            f"  🆔 {result.get('id')}"
        )
    
    # ─── ELIMINAR ──────────────────────────────────────────────────────
    elif action == "delete":
        if not file_id:
            return "❌ Especifica el ID del archivo (file_id='...')"
        
        result = drive.delete_file(file_id)
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        return f"🗑️ Archivo eliminado correctamente"
    
    # ─── COMPARTIR ──────────────────────────────────────────────────────
    elif action == "share":
        if not file_id or not email:
            return "❌ Especifica file_id y email"
        
        result = drive.share_file(file_id, email, role)
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        return f"✅ Archivo compartido con {email} (rol: {role})"
    
    # ─── INFORMACIÓN ────────────────────────────────────────────────────
    elif action == "info":
        if not file_id:
            return "❌ Especifica el ID del archivo (file_id='...')"
        
        info = drive.get_file_info(file_id)
        
        if "error" in info:
            return f"❌ {info['error']}"
        
        lines = [
            f"📊 INFORMACIÓN DEL ARCHIVO",
            "━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"📄 Nombre: {info.get('name')}",
            f"🆔 ID: {info.get('id')}",
            f"📂 Tipo: {'📁 Carpeta' if info.get('is_folder') else '📄 Archivo'}",
            f"📦 Tamaño: {info.get('size_human', 'N/A')}",
            f"📅 Creado: {info.get('createdTime', '')[:16].replace('T', ' ')}",
            f"📅 Modificado: {info.get('modifiedTime', '')[:16].replace('T', ' ')}",
            f"🔗 Enlace: {info.get('webViewLink', 'N/A')}",
            f"⭐ Favorito: {'✅' if info.get('star') else '❌'}"
        ]
        
        if info.get('description'):
            lines.append(f"📝 Descripción: {info['description']}")
        
        return "\n".join(lines)
    
    # ─── SINCRONIZAR ────────────────────────────────────────────────────
    elif action == "sync":
        if not folder_id or not path:
            return "❌ Especifica folder_id y path"
        
        direction = p.get("direction", "both")
        result = drive.sync_folder(folder_id, path, direction)
        
        if result.get('errors'):
            return f"⚠️ Sincronización con errores:\n{chr(10).join(result['errors'])}"
        
        return (
            f"✅ Sincronización completada\n"
            f"  📥 Descargados: {result.get('downloaded', 0)}\n"
            f"  📤 Subidos: {result.get('uploaded', 0)}\n"
            f"  ⏭️ Omitidos: {result.get('skipped', 0)}"
        )
    
    # ─── ESTADÍSTICAS ──────────────────────────────────────────────────
    elif action == "stats":
        stats = drive.get_stats()
        
        if "error" in stats:
            return f"❌ {stats['error']}"
        
        storage = stats.get('storage', {})
        usage = int(storage.get('usage', 0))
        limit = int(storage.get('limit', 0))
        percent = (usage / limit * 100) if limit > 0 else 0
        
        lines = [
            "📊 ESTADÍSTICAS DE GOOGLE DRIVE",
            "━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"👤 Usuario: {stats.get('user', {}).get('displayName', 'N/A')}",
            f"📧 Email: {stats.get('user', {}).get('emailAddress', 'N/A')}",
            "",
            "💾 Almacenamiento:",
            f"  Usado: {drive._format_size(usage)}",
            f"  Total: {drive._format_size(limit)}",
            f"  Uso: {percent:.1f}%",
            "",
            f"📂 Total archivos: {stats.get('total_files', 0)}",
            "",
            "📄 Archivos recientes:"
        ]
        
        for file in stats.get('recent_files', [])[:5]:
            lines.append(f"  • {file.get('name')} ({file.get('size_human', 'N/A')})")
        
        return "\n".join(lines)
    
    # ─── AYUDA ──────────────────────────────────────────────────────────
    else:
        return (
            "📖 COMANDOS DE GOOGLE DRIVE\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📋 list - Listar archivos\n"
            "  folder_id='root' limit=20\n\n"
            "🔍 search - Buscar archivos\n"
            "  query='término' limit=20\n\n"
            "📤 upload - Subir archivo\n"
            "  path='ruta' [folder_id='root'] [name='nombre']\n\n"
            "📥 download - Descargar archivo\n"
            "  file_id='ID' [path='ruta']\n\n"
            "📁 create_folder - Crear carpeta\n"
            "  name='nombre' [folder_id='root']\n\n"
            "🗑️ delete - Eliminar archivo\n"
            "  file_id='ID'\n\n"
            "🔗 share - Compartir archivo\n"
            "  file_id='ID' email='email' role='reader'\n\n"
            "📊 info - Información del archivo\n"
            "  file_id='ID'\n\n"
            "🔄 sync - Sincronizar carpeta\n"
            "  folder_id='ID' path='ruta' direction='both'\n\n"
            "📊 stats - Estadísticas de Drive\n\n"
            "📌 Ejemplos:\n"
            "  {'action':'list'}\n"
            "  {'action':'search','query':'reporte'}\n"
            "  {'action':'upload','path':'C:/doc.pdf'}\n"
            "  {'action':'share','file_id':'abc123','email':'user@gmail.com'}"
        )


# ─── INICIALIZACIÓN ──────────────────────────────────────────────────────
def init_google_drive():
    """Inicializa el módulo de Google Drive."""
    print("[GoogleDrive] Inicializando...")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    # Verificar dependencias
    if not build:
        print("[GoogleDrive] ⚠️ Google API no instalado")
        print("[GoogleDrive] Instalar: pip install google-auth google-auth-oauthlib google-api-python-client")
    
    # Verificar credenciales
    if not CREDENTIALS_FILE.exists():
        print("[GoogleDrive] ⚠️ Credenciales no encontradas")
        print("[GoogleDrive] Coloca google_drive_credentials.json en config/")
    
    print("[GoogleDrive] ✅ Listo")
    return True