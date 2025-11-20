"""
Teste de tradução de notícias para Telegram
"""
import os
import sys
import yaml
from dotenv import load_dotenv

# Adicionar diretório src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from notifications.telegram_bot import TelegramNotifier

def test_translation():
    """Testa envio de notícia traduzida"""
    
    print("\n" + "="*60)
    print("TESTE DE TRADUÇÃO DE NOTÍCIAS")
    print("="*60)
    
    # Carregar config
    load_dotenv('.env')
    
    with open('config/config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Criar notifier
    telegram = TelegramNotifier(config)
    
    if not telegram.enabled:
        print("\n❌ Telegram não configurado!")
        print("Configure TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID no .env")
        return
    
    print("\n✅ Telegram configurado")
    print(f"Chat ID: {telegram.chat_id}")
    
    # Exemplos de notícias (em inglês)
    news_examples = [
        {
            'title': 'Fed Holds Interest Rates Steady at 5.25%-5.50%',
            'content': 'The Federal Reserve has decided to maintain interest rates at current levels, citing progress in inflation control while monitoring economic data.',
            'source': 'Reuters',
            'importance': 'high'
        },
        {
            'title': 'Gold Prices Surge to New Record High',
            'content': 'Gold reached $2,100 per ounce amid geopolitical tensions and dollar weakness.',
            'source': 'Bloomberg',
            'importance': 'medium'
        },
        {
            'title': 'US Jobless Claims Fall More Than Expected',
            'content': 'Initial jobless claims dropped to 220,000, beating economist expectations of 230,000.',
            'source': 'MarketWatch',
            'importance': 'medium'
        }
    ]
    
    print("\n📨 Enviando notícias traduzidas...\n")
    
    for i, news in enumerate(news_examples, 1):
        print(f"{i}. Enviando: {news['title'][:50]}...")
        
        success = telegram.send_news_notification(
            news_title=news['title'],
            news_content=news['content'],
            source=news['source'],
            importance=news['importance']
        )
        
        if success:
            print(f"   ✅ Enviada com sucesso!")
        else:
            print(f"   ❌ Falha no envio")
        
        # Aguardar 2 segundos entre mensagens
        import time
        time.sleep(2)
    
    print("\n" + "="*60)
    print("TESTE CONCLUÍDO!")
    print("="*60)
    print("\nVerifique seu Telegram para ver as notícias traduzidas!")
    print("\n")

if __name__ == "__main__":
    test_translation()
