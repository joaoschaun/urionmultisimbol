"""
Order Generator (Multi-Thread Multi-Symbol)
Gerencia múltiplas estratégias em threads independentes
🔥 CORRIGIDO: Cada símbolo tem suas próprias instâncias de analyzers e strategies
"""

import time
from typing import Dict, List, Optional
from loguru import logger

from core.mt5_connector import MT5Connector
from core.config_manager import ConfigManager
from core.risk_manager import RiskManager
from core.strategy_executor import StrategyExecutor
from core.watchdog import ThreadWatchdog
from analysis.technical_analyzer import TechnicalAnalyzer
from analysis.news_analyzer import NewsAnalyzer
from strategies.strategy_manager import StrategyManager

# Import opcional do Telegram (pode falhar em ambientes sem SSL configurado)
try:
    from notifications.telegram_bot import TelegramNotifier
    TELEGRAM_AVAILABLE = True
except Exception as e:
    logger.warning(f"⚠️ Telegram não disponível: {e}")
    TelegramNotifier = None
    TELEGRAM_AVAILABLE = False


class OrderGenerator:
    """
    Gerador de ordens multi-thread multi-symbol
    Cada símbolo tem instâncias SEPARADAS de analyzers e estratégias
    para evitar contaminação de dados entre símbolos
    """
    
    def __init__(self, config=None, telegram=None):
        """Inicializa Order Generator"""
        
        # Carregar configurações
        if config is None:
            self.config_manager = ConfigManager()
            self.config = self.config_manager.config
        else:
            self.config = config
        
        # Componentes compartilhados (seguros para multi-thread)
        self.mt5 = MT5Connector(self.config)
        self.risk_manager = RiskManager(self.config, self.mt5)
        
        # Telegram opcional
        if telegram:
            self.telegram = telegram
        elif TELEGRAM_AVAILABLE and TelegramNotifier:
            try:
                self.telegram = TelegramNotifier(self.config)
            except Exception as e:
                logger.warning(f"⚠️ Erro ao iniciar Telegram: {e}")
                self.telegram = None
        else:
            self.telegram = None
        
        # Watchdog para monitoramento de threads
        self.watchdog = ThreadWatchdog(timeout_seconds=600)  # 10 min
        
        # 🔥 INSTÂNCIAS POR SÍMBOLO (evita contaminação de cache/dados)
        self.analyzers_by_symbol: Dict[str, Dict] = {}
        self.strategies_by_symbol: Dict[str, StrategyManager] = {}
        
        # Criar executors para cada estratégia
        self.executors: List[StrategyExecutor] = []
        self._create_strategy_executors()
        
        # Estado
        self.running = False
        
        logger.info(
            f"OrderGenerator inicializado com "
            f"{len(self.executors)} executores independentes"
        )
    
    def _get_or_create_analyzers(self, symbol: str) -> Dict:
        """
        Obtém ou cria analyzers para um símbolo específico
        Cada símbolo tem suas próprias instâncias para evitar contaminação
        """
        if symbol not in self.analyzers_by_symbol:
            logger.info(f"🔧 Criando analyzers dedicados para {symbol}")
            self.analyzers_by_symbol[symbol] = {
                'technical': TechnicalAnalyzer(self.mt5, self.config, symbol=symbol),
                'news': NewsAnalyzer(self.config)
            }
        return self.analyzers_by_symbol[symbol]
    
    def _get_or_create_strategies(self, symbol: str) -> StrategyManager:
        """
        Obtém ou cria StrategyManager para um símbolo específico
        Cada símbolo tem suas próprias instâncias de estratégias
        🧠 v2.0: Passa TechnicalAnalyzer para habilitar Market Context
        """
        if symbol not in self.strategies_by_symbol:
            logger.info(f"🔧 Criando estratégias dedicadas para {symbol}")
            
            # 🧠 Obter o TechnicalAnalyzer do símbolo para Market Context
            analyzers = self._get_or_create_analyzers(symbol)
            technical_analyzer = analyzers.get('technical')
            
            self.strategies_by_symbol[symbol] = StrategyManager(
                self.config, 
                symbol=symbol,
                technical_analyzer=technical_analyzer  # 🧠 Para comunicação entre TFs
            )
        return self.strategies_by_symbol[symbol]
    
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
            
            # 🔥 INSTÂNCIAS DEDICADAS POR SÍMBOLO
            analyzers = self._get_or_create_analyzers(symbol)
            strategy_manager = self._get_or_create_strategies(symbol)
            
            for name, strategy in strategy_manager.strategies.items():
                if strategy.is_enabled():
                    executor = StrategyExecutor(
                        strategy_name=name,
                        strategy_instance=strategy,
                        config=self.config,
                        mt5=self.mt5,
                        risk_manager=self.risk_manager,
                        technical_analyzer=analyzers['technical'],  # Analyzer do símbolo
                        news_analyzer=analyzers['news'],  # News do símbolo
                        telegram=self.telegram,
                        watchdog=self.watchdog,
                        symbol=symbol,
                        symbol_config=symbol_config
                    )
                    self.executors.append(executor)
                    logger.info(f"✅ Executor criado: {name} @ {symbol} (magic: {executor.magic_number})")
    
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
