from telegram import Bot
import asyncio

async def main():
    bot = Bot('8132050201:AAHofFjkr5EFdeFxjVBOgD4JFpuL3PmBGFM')
    
    try:
        result = await bot.send_message(
            chat_id='7005082427',
            text='🧪 TESTE DIRETO DO BOT\n\n✅ Se você recebeu esta mensagem, o Telegram está funcionando!'
        )
        print(f'✅ Mensagem enviada! ID: {result.message_id}')
    except Exception as e:
        print(f'❌ Erro: {e}')

asyncio.run(main())
