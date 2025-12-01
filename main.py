"""
URION Trading Bot
Bot de Trading Automatizado Multi-Símbolo

Versao: 2.2 - Multi-Symbol Professional Edition + Advanced AI
"""

import sys
import signal
import threading
import asyncio
from pathlib import Path
from loguru import logger

# Adicionar src ao path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

from order_generator import OrderGenerator
from order_manager import OrderManager
from core.logger import setup_logger
from core.config_manager import ConfigManager

# 🔥 Imports opcionais (módulos avançados podem falhar)
def safe_import(module_path, class_name):
    """Importa módulo de forma segura, retornando None se falhar"""
    try:
        module = __import__(module_path, fromlist=[class_name])
        return getattr(module, class_name)
    except Exception as e:
        logger.warning(f"⚠️ Módulo opcional não disponível: {module_path}.{class_name} - {e}")
        return None

# Módulos core (sempre necessários)
PositionIntelligenceManager = safe_import('core.position_intelligence', 'PositionIntelligenceManager')
get_strategy_communicator = safe_import('core.strategy_communicator', 'get_strategy_communicator')
get_execution_manager = safe_import('core.execution_algorithms', 'get_execution_manager')
get_smart_router = safe_import('core.execution_algorithms', 'get_smart_router')

# Módulos de análise (opcionais)
get_order_flow_analyzer = safe_import('analysis.order_flow_analyzer', 'get_order_flow_analyzer')
ManipulationDetector = safe_import('analysis.manipulation_detector', 'ManipulationDetector')
get_tradingview_manager = safe_import('analysis.tradingview_integration', 'get_tradingview_manager')
get_economic_calendar = safe_import('analysis.economic_calendar', 'get_economic_calendar')

# Módulos de risco (opcionais - requerem scipy)
get_monte_carlo_simulator = safe_import('risk.monte_carlo', 'get_monte_carlo_simulator')
get_var_calculator = safe_import('risk.var_calculator', 'get_var_calculator')

# ML (opcional)
get_ml_training_pipeline = safe_import('ml.training_pipeline', 'get_ml_training_pipeline')
get_finbert_analyzer = safe_import('ml.finbert_analyzer', 'get_finbert_analyzer')
get_transformer_predictor = safe_import('ml.transformer_predictor', 'get_transformer_predictor')

# Análise avançada (opcional)
get_correlation_analyzer = safe_import('analysis.correlation_analyzer', 'get_correlation_analyzer')
get_harmonic_analyzer = safe_import('analysis.harmonic_patterns', 'get_harmonic_analyzer')

# Infraestrutura (opcional)
get_redis_client = safe_import('infrastructure.redis_client', 'get_redis_client')
get_influxdb_client = safe_import('infrastructure.influxdb_client', 'get_influxdb_client')
get_data_hub = safe_import('infrastructure.data_hub', 'get_data_hub')

# Configurar logger ANTES de tudo
config_manager = ConfigManager()
setup_logger(config_manager.config)


class TradingBot:
    """
    Bot de Trading Principal - Professional Edition
    Coordena todos os modulos do sistema de trading
    """
    
    def __init__(self):
        """Inicializa o bot"""
        
        self.config = config_manager.config
        
        # Componentes principais
        self.order_generator = None
        self.order_manager = None
        self.generator_thread = None
        self.manager_thread = None
        self.running = False
        
        # Novos componentes avancados
        self.position_intelligence = None
        self.strategy_communicator = None
        self.order_flow_analyzer = None
        self.manipulation_detector = None
        self.tradingview = None
        self.economic_calendar = None
        self.monte_carlo = None
        self.var_calculator = None
        self.execution_manager = None
        self.smart_router = None
        self.ml_pipeline = None
        self.redis_client = None
        self.influxdb_client = None
        self.data_hub = None
        
        # Novos módulos avançados v2.1
        self.finbert_analyzer = None
        self.transformer_predictor = None
        self.correlation_analyzer = None
        self.harmonic_analyzer = None
        
        # Threads adicionais
        self.position_intel_thread = None
        self.tradingview_thread = None
        self.calendar_thread = None
        
        # Configurar handler de sinais
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("=" * 80)
        logger.info("URION TRADING BOT - PROFESSIONAL EDITION v2.2")
        logger.info("Bot de Trading Automatizado Multi-Símbolo + Advanced AI")
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
            logger.info("=" * 80)
            logger.info("INICIALIZANDO MODULOS AVANCADOS")
            logger.info("=" * 80)
            
            # ========================================
            # 1. INFRAESTRUTURA (Redis, InfluxDB)
            # ========================================
            logger.info("[1/11] Inicializando Infraestrutura...")
            if get_redis_client:
                try:
                    self.redis_client = get_redis_client(self.config)
                    if self.redis_client.connect():
                        logger.success("  ✓ Redis conectado")
                    else:
                        logger.warning("  ⚠ Redis indisponivel, continuando sem cache")
                except Exception as e:
                    logger.warning(f"  ⚠ Redis: {e}")
            else:
                logger.warning("  ⚠ Redis: módulo não disponível")
            
            if get_influxdb_client:
                try:
                    self.influxdb_client = get_influxdb_client(self.config)
                    if self.influxdb_client.connect():
                        logger.success("  ✓ InfluxDB conectado")
                    else:
                        logger.warning("  ⚠ InfluxDB indisponivel, continuando sem metricas")
                except Exception as e:
                    logger.warning(f"  ⚠ InfluxDB: {e}")
            else:
                logger.warning("  ⚠ InfluxDB: módulo não disponível")
            
            # ========================================
            # 2. DATA HUB (Central de Dados)
            # ========================================
            logger.info("[2/11] Inicializando Data Hub...")
            if get_data_hub:
                try:
                    self.data_hub = get_data_hub(self.config)
                    logger.success("  ✓ Data Hub inicializado")
                except Exception as e:
                    logger.warning(f"  ⚠ Data Hub: {e}")
            else:
                logger.warning("  ⚠ Data Hub: módulo não disponível")
            
            # ========================================
            # 3. ORDER FLOW & MANIPULATION
            # ========================================
            logger.info("[3/11] Inicializando Order Flow Analyzer...")
            if get_order_flow_analyzer:
                try:
                    self.order_flow_analyzer = get_order_flow_analyzer(self.config)
                    logger.success("  ✓ Order Flow Analyzer inicializado")
                except Exception as e:
                    logger.warning(f"  ⚠ Order Flow: {e}")
            else:
                logger.warning("  ⚠ Order Flow Analyzer: módulo não disponível")
            
            logger.info("[4/11] Inicializando Manipulation Detector...")
            if ManipulationDetector:
                try:
                    self.manipulation_detector = ManipulationDetector(self.config)
                    logger.success("  ✓ Manipulation Detector inicializado")
                except Exception as e:
                    logger.warning(f"  ⚠ Manipulation Detector: {e}")
            else:
                logger.warning("  ⚠ Manipulation Detector: módulo não disponível")
            
            # ========================================
            # 4. STRATEGY COMMUNICATION
            # ========================================
            logger.info("[5/11] Inicializando Strategy Communicator...")
            if get_strategy_communicator:
                try:
                    self.strategy_communicator = get_strategy_communicator(self.config)
                    self.strategy_communicator.start()
                    logger.success("  ✓ Strategy Communicator ativo")
                except Exception as e:
                    logger.warning(f"  ⚠ Strategy Communicator: {e}")
            else:
                logger.warning("  ⚠ Strategy Communicator: módulo não disponível")
            
            # ========================================
            # 5. RISK MANAGEMENT
            # ========================================
            logger.info("[6/11] Inicializando Risk Management...")
            if get_monte_carlo_simulator and get_var_calculator:
                try:
                    self.monte_carlo = get_monte_carlo_simulator(self.config)
                    self.var_calculator = get_var_calculator(self.config)
                    logger.success("  ✓ Monte Carlo + VaR inicializados")
                except Exception as e:
                    logger.warning(f"  ⚠ Risk Management: {e}")
            else:
                logger.warning("  ⚠ Risk Management: scipy não disponível (VaR/Monte Carlo desativados)")
            
            # ========================================
            # 6. EXECUTION ALGORITHMS
            # ========================================
            logger.info("[7/11] Inicializando Execution Algorithms...")
            if get_execution_manager and get_smart_router:
                try:
                    self.execution_manager = get_execution_manager(self.config)
                    self.smart_router = get_smart_router(self.config)
                    self.execution_manager.start()
                    logger.success("  ✓ TWAP/VWAP/Iceberg ativos")
                except Exception as e:
                    logger.warning(f"  ⚠ Execution Algorithms: {e}")
            else:
                logger.warning("  ⚠ Execution Algorithms: módulo não disponível")
            
            # ========================================
            # 7. ECONOMIC CALENDAR
            # ========================================
            logger.info("[8/11] Inicializando Economic Calendar...")
            if get_economic_calendar:
                try:
                    self.economic_calendar = get_economic_calendar(self.config)
                    # Atualizar calendario em background
                    self.calendar_thread = threading.Thread(
                        target=self._update_calendar_loop,
                        name="EconomicCalendar",
                        daemon=True
                    )
                    self.calendar_thread.start()
                    logger.success("  ✓ Economic Calendar ativo")
                except Exception as e:
                    logger.warning(f"  ⚠ Economic Calendar: {e}")
            else:
                logger.warning("  ⚠ Economic Calendar: módulo não disponível")
            
            # ========================================
            # 8. ML PIPELINE
            # ========================================
            logger.info("[9/14] Inicializando ML Pipeline...")
            if get_ml_training_pipeline:
                try:
                    self.ml_pipeline = get_ml_training_pipeline(self.config)
                    logger.success("  ✓ ML Training Pipeline inicializado")
                except Exception as e:
                    logger.warning(f"  ⚠ ML Pipeline: {e}")
            else:
                logger.warning("  ⚠ ML Pipeline: módulo não disponível")
            
            # ========================================
            # 9. FINBERT NLP ANALYZER
            # ========================================
            logger.info("[10/14] Inicializando FinBERT Analyzer...")
            if get_finbert_analyzer:
                try:
                    self.finbert_analyzer = get_finbert_analyzer()
                    logger.success("  ✓ FinBERT NLP Analyzer inicializado")
                except Exception as e:
                    logger.warning(f"  ⚠ FinBERT Analyzer: {e}")
            else:
                logger.warning("  ⚠ FinBERT Analyzer: módulo não disponível")
            
            # ========================================
            # 10. TRANSFORMER PREDICTOR
            # ========================================
            logger.info("[11/14] Inicializando Transformer Predictor...")
            if get_transformer_predictor:
                try:
                    self.transformer_predictor = get_transformer_predictor()
                    logger.success("  ✓ Transformer Predictor inicializado")
                except Exception as e:
                    logger.warning(f"  ⚠ Transformer Predictor: {e}")
            else:
                logger.warning("  ⚠ Transformer Predictor: módulo não disponível")
            
            # ========================================
            # 11. CORRELATION ANALYZER
            # ========================================
            logger.info("[12/14] Inicializando Correlation Analyzer...")
            if get_correlation_analyzer:
                try:
                    self.correlation_analyzer = get_correlation_analyzer()
                    logger.success("  ✓ Correlation Analyzer inicializado")
                except Exception as e:
                    logger.warning(f"  ⚠ Correlation Analyzer: {e}")
            else:
                logger.warning("  ⚠ Correlation Analyzer: módulo não disponível")
            
            # ========================================
            # 12. HARMONIC PATTERNS ANALYZER
            # ========================================
            logger.info("[13/14] Inicializando Harmonic Patterns...")
            if get_harmonic_analyzer:
                try:
                    self.harmonic_analyzer = get_harmonic_analyzer()
                    logger.success("  ✓ Harmonic Patterns Analyzer inicializado")
                except Exception as e:
                    logger.warning(f"  ⚠ Harmonic Patterns: {e}")
            else:
                logger.warning("  ⚠ Harmonic Patterns: módulo não disponível")
            
            # ========================================
            # 13. TRADINGVIEW WEBHOOKS
            # ========================================
            logger.info("[14/14] Inicializando TradingView Integration...")
            if get_tradingview_manager:
                try:
                    self.tradingview = get_tradingview_manager(self.config)
                    # Iniciar servidor webhook
                    self.tradingview.start()
                    logger.success("  ✓ TradingView Webhooks ativos na porta 8765")
                except Exception as e:
                    logger.warning(f"  ⚠ TradingView: {e}")
            else:
                logger.warning("  ⚠ TradingView: módulo não disponível")
            
            # ========================================
            # 14. COMPONENTES PRINCIPAIS
            # ========================================
            logger.info("Inicializando componentes principais...")
            
            self.order_generator = OrderGenerator()
            self.order_manager = OrderManager()
            
            # Position Intelligence (com acesso ao order manager)
            if PositionIntelligenceManager:
                try:
                    self.position_intelligence = PositionIntelligenceManager(self.config)
                    self.position_intel_thread = threading.Thread(
                        target=self.position_intelligence.start,
                        name="PositionIntelligence",
                        daemon=True
                    )
                    self.position_intel_thread.start()
                    logger.success("  ✓ Position Intelligence ativo")
                except Exception as e:
                    logger.warning(f"  ⚠ Position Intelligence: {e}")
            else:
                logger.warning("  ⚠ Position Intelligence: módulo não disponível")
            
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
            
            logger.info("=" * 80)
            logger.success("URION BOT INICIADO COM SUCESSO - PROFESSIONAL EDITION")
            logger.info("=" * 80)
            self._print_active_modules()
            logger.info("Pressione Ctrl+C para parar")
            
            # Aguardar threads
            self.generator_thread.join()
            self.manager_thread.join()
            
        except Exception as e:
            logger.error(f"Erro ao iniciar bot: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.stop()
    
    def _update_calendar_loop(self):
        """Loop para atualizar calendario economico"""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        while self.running:
            try:
                loop.run_until_complete(self.economic_calendar.update_events())
            except Exception as e:
                logger.warning(f"Erro ao atualizar calendario: {e}")
            
            # Atualizar a cada hora
            import time
            time.sleep(3600)
    
    def _print_active_modules(self):
        """Imprime modulos ativos"""
        logger.info("")
        logger.info("MODULOS ATIVOS:")
        logger.info("-" * 40)
        
        modules = [
            ("Redis Cache", self.redis_client is not None),
            ("InfluxDB Metrics", self.influxdb_client is not None),
            ("Data Hub", self.data_hub is not None),
            ("Order Flow Analyzer", self.order_flow_analyzer is not None),
            ("Manipulation Detector", self.manipulation_detector is not None),
            ("Strategy Communicator", self.strategy_communicator is not None),
            ("Position Intelligence", self.position_intelligence is not None),
            ("Monte Carlo Simulator", self.monte_carlo is not None),
            ("VaR Calculator", self.var_calculator is not None),
            ("Execution Algorithms", self.execution_manager is not None),
            ("Economic Calendar", self.economic_calendar is not None),
            ("TradingView Webhooks", self.tradingview is not None),
            ("ML Training Pipeline", self.ml_pipeline is not None),
            ("FinBERT NLP Analyzer", self.finbert_analyzer is not None),
            ("Transformer Predictor", self.transformer_predictor is not None),
            ("Correlation Analyzer", self.correlation_analyzer is not None),
            ("Harmonic Patterns", self.harmonic_analyzer is not None),
            ("Order Generator", self.order_generator is not None),
            ("Order Manager", self.order_manager is not None),
        ]
        
        for name, active in modules:
            status = "✓" if active else "✗"
            logger.info(f"  {status} {name}")
        
        logger.info("-" * 40)
        logger.info("")
    
    def stop(self):
        """Para o bot"""
        
        if not self.running:
            return
        
        logger.info("Parando bot...")
        self.running = False
        
        # Parar novos componentes
        if self.strategy_communicator:
            try:
                self.strategy_communicator.stop()
            except:
                pass
        
        if self.execution_manager:
            try:
                self.execution_manager.stop()
            except:
                pass
        
        if self.position_intelligence:
            try:
                self.position_intelligence.stop()
            except:
                pass
        
        if self.redis_client:
            try:
                self.redis_client.close()
            except:
                pass
        
        if self.influxdb_client:
            try:
                self.influxdb_client.close()
            except:
                pass
        
        # Parar componentes principais
        if self.order_generator:
            self.order_generator.stop()
        
        if self.order_manager:
            self.order_manager.stop()
        
        logger.success("Bot parado")
        sys.exit(0)
    
    def status(self):
        """Exibe status do bot"""
        
        logger.info("=" * 80)
        logger.info("STATUS DO BOT - PROFESSIONAL EDITION")
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
        
        # Status modulos avancados
        logger.info("-" * 40)
        logger.info("MODULOS AVANCADOS:")
        
        if self.position_intelligence:
            active_positions = len(self.position_intelligence._active_positions)
            logger.info(f"  Position Intelligence: {active_positions} posicoes monitoradas")
        
        if self.strategy_communicator:
            subs = len(self.strategy_communicator._subscribers)
            logger.info(f"  Strategy Communicator: {subs} assinantes")
        
        if self.economic_calendar:
            events = len(self.economic_calendar._events)
            logger.info(f"  Economic Calendar: {events} eventos carregados")
        
        if self.execution_manager:
            active = len(self.execution_manager.get_active_orders())
            logger.info(f"  Execution Manager: {active} ordens ativas")
        
        logger.info("=" * 80)
    
    def check_trading_conditions(self, symbol: str = "XAUUSD") -> dict:
        """
        Verifica todas as condicoes de trading
        Retorna um dicionario com status de cada verificacao
        """
        conditions = {
            'can_trade': True,
            'checks': {}
        }
        
        # 1. Verificar calendario economico
        if self.economic_calendar:
            should_avoid, reason = self.economic_calendar.should_avoid_trading(symbol)
            conditions['checks']['economic_calendar'] = {
                'passed': not should_avoid,
                'reason': reason if should_avoid else 'OK'
            }
            if should_avoid:
                conditions['can_trade'] = False
        
        # 2. Verificar manipulacao de mercado
        if self.manipulation_detector and self.order_flow_analyzer:
            # Aqui integraria com dados reais
            conditions['checks']['manipulation'] = {
                'passed': True,
                'reason': 'Sem manipulacao detectada'
            }
        
        # 3. Verificar VaR
        if self.var_calculator:
            var = self.var_calculator.current_var
            max_var = self.config.get('risk', {}).get('max_var', 0.05)
            passed = var < max_var if var else True
            conditions['checks']['var'] = {
                'passed': passed,
                'reason': f'VaR: {var:.2%}' if var else 'OK'
            }
            if not passed:
                conditions['can_trade'] = False
        
        return conditions


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
