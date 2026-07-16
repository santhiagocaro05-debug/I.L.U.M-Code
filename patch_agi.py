import re

def patch():
    with open('main.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Add conversational state tracking and AGI daemon to NexusLive.__init__
    init_marker = "self.respond_only_by_name = bool(cfg_keys.get(\"respond_only_by_name\", False))"
    init_injection = """self.respond_only_by_name = bool(cfg_keys.get("respond_only_by_name", False))
        self.conversation_hot_until = 0.0
        self.vision_buffer = []  # To hold the last few screenshots for permanent vision
        
        # Iniciar Daemon AGI Proactivo
        import threading
        self._agi_daemon = threading.Thread(target=self._run_agi_daemon, daemon=True)
        self._agi_daemon.start()"""
    
    if "self._agi_daemon" not in content:
        content = content.replace(init_marker, init_injection)

    # 2. Modify the wake word check to allow hot conversation
    # We already modified this via patch_main_wake.py, let's look for our previous patch
    old_wake_check = """            if getattr(self, "respond_only_by_name", False):
                if not self._is_name_activation(text):
                    return"""
    new_wake_check = """            import time
            is_hot = time.time() < getattr(self, "conversation_hot_until", 0)
            if getattr(self, "respond_only_by_name", False) and not is_hot:
                if not self._is_name_activation(text):
                    return"""
    
    # Actually, the previous patch in main.py looks exactly like:
    #         if getattr(self, "respond_only_by_name", False):
    #             if not self._is_name_activation(text):
    #                 return
    # I will replace it using regex to ensure it hits both spots
    
    content = re.sub(
        r'if getattr\(self, "respond_only_by_name", False\):\s*if not self\._is_name_activation\(text\):\s*return',
        r'import time\n            is_hot = time.time() < getattr(self, "conversation_hot_until", 0)\n            if getattr(self, "respond_only_by_name", False) and not is_hot:\n                if not self._is_name_activation(text):\n                    return',
        content
    )
    
    # 3. Update set_speaking to renew hot conversation state
    set_speaking_marker = """    def set_speaking(self, value: bool):
        with self._speaking_lock:
            self._is_speaking = value"""
    set_speaking_new = """    def set_speaking(self, value: bool):
        with self._speaking_lock:
            self._is_speaking = value
            if not value:
                import time
                self.conversation_hot_until = time.time() + 12.0  # 12 seconds hot timeout"""
    
    if "self.conversation_hot_until =" not in content.split("def set_speaking")[1][:200]:
        content = content.replace(set_speaking_marker, set_speaking_new)
        
    # 4. Add the AGI Daemon method to NexusLive
    # Find the end of NexusLive methods, e.g., right before `def run(self):` or at the end of the class.
    # We will insert it before `async def run(self):`
    
    daemon_code = """
    def _run_agi_daemon(self):
        import time
        import psutil
        from PIL import ImageGrab
        import io
        import os
        from pathlib import Path
        
        tick = 0
        while True:
            time.sleep(10)
            if not self._loop or not self.session:
                continue
            if getattr(self, "is_sleeping", False):
                continue
                
            tick += 1
            
            # 1. Visión Permanente (cada 20s = 2 ticks)
            if tick % 2 == 0:
                try:
                    # Capturar pantalla en baja resolución para buffer
                    screenshot = ImageGrab.grab()
                    screenshot.thumbnail((800, 600)) # Low res to save RAM
                    buf = io.BytesIO()
                    screenshot.save(buf, format="JPEG", quality=60)
                    self.vision_buffer.append(buf.getvalue())
                    if len(self.vision_buffer) > 3:
                        self.vision_buffer.pop(0)
                except:
                    pass
            
            # 2. Modo Proactivo: Batería y CPU (cada 60s = 6 ticks)
            if tick % 6 == 0:
                try:
                    battery = psutil.sensors_battery()
                    if battery and not battery.power_plugged and battery.percent < 20:
                        if getattr(self, "_last_battery_warn", 100) > battery.percent:
                            self.speak(f"Aviso de sistema: La batería está al {int(battery.percent)}%. Te sugiero conectarla.")
                            self._last_battery_warn = battery.percent
                            
                    cpu_usage = psutil.cpu_percent(interval=None)
                    if cpu_usage > 95:
                        if time.time() - getattr(self, "_last_cpu_warn", 0) > 300: # only warn every 5 mins
                            self.speak("El uso del procesador está al máximo. Recomiendo cerrar algunos programas.")
                            self._last_cpu_warn = time.time()
                except:
                    pass
                    
            # 3. Organización Automática de Archivos (cada 10 mins = 60 ticks)
            if tick % 60 == 0:
                try:
                    target_dir = Path.home() / "Downloads"
                    if target_dir.exists():
                        unorganized_files = [f for f in target_dir.iterdir() if f.is_file() and not f.name.startswith('.')]
                        if len(unorganized_files) > 20:
                            if time.time() - getattr(self, "_last_org_warn", 0) > 3600: # Only ask once an hour
                                self.speak(f"He detectado {len(unorganized_files)} archivos sin organizar en tu carpeta de Descargas. ¿Deseas que los clasifique automáticamente?")
                                self._last_org_warn = time.time()
                except:
                    pass

"""
    if "def _run_agi_daemon(self):" not in content:
        content = content.replace("    async def run(self):", daemon_code + "    async def run(self):")
        
    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    patch()
