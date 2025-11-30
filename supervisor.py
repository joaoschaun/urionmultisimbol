"""
Bot Supervisor
Monitora e reinicia o bot automaticamente em caso de falha
"""

import os
import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime
from loguru import logger

# Configurar logging
log_file = Path(__file__).parent.parent / "logs" / "supervisor.log"
log_file.parent.mkdir(exist_ok=True)

logger.add(
    log_file,
    rotation="10 MB",
    retention="30 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)


class BotSupervisor:
    """
    Supervisor que mantém o bot rodando
    - Restart automático em caso de crash
    - Limitador de restarts consecutivos
    - Logging de falhas
    """
    
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.python_exe = self.base_dir / "venv" / "Scripts" / "python.exe"
        self.main_script = self.base_dir / "src" / "main.py"
        
        # Limites de segurança
        self.max_consecutive_failures = 5
        self.failure_window = 300  # 5 minutos
        self.restart_delay = 10  # segundos
        
        # Histórico de falhas
        self.failures = []
        
    def run_bot(self) -> int:
        """Executa o bot e retorna o código de saída"""
        try:
            logger.info("🚀 Iniciando bot...")
            
            process = subprocess.Popen(
                [str(self.python_exe), str(self.main_script)],
                cwd=str(self.base_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            logger.success(f"✅ Bot iniciado (PID: {process.pid})")
            
            # Aguardar processo
            return_code = process.wait()
            
            logger.info(f"🛑 Bot encerrado (código: {return_code})")
            return return_code
            
        except Exception as e:
            logger.error(f"❌ Erro ao executar bot: {e}")
            return 1
    
    def should_restart(self, return_code: int) -> bool:
        """Decide se deve reiniciar baseado no histórico"""
        now = time.time()
        
        # Limpar falhas antigas (fora da janela)
        self.failures = [f for f in self.failures if now - f < self.failure_window]
        
        # Adicionar falha atual
        if return_code != 0:
            self.failures.append(now)
            
        # Verificar se excedeu o limite
        if len(self.failures) >= self.max_consecutive_failures:
            logger.error(
                f"❌ Muitas falhas consecutivas ({len(self.failures)}) "
                f"em {self.failure_window}s. PARANDO supervisor."
            )
            return False
            
        # Shutdown normal (código 0 ou KeyboardInterrupt)
        if return_code == 0:
            logger.info("✅ Shutdown normal detectado. NÃO reiniciando.")
            return False
            
        return True
    
    def start(self):
        """Inicia loop de supervisão"""
        logger.success("=" * 80)
        logger.success("🎯 BOT SUPERVISOR INICIADO")
        logger.success("=" * 80)
        logger.info(f"Python: {self.python_exe}")
        logger.info(f"Script: {self.main_script}")
        logger.info(f"Max falhas: {self.max_consecutive_failures} em {self.failure_window}s")
        logger.info(f"Delay restart: {self.restart_delay}s")
        logger.success("=" * 80)
        
        restart_count = 0
        
        try:
            while True:
                start_time = datetime.now()
                return_code = self.run_bot()
                end_time = datetime.now()
                
                runtime = (end_time - start_time).total_seconds()
                logger.info(f"📊 Tempo de execução: {runtime:.1f}s")
                
                # Decidir se reinicia
                if not self.should_restart(return_code):
                    break
                    
                restart_count += 1
                logger.warning(f"🔄 Restart #{restart_count} em {self.restart_delay}s...")
                logger.warning(f"   Falhas na janela: {len(self.failures)}/{self.max_consecutive_failures}")
                
                time.sleep(self.restart_delay)
                
        except KeyboardInterrupt:
            logger.info("🛑 Supervisor encerrado manualmente")
        except Exception as e:
            logger.exception(f"❌ Erro crítico no supervisor: {e}")
        finally:
            logger.success("=" * 80)
            logger.success(f"✅ SUPERVISOR ENCERRADO (Total restarts: {restart_count})")
            logger.success("=" * 80)


if __name__ == "__main__":
    supervisor = BotSupervisor()
    supervisor.start()
