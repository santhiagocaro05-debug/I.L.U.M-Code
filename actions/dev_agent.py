"""
dev_agent.py — Agente autónomo de desarrollo de software
Crea proyectos completos desde cero con un solo comando
"""

import os
import subprocess
import json
import time
from pathlib import Path
from typing import Dict, List, Optional

try:
    import openrouter_agent
except ImportError:
    openrouter_agent = None

# ─── CONFIGURACIÓN ──────────────────────────────────────────────────────────
DEV_AGENT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "dev_agent.json"

def _get_config() -> Dict:
    """Carga la configuración del agente."""
    if DEV_AGENT_CONFIG.exists():
        try:
            return json.loads(DEV_AGENT_CONFIG.read_text(encoding="utf-8"))
        except:
            pass
    
    default = {
        "projects_path": str(Path.home() / "Projects" / "NEXUS_Projects"),
        "default_language": "python",
        "vscode_path": "C:\\Program Files\\Microsoft VS Code\\Code.exe",
        "auto_install": True,
        "auto_open": True
    }
    DEV_AGENT_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    DEV_AGENT_CONFIG.write_text(json.dumps(default, indent=2), encoding="utf-8")
    return default

def _save_config(config: Dict):
    """Guarda la configuración."""
    DEV_AGENT_CONFIG.write_text(json.dumps(config, indent=2), encoding="utf-8")

def _get_language_config(language: str) -> Dict:
    """Obtiene la configuración para un lenguaje específico."""
    languages = {
        "python": {
            "ext": ".py",
            "deps": "requirements.txt",
            "init": "print('Hello World')",
            "cmd": "python {filename}"
        },
        "javascript": {
            "ext": ".js",
            "deps": "package.json",
            "init": "console.log('Hello World');",
            "cmd": "node {filename}"
        },
        "typescript": {
            "ext": ".ts",
            "deps": "package.json",
            "init": "console.log('Hello World');",
            "cmd": "ts-node {filename}"
        },
        "html": {
            "ext": ".html",
            "deps": "",
            "init": '<!DOCTYPE html>\n<html>\n<head><title>Mi Proyecto</title></head>\n<body>\n  <h1>Hello World</h1>\n</body>\n</html>',
            "cmd": "start {filename}"
        },
        "cpp": {
            "ext": ".cpp",
            "deps": "CMakeLists.txt",
            "init": '#include <iostream>\n\nint main() {\n    std::cout << "Hello World" << std::endl;\n    return 0;\n}',
            "cmd": "g++ {filename} -o output && output"
        },
        "rust": {
            "ext": ".rs",
            "deps": "Cargo.toml",
            "init": 'fn main() {\n    println!("Hello World");\n}',
            "cmd": "rustc {filename} && ./{executable}"
        },
        "java": {
            "ext": ".java",
            "deps": "",
            "init": 'public class Main {\n    public static void main(String[] args) {\n        System.out.println("Hello World");\n    }\n}',
            "cmd": "javac {filename} && java Main"
        }
    }
    return languages.get(language, languages["python"])

def _generate_project_structure(project_path: Path, language: str, description: str) -> Dict:
    """
    Genera la estructura de un proyecto usando IA.
    """
    if not openrouter_agent:
        return None
    
    prompt = f"""
    Genera la estructura de archivos para un proyecto de {language} basado en esta descripción:
    
    {description}
    
    Responde con JSON que contenga:
    - files: lista de archivos con su contenido
    - dependencies: lista de dependencias necesarias
    - commands: comandos para ejecutar el proyecto
    
    Ejemplo de respuesta:
    {{
        "files": [
            {{"path": "main.py", "content": "print('Hello World')"}},
            {{"path": "README.md", "content": "# Mi Proyecto\\nDescripción"}}
        ],
        "dependencies": ["flask", "requests"],
        "commands": {{
            "install": "pip install -r requirements.txt",
            "run": "python main.py"
        }}
    }}
    """
    
    try:
        response = openrouter_agent(prompt)
        # Intentar extraer JSON de la respuesta
        import re
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            return json.loads(json_match.group())
    except:
        pass
    
    return None

# ─── FUNCIÓN PRINCIPAL ──────────────────────────────────────────────────────

def dev_agent(parameters: dict, player=None, speak=None) -> str:
    """
    Agente autónomo de desarrollo de software.
    
    Acciones:
    - create: Crea un nuevo proyecto desde cero
    - build: Construye/compila el proyecto
    - run: Ejecuta el proyecto
    - open: Abre el proyecto en VS Code
    - status: Estado del proyecto
    """
    
    action = parameters.get("action", "create").lower().strip()
    description = parameters.get("description", "")
    language = parameters.get("language", "python")
    project_name = parameters.get("project_name", "")
    
    config = _get_config()
    projects_path = Path(config.get("projects_path", ""))
    vscode_path = config.get("vscode_path", "")
    
    # ─── MAPEO DE ACCIONES ──────────────────────────────────────────────────
    
    # 1. CREAR PROYECTO
    if action == "create":
        if not description:
            return "❌ Se requiere 'description' para crear un proyecto."
        
        if not project_name:
            # Generar nombre del proyecto desde la descripción
            words = description.split()[:3]
            project_name = "_".join(words).lower().replace(" ", "_")
        
        if player: player.write_log(f"🚀 Creando proyecto '{project_name}' en {language}...")
        
        # Crear carpeta del proyecto
        project_path = projects_path / project_name
        project_path.mkdir(parents=True, exist_ok=True)
        
        # Generar estructura con IA
        structure = _generate_project_structure(project_path, language, description)
        
        if structure:
            # Crear archivos
            for file_info in structure.get("files", []):
                file_path = project_path / file_info["path"]
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(file_info["content"], encoding="utf-8")
            
            # Crear requirements.txt si hay dependencias
            deps = structure.get("dependencies", [])
            if deps:
                req_path = project_path / "requirements.txt"
                req_path.write_text("\n".join(deps), encoding="utf-8")
            
            # Guardar estructura
            (project_path / ".nexus_project.json").write_text(
                json.dumps({
                    "name": project_name,
                    "language": language,
                    "description": description,
                    "dependencies": deps,
                    "created": time.time()
                }, indent=2),
                encoding="utf-8"
            )
            
            # Abrir en VS Code
            if config.get("auto_open", True) and os.path.exists(vscode_path):
                subprocess.Popen([vscode_path, str(project_path)])
            
            # Instalar dependencias
            if config.get("auto_install", True) and deps:
                if player: player.write_log("📦 Instalando dependencias...")
                try:
                    subprocess.run(
                        ["pip", "install"] + deps,
                        cwd=str(project_path),
                        capture_output=True
                    )
                except:
                    pass
            
            result = f"""
✅ PROYECTO CREADO EXITOSAMENTE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📁 Nombre: {project_name}
📂 Ruta: {project_path}
🔤 Lenguaje: {language}
📦 Dependencias: {len(deps)}
📄 Archivos: {len(structure.get('files', []))}

🚀 Comandos:
  • run: {structure.get('commands', {}).get('run', 'N/A')}
  • install: {structure.get('commands', {}).get('install', 'N/A')}
  • open: abre en VS Code
"""
            if speak:
                speak(f"Proyecto {project_name} creado exitosamente en {language}")
            
            return result
        
        else:
            # Fallback: proyecto simple sin IA
            lang_config = _get_language_config(language)
            
            # Crear archivo principal
            main_file = project_path / f"main{lang_config['ext']}"
            main_file.write_text(lang_config["init"], encoding="utf-8")
            
            # Crear README
            readme = project_path / "README.md"
            readme.write_text(f"# {project_name}\n\n{description}\n\n## Instalación\n\n```\n{lang_config.get('cmd', '')}\n```", encoding="utf-8")
            
            return f"""
✅ PROYECTO CREADO (MODO SIMPLE):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📁 Nombre: {project_name}
📂 Ruta: {project_path}
🔤 Lenguaje: {language}
📄 Archivo principal: main{lang_config['ext']}

🚀 Ejecutar: {lang_config['cmd'].format(filename='main' + lang_config['ext'], executable=project_name)}
"""
    
    # 2. ABRIR PROYECTO
    elif action == "open":
        if not project_name:
            return "❌ Se requiere 'project_name' para abrir un proyecto."
        
        project_path = projects_path / project_name
        if not project_path.exists():
            return f"❌ Proyecto '{project_name}' no encontrado en {projects_path}"
        
        if os.path.exists(vscode_path):
            subprocess.Popen([vscode_path, str(project_path)])
            return f"✅ Proyecto '{project_name}' abierto en VS Code"
        else:
            os.startfile(str(project_path))
            return f"✅ Carpeta del proyecto '{project_name}' abierta"
    
    # 3. EJECUTAR PROYECTO
    elif action == "run":
        if not project_name:
            return "❌ Se requiere 'project_name' para ejecutar un proyecto."
        
        project_path = projects_path / project_name
        if not project_path.exists():
            return f"❌ Proyecto '{project_name}' no encontrado."
        
        # Buscar archivo principal
        main_files = list(project_path.glob("main.*")) + list(project_path.glob("index.*"))
        if not main_files:
            return f"❌ No se encontró archivo principal en {project_path}"
        
        main_file = main_files[0]
        lang_config = _get_language_config(language)
        
        cmd = lang_config.get("cmd", "").format(
            filename=main_file.name,
            executable=project_name
        )
        
        if player: player.write_log(f"▶️ Ejecutando: {cmd}")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=str(project_path),
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            output = result.stdout.strip() or result.stderr.strip() or "Sin salida"
            return f"▶️ SALIDA DEL PROYECTO '{project_name}':\n{'-' * 40}\n{output}\n{'-' * 40}"
        except subprocess.TimeoutExpired:
            return "⏱️ El proyecto tardó demasiado en ejecutarse (timeout)."
        except Exception as e:
            return f"❌ Error ejecutando proyecto: {e}"
    
    # 4. STATUS
    elif action == "status":
        projects = list(projects_path.glob("*")) if projects_path.exists() else []
        
        return f"""
📊 ESTADO DEL AGENTE DE DESARROLLO:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📁 Carpeta de proyectos: {projects_path}
📦 Proyectos existentes: {len([p for p in projects if p.is_dir()])}
🔧 VS Code: {'✅ OK' if os.path.exists(vscode_path) else '❌ No encontrado'}
📦 Dependencias: {'✅ Auto-install' if config.get('auto_install') else '❌ Manual'}

📋 Acciones disponibles:
  • create → Crear nuevo proyecto
  • open → Abrir proyecto en VS Code
  • run → Ejecutar proyecto
  • status → Estado actual

📝 Ejemplos:
  {"action": "create", "description": "API REST con Flask y SQLite", "language": "python"}
  {"action": "open", "project_name": "mi_proyecto"}
  {"action": "run", "project_name": "mi_proyecto"}
"""
    
    # 5. HELP
    else:
        return """
🎯 DEV AGENT - Agente de Desarrollo Autónomo:

📁 Creación:
  • create → Crea proyecto desde descripción
  • open → Abre proyecto en VS Code
  • run → Ejecuta proyecto
  • status → Estado del agente

📝 Ejemplos:
  {"action": "create", "description": "API REST con Flask y SQLite", "language": "python"}
  {"action": "create", "description": "Página web de portafolio", "language": "html"}
  {"action": "open", "project_name": "mi_api"}

🔤 Lenguajes soportados:
  python, javascript, typescript, html, cpp, rust, java

🔧 REQUISITOS:
  • VS Code instalado (opcional)
  • Git instalado (opcional)
  • Dependencias específicas del lenguaje
"""
