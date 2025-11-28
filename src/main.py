"""
Urion Trading Bot - Main Entry Point
Virtus Investimentos
"""
import sys
import argparse
import threading
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager
from core.logger import setup_logger
from core.symbol_manager import SymbolManager  # 🆕 Multi-símbolo
from core.auto_backup import get_auto_backup  # 🆕 Backup automático
from notifications.telegram_bot import TelegramNotifier
from notifications.news_notifier import NewsNotifier  # 🆕 Notificações de notícias
from analysis.news_analyzer import NewsAnalyzer  # 🆕 Análise de notícias
from monitoring.prometheus_metrics import get_metrics
from reporting.daily_report import DailyReportGenerator
from reporting.weekly_report import WeeklyReportGenerator
from reporting.monthly_report import MonthlyReportGenerator
from loguru import logger


def main():
    """Main entry point for Urion Trading Bot"""
    
    parser = argparse.ArgumentParser(description='Urion Trading Bot')
    parser.add_argument(
        '--mode',
        type=str,
        choices=['full', 'generator', 'manager'],
        default='full',
        help='Execution mode: full (both), generator only, or manager only'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config/config.yaml',
        help='Path to configuration file'
    )
    
    args = parser.parse_args()
    
    # Initialize configuration
    config_manager = ConfigManager(args.config)
    config = config_manager.config
    
    # Setup logger
    setup_logger(config)
    
    logger.info("=" * 80)
    logger.info("URION TRADING BOT - VIRTUS INVESTIMENTOS")
    logger.info("=" * 80)
    logger.info(f"Mode: {args.mode}")
    logger.info(f"Environment: {config.get('ENVIRONMENT', 'production')}")
    
    # Initialize Prometheus metrics
    _ = get_metrics()  # Inicia servidor HTTP
    logger.success(
        "✅ Prometheus metrics disponíveis em "
        "http://localhost:8000/metrics"
    )
    
    # Initialize Telegram (SymbolManager cria MT5/DB internamente)
    telegram = TelegramNotifier(config)
    telegram.send_message_sync("🚀 Urion Trading Bot iniciado!")
    
    # 🆕 Initialize News Notifier (notificações em português)
    news_analyzer = NewsAnalyzer(config)
    news_notifier = NewsNotifier(news_analyzer, telegram, config)
    news_notifier.start()
    logger.success("✅ NewsNotifier iniciado - Notícias em português ativas")
    
    # Initialize Report Generators
    # (usam SymbolManager.stats_db depois)
    from database.strategy_stats import StrategyStatsDB
    stats_db = StrategyStatsDB()
    
    daily_report = DailyReportGenerator(stats_db, telegram)
    weekly_report = WeeklyReportGenerator(stats_db, telegram)
    monthly_report = MonthlyReportGenerator(stats_db, telegram)
    
    # Schedule reports
    import schedule
    
    # Relatório diário às 23:59
    def generate_daily():
        try:
            report = daily_report.generate_report()
            daily_report.send_report(report)
        except Exception as e:
            logger.error(f"Erro ao gerar relatório diário: {e}")
    
    schedule.every().day.at("23:59").do(generate_daily)
    
    # Relatório semanal domingo 23:59
    def generate_weekly():
        try:
            report = weekly_report.generate_report()
            weekly_report.send_report(report)
        except Exception as e:
            logger.error(f"Erro ao gerar relatório semanal: {e}")
    
    schedule.every().sunday.at("23:59").do(generate_weekly)
    
    # Relatório mensal último dia do mês 23:59
    def generate_monthly():
        try:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            # Verificar se é último dia do mês
            import calendar
            last_day = calendar.monthrange(now.year, now.month)[1]
            if now.day == last_day:
                report = monthly_report.generate_report()
                monthly_report.send_report(report)
        except Exception as e:
            logger.error(f"Erro ao gerar relatório mensal: {e}")
    
    schedule.every().day.at("23:59").do(generate_monthly)
    
    logger.success("✅ Relatórios agendados (diário, semanal, mensal)")
    
    # 🆕 Inicializar backup automático
    auto_backup = get_auto_backup(enabled=True)
    auto_backup.start_scheduler()
    logger.success("✅ Backup automático ativado (diário às 00:00)")
    
    # Start schedule checker thread
    def run_schedule():
        while True:
            schedule.run_pending()
            import time
            time.sleep(60)  # Check every minute
    
    schedule_thread = threading.Thread(target=run_schedule, daemon=True)
    schedule_thread.start()
    logger.success("✅ Thread de agendamento iniciada")
    
    try:
        if args.mode == 'full':
            # ════════════════════════════════════════════════════════
            # 🌍 MODO MULTI-SÍMBOLO (NOVA ARQUITETURA)
            # ════════════════════════════════════════════════════════
            logger.info("Starting in FULL mode (Multi-Symbol)")
            
            # Criar SymbolManager (gerencia XAUUSD, EURUSD, etc)
            symbol_manager = SymbolManager(config)
            
            # Iniciar todos os símbolos ativos
            symbol_manager.start_all()
            
            # Manter thread principal viva
            logger.info("✅ SymbolManager ativo. Aguardando sinais...")
            import signal
            
            def signal_handler(sig, frame):
                logger.info("🛑 Sinal de interrupção recebido")
                symbol_manager.stop_all()
                raise KeyboardInterrupt
            
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            
            # Loop infinito (aguarda Ctrl+C)
            while True:
                import time
                time.sleep(60)  # Check a cada minuto
            
        elif args.mode == 'generator':
            # Modo legado (compatibilidade)
            logger.warning(
                "⚠️ Modo 'generator' está deprecated. "
                "Use 'full' com multi-symbol."
            )
            from order_generator import OrderGenerator
            generator = OrderGenerator(config=config, telegram=telegram)
            generator.start()
            
        elif args.mode == 'manager':
            # Modo legado (compatibilidade)
            logger.warning(
                "⚠️ Modo 'manager' está deprecated. "
                "Use 'full' com multi-symbol."
            )
            from order_manager import OrderManager
            manager = OrderManager(config=config, telegram=telegram)
            manager.start()
            
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
        telegram.send_message_sync("⏹️ Urion Trading Bot encerrado pelo usuário")
        
    except Exception as e:
        logger.exception(f"Critical error: {e}")
        telegram.send_message_sync(f"❌ ERRO CRÍTICO: {e}")
        
    finally:
        logger.info("Urion Trading Bot stopped")
        telegram.send_message_sync("🛑 Urion Trading Bot encerrado")


if __name__ == "__main__":
    main()
