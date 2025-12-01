"""
URION Bot - Start Simples
Inicia o bot de forma direta sem modulos opcionais
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
from core.config_manager import ConfigManager

# Configurar logger simples
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level:7s}</level> | {message}",
    level="INFO"
)
logger.add(
    "logs/urion.log",
    rotation="10 MB",
    retention="7 days",
    level="DEBUG"
)


class SimpleTradingBot:
    """Bot simplificado que funciona"""
    
    def __init__(self):
        self.config = ConfigManager().config
        self.order_generator = None
        self.order_manager = None
        self.running = False
        
        signal.signal(signal.SIGINT, self._signal_handler)
        
        logger.info("=" * 60)
        logger.info("   URION TRADING BOT v2.1 - MULTI-SYMBOL")
        logger.info("=" * 60)
    
    def _signal_handler(self, signum, frame):
        logger.info("Parando bot...")
        self.stop()
    
    def start(self):
        if self.running:
            return
        
        logger.info("Iniciando componentes...")
        
        # Criar componentes
        self.order_generator = OrderGenerator()
        self.order_manager = OrderManager()
        
        # Mostrar executors
        logger.info(f"Total Executors: {len(self.order_generator.executors)}")
        
        symbols = {}
        for ex in self.order_generator.executors:
            if ex.symbol not in symbols:
                symbols[ex.symbol] = []
            symbols[ex.symbol].append(ex.strategy_name)
        
        for sym, strats in symbols.items():
            logger.info(f"  {sym}: {', '.join(strats)}")
        
        # Iniciar Order Manager em thread
        logger.info("Iniciando Order Manager...")
        manager_thread = threading.Thread(
            target=self.order_manager.start,
            name="OrderManager",
            daemon=True
        )
        manager_thread.start()
        
        # Iniciar Order Generator (bloqueia)
        logger.info("Iniciando Order Generator...")
        self.running = True
        
        logger.success("=" * 60)
        logger.success("   BOT ATIVO - Operando em 4 simbolos")
        logger.success("   Pressione Ctrl+C para parar")
        logger.success("=" * 60)
        
        try:
            self.order_generator.start()
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        if not self.running:
            return
        
        self.running = False
        
        if self.order_generator:
            self.order_generator.stop()
        
        if self.order_manager:
            self.order_manager.stop()
        
        logger.success("Bot parado")
        sys.exit(0)


if __name__ == "__main__":
    bot = SimpleTradingBot()
    bot.start()
