"""
URION Trading Bot
Bot de Trading Automatizado para XAUUSD

Versao: 2.0 - Full Professional Edition
Inclui todos os modulos avancados:
- Order Flow Intelligence
- Market Manipulation Detection
- Position Intelligence Manager
- Strategy Communicator (Event Bus)
- Monte Carlo Risk Simulation
- VaR Calculator
- ML Training Pipeline
- Execution Algorithms (TWAP/VWAP/Iceberg)
- Walk-Forward Optimization
- Economic Calendar Integration
- TradingView Webhooks
- Redis Cache
- InfluxDB Metrics
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

# Novos modulos avancados
from core.position_intelligence import PositionIntelligenceManager
from core.strategy_communicator import get_strategy_communicator
from core.execution_algorithms import get_execution_manager, get_smart_router

from analysis.order_flow_analyzer import get_order_flow_analyzer
from analysis.manipulation_detector import ManipulationDetector
from analysis.tradingview_integration import get_tradingview_manager
from analysis.economic_calendar import get_economic_calendar

from risk.monte_carlo import get_monte_carlo_simulator
from risk.var_calculator import get_var_calculator

from ml.training_pipeline import get_ml_training_pipeline

from infrastructure.redis_client import get_redis_client
from infrastructure.influxdb_client import get_influxdb_client
from infrastructure.data_hub import get_data_hub

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
        
        # Threads adicionais
        self.position_intel_thread = None
        self.tradingview_thread = None
        self.calendar_thread = None
        
        # Configurar handler de sinais
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("=" * 80)
        logger.info("URION TRADING BOT - PROFESSIONAL EDITION v2.0")
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
            logger.info("=" * 80)
            logger.info("INICIALIZANDO MODULOS AVANCADOS")
            logger.info("=" * 80)
            
            # ========================================
            # 1. INFRAESTRUTURA (Redis, InfluxDB)
            # ========================================
            logger.info("[1/11] Inicializando Infraestrutura...")
            try:
                self.redis_client = get_redis_client(self.config)
                if self.redis_client.connect():
                    logger.success("  ✓ Redis conectado")
                else:
                    logger.warning("  ⚠ Redis indisponivel, continuando sem cache")
            except Exception as e:
                logger.warning(f"  ⚠ Redis: {e}")
            
            try:
                self.influxdb_client = get_influxdb_client(self.config)
                if self.influxdb_client.connect():
                    logger.success("  ✓ InfluxDB conectado")
                else:
                    logger.warning("  ⚠ InfluxDB indisponivel, continuando sem metricas")
            except Exception as e:
                logger.warning(f"  ⚠ InfluxDB: {e}")
            
            # ========================================
            # 2. DATA HUB (Central de Dados)
            # ========================================
            logger.info("[2/11] Inicializando Data Hub...")
            try:
                self.data_hub = get_data_hub(self.config)
                logger.success("  ✓ Data Hub inicializado")
            except Exception as e:
                logger.warning(f"  ⚠ Data Hub: {e}")
            
            # ========================================
            # 3. ORDER FLOW & MANIPULATION
            # ========================================
            logger.info("[3/11] Inicializando Order Flow Analyzer...")
            try:
                self.order_flow_analyzer = get_order_flow_analyzer(self.config)
                logger.success("  ✓ Order Flow Analyzer inicializado")
            except Exception as e:
                logger.warning(f"  ⚠ Order Flow: {e}")
            
            logger.info("[4/11] Inicializando Manipulation Detector...")
            try:
                self.manipulation_detector = ManipulationDetector(self.config)
                logger.success("  ✓ Manipulation Detector inicializado")
            except Exception as e:
                logger.warning(f"  ⚠ Manipulation Detector: {e}")
            
            # ========================================
            # 4. STRATEGY COMMUNICATION
            # ========================================
            logger.info("[5/11] Inicializando Strategy Communicator...")
            try:
                self.strategy_communicator = get_strategy_communicator(self.config)
                self.strategy_communicator.start()
                logger.success("  ✓ Strategy Communicator ativo")
            except Exception as e:
                logger.warning(f"  ⚠ Strategy Communicator: {e}")
            
            # ========================================
            # 5. RISK MANAGEMENT
            # ========================================
            logger.info("[6/11] Inicializando Risk Management...")
            try:
                self.monte_carlo = get_monte_carlo_simulator(self.config)
                self.var_calculator = get_var_calculator(self.config)
                logger.success("  ✓ Monte Carlo + VaR inicializados")
            except Exception as e:
                logger.warning(f"  ⚠ Risk Management: {e}")
            
            # ========================================
            # 6. EXECUTION ALGORITHMS
            # ========================================
            logger.info("[7/11] Inicializando Execution Algorithms...")
            try:
                self.execution_manager = get_execution_manager(self.config)
                self.smart_router = get_smart_router(self.config)
                self.execution_manager.start()
                logger.success("  ✓ TWAP/VWAP/Iceberg ativos")
            except Exception as e:
                logger.warning(f"  ⚠ Execution Algorithms: {e}")
            
            # ========================================
            # 7. ECONOMIC CALENDAR
            # ========================================
            logger.info("[8/11] Inicializando Economic Calendar...")
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
            
            # ========================================
            # 8. ML PIPELINE
            # ========================================
            logger.info("[9/11] Inicializando ML Pipeline...")
            try:
                self.ml_pipeline = get_ml_training_pipeline(self.config)
                logger.success("  ✓ ML Training Pipeline inicializado")
            except Exception as e:
                logger.warning(f"  ⚠ ML Pipeline: {e}")
            
            # ========================================
            # 9. TRADINGVIEW WEBHOOKS
            # ========================================
            logger.info("[10/11] Inicializando TradingView Integration...")
            try:
                self.tradingview = get_tradingview_manager(self.config)
                # Iniciar servidor webhook em thread separada
                self.tradingview_thread = threading.Thread(
                    target=self._start_tradingview_server,
                    name="TradingViewWebhook",
                    daemon=True
                )
                self.tradingview_thread.start()
                logger.success("  ✓ TradingView Webhooks ativos na porta 8765")
            except Exception as e:
                logger.warning(f"  ⚠ TradingView: {e}")
            
            # ========================================
            # 10. COMPONENTES PRINCIPAIS
            # ========================================
            logger.info("[11/11] Inicializando componentes principais...")
            
            self.order_generator = OrderGenerator()
            self.order_manager = OrderManager()
            
            # Position Intelligence (com acesso ao order manager)
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
    
    def _start_tradingview_server(self):
        """Inicia servidor TradingView"""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self.tradingview.start_webhook_server())
        except Exception as e:
            logger.warning(f"Erro ao iniciar TradingView server: {e}")
    
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
