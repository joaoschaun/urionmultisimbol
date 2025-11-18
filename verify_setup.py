"""
Script de Verificação Rápida - Urion Trading Bot
Verifica se todas as dependências e conexões estão funcionando
"""

import sys
from pathlib import Path

# Adicionar src ao path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))


def check_dependencies():
    """Verifica se todas as dependências estão instaladas"""
    print("\n" + "="*60)
    print("VERIFICANDO DEPENDÊNCIAS")
    print("="*60)
    
    packages_to_check = {
        'MetaTrader5': 'MetaTrader5',
        'pandas': 'pandas',
        'numpy': 'numpy',
        'ta': 'ta',
        'loguru': 'loguru',
        'python-telegram-bot': 'telegram',
        'textblob': 'textblob',
        'requests': 'requests',
        'yaml': 'yaml',
    }
    
    missing = []
    for display_name, import_name in packages_to_check.items():
        try:
            __import__(import_name)
            print(f"✅ {display_name}")
        except ImportError:
            print(f"❌ {display_name} - FALTANDO")
            missing.append(display_name)
    
    if missing:
        print(f"\n⚠️  Instalar pacotes faltando:")
        print(f"pip install {' '.join(missing)}")
        return False
    
    print("\n✅ Todas as dependências instaladas!")
    return True


def check_config():
    """Verifica se configuração está presente"""
    print("\n" + "="*60)
    print("VERIFICANDO CONFIGURAÇÃO")
    print("="*60)
    
    config_file = Path('config/config.yaml')
    env_file = Path('.env')
    
    if not config_file.exists():
        print("❌ config/config.yaml não encontrado")
        return False
    else:
        print("✅ config.yaml encontrado")
    
    if not env_file.exists():
        print("⚠️  .env não encontrado (copie .env.example)")
        return False
    else:
        print("✅ .env encontrado")
    
    return True


def check_mt5_connection():
    """Verifica conexão com MT5"""
    print("\n" + "="*60)
    print("VERIFICANDO CONEXÃO MT5")
    print("="*60)
    
    try:
        from core.mt5_connector import MT5Connector
        from core.config_manager import ConfigManager
        
        config = ConfigManager()
        mt5 = MT5Connector(config)
        
        if mt5.connect():
            print("✅ MT5 conectado!")
            
            # Informações da conta
            account_info = mt5.get_account_info()
            if account_info:
                print(f"\n📊 Conta: {account_info.get('login', 'N/A')}")
                print(f"📊 Servidor: {account_info.get('server', 'N/A')}")
                print(f"💰 Saldo: ${account_info.get('balance', 0):.2f}")
                print(f"💵 Equity: ${account_info.get('equity', 0):.2f}")
            
            mt5.disconnect()
            return True
        else:
            print("❌ Falha ao conectar MT5")
            print("\n⚠️  Verifique:")
            print("   - MT5 está instalado?")
            print("   - Credenciais no .env estão corretas?")
            print("   - MT5_PATH aponta para terminal64.exe?")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao testar MT5: {e}")
        return False


def check_telegram():
    """Verifica Telegram"""
    print("\n" + "="*60)
    print("VERIFICANDO TELEGRAM")
    print("="*60)
    
    try:
        from notifications.telegram_bot import TelegramNotifier
        from core.config_manager import ConfigManager
        import asyncio
        
        config = ConfigManager()
        telegram = TelegramNotifier(config.get_all())
        
        if telegram.enabled:
            print("✅ Telegram configurado")
            
            # Tentar enviar mensagem de teste (async)
            try:
                asyncio.run(telegram.send_message("🤖 Bot configurado e pronto!"))
                print("✅ Mensagem de teste enviada!")
                return True
            except Exception as e:
                print(f"⚠️  Erro ao enviar mensagem: {e}")
                return False
        else:
            print("⚠️  Telegram desabilitado na config")
            return True
            
    except Exception as e:
        print(f"❌ Erro ao testar Telegram: {e}")
        return False


def check_apis():
    """Verifica APIs de notícias"""
    print("\n" + "="*60)
    print("VERIFICANDO APIs DE NOTÍCIAS")
    print("="*60)
    
    from core.config_manager import ConfigManager
    
    config = ConfigManager()
    
    # Verificar se keys estão configuradas
    forex_key = config.get('news.api_keys.forexnews')
    finazon_key = config.get('news.api_keys.finazon')
    fmp_key = config.get('news.api_keys.financialmodelingprep')
    
    all_ok = True
    
    if forex_key and forex_key != 'your_forexnews_api_key':
        print("✅ ForexNewsAPI key configurada")
    else:
        print("⚠️  ForexNewsAPI key faltando")
        all_ok = False
    
    if finazon_key and finazon_key != 'your_finazon_api_key':
        print("✅ Finazon key configurada")
    else:
        print("⚠️  Finazon key faltando")
        all_ok = False
    
    if fmp_key and fmp_key != 'your_fmp_api_key':
        print("✅ Financial Modeling Prep key configurada")
    else:
        print("⚠️  FMP key faltando")
        all_ok = False
    
    if not all_ok:
        print("\n⚠️  APIs de notícias não configuradas")
        print("   Bot funcionará sem análise de notícias")
    
    return True  # Não é crítico


def main():
    """Executa todas as verificações"""
    print("\n" + "="*60)
    print("URION TRADING BOT - VERIFICAÇÃO RÁPIDA")
    print("="*60)
    
    results = []
    
    # 1. Dependências
    results.append(("Dependências", check_dependencies()))
    
    # 2. Configuração
    results.append(("Configuração", check_config()))
    
    # 3. MT5
    results.append(("MT5", check_mt5_connection()))
    
    # 4. Telegram
    results.append(("Telegram", check_telegram()))
    
    # 5. APIs
    results.append(("APIs", check_apis()))
    
    # Resumo
    print("\n" + "="*60)
    print("RESUMO")
    print("="*60)
    
    for name, status in results:
        status_icon = "✅" if status else "❌"
        print(f"{status_icon} {name}")
    
    all_ok = all(status for _, status in results)
    
    if all_ok:
        print("\n" + "="*60)
        print("🎉 TUDO PRONTO!")
        print("="*60)
        print("\nVocê pode executar o bot agora:")
        print("  python main.py")
        print("\n⚠️  LEMBRE-SE: Use conta DEMO para testes!")
    else:
        print("\n" + "="*60)
        print("⚠️  CORREÇÕES NECESSÁRIAS")
        print("="*60)
        print("\nCorrija os itens marcados com ❌ antes de executar o bot")
        print("\nConsulte:")
        print("  - PROXIMOS_PASSOS.md (seção 1.1)")
        print("  - docs/QUICKSTART.md")
    
    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    main()
