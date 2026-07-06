"""
Git Control Module for ILUM
===========================
Gestión completa de Git: status, commit, push, pull, branches, stash, logs, diffs y más.
Soporte para múltiples repositorios y operaciones avanzadas.
"""

import os
import sys
import subprocess
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import threading
import queue

# ─── CONFIGURACIÓN ─────────────────────────────────────────────────────────
CONFIG_DIR = Path("config")
GIT_CONFIG_PATH = CONFIG_DIR / "git_config.json"
GIT_CACHE_DIR = CONFIG_DIR / "git_cache"
GIT_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ─── GESTOR DE GIT ────────────────────────────────────────────────────────
class GitManager:
    """Gestor principal de Git."""
    
    def __init__(self):
        self.config = self._load_config()
        self._cache = {}
        self._cache_timestamp = {}
        self._cache_lifetime = 30  # segundos
        self._check_git_installed()
    
    def _load_config(self) -> Dict:
        """Carga la configuración de Git."""
        if GIT_CONFIG_PATH.exists():
            try:
                return json.loads(GIT_CONFIG_PATH.read_text(encoding="utf-8"))
            except:
                return {}
        return {
            "default_repo": "",
            "repos": {},
            "global": {
                "user.name": "",
                "user.email": ""
            }
        }
    
    def _save_config(self):
        """Guarda la configuración."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        GIT_CONFIG_PATH.write_text(
            json.dumps(self.config, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    
    def _check_git_installed(self) -> bool:
        """Verifica si Git está instalado."""
        try:
            subprocess.run(["git", "--version"], 
                         capture_output=True, check=True, shell=True)
            return True
        except:
            print("[Git] ⚠️ Git no está instalado en el sistema")
            return False
    
    def _run_git(self, repo_path: str, args: List[str], 
                 capture: bool = True) -> Tuple[bool, str]:
        """
        Ejecuta un comando Git en un repositorio.
        
        Args:
            repo_path: Ruta del repositorio
            args: Argumentos del comando Git
            capture: Capturar salida
        
        Returns:
            (éxito, salida)
        """
        try:
            cmd = ["git"] + args
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=capture,
                text=True,
                shell=True,
                timeout=60
            )
            
            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                return False, result.stderr.strip()
        except subprocess.TimeoutExpired:
            return False, "Comando timeout (más de 60s)"
        except Exception as e:
            return False, str(e)
    
    def _format_commit(self, commit: Dict) -> str:
        """Formatea un commit para mostrar."""
        return f"{commit['hash'][:8]} - {commit['author']} - {commit['message']}"
    
    def _parse_log(self, log_output: str) -> List[Dict]:
        """Parsea la salida de git log."""
        commits = []
        if not log_output:
            return commits
        
        # Formato: hash|author|date|message
        for line in log_output.split('\n'):
            if line.strip():
                parts = line.split('|', 3)
                if len(parts) >= 4:
                    commits.append({
                        'hash': parts[0],
                        'author': parts[1],
                        'date': parts[2],
                        'message': parts[3]
                    })
        return commits
    
    # ─── OPERACIONES BÁSICAS ─────────────────────────────────────────────
    def status(self, repo_path: str) -> Dict:
        """Obtiene el estado del repositorio."""
        success, output = self._run_git(repo_path, ["status", "--porcelain"])
        
        if not success:
            return {"error": output}
        
        files = []
        for line in output.split('\n'):
            if line:
                status_code = line[:2]
                file_name = line[3:]
                files.append({
                    'status': status_code,
                    'file': file_name,
                    'type': self._get_status_type(status_code)
                })
        
        # Obtener información de la rama
        branch_success, branch_output = self._run_git(repo_path, ["branch", "--show-current"])
        branch = branch_output.strip() if branch_success else "detached"
        
        return {
            "branch": branch,
            "files": files,
            "modified": sum(1 for f in files if 'M' in f['status']),
            "added": sum(1 for f in files if 'A' in f['status']),
            "deleted": sum(1 for f in files if 'D' in f['status']),
            "untracked": sum(1 for f in files if '??' in f['status'])
        }
    
    def _get_status_type(self, status: str) -> str:
        """Obtiene el tipo de cambio del archivo."""
        if 'A' in status:
            return "añadido"
        elif 'M' in status:
            return "modificado"
        elif 'D' in status:
            return "eliminado"
        elif 'R' in status:
            return "renombrado"
        elif '??' in status:
            return "no seguido"
        else:
            return "cambiado"
    
    def commit(self, repo_path: str, message: str, 
               add_all: bool = True, files: List[str] = None) -> Dict:
        """
        Realiza un commit.
        
        Args:
            repo_path: Ruta del repositorio
            message: Mensaje del commit
            add_all: Agregar todos los cambios
            files: Lista de archivos específicos (opcional)
        """
        # Agregar archivos
        if add_all:
            success, output = self._run_git(repo_path, ["add", "-A"])
            if not success:
                return {"error": f"Error al agregar archivos: {output}"}
        elif files:
            success, output = self._run_git(repo_path, ["add"] + files)
            if not success:
                return {"error": f"Error al agregar archivos: {output}"}
        
        # Realizar commit
        success, output = self._run_git(repo_path, ["commit", "-m", message])
        
        if success:
            # Obtener hash del commit
            hash_success, hash_output = self._run_git(repo_path, ["rev-parse", "HEAD"])
            return {
                "success": True,
                "message": message,
                "hash": hash_output.strip()[:8] if hash_success else "unknown"
            }
        else:
            return {"error": output}
    
    def push(self, repo_path: str, remote: str = "origin", 
             branch: str = None, force: bool = False) -> Dict:
        """Sube cambios al remoto."""
        if not branch:
            success, branch_output = self._run_git(repo_path, ["branch", "--show-current"])
            branch = branch_output.strip() if success else "main"
        
        args = ["push"]
        if force:
            args.append("--force")
        args.extend([remote, branch])
        
        success, output = self._run_git(repo_path, args)
        
        if success:
            return {"success": True, "message": f"Push a {remote}/{branch} completado"}
        else:
            return {"error": output}
    
    def pull(self, repo_path: str, remote: str = "origin", 
             branch: str = None, rebase: bool = False) -> Dict:
        """Trae cambios del remoto."""
        if not branch:
            success, branch_output = self._run_git(repo_path, ["branch", "--show-current"])
            branch = branch_output.strip() if success else "main"
        
        args = ["pull"]
        if rebase:
            args.append("--rebase")
        args.extend([remote, branch])
        
        success, output = self._run_git(repo_path, args)
        
        if success:
            return {"success": True, "message": f"Pull de {remote}/{branch} completado"}
        else:
            return {"error": output}
    
    def log(self, repo_path: str, n: int = 10, 
            author: str = None, since: str = None) -> Dict:
        """Obtiene el historial de commits."""
        args = [
            "log",
            f"-{n}",
            "--pretty=format:%H|%an|%ad|%s",
            "--date=short"
        ]
        
        if author:
            args.append(f"--author={author}")
        if since:
            args.append(f"--since={since}")
        
        success, output = self._run_git(repo_path, args)
        
        if success:
            commits = self._parse_log(output)
            return {
                "success": True,
                "commits": commits,
                "count": len(commits)
            }
        else:
            return {"error": output}
    
    def diff(self, repo_path: str, file: str = None, 
             staged: bool = False, commit1: str = None, commit2: str = None) -> Dict:
        """Muestra diferencias en el repositorio."""
        args = ["diff"]
        
        if staged:
            args.append("--staged")
        if file:
            args.append(file)
        if commit1 and commit2:
            args = ["diff", f"{commit1}..{commit2}"]
            if file:
                args.append(file)
        
        success, output = self._run_git(repo_path, args)
        
        if success:
            # Parsear diff para mostrar resumen
            changes = {
                "additions": 0,
                "deletions": 0,
                "files_changed": 0,
                "raw": output
            }
            
            # Contar cambios
            for line in output.split('\n'):
                if line.startswith('+') and not line.startswith('+++'):
                    changes["additions"] += 1
                elif line.startswith('-') and not line.startswith('---'):
                    changes["deletions"] += 1
                elif line.startswith('diff --git'):
                    changes["files_changed"] += 1
            
            return {"success": True, "changes": changes}
        else:
            return {"error": output}
    
    # ─── BRANCHES ─────────────────────────────────────────────────────────
    def list_branches(self, repo_path: str) -> Dict:
        """Lista las ramas del repositorio."""
        # Obtener rama actual
        success, current = self._run_git(repo_path, ["branch", "--show-current"])
        
        # Listar todas las ramas
        success, output = self._run_git(repo_path, ["branch", "-a"])
        
        if success:
            branches = []
            for line in output.split('\n'):
                if line:
                    is_current = line.startswith('*')
                    name = line[2:].strip()
                    branches.append({
                        'name': name,
                        'current': is_current,
                        'remote': 'remotes/' in name
                    })
            
            return {"success": True, "branches": branches}
        else:
            return {"error": output}
    
    def create_branch(self, repo_path: str, branch_name: str, 
                      from_branch: str = None) -> Dict:
        """Crea una nueva rama."""
        args = ["checkout", "-b", branch_name]
        if from_branch:
            args.append(from_branch)
        
        success, output = self._run_git(repo_path, args)
        
        if success:
            return {"success": True, "message": f"Rama '{branch_name}' creada"}
        else:
            return {"error": output}
    
    def checkout(self, repo_path: str, branch: str) -> Dict:
        """Cambia a otra rama."""
        success, output = self._run_git(repo_path, ["checkout", branch])
        
        if success:
            return {"success": True, "message": f"Cambiado a rama '{branch}'"}
        else:
            return {"error": output}
    
    def delete_branch(self, repo_path: str, branch_name: str, force: bool = False) -> Dict:
        """Elimina una rama."""
        args = ["branch", "-d"]
        if force:
            args.append("-D")
        args.append(branch_name)
        
        success, output = self._run_git(repo_path, args)
        
        if success:
            return {"success": True, "message": f"Rama '{branch_name}' eliminada"}
        else:
            return {"error": output}
    
    def merge(self, repo_path: str, branch: str) -> Dict:
        """Fusiona una rama en la actual."""
        success, output = self._run_git(repo_path, ["merge", branch])
        
        if success:
            return {"success": True, "message": f"Rama '{branch}' fusionada"}
        else:
            return {"error": output}
    
    # ─── STASH ────────────────────────────────────────────────────────────
    def stash_list(self, repo_path: str) -> Dict:
        """Lista los stashes."""
        success, output = self._run_git(repo_path, ["stash", "list"])
        
        if success:
            stashes = []
            for line in output.split('\n'):
                if line:
                    # Formato: stash@{0}: On main: mensaje
                    match = re.match(r'stash@\{(\d+)\}: (.*)', line)
                    if match:
                        stashes.append({
                            'index': int(match.group(1)),
                            'message': match.group(2)
                        })
            
            return {"success": True, "stashes": stashes}
        else:
            return {"error": output}
    
    def stash_push(self, repo_path: str, message: str = None) -> Dict:
        """Guarda cambios en stash."""
        args = ["stash", "push"]
        if message:
            args.extend(["-m", message])
        
        success, output = self._run_git(repo_path, args)
        
        if success:
            return {"success": True, "message": "Cambios guardados en stash"}
        else:
            return {"error": output}
    
    def stash_pop(self, repo_path: str, index: int = 0) -> Dict:
        """Aplica y elimina un stash."""
        args = ["stash", "pop", f"stash@{{{index}}}"]
        
        success, output = self._run_git(repo_path, args)
        
        if success:
            return {"success": True, "message": f"Stash {index} aplicado"}
        else:
            return {"error": output}
    
    def stash_apply(self, repo_path: str, index: int = 0) -> Dict:
        """Aplica un stash sin eliminarlo."""
        args = ["stash", "apply", f"stash@{{{index}}}"]
        
        success, output = self._run_git(repo_path, args)
        
        if success:
            return {"success": True, "message": f"Stash {index} aplicado (mantenido)"}
        else:
            return {"error": output}
    
    def stash_drop(self, repo_path: str, index: int = 0) -> Dict:
        """Elimina un stash."""
        args = ["stash", "drop", f"stash@{{{index}}}"]
        
        success, output = self._run_git(repo_path, args)
        
        if success:
            return {"success": True, "message": f"Stash {index} eliminado"}
        else:
            return {"error": output}
    
    # ─── REPOSITORIOS ────────────────────────────────────────────────────
    def clone(self, url: str, path: str, branch: str = None) -> Dict:
        """Clona un repositorio."""
        args = ["clone", url, path]
        if branch:
            args.extend(["-b", branch])
        
        success, output = self._run_git(str(Path(path).parent), args)
        
        if success:
            self._add_repo(path, url)
            return {"success": True, "message": f"Repositorio clonado en {path}"}
        else:
            return {"error": output}
    
    def init(self, path: str) -> Dict:
        """Inicializa un nuevo repositorio."""
        success, output = self._run_git(path, ["init"])
        
        if success:
            self._add_repo(path, "local")
            return {"success": True, "message": f"Repositorio inicializado en {path}"}
        else:
            return {"error": output}
    
    def add_remote(self, repo_path: str, name: str, url: str) -> Dict:
        """Añade un remoto."""
        success, output = self._run_git(repo_path, ["remote", "add", name, url])
        
        if success:
            return {"success": True, "message": f"Remoto '{name}' añadido"}
        else:
            return {"error": output}
    
    def list_remotes(self, repo_path: str) -> Dict:
        """Lista los remotos."""
        success, output = self._run_git(repo_path, ["remote", "-v"])
        
        if success:
            remotes = []
            seen = set()
            for line in output.split('\n'):
                if line:
                    parts = line.split()
                    if len(parts) >= 2:
                        name = parts[0]
                        url = parts[1]
                        if name not in seen:
                            seen.add(name)
                            remotes.append({
                                'name': name,
                                'url': url
                            })
            
            return {"success": True, "remotes": remotes}
        else:
            return {"error": output}
    
    def _add_repo(self, path: str, url: str):
        """Añade un repositorio a la configuración."""
        repo_name = Path(path).name
        self.config["repos"][repo_name] = {
            "path": str(Path(path).resolve()),
            "url": url,
            "last_used": datetime.now().isoformat()
        }
        self._save_config()
    
    # ─── ANÁLISIS ─────────────────────────────────────────────────────────
    def analyze_repo(self, repo_path: str) -> Dict:
        """Analiza el repositorio en busca de problemas."""
        result = {
            "warnings": [],
            "issues": [],
            "suggestions": []
        }
        
        # Verificar estado
        status = self.status(repo_path)
        if "error" in status:
            result["issues"].append(f"Error al obtener estado: {status['error']}")
            return result
        
        # Verificar archivos sin seguimiento
        if status.get("untracked", 0) > 10:
            result["warnings"].append(
                f"Hay {status['untracked']} archivos sin seguimiento"
            )
            result["suggestions"].append(
                "git add . -A  # Añadir todos o revisar .gitignore"
            )
        
        # Verificar cambios sin commit
        total_changes = status.get("modified", 0) + status.get("added", 0)
        if total_changes > 20:
            result["warnings"].append(
                f"Hay {total_changes} archivos sin commit"
            )
            result["suggestions"].append(
                "git commit -m 'Mensaje descriptivo'  # Hacer commit"
            )
        
        # Verificar si está sincronizado
        remote_success, remote_output = self._run_git(repo_path, ["fetch", "--dry-run"])
        if remote_success and "up to date" not in remote_output:
            result["warnings"].append(
                "El repositorio no está sincronizado con el remoto"
            )
            result["suggestions"].append(
                "git pull  # Traer cambios del remoto"
            )
        
        # Verificar ramas sin fusionar
        branches = self.list_branches(repo_path)
        if "success" in branches:
            unmerged = [b for b in branches.get("branches", []) 
                       if not b.get("current") and not b.get("remote")]
            if len(unmerged) > 3:
                result["warnings"].append(
                    f"Hay {len(unmerged)} ramas locales sin fusionar"
                )
                result["suggestions"].append(
                    "git branch --merged  # Ver ramas fusionadas"
                )
                result["suggestions"].append(
                    "git branch -d <rama>  # Eliminar rama fusionada"
                )
        
        return result


# ─── INSTANCIA GLOBAL ────────────────────────────────────────────────────
_git_manager: Optional[GitManager] = None

def get_git_manager() -> GitManager:
    """Obtiene la instancia del gestor de Git."""
    global _git_manager
    if _git_manager is None:
        _git_manager = GitManager()
    return _git_manager


# ─── FUNCIÓN PRINCIPAL ────────────────────────────────────────────────────
def git_control(parameters: dict, player=None) -> str:
    """
    Controla Git en repositorios.
    
    Args:
        parameters: Diccionario con parámetros
            - action: status | commit | push | pull | log | diff | branches | 
                      branch_create | checkout | branch_delete | merge |
                      stash | stash_pop | stash_apply | stash_drop |
                      clone | init | remote | remote_add | analyze
            - repo_path: Ruta del repositorio
            - message: Mensaje de commit
            - branch: Nombre de la rama
            - file: Archivo específico
            - n: Número de commits para log
            - force: Forzar operación
            - remote: Nombre del remoto
            - url: URL del remoto
            - staged: Mostrar cambios staged
            - commit1, commit2: Hashes para diff
            - since: Fecha para log
            - author: Autor para log
    
    Returns:
        Mensaje de resultado
    """
    p = parameters or {}
    action = p.get("action", "status").strip().lower()
    repo_path = p.get("repo_path", "").strip()
    message = p.get("message", "").strip()
    branch = p.get("branch", "").strip()
    file_path = p.get("file", "").strip()
    n = int(p.get("n", 10))
    force = p.get("force", False)
    remote = p.get("remote", "origin")
    url = p.get("url", "").strip()
    staged = p.get("staged", False)
    commit1 = p.get("commit1", "").strip()
    commit2 = p.get("commit2", "").strip()
    since = p.get("since", "").strip()
    author = p.get("author", "").strip()
    
    git = get_git_manager()
    
    # Si no hay repo_path, usar el por defecto
    if not repo_path and git.config.get("default_repo"):
        repo_path = git.config.get("default_repo")
    
    # ─── STATUS ──────────────────────────────────────────────────────────
    if action == "status":
        if not repo_path:
            return "❌ Especifica la ruta del repositorio (repo_path='...')"
        
        result = git.status(repo_path)
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        lines = [
            f"📊 ESTADO DEL REPOSITORIO",
            f"━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"🌿 Rama: {result['branch']}",
            "",
            f"📝 Cambios:",
            f"  Modificados: {result.get('modified', 0)}",
            f"  Añadidos: {result.get('added', 0)}",
            f"  Eliminados: {result.get('deleted', 0)}",
            f"  No seguidos: {result.get('untracked', 0)}",
        ]
        
        if result.get('files'):
            lines.append("")
            lines.append("📄 Archivos:")
            for file in result['files'][:10]:
                status_map = {
                    "añadido": "➕",
                    "modificado": "✏️",
                    "eliminado": "🗑️",
                    "renombrado": "🔄",
                    "no seguido": "❓",
                    "cambiado": "🔀"
                }
                icon = status_map.get(file['type'], "📄")
                lines.append(f"  {icon} {file['file']} ({file['status']})")
            
            if len(result['files']) > 10:
                lines.append(f"  ... y {len(result['files']) - 10} más")
        
        return "\n".join(lines)
    
    # ─── COMMIT ─────────────────────────────────────────────────────────
    elif action == "commit":
        if not repo_path:
            return "❌ Especifica la ruta del repositorio (repo_path='...')"
        if not message:
            return "❌ Especifica un mensaje de commit (message='...')"
        
        add_all = p.get("add_all", True)
        result = git.commit(repo_path, message, add_all)
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        return f"✅ Commit realizado: {result['message']} ({result.get('hash', '')})"
    
    # ─── PUSH ────────────────────────────────────────────────────────────
    elif action == "push":
        if not repo_path:
            return "❌ Especifica la ruta del repositorio (repo_path='...')"
        
        result = git.push(repo_path, remote, branch, force)
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        return f"✅ {result['message']}"
    
    # ─── PULL ────────────────────────────────────────────────────────────
    elif action == "pull":
        if not repo_path:
            return "❌ Especifica la ruta del repositorio (repo_path='...')"
        
        rebase = p.get("rebase", False)
        result = git.pull(repo_path, remote, branch, rebase)
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        return f"✅ {result['message']}"
    
    # ─── LOG ─────────────────────────────────────────────────────────────
    elif action == "log":
        if not repo_path:
            return "❌ Especifica la ruta del repositorio (repo_path='...')"
        
        result = git.log(repo_path, n, author, since)
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        lines = [
            f"📜 HISTORIAL DE COMMITS ({result['count']} mostrados)",
            "━━━━━━━━━━━━━━━━━━━━━━━━━"
        ]
        
        for commit in result.get('commits', []):
            lines.append(f"🔷 {commit['hash'][:8]} - {commit['author']}")
            lines.append(f"   📅 {commit['date']} - {commit['message']}")
        
        return "\n".join(lines)
    
    # ─── DIFF ────────────────────────────────────────────────────────────
    elif action == "diff":
        if not repo_path:
            return "❌ Especifica la ruta del repositorio (repo_path='...')"
        
        result = git.diff(repo_path, file_path, staged, commit1, commit2)
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        changes = result.get('changes', {})
        return (
            f"📊 DIFERENCIAS\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📄 Archivos cambiados: {changes.get('files_changed', 0)}\n"
            f"➕ Líneas añadidas: {changes.get('additions', 0)}\n"
            f"➖ Líneas eliminadas: {changes.get('deletions', 0)}\n\n"
            f"💡 Usa file='nombre' para ver diff de un archivo específico"
        )
    
    # ─── BRANCHES ────────────────────────────────────────────────────────
    elif action == "branches":
        if not repo_path:
            return "❌ Especifica la ruta del repositorio (repo_path='...')"
        
        result = git.list_branches(repo_path)
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        lines = ["🌿 RAMAS DEL REPOSITORIO", "━━━━━━━━━━━━━━━━━━━━━━━━━"]
        
        for branch in result.get('branches', []):
            marker = "⭐" if branch.get('current') else "  "
            remote_marker = "🌐" if branch.get('remote') else "📁"
            lines.append(f"{marker} {remote_marker} {branch['name']}")
        
        return "\n".join(lines)
    
    # ─── CREATE BRANCH ──────────────────────────────────────────────────
    elif action == "branch_create":
        if not repo_path:
            return "❌ Especifica la ruta del repositorio (repo_path='...')"
        if not branch:
            return "❌ Especifica el nombre de la rama (branch='...')"
        
        from_branch = p.get("from_branch", None)
        result = git.create_branch(repo_path, branch, from_branch)
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        return f"✅ {result['message']}"
    
    # ─── CHECKOUT ────────────────────────────────────────────────────────
    elif action == "checkout":
        if not repo_path:
            return "❌ Especifica la ruta del repositorio (repo_path='...')"
        if not branch:
            return "❌ Especifica el nombre de la rama (branch='...')"
        
        result = git.checkout(repo_path, branch)
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        return f"✅ {result['message']}"
    
    # ─── DELETE BRANCH ──────────────────────────────────────────────────
    elif action == "branch_delete":
        if not repo_path:
            return "❌ Especifica la ruta del repositorio (repo_path='...')"
        if not branch:
            return "❌ Especifica el nombre de la rama (branch='...')"
        
        result = git.delete_branch(repo_path, branch, force)
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        return f"✅ {result['message']}"
    
    # ─── MERGE ───────────────────────────────────────────────────────────
    elif action == "merge":
        if not repo_path:
            return "❌ Especifica la ruta del repositorio (repo_path='...')"
        if not branch:
            return "❌ Especifica la rama a fusionar (branch='...')"
        
        result = git.merge(repo_path, branch)
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        return f"✅ {result['message']}"
    
    # ─── STASH ──────────────────────────────────────────────────────────
    elif action == "stash":
        if not repo_path:
            return "❌ Especifica la ruta del repositorio (repo_path='...')"
        
        result = git.stash_list(repo_path)
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        if not result.get('stashes'):
            return "📭 No hay stashes guardados"
        
        lines = ["📦 STASHES", "━━━━━━━━━━━━━━━━━━━━━━━━━"]
        for stash in result.get('stashes', []):
            lines.append(f"🔷 stash@{{{stash['index']}}} - {stash['message']}")
        
        return "\n".join(lines)
    
    # ─── STASH PUSH ─────────────────────────────────────────────────────
    elif action == "stash_push":
        if not repo_path:
            return "❌ Especifica la ruta del repositorio (repo_path='...')"
        
        result = git.stash_push(repo_path, message)
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        return f"✅ {result['message']}"
    
    # ─── STASH POP ──────────────────────────────────────────────────────
    elif action == "stash_pop":
        if not repo_path:
            return "❌ Especifica la ruta del repositorio (repo_path='...')"
        
        index = int(p.get("index", 0))
        result = git.stash_pop(repo_path, index)
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        return f"✅ {result['message']}"
    
    # ─── STASH APPLY ────────────────────────────────────────────────────
    elif action == "stash_apply":
        if not repo_path:
            return "❌ Especifica la ruta del repositorio (repo_path='...')"
        
        index = int(p.get("index", 0))
        result = git.stash_apply(repo_path, index)
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        return f"✅ {result['message']}"
    
    # ─── STASH DROP ─────────────────────────────────────────────────────
    elif action == "stash_drop":
        if not repo_path:
            return "❌ Especifica la ruta del repositorio (repo_path='...')"
        
        index = int(p.get("index", 0))
        result = git.stash_drop(repo_path, index)
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        return f"✅ {result['message']}"
    
    # ─── CLONE ──────────────────────────────────────────────────────────
    elif action == "clone":
        if not url:
            return "❌ Especifica la URL del repositorio (url='...')"
        if not repo_path:
            repo_path = Path(url).stem
        
        branch = p.get("branch", None)
        result = git.clone(url, repo_path, branch)
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        return f"✅ {result['message']}"
    
    # ─── INIT ───────────────────────────────────────────────────────────
    elif action == "init":
        if not repo_path:
            return "❌ Especifica la ruta del repositorio (repo_path='...')"
        
        result = git.init(repo_path)
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        return f"✅ {result['message']}"
    
    # ─── REMOTE ─────────────────────────────────────────────────────────
    elif action == "remote":
        if not repo_path:
            return "❌ Especifica la ruta del repositorio (repo_path='...')"
        
        result = git.list_remotes(repo_path)
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        if not result.get('remotes'):
            return "📭 No hay remotos configurados"
        
        lines = ["🌐 REMOTOS", "━━━━━━━━━━━━━━━━━━━━━━━━━"]
        for remote in result.get('remotes', []):
            lines.append(f"📁 {remote['name']}: {remote['url']}")
        
        return "\n".join(lines)
    
    # ─── REMOTE ADD ─────────────────────────────────────────────────────
    elif action == "remote_add":
        if not repo_path:
            return "❌ Especifica la ruta del repositorio (repo_path='...')"
        if not remote:
            return "❌ Especifica el nombre del remoto (remote='...')"
        if not url:
            return "❌ Especifica la URL del remoto (url='...')"
        
        result = git.add_remote(repo_path, remote, url)
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        return f"✅ {result['message']}"
    
    # ─── ANALYZE ────────────────────────────────────────────────────────
    elif action == "analyze":
        if not repo_path:
            return "❌ Especifica la ruta del repositorio (repo_path='...')"
        
        result = git.analyze_repo(repo_path)
        
        lines = ["🔍 ANÁLISIS DEL REPOSITORIO", "━━━━━━━━━━━━━━━━━━━━━━━━━"]
        
        if result.get('warnings'):
            lines.append("")
            lines.append("⚠️ ADVERTENCIAS:")
            for warning in result['warnings']:
                lines.append(f"  • {warning}")
        
        if result.get('issues'):
            lines.append("")
            lines.append("❌ PROBLEMAS:")
            for issue in result['issues']:
                lines.append(f"  • {issue}")
        
        if result.get('suggestions'):
            lines.append("")
            lines.append("💡 SUGERENCIAS:")
            for suggestion in result['suggestions']:
                lines.append(f"  • {suggestion}")
        
        if not result.get('warnings') and not result.get('issues'):
            lines.append("")
            lines.append("✅ Repositorio en buen estado")
        
        return "\n".join(lines)
    
    # ─── SET DEFAULT REPO ──────────────────────────────────────────────
    elif action == "set_default":
        if not repo_path:
            return "❌ Especifica la ruta del repositorio (repo_path='...')"
        
        git.config["default_repo"] = str(Path(repo_path).resolve())
        git._save_config()
        return f"✅ Repositorio por defecto: {git.config['default_repo']}"
    
    # ─── AYUDA ──────────────────────────────────────────────────────────
    else:
        return (
            "📖 COMANDOS DE GIT\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📊 status - Estado del repositorio\n"
            "  repo_path='...'\n\n"
            "💾 commit - Hacer commit\n"
            "  repo_path='...' message='...' [add_all=True]\n\n"
            "📤 push - Subir cambios\n"
            "  repo_path='...' [remote='origin'] [branch='...'] [force=False]\n\n"
            "📥 pull - Traer cambios\n"
            "  repo_path='...' [remote='origin'] [branch='...'] [rebase=False]\n\n"
            "📜 log - Historial de commits\n"
            "  repo_path='...' [n=10] [author='...'] [since='...']\n\n"
            "📊 diff - Ver diferencias\n"
            "  repo_path='...' [file='...'] [staged=True] [commit1='...'] [commit2='...']\n\n"
            "🌿 branches - Listar ramas\n"
            "  repo_path='...'\n\n"
            "🌿 branch_create - Crear rama\n"
            "  repo_path='...' branch='...' [from_branch='...']\n\n"
            "🌿 checkout - Cambiar rama\n"
            "  repo_path='...' branch='...'\n\n"
            "🌿 branch_delete - Eliminar rama\n"
            "  repo_path='...' branch='...' [force=False]\n\n"
            "🌿 merge - Fusionar rama\n"
            "  repo_path='...' branch='...'\n\n"
            "📦 stash - Listar stashes\n"
            "  repo_path='...'\n\n"
            "📦 stash_push - Guardar en stash\n"
            "  repo_path='...' [message='...']\n\n"
            "📦 stash_pop - Aplicar y eliminar stash\n"
            "  repo_path='...' [index=0]\n\n"
            "📦 stash_apply - Aplicar stash\n"
            "  repo_path='...' [index=0]\n\n"
            "📦 stash_drop - Eliminar stash\n"
            "  repo_path='...' [index=0]\n\n"
            "📥 clone - Clonar repositorio\n"
            "  url='...' [repo_path='...'] [branch='...']\n\n"
            "📁 init - Inicializar repositorio\n"
            "  repo_path='...'\n\n"
            "🌐 remote - Listar remotos\n"
            "  repo_path='...'\n\n"
            "🌐 remote_add - Añadir remoto\n"
            "  repo_path='...' remote='...' url='...'\n\n"
            "🔍 analyze - Analizar repositorio\n"
            "  repo_path='...'\n\n"
            "📌 Ejemplos:\n"
            "  {'action':'status','repo_path':'C:/mi-proyecto'}\n"
            "  {'action':'commit','repo_path':'C:/mi-proyecto','message':'Fix: Corrección de bug'}\n"
            "  {'action':'push','repo_path':'C:/mi-proyecto'}\n"
            "  {'action':'log','repo_path':'C:/mi-proyecto','n':5}"
        )


# ─── INICIALIZACIÓN ──────────────────────────────────────────────────────
def init_git():
    """Inicializa el módulo de Git."""
    print("[Git] Inicializando...")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    # Verificar Git
    try:
        version = subprocess.run(["git", "--version"], 
                                capture_output=True, text=True, shell=True)
        print(f"[Git] ✅ {version.stdout.strip()}")
    except:
        print("[Git] ⚠️ Git no instalado")
    
    print("[Git] ✅ Listo")
    return True