#!/usr/bin/env python3
"""
Diagnóstico completo do sistema Telegram
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

print("\n" + "="*80)
print("DIAGNÓSTICO DO TELEGRAM - URION BOT")
print("="*80 + "\n")

# Teste 1: Credenciais
print("TESTE 1: Verificando credenciais...")
print("-" * 80)

token = os.getenv('TELEGRAM_BOT_TOKEN')
chat_id = os.getenv('TELEGRAM_CHAT_ID')

if token:
    print(f"✅ TELEGRAM_BOT_TOKEN configurado: {token[:15]}...{token[-10:]}")
else:
    print("❌ TELEGRAM_BOT_TOKEN NÃO ENCONTRADO!")
    sys.exit(1)

if chat_id:
    print(f"✅ TELEGRAM_CHAT_ID configurado: {chat_id}")
else:
    print("❌ TELEGRAM_CHAT_ID NÃO ENCONTRADO!")
    sys.exit(1)

print()

# Teste 2: Módulo telegram
print("TESTE 2: Verificando módulo python-telegram-bot...")
print("-" * 80)

try:
    import telegram
    print(f"✅ Módulo telegram instalado: versão {telegram.__version__}")
except ImportError as e:
    print(f"❌ Módulo telegram NÃO instalado!")
    print(f"   Execute: pip install python-telegram-bot")
    sys.exit(1)

print()

# Teste 3: Conexão com Bot
print("TESTE 3: Testando conexão com bot...")
print("-" * 80)

try:
    from telegram import Bot
    import asyncio
    
    async def test_bot_connection():
        bot = Bot(token=token)
        async with bot:
            bot_info = await bot.get_me()
            return bot_info
    
    bot_info = asyncio.run(test_bot_connection())
    print(f"✅ Conectado com sucesso!")
    print(f"   Nome: @{bot_info.username}")
    print(f"   ID: {bot_info.id}")
    print(f"   First name: {bot_info.first_name}")
    
except Exception as e:
    print(f"❌ Erro ao conectar com bot: {e}")
    print(f"   Verifique se o token está correto")
    sys.exit(1)

print()

# Teste 4: Enviar mensagem de teste
print("TESTE 4: Enviando mensagem de teste...")
print("-" * 80)

try:
    from telegram import Bot
    import asyncio
    from datetime import datetime
    
    async def send_test_message():
        bot = Bot(token=token)
        async with bot:
            message = f"""🤖 *TESTE DE NOTIFICAÇÃO - URION BOT*

✅ Sistema de notificações funcionando!

_Horário:_ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Se você recebeu esta mensagem, o Telegram está configurado corretamente.
"""
            result = await bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode='Markdown'
            )
            return result
    
    result = asyncio.run(send_test_message())
    print(f"✅ Mensagem enviada com sucesso!")
    print(f"   Message ID: {result.message_id}")
    print(f"   Para: {result.chat.id}")
    print(f"\n💡 Verifique seu Telegram para confirmar o recebimento!")
    
except Exception as e:
    print(f"❌ Erro ao enviar mensagem: {e}")
    print(f"\n🔧 POSSÍVEIS CAUSAS:")
    print(f"   1. Chat ID incorreto")
    print(f"   2. Você não iniciou conversa com o bot")
    print(f"   3. O bot foi bloqueado")
    print(f"\n💡 SOLUÇÃO:")
    print(f"   1. Abra o Telegram")
    print(f"   2. Procure por @{bot_info.username if 'bot_info' in locals() else 'seu_bot'}")
    print(f"   3. Clique em START ou envie /start")
    print(f"   4. Execute este teste novamente")
    sys.exit(1)

print()

# Teste 5: TelegramNotifier do Bot
print("TESTE 5: Testando TelegramNotifier do bot...")
print("-" * 80)

try:
    sys.path.insert(0, str(Path(__file__).parent / 'src'))
    from notifications.telegram_bot import TelegramNotifier
    import yaml
    
    # Carregar config
    config_path = Path(__file__).parent / 'config' / 'config.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Adicionar credenciais
    config['telegram'] = {
        'bot_token': token,
        'chat_id': chat_id
    }
    
    # Inicializar notifier
    notifier = TelegramNotifier(config)
    
    # Enviar mensagem
    success = notifier.send_message(
        "🎯 *TESTE VIA TELEGRAM NOTIFIER*\n\n"
        "Esta mensagem foi enviada usando o TelegramNotifier do Urion Bot.\n\n"
        "✅ Sistema operacional!"
    )
    
    if success:
        print("✅ TelegramNotifier funcionando!")
    else:
        print("⚠️ TelegramNotifier retornou False (mas pode ter enviado)")
    
except Exception as e:
    print(f"❌ Erro no TelegramNotifier: {e}")
    import traceback
    traceback.print_exc()

print()

# Teste 6: Notificação de Trade
print("TESTE 6: Enviando notificação de trade simulado...")
print("-" * 80)

try:
    success = notifier.send_trade_notification(
        action='BUY',
        symbol='XAUUSD',
        price=2650.50,
        volume=0.01,
        sl=2640.00,
        tp=2670.00,
        strategy='TrendFollowing',
        confidence=75.5
    )
    
    if success:
        print("✅ Notificação de trade enviada!")
        print("   💡 Verifique seu Telegram")
    else:
        print("⚠️ send_trade_notification retornou False")
    
except Exception as e:
    print(f"❌ Erro ao enviar notificação de trade: {e}")

print()
print("="*80)
print("DIAGNÓSTICO COMPLETO!")
print("="*80)
print("\n💡 Se você recebeu as mensagens no Telegram, tudo está funcionando!")
print("❌ Se NÃO recebeu, verifique:")
print("   1. Chat ID está correto?")
print("   2. Você iniciou conversa com o bot (/start)?")
print("   3. O bot está ativo no BotFather?")
print()
