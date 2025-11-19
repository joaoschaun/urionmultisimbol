"""
URION Trading Bot
Bot de Trading Automatizado para XAUUSD
"""

import sys
import signal
import threading
from pathlib import Path
from loguru import logger

# Adicionar src ao path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

from order_generator import OrderGenerator
from order_manager import OrderManager
from core.logger import setup_logger
from core.config_manager import ConfigManager

# Configurar logger ANTES de tudo
config_manager = ConfigManager()
setup_logger(config_manager.config)


class TradingBot:
    """
    Bot de Trading Principal
    Coordena Order Generator e Order Manager
    """
    
    def __init__(self):
        """Inicializa o bot"""
        
        self.order_generator = None
        self.order_manager = None
        self.generator_thread = None
        self.manager_thread = None
        self.running = False
        
        # Configurar handler de sinais
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("=" * 80)
        logger.info("URION TRADING BOT")
        logger.info("Bot de Trading Automatizado para XAUUSD")
        logger.info("=" * 80)
    
    def _signal_handler(self, signum, frame):
        """Handler para sinais de interrupção"""
        logger.info(f"\nSinal {signum} recebido, parando bot...")
        self.stop()
    
    def start(self):
        """Inicia o bot"""
        
        if self.running:
            logger.warning("Bot já está executando")
            return
        
        try:
            # Inicializar componentes
            logger.info("Inicializando componentes...")
            
            self.order_generator = OrderGenerator()
            self.order_manager = OrderManager()
            
            # Iniciar Order Manager em thread separada
            logger.info("Iniciando Order Manager...")
            self.manager_thread = threading.Thread(
                target=self.order_manager.start,
                name="OrderManager",
                daemon=True
            )
            self.manager_thread.start()
            
            # Iniciar Order Generator em thread separada
            logger.info("Iniciando Order Generator...")
            self.generator_thread = threading.Thread(
                target=self.order_generator.start,
                name="OrderGenerator",
                daemon=True
            )
            self.generator_thread.start()
            
            self.running = True
            
            logger.success("Bot iniciado com sucesso!")
            logger.info("Pressione Ctrl+C para parar")
            
            # Aguardar threads
            self.generator_thread.join()
            self.manager_thread.join()
            
        except Exception as e:
            logger.error(f"Erro ao iniciar bot: {e}")
            self.stop()
    
    def stop(self):
        """Para o bot"""
        
        if not self.running:
            return
        
        logger.info("Parando bot...")
        self.running = False
        
        # Parar componentes
        if self.order_generator:
            self.order_generator.stop()
        
        if self.order_manager:
            self.order_manager.stop()
        
        logger.success("Bot parado")
        sys.exit(0)
    
    def status(self):
        """Exibe status do bot"""
        
        logger.info("=" * 80)
        logger.info("STATUS DO BOT")
        logger.info("=" * 80)
        
        logger.info(f"Running: {self.running}")
        
        if self.order_generator:
            logger.info(
                f"Order Generator: "
                f"{'Ativo' if self.order_generator.running else 'Inativo'}"
            )
            if self.order_generator.last_execution:
                logger.info(
                    f"Última execução: {self.order_generator.last_execution}"
                )
        
        if self.order_manager:
            logger.info(
                f"Order Manager: "
                f"{'Ativo' if self.order_manager.running else 'Inativo'}"
            )
            logger.info(
                f"Posições monitoradas: "
                f"{len(self.order_manager.monitored_positions)}"
            )
        
        logger.info("=" * 80)


def main():
    """Função principal"""
    
    # Criar e iniciar bot
    bot = TradingBot()
    
    try:
        bot.start()
    except KeyboardInterrupt:
        logger.info("\nInterrupção pelo usuário")
        bot.stop()
    except Exception as e:
        logger.error(f"Erro fatal: {e}")
        bot.stop()


if __name__ == "__main__":
    main()
