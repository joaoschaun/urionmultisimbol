"""
Symbol Context - Isola recursos por símbolo
Virtus Investimentos
"""

import threading
from typing import Dict, Optional
from loguru import logger

from core.mt5_connector import MT5Connector
from core.risk_manager import RiskManager
from core.strategy_executor import StrategyExecutor
from core.watchdog import ThreadWatchdog
from core.market_hours import MarketHoursManager, ForexMarketHours
from analysis.technical_analyzer import TechnicalAnalyzer
from analysis.news_analyzer import NewsAnalyzer
from strategies.strategy_manager import StrategyManager
from notifications.telegram_bot import TelegramNotifier
from database.strategy_stats import StrategyStatsDB
from ml.strategy_learner import StrategyLearner


class SymbolContext:
    """
    Contexto isolado para um símbolo específico
    Gerencia recursos dedicados (OrderGenerator/Manager) e compartilhados (MT5/Telegram)
    """
    
    def __init__(
        self,
        symbol: str,
        symbol_config: Dict,
        shared_resources: Dict,
        global_config: Dict
    ):
        """
        Inicializa contexto para um símbolo
        
        Args:
            symbol: Nome do símbolo (XAUUSD, EURUSD, etc)
            symbol_config: Configurações específicas do símbolo
            shared_resources: Recursos compartilhados (mt5, telegram, etc)
            global_config: Configuração global completa
        """
        self.symbol = symbol
        self.symbol_config = symbol_config
        self.global_config = global_config
        self.enabled = symbol_config.get('enabled', True)
        
        logger.info(f"Inicializando SymbolContext para {symbol}")
        
        # ════════════════════════════════════════════════════════
        # 🔄 RECURSOS COMPARTILHADOS (recebidos prontos)
        # ════════════════════════════════════════════════════════
        self.mt5: MT5Connector = shared_resources['mt5']
        self.risk_manager: RiskManager = shared_resources['risk_manager']
        self.telegram: TelegramNotifier = shared_resources['telegram']
        self.news_analyzer: NewsAnalyzer = shared_resources['news_analyzer']
        self.stats_db: StrategyStatsDB = shared_resources['stats_db']
        self.learner: StrategyLearner = shared_resources['learner']
        self.watchdog: ThreadWatchdog = shared_resources['watchdog']
        
        # ════════════════════════════════════════════════════════
        # ⚡ RECURSOS ISOLADOS (criados para este símbolo)
        # ════════════════════════════════════════════════════════
        
        # Technical Analyzer isolado (cada símbolo tem seus próprios indicadores)
        self.technical_analyzer = TechnicalAnalyzer(
            self.mt5,
            self._build_symbol_config()
        )
        
        # Strategy Manager isolado (estratégias independentes por símbolo)
        self.strategy_manager = StrategyManager(
            self._build_symbol_config()
        )
        
        # 🆕 Criar MarketHours apropriado para o tipo de símbolo
        self.market_hours = self._create_market_hours()
        
        # Criar executors para estratégias ativas deste símbolo
        self.executors = []
        self._create_strategy_executors()
        
        # Threads de Order Generator/Manager
        self.generator_thread: Optional[threading.Thread] = None
        self.manager_thread: Optional[threading.Thread] = None
        
        # Estado
        self.running = False
        
        logger.success(
            f"✅ SymbolContext {symbol} inicializado: "
            f"{len(self.executors)} estratégias ativas"
        )
    
    def _build_symbol_config(self) -> Dict:
        """
        Constrói configuração mesclando global + específico do símbolo
        """
        config = self.global_config.copy()
        
        # Override trading settings com configs específicas do símbolo
        if 'trading' not in config:
            config['trading'] = {}
        
        config['trading']['symbol'] = self.symbol
        config['trading'].update(self.symbol_config)
        
        return config
    
    def _create_market_hours(self):
        """
        Cria gerenciador de horários apropriado para o tipo de símbolo
        
        XAUUSD (Ouro): MarketHoursManager (COMEX NY, respeita feriados)
        Forex (EUR/GBP/JPY): ForexMarketHours (24/5, sem feriados)
        """
        symbol_upper = self.symbol.upper()
        
        # Lista de símbolos que operam via COMEX/NY (respeitam feriados dos EUA)
        us_market_symbols = ['XAUUSD', 'XAGUSD']  # Ouro e Prata
        
        if symbol_upper in us_market_symbols:
            logger.info(f"  📍 {self.symbol}: MarketHours COMEX/NY (com feriados)")
            return MarketHoursManager(self.global_config)
        else:
            logger.info(f"  🌍 {self.symbol}: MarketHours FOREX (24/5, sem feriados)")
            return ForexMarketHours(self.global_config)
    
    def _create_strategy_executors(self):
        """Cria executors para cada estratégia ativa deste símbolo"""
        for name, strategy in self.strategy_manager.strategies.items():
            if strategy.is_enabled():
                executor = StrategyExecutor(
                    strategy_name=name,
                    strategy_instance=strategy,
                    config=self._build_symbol_config(),
                    mt5=self.mt5,
                    risk_manager=self.risk_manager,
                    technical_analyzer=self.technical_analyzer,
                    news_analyzer=self.news_analyzer,
                    telegram=self.telegram,
                    learner=self.learner,
                    watchdog=self.watchdog,
                    market_hours=self.market_hours  # 🆕 Passar market_hours customizado
                )
                self.executors.append(executor)
                logger.info(f"  ├─ Executor {name} criado para {self.symbol}")
    
    def start(self):
        """Inicia order generator e manager para este símbolo"""
        if not self.enabled:
            logger.warning(f"⚠️ {self.symbol} está desabilitado no config")
            return
        
        if self.running:
            logger.warning(f"⚠️ {self.symbol} já está executando")
            return
        
        self.running = True
        logger.info(f"🚀 Iniciando {self.symbol}...")
        
        # ════════════════════════════════════════════════════════
        # 🔥 INICIAR ORDER GENERATOR (estratégias em threads)
        # ════════════════════════════════════════════════════════
        for executor in self.executors:
            executor.start()
        
        logger.success(
            f"✅ {self.symbol} OrderGenerator iniciado: "
            f"{len(self.executors)} threads de estratégia"
        )
        
        # ════════════════════════════════════════════════════════
        # 🔥 INICIAR ORDER MANAGER (monitoramento de posições)
        # ════════════════════════════════════════════════════════
        from order_manager import OrderManager
        
        self.order_manager = OrderManager(
            config=self._build_symbol_config(),
            telegram=self.telegram,
            market_hours=self.market_hours  # 🆕 Passar market_hours customizado
        )
        
        self.manager_thread = threading.Thread(
            target=self.order_manager.start,
            name=f"OrderManager-{self.symbol}",
            daemon=True
        )
        self.manager_thread.start()
        
        logger.success(f"✅ {self.symbol} OrderManager iniciado em thread separada")
    
    def stop(self):
        """Para order generator e manager deste símbolo"""
        if not self.running:
            logger.warning(f"⚠️ {self.symbol} já está parado")
            return
        
        logger.info(f"🛑 Parando {self.symbol}...")
        self.running = False
        
        # Parar executors
        for executor in self.executors:
            executor.stop()
        
        # Parar order manager
        if hasattr(self, 'order_manager'):
            self.order_manager.stop()
        
        logger.success(f"✅ {self.symbol} parado")
    
    def get_status(self) -> Dict:
        """Retorna status do contexto"""
        return {
            'symbol': self.symbol,
            'enabled': self.enabled,
            'running': self.running,
            'strategies': len(self.executors),
            'strategy_names': [
                name for name in self.strategy_manager.strategies.keys()
                if self.strategy_manager.strategies[name].is_enabled()
            ]
        }
