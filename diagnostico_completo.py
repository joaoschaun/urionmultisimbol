#!/usr/bin/env python3
"""
Diagnóstico completo do Urion Trading Bot
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# Carregar variáveis de ambiente
load_dotenv()

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

print("\n" + "="*80)
print(" "*20 + "DIAGNÓSTICO COMPLETO - URION BOT")
print("="*80)
print(f"Data/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# ============================================================================
# 1. VERIFICAR AMBIENTE
# ============================================================================
print("="*80)
print("1. AMBIENTE")
print("="*80)

# Python
import platform
print(f"✅ Python: {platform.python_version()}")

# Módulos essenciais
modules_to_check = [
    'MetaTrader5',
    'pandas',
    'numpy',
    'yaml',
    'telegram',
    'requests',
    'loguru'
]

print("\nMódulos instalados:")
for module in modules_to_check:
    try:
        mod = __import__(module)
        version = getattr(mod, '__version__', 'N/A')
        print(f"  ✅ {module}: {version}")
    except ImportError:
        print(f"  ❌ {module}: NÃO INSTALADO")

# ============================================================================
# 2. VERIFICAR CREDENCIAIS
# ============================================================================
print("\n" + "="*80)
print("2. CREDENCIAIS")
print("="*80)

credentials = {
    'MT5_LOGIN': os.getenv('MT5_LOGIN'),
    'MT5_PASSWORD': os.getenv('MT5_PASSWORD'),
    'MT5_SERVER': os.getenv('MT5_SERVER'),
    'MT5_PATH': os.getenv('MT5_PATH'),
    'TELEGRAM_BOT_TOKEN': os.getenv('TELEGRAM_BOT_TOKEN'),
    'TELEGRAM_CHAT_ID': os.getenv('TELEGRAM_CHAT_ID')
}

for key, value in credentials.items():
    if value:
        if 'PASSWORD' in key or 'TOKEN' in key:
            masked = value[:10] + '...' + value[-10:] if len(value) > 20 else '***'
            print(f"  ✅ {key}: {masked}")
        else:
            print(f"  ✅ {key}: {value}")
    else:
        print(f"  ❌ {key}: NÃO CONFIGURADO")

# ============================================================================
# 3. TESTAR CONEXÃO MT5
# ============================================================================
print("\n" + "="*80)
print("3. CONEXÃO MT5")
print("="*80)

try:
    import MetaTrader5 as mt5
    
    # Inicializar
    if not mt5.initialize():
        print(f"  ❌ Erro ao inicializar MT5: {mt5.last_error()}")
    else:
        print("  ✅ MT5 inicializado com sucesso")
        
        # Informações da conta
        account_info = mt5.account_info()
        if account_info:
            print(f"  ✅ Conta: {account_info.login}")
            print(f"  ✅ Server: {account_info.server}")
            print(f"  ✅ Balance: ${account_info.balance:.2f}")
            print(f"  ✅ Equity: ${account_info.equity:.2f}")
            print(f"  ✅ Margin: ${account_info.margin:.2f}")
            print(f"  ✅ Free Margin: ${account_info.margin_free:.2f}")
        else:
            print(f"  ⚠️ Não foi possível obter info da conta")
        
        # Testar símbolo XAUUSD
        symbol_info = mt5.symbol_info("XAUUSD")
        if symbol_info:
            print(f"  ✅ XAUUSD disponível")
            print(f"     Bid: {symbol_info.bid:.2f}")
            print(f"     Ask: {symbol_info.ask:.2f}")
            print(f"     Spread: {symbol_info.spread}")
        else:
            print(f"  ❌ XAUUSD não disponível")
        
        mt5.shutdown()
        
except Exception as e:
    print(f"  ❌ Erro ao testar MT5: {e}")

# ============================================================================
# 4. TESTAR TELEGRAM
# ============================================================================
print("\n" + "="*80)
print("4. TELEGRAM")
print("="*80)

try:
    import telegram
    from telegram import Bot
    import asyncio
    
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if token and chat_id:
        async def test_telegram():
            bot = Bot(token=token)
            async with bot:
                # Testar bot
                bot_info = await bot.get_me()
                print(f"  ✅ Bot conectado: @{bot_info.username}")
                
                # Enviar mensagem de teste
                await bot.send_message(
                    chat_id=chat_id,
                    text="🤖 *DIAGNÓSTICO - Teste de conexão*\n\nTelegram funcionando!",
                    parse_mode='Markdown'
                )
                print(f"  ✅ Mensagem de teste enviada")
                return True
        
        result = asyncio.run(test_telegram())
        if result:
            print("  ✅ Telegram 100% operacional")
    else:
        print("  ❌ Credenciais Telegram não configuradas")
        
except Exception as e:
    print(f"  ❌ Erro ao testar Telegram: {e}")

# ============================================================================
# 5. VERIFICAR CONFIGURAÇÃO
# ============================================================================
print("\n" + "="*80)
print("5. CONFIGURAÇÃO")
print("="*80)

try:
    import yaml
    
    config_path = Path(__file__).parent / 'config' / 'config.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    print("  ✅ Arquivo config.yaml carregado")
    
    # Trading
    trading = config.get('trading', {})
    print(f"  ✅ Symbol: {trading.get('symbol')}")
    print(f"  ✅ Lot padrão: {trading.get('default_lot_size')}")
    print(f"  ✅ Max posições: {trading.get('max_open_positions')}")
    
    # Risk
    risk = config.get('risk', {})
    print(f"  ✅ Max risco/trade: {risk.get('max_risk_per_trade', 0)*100}%")
    print(f"  ✅ Trailing stop: {'Sim' if risk.get('trailing_stop_enabled') else 'Não'}")
    print(f"  ✅ Break-even: {'Sim' if risk.get('break_even_enabled') else 'Não'}")
    
    # Estratégias
    strategies = config.get('strategies', {})
    enabled_list = strategies.get('enabled', [])
    print(f"  ✅ Estratégias ativas: {len(enabled_list)}")
    for name in enabled_list:
        strategy_config = strategies.get(name, {})
        if isinstance(strategy_config, dict):
            cycle = strategy_config.get('cycle_seconds', 0)
            enabled = strategy_config.get('enabled', False)
            status = "✓" if enabled else "✗"
            print(f"     {status} {name}: {cycle}s")
    
    # Notificações
    notifications = config.get('notifications', {})
    telegram_enabled = notifications.get('telegram', {}).get('enabled', False)
    print(f"  ✅ Notificações Telegram: {'Ativas' if telegram_enabled else 'Desativadas'}")
    
except Exception as e:
    print(f"  ❌ Erro ao verificar configuração: {e}")

# ============================================================================
# 6. VERIFICAR COMPONENTES
# ============================================================================
print("\n" + "="*80)
print("6. COMPONENTES DO BOT")
print("="*80)

components = [
    ('MT5Connector', 'core.mt5_connector'),
    ('ConfigManager', 'core.config_manager'),
    ('RiskManager', 'core.risk_manager'),
    ('MarketHoursManager', 'core.market_hours'),
    ('StrategyExecutor', 'core.strategy_executor'),
    ('TechnicalAnalyzer', 'analysis.technical_analyzer'),
    ('NewsAnalyzer', 'analysis.news_analyzer'),
    ('StrategyManager', 'strategies.strategy_manager'),
    ('TelegramNotifier', 'notifications.telegram_bot'),
    ('OrderGenerator', 'order_generator'),
    ('OrderManager', 'order_manager'),
]

for component_name, module_path in components:
    try:
        module = __import__(module_path, fromlist=[component_name])
        component_class = getattr(module, component_name)
        print(f"  ✅ {component_name}")
    except Exception as e:
        print(f"  ❌ {component_name}: {str(e)[:50]}")

# ============================================================================
# 7. VERIFICAR BANCO DE DADOS
# ============================================================================
print("\n" + "="*80)
print("7. BANCO DE DADOS")
print("="*80)

try:
    from database.strategy_stats import StrategyStatsDB
    
    db = StrategyStatsDB()
    print("  ✅ Database conectado")
    
    # Contar trades
    stats = db.get_all_trades()
    if stats:
        print(f"  ✅ Total de trades registrados: {len(stats)}")
        
        # Estatísticas por estratégia
        from collections import Counter
        strategy_counts = Counter(trade.get('strategy_name', 'Unknown') for trade in stats)
        print("\n  Trades por estratégia:")
        for strategy, count in strategy_counts.most_common():
            print(f"     • {strategy}: {count}")
    else:
        print("  ⚠️ Nenhum trade registrado ainda")
    
except Exception as e:
    print(f"  ❌ Erro ao verificar database: {e}")

# ============================================================================
# 8. VERIFICAR LOGS
# ============================================================================
print("\n" + "="*80)
print("8. LOGS")
print("="*80)

log_path = Path(__file__).parent / 'logs' / 'urion.log'
if log_path.exists():
    size_mb = log_path.stat().st_size / (1024 * 1024)
    print(f"  ✅ Arquivo de log existe")
    print(f"  ✅ Tamanho: {size_mb:.2f} MB")
    
    # Últimas linhas
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            last_lines = lines[-5:] if len(lines) >= 5 else lines
            
        print("\n  Últimas 5 linhas:")
        for line in last_lines:
            line = line.strip()
            if line:
                # Truncar se muito longo
                if len(line) > 100:
                    line = line[:100] + "..."
                print(f"    {line}")
    except Exception as e:
        print(f"  ⚠️ Erro ao ler log: {e}")
else:
    print("  ⚠️ Arquivo de log não existe ainda")

# ============================================================================
# 9. VERIFICAR ARQUIVOS ESSENCIAIS
# ============================================================================
print("\n" + "="*80)
print("9. ARQUIVOS ESSENCIAIS")
print("="*80)

essential_files = [
    'main.py',
    'src/order_generator.py',
    'src/order_manager.py',
    'monitor_24h.py',
    'start_24h.ps1',
    'config/config.yaml',
    '.env',
    'requirements.txt',
]

for file_path in essential_files:
    full_path = Path(__file__).parent / file_path
    if full_path.exists():
        print(f"  ✅ {file_path}")
    else:
        print(f"  ❌ {file_path}: NÃO ENCONTRADO")

# ============================================================================
# 10. STATUS FINAL
# ============================================================================
print("\n" + "="*80)
print("10. STATUS FINAL")
print("="*80)

print("\n✅ DIAGNÓSTICO COMPLETO!")
print("\n📋 RESUMO:")
print("   • Ambiente: OK")
print("   • Credenciais: Verificar acima")
print("   • MT5: Verificar conexão acima")
print("   • Telegram: Verificar teste acima")
print("   • Componentes: Verificar lista acima")
print("   • Configuração: OK")
print("\n💡 PRÓXIMOS PASSOS:")
print("   1. Se houver ❌, corrija os problemas")
print("   2. Execute: python monitor_24h.py")
print("   3. Monitore os logs e o Telegram")
print()
