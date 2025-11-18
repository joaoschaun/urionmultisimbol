"""
Order Generator (Multi-Thread)
Gerencia múltiplas estratégias em threads independentes
"""

import time
from typing import Dict, List
from loguru import logger

from core.mt5_connector import MT5Connector
from core.config_manager import ConfigManager
from core.risk_manager import RiskManager
from core.strategy_executor import StrategyExecutor
from analysis.technical_analyzer import TechnicalAnalyzer
from analysis.news_analyzer import NewsAnalyzer
from strategies.strategy_manager import StrategyManager
from notifications.telegram_bot import TelegramNotifier


class OrderGenerator:
    """
    Gerador de ordens multi-thread
    Cada estratégia executa em thread independente
    """
    
    def __init__(self):
        """Inicializa Order Generator"""
        
        # Carregar configurações
        self.config_manager = ConfigManager()
        self.config = self.config_manager.config
        
        # Componentes compartilhados
        self.mt5 = MT5Connector(self.config)
        self.risk_manager = RiskManager(self.config, self.mt5)
        self.technical_analyzer = TechnicalAnalyzer(self.mt5, self.config)
        self.news_analyzer = NewsAnalyzer(self.config)
        self.strategy_manager = StrategyManager(self.config)
        self.telegram = TelegramNotifier(self.config)
        
        # Criar executors para cada estratégia
        self.executors: List[StrategyExecutor] = []
        self._create_strategy_executors()
        
        # Estado
        self.running = False
        
        logger.info(
            f"OrderGenerator inicializado com "
            f"{len(self.executors)} estratégias independentes"
        )
    
    def _create_strategy_executors(self):
        """Cria executors para cada estratégia ativa"""
        for name, strategy in self.strategy_manager.strategies.items():
            if strategy.is_enabled():
                executor = StrategyExecutor(
                    strategy_name=name,
                    strategy_instance=strategy,
                    config=self.config,
                    mt5=self.mt5,
                    risk_manager=self.risk_manager,
                    technical_analyzer=self.technical_analyzer,
                    news_analyzer=self.news_analyzer,
                    telegram=self.telegram
                )
                self.executors.append(executor)
                logger.info(f"Executor criado para: {name}")
    
    def start(self):
        """Inicia todos os executors"""
        if self.running:
            logger.warning("OrderGenerator já está executando")
            return
        
        self.running = True
        logger.info("Iniciando OrderGenerator (multi-thread)...")
        
        # Conectar MT5
        if not self.mt5.is_connected():
            if not self.mt5.connect():
                logger.error("Falha ao conectar MT5")
                self.running = False
                return
        
        # Iniciar cada executor
        for executor in self.executors:
            executor.start()
        
        logger.success(
            f"✅ OrderGenerator iniciado! "
            f"{len(self.executors)} estratégias operando"
        )
        
        # Loop principal (apenas mantém vivo)
        try:
            while self.running:
                time.sleep(60)
        except KeyboardInterrupt:
            logger.info("Interrupção detectada")
            self.stop()
    
    def stop(self):
        """Para todos os executors"""
        if not self.running:
            return
        
        logger.info("Parando OrderGenerator...")
        self.running = False
        
        # Parar cada executor
        for executor in self.executors:
            executor.stop()
        
        logger.success("OrderGenerator parado")
    
    def status(self):
        """Exibe status de todas as estratégias"""
        logger.info("=" * 80)
        logger.info("STATUS DO ORDER GENERATOR (MULTI-THREAD)")
        logger.info("=" * 80)
        
        logger.info(f"Running: {self.running}")
        logger.info(f"Executors ativos: {len(self.executors)}")
        
        for executor in self.executors:
            status = "🟢 Rodando" if executor.running else "🔴 Parado"
            logger.info(
                f"  [{executor.strategy_name}] {status} - "
                f"Ciclo: {executor.cycle_seconds}s - "
                f"Max Pos: {executor.max_positions} - "
                f"Magic: {executor.magic_number}"
            )
        
        logger.info("=" * 80)
