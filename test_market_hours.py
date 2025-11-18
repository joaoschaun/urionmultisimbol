"""
Teste do sistema de horários de mercado
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.config_manager import ConfigManager
from core.market_hours import MarketHoursManager
from loguru import logger

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO")

def main():
    logger.info("=" * 70)
    logger.info("TESTE DO SISTEMA DE HORÁRIOS DE MERCADO")
    logger.info("=" * 70)
    
    # Carregar config
    config_manager = ConfigManager()
    config = config_manager.config
    
    # Inicializar market hours
    market_hours = MarketHoursManager(config)
    
    # Mostrar status atual
    market_hours.log_market_status()
    
    # Mostrar resumo
    status = market_hours.get_market_status()
    
    print()
    logger.info("RESUMO:")
    logger.info(f"  Mercado Aberto: {'✅ SIM' if status['is_open'] else '❌ NÃO'}")
    logger.info(f"  Pode Abrir Posições: {'✅ SIM' if status['can_open_positions'] else '❌ NÃO'}")
    
    if not status['can_open_positions']:
        logger.warning(f"  Motivo: {status['reason']}")
    
    if status['should_close_positions']:
        logger.error("  ⚠️  ATENÇÃO: DEVE FECHAR POSIÇÕES!")
    
    print()
    logger.info("=" * 70)
    logger.info("HORÁRIOS CONFIGURADOS:")
    logger.info("=" * 70)
    logger.info("📅 Abertura Semanal:")
    logger.info("   Domingo às 18:30 UTC")
    logger.info("   Não operar nos primeiros 15 minutos")
    logger.info("")
    logger.info("📅 Fechamento Semanal:")
    logger.info("   Sexta-feira às 16:30 UTC")
    logger.info("   Fechar todas as posições 30 min antes (16:00)")
    logger.info("")
    logger.info("🔒 Janela de Segurança:")
    logger.info("   Abertura: 15 minutos após open")
    logger.info("   Fechamento: 30 minutos antes do close")
    logger.info("=" * 70)

if __name__ == "__main__":
    main()
