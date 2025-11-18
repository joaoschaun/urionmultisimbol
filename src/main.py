"""
Urion Trading Bot - Main Entry Point
Virtus Investimentos
"""
import sys
import argparse
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager
from core.logger import setup_logger
from order_generator import OrderGenerator
from order_manager import OrderManager
from notifications.telegram_bot import TelegramNotifier


async def main():
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
    config = ConfigManager(args.config)
    logger = setup_logger(config)
    
    logger.info("=" * 80)
    logger.info("URION TRADING BOT - VIRTUS INVESTIMENTOS")
    logger.info("=" * 80)
    logger.info(f"Mode: {args.mode}")
    logger.info(f"Environment: {config.get('ENVIRONMENT', 'production')}")
    
    # Initialize Telegram notifications
    telegram = TelegramNotifier(config)
    await telegram.send_message("🚀 Urion Trading Bot iniciado!")
    
    try:
        if args.mode == 'full':
            # Run both generator and manager
            logger.info("Starting in FULL mode (Generator + Manager)")
            
            generator = OrderGenerator(config, telegram)
            manager = OrderManager(config, telegram)
            
            await asyncio.gather(
                generator.start(),
                manager.start()
            )
            
        elif args.mode == 'generator':
            # Run only order generator
            logger.info("Starting in GENERATOR mode")
            
            generator = OrderGenerator(config, telegram)
            await generator.start()
            
        elif args.mode == 'manager':
            # Run only order manager
            logger.info("Starting in MANAGER mode")
            
            manager = OrderManager(config, telegram)
            await manager.start()
            
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
        await telegram.send_message("⏹️ Urion Trading Bot encerrado pelo usuário")
        
    except Exception as e:
        logger.exception(f"Critical error: {e}")
        await telegram.send_message(f"❌ ERRO CRÍTICO: {e}")
        
    finally:
        logger.info("Urion Trading Bot stopped")
        await telegram.send_message("🛑 Urion Trading Bot encerrado")


if __name__ == "__main__":
    asyncio.run(main())
