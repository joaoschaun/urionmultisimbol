# -*- coding: utf-8 -*-
"""
URION TRADING BOT - MONITOR 24 HORAS
=====================================
Monitora todos os módulos e operações do bot por 24 horas
Gera relatórios de saúde do sistema a cada intervalo

Autor: Urion Team
Data: 30/11/2025
"""

import os
import sys
import time
import json
import logging
import requests
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict

# Configurar encoding para Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'replace')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'replace')

# Adicionar src ao path
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR / "src"))

# ============================================================================
# CONFIGURAÇÕES
# ============================================================================

CONFIG = {
    "backend_url": "http://localhost:8080",
    "frontend_url": "http://localhost:3000",
    "check_interval": 60,  # Verificar a cada 60 segundos
    "report_interval": 3600,  # Relatório completo a cada 1 hora
    "log_file": BASE_DIR / "logs" / "monitor_24h.log",
    "report_file": BASE_DIR / "logs" / "monitor_report.json",
    "duration_hours": 24,
}

# ============================================================================
# CONFIGURAR LOGGING
# ============================================================================

os.makedirs(BASE_DIR / "logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(CONFIG["log_file"], encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Monitor24H")


# ============================================================================
# CLASSE DE MONITORAMENTO
# ============================================================================

class UrionMonitor:
    """Monitor de 24 horas para o Urion Trading Bot"""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.end_time = self.start_time + timedelta(hours=CONFIG["duration_hours"])
        
        # Estatísticas
        self.stats = {
            "checks_total": 0,
            "checks_success": 0,
            "checks_failed": 0,
            "backend_errors": 0,
            "frontend_errors": 0,
            "mt5_errors": 0,
            "trades_detected": 0,
            "positions_opened": 0,
            "positions_closed": 0,
            "api_response_times": [],
            "errors": [],
            "events": [],
            "hourly_reports": [],
        }
        
        # Estado anterior (para detectar mudanças)
        self.previous_state = {
            "positions": [],
            "balance": 0,
            "trades_count": 0,
        }
        
        # Módulos a verificar
        self.modules = {
            "backend_api": {"status": "unknown", "last_check": None, "errors": 0},
            "frontend": {"status": "unknown", "last_check": None, "errors": 0},
            "mt5_connection": {"status": "unknown", "last_check": None, "errors": 0},
            "websocket": {"status": "unknown", "last_check": None, "errors": 0},
            "database": {"status": "unknown", "last_check": None, "errors": 0},
        }
        
        self.running = True
    
    def log_event(self, event_type: str, message: str, data: Dict = None):
        """Registra um evento"""
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "message": message,
            "data": data or {}
        }
        self.stats["events"].append(event)
        
        if event_type == "ERROR":
            logger.error(f"{message}")
            self.stats["errors"].append(event)
        elif event_type == "WARNING":
            logger.warning(f"{message}")
        elif event_type == "TRADE":
            logger.info(f"[TRADE] {message}")
        else:
            logger.info(f"{message}")
    
    def check_backend(self) -> bool:
        """Verifica se o backend está respondendo"""
        try:
            start = time.time()
            response = requests.get(
                f"{CONFIG['backend_url']}/api/status",
                timeout=10
            )
            elapsed = (time.time() - start) * 1000
            self.stats["api_response_times"].append(elapsed)
            
            if response.status_code == 200:
                data = response.json()
                self.modules["backend_api"]["status"] = "online"
                self.modules["backend_api"]["last_check"] = datetime.now().isoformat()
                return True
            else:
                raise Exception(f"Status code: {response.status_code}")
                
        except Exception as e:
            self.modules["backend_api"]["status"] = "error"
            self.modules["backend_api"]["errors"] += 1
            self.stats["backend_errors"] += 1
            self.log_event("ERROR", f"Backend API falhou: {str(e)}")
            return False
    
    def check_frontend(self) -> bool:
        """Verifica se o frontend está respondendo"""
        try:
            response = requests.get(
                CONFIG['frontend_url'],
                timeout=10
            )
            if response.status_code == 200:
                self.modules["frontend"]["status"] = "online"
                self.modules["frontend"]["last_check"] = datetime.now().isoformat()
                return True
            else:
                raise Exception(f"Status code: {response.status_code}")
                
        except Exception as e:
            self.modules["frontend"]["status"] = "error"
            self.modules["frontend"]["errors"] += 1
            self.stats["frontend_errors"] += 1
            self.log_event("ERROR", f"Frontend falhou: {str(e)}")
            return False
    
    def check_mt5(self) -> Dict:
        """Verifica conexão com MT5 e retorna dados da conta"""
        try:
            response = requests.get(
                f"{CONFIG['backend_url']}/api/account",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                self.modules["mt5_connection"]["status"] = "online"
                self.modules["mt5_connection"]["last_check"] = datetime.now().isoformat()
                return data
            else:
                raise Exception(f"Status code: {response.status_code}")
                
        except Exception as e:
            self.modules["mt5_connection"]["status"] = "error"
            self.modules["mt5_connection"]["errors"] += 1
            self.stats["mt5_errors"] += 1
            self.log_event("ERROR", f"MT5 Connection falhou: {str(e)}")
            return None
    
    def check_positions(self) -> List[Dict]:
        """Verifica posições abertas"""
        try:
            response = requests.get(
                f"{CONFIG['backend_url']}/api/positions",
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            return []
        except:
            return []
    
    def check_trades(self) -> int:
        """Verifica total de trades"""
        try:
            response = requests.get(
                f"{CONFIG['backend_url']}/api/metrics?days=1",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("total_trades", 0)
            return 0
        except:
            return 0
    
    def detect_changes(self, account: Dict, positions: List, trades_count: int):
        """Detecta mudanças no estado (novas trades, posições, etc)"""
        
        # Detectar mudança de balance
        if account and self.previous_state["balance"] > 0:
            balance_change = account["balance"] - self.previous_state["balance"]
            if abs(balance_change) > 0.01:
                self.log_event(
                    "TRADE",
                    f"Balance alterado: ${balance_change:+.2f} (${self.previous_state['balance']:.2f} -> ${account['balance']:.2f})"
                )
        
        # Detectar novas posições
        current_tickets = {p["ticket"] for p in positions}
        previous_tickets = {p["ticket"] for p in self.previous_state["positions"]}
        
        new_positions = current_tickets - previous_tickets
        closed_positions = previous_tickets - current_tickets
        
        for ticket in new_positions:
            pos = next((p for p in positions if p["ticket"] == ticket), None)
            if pos:
                self.stats["positions_opened"] += 1
                self.log_event(
                    "TRADE",
                    f"Nova posição aberta: {pos['symbol']} {pos['type']} {pos['volume']} lots @ {pos['price_open']}"
                )
        
        for ticket in closed_positions:
            pos = next((p for p in self.previous_state["positions"] if p["ticket"] == ticket), None)
            if pos:
                self.stats["positions_closed"] += 1
                self.log_event(
                    "TRADE",
                    f"Posição fechada: {pos['symbol']} {pos['type']} - Profit: ${pos.get('profit', 0):.2f}"
                )
        
        # Detectar novos trades
        if trades_count > self.previous_state["trades_count"]:
            new_trades = trades_count - self.previous_state["trades_count"]
            self.stats["trades_detected"] += new_trades
            self.log_event("TRADE", f"Detectados {new_trades} novo(s) trade(s)")
        
        # Atualizar estado anterior
        if account:
            self.previous_state["balance"] = account["balance"]
        self.previous_state["positions"] = positions
        self.previous_state["trades_count"] = trades_count
    
    def run_check(self):
        """Executa uma verificação completa"""
        self.stats["checks_total"] += 1
        
        # Verificar todos os módulos
        backend_ok = self.check_backend()
        frontend_ok = self.check_frontend()
        account = self.check_mt5()
        positions = self.check_positions()
        trades_count = self.check_trades()
        
        # Detectar mudanças
        self.detect_changes(account, positions, trades_count)
        
        # Contabilizar sucesso/falha
        if backend_ok and frontend_ok and account:
            self.stats["checks_success"] += 1
        else:
            self.stats["checks_failed"] += 1
    
    def generate_report(self) -> Dict:
        """Gera relatório de status"""
        runtime = datetime.now() - self.start_time
        hours = runtime.total_seconds() / 3600
        
        avg_response = 0
        if self.stats["api_response_times"]:
            avg_response = sum(self.stats["api_response_times"]) / len(self.stats["api_response_times"])
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "runtime_hours": round(hours, 2),
            "runtime_formatted": str(runtime).split('.')[0],
            "remaining_hours": round((self.end_time - datetime.now()).total_seconds() / 3600, 2),
            
            "health": {
                "overall": "healthy" if self.stats["checks_failed"] == 0 else "degraded",
                "uptime_percent": round(
                    (self.stats["checks_success"] / max(1, self.stats["checks_total"])) * 100, 2
                ),
                "checks_total": self.stats["checks_total"],
                "checks_success": self.stats["checks_success"],
                "checks_failed": self.stats["checks_failed"],
            },
            
            "modules": self.modules,
            
            "performance": {
                "avg_response_ms": round(avg_response, 2),
                "min_response_ms": round(min(self.stats["api_response_times"]) if self.stats["api_response_times"] else 0, 2),
                "max_response_ms": round(max(self.stats["api_response_times"]) if self.stats["api_response_times"] else 0, 2),
            },
            
            "trading": {
                "trades_detected": self.stats["trades_detected"],
                "positions_opened": self.stats["positions_opened"],
                "positions_closed": self.stats["positions_closed"],
            },
            
            "errors": {
                "total": len(self.stats["errors"]),
                "backend": self.stats["backend_errors"],
                "frontend": self.stats["frontend_errors"],
                "mt5": self.stats["mt5_errors"],
                "recent": self.stats["errors"][-5:] if self.stats["errors"] else [],
            },
        }
        
        return report
    
    def print_status(self):
        """Imprime status atual no console"""
        report = self.generate_report()
        
        print("\n" + "=" * 60)
        print("  URION MONITOR 24H - STATUS")
        print("=" * 60)
        print(f"  Runtime: {report['runtime_formatted']} | Restante: {report['remaining_hours']:.1f}h")
        print("-" * 60)
        print(f"  Saúde: {report['health']['overall'].upper()} ({report['health']['uptime_percent']}% uptime)")
        print(f"  Checks: {report['health']['checks_success']}/{report['health']['checks_total']} OK")
        print("-" * 60)
        print("  MÓDULOS:")
        for name, mod in report["modules"].items():
            status_icon = "[OK]" if mod["status"] == "online" else "[X]" if mod["status"] == "error" else "[?]"
            print(f"    {status_icon} {name}: {mod['status']} (erros: {mod['errors']})")
        print("-" * 60)
        print(f"  TRADING:")
        print(f"    Trades detectados: {report['trading']['trades_detected']}")
        print(f"    Posições abertas: {report['trading']['positions_opened']}")
        print(f"    Posições fechadas: {report['trading']['positions_closed']}")
        print("-" * 60)
        print(f"  API Response: avg {report['performance']['avg_response_ms']:.0f}ms")
        print(f"  Erros totais: {report['errors']['total']}")
        print("=" * 60 + "\n")
    
    def save_report(self):
        """Salva relatório em arquivo JSON"""
        report = self.generate_report()
        self.stats["hourly_reports"].append(report)
        
        with open(CONFIG["report_file"], 'w', encoding='utf-8') as f:
            json.dump({
                "last_update": datetime.now().isoformat(),
                "current": report,
                "hourly_reports": self.stats["hourly_reports"],
                "all_events": self.stats["events"][-100:],  # Últimos 100 eventos
            }, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Relatório salvo em {CONFIG['report_file']}")
    
    def run(self):
        """Executa o monitor por 24 horas"""
        print("\n" + "=" * 60)
        print("  URION TRADING BOT - MONITOR 24 HORAS")
        print("=" * 60)
        print(f"  Início: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Término previsto: {self.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Intervalo de verificação: {CONFIG['check_interval']}s")
        print(f"  Intervalo de relatório: {CONFIG['report_interval']}s")
        print("=" * 60)
        print("\nIniciando monitoramento... (Ctrl+C para parar)\n")
        
        last_report_time = time.time()
        last_status_time = time.time()
        
        try:
            while self.running and datetime.now() < self.end_time:
                # Executar verificação
                self.run_check()
                
                # Mostrar status a cada 5 minutos
                if time.time() - last_status_time >= 300:
                    self.print_status()
                    last_status_time = time.time()
                
                # Salvar relatório a cada hora
                if time.time() - last_report_time >= CONFIG["report_interval"]:
                    self.save_report()
                    last_report_time = time.time()
                
                # Aguardar próximo intervalo
                time.sleep(CONFIG["check_interval"])
                
        except KeyboardInterrupt:
            logger.info("Monitor interrompido pelo usuário")
        
        # Relatório final
        print("\n" + "=" * 60)
        print("  MONITORAMENTO FINALIZADO")
        print("=" * 60)
        self.print_status()
        self.save_report()
        
        return self.generate_report()


# ============================================================================
# EXECUÇÃO PRINCIPAL
# ============================================================================

if __name__ == "__main__":
    monitor = UrionMonitor()
    final_report = monitor.run()
    
    # Resumo final
    print("\n" + "=" * 60)
    print("  RESUMO FINAL DO MONITORAMENTO")
    print("=" * 60)
    print(f"  Duração total: {final_report['runtime_formatted']}")
    print(f"  Uptime: {final_report['health']['uptime_percent']}%")
    print(f"  Total de verificações: {final_report['health']['checks_total']}")
    print(f"  Trades detectados: {final_report['trading']['trades_detected']}")
    print(f"  Erros totais: {final_report['errors']['total']}")
    print("=" * 60)
    print(f"\nRelatório completo salvo em: {CONFIG['report_file']}")
