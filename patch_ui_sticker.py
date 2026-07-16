def patch_sticker():
    with open('ui.py', 'r', encoding='utf-8') as f:
        content = f.read()

    old_class = """class DraggableSticker(QLabel):
    \"\"\"Sticker que se puede arrastrar a cualquier posición.\"\"\"
    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_pos = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            new_pos = self.pos() + event.position().toPoint() - self._drag_pos
            # Clamp dentro del parent
            parent = self.parentWidget()
            if parent:
                max_x = parent.width() - self.width()
                max_y = parent.height() - self.height()
                new_pos.setX(max(0, min(new_pos.x(), max_x)))
                new_pos.setY(max(0, min(new_pos.y(), max_y)))
            self.move(new_pos)
        super().mouseMoveEvent(event)"""

    new_class = """class DraggableSticker(QLabel):
    \"\"\"Sticker que se puede arrastrar a cualquier posición.\"\"\"
    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_pos = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self._drag_pos
            # Clamp dentro del parent
            parent = self.parentWidget()
            if parent:
                max_x = parent.width() - self.width()
                max_y = parent.height() - self.height()
                new_pos.setX(max(0, min(new_pos.x(), max_x)))
                new_pos.setY(max(0, min(new_pos.y(), max_y)))
            self.move(new_pos)
        super().mouseMoveEvent(event)"""

    content = content.replace(old_class, new_class)

    with open('ui.py', 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    patch_sticker()
