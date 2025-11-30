# -*- coding: utf-8 -*-
"""
Urion Trading Bot - ELITE v2.0
==============================
Sistema de Trading Automatizado com ML e Módulos Avançados

Módulos Integrados:
- Machine Learning (XGBoost, TensorFlow, PyTorch)
- Partial Take Profit Multinível
- Config Hot Reload
- Trade Journal
- Market Regime Detection
- REST API + WebSocket
- Backtesting Engine
- Dashboard de Métricas
"""

import sys
import os
import argparse
import threading
import asyncio
from pathlib import Path
from datetime import datetime, timezone
import signal

# Configurar ambiente ANTES de qualquer import
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'max_split_size_mb:512'
os.environ['OMP_NUM_THREADS'] = '4'

import warnings
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=UserWarning)

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent))

# ============================================================================
# IMPORTS CORE
# ============================================================================
from core.config_manager import ConfigManager
from core.logger import setup_logger
from core.symbol_manager import SymbolManager
from core.auto_backup import get_auto_backup
from core.process_manager import ProcessManager
from notifications.telegram_bot import TelegramNotifier
from notifications.telegram_professional import TelegramProfessional, get_telegram
from notifications.news_notifier import NewsNotifier
from analysis.news_analyzer import NewsAnalyzer
from monitoring.prometheus_metrics import get_metrics
from reporting.daily_report import DailyReportGenerator
from reporting.weekly_report import WeeklyReportGenerator
from reporting.monthly_report import MonthlyReportGenerator
from database.strategy_stats import StrategyStatsDB
from loguru import logger

# ============================================================================
# VERIFICAR DEPENDÊNCIAS
# ============================================================================
DEPS = {
    'xgboost': False,
    'sklearn': False,
    'tensorflow': False,
    'torch': False,
    'fastapi': False,
    'watchdog': False,
    'optuna': False
}

def check_dependencies():
    """Verifica dependências disponíveis"""
    global DEPS
    
    try:
        import xgboost
        DEPS['xgboost'] = True
    except ImportError:
        pass
    
    try:
        import sklearn
        DEPS['sklearn'] = True
    except ImportError:
        pass
    
    try:
        import tensorflow
        DEPS['tensorflow'] = True
    except ImportError:
        pass
    
    try:
        import torch
        DEPS['torch'] = True
    except ImportError:
        pass
    
    try:
        import fastapi
        DEPS['fastapi'] = True
    except ImportError:
        pass
    
    try:
        import watchdog
        DEPS['watchdog'] = True
    except ImportError:
        pass
    
    try:
        import optuna
        DEPS['optuna'] = True
    except ImportError:
        pass
    
    return DEPS

DEPS = check_dependencies()

# ============================================================================
# IMPORTS CONDICIONAIS - NOVOS MÓDULOS
# ============================================================================

# ML Integration
ML_MANAGER = None
ELITE_MODE = False

try:
    if DEPS['xgboost'] and DEPS['sklearn']:
        from ml.ml_integration import get_ml_manager
        ELITE_MODE = True
except Exception as e:
    pass

# Partial TP Manager
PARTIAL_TP_MANAGER = None

# Config Hot Reload
CONFIG_RELOADER = None

# Trade Journal
TRADE_JOURNAL = None

# Market Regime Detector
REGIME_DETECTOR = None

# API Server
API_SERVER = None

# Dashboard
DASHBOARD = None

# Advanced Metrics
ADVANCED_METRICS = None


# ============================================================================
# FUNÇÕES DE INICIALIZAÇÃO
# ============================================================================

async def initialize_ml_system(config: dict) -> bool:
    """Inicializa sistema de ML"""
    global ML_MANAGER
    
    elite_config = config.get('elite', {})
    if not elite_config.get('enabled', False):
        return False
    
    if not ELITE_MODE:
        return False
    
    try:
        ML_MANAGER = get_ml_manager(config, elite_mode=True)
        load_results = await ML_MANAGER.load_models('data/ml')
        
        for model, success in load_results.items():
            status = "carregado" if success else "será treinado"
            logger.info(f"  Modelo {model}: {status}")
        
        return True
    
    except Exception as e:
        logger.error(f"Erro ML: {e}")
        return False


def initialize_new_modules(config: dict, telegram: TelegramNotifier) -> dict:
    """Inicializa todos os novos módulos v2.0"""
    global PARTIAL_TP_MANAGER, CONFIG_RELOADER, TRADE_JOURNAL
    global REGIME_DETECTOR, API_SERVER, DASHBOARD, ADVANCED_METRICS
    
    modules = {}
    
    # 1. Partial TP Manager
    try:
        from core.partial_tp_manager import PartialTPManager
        partial_config = config.get('partial_tp', {})
        if partial_config.get('enabled', True):
            PARTIAL_TP_MANAGER = PartialTPManager(config)
            modules['partial_tp'] = PARTIAL_TP_MANAGER
            logger.success("✓ Partial TP Manager")
    except Exception as e:
        logger.warning(f"✗ Partial TP: {e}")
    
    # 2. Config Hot Reload
    try:
        if DEPS['watchdog']:
            from core.config_hot_reload import ConfigHotReload
            config_mgr = ConfigManager(config.get('_config_path', 'config/config.yaml'))
            
            CONFIG_RELOADER = ConfigHotReload(
                config_manager=config_mgr,
                check_interval=5.0,
                auto_reload=True
            )
            CONFIG_RELOADER.start()
            modules['config_reload'] = CONFIG_RELOADER
            logger.success("✓ Config Hot Reload")
    except Exception as e:
        logger.warning(f"✗ Config Reload: {e}")
    
    # 3. Trade Journal
    try:
        from core.trade_journal import TradeJournal
        TRADE_JOURNAL = TradeJournal(db_path='data/trade_journal.db')
        modules['trade_journal'] = TRADE_JOURNAL
        logger.success("✓ Trade Journal")
    except Exception as e:
        logger.warning(f"✗ Trade Journal: {e}")
    
    # 4. Market Regime Detector
    try:
        from analysis.market_regime import MarketRegimeDetector
        REGIME_DETECTOR = MarketRegimeDetector()
        modules['regime_detector'] = REGIME_DETECTOR
        logger.success("✓ Market Regime Detector")
    except Exception as e:
        logger.warning(f"✗ Regime Detector: {e}")
    
    # 5. API Server
    try:
        if DEPS['fastapi']:
            from api.server import APIServer
            api_config = config.get('api', {})
            if api_config.get('enabled', False):
                API_SERVER = APIServer(config)
                api_thread = threading.Thread(
                    target=API_SERVER.run,
                    kwargs={'host': '0.0.0.0', 'port': api_config.get('port', 8080)},
                    daemon=True
                )
                api_thread.start()
                modules['api_server'] = API_SERVER
                port = api_config.get('port', 8080)
                logger.success(f"✓ API Server :{port}")
    except Exception as e:
        logger.warning(f"✗ API Server: {e}")
    
    # 6. Dashboard
    try:
        from monitoring.dashboard import MetricsDashboard
        DASHBOARD = MetricsDashboard(output_dir='reports')
        modules['dashboard'] = DASHBOARD
        logger.success("✓ Dashboard")
    except Exception as e:
        logger.warning(f"✗ Dashboard: {e}")
    
    # 7. Advanced Metrics
    try:
        from core.advanced_metrics import AdvancedMetrics
        ADVANCED_METRICS = AdvancedMetrics()
        modules['advanced_metrics'] = ADVANCED_METRICS
        logger.success("✓ Advanced Metrics")
    except Exception as e:
        logger.warning(f"✗ Advanced Metrics: {e}")
    
    return modules


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Função principal do Urion Bot"""
    
    parser = argparse.ArgumentParser(description='Urion Trading Bot ELITE v2.0')
    parser.add_argument('--mode', type=str, 
                        choices=['full', 'generator', 'manager', 'api'],
                        default='full')
    parser.add_argument('--config', type=str, default='config/config.yaml')
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--no-elite', action='store_true')
    parser.add_argument('--no-api', action='store_true')
    
    args = parser.parse_args()
    
    # Carregar configuração
    config_manager = ConfigManager(args.config)
    config = config_manager.config
    config['_config_path'] = args.config
    
    setup_logger(config)
    
    # Banner
    logger.info("=" * 70)
    logger.info("  URION TRADING BOT - ELITE v2.0")
    logger.info("=" * 70)
    logger.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"  Modo: {args.mode.upper()}")
    logger.info("=" * 70)
    
    # Dependências
    logger.info("\n📦 DEPENDÊNCIAS:")
    for dep, ok in DEPS.items():
        logger.info(f"   {'✓' if ok else '✗'} {dep}")
    
    # Process Manager
    process_mgr = ProcessManager("urion_bot")
    
    if not process_mgr.acquire_lock(force=args.force):
        logger.error("Outra instância rodando. Use --force")
        sys.exit(1)
    
    logger.info("\n🔒 Lock OK")
    
    # Prometheus
    try:
        _ = get_metrics()
        logger.success("📊 Prometheus :8000/metrics")
    except Exception as e:
        logger.warning(f"Prometheus: {e}")
    
    # Telegram - Sistema Profissional
    telegram = TelegramNotifier(config)
    telegram_pro = TelegramProfessional(config)
    
    # Enviar mensagem de inicialização
    telegram_pro.notify_system(
        "BOT INICIADO",
        f"Urion Trading Bot v2.0\nModo: {'Demo' if 'demo' in config.get('mt5', {}).get('server', '').lower() else 'Real'}\nHorário: {datetime.now().strftime('%H:%M:%S')}",
        "success"
    )
    
    # News
    try:
        news_analyzer = NewsAnalyzer(config)
        news_notifier = NewsNotifier(news_analyzer, telegram, config)
        news_notifier.start()
        logger.success("📰 NewsNotifier OK")
    except Exception as e:
        logger.warning(f"News: {e}")
    
    # Relatórios
    stats_db = StrategyStatsDB()
    daily_report = DailyReportGenerator(stats_db, telegram)
    weekly_report = WeeklyReportGenerator(stats_db, telegram)
    monthly_report = MonthlyReportGenerator(stats_db, telegram)
    
    import schedule
    import calendar
    
    schedule.every().day.at("23:59").do(
        lambda: daily_report.send_report(daily_report.generate_report()))
    schedule.every().sunday.at("23:59").do(
        lambda: weekly_report.send_report(weekly_report.generate_report()))
    logger.success("📅 Relatórios agendados")
    
    # Backup
    try:
        auto_backup = get_auto_backup(enabled=True)
        auto_backup.start_scheduler()
        logger.success("💾 Backup OK")
    except:
        pass
    
    # Scheduler thread
    def run_scheduler():
        while True:
            try:
                schedule.run_pending()
            except:
                pass
            import time
            time.sleep(60)
    
    threading.Thread(target=run_scheduler, daemon=True).start()
    
    # ========================================================================
    # MÓDULOS v2.0
    # ========================================================================
    logger.info("\n🔧 MÓDULOS v2.0:")
    logger.info("-" * 40)
    
    modules = {}
    if not args.no_api:
        modules = initialize_new_modules(config, telegram)
    
    active = [k for k, v in modules.items() if v is not None]
    logger.info(f"\n✅ {len(active)} módulos ativos")
    
    symbol_manager = None
    
    # Shutdown
    def shutdown(signum=None, frame=None):
        logger.info("\n🛑 Shutdown...")
        
        if symbol_manager:
            symbol_manager.stop_all()
        
        if ML_MANAGER:
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(ML_MANAGER.save_models('data/ml'))
            except:
                pass
        
        if CONFIG_RELOADER:
            try:
                CONFIG_RELOADER.stop()
            except:
                pass
        
        process_mgr.release_lock()
        logger.success("✅ Shutdown OK!")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    
    # ========================================================================
    # EXECUÇÃO
    # ========================================================================
    try:
        if args.mode == 'full':
            logger.info("\n" + "=" * 70)
            logger.info("  MODO FULL")
            logger.info("=" * 70)
            
            # ML Elite
            if ELITE_MODE and not args.no_elite:
                logger.info("\n🧠 ML Elite...")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                ml_ok = loop.run_until_complete(initialize_ml_system(config))
                
                if ml_ok:
                    logger.success("🧠 ML Elite ATIVO!")
                else:
                    logger.warning("ML modo Standard")
            
            # Symbol Manager
            symbol_manager = SymbolManager(config)
            
            if ML_MANAGER:
                symbol_manager.ml_manager = ML_MANAGER
            
            # Injetar módulos
            if modules.get('partial_tp'):
                symbol_manager.partial_tp_manager = modules['partial_tp']
            if modules.get('trade_journal'):
                symbol_manager.trade_journal = modules['trade_journal']
            if modules.get('regime_detector'):
                symbol_manager.regime_detector = modules['regime_detector']
            if modules.get('advanced_metrics'):
                symbol_manager.advanced_metrics = modules['advanced_metrics']
            
            symbol_manager.start_all()
            
            info = process_mgr.get_process_info()
            logger.info(f"\n📊 PID: {info['pid']}, {info['memory_mb']:.1f} MB")
            
            symbols = [s for s, c in config.get('trading', {}).get('symbols', {}).items() 
                      if c.get('enabled', False)]
            
            logger.success("\n" + "=" * 70)
            logger.success(f"  🚀 URION v2.0 ATIVO - {', '.join(symbols)}")
            logger.success("=" * 70)
            
            telegram.send_message_sync(
                f"🚀 Urion v2.0 Ativo!\n"
                f"📊 {', '.join(symbols)}\n"
                f"🔧 {len(active)} módulos"
            )
            
            while True:
                import time
                time.sleep(60)
                
        elif args.mode == 'generator':
            from order_generator import OrderGenerator
            OrderGenerator(config=config, telegram=telegram).start()
            
        elif args.mode == 'manager':
            from order_manager import OrderManager
            OrderManager(config=config, telegram=telegram).start()
            
        elif args.mode == 'api':
            if not DEPS['fastapi']:
                logger.error("FastAPI não instalado!")
                sys.exit(1)
            
            from api.server import APIServer
            api = APIServer(config)
            port = config.get('api', {}).get('port', 8080)
            api.run(host='0.0.0.0', port=port)
            
    except KeyboardInterrupt:
        shutdown()
        
    except Exception as e:
        logger.exception(f"ERRO: {e}")
        telegram.send_message_sync(f"❌ ERRO: {str(e)[:200]}")
        shutdown()


if __name__ == "__main__":
    main()
