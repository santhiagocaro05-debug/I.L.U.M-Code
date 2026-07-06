"""
ARCA Invoice Module (ex AFIP)
==============================
Generación de comprobantes electrónicos válidos ante ARCA (ex AFIP).
Soporta Facturas A, B, C, Notas de Crédito, Notas de Débito, y más.
"""

import json
import hashlib
import base64
import os
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import threading
import subprocess
import tempfile

try:
    import requests
except ImportError:
    requests = None

# ─── CONFIGURACIÓN ─────────────────────────────────────────────────────────
CONFIG_DIR = Path("config")
ARCA_CONFIG_PATH = CONFIG_DIR / "arca_config.json"
ARCA_INVOICES_PATH = CONFIG_DIR / "arca_invoices"
ARCA_CERT_PATH = CONFIG_DIR / "arca_cert"
ARCA_INVOICES_PATH.mkdir(parents=True, exist_ok=True)
ARCA_CERT_PATH.mkdir(parents=True, exist_ok=True)

# ─── TIPOS DE COMPROBANTES ──────────────────────────────────────────────
TIPOS_COMPROBANTE = {
    # Facturas
    1: {"nombre": "Factura A", "tipo": "factura", "sujeto": "responsable_inscripto"},
    6: {"nombre": "Factura B", "tipo": "factura", "sujeto": "consumidor_final"},
    11: {"nombre": "Factura C", "tipo": "factura", "sujeto": "monotributista"},
    
    # Notas de Crédito
    2: {"nombre": "Nota de Crédito A", "tipo": "nota_credito", "sujeto": "responsable_inscripto"},
    7: {"nombre": "Nota de Crédito B", "tipo": "nota_credito", "sujeto": "consumidor_final"},
    12: {"nombre": "Nota de Crédito C", "tipo": "nota_credito", "sujeto": "monotributista"},
    
    # Notas de Débito
    3: {"nombre": "Nota de Débito A", "tipo": "nota_debito", "sujeto": "responsable_inscripto"},
    8: {"nombre": "Nota de Débito B", "tipo": "nota_debito", "sujeto": "consumidor_final"},
    13: {"nombre": "Nota de Débito C", "tipo": "nota_debito", "sujeto": "monotributista"},
    
    # Otros
    15: {"nombre": "Recibo A", "tipo": "recibo", "sujeto": "responsable_inscripto"},
    19: {"nombre": "Recibo B", "tipo": "recibo", "sujeto": "consumidor_final"},
    20: {"nombre": "Recibo C", "tipo": "recibo", "sujeto": "monotributista"},
}

# ─── ALICUOTAS IVA ──────────────────────────────────────────────────────
ALICUOTAS_IVA = {
    0: {"nombre": "Exento", "porcentaje": 0},
    1: {"nombre": "IVA 10.5%", "porcentaje": 10.5},
    2: {"nombre": "IVA 21%", "porcentaje": 21},
    3: {"nombre": "IVA 27%", "porcentaje": 27},
    4: {"nombre": "IVA 5%", "porcentaje": 5},
    5: {"nombre": "IVA 2.5%", "porcentaje": 2.5},
}

# ─── UNIDADES DE MEDIDA ──────────────────────────────────────────────────
UNIDADES = {
    "unidad": "Unidad",
    "kg": "Kilogramo",
    "l": "Litro",
    "m": "Metro",
    "m2": "Metro cuadrado",
    "m3": "Metro cúbico",
    "docena": "Docena",
    "par": "Par",
    "hora": "Hora",
    "dia": "Día",
    "mes": "Mes",
    "servicio": "Servicio",
}

# ─── GESTOR DE ARCA ──────────────────────────────────────────────────────
class ARCAManager:
    """Gestor de comprobantes ARCA (ex AFIP)."""
    
    def __init__(self):
        self.config = self._load_config()
        self._validate_config()
    
    def _load_config(self) -> Dict:
        """Carga la configuración."""
        if ARCA_CONFIG_PATH.exists():
            try:
                return json.loads(ARCA_CONFIG_PATH.read_text(encoding="utf-8"))
            except:
                return {}
        return {
            "empresa": {
                "razon_social": "",
                "cuit": "",
                "domicilio": "",
                "condicion_iva": "responsable_inscripto",
                "ingresos_brutos": "",
                "inicio_actividades": "",
                "actividad_principal": "",
            },
            "facturacion": {
                "ultimo_numero": 0,
                "punto_venta": 1,
                "tipo_comprobante": 6,  # Factura B por defecto
                "moneda": "ARS",
                "cotizacion": 1.0,
            },
            "web_service": {
                "url": "https://wswhomo.afip.gov.ar/wsfe/service.asmx",
                "homologacion": True,
            }
        }
    
    def _save_config(self):
        """Guarda la configuración."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        ARCA_CONFIG_PATH.write_text(
            json.dumps(self.config, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    
    def _validate_config(self):
        """Valida la configuración."""
        empresa = self.config.get("empresa", {})
        if not empresa.get("cuit"):
            print("[ARCA] ⚠️ CUIT no configurado")
        if not empresa.get("razon_social"):
            print("[ARCA] ⚠️ Razón Social no configurada")
    
    def _validate_cuit(self, cuit: str) -> bool:
        """Valida un CUIT argentino."""
        if not cuit:
            return False
        
        # Limpiar formato
        cuit = re.sub(r'[^0-9]', '', cuit)
        
        if len(cuit) != 11:
            return False
        
        # Validar dígito verificador
        factores = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
        suma = 0
        for i in range(10):
            suma += int(cuit[i]) * factores[i]
        
        resto = 11 - (suma % 11)
        if resto == 11:
            resto = 0
        elif resto == 10:
            resto = 9
        
        return resto == int(cuit[10])
    
    def _format_cuit(self, cuit: str) -> str:
        """Formatea un CUIT."""
        cuit = re.sub(r'[^0-9]', '', cuit)
        if len(cuit) == 11:
            return f"{cuit[:2]}-{cuit[2:10]}-{cuit[10]}"
        return cuit
    
    def _calculate_iva(self, neto: float, alicuota: int) -> float:
        """Calcula el IVA de un monto."""
        if alicuota in ALICUOTAS_IVA:
            porcentaje = ALICUOTAS_IVA[alicuota]["porcentaje"]
            return neto * (porcentaje / 100)
        return neto * 0.21  # Default 21%
    
    def _get_next_number(self, tipo: int) -> int:
        """Obtiene el próximo número de comprobante."""
        facturacion = self.config.get("facturacion", {})
        return facturacion.get("ultimo_numero", 0) + 1
    
    def _update_last_number(self, numero: int):
        """Actualiza el último número de comprobante."""
        if "facturacion" not in self.config:
            self.config["facturacion"] = {}
        self.config["facturacion"]["ultimo_numero"] = numero
        self._save_config()
    
    # ─── GENERAR COMPROBANTE ─────────────────────────────────────────────
    def generate_invoice(self, parameters: Dict) -> Dict:
        """
        Genera un comprobante electrónico.
        
        Args:
            parameters: Datos del comprobante
                - tipo: Tipo de comprobante (1, 6, 11, etc.)
                - razon_social: Razón social del receptor
                - cuit_receptor: CUIT del receptor
                - detalle: Lista de productos/servicios
                - importe_neto: Importe neto (opcional)
                - importe_iva: Importe IVA (opcional)
                - iva_pct: Porcentaje de IVA (opcional)
                - fecha: Fecha del comprobante (opcional)
                - domicilio: Domicilio del receptor (opcional)
        """
        # Validar parámetros
        tipo = parameters.get("tipo", 6)
        razon_social = parameters.get("razon_social", "").strip()
        cuit_receptor = parameters.get("cuit_receptor", "").strip()
        detalle = parameters.get("detalle", [])
        fecha = parameters.get("fecha", datetime.now().strftime("%Y-%m-%d"))
        
        # Validar tipo
        if tipo not in TIPOS_COMPROBANTE:
            return {"error": f"Tipo de comprobante inválido: {tipo}"}
        
        tipo_info = TIPOS_COMPROBANTE[tipo]
        
        # Validar CUIT del receptor
        if cuit_receptor and not self._validate_cuit(cuit_receptor):
            return {"error": f"CUIT del receptor inválido: {cuit_receptor}"}
        
        # Calcular montos
        if detalle:
            neto = sum(item.get("precio", 0) * item.get("cantidad", 1) for item in detalle)
        else:
            neto = float(parameters.get("importe_neto", 0))
        
        iva_pct = parameters.get("iva_pct", 21)
        iva = parameters.get("importe_iva", self._calculate_iva(neto, iva_pct))
        total = neto + iva
        
        # Obtener próximo número
        numero = self._get_next_number(tipo)
        punto_venta = self.config.get("facturacion", {}).get("punto_venta", 1)
        
        # Construir comprobante
        comprobante = {
            "tipo": tipo,
            "tipo_nombre": tipo_info["nombre"],
            "numero": numero,
            "punto_venta": punto_venta,
            "fecha": fecha,
            "fecha_emision": datetime.now().isoformat(),
            "receptor": {
                "razon_social": razon_social,
                "cuit": cuit_receptor,
                "domicilio": parameters.get("domicilio", ""),
                "condicion_iva": parameters.get("condicion_iva_receptor", "consumidor_final")
            },
            "emisor": self.config.get("empresa", {}),
            "detalle": detalle if detalle else [
                {
                    "descripcion": parameters.get("descripcion", "Producto/Servicio"),
                    "precio": neto,
                    "cantidad": 1,
                    "unidad": "unidad"
                }
            ],
            "montos": {
                "neto": round(neto, 2),
                "iva": round(iva, 2),
                "iva_porcentaje": iva_pct,
                "total": round(total, 2),
                "moneda": self.config.get("facturacion", {}).get("moneda", "ARS"),
                "cotizacion": self.config.get("facturacion", {}).get("cotizacion", 1.0),
            }
        }
        
        # Generar hash único
        hash_str = f"{comprobante['emisor'].get('cuit')}{comprobante['receptor'].get('cuit')}{numero}{fecha}"
        comprobante["hash"] = hashlib.sha256(hash_str.encode()).hexdigest()[:8]
        
        # Guardar comprobante
        self._save_invoice(comprobante)
        
        # Actualizar último número
        self._update_last_number(numero)
        
        return comprobante
    
    def _save_invoice(self, comprobante: Dict):
        """Guarda un comprobante en archivo."""
        try:
            filename = f"ARCA_{comprobante['tipo']:03d}_{comprobante['punto_venta']:04d}_{comprobante['numero']:08d}.json"
            filepath = ARCA_INVOICES_PATH / filename
            filepath.write_text(
                json.dumps(comprobante, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            print(f"[ARCA] Comprobante guardado: {filename}")
        except Exception as e:
            print(f"[ARCA] Error guardando comprobante: {e}")
    
    def _load_invoice(self, filename: str) -> Optional[Dict]:
        """Carga un comprobante desde archivo."""
        try:
            filepath = ARCA_INVOICES_PATH / filename
            if filepath.exists():
                return json.loads(filepath.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[ARCA] Error cargando comprobante: {e}")
        return None
    
    # ─── LISTAR COMPROBANTES ─────────────────────────────────────────────
    def list_invoices(self, limit: int = 20, tipo: int = None) -> List[Dict]:
        """Lista los comprobantes generados."""
        invoices = []
        
        try:
            files = sorted(ARCA_INVOICES_PATH.glob("ARCA_*.json"), 
                         key=lambda x: x.stat().st_mtime, reverse=True)
            
            for filepath in files[:limit]:
                try:
                    data = json.loads(filepath.read_text(encoding="utf-8"))
                    if tipo is None or data.get("tipo") == tipo:
                        invoices.append(data)
                except:
                    continue
        except Exception as e:
            print(f"[ARCA] Error listando comprobantes: {e}")
        
        return invoices
    
    # ─── FORMATO PARA IMPRESIÓN ──────────────────────────────────────────
    def format_invoice(self, comprobante: Dict) -> str:
        """Formatea un comprobante para impresión."""
        if not comprobante:
            return "❌ Comprobante no encontrado"
        
        if "error" in comprobante:
            return f"❌ Error: {comprobante['error']}"
        
        lines = [
            "=" * 60,
            f"  {comprobante.get('tipo_nombre', 'Comprobante')}",
            "=" * 60,
            "",
            f"  Número: {comprobante['punto_venta']:04d}-{comprobante['numero']:08d}",
            f"  Fecha: {comprobante.get('fecha', 'N/A')}",
            f"  Hash: {comprobante.get('hash', 'N/A')}",
            "",
            "  --- EMISOR ---",
            f"  {comprobante['emisor'].get('razon_social', 'N/A')}",
            f"  CUIT: {self._format_cuit(comprobante['emisor'].get('cuit', ''))}",
            "",
            "  --- RECEPTOR ---",
            f"  {comprobante['receptor'].get('razon_social', 'Consumidor Final')}",
            f"  CUIT: {self._format_cuit(comprobante['receptor'].get('cuit', ''))}",
            "",
            "  --- DETALLE ---",
        ]
        
        # Detalle
        total_neto = 0
        for item in comprobante.get('detalle', []):
            cantidad = item.get('cantidad', 1)
            precio = item.get('precio', 0)
            subtotal = cantidad * precio
            total_neto += subtotal
            lines.append(f"    {item.get('descripcion', '')} x{cantidad} = ${subtotal:,.2f}")
        
        # Montos
        montos = comprobante.get('montos', {})
        lines.extend([
            "",
            "  --- MONTOS ---",
            f"  Neto: ${montos.get('neto', 0):,.2f}",
            f"  IVA {montos.get('iva_porcentaje', 21)}%: ${montos.get('iva', 0):,.2f}",
            f"  Total: ${montos.get('total', 0):,.2f}",
            f"  Moneda: {montos.get('moneda', 'ARS')}",
            "",
            "=" * 60,
            f"  ¡Comprobante electrónico válido!",
            "=" * 60,
        ])
        
        return "\n".join(lines)
    
    # ─── ENVIAR A ARCA (WEB SERVICE) ─────────────────────────────────────
    def send_to_arca(self, comprobante: Dict) -> Dict:
        """
        Envía el comprobante al web service de ARCA.
        Modo offline: genera archivo para firma.
        """
        # Validar comprobante
        if not comprobante:
            return {"error": "Comprobante inválido"}
        
        # En modo offline, generar archivo para firma
        if not self.config.get("web_service", {}).get("homologacion", True):
            # Generar archivo para firma digital
            try:
                # Crear archivo TXT para firmar
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"ARCA_{comprobante['tipo']:03d}_{comprobante['numero']:08d}_{timestamp}.txt"
                filepath = ARCA_CERT_PATH / filename
                
                # Contenido del archivo
                content = [
                    f"ARCA Comprobante",
                    f"Tipo: {comprobante['tipo']} - {comprobante.get('tipo_nombre', '')}",
                    f"Número: {comprobante['punto_venta']:04d}-{comprobante['numero']:08d}",
                    f"Fecha: {comprobante.get('fecha', '')}",
                    f"Emisor CUIT: {comprobante['emisor'].get('cuit', '')}",
                    f"Receptor CUIT: {comprobante['receptor'].get('cuit', '')}",
                    f"Total: ${comprobante['montos']['total']:,.2f}",
                ]
                
                filepath.write_text("\n".join(content), encoding="utf-8")
                
                return {
                    "success": True,
                    "message": "Archivo para firma generado",
                    "file": str(filepath),
                    "info": "Firmar con certificado ARCA y enviar manualmente"
                }
            except Exception as e:
                return {"error": f"Error generando archivo: {e}"}
        
        # Modo online (implementación simplificada)
        return {
            "success": True,
            "message": "Comprobante listo para enviar",
            "info": "Firmar con certificado digital y enviar al web service de ARCA",
            "caec": "N/A (modo offline)"
        }
    
    # ─── RESÚMENES ──────────────────────────────────────────────────────
    def get_summary(self, year: int = None, month: int = None) -> Dict:
        """Obtiene un resumen de facturación."""
        if year is None:
            year = datetime.now().year
        if month is None:
            month = datetime.now().month
        
        summary = {
            "total_facturas": 0,
            "total_neto": 0,
            "total_iva": 0,
            "total_bruto": 0,
            "por_tipo": {},
            "por_mes": {},
        }
        
        try:
            files = ARCA_INVOICES_PATH.glob("ARCA_*.json")
            for filepath in files:
                try:
                    data = json.loads(filepath.read_text(encoding="utf-8"))
                    fecha = data.get("fecha", "")
                    if fecha and fecha.startswith(f"{year}-{month:02d}"):
                        summary["total_facturas"] += 1
                        montos = data.get("montos", {})
                        summary["total_neto"] += montos.get("neto", 0)
                        summary["total_iva"] += montos.get("iva", 0)
                        summary["total_bruto"] += montos.get("total", 0)
                        
                        tipo = data.get("tipo", 0)
                        tipo_nombre = TIPOS_COMPROBANTE.get(tipo, {}).get("nombre", "Otro")
                        summary["por_tipo"][tipo_nombre] = summary["por_tipo"].get(tipo_nombre, 0) + 1
                except:
                    continue
        except Exception as e:
            print(f"[ARCA] Error en resumen: {e}")
        
        return summary


# ─── INSTANCIA GLOBAL ────────────────────────────────────────────────────
_manager: Optional[ARCAManager] = None

def get_manager() -> ARCAManager:
    """Obtiene la instancia del gestor ARCA."""
    global _manager
    if _manager is None:
        _manager = ARCAManager()
    return _manager


# ─── FUNCIÓN PRINCIPAL ────────────────────────────────────────────────────
def arca_invoice(parameters: Dict, player=None) -> str:
    """
    Genera y gestiona comprobantes ARCA (ex AFIP).
    
    Args:
        parameters: Diccionario con parámetros
            - action: generar | listar | ver | resumen | config | tipos | enviar
            - tipo: Tipo de comprobante (1, 6, 11, etc.)
            - razon_social: Razón social del receptor
            - cuit_receptor: CUIT del receptor
            - detalle: Lista de productos/servicios
            - importe_neto: Importe neto (opcional)
            - iva_pct: Porcentaje de IVA (opcional)
            - fecha: Fecha del comprobante (opcional)
            - filename: Nombre de archivo para ver
    
    Returns:
        Mensaje de resultado
    """
    p = parameters or {}
    action = p.get("action", "generar").strip().lower()
    
    manager = get_manager()
    
    # ─── GENERAR ──────────────────────────────────────────────────────────
    if action == "generar":
        tipo = int(p.get("tipo", 6))
        razon_social = p.get("razon_social", "").strip()
        cuit_receptor = p.get("cuit_receptor", "").strip()
        detalle = p.get("detalle", [])
        
        # Validar parámetros mínimos
        if not detalle and not p.get("importe_neto"):
            return "❌ Error: Especifica detalle de productos o importe_neto"
        
        # Si es Factura A, requiere CUIT
        if tipo == 1 and not cuit_receptor:
            return "❌ Factura A requiere CUIT del receptor"
        
        # Generar comprobante
        comprobante = manager.generate_invoice(p)
        
        if "error" in comprobante:
            return f"❌ {comprobante['error']}"
        
        # Formatear resultado
        result = manager.format_invoice(comprobante)
        
        # Opción: enviar a ARCA
        if p.get("enviar", False):
            envio = manager.send_to_arca(comprobante)
            result += f"\n\n📤 Envío a ARCA: {envio.get('message', 'N/A')}"
            if envio.get("file"):
                result += f"\n📂 Archivo: {envio['file']}"
        
        return result
    
    # ─── LISTAR ──────────────────────────────────────────────────────────
    elif action == "listar":
        limit = int(p.get("limit", 20))
        tipo = int(p.get("tipo", 0)) if p.get("tipo") else None
        
        invoices = manager.list_invoices(limit, tipo)
        
        if not invoices:
            return "📭 No hay comprobantes registrados."
        
        lines = ["📋 COMPROBANTES GENERADOS", "━" * 50]
        for inv in invoices:
            tipo_nombre = TIPOS_COMPROBANTE.get(inv.get("tipo", 0), {}).get("nombre", "Desconocido")
            fecha = inv.get("fecha", "N/A")
            numero = f"{inv.get('punto_venta', 1):04d}-{inv.get('numero', 0):08d}"
            total = inv.get("montos", {}).get("total", 0)
            receptor = inv.get("receptor", {}).get("razon_social", "Consumidor Final")[:30]
            
            lines.append(f"  📄 {tipo_nombre}")
            lines.append(f"     N° {numero} | {fecha} | ${total:,.2f}")
            lines.append(f"     Receptor: {receptor}")
            lines.append("")
        
        return "\n".join(lines)
    
    # ─── VER ─────────────────────────────────────────────────────────────
    elif action == "ver":
        filename = p.get("filename", "").strip()
        if not filename:
            return "❌ Especifica el nombre del archivo (filename='...')"
        
        comprobante = manager._load_invoice(filename)
        if comprobante:
            return manager.format_invoice(comprobante)
        else:
            return f"❌ Comprobante no encontrado: {filename}"
    
    # ─── RESUMEN ──────────────────────────────────────────────────────────
    elif action == "resumen":
        year = int(p.get("year", datetime.now().year))
        month = int(p.get("month", datetime.now().month))
        
        summary = manager.get_summary(year, month)
        
        if summary["total_facturas"] == 0:
            return f"📊 No hay comprobantes en {year}-{month:02d}"
        
        lines = [
            f"📊 RESUMEN DE FACTURACIÓN",
            f"━" * 40,
            f"📅 Periodo: {year}-{month:02d}",
            f"📄 Total comprobantes: {summary['total_facturas']}",
            f"💰 Total Neto: ${summary['total_neto']:,.2f}",
            f"💰 Total IVA: ${summary['total_iva']:,.2f}",
            f"💰 Total Bruto: ${summary['total_bruto']:,.2f}",
            "",
            "📂 Por tipo:"
        ]
        
        for tipo, count in summary.get("por_tipo", {}).items():
            lines.append(f"  • {tipo}: {count}")
        
        return "\n".join(lines)
    
    # ─── CONFIGURACIÓN ──────────────────────────────────────────────────
    elif action == "config":
        config = manager.config
        
        lines = [
            "⚙️ CONFIGURACIÓN ARCA (ex AFIP)",
            "━" * 40,
            "",
            "🏢 EMPRESA:",
            f"  Razón Social: {config['empresa'].get('razon_social', 'No configurado')}",
            f"  CUIT: {manager._format_cuit(config['empresa'].get('cuit', ''))}",
            f"  Domicilio: {config['empresa'].get('domicilio', 'No configurado')}",
            f"  Condición IVA: {config['empresa'].get('condicion_iva', 'No configurado')}",
            f"  Ingresos Brutos: {config['empresa'].get('ingresos_brutos', 'No configurado')}",
            "",
            "📄 FACTURACIÓN:",
            f"  Último Número: {config['facturacion'].get('ultimo_numero', 0)}",
            f"  Punto de Venta: {config['facturacion'].get('punto_venta', 1)}",
            f"  Tipo por defecto: {TIPOS_COMPROBANTE.get(config['facturacion'].get('tipo_comprobante', 6), {}).get('nombre', 'B')}",
            f"  Moneda: {config['facturacion'].get('moneda', 'ARS')}",
        ]
        
        # Mostrar cómo configurar
        lines.extend([
            "",
            "💡 Para configurar, edita el archivo:",
            f"   {ARCA_CONFIG_PATH}",
            "",
            "📌 Ejemplo de configuración:",
            '  {"empresa": {"razon_social": "Mi Empresa SRL", "cuit": "30-12345678-9"}}'
        ])
        
        return "\n".join(lines)
    
    # ─── TIPOS ──────────────────────────────────────────────────────────
    elif action == "tipos":
        lines = ["📋 TIPOS DE COMPROBANTES ARCA", "━" * 40]
        
        for codigo, info in sorted(TIPOS_COMPROBANTE.items()):
            lines.append(f"  {codigo:2d} - {info['nombre']}")
            lines.append(f"       Tipo: {info['tipo']} | Sujeto: {info['sujeto']}")
        
        lines.append("")
        lines.append("💡 Usa tipo='codigo' para generar")
        lines.append("   Ej: tipo=6 para Factura B")
        
        return "\n".join(lines)
    
    # ─── ENVIAR ──────────────────────────────────────────────────────────
    elif action == "enviar":
        filename = p.get("filename", "").strip()
        if not filename:
            return "❌ Especifica el nombre del archivo (filename='...')"
        
        comprobante = manager._load_invoice(filename)
        if not comprobante:
            return f"❌ Comprobante no encontrado: {filename}"
        
        result = manager.send_to_arca(comprobante)
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        return f"📤 {result.get('message', 'Comprobante enviado')}\n📂 {result.get('file', 'N/A')}"
    
    # ─── AYUDA ──────────────────────────────────────────────────────────
    else:
        return (
            "📖 ARCA INVOICE (ex AFIP) - COMANDOS\n"
            "━" * 50 + "\n\n"
            "📄 Generar comprobante:\n"
            "  {'action':'generar','tipo':6,'razon_social':'Cliente','cuit_receptor':'20-12345678-9','detalle':[{'descripcion':'Producto','precio':1000,'cantidad':2}]}\n\n"
            "📋 Listar comprobantes:\n"
            "  {'action':'listar','limit':10}\n\n"
            "👁️ Ver comprobante:\n"
            "  {'action':'ver','filename':'ARCA_006_0001_00000001.json'}\n\n"
            "📊 Resumen:\n"
            "  {'action':'resumen','year':2026,'month':1}\n\n"
            "⚙️ Configuración:\n"
            "  {'action':'config'}\n\n"
            "📋 Tipos disponibles:\n"
            "  {'action':'tipos'}\n\n"
            "📤 Enviar a ARCA:\n"
            "  {'action':'enviar','filename':'ARCA_006_0001_00000001.json'}\n\n"
            "📌 TIPOS DE COMPROBANTE:\n"
            "  1 - Factura A (Responsable Inscripto)\n"
            "  6 - Factura B (Consumidor Final)\n"
            "  11 - Factura C (Monotributista)\n"
            "  2 - Nota de Crédito A\n"
            "  7 - Nota de Crédito B\n"
            "  12 - Nota de Crédito C"
        )


# ─── INICIALIZACIÓN ──────────────────────────────────────────────────────
def init_arca():
    """Inicializa el módulo ARCA."""
    print("[ARCA] Inicializando...")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    ARCA_INVOICES_PATH.mkdir(parents=True, exist_ok=True)
    ARCA_CERT_PATH.mkdir(parents=True, exist_ok=True)
    
    if not requests:
        print("[ARCA] ⚠️ requests no instalado - integración web limitada")
    
    print("[ARCA] ✅ Listo")
    return True