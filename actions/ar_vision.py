import cv2
import numpy as np
import pyautogui
from PIL import Image, ImageDraw, ImageFont
import pytesseract
from ultralytics import YOLO
import json
from pathlib import Path
import win32gui
import win32con
import win32ui
import win32api

# 🔥 CAMBIADO: PySide6 → PyQt6
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QPointF, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QBrush, QLinearGradient, QRadialGradient

import threading
import time
from collections import deque, OrderedDict
import mss
import hashlib
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union
import asyncio
from concurrent.futures import ThreadPoolExecutor

@dataclass
class DetectionMemory:
    """Memoria de detecciones para evitar repeticiones"""
    object_hash: str
    first_seen: float
    last_seen: float
    times_seen: int
    last_announced: float
    position: Tuple[int, int, int, int]

class JarvisOverlay(QMainWindow):
    """Overlay estilo JARVIS mejorado"""
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(0, 0, win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1))
        
        self.detections = []
        self.cursor_pos = (0, 0)
        self.scan_line_y = 0
        self.animations = []
        self.hud_elements = []
        self.show_scan_effect = True
        
        # Timer para animaciones
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._update_animations)
        self.animation_timer.start(16)  # ~60 FPS para animaciones suaves
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        
        # Efecto de escaneo horizontal
        if self.show_scan_effect:
            self._draw_scan_effect(painter)
        
        # Dibujar HUD
        self._draw_hud(painter)
        
        # Dibujar detecciones con estilo JARVIS
        for det in self.detections:
            self._draw_jarvis_detection(painter, det)
        
        # Dibujar cursor mejorado
        self._draw_jarvis_cursor(painter)
    
    def _draw_scan_effect(self, painter):
        """Efecto de línea de escaneo horizontal"""
        gradient = QLinearGradient(0, self.scan_line_y - 50, 0, self.scan_line_y + 50)
        gradient.setColorAt(0, QColor(0, 255, 255, 0))
        gradient.setColorAt(0.5, QColor(0, 255, 255, 80))
        gradient.setColorAt(1, QColor(0, 255, 255, 0))
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawRect(0, self.scan_line_y - 2, self.width(), 4)
    
    def _draw_hud(self, painter):
        """Dibuja elementos HUD en las esquinas"""
        # Esquina superior izquierda
        painter.setPen(QPen(QColor(0, 255, 255, 100), 1))
        painter.drawLine(20, 20, 20, 50)
        painter.drawLine(20, 20, 50, 20)
        
        # Esquina superior derecha
        painter.drawLine(self.width() - 20, 20, self.width() - 20, 50)
        painter.drawLine(self.width() - 20, 20, self.width() - 50, 20)
        
        # Esquina inferior izquierda
        painter.drawLine(20, self.height() - 20, 20, self.height() - 50)
        painter.drawLine(20, self.height() - 20, 50, self.height() - 20)
        
        # Esquina inferior derecha
        painter.drawLine(self.width() - 20, self.height() - 20, 
                        self.width() - 20, self.height() - 50)
        painter.drawLine(self.width() - 20, self.height() - 20, 
                        self.width() - 50, self.height() - 20)
        
        # Información del sistema
        font = QFont("Consolas", 9)
        painter.setFont(font)
        painter.setPen(QColor(0, 255, 255, 150))
        
        cursor_text = f"X:{self.cursor_pos[0]} Y:{self.cursor_pos[1]}"
        painter.drawText(30, self.height() - 30, cursor_text)
        
        detections_text = f"OBJETOS: {len(self.detections)}"
        painter.drawText(self.width() - 150, self.height() - 30, detections_text)
    
    def _draw_jarvis_detection(self, painter, det):
        """Dibuja detección con estilo JARVIS futurista"""
        x1, y1, x2, y2 = det['bbox']
        conf = det['confidence']
        name = det['name']
        
        # Color basado en confianza (verde=alto, amarillo=medio, rojo=bajo)
        if conf > 0.7:
            color = QColor(0, 255, 200, 200)  # Cian brillante
        elif conf > 0.5:
            color = QColor(255, 200, 0, 200)  # Amarillo
        else:
            color = QColor(255, 50, 50, 200)  # Rojo
        
        # Rectángulo principal con esquinas redondeadas
        pen = QPen(color, 2)
        painter.setPen(pen)
        
        # Esquinas estilizadas
        corner_len = min(20, (x2-x1)//4, (y2-y1)//4)
        
        # Esquina superior izquierda
        painter.drawLine(x1, y1 + corner_len, x1, y1)
        painter.drawLine(x1, y1, x1 + corner_len, y1)
        
        # Esquina superior derecha
        painter.drawLine(x2 - corner_len, y1, x2, y1)
        painter.drawLine(x2, y1, x2, y1 + corner_len)
        
        # Esquina inferior izquierda
        painter.drawLine(x1, y2 - corner_len, x1, y2)
        painter.drawLine(x1, y2, x1 + corner_len, y2)
        
        # Esquina inferior derecha
        painter.drawLine(x2 - corner_len, y2, x2, y2)
        painter.drawLine(x2, y2 - corner_len, x2, y2)
        
        # Línea de conexión al objeto
        center_x = (x1 + x2) // 2
        painter.drawLine(center_x, y1 - 30, center_x, y1)
        
        # Etiqueta con fondo
        label = f"{name} {conf:.0%}"
        font = QFont("Consolas", 10)
        painter.setFont(font)
        
        text_width = painter.fontMetrics().horizontalAdvance(label) + 10
        text_rect_x = center_x - text_width // 2
        text_rect_y = y1 - 50
        
        # Fondo de etiqueta con gradiente
        bg_gradient = QLinearGradient(text_rect_x, text_rect_y, 
                                     text_rect_x, text_rect_y + 20)
        bg_gradient.setColorAt(0, QColor(0, 0, 0, 200))
        bg_gradient.setColorAt(1, QColor(0, 50, 50, 200))
        
        painter.fillRect(text_rect_x, text_rect_y, text_width, 20, bg_gradient)
        painter.setPen(color)
        painter.drawText(text_rect_x + 5, text_rect_y + 15, label)
        
        # Barra de confianza
        bar_width = 30
        bar_height = 3
        bar_x = x2 - bar_width - 5
        bar_y = y1 + 10
        
        painter.fillRect(bar_x, bar_y, bar_width, bar_height, 
                        QColor(0, 0, 0, 150))
        painter.fillRect(bar_x, bar_y, int(bar_width * conf), bar_height, color)
    
    def _draw_jarvis_cursor(self, painter):
        """Cursor estilo JARVIS"""
        x, y = self.cursor_pos
        
        # Círculo exterior pulsante
        painter.setPen(QPen(QColor(0, 255, 255, 100), 1))
        radius = 15 + np.sin(time.time() * 3) * 3
        painter.drawEllipse(QPointF(x, y), int(radius), int(radius))
        
        # Punto central
        painter.setPen(QPen(QColor(0, 255, 255, 200), 2))
        painter.drawPoint(int(x), int(y))
        
        # Líneas cruzadas
        line_len = 20
        painter.drawLine(x - line_len, y, x - 5, y)
        painter.drawLine(x + 5, y, x + line_len, y)
        painter.drawLine(x, y - line_len, x, y - 5)
        painter.drawLine(x, y + 5, x, y + line_len)
    
    def _update_animations(self):
        """Actualiza animaciones"""
        self.scan_line_y = (self.scan_line_y + 3) % self.height()
        self.update()

class OptimizedScreenCapture(QThread):
    """Captura de pantalla ultra-optimizada"""
    frame_ready = pyqtSignal(np.ndarray, float)  # frame + hash
    
    def __init__(self, target_fps=30):
        super().__init__()
        self.running = True
        self.sct = mss.mss()
        self.monitor = self.sct.monitors[1]
        self.target_fps = target_fps
        self.last_frame_hash = None
        self.frame_count = 0
        self.skip_frames = 0
        
    def run(self):
        frame_time = 1.0 / self.target_fps
        last_time = time.time()
        
        while self.running:
            current_time = time.time()
            elapsed = current_time - last_time
            
            if elapsed >= frame_time:
                # Capturar frame
                screenshot = self.sct.grab(self.monitor)
                frame = np.array(screenshot)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                
                # Verificar si el frame cambió significativamente
                frame_hash = hashlib.md5(frame.tobytes()).hexdigest()
                
                if frame_hash != self.last_frame_hash:
                    # Reducir resolución para procesamiento
                    frame_resized = cv2.resize(frame, (640, 480))
                    self.frame_ready.emit(frame_resized, time.time())
                    self.last_frame_hash = frame_hash
                    self.frame_count += 1
                else:
                    self.skip_frames += 1
                
                last_time = current_time
            
            # Dormir un poco para no saturar la CPU
            time.sleep(0.001)
    
    def stop(self):
        self.running = False

class IntelligentWindowDetector:
    """Detector inteligente de ventanas y aplicaciones"""
    
    # Base de datos de aplicaciones conocidas
    KNOWN_APPS = {
        'discord': {'class': ['discord'], 'title': ['discord']},
        'spotify': {'class': ['spotify'], 'title': ['spotify']},
        'steam': {'class': ['steam', 'vgui'], 'title': ['steam']},
        'vscode': {'class': ['code'], 'title': ['visual studio code']},
        'obs': {'class': ['obs'], 'title': ['obs']},
        'photoshop': {'class': ['photoshop'], 'title': ['adobe photoshop']},
        'blender': {'class': ['blender'], 'title': ['blender']},
        'premiere': {'class': ['premiere'], 'title': ['adobe premiere']},
        'after_effects': {'class': ['after effects'], 'title': ['adobe after effects']},
        'excel': {'class': ['excel', 'xlmain'], 'title': ['excel']},
        'word': {'class': ['word', 'opusapp'], 'title': ['word']},
        'powerpoint': {'class': ['powerpoint'], 'title': ['powerpoint']},
        'chrome': {'class': ['chrome'], 'title': ['chrome']},
        'firefox': {'class': ['firefox', 'mozilla'], 'title': ['firefox']},
        'edge': {'class': ['edge'], 'title': ['edge']},
        'explorer': {'class': ['explorer', 'cabinetwclass'], 'title': ['explorador']},
        'notepad': {'class': ['notepad'], 'title': ['notepad', 'bloc de notas']},
        'terminal': {'class': ['terminal', 'cmd', 'powershell'], 'title': ['terminal', 'símbolo']},
        'whatsapp': {'class': ['whatsapp'], 'title': ['whatsapp']},
        'telegram': {'class': ['telegram'], 'title': ['telegram']},
        'slack': {'class': ['slack'], 'title': ['slack']},
        'zoom': {'class': ['zoom'], 'title': ['zoom']},
        'teams': {'class': ['teams'], 'title': ['microsoft teams']},
    }
    
    @classmethod
    def detect_window(cls):
        """Detecta la ventana activa con inteligencia mejorada"""
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        
        try:
            title = win32gui.GetWindowText(hwnd).lower()
            class_name = win32gui.GetClassName(hwnd).lower()
            rect = win32gui.GetWindowRect(hwnd)
            
            # Buscar en la base de datos
            for app_name, patterns in cls.KNOWN_APPS.items():
                class_match = any(pattern in class_name for pattern in patterns['class'])
                title_match = any(pattern in title for pattern in patterns['title'])
                
                if class_match or title_match:
                    return {
                        'name': app_name,
                        'title': win32gui.GetWindowText(hwnd),
                        'class': class_name,
                        'rect': rect,
                        'type': cls._get_app_type(app_name),
                        'confidence': 0.9 if class_match and title_match else 0.7
                    }
            
            # Clasificación genérica
            return {
                'name': 'unknown',
                'title': win32gui.GetWindowText(hwnd),
                'class': class_name,
                'rect': rect,
                'type': cls._guess_type(class_name, title),
                'confidence': 0.5
            }
            
        except:
            return None
    
    @classmethod
    def _get_app_type(cls, app_name):
        """Obtiene el tipo de aplicación"""
        types = {
            'discord': 'communication',
            'spotify': 'media',
            'steam': 'gaming',
            'vscode': 'development',
            'obs': 'streaming',
            'photoshop': 'design',
            'blender': '3d_design',
            'premiere': 'video_editing',
            'after_effects': 'video_editing',
            'excel': 'productivity',
            'word': 'productivity',
            'powerpoint': 'productivity',
            'chrome': 'browser',
            'firefox': 'browser',
            'edge': 'browser',
            'explorer': 'file_manager',
            'terminal': 'terminal',
        }
        return types.get(app_name, 'application')
    
    @classmethod
    def _guess_type(cls, class_name, title):
        """Adivina el tipo de aplicación desconocida"""
        if 'editor' in title or 'edit' in class_name:
            return 'editor'
        elif 'player' in title or 'media' in class_name:
            return 'media'
        elif 'game' in title:
            return 'game'
        return 'application'

class ARVisionUltimate:
    """Visión Aumentada Definitiva con todas las optimizaciones"""
    
    def __init__(self):
        # Modelo singleton (se carga una sola vez)
        self.model = None
        self.model_loaded = False
        
        # Overlay
        self.overlay = None
        self.app = None
        
        # Captura optimizada
        self.capture_thread = None
        
        # Memoria de detecciones
        self.detection_memory = OrderedDict()
        self.memory_timeout = 30  # segundos
        
        # OCR inteligente
        self.text_cache = {}
        self.last_ocr_time = 0
        self.ocr_cooldown = 2.0  # segundos entre OCR
        self.last_ocr_hash = None
        
        # Threading optimizado
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        # Tracking
        self.cursor_history = deque(maxlen=20)
        self.window_history = deque(maxlen=5)
        
        # Estadísticas
        self.stats = {
            'frames_processed': 0,
            'detections_made': 0,
            'ocr_performed': 0,
            'windows_detected': 0
        }
        
    def load_model(self):
        """Carga el modelo YOLO una sola vez"""
        if self.model_loaded:
            return True
            
        try:
            print("🔄 Cargando modelo YOLO...")
            self.model = YOLO('yolov8n.pt')
            self.model.fuse()  # Optimizar
            self.model_loaded = True
            print("✅ Modelo YOLO cargado correctamente")
            return True
        except Exception as e:
            print(f"❌ Error cargando modelo: {e}")
            return False
    
    def _parse_region(self, region) -> Optional[List[int]]:
        """Convierte region en una lista de 4 enteros [x, y, width, height]"""
        if region is None:
            return None
            
        # Si ya es una lista/tupla de 4 elementos
        if isinstance(region, (list, tuple)) and len(region) == 4:
            try:
                return [int(x) for x in region]
            except (ValueError, TypeError):
                pass
        
        # Si es un string como "10,100,800,600"
        if isinstance(region, str):
            try:
                parts = [int(x.strip()) for x in region.split(',')]
                if len(parts) == 4:
                    return parts
                else:
                    print(f"⚠️ region debe tener 4 valores, tiene {len(parts)}")
                    return None
            except ValueError:
                print(f"⚠️ region inválida: {region} - Debe ser números separados por comas")
                return None
        
        # Si es un dict con left, top, width, height
        if isinstance(region, dict):
            try:
                return [
                    int(region.get('left', 0)),
                    int(region.get('top', 0)),
                    int(region.get('width', 100)),
                    int(region.get('height', 100))
                ]
            except (ValueError, TypeError):
                pass
        
        print(f"⚠️ region inválida: {region}")
        return None
    
    def update_detection_memory(self, detections):
        """Actualiza la memoria de detecciones para evitar repeticiones"""
        current_time = time.time()
        
        # Limpiar detecciones antiguas
        self.detection_memory = OrderedDict(
            (k, v) for k, v in self.detection_memory.items()
            if current_time - v.last_seen < self.memory_timeout
        )
        
        new_detections = []
        for det in detections:
            # Crear hash único para la detección
            det_hash = hashlib.md5(
                f"{det['name']}{det['bbox']}".encode()
            ).hexdigest()
            
            if det_hash in self.detection_memory:
                # Actualizar detección existente
                mem = self.detection_memory[det_hash]
                mem.last_seen = current_time
                mem.times_seen += 1
                
                # Solo anunciar si ha pasado suficiente tiempo
                if current_time - mem.last_announced > 10:  # 10 segundos
                    mem.last_announced = current_time
                    new_detections.append(det)
            else:
                # Nueva detección
                self.detection_memory[det_hash] = DetectionMemory(
                    object_hash=det_hash,
                    first_seen=current_time,
                    last_seen=current_time,
                    times_seen=1,
                    last_announced=current_time,
                    position=det['bbox']
                )
                new_detections.append(det)
        
        return new_detections
    
    def detect_objects_sync(self, frame):
        """Detección de objetos sincrónica optimizada"""
        if not self.model_loaded:
            return []
        
        try:
            results = self.model(frame, verbose=False)
            
            detected = []
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    if len(box.xyxy[0]) >= 4:
                        x1, y1, x2, y2 = box.xyxy[0][:4].tolist()
                        conf = float(box.conf[0])
                        cls = int(box.cls[0])
                        name = self.model.names[cls]
                        
                        # Filtrar detecciones de baja confianza
                        if conf > 0.5:
                            detected.append({
                                'name': name,
                                'confidence': conf,
                                'bbox': [int(x1), int(y1), int(x2), int(y2)]
                            })
            
            self.stats['detections_made'] += len(detected)
            return detected
            
        except Exception as e:
            print(f"Error en detección: {e}")
            return []
    
    def smart_ocr(self, frame, force=False):
        """OCR inteligente que solo procesa cuando es necesario"""
        current_time = time.time()
        
        # No hacer OCR si no ha pasado suficiente tiempo
        if not force and current_time - self.last_ocr_time < self.ocr_cooldown:
            return self.text_cache.get('last_text', '')
        
        # Verificar si la imagen cambió significativamente
        frame_hash = hashlib.md5(frame.tobytes()).hexdigest()
        if not force and frame_hash == self.last_ocr_hash:
            return self.text_cache.get('last_text', '')
        
        try:
            # Preprocesamiento optimizado
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, None, fx=0.5, fy=0.5)  # Reducir resolución
            gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
            
            # OCR con configuración optimizada
            text = pytesseract.image_to_string(
                gray, 
                lang='spa+eng', 
                config='--psm 6 -c tessedit_do_invert=0'
            )
            
            self.text_cache['last_text'] = text
            self.last_ocr_time = current_time
            self.last_ocr_hash = frame_hash
            self.stats['ocr_performed'] += 1
            
            return text
            
        except Exception as e:
            print(f"Error en OCR: {e}")
            return ""
    
    def track_cursor_intelligent(self):
        """Seguimiento inteligente del cursor"""
        cursor_pos = pyautogui.position()
        self.cursor_history.append({
            'pos': cursor_pos,
            'time': time.time()
        })
        
        if len(self.cursor_history) >= 3:
            # Calcular velocidad y dirección
            p1 = self.cursor_history[-3]['pos']
            p2 = self.cursor_history[-1]['pos']
            dt = self.cursor_history[-1]['time'] - self.cursor_history[-3]['time']
            
            if dt > 0:
                dx = p2[0] - p1[0]
                dy = p2[1] - p1[1]
                speed = np.sqrt(dx**2 + dy**2) / dt
                
                # Predecir siguiente posición
                pred_x = p2[0] + dx / 2
                pred_y = p2[1] + dy / 2
                
                return {
                    'position': cursor_pos,
                    'speed': speed,
                    'is_moving': speed > 3,
                    'predicted_position': (int(pred_x), int(pred_y)),
                    'direction': np.arctan2(dy, dx)
                }
        
        return {
            'position': cursor_pos,
            'speed': 0,
            'is_moving': False,
            'predicted_position': cursor_pos,
            'direction': 0
        }
    
    def create_jarvis_overlay(self):
        """Inicia el overlay estilo JARVIS"""
        if not self.app:
            self.app = QApplication.instance()
            if not self.app:
                self.app = QApplication([])
        
        if not self.overlay:
            self.overlay = JarvisOverlay()
            self.overlay.show()
        
        # Iniciar captura optimizada
        if not self.capture_thread:
            self.capture_thread = OptimizedScreenCapture(target_fps=30)
            self.capture_thread.frame_ready.connect(self._process_frame_smart)
            self.capture_thread.start()
    
    def _process_frame_smart(self, frame, timestamp):
        """Procesamiento inteligente de frames"""
        self.stats['frames_processed'] += 1
        
        # Detectar objetos solo si el frame cambió
        detections = self.detect_objects_sync(frame)
        
        # Filtrar detecciones repetidas
        new_detections = self.update_detection_memory(detections)
        
        # Actualizar overlay solo si hay cambios
        if new_detections or self.overlay:
            # Escalar coordenadas
            screen_w = win32api.GetSystemMetrics(0)
            screen_h = win32api.GetSystemMetrics(1)
            scale_x = screen_w / 640
            scale_y = screen_h / 480
            
            scaled_detections = []
            for det in new_detections:
                scaled_det = det.copy()
                scaled_det['bbox'] = [
                    int(det['bbox'][0] * scale_x),
                    int(det['bbox'][1] * scale_y),
                    int(det['bbox'][2] * scale_x),
                    int(det['bbox'][3] * scale_y)
                ]
                scaled_detections.append(scaled_det)
            
            # Actualizar overlay
            if self.overlay:
                self.overlay.detections = scaled_detections
                
                # Actualizar cursor
                cursor_info = self.track_cursor_intelligent()
                self.overlay.cursor_pos = cursor_info['position']
        
        # OCR solo cuando el usuario lo solicite (no automático)
        # self.smart_ocr(frame)  # Comentado para ahorrar recursos
    
    def run_ar_vision(self, parameters: dict):
        """Ejecuta visión aumentada con todas las optimizaciones"""
        action = parameters.get('action', 'identify')
        region_raw = parameters.get('region')
        
        try:
            # Cargar modelo solo la primera vez
            if not self.model_loaded:
                if not self.load_model():
                    return "❌ Error: No se pudo cargar el modelo de detección"
            
            # 🆕 PARSEAR REGION CORRECTAMENTE
            region = self._parse_region(region_raw)
            
            if action == 'identify':
                # Captura rápida
                with mss.mss() as sct:
                    screenshot = sct.grab(sct.monitors[1])
                    frame = np.array(screenshot)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                    frame = cv2.resize(frame, (640, 480))
                
                # Detectar objetos
                detections = self.detect_objects_sync(frame)
                
                # Detectar ventana
                window_info = IntelligentWindowDetector.detect_window()
                self.stats['windows_detected'] += 1
                
                # Generar descripción inteligente
                description_parts = []
                
                if window_info:
                    app_name = window_info['name'].replace('_', ' ').title()
                    description_parts.append(
                        f"🖥️ {app_name}: {window_info['title']}"
                    )
                
                if detections:
                    # Agrupar por tipo
                    objects_count = {}
                    for det in detections:
                        name = det['name']
                        objects_count[name] = objects_count.get(name, 0) + 1
                    
                    objects_desc = []
                    for name, count in objects_count.items():
                        if count > 1:
                            objects_desc.append(f"{count} {name}s")
                        else:
                            objects_desc.append(f"1 {name}")
                    
                    description_parts.append("👁️ " + ", ".join(objects_desc[:5]))
                
                # Análisis del cursor
                cursor_info = self.track_cursor_intelligent()
                if cursor_info['is_moving']:
                    description_parts.append(
                        f"🖱️ Cursor moviéndose a {cursor_info['predicted_position']}"
                    )
                
                result = " | ".join(description_parts) if description_parts else "Pantalla normal"
                
                # Añadir detalles si se solicitan
                if parameters.get('detailed', False):
                    result += "\n\n📊 **Detalles:**"
                    result += f"\n• Frames procesados: {self.stats['frames_processed']}"
                    result += f"\n• Detecciones totales: {self.stats['detections_made']}"
                    result += f"\n• Ventanas detectadas: {self.stats['windows_detected']}"
                
                return result
            
            elif action == 'read_text':
                # OCR bajo demanda con region corregida
                with mss.mss() as sct:
                    if region:
                        monitor = {
                            'left': int(region[0]),
                            'top': int(region[1]),
                            'width': int(region[2]),
                            'height': int(region[3])
                        }
                        screenshot = sct.grab(monitor)
                    else:
                        screenshot = sct.grab(sct.monitors[1])
                    
                    frame = np.array(screenshot)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                
                text = self.smart_ocr(frame, force=True)
                
                if text.strip():
                    return f"📝 **Texto detectado:**\n{text.strip()}"
                return "📝 No se detectó texto significativo"
            
            elif action == 'scan_qr':
                # Detección de QR
                with mss.mss() as sct:
                    screenshot = sct.grab(sct.monitors[1])
                    frame = np.array(screenshot)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                
                detector = cv2.QRCodeDetector()
                data, bbox, _ = detector.detectAndDecode(frame)
                
                if data:
                    return f"📱 **QR Detectado:**\n{data}"
                return "❌ No se encontraron códigos QR"
            
            elif action == 'jarvis_overlay':
                # Iniciar overlay JARVIS
                self.create_jarvis_overlay()
                return "🖥️ **Overlay JARVIS activado**\nPresiona Ctrl+Shift+Q para cerrar"
            
            elif action == 'analyze_window':
                # Análisis detallado de ventana
                window_info = IntelligentWindowDetector.detect_window()
                
                if window_info:
                    result = f"🔍 **Análisis de ventana:**\n"
                    result += f"• Aplicación: {window_info['name'].title()}\n"
                    result += f"• Título: {window_info['title']}\n"
                    result += f"• Tipo: {window_info['type']}\n"
                    result += f"• Confianza: {window_info['confidence']:.1%}\n"
                    result += f"• Posición: {window_info['rect']}"
                    return result
                return "❌ No se pudo analizar la ventana activa"
            
            elif action == 'stats':
                # Mostrar estadísticas
                return f"""📊 **Estadísticas de Visión AR:**
• Frames procesados: {self.stats['frames_processed']}
• Detecciones realizadas: {self.stats['detections_made']}
• OCR realizados: {self.stats['ocr_performed']}
• Ventanas analizadas: {self.stats['windows_detected']}
• Objetos en memoria: {len(self.detection_memory)}
• Uso de CPU: {self.executor._threads if hasattr(self.executor, '_threads') else 'N/A'}"""
            
            else:
                return f"❌ Acción desconocida: {action}. Usa: identify, read_text, scan_qr, jarvis_overlay, analyze_window, stats"
        
        except Exception as e:
            return f"❌ Error en ar_vision: {str(e)}"

# Singleton global para mantener el estado
_ar_vision_instance = None

def ar_vision(parameters: dict, player=None):
    """
    Visión Aumentada JARVIS Definitiva
    
    Args:
        parameters: {
            'action': 'identify' | 'read_text' | 'scan_qr' | 'jarvis_overlay' | 'analyze_window' | 'stats',
            'region': 'x,y,width,height' (opcional, string) | [x,y,width,height] (opcional, lista),
            'detailed': True/False (opcional, para más detalles)
        }
    """
    global _ar_vision_instance
    
    # Mantener una sola instancia para conservar el estado
    if _ar_vision_instance is None:
        _ar_vision_instance = ARVisionUltimate()
    
    return _ar_vision_instance.run_ar_vision(parameters)

# Ejemplo de uso
if __name__ == "__main__":
    print("🚀 Iniciando AR Vision Ultimate...")
    
    # Identificar pantalla
    result = ar_vision({'action': 'identify', 'detailed': True})
    print(result)
    
    # Analizar ventana específica
    result = ar_vision({'action': 'analyze_window'})
    print(result)
    
    # Ver estadísticas
    result = ar_vision({'action': 'stats'})
    print(result)