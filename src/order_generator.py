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
from core.watchdog import ThreadWatchdog
from analysis.technical_analyzer import TechnicalAnalyzer
from analysis.news_analyzer import NewsAnalyzer
from strategies.strategy_manager import StrategyManager
from notifications.telegram_bot import TelegramNotifier


class OrderGenerator:
    """
    Gerador de ordens multi-thread
    Cada estratégia executa em thread independente
    """
    
    def __init__(self, config=None, telegram=None):
        """Inicializa Order Generator"""
        
        # Carregar configurações
        if config is None:
            self.config_manager = ConfigManager()
            self.config = self.config_manager.config
        else:
            self.config = config
        
        # Componentes compartilhados
        self.mt5 = MT5Connector(self.config)
        self.risk_manager = RiskManager(self.config, self.mt5)
        self.technical_analyzer = TechnicalAnalyzer(self.mt5, self.config)
        self.news_analyzer = NewsAnalyzer(self.config)
        self.strategy_manager = StrategyManager(self.config)
        self.telegram = telegram if telegram else TelegramNotifier(self.config)
        
        # Watchdog para monitoramento de threads
        self.watchdog = ThreadWatchdog(timeout_seconds=600)  # 10 min
        
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
        """Cria executors para cada estratégia ativa E cada símbolo ativo"""
        
        # Obter símbolos ativos da configuração
        symbols_config = self.config.get('trading', {}).get('symbols', {})
        active_symbols = []
        
        for symbol, symbol_config in symbols_config.items():
            if isinstance(symbol_config, dict) and symbol_config.get('enabled', False):
                active_symbols.append(symbol)
        
        # Fallback: se não há símbolos configurados, usar XAUUSD
        if not active_symbols:
            active_symbols = ['XAUUSD']
            logger.warning("Nenhum símbolo ativo encontrado, usando XAUUSD como fallback")
        
        logger.info(f"🌍 Símbolos ativos: {active_symbols}")
        
        # Criar executor para cada combinação de estratégia + símbolo
        for symbol in active_symbols:
            symbol_config = symbols_config.get(symbol, {})
            
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
                        telegram=self.telegram,
                        watchdog=self.watchdog,
                        symbol=symbol,  # Passar símbolo específico
                        symbol_config=symbol_config  # Configuração do símbolo
                    )
                    self.executors.append(executor)
                    logger.info(f"Executor criado: {name} @ {symbol}")
    
    def start(self):
        """Inicia todos os executors"""
        if self.running:
            logger.warning("OrderGenerator já está executando")
            return
        
        self.running = True
        logger.info("Iniciando OrderGenerator (multi-thread)...")
        
        # Iniciar watchdog
        self.watchdog.start()
        logger.success("✅ Watchdog iniciado (timeout: 10 min)")
        
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
        
        # Parar watchdog
        self.watchdog.stop()
        
        # Parar cada executor
        for executor in self.executors:
            executor.stop()
        
        logger.success("OrderGenerator parado")
    
    def status(self):
        """Exibe status de todas as estratégias"""
        logger.info("=" * 80)
        logger.info("STATUS DO ORDER GENERATOR (MULTI-THREAD MULTI-SYMBOL)")
        logger.info("=" * 80)
        
        logger.info(f"Running: {self.running}")
        logger.info(f"Executors ativos: {len(self.executors)}")
        
        # Agrupar por símbolo
        by_symbol = {}
        for executor in self.executors:
            symbol = executor.symbol
            if symbol not in by_symbol:
                by_symbol[symbol] = []
            by_symbol[symbol].append(executor)
        
        for symbol, executors in by_symbol.items():
            logger.info(f"\n  🌍 {symbol}:")
            for executor in executors:
                status = "🟢" if executor.running else "🔴"
                logger.info(
                    f"    {status} {executor.strategy_name} - "
                    f"Ciclo: {executor.cycle_seconds}s - "
                    f"Magic: {executor.magic_number}"
                )
        
        logger.info("=" * 80)
