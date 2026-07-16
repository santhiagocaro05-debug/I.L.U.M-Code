import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update the startup dialog check in equire_api_key_or_exit()
pattern_startup = r"ai_provider = cfg\.get\(\"ai_provider\", \"gemini\"\)\.strip\(\)\s*# If Ollama is the active provider.*?\s*if ai_provider == \"ollama\" or gemini or openrouter:"
new_startup = '''ai_provider = cfg.get("active_ai_provider", "gemini").strip()
        
        # If not gemini or we have gemini key, safe to start
        if ai_provider != "gemini" or gemini:'''

if re.search(pattern_startup, content, re.DOTALL):
    content = re.sub(pattern_startup, new_startup, content, count=1, flags=re.DOTALL)
    print("Startup check patched!")
else:
    print("Startup check not found!")

# 2. Update the main un() method where it decides to use Gemini or alternative provider
pattern_run = r"api_provider = cfg\.get\(\"ai_provider\", \"gemini\"\)\.lower\(\)\.strip\(\)\n\s*except Exception:\n\s*pass\n\s*if api_provider in \[\"ollama\", \"openrouter\"\]:"
new_run = '''api_provider = cfg.get("active_ai_provider", "gemini").lower().strip()
        except Exception:
            pass

        if api_provider != "gemini":'''

if re.search(pattern_run, content):
    content = re.sub(pattern_run, new_run, content, count=1)
    print("Run loop check patched!")
else:
    print("Run loop check not found!")

# 3. Update the openrouter_agent call inside _offline_run() to pass the correct provider
pattern_agent = r"openrouter_agent\(text, force_provider=\"ollama\"\)"
new_agent = r"openrouter_agent(text, force_provider=api_provider)"
# Wait, pi_provider isn't defined inside _offline_run(), I need to read it there too.
pattern_offline = r"async def _offline_run\(self, check_internet: bool = False\):\s*\"\"\"Bucle de supervivencia.*?\"\"\""
new_offline = '''async def _offline_run(self, check_internet: bool = False):
        """Bucle de supervivencia offline o proveedor alternativo (Ollama/OpenRouter)."""
        import json
        from pathlib import Path
        api_cfg_path = Path(__file__).resolve().parent / "config" / "api_keys.json"
        api_provider = "ollama"
        if api_cfg_path.exists():
            try:
                api_provider = json.loads(api_cfg_path.read_text(encoding="utf-8")).get("active_ai_provider", "ollama")
            except: pass
'''
if re.search(pattern_offline, content):
    content = re.sub(pattern_offline, new_offline, content, count=1)
    content = re.sub(pattern_agent, new_agent, content)
    print("_offline_run patched!")
else:
    print("_offline_run not found!")

with open("main.py", "w", encoding="utf-8") as f:
    f.write(content)
