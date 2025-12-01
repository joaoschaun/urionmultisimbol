"""
URION Trading Bot - Fast Startup
Versão otimizada para inicialização rápida e confiável
"""

import sys
import os
import signal
import threading
import time
from pathlib import Path

# Configurar path ANTES de qualquer import
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

# Desabilitar cache bytecode para evitar problemas
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

# Import logger primeiro
from loguru import logger

# Configurar logger simples
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
    level="INFO"
)
logger.add(
    "logs/urion.log",
    rotation="10 MB",
    retention="7 days",
    level="DEBUG",
    encoding="utf-8"
)

logger.info("=" * 60)
logger.info("URION TRADING BOT v2.1 - FAST STARTUP")
logger.info("=" * 60)


class FastTradingBot:
    """Bot de Trading com inicialização rápida"""
    
    def __init__(self):
        self.running = False
        self.order_generator = None
        self.order_manager = None
        self.generator_thread = None
        self.manager_thread = None
        self.pim_thread = None
        self.pim = None  # Inicializar como None
        
        # Handler de sinais
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        logger.warning(f"Sinal {signum} recebido, parando...")
        self.stop()
    
    def start(self):
        """Inicia o bot de forma rápida"""
        if self.running:
            logger.warning("Bot já está rodando")
            return
        
        try:
            # 1. Config Manager
            logger.info("[1/4] Carregando configurações...")
            from core.config_manager import ConfigManager
            config_manager = ConfigManager()
            config = config_manager.config
            logger.success("  ✓ Configurações carregadas")
            
            # 2. Order Generator (cria executores)
            logger.info("[2/4] Inicializando Order Generator...")
            from order_generator import OrderGenerator
            self.order_generator = OrderGenerator()
            logger.success(f"  ✓ {len(self.order_generator.executors)} executores criados")
            
            # 3. Order Manager (gerencia posições)
            logger.info("[3/4] Inicializando Order Manager...")
            from order_manager import OrderManager
            from core.mt5_connector import MT5Connector
            mt5_connector = MT5Connector(config)
            self.order_manager = OrderManager(config, mt5_connector)
            logger.success(f"  ✓ Order Manager pronto ({len(self.order_manager.strategy_map)} magic numbers)")
            
            # 4. Position Intelligence Manager
            logger.info("[4/4] Inicializando Position Intelligence...")
            try:
                from core.position_intelligence import PositionIntelligenceManager
                self.pim = PositionIntelligenceManager(config, mt5_connector)
                logger.success("  ✓ Position Intelligence Manager ativo")
            except Exception as e:
                logger.warning(f"  ⚠ PIM não disponível: {e}")
                self.pim = None
            
            self.running = True
            
            # Iniciar threads
            logger.info("=" * 60)
            logger.info("INICIANDO THREADS DE EXECUÇÃO")
            logger.info("=" * 60)
            
            # Thread do Order Generator
            self.generator_thread = threading.Thread(
                target=self._run_generator,
                name="OrderGenerator",
                daemon=True
            )
            self.generator_thread.start()
            logger.success("✓ Order Generator thread iniciada")
            
            # Thread do Order Manager
            self.manager_thread = threading.Thread(
                target=self._run_manager,
                name="OrderManager",
                daemon=True
            )
            self.manager_thread.start()
            logger.success("✓ Order Manager thread iniciada")
            
            # Thread do Position Intelligence
            if self.pim:
                self.pim_thread = threading.Thread(
                    target=self._run_pim,
                    name="PositionIntelligence",
                    daemon=True
                )
                self.pim_thread.start()
                logger.success("✓ Position Intelligence thread iniciada")
            
            logger.info("=" * 60)
            logger.success("🚀 BOT INICIADO COM SUCESSO!")
            logger.info("=" * 60)
            
            # Verificação de status a cada 60s
            self._status_loop()
            
        except Exception as e:
            logger.exception(f"Erro ao iniciar bot: {e}")
            self.stop()
    
    def _run_generator(self):
        """Loop do Order Generator"""
        try:
            self.order_generator.start()
        except Exception as e:
            logger.error(f"Erro no Order Generator: {e}")
    
    def _run_manager(self):
        """Loop do Order Manager"""
        try:
            self.order_manager.start()
        except Exception as e:
            logger.error(f"Erro no Order Manager: {e}")
    
    def _run_pim(self):
        """Loop do Position Intelligence"""
        try:
            self.pim.start()
        except Exception as e:
            logger.error(f"Erro no PIM: {e}")
    
    def _status_loop(self):
        """Loop de status enquanto bot roda"""
        import MetaTrader5 as mt5
        
        while self.running:
            try:
                time.sleep(60)  # A cada minuto
                
                if not mt5.initialize():
                    logger.warning("MT5 desconectado!")
                    continue
                
                # Status das posições
                positions = mt5.positions_get()
                if positions:
                    total_profit = sum(p.profit for p in positions)
                    logger.info(
                        f"📊 Status: {len(positions)} posições | "
                        f"Profit: ${total_profit:.2f}"
                    )
                
                # Status da conta
                info = mt5.account_info()
                if info:
                    logger.info(
                        f"💰 Conta: Balance=${info.balance:.2f} | "
                        f"Equity=${info.equity:.2f}"
                    )
                
            except Exception as e:
                logger.error(f"Erro no status loop: {e}")
    
    def stop(self):
        """Para o bot"""
        logger.info("Parando bot...")
        self.running = False
        
        if self.order_generator:
            self.order_generator.stop()
        
        if self.order_manager:
            self.order_manager.stop()
        
        if self.pim:
            self.pim.stop()
        
        logger.success("Bot parado com sucesso")
        sys.exit(0)


if __name__ == "__main__":
    bot = FastTradingBot()
    bot.start()
