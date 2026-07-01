import os

path = r'c:\Users\Leguion T\Desktop\ILUM\ui.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

target = '''    def update_macros_list_if_open(self):
        if hasattr(self, "_active_settings_dialog") and self._active_settings_dialog:
            self._active_settings_dialog.load_macros()'''

replacement = '''    def update_macros_list_if_open(self):
        if hasattr(self, "_active_settings_dialog") and self._active_settings_dialog:
            self._active_settings_dialog.load_macros()
        if hasattr(self, "files_panel"):
            self.files_panel.load_macros()'''

if target in text:
    text = text.replace(target, replacement)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    print('SUCCESS')
else:
    print('TARGET NOT FOUND')
