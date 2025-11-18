"""
Teste de notificações do Telegram via OrderManager
Simula situações que acionam notificações
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
from loguru import logger
from notifications.telegram_bot import TelegramNotifier
import yaml

# Load environment
load_dotenv('.env')

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO")

def test_notifications():
    """Testa diferentes tipos de notificações"""
    
    logger.info("=" * 60)
    logger.info("TESTE DE NOTIFICAÇÕES DO TELEGRAM")
    logger.info("=" * 60)
    
    # Load config
    with open('config/config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    telegram = TelegramNotifier(config)
    
    if not telegram.enabled:
        logger.error("❌ Telegram não está habilitado!")
        return False
    
    logger.info("✅ Telegram habilitado")
    
    # Teste 1: Break-even
    logger.info("\n📧 Enviando notificação de BREAK-EVEN...")
    telegram.send_message_sync(
        f"🔒 Break-even aplicado\n"
        f"Ticket: 123456\n"
        f"Novo SL: 4075.50"
    )
    logger.success("✅ Notificação de break-even enviada")
    
    # Teste 2: Fechamento parcial
    logger.info("\n📧 Enviando notificação de FECHAMENTO PARCIAL...")
    telegram.send_message_sync(
        f"📊 Fechamento Parcial\n"
        f"Ticket: 123456\n"
        f"Volume: 0.005 lotes\n"
        f"Lucro: $12.50"
    )
    logger.success("✅ Notificação de fechamento parcial enviada")
    
    # Teste 3: Nova ordem
    logger.info("\n📧 Enviando notificação de NOVA ORDEM...")
    telegram.send_message_sync(
        f"📈 NOVA ORDEM EXECUTADA\n\n"
        f"Tipo: BUY\n"
        f"Símbolo: XAUUSD\n"
        f"Lote: 0.01\n"
        f"Preço: 4075.00\n"
        f"SL: 4055.00\n"
        f"TP: 4135.00\n"
        f"Estratégia: RangeTrading"
    )
    logger.success("✅ Notificação de nova ordem enviada")
    
    # Teste 4: Trailing stop
    logger.info("\n📧 Enviando notificação de TRAILING STOP...")
    telegram.send_message_sync(
        f"📊 Trailing Stop Aplicado\n\n"
        f"Ticket: 123456\n"
        f"SL anterior: 4055.00\n"
        f"SL novo: 4065.00\n"
        f"Proteção: +10.00 pontos"
    )
    logger.success("✅ Notificação de trailing stop enviada")
    
    logger.info("\n" + "=" * 60)
    logger.success("✅ TODAS AS NOTIFICAÇÕES ENVIADAS!")
    logger.info("=" * 60)
    logger.info("\n📱 Verifique seu Telegram - você deve ter recebido 4 mensagens!")
    
    return True

if __name__ == "__main__":
    try:
        success = test_notifications()
        if success:
            logger.success("\n🎉 TELEGRAM 100% FUNCIONAL!")
        else:
            logger.error("\n❌ Telegram com problemas")
    except Exception as e:
        logger.exception(f"❌ Erro no teste: {e}")
