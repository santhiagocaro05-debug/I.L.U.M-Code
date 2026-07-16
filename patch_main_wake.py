import re

def patch_main():
    with open('main.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # Block 1 (around line 3854)
    old_block_1 = """        if getattr(self, "respond_only_by_name", False) and not self._is_name_activation(text):
            return"""
    new_block_1 = """        if getattr(self, "respond_only_by_name", False):
            if not self._is_name_activation(text):
                return
            # Verificar que haya una instrucción además del nombre
            text_lower = str(text).lower().strip()
            # Remover palabras comunes de activación
            for w in ["nexus", "nex", getattr(self, "ai_name", "").lower().strip()]:
                if w and len(w) > 1:
                    text_lower = re.sub(rf"\\b{re.escape(w)}\\b", "", text_lower).strip()
            if not text_lower or len(text_lower) < 2:
                # Solo dijo el nombre sin pedir nada, ignorar
                return"""

    # Block 2 (around line 5104)
    old_block_2 = """            if getattr(self, "respond_only_by_name", False) and not getattr(self, "is_sleeping", False):
                if not self._is_name_activation(text):
                    return"""
    new_block_2 = """            if getattr(self, "respond_only_by_name", False) and not getattr(self, "is_sleeping", False):
                if not self._is_name_activation(text):
                    return
                # Verificar que haya una instrucción además del nombre
                t_lower = str(text).lower().strip()
                for w in ["nexus", "nex", getattr(self, "ai_name", "").lower().strip()]:
                    if w and len(w) > 1:
                        t_lower = re.sub(rf"\\b{re.escape(w)}\\b", "", t_lower).strip()
                if not t_lower or len(t_lower) < 2:
                    return"""

    content = content.replace(old_block_1, new_block_1)
    content = content.replace(old_block_2, new_block_2)

    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    patch_main()
