import subprocess
import json
import re
import threading
import time
import os
import socket
from pathlib import Path
import psutil
import requests

try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
        QListWidget, QListWidgetItem, QFrame, QGraphicsDropShadowEffect
    )
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QSize, QRectF, QPointF
    from PyQt6.QtGui import QColor, QPainter, QPainterPath, QLinearGradient, QPen
    HAS_QT = True
except ImportError:
    HAS_QT = False

try:
    import qtawesome as qta
    HAS_QTA = True
except ImportError:
    HAS_QTA = False


class NetworkManager:
    def __init__(self):
        self.wifi_networks = []
        self.current_connection = None
        self.devices = []
        self._iface_cache = None

    # ── Interfaz WiFi real (ya no hardcodeada) ──────────────────────────
    def _get_wifi_interface_name(self):
        if self._iface_cache:
            return self._iface_cache
        try:
            result = subprocess.run(
                ['netsh', 'wlan', 'show', 'interfaces'],
                capture_output=True, text=True, encoding='utf-8', errors='ignore'
            )
            for line in result.stdout.split('\n'):
                l = line.strip()
                if l.lower().startswith('name') and ':' in l:
                    name = l.split(':', 1)[1].strip()
                    if name:
                        self._iface_cache = name
                        return name
        except Exception:
            pass
        self._iface_cache = "Wi-Fi"
        return "Wi-Fi"

    def list_wifi_networks(self):
        """Lista redes WiFi disponibles (solo nombres, compatibilidad hacia atrás)."""
        try:
            result = subprocess.run(
                ['netsh', 'wlan', 'show', 'networks'],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore'
            )

            networks = []
            for line in result.stdout.split('\n'):
                if 'SSID' in line and ':' in line and 'BSSID' not in line:
                    ssid = line.split(':', 1)[1].strip()
                    if ssid:
                        networks.append(ssid)

            self.wifi_networks = networks
            return networks

        except Exception as e:
            return f"Error listando redes: {e}"

    def list_wifi_networks_detailed(self):
        """Lista redes WiFi con señal y si están protegidas o abiertas (para el panel)."""
        try:
            result = subprocess.run(
                ['netsh', 'wlan', 'show', 'networks', 'mode=bssid'],
                capture_output=True, text=True, encoding='utf-8', errors='ignore'
            )

            entries = []
            current = None
            for raw_line in result.stdout.split('\n'):
                line = raw_line.strip()
                if line.startswith('SSID') and 'BSSID' not in line and ':' in line:
                    if current and current.get('ssid'):
                        entries.append(current)
                    ssid = line.split(':', 1)[1].strip()
                    current = {"ssid": ssid, "signal": None, "secured": True, "auth": ""}
                elif line.lower().startswith('authentication') and current is not None:
                    auth = line.split(':', 1)[1].strip()
                    current['auth'] = auth
                    current['secured'] = auth.lower() not in ('open', 'abierta', 'abierto')
                elif line.lower().startswith('signal') and current is not None:
                    if current.get('signal') is None:
                        current['signal'] = line.split(':', 1)[1].strip()
            if current and current.get('ssid'):
                entries.append(current)

            # Deduplicar por SSID (puede haber varios BSSID de la misma red);
            # nos quedamos con la de mejor señal.
            best = {}
            for n in entries:
                ssid = n.get('ssid')
                if not ssid:
                    continue
                sig_txt = (n.get('signal') or '').replace('%', '').strip()
                sig_val = int(sig_txt) if sig_txt.isdigit() else -1
                if ssid not in best or sig_val > best[ssid][0]:
                    best[ssid] = (sig_val, n)

            result_list = [v[1] for v in best.values()]
            result_list.sort(
                key=lambda x: -(int(x['signal'].replace('%', '')) if x.get('signal') and x['signal'].replace('%', '').strip().isdigit() else 0)
            )
            return result_list

        except Exception as e:
            return f"Error listando redes: {e}"

    def get_current_connection(self):
        """Devuelve el estado real de la interfaz WiFi (conectado, SSID, señal)."""
        try:
            result = subprocess.run(
                ['netsh', 'wlan', 'show', 'interfaces'],
                capture_output=True, text=True, encoding='utf-8', errors='ignore'
            )
            info = {"connected": False, "ssid": None, "signal": None, "state": None}
            for raw_line in result.stdout.split('\n'):
                line = raw_line.strip()
                low = line.lower()
                if low.startswith('state') and ':' in line:
                    info["state"] = line.split(':', 1)[1].strip()
                    info["connected"] = "conectad" in info["state"].lower() or "connected" in info["state"].lower()
                elif low.startswith('ssid') and 'bssid' not in low and ':' in line:
                    info["ssid"] = line.split(':', 1)[1].strip()
                elif low.startswith('signal') and ':' in line:
                    info["signal"] = line.split(':', 1)[1].strip()
            return info
        except Exception as e:
            return {"connected": False, "ssid": None, "signal": None, "state": f"error: {e}"}

    def connect_wifi(self, ssid, password=None, timeout=10):
        """Conecta a una red WiFi y VERIFICA que la conexión realmente se haya establecido."""
        if not ssid:
            return {"success": False, "message": "SSID no proporcionado"}

        iface = self._get_wifi_interface_name()

        try:
            # Borrar perfil previo (evita conflictos con una contraseña vieja guardada)
            subprocess.run(
                ['netsh', 'wlan', 'delete', 'profile', f'name={ssid}', f'interface={iface}'],
                capture_output=True, text=True
            )

            if password:
                profile_xml = (
                    '<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">\n'
                    f'    <name>{ssid}</name>\n'
                    '    <SSIDConfig>\n'
                    '        <SSID>\n'
                    f'            <name>{ssid}</name>\n'
                    '        </SSID>\n'
                    '    </SSIDConfig>\n'
                    '    <connectionType>ESS</connectionType>\n'
                    '    <connectionMode>auto</connectionMode>\n'
                    '    <MSM>\n'
                    '        <security>\n'
                    '            <authEncryption>\n'
                    '                <authentication>WPA2PSK</authentication>\n'
                    '                <encryption>AES</encryption>\n'
                    '                <useOneX>false</useOneX>\n'
                    '            </authEncryption>\n'
                    '            <sharedKey>\n'
                    '                <keyType>passPhrase</keyType>\n'
                    '                <protected>false</protected>\n'
                    f'                <keyMaterial>{password}</keyMaterial>\n'
                    '            </sharedKey>\n'
                    '        </security>\n'
                    '    </MSM>\n'
                    '</WLANProfile>'
                )
            else:
                profile_xml = (
                    '<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">\n'
                    f'    <name>{ssid}</name>\n'
                    '    <SSIDConfig>\n'
                    '        <SSID>\n'
                    f'            <name>{ssid}</name>\n'
                    '        </SSID>\n'
                    '    </SSIDConfig>\n'
                    '    <connectionType>ESS</connectionType>\n'
                    '    <connectionMode>auto</connectionMode>\n'
                    '    <MSM>\n'
                    '        <security>\n'
                    '            <authEncryption>\n'
                    '                <authentication>open</authentication>\n'
                    '                <encryption>none</encryption>\n'
                    '                <useOneX>false</useOneX>\n'
                    '            </authEncryption>\n'
                    '        </security>\n'
                    '    </MSM>\n'
                    '</WLANProfile>'
                )

            safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', ssid)
            profile_file = Path(f"temp_{safe_name}.xml")
            profile_file.write_text(profile_xml, encoding='utf-8')

            subprocess.run(
                ['netsh', 'wlan', 'add', 'profile', f'filename={profile_file}', f'interface={iface}'],
                capture_output=True, text=True
            )
            subprocess.run(
                ['netsh', 'wlan', 'connect', f'name={ssid}', f'ssid={ssid}', f'interface={iface}'],
                capture_output=True, text=True
            )

            try:
                profile_file.unlink()
            except Exception:
                pass

            # Verificación real: Windows responde "ok" al instante aunque la
            # autenticación falle después, así que esperamos y comprobamos.
            start = time.time()
            while time.time() - start < timeout:
                time.sleep(1)
                status = self.get_current_connection()
                if status.get('connected') and status.get('ssid') == ssid:
                    self.current_connection = ssid
                    return {"success": True, "message": f"Conectado a {ssid}"}

            return {
                "success": False,
                "message": f"No se pudo confirmar la conexión a '{ssid}'. Verifica la contraseña o conéctate desde la configuración de Windows."
            }

        except Exception as e:
            return {"success": False, "message": f"Error conectando a {ssid}: {e}"}

    def disconnect_wifi(self):
        """Desconecta de la red WiFi actual"""
        try:
            subprocess.run(['netsh', 'wlan', 'disconnect'], capture_output=True)
            self.current_connection = None
            return "Desconectado de WiFi"
        except Exception as e:
            return f"Error desconectando: {e}"

    def open_wifi_settings(self):
        """Abre el panel nativo de configuración de WiFi de Windows (fallback manual)."""
        try:
            os.startfile("ms-settings:network-wifi")
            return "Abriendo configuración de WiFi de Windows…"
        except Exception:
            try:
                subprocess.run(['cmd', '/c', 'start', '', 'ms-settings:network-wifi'], shell=False)
                return "Abriendo configuración de WiFi de Windows…"
            except Exception as e2:
                return f"No se pudo abrir la configuración de Windows: {e2}"

    def scan_devices(self):
        """Escanea dispositivos en la red local (compatibilidad hacia atrás)."""
        try:
            result = subprocess.run(
                ['arp', '-a'],
                capture_output=True,
                text=True,
                encoding='cp850',
                errors='ignore'
            )

            devices = []
            for line in result.stdout.split('\n'):
                if 'Internet' in line or 'Estática' in line or 'Dynamic' in line or 'Dinámic' in line:
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        ip = parts[0]
                        mac = parts[1]
                        if '--' not in mac and re.match(r'^\d{1,3}(\.\d{1,3}){3}$', ip):
                            devices.append({
                                'ip': ip,
                                'mac': mac,
                                'status': 'active'
                            })

            self.devices = devices
            return devices

        except Exception as e:
            return f"Error escaneando dispositivos: {e}"

    def resolve_hostname(self, ip, timeout=0.6):
        """Intenta resolver el nombre de host de una IP, sin bloquear demasiado."""
        old_timeout = socket.getdefaulttimeout()
        try:
            socket.setdefaulttimeout(timeout)
            return socket.gethostbyaddr(ip)[0]
        except Exception:
            return ""
        finally:
            socket.setdefaulttimeout(old_timeout)

    def scan_devices_detailed(self, resolve_names=True, max_resolve=25):
        """Igual que scan_devices pero intenta agregar el nombre de host (para el panel)."""
        devices = self.scan_devices()
        if isinstance(devices, str):
            return devices
        if resolve_names:
            for d in devices[:max_resolve]:
                d['host'] = self.resolve_hostname(d['ip'])
        return devices

    def speed_test(self):
        """Realiza prueba de velocidad de internet"""
        try:
            import speedtest
            st = speedtest.Speedtest()
            st.get_best_server()

            download = st.download() / 1_000_000  # Mbps
            upload = st.upload() / 1_000_000
            ping = st.results.ping

            return {
                'download': f"{download:.2f} Mbps",
                'upload': f"{upload:.2f} Mbps",
                'ping': f"{ping} ms"
            }

        except ImportError:
            return "Instala speedtest-cli: pip install speedtest-cli"
        except Exception as e:
            return f"Error en speed test: {e}"

    def get_ip(self):
        """Obtiene la IP local del equipo"""
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            return {
                'hostname': hostname,
                'ip': ip,
                'public_ip': self.get_public_ip()
            }
        except Exception as e:
            return f"Error obteniendo IP: {e}"

    def get_public_ip(self):
        """Obtiene la IP pública"""
        try:
            response = requests.get('https://api.ipify.org?format=json', timeout=5)
            return response.json().get('ip', 'Desconocida')
        except Exception:
            return 'No disponible'

    def set_dns(self, dns1='8.8.8.8', dns2='8.8.4.4'):
        """Cambia los servidores DNS"""
        try:
            iface = self._get_wifi_interface_name()
            subprocess.run([
                'netsh', 'interface', 'ipv4', 'set', 'dns',
                f'name={iface}', 'source=static', f'address={dns1}',
                'register=primary', 'validate=no'
            ], capture_output=True)
            subprocess.run([
                'netsh', 'interface', 'ipv4', 'add', 'dns',
                f'name={iface}', f'address={dns2}', 'index=2'
            ], capture_output=True)
            return f"DNS cambiado a {dns1} y {dns2}"
        except Exception as e:
            return f"Error cambiando DNS: {e}"

    def flush_dns(self):
        """Limpia la caché DNS"""
        try:
            subprocess.run(['ipconfig', '/flushdns'], capture_output=True)
            return "Caché DNS limpiada"
        except Exception as e:
            return f"Error limpiando DNS: {e}"


# ═══════════════════════════════════════════════════════════════════════════
#  PANEL "LIQUID GLASS" — WiFi + Dispositivos
# ═══════════════════════════════════════════════════════════════════════════

if HAS_QT:

    class WifiScanWorker(QThread):
        finished_signal = pyqtSignal(list, dict, str)  # (redes, conexion_actual, error)

        def __init__(self, nm: NetworkManager):
            super().__init__()
            self.nm = nm

        def run(self):
            try:
                networks = self.nm.list_wifi_networks_detailed()
                if isinstance(networks, str):
                    self.finished_signal.emit([], {}, networks)
                    return
                current = self.nm.get_current_connection()
                self.finished_signal.emit(networks, current, "")
            except Exception as e:
                self.finished_signal.emit([], {}, str(e))

    class WifiConnectWorker(QThread):
        finished_signal = pyqtSignal(dict)

        def __init__(self, nm: NetworkManager, ssid, password):
            super().__init__()
            self.nm = nm
            self.ssid = ssid
            self.password = password

        def run(self):
            result = self.nm.connect_wifi(self.ssid, self.password)
            self.finished_signal.emit(result)

    class DeviceScanWorker(QThread):
        finished_signal = pyqtSignal(list, str)

        def __init__(self, nm: NetworkManager):
            super().__init__()
            self.nm = nm

        def run(self):
            try:
                devices = self.nm.scan_devices_detailed()
                if isinstance(devices, str):
                    self.finished_signal.emit([], devices)
                    return
                self.finished_signal.emit(devices, "")
            except Exception as e:
                self.finished_signal.emit([], str(e))

    class NetworkPanelWidget(QWidget):
        """Panel flotante liquid glass: WiFi disponibles + dispositivos conectados."""

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setObjectName("NetworkPanelWidget")
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setFixedSize(430, 620)
            self._radius = 24
            self._drag_offset = None
            self.nm = NetworkManager()
            self._selected_ssid = None
            self._selected_secured = True

            self.setStyleSheet("""
                QLabel { background: transparent; border: none; color: rgba(255,255,255,0.85); }
                QPushButton {
                    background: rgba(255,255,255,0.05);
                    color: rgba(255,255,255,0.78);
                    border: 1px solid rgba(255,255,255,0.09);
                    border-radius: 11px;
                    font-weight: 700;
                    font-size: 11px;
                    padding: 8px 12px;
                }
                QPushButton:hover {
                    background: rgba(34, 211, 238, 0.10);
                    color: rgba(255,255,255,0.95);
                    border-color: rgba(34, 211, 238, 0.30);
                }
                QPushButton:disabled {
                    color: rgba(255,255,255,0.30);
                }
                QPushButton#btn_connect {
                    background: rgba(16, 220, 140, 0.12);
                    border-color: rgba(16, 220, 140, 0.30);
                    color: rgba(60, 240, 170, 0.95);
                }
                QPushButton#btn_connect:hover {
                    background: rgba(16, 220, 140, 0.22);
                    border-color: rgba(16, 220, 140, 0.5);
                }
                QPushButton#btn_settings {
                    background: rgba(251, 191, 36, 0.10);
                    border-color: rgba(251, 191, 36, 0.28);
                    color: rgba(251, 191, 36, 0.95);
                }
                QPushButton#btn_settings:hover {
                    background: rgba(251, 191, 36, 0.20);
                    border-color: rgba(251, 191, 36, 0.45);
                }
                QPushButton#btn_close {
                    background: rgba(255, 69, 58, 0.08);
                    color: rgba(255, 110, 100, 0.55);
                    border: 1px solid rgba(255, 69, 58, 0.16);
                    border-radius: 15px;
                    font-size: 12px;
                }
                QPushButton#btn_close:hover {
                    background: rgba(255, 69, 58, 0.18);
                    color: rgba(255, 110, 100, 0.95);
                    border-color: rgba(255, 69, 58, 0.35);
                }
                QLineEdit {
                    background: rgba(0,0,0,0.32);
                    border: 1px solid rgba(255,255,255,0.10);
                    border-radius: 10px;
                    padding: 8px 12px;
                    color: rgba(255,255,255,0.9);
                    font-size: 12px;
                }
                QLineEdit:focus { border-color: rgba(34, 211, 238, 0.4); }
                QListWidget {
                    background: rgba(0,0,0,0.28);
                    border: 1px solid rgba(255,255,255,0.07);
                    border-radius: 12px;
                    color: rgba(255,255,255,0.85);
                    padding: 4px;
                    font-size: 12px;
                }
                QListWidget::item { padding: 8px 8px; border-radius: 8px; }
                QListWidget::item:selected {
                    background: rgba(34, 211, 238, 0.16);
                    border: 1px solid rgba(34, 211, 238, 0.30);
                }
                QListWidget::item:hover { background: rgba(255,255,255,0.05); }
                QScrollBar:vertical {
                    border: none; background: rgba(255,255,255,0.02); width: 4px; border-radius: 2px;
                }
                QScrollBar::handle:vertical {
                    background: rgba(255,255,255,0.12); min-height: 24px; border-radius: 2px;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            """)

            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(45)
            shadow.setColor(QColor(0, 0, 0, 190))
            shadow.setOffset(0, 12)
            self.setGraphicsEffect(shadow)

            root = QVBoxLayout(self)
            root.setContentsMargins(22, 18, 22, 18)
            root.setSpacing(12)

            # ── Header ──────────────────────────────────────────────
            header = QHBoxLayout()
            header.setSpacing(10)
            lbl_icon = QLabel()
            if HAS_QTA:
                lbl_icon.setPixmap(qta.icon('fa5s.wifi', color='#22d3ee').pixmap(20, 20))
            header.addWidget(lbl_icon)
            title = QLabel("RED Y DISPOSITIVOS")
            title.setStyleSheet("font-size:14px;font-weight:800;letter-spacing:2px;color:rgba(255,255,255,0.92);")
            header.addWidget(title)
            header.addStretch()
            btn_close = QPushButton()
            btn_close.setObjectName("btn_close")
            btn_close.setFixedSize(28, 28)
            if HAS_QTA:
                btn_close.setIcon(qta.icon('fa5s.times', color='#ff6e64'))
            else:
                btn_close.setText("x")
            btn_close.clicked.connect(self.hide)
            header.addWidget(btn_close)
            root.addLayout(header)

            # ── Conexión actual ─────────────────────────────────────
            self.lbl_current = QLabel("Consultando conexión actual…")
            self.lbl_current.setWordWrap(True)
            self.lbl_current.setStyleSheet("font-size:11px;font-weight:700;color:rgba(255,255,255,0.55);")
            root.addWidget(self.lbl_current)

            # ── Sección WiFi ─────────────────────────────────────────
            wifi_hdr = QHBoxLayout()
            lbl_wifi = QLabel("REDES WIFI DISPONIBLES")
            lbl_wifi.setStyleSheet("font-size:11px;font-weight:700;letter-spacing:1px;color:rgba(255,255,255,0.5);")
            wifi_hdr.addWidget(lbl_wifi)
            wifi_hdr.addStretch()
            self.btn_scan_wifi = QPushButton("  ESCANEAR")
            if HAS_QTA:
                self.btn_scan_wifi.setIcon(qta.icon('fa5s.search', color='#22d3ee'))
            self.btn_scan_wifi.clicked.connect(self.scan_wifi)
            wifi_hdr.addWidget(self.btn_scan_wifi)
            root.addLayout(wifi_hdr)

            self.list_wifi = QListWidget()
            self.list_wifi.setFixedHeight(150)
            self.list_wifi.itemClicked.connect(self._on_wifi_item_clicked)
            root.addWidget(self.list_wifi)

            # ── Fila de conexión inline (oculta hasta seleccionar red) ──
            self.connect_row = QFrame()
            self.connect_row.setStyleSheet("""
                QFrame {
                    background: rgba(255,255,255,0.025);
                    border: 1px solid rgba(34, 211, 238, 0.12);
                    border-radius: 12px;
                }
            """)
            cr_layout = QVBoxLayout(self.connect_row)
            cr_layout.setContentsMargins(12, 10, 12, 10)
            cr_layout.setSpacing(8)

            self.lbl_selected_ssid = QLabel("Selecciona una red")
            self.lbl_selected_ssid.setStyleSheet("font-size:12px;font-weight:700;color:rgba(34,211,238,0.9);")
            cr_layout.addWidget(self.lbl_selected_ssid)

            pw_row = QHBoxLayout()
            pw_row.setSpacing(6)
            self.inp_password = QLineEdit()
            self.inp_password.setPlaceholderText("Contraseña de la red")
            self.inp_password.setEchoMode(QLineEdit.EchoMode.Password)
            self.inp_password.returnPressed.connect(self.connect_selected_wifi)
            pw_row.addWidget(self.inp_password, 1)

            self.btn_toggle_pw = QPushButton()
            self.btn_toggle_pw.setFixedSize(36, 36)
            if HAS_QTA:
                self.btn_toggle_pw.setIcon(qta.icon('fa5s.eye', color='rgba(255,255,255,0.6)'))
            else:
                self.btn_toggle_pw.setText("👁")
            self.btn_toggle_pw.clicked.connect(self._toggle_password_visibility)
            pw_row.addWidget(self.btn_toggle_pw)
            cr_layout.addLayout(pw_row)

            btn_row = QHBoxLayout()
            btn_row.setSpacing(8)
            self.btn_connect = QPushButton("  CONECTAR")
            self.btn_connect.setObjectName("btn_connect")
            if HAS_QTA:
                self.btn_connect.setIcon(qta.icon('fa5s.plug', color='rgba(60,240,170,0.95)'))
            self.btn_connect.clicked.connect(self.connect_selected_wifi)
            btn_row.addWidget(self.btn_connect)

            self.btn_open_settings = QPushButton("  ABRIR CONFIG. DE WINDOWS")
            self.btn_open_settings.setObjectName("btn_settings")
            if HAS_QTA:
                self.btn_open_settings.setIcon(qta.icon('fa5s.cog', color='#fbbf24'))
            self.btn_open_settings.clicked.connect(self.open_windows_wifi_settings)
            btn_row.addWidget(self.btn_open_settings)
            cr_layout.addLayout(btn_row)

            self.connect_row.hide()
            root.addWidget(self.connect_row)

            # ── Sección Dispositivos ─────────────────────────────────
            dev_hdr = QHBoxLayout()
            lbl_dev = QLabel("DISPOSITIVOS EN LA RED")
            lbl_dev.setStyleSheet("font-size:11px;font-weight:700;letter-spacing:1px;color:rgba(255,255,255,0.5);")
            dev_hdr.addWidget(lbl_dev)
            dev_hdr.addStretch()
            self.btn_scan_devices = QPushButton("  ACTUALIZAR")
            if HAS_QTA:
                self.btn_scan_devices.setIcon(qta.icon('fa5s.sync-alt', color='#c9a8f7'))
            self.btn_scan_devices.clicked.connect(self.scan_devices)
            dev_hdr.addWidget(self.btn_scan_devices)
            root.addLayout(dev_hdr)

            self.list_devices = QListWidget()
            self.list_devices.setMinimumHeight(120)
            root.addWidget(self.list_devices, 1)

            # ── Estado ────────────────────────────────────────────────
            self.lbl_status = QLabel("Listo.")
            self.lbl_status.setWordWrap(True)
            self.lbl_status.setStyleSheet("font-size:10px;color:rgba(255,255,255,0.4);")
            root.addWidget(self.lbl_status)

            self.hide()
            self._load_position()

        # ── Utilidades de estado ────────────────────────────────────
        def _set_status(self, text, kind="info"):
            colors = {
                "info": "rgba(255,255,255,0.45)",
                "success": "rgba(60, 240, 170, 0.85)",
                "warning": "rgba(251, 191, 36, 0.85)",
                "error": "rgba(255, 110, 100, 0.85)",
            }
            self.lbl_status.setStyleSheet(f"font-size:10px;font-weight:700;color:{colors.get(kind, colors['info'])};")
            self.lbl_status.setText(text)

        def refresh_all(self):
            self.scan_wifi()
            self.scan_devices()

        # ── WiFi: escaneo ────────────────────────────────────────────
        def scan_wifi(self):
            self.btn_scan_wifi.setEnabled(False)
            self._set_status("Escaneando redes WiFi…")
            self._wifi_worker = WifiScanWorker(self.nm)
            self._wifi_worker.finished_signal.connect(self._on_wifi_scanned)
            self._wifi_worker.start()

        @pyqtSlot(list, dict, str)
        def _on_wifi_scanned(self, networks, current, error):
            self.btn_scan_wifi.setEnabled(True)
            if error:
                self._set_status(f"Error escaneando: {error}", "error")
                return

            if current.get("connected") and current.get("ssid"):
                signal = current.get("signal") or "?"
                self.lbl_current.setText(f"Conectado a: {current['ssid']}  ·  Señal: {signal}")
                self.lbl_current.setStyleSheet("font-size:11px;font-weight:700;color:rgba(60,240,170,0.9);")
            else:
                self.lbl_current.setText("No hay conexión WiFi activa")
                self.lbl_current.setStyleSheet("font-size:11px;font-weight:700;color:rgba(255,110,100,0.75);")

            self.list_wifi.clear()
            if not networks:
                self.list_wifi.addItem("No se encontraron redes.")
                self._set_status("Sin redes encontradas.", "warning")
                return

            for n in networks:
                ssid = n.get("ssid", "?")
                secured = n.get("secured", True)
                signal = n.get("signal", "")
                lock = "🔒" if secured else "📶"
                is_current = current.get("ssid") == ssid and current.get("connected")
                mark = " ✓" if is_current else ""
                item = QListWidgetItem(f"{lock}  {ssid}   {signal}{mark}")
                item.setData(Qt.ItemDataRole.UserRole, {"ssid": ssid, "secured": secured})
                self.list_wifi.addItem(item)

            self._set_status(f"{len(networks)} redes encontradas.", "success")

        def _on_wifi_item_clicked(self, item):
            data = item.data(Qt.ItemDataRole.UserRole)
            if not data:
                return
            self._selected_ssid = data["ssid"]
            self._selected_secured = data["secured"]
            self.lbl_selected_ssid.setText(f"Red seleccionada: {self._selected_ssid}")
            self.inp_password.setVisible(self._selected_secured)
            self.btn_toggle_pw.setVisible(self._selected_secured)
            self.inp_password.clear()
            self.connect_row.show()
            if self._selected_secured:
                self.inp_password.setFocus()

        def _toggle_password_visibility(self):
            if self.inp_password.echoMode() == QLineEdit.EchoMode.Password:
                self.inp_password.setEchoMode(QLineEdit.EchoMode.Normal)
                if HAS_QTA:
                    self.btn_toggle_pw.setIcon(qta.icon('fa5s.eye-slash', color='rgba(255,255,255,0.6)'))
            else:
                self.inp_password.setEchoMode(QLineEdit.EchoMode.Password)
                if HAS_QTA:
                    self.btn_toggle_pw.setIcon(qta.icon('fa5s.eye', color='rgba(255,255,255,0.6)'))

        # ── WiFi: conexión ───────────────────────────────────────────
        def connect_selected_wifi(self):
            if not self._selected_ssid:
                self._set_status("Selecciona una red primero.", "warning")
                return
            password = self.inp_password.text() if self._selected_secured else None
            if self._selected_secured and not password:
                self._set_status("Escribe la contraseña de la red.", "warning")
                return

            self.btn_connect.setEnabled(False)
            self._set_status(f"Conectando a {self._selected_ssid}…")
            self._connect_worker = WifiConnectWorker(self.nm, self._selected_ssid, password)
            self._connect_worker.finished_signal.connect(self._on_connect_finished)
            self._connect_worker.start()

        @pyqtSlot(dict)
        def _on_connect_finished(self, result):
            self.btn_connect.setEnabled(True)
            if result.get("success"):
                self._set_status(result.get("message", "Conectado."), "success")
                self.connect_row.hide()
                self.scan_wifi()
                self.scan_devices()
            else:
                self._set_status(result.get("message", "No se pudo conectar."), "error")
                # Fallback automático: si no se pudo confirmar la conexión,
                # abrimos la configuración nativa de Windows para que el
                # usuario la complete manualmente (ej. portal cautivo, 2FA, etc.)
                self.open_windows_wifi_settings()

        def open_windows_wifi_settings(self):
            msg = self.nm.open_wifi_settings()
            self._set_status(msg, "info")

        # ── Dispositivos ─────────────────────────────────────────────
        def scan_devices(self):
            self.btn_scan_devices.setEnabled(False)
            self._set_status("Buscando dispositivos en la red…")
            self._device_worker = DeviceScanWorker(self.nm)
            self._device_worker.finished_signal.connect(self._on_devices_scanned)
            self._device_worker.start()

        @pyqtSlot(list, str)
        def _on_devices_scanned(self, devices, error):
            self.btn_scan_devices.setEnabled(True)
            if error:
                self._set_status(f"Error: {error}", "error")
                return
            self.list_devices.clear()
            if not devices:
                self.list_devices.addItem("No se encontraron dispositivos.")
                return
            for d in devices:
                host = d.get("host") or ""
                label = f"{d['ip']}   ·   {d['mac']}"
                if host:
                    label += f"   ·   {host}"
                self.list_devices.addItem(label)
            self._set_status(f"{len(devices)} dispositivos encontrados.", "success")

        # ── Posición / arrastre ──────────────────────────────────────
        def _load_position(self):
            try:
                from memory.config_manager import load_api_keys
                cfg = load_api_keys()
                x = cfg.get("widget_pos_NetworkPanelWidget_x")
                y = cfg.get("widget_pos_NetworkPanelWidget_y")
                if x is not None and y is not None:
                    self.move(int(x), int(y))
            except Exception:
                pass

        def _save_position(self):
            try:
                from memory.config_manager import load_api_keys, save_api_keys
                cfg = load_api_keys()
                cfg["widget_pos_NetworkPanelWidget_x"] = self.x()
                cfg["widget_pos_NetworkPanelWidget_y"] = self.y()
                save_api_keys(cfg)
            except Exception:
                pass

        def mousePressEvent(self, event):
            if event.button() == Qt.MouseButton.LeftButton:
                self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()

        def mouseMoveEvent(self, event):
            if event.buttons() & Qt.MouseButton.LeftButton and self._drag_offset is not None:
                self.move(event.globalPosition().toPoint() - self._drag_offset)
                event.accept()

        def mouseReleaseEvent(self, event):
            if self._drag_offset is not None:
                self._save_position()
                self._drag_offset = None
            super().mouseReleaseEvent(event)

        # ── Fondo "liquid glass" (mismo estilo que el resto de NEXUS) ──
        def paintEvent(self, event):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            rect = QRectF(self.rect()).adjusted(0.75, 0.75, -0.75, -0.75)
            path = QPainterPath()
            path.addRoundedRect(rect, self._radius, self._radius)

            base_gradient = QLinearGradient(0, 0, 0, self.height())
            base_gradient.setColorAt(0.0, QColor(255, 255, 255, 30))
            base_gradient.setColorAt(0.5, QColor(200, 210, 230, 18))
            base_gradient.setColorAt(1.0, QColor(160, 170, 200, 26))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(base_gradient)
            painter.drawPath(path)

            painter.setBrush(QColor(18, 18, 24, 210))
            painter.drawPath(path)

            painter.setBrush(QColor(255, 255, 255, 8))
            painter.drawPath(path)

            bottom_gradient = QLinearGradient(0, self.height() * 0.6, 0, self.height())
            bottom_gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
            bottom_gradient.setColorAt(1.0, QColor(0, 0, 0, 40))
            painter.setBrush(bottom_gradient)
            painter.drawPath(path)

            painter.setPen(QPen(QColor(255, 255, 255, 70), 1.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

            shine_rect = QRectF(
                rect.left() + self._radius * 0.6, rect.top() + 2,
                rect.width() - self._radius * 1.2, self._radius * 0.6
            )
            shine_path = QPainterPath()
            shine_path.addRoundedRect(shine_rect, shine_rect.height() / 2, shine_rect.height() / 2)
            shine_gradient = QLinearGradient(0, shine_rect.top(), 0, shine_rect.bottom())
            shine_gradient.setColorAt(0.0, QColor(255, 255, 255, 35))
            shine_gradient.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(shine_gradient)
            painter.drawPath(shine_path)

            super().paintEvent(event)


    _panel_ref = {"widget": None}

    def _widget_is_alive(widget):
        try:
            widget.isVisible()
            return True
        except RuntimeError:
            return False

    def show_network_panel(parent=None):
        """Crea (si hace falta) y muestra el panel de red.
        `parent` debe ser el central_widget de la ventana principal de NEXUS."""
        widget = _panel_ref.get("widget")
        if widget is None or not _widget_is_alive(widget):
            widget = NetworkPanelWidget(parent)
            _panel_ref["widget"] = widget

        if parent is not None:
            try:
                w, h = parent.width(), parent.height()
                widget.move(max(0, (w - widget.width()) // 2), max(0, (h - widget.height()) // 2))
            except Exception:
                pass

        widget.show()
        widget.raise_()
        widget.refresh_all()
        return "Panel de red abierto."

else:
    def show_network_panel(parent=None):
        return "PyQt6 no está disponible en este entorno; no se puede abrir el panel."


# ═══════════════════════════════════════════════════════════════════════════
#  Función de herramienta (tool) — igual que antes + acción nueva open_panel
# ═══════════════════════════════════════════════════════════════════════════

def network_manager(parameters: dict, player=None):
    """
    Gestor de redes para NEXUS

    Args:
        parameters: {
            'action': 'list_wifi' | 'connect' | 'disconnect' | 'scan_devices' |
                      'speed_test' | 'get_ip' | 'set_dns' | 'flush_dns' |
                      'open_panel' | 'open_wifi_settings',
            'ssid': (opcional) SSID de la red,
            'password': (opcional) contraseña de la red,
            'dns1': (opcional) primer DNS,
            'dns2': (opcional) segundo DNS
        }
        player: objeto UI de NEXUS (self.ui en main.py). Se usa para anclar
                el panel visual a la ventana principal cuando action=open_panel.
    """
    action = parameters.get('action', 'list_wifi')
    ssid = parameters.get('ssid')
    password = parameters.get('password')
    dns1 = parameters.get('dns1', '8.8.8.8')
    dns2 = parameters.get('dns2', '8.8.4.4')

    # Singleton
    if not hasattr(network_manager, 'instance'):
        network_manager.instance = NetworkManager()

    nm = network_manager.instance

    if action == 'list_wifi':
        networks = nm.list_wifi_networks()
        if isinstance(networks, str):
            return networks

        result = "📶 REDES WIFI DISPONIBLES:\n"
        for i, network in enumerate(networks[:20], 1):
            result += f"  {i}. {network}\n"
        return result

    elif action == 'connect':
        if not ssid:
            return "❌ Proporciona el SSID de la red"
        res = nm.connect_wifi(ssid, password)
        if isinstance(res, dict):
            return res.get("message", "")
        return res

    elif action == 'disconnect':
        return nm.disconnect_wifi()

    elif action == 'open_wifi_settings':
        return nm.open_wifi_settings()

    elif action == 'open_panel':
        parent_widget = None
        try:
            parent_widget = player._win.central_widget
        except Exception:
            parent_widget = None
        return show_network_panel(parent_widget)

    elif action == 'scan_devices':
        devices = nm.scan_devices()
        if isinstance(devices, str):
            return devices

        result = "🌐 DISPOSITIVOS EN LA RED:\n"
        for device in devices[:20]:
            result += f"  • {device['ip']} - {device['mac']}\n"
        return result

    elif action == 'speed_test':
        result = nm.speed_test()
        if isinstance(result, str):
            return result

        return f"📊 PRUEBA DE VELOCIDAD:\nDescarga: {result['download']}\nSubida: {result['upload']}\nPing: {result['ping']}"

    elif action == 'get_ip':
        result = nm.get_ip()
        if isinstance(result, str):
            return result

        return f"🖥️ INFORMACIÓN DE RED:\nHostname: {result['hostname']}\nIP Local: {result['ip']}\nIP Pública: {result['public_ip']}"

    elif action == 'set_dns':
        return nm.set_dns(dns1, dns2)

    elif action == 'flush_dns':
        return nm.flush_dns()

    else:
        return "❌ Acción no reconocida. Usa: list_wifi, connect, disconnect, scan_devices, speed_test, get_ip, set_dns, flush_dns, open_panel, open_wifi_settings"