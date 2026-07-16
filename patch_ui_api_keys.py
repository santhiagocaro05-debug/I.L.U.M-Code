import re

def patch_ui():
    with open('ui.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Add inputs in layout
    openrouter_block = """        layout1.addWidget(self.inp_openrouter, 1, 1, 1, 3)"""
    new_inputs = """
        # OpenAI API Key
        lbl_openai = QLabel("🟢 OpenAI API Key:")
        lbl_openai.setStyleSheet("color: rgba(255,255,255,0.8); font-weight: 600; font-size: 12px;")
        layout1.addWidget(lbl_openai, 10, 0)
        
        self.inp_openai = QLineEdit()
        self.inp_openai.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp_openai.setPlaceholderText("Ingresa tu API Key de OpenAI")
        self.inp_openai.setMinimumHeight(42)
        self.inp_openai.setStyleSheet(self.inp_openrouter.styleSheet())
        layout1.addWidget(self.inp_openai, 10, 1, 1, 3)

        # Grok API Key
        lbl_grok = QLabel("🌌 Grok API Key:")
        lbl_grok.setStyleSheet("color: rgba(255,255,255,0.8); font-weight: 600; font-size: 12px;")
        layout1.addWidget(lbl_grok, 11, 0)
        
        self.inp_grok = QLineEdit()
        self.inp_grok.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp_grok.setPlaceholderText("Ingresa tu API Key de Grok")
        self.inp_grok.setMinimumHeight(42)
        self.inp_grok.setStyleSheet(self.inp_openrouter.styleSheet())
        layout1.addWidget(self.inp_grok, 11, 1, 1, 3)

        # Groq API Key
        lbl_groq = QLabel("⚡ Groq API Key:")
        lbl_groq.setStyleSheet("color: rgba(255,255,255,0.8); font-weight: 600; font-size: 12px;")
        layout1.addWidget(lbl_groq, 12, 0)
        
        self.inp_groq = QLineEdit()
        self.inp_groq.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp_groq.setPlaceholderText("Ingresa tu API Key de Groq")
        self.inp_groq.setMinimumHeight(42)
        self.inp_groq.setStyleSheet(self.inp_openrouter.styleSheet())
        layout1.addWidget(self.inp_groq, 12, 1, 1, 3)
"""
    content = content.replace(openrouter_block, openrouter_block + new_inputs)

    # 2. Update cmb_ai_provider options
    cmb_block = """        self.cmb_ai_provider.addItem("🟢 Ollama (Local)", "ollama")"""
    new_cmb = """        self.cmb_ai_provider.addItem("🟢 Ollama (Local)", "ollama")
        self.cmb_ai_provider.addItem("🟢 ChatGPT (OpenAI)", "openai")
        self.cmb_ai_provider.addItem("🌌 Grok", "grok")
        self.cmb_ai_provider.addItem("⚡ Groq", "groq")"""
    content = content.replace(cmb_block, new_cmb)

    # 3. Load values
    load_block = """            self.inp_gemini.setText(cfg.get("gemini_api_key", ""))"""
    new_loads = """            self.inp_gemini.setText(cfg.get("gemini_api_key", ""))
            self.inp_openai.setText(cfg.get("openai_api_key", ""))
            self.inp_grok.setText(cfg.get("grok_api_key", ""))
            self.inp_groq.setText(cfg.get("groq_api_key", ""))"""
    content = content.replace(load_block, new_loads)

    # 4. Save values
    save_block = """                "gemini_api_key": self.inp_gemini.text().strip(),"""
    new_saves = """                "gemini_api_key": self.inp_gemini.text().strip(),
                "openai_api_key": self.inp_openai.text().strip(),
                "grok_api_key": self.inp_grok.text().strip(),
                "groq_api_key": self.inp_groq.text().strip(),"""
    content = content.replace(save_block, new_saves)

    with open('ui.py', 'w', encoding='utf-8') as f:
        f.write(content)
        
if __name__ == '__main__':
    patch_ui()
