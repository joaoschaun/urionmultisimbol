"""
Script de teste para Telegram
Testa envio síncrono de mensagens
"""
import asyncio
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
from loguru import logger

# Load environment
load_dotenv('.env')

# Configure logger
logger.remove()
logger.add(sys.stderr, level="DEBUG")

async def test_telegram_async():
    """Teste ASYNC do Telegram"""
    from notifications.telegram_bot import TelegramNotifier
    
    logger.info("🧪 Testando Telegram (ASYNC)...")
    
    telegram = TelegramNotifier()
    
    if not telegram.enabled:
        logger.error("❌ Telegram não está habilitado!")
        logger.error(f"Token: {os.getenv('TELEGRAM_BOT_TOKEN')[:20]}...")
        logger.error(f"Chat ID: {os.getenv('TELEGRAM_CHAT_ID')}")
        return False
    
    logger.info("✅ Telegram habilitado")
    logger.info(f"Token: {telegram.bot_token[:20]}...")
    logger.info(f"Chat ID: {telegram.chat_id}")
    
    # Testar envio ASYNC
    logger.info("Enviando mensagem de teste (ASYNC)...")
    try:
        await telegram.send_message(
            "🧪 TESTE DE NOTIFICAÇÃO\n\n"
            "✅ Bot Urion conectado!\n"
            "📊 Sistema operacional\n"
            "🤖 Telegram funcionando"
        )
        logger.success("✅ Mensagem ASYNC enviada com sucesso!")
        return True
    except Exception as e:
        logger.exception(f"❌ Erro ao enviar mensagem ASYNC: {e}")
        return False

def test_telegram_sync():
    """Teste SYNC do Telegram"""
    from notifications.telegram_bot import TelegramNotifier
    
    logger.info("\n🧪 Testando Telegram (SYNC)...")
    
    telegram = TelegramNotifier()
    
    if not telegram.enabled:
        logger.error("❌ Telegram não está habilitado!")
        return False
    
    logger.info("✅ Telegram habilitado")
    
    # Testar envio SYNC
    logger.info("Enviando mensagem de teste (SYNC)...")
    try:
        telegram.send_message_sync(
            "🧪 TESTE SÍNCRONO\n\n"
            "✅ Método send_message_sync() funcionando!\n"
            "📊 Notificações operacionais\n"
            "🎯 Sistema 100%"
        )
        logger.success("✅ Mensagem SYNC enviada com sucesso!")
        return True
    except Exception as e:
        logger.exception(f"❌ Erro ao enviar mensagem SYNC: {e}")
        return False

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("TESTE DO TELEGRAM BOT")
    logger.info("=" * 60)
    
    # Teste 1: ASYNC
    result_async = asyncio.run(test_telegram_async())
    
    # Teste 2: SYNC
    result_sync = test_telegram_sync()
    
    # Resultado
    logger.info("\n" + "=" * 60)
    logger.info("RESULTADO DOS TESTES")
    logger.info("=" * 60)
    logger.info(f"Teste ASYNC: {'✅ PASSOU' if result_async else '❌ FALHOU'}")
    logger.info(f"Teste SYNC: {'✅ PASSOU' if result_sync else '❌ FALHOU'}")
    
    if result_async and result_sync:
        logger.success("\n✅ TELEGRAM 100% FUNCIONAL!")
        logger.info("Verifique seu Telegram para ver as 2 mensagens de teste")
    else:
        logger.error("\n❌ TELEGRAM COM PROBLEMAS!")
        logger.info("Verifique:")
        logger.info("1. Token do bot está correto?")
        logger.info("2. Chat ID está correto?")
        logger.info("3. Você iniciou conversa com o bot (/start)?")
