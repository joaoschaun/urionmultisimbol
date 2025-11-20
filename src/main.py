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
from core.mt5_connector import MT5Connector
from database.strategy_stats import StrategyStatsDB
from order_generator import OrderGenerator
from order_manager import OrderManager
from notifications.telegram_bot import TelegramNotifier
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
    
    logger.info("=" * 80)
    logger.info("URION TRADING BOT - VIRTUS INVESTIMENTOS")
    logger.info("=" * 80)
    logger.info(f"Mode: {args.mode}")
    logger.info(f"Environment: {config.get('ENVIRONMENT', 'production')}")
    
    # Initialize MT5 and Database for Telegram commands
    mt5 = MT5Connector(config)
    stats_db = StrategyStatsDB()
    
    # Initialize Telegram notifications with command support
    telegram = TelegramNotifier(config, mt5=mt5, stats_db=stats_db)
    telegram.send_message_sync("🚀 Urion Trading Bot iniciado!")
    
    try:
        if args.mode == 'full':
            # Run both generator and manager in separate threads
            logger.info("Starting in FULL mode (Generator + Manager)")
            
            generator = OrderGenerator(config=config, telegram=telegram)
            manager = OrderManager(config=config, telegram=telegram)
            
            # Start OrderManager in separate thread
            manager_thread = threading.Thread(
                target=manager.start,
                name="OrderManager-Thread",
                daemon=True
            )
            manager_thread.start()
            logger.success("✅ OrderManager iniciado em thread separada")
            
            # Start OrderGenerator in main thread (blocks)
            generator.start()
            
        elif args.mode == 'generator':
            # Run only order generator
            logger.info("Starting in GENERATOR mode")
            
            generator = OrderGenerator(config=config, telegram=telegram)
            generator.start()
            
        elif args.mode == 'manager':
            # Run only order manager
            logger.info("Starting in MANAGER mode")
            
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
