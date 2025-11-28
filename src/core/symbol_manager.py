"""
Symbol Manager - Orquestra múltiplos símbolos
Virtus Investimentos
"""

from typing import Dict
from loguru import logger

from core.mt5_connector import MT5Connector
from core.risk_manager import RiskManager
from core.watchdog import ThreadWatchdog
from core.symbol_context import SymbolContext
from analysis.news_analyzer import NewsAnalyzer
from notifications.telegram_bot import TelegramNotifier
from database.strategy_stats import StrategyStatsDB
from ml.strategy_learner import StrategyLearner


class SymbolManager:
    """
    Gerenciador multi-símbolo
    Coordena contextos independentes para cada símbolo (XAUUSD, EURUSD, etc)
    """
    
    def __init__(self, config: Dict):
        """
        Inicializa gerenciador multi-símbolo
        
        Args:
            config: Configuração global completa
        """
        self.config = config
        self.contexts: Dict[str, SymbolContext] = {}
        
        logger.info("=" * 80)
        logger.info("INICIALIZANDO SYMBOL MANAGER (MULTI-SÍMBOLO)")
        logger.info("=" * 80)
        
        # ════════════════════════════════════════════════════════
        # 🔄 CRIAR RECURSOS COMPARTILHADOS (uma única instância)
        # ════════════════════════════════════════════════════════
        
        logger.info("Inicializando recursos compartilhados...")
        
        # MT5 Connector (conexão única)
        self.mt5 = MT5Connector(config)
        if not self.mt5.connect():
            raise RuntimeError("❌ Falha ao conectar MT5")
        logger.success("  ✅ MT5 conectado")
        
        # Risk Manager (gerencia risco global)
        self.risk_manager = RiskManager(config, self.mt5)
        logger.success("  ✅ RiskManager inicializado")
        
        # Telegram (notificações centralizadas)
        self.telegram = TelegramNotifier(
            config,
            mt5=self.mt5,
            stats_db=None  # Será definido abaixo
        )
        logger.success("  ✅ Telegram inicializado")
        
        # Database (stats compartilhadas)
        self.stats_db = StrategyStatsDB()
        self.telegram.stats_db = self.stats_db  # Vincular
        logger.success("  ✅ StrategyStatsDB inicializado")
        
        # News Analyzer (análise de notícias global)
        self.news_analyzer = NewsAnalyzer(config)
        logger.success("  ✅ NewsAnalyzer inicializado")
        
        # Strategy Learner (aprendizagem ML global)
        self.learner = StrategyLearner()
        logger.success("  ✅ StrategyLearner inicializado")
        
        # Watchdog (monitoramento de threads)
        self.watchdog = ThreadWatchdog(timeout_seconds=600)  # 10 min
        self.watchdog.start()
        logger.success("  ✅ Watchdog iniciado (timeout: 10 min)")
        
        # Pacote de recursos compartilhados
        self.shared_resources = {
            'mt5': self.mt5,
            'risk_manager': self.risk_manager,
            'telegram': self.telegram,
            'stats_db': self.stats_db,
            'news_analyzer': self.news_analyzer,
            'learner': self.learner,
            'watchdog': self.watchdog
        }
        
        logger.success("✅ Recursos compartilhados prontos\n")
        
        # ════════════════════════════════════════════════════════
        # ⚡ CRIAR CONTEXTOS PARA CADA SÍMBOLO
        # ════════════════════════════════════════════════════════
        self._create_symbol_contexts()
    
    def _create_symbol_contexts(self):
        """Cria contextos para símbolos configurados"""
        trading_config = self.config.get('trading', {})
        
        # Detectar se é configuração antiga (symbol: XAUUSD) ou nova (symbols: {...})
        if 'symbols' in trading_config:
            # ✅ NOVA ESTRUTURA: trading.symbols.XAUUSD, trading.symbols.EURUSD
            logger.info("Detectada configuração multi-símbolo (nova estrutura)")
            symbols_config = trading_config['symbols']
            
            for symbol, symbol_config in symbols_config.items():
                if symbol_config.get('enabled', True):
                    logger.info(f"\n📊 Criando contexto para {symbol}...")
                    
                    context = SymbolContext(
                        symbol=symbol,
                        symbol_config=symbol_config,
                        shared_resources=self.shared_resources,
                        global_config=self.config
                    )
                    
                    self.contexts[symbol] = context
                    logger.success(f"✅ Contexto {symbol} criado\n")
                else:
                    logger.warning(f"⚠️ {symbol} desabilitado no config")
        
        else:
            # ⚠️ ESTRUTURA ANTIGA: trading.symbol = XAUUSD (compatibilidade)
            logger.warning(
                "Detectada configuração antiga (single-symbol). "
                "Criando contexto único para compatibilidade."
            )
            
            symbol = trading_config.get('symbol', 'XAUUSD')
            
            # Extrair configurações relevantes
            symbol_config = {
                'enabled': True,
                'default_lot_size': trading_config.get('default_lot_size', 0.01),
                'min_lot_size': trading_config.get('min_lot_size', 0.01),
                'max_lot_size': trading_config.get('max_lot_size', 1.0),
                'max_open_positions': trading_config.get('max_open_positions', 12),
                'spread_threshold': trading_config.get('spread_threshold', 5),
                'slippage': trading_config.get('slippage', 3),
            }
            
            context = SymbolContext(
                symbol=symbol,
                symbol_config=symbol_config,
                shared_resources=self.shared_resources,
                global_config=self.config
            )
            
            self.contexts[symbol] = context
            logger.success(f"✅ Contexto {symbol} criado (modo compatibilidade)\n")
        
        if not self.contexts:
            raise RuntimeError("❌ Nenhum símbolo habilitado no config!")
        
        logger.info("=" * 80)
        logger.info(f"SYMBOL MANAGER PRONTO: {len(self.contexts)} símbolos ativos")
        logger.info("=" * 80)
        for symbol in self.contexts.keys():
            logger.info(f"  📊 {symbol}")
        logger.info("=" * 80 + "\n")
    
    def start_all(self):
        """Inicia todos os contextos de símbolos"""
        logger.info("🚀 Iniciando todos os contextos...\n")
        
        for symbol, context in self.contexts.items():
            try:
                context.start()
                logger.success(f"✅ {symbol} iniciado\n")
            except Exception as e:
                logger.error(f"❌ Erro ao iniciar {symbol}: {e}")
                self.telegram.send_message_sync(
                    f"❌ ERRO ao iniciar {symbol}: {e}"
                )
        
        # Mensagem consolidada
        active_symbols = [s for s, c in self.contexts.items() if c.running]
        
        if active_symbols:
            message = (
                f"🚀 *URION MULTI-SÍMBOLO ATIVO*\n\n"
                f"Símbolos: {', '.join(active_symbols)}\n"
                f"Threads: {sum(len(c.executors) for c in self.contexts.values())} estratégias\n"
                f"Status: ✅ Operacional"
            )
            self.telegram.send_message_sync(message)
            logger.success("✅ SymbolManager: Todos os contextos iniciados!")
        else:
            logger.error("❌ Nenhum contexto foi iniciado com sucesso")
    
    def stop_all(self):
        """Para todos os contextos"""
        logger.info("🛑 Parando todos os contextos...\n")
        
        for symbol, context in self.contexts.items():
            try:
                context.stop()
                logger.success(f"✅ {symbol} parado")
            except Exception as e:
                logger.error(f"❌ Erro ao parar {symbol}: {e}")
        
        # Parar watchdog
        if hasattr(self, 'watchdog'):
            self.watchdog.stop()
            logger.success("✅ Watchdog parado")
        
        logger.success("✅ SymbolManager: Todos os contextos parados")
    
    def get_status(self) -> Dict:
        """Retorna status de todos os contextos"""
        return {
            'total_symbols': len(self.contexts),
            'active_symbols': sum(1 for c in self.contexts.values() if c.running),
            'contexts': {
                symbol: context.get_status()
                for symbol, context in self.contexts.items()
            }
        }
    
    def get_context(self, symbol: str) -> SymbolContext:
        """Retorna contexto de um símbolo específico"""
        if symbol not in self.contexts:
            raise KeyError(f"Símbolo {symbol} não encontrado")
        return self.contexts[symbol]
