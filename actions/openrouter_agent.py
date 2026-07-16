# -*- coding: utf-8 -*-
"""
openrouter_agent.py — Unified Local AI (Ollama) and Cloud API (OpenRouter) completion agent for ILUM.
"""
import json
import urllib.request
import urllib.error
import traceback
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
API_FILE = BASE_DIR / "config" / "api_keys.json"

def _load_config() -> dict:
    if not API_FILE.exists():
        return {}
    try:
        return json.loads(API_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def openrouter_agent(query: str, model: str = "google/gemini-2.5-flash", force_provider: str = None) -> str:
    """
    Routes complex queries to either OpenRouter (Cloud) or Ollama (Local AI)
    based on user settings or force_provider flag.
    """
    cfg = _load_config()
    provider = force_provider.lower().strip() if force_provider else cfg.get("active_ai_provider", "openrouter").lower().strip()

    # Load active personality dynamically
    active_pers_prompt = ""
    try:
        pers_path = BASE_DIR / "config" / "personalities.json"
        if pers_path.exists():
            pers_data = json.loads(pers_path.read_text(encoding="utf-8"))
            active_key = pers_data.get("active", "actual")
            active_pers = pers_data.get("personalities", {}).get(active_key)
            if active_pers:
                if active_key != "actual":
                    active_pers_prompt = (
                        f" [CRITICAL SYSTEM OVERRIDE: Tu personalidad activa es '{active_pers['name'].upper()}'. "
                        f"Ignora cualquier directiva anterior de actuar como un asistente neutral, seco, corto o sarcástico si contradice a esta personalidad activa. "
                        f"Debes adoptar de forma absoluta esta actitud, tono de voz y estilo en tu respuesta: {active_pers['prompt']}]"
                    )
                else:
                    active_pers_prompt = f" Adopta estrictamente esta personalidad y estilo en tu respuesta: {active_pers['prompt']}"
    except Exception:
        pass

    # 1. LOCAL OLLAMA ROUTING
    if provider == "ollama":
        ollama_url = cfg.get("ollama_url", "http://127.0.0.1:11434").strip().rstrip("/")
        if "localhost" in ollama_url:
            ollama_url = ollama_url.replace("localhost", "127.0.0.1")
        ollama_model = cfg.get("ollama_model", "gemma2:2b").strip()
        
        url = f"{ollama_url}/api/chat"
        payload = {
            "model": ollama_model,
            "messages": [
                {"role": "system", "content": f"Eres ILUM, un asistente inteligente local. Responde de forma clara, directa, muy concisa y al grano en español. Evita preámbulos y respuestas innecesariamente largas para responder a máxima velocidad.{active_pers_prompt}"},
                {"role": "user", "content": query}
            ],
            "options": {
                "temperature": 0.3,
                "num_predict": 150
            },
            "stream": False
        }
        
        try:
            req = urllib.request.Request(
                url, 
                data=json.dumps(payload).encode("utf-8"), 
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=45) as response:
                resp_data = json.loads(response.read().decode("utf-8"))
                if "message" in resp_data and "content" in resp_data["message"]:
                    return resp_data["message"]["content"]
                else:
                    return "Error: Respuesta inesperada de Ollama local."
        except urllib.error.URLError as e:
            return (
                f"Error al conectar con Ollama local ({ollama_url}): {e.reason}.\n"
                "Asegúrate de que Ollama esté ejecutándose en tu máquina (ollama serve) y de haber descargado el modelo."
            )
        except Exception as e:
            return f"Error en la llamada a Ollama local: {str(e)}"

    # 2. CLOUD ROUTING (OpenAI, Grok, Groq, OpenRouter)
    else:
        # Determine API URL, Auth Key, and Model based on provider
        if provider == "openai":
            api_key = cfg.get("openai_api_key", "").strip()
            url = "https://api.openai.com/v1/chat/completions"
            active_model = "gpt-4o-mini"
        elif provider == "grok":
            api_key = cfg.get("grok_api_key", "").strip()
            url = "https://api.x.ai/v1/chat/completions"
            active_model = "grok-beta"
        elif provider == "groq":
            api_key = cfg.get("groq_api_key", "").strip()
            url = "https://api.groq.com/openai/v1/chat/completions"
            active_model = "llama3-70b-8192"
        else: # Default openrouter
            provider = "openrouter"
            api_key = cfg.get("openrouter_api_key", "").strip()
            url = "https://openrouter.ai/api/v1/chat/completions"
            active_model = cfg.get("openrouter_model", model).strip()

        if not api_key:
            return (
                f"No se encontró una clave de {provider.upper()} en la configuración. "
                f"Por favor, añade '{provider}_api_key' en config/api_keys.json o cambia de proveedor."
            )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/ilum-beta",
            "X-Title": "ILUM AI Assistant",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": active_model,
            "max_tokens": 1500,
            "messages": [
                {"role": "system", "content": f"Eres un Agente Especialista de ILUM. Responde de forma clara, directa y muy concisa en español. Evita rodeos, preámbulos o introducciones innecesarias para optimizar el tiempo de respuesta.{active_pers_prompt}"},
                {"role": "user", "content": query}
            ]
        }

        try:
            req = urllib.request.Request(
                url, 
                data=json.dumps(payload).encode("utf-8"), 
                headers=headers, 
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=45) as response:
                response_data = json.loads(response.read().decode("utf-8"))
                if "choices" in response_data and len(response_data["choices"]) > 0:
                    return response_data["choices"][0]["message"]["content"]
                else:
                    return f"Error: Respuesta vacía o inesperada de {provider.upper()}."
        except urllib.error.HTTPError as e:
            try:
                error_info = e.read().decode("utf-8")
            except Exception:
                error_info = ""
            if e.code == 401:
                return (
                    f"Error de {provider.upper()} (HTTP 401 - No Autorizado): Tus credenciales son inválidas. "
                    "Verifica tu API Key en la configuración."
                )
            return f"Error de {provider.upper()} (HTTP {e.code}): {error_info}"
        except Exception as e:
            return f"Error al conectar con {provider.upper()}: {str(e)}"
