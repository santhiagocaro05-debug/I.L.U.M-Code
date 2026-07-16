import re

with open('ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. We will comment out the old API keys being added to layout1
# and replace them with a dynamic label and input.
# We'll just replace the whole chunk from "# Gemini API Key" to "# Modelo OpenRouter"

pattern_ui = r"(?s)(# Gemini API Key.*?)(?=# Modelo OpenRouter)"

new_ui = '''# Dynamic API Key Input
        self.lbl_dynamic_api = QLabel("?? API Key:")
        self.lbl_dynamic_api.setStyleSheet("color: rgba(255,255,255,0.8); font-weight: 600; font-size: 12px;")
        layout1.addWidget(self.lbl_dynamic_api, 3, 2)
        
        self.inp_dynamic_api = QLineEdit()
        self.inp_dynamic_api.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp_dynamic_api.setPlaceholderText("Ingresa tu API Key")
        self.inp_dynamic_api.setMinimumHeight(42)
        self.inp_dynamic_api.setStyleSheet("""
            QLineEdit {
                background: rgba(0,0,0,0.3);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                padding: 10px 16px;
                color: rgba(255,255,255,0.9);
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: rgba(245, 158, 11, 0.3);
            }
        """)
        layout1.addWidget(self.inp_dynamic_api, 3, 3)

        # Internal dict to store keys
        self._internal_api_keys = {}

        def _on_provider_changed():
            provider = self.cmb_ai_provider.currentData()
            # save current text to previous provider
            if hasattr(self, "_last_provider"):
                self._internal_api_keys[self._last_provider] = self.inp_dynamic_api.text().strip()
            # load new provider text
            self.inp_dynamic_api.setText(self._internal_api_keys.get(provider, ""))
            self.lbl_dynamic_api.setText(f"?? API Key ({provider.capitalize()}):")
            self._last_provider = provider

        self.cmb_ai_provider.currentIndexChanged.connect(_on_provider_changed)

        '''

if re.search(pattern_ui, content):
    content = re.sub(pattern_ui, new_ui, content, count=1)
    print("UI chunk replaced!")
else:
    print("UI chunk not found!")

# 2. Update load settings
# In ui.py:
#             self.inp_gemini.setText(cfg.get("gemini_api_key", ""))
#             self.inp_openai.setText(cfg.get("openai_api_key", ""))

pattern_load = r"(?s)(self\.inp_gemini\.setText\(cfg\.get\(\"gemini_api_key\", \"\"\)\).*?self\.inp_openrouter_model\.setText\(cfg\.get\(\"openrouter_model\", \"google/gemini-2\.5-flash\"\)\))"

new_load = '''self._internal_api_keys["gemini"] = cfg.get("gemini_api_key", "")
            self._internal_api_keys["openai"] = cfg.get("openai_api_key", "")
            self._internal_api_keys["grok"] = cfg.get("grok_api_key", "")
            self._internal_api_keys["groq"] = cfg.get("groq_api_key", "")
            self._internal_api_keys["openrouter"] = cfg.get("openrouter_api_key", "")
            self._internal_api_keys["ollama"] = cfg.get("ollama_api_key", "http://localhost:11434")
            self.inp_openrouter_model.setText(cfg.get("openrouter_model", "google/gemini-2.5-flash"))
            
            # Select provider
            active_provider = cfg.get("active_ai_provider", "gemini")
            idx = self.cmb_ai_provider.findData(active_provider)
            if idx >= 0:
                self.cmb_ai_provider.setCurrentIndex(idx)
            self._last_provider = active_provider
            self.inp_dynamic_api.setText(self._internal_api_keys.get(active_provider, ""))
            self.lbl_dynamic_api.setText(f"?? API Key ({active_provider.capitalize()}):")'''

if re.search(pattern_load, content):
    content = re.sub(pattern_load, new_load, content, count=1)
    print("Load settings replaced!")
else:
    print("Load settings not found!")

# 3. Update save settings
# In ui.py:
#                 "gemini_api_key": self.inp_gemini.text().strip(),

pattern_save = r"(?s)(\"gemini_api_key\": self\.inp_gemini\.text\(\)\.strip\(\).*?\"openrouter_model\": self\.inp_openrouter_model\.text\(\)\.strip\(\),)"

new_save = '''"gemini_api_key": self._internal_api_keys.get("gemini", "").strip(),
                "openai_api_key": self._internal_api_keys.get("openai", "").strip(),
                "grok_api_key": self._internal_api_keys.get("grok", "").strip(),
                "groq_api_key": self._internal_api_keys.get("groq", "").strip(),
                "openrouter_api_key": self._internal_api_keys.get("openrouter", "").strip(),
                "ollama_api_key": self._internal_api_keys.get("ollama", "").strip(),
                "active_ai_provider": self.cmb_ai_provider.currentData(),
                "openrouter_model": self.inp_openrouter_model.text().strip(),'''

# Ensure we save the currently typing key before saving
save_hook_pattern = r"cfg\.update\(\{"
new_save_hook = '''# Save currently typing key to dict
            provider = self.cmb_ai_provider.currentData()
            self._internal_api_keys[provider] = self.inp_dynamic_api.text().strip()
            cfg.update({'''

if re.search(pattern_save, content):
    content = re.sub(pattern_save, new_save, content, count=1)
    content = re.sub(save_hook_pattern, new_save_hook, content, count=1)
    print("Save settings replaced!")
else:
    print("Save settings not found!")

with open("ui.py", "w", encoding="utf-8") as f:
    f.write(content)

