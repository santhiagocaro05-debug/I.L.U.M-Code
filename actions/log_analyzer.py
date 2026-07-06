import json
import re
import os
from pathlib import Path
from datetime import datetime
from collections import defaultdict

class LogAnalyzer:
    def __init__(self):
        self.log_file = Path("nexus.log")
        self.errors = []
        self.patterns = {
            'error': r'ERROR|ERR|❌',
            'warning': r'WARNING|WARN|⚠️',
            'critical': r'CRITICAL|CRIT|🚨'
        }
        
    def scan_logs(self, lines=100):
        """Escanea las últimas N líneas del log"""
        if not self.log_file.exists():
            return "Archivo de log no encontrado"
            
        try:
            content = self.log_file.read_text(encoding='utf-8', errors='ignore')
            lines_list = content.split('\n')
            recent_lines = lines_list[-lines:]
            
            analysis = {
                'total_lines': len(lines_list),
                'analyzed': len(recent_lines),
                'errors': [],
                'warnings': [],
                'critical': [],
                'timestamps': []
            }
            
            for line in recent_lines:
                if not line.strip():
                    continue
                    
                # Detectar timestamp
                timestamp_match = re.search(r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}', line)
                if timestamp_match:
                    analysis['timestamps'].append(timestamp_match.group())
                    
                # Detectar errores
                for level, pattern in self.patterns.items():
                    if re.search(pattern, line, re.IGNORECASE):
                        analysis[level].append(line.strip())
                        break
                        
            return analysis
            
        except Exception as e:
            return f"Error escaneando logs: {e}"
            
    def diagnose_errors(self):
        """Diagnostica errores comunes"""
        analysis = self.scan_logs()
        
        if isinstance(analysis, str):
            return analysis
            
        diagnosis = []
        
        # Analizar errores
        if analysis['critical']:
            diagnosis.append("🚨 Se detectaron errores críticos:")
            for error in analysis['critical'][-5:]:
                diagnosis.append(f"  • {error}")
                
        if analysis['errors']:
            diagnosis.append("\n⚠️ Errores detectados:")
            for error in analysis['errors'][-5:]:
                diagnosis.append(f"  • {error}")
                
        if not diagnosis:
            diagnosis.append("✅ No se detectaron problemas graves en los logs.")
            
        # Sugerencias basadas en patrones
        suggestions = self.suggest_fixes(analysis)
        if suggestions:
            diagnosis.append("\n💡 Sugerencias:")
            for suggestion in suggestions:
                diagnosis.append(f"  • {suggestion}")
                
        return '\n'.join(diagnosis)
        
    def suggest_fixes(self, analysis):
        """Sugiere soluciones para problemas comunes"""
        suggestions = []
        
        # Convertir todo a string para análisis
        all_text = str(analysis).lower()
        
        if 'connection' in all_text or 'timeout' in all_text:
            suggestions.append("Verifica tu conexión a internet y reinicia")
            
        if 'permission' in all_text or 'access denied' in all_text:
            suggestions.append("Ejecuta NEXUS como administrador")
            
        if 'memory' in all_text or 'out of' in all_text:
            suggestions.append("Cierra otras aplicaciones para liberar memoria RAM")
            
        if 'import' in all_text or 'module' in all_text:
            suggestions.append("Verifica las dependencias instaladas (pip install -r requirements.txt)")
            
        if 'api' in all_text or 'key' in all_text:
            suggestions.append("Verifica tus API Keys en config/api_keys.json")
            
        return suggestions

def log_analyzer(parameters: dict, player=None):
    """
    Analizador de logs para NEXUS
    
    Args:
        parameters: {
            'action': 'scan' | 'diagnose' | 'fix_suggestion',
            'lines': (opcional) número de líneas a escanear
        }
    """
    action = parameters.get('action', 'diagnose')
    lines = parameters.get('lines', 100)
    
    # Singleton
    if not hasattr(log_analyzer, 'instance'):
        log_analyzer.instance = LogAnalyzer()
    
    analyzer = log_analyzer.instance
    
    if action == 'scan':
        analysis = analyzer.scan_logs(lines)
        if isinstance(analysis, str):
            return analysis
            
        result = f"📋 ANÁLISIS DE LOGS (últimas {lines} líneas):\n"
        result += f"Total de líneas: {analysis['total_lines']}\n"
        result += f"Líneas analizadas: {analysis['analyzed']}\n"
        result += f"Errores críticos: {len(analysis['critical'])}\n"
        result += f"Errores: {len(analysis['errors'])}\n"
        result += f"Warnings: {len(analysis['warnings'])}\n"
        
        if analysis['errors'][:3]:
            result += "\nEjemplos de errores:\n"
            for error in analysis['errors'][:3]:
                result += f"  • {error[:100]}...\n"
                
        return result
        
    elif action == 'diagnose':
        return analyzer.diagnose_errors()
        
    elif action == 'fix_suggestion':
        return analyzer.suggest_fixes({})
        
    else:
        return "Acción no reconocida. Usa: scan, diagnose, fix_suggestion"