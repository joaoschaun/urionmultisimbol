"""
Script de Teste Completo do Sistema
Testa todos os componentes do bot
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from loguru import logger
import sqlite3
from datetime import datetime
import MetaTrader5 as mt5

logger.add("logs/teste_completo.log", rotation="10 MB")

print("=" * 80)
print("🔍 TESTE COMPLETO DO SISTEMA URION")
print("=" * 80)

# ============================================================================
# 1. TESTE DE BANCO DE DADOS
# ============================================================================
print("\n1️⃣ TESTANDO BANCO DE DADOS...")
try:
    conn = sqlite3.connect('data/strategy_stats.db')
    cursor = conn.cursor()
    
    # Verificar tabelas
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"   ✅ Tabelas encontradas: {[t[0] for t in tables]}")
    
    # Verificar total de trades
    cursor.execute("SELECT COUNT(*) FROM strategy_trades")
    total = cursor.fetchone()[0]
    print(f"   ✅ Total de trades: {total}")
    
    # Verificar por estratégia
    cursor.execute("""
        SELECT strategy_name, COUNT(*) as count, 
               SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins
        FROM strategy_trades 
        WHERE status = 'closed'
        GROUP BY strategy_name
    """)
    stats = cursor.fetchall()
    print(f"   📊 Por estratégia:")
    for name, count, wins in stats:
        wr = (wins/count*100) if count > 0 else 0
        print(f"      - {name}: {count} trades, {wins} wins ({wr:.1f}%)")
    
    # Verificar trades recentes
    cursor.execute("""
        SELECT ticket, strategy_name, type, profit, close_time
        FROM strategy_trades
        ORDER BY open_time DESC
        LIMIT 5
    """)
    recent = cursor.fetchall()
    print(f"   📈 Últimos 5 trades:")
    for ticket, strat, typ, profit, close_time in recent:
        tipo = "BUY" if typ == 0 else "SELL"
        print(f"      #{ticket}: {strat} {tipo} = ${profit:.2f} ({close_time})")
    
    conn.close()
    print("   ✅ Banco de dados OK\n")
except Exception as e:
    print(f"   ❌ ERRO no banco: {e}\n")

# ============================================================================
# 2. TESTE DE CONEXÃO MT5
# ============================================================================
print("2️⃣ TESTANDO CONEXÃO MT5...")
try:
    if not mt5.initialize():
        print("   ❌ Falha ao inicializar MT5")
    else:
        account = mt5.account_info()
        if account:
            print(f"   ✅ Conta: {account.login}")
            print(f"   💰 Balance: ${account.balance:.2f}")
            print(f"   📊 Equity: ${account.equity:.2f}")
            print(f"   📉 Profit: ${account.profit:.2f}")
            
            # Verificar posições abertas
            positions = mt5.positions_get(symbol="XAUUSD")
            if positions:
                print(f"   📍 Posições abertas: {len(positions)}")
                for pos in positions[:3]:
                    tipo = "BUY" if pos.type == 0 else "SELL"
                    print(f"      #{pos.ticket}: {tipo} @ {pos.price_open:.2f}, Profit: ${pos.profit:.2f}")
            else:
                print(f"   📍 Nenhuma posição aberta")
            
            # Verificar preço atual
            tick = mt5.symbol_info_tick("XAUUSD")
            if tick:
                print(f"   💹 XAUUSD: Bid={tick.bid:.2f}, Ask={tick.ask:.2f}, Spread={tick.ask-tick.bid:.2f}")
        
        mt5.shutdown()
        print("   ✅ MT5 OK\n")
except Exception as e:
    print(f"   ❌ ERRO no MT5: {e}\n")

# ============================================================================
# 3. TESTE DE CONFIGURAÇÕES
# ============================================================================
print("3️⃣ TESTANDO CONFIGURAÇÕES...")
try:
    from core.config_manager import ConfigManager
    
    config = ConfigManager()
    
    # Verificar estratégias habilitadas
    enabled = config.config.get('strategies', {}).get('enabled', [])
    print(f"   ✅ Estratégias habilitadas: {len(enabled)}")
    for strat in enabled:
        strat_config = config.config['strategies'].get(strat, {})
        print(f"      - {strat}: Ciclo={strat_config.get('cycle_seconds')}s, Max={strat_config.get('max_positions')}")
    
    # Verificar risk config
    risk = config.config.get('risk', {})
    print(f"   🛡️ Risk Management:")
    print(f"      - Max risk/trade: {risk.get('max_risk_per_trade')*100}%")
    print(f"      - Max drawdown: {risk.get('max_drawdown')*100}%")
    print(f"      - Max daily loss: {risk.get('max_daily_loss')*100}%")
    
    # Verificar trading config
    trading = config.config.get('trading', {})
    print(f"   💼 Trading:")
    print(f"      - Max posições: {trading.get('max_open_positions')}")
    print(f"      - Símbolo: {trading.get('symbol')}")
    
    print("   ✅ Configurações OK\n")
except Exception as e:
    print(f"   ❌ ERRO nas configurações: {e}\n")

# ============================================================================
# 4. TESTE DE SISTEMA DE APRENDIZADO
# ============================================================================
print("4️⃣ TESTANDO SISTEMA DE APRENDIZADO...")
try:
    from ml.strategy_learner import StrategyLearner
    
    learner = StrategyLearner()
    
    # Verificar dados de aprendizagem
    print(f"   📚 Estratégias com dados de aprendizagem: {len(learner.learning_data)}")
    
    # Analisar cada estratégia
    strategies = ['trend_following', 'mean_reversion', 'breakout', 'scalping', 'range_trading', 'news_trading']
    for strat in strategies:
        perf = learner.analyze_strategy_performance(strat, days=7)
        if perf.get('total_trades', 0) > 0:
            print(f"   📊 {strat}:")
            print(f"      - Trades: {perf['total_trades']}")
            print(f"      - Win Rate: {perf.get('win_rate', 0)*100:.1f}%")
            print(f"      - Profit Factor: {perf.get('profit_factor', 0):.2f}")
            print(f"      - Recomendação: {perf.get('recommendation', 'N/A')}")
    
    print("   ✅ Sistema de aprendizado OK\n")
except Exception as e:
    print(f"   ❌ ERRO no aprendizado: {e}\n")

# ============================================================================
# 5. TESTE DE ANÁLISE TÉCNICA
# ============================================================================
print("5️⃣ TESTANDO ANÁLISE TÉCNICA...")
try:
    from core.mt5_connector import MT5Connector
    from core.config_manager import ConfigManager
    from analysis.technical_analyzer import TechnicalAnalyzer
    
    config = ConfigManager()
    mt5_conn = MT5Connector(config.config)
    
    if mt5_conn.connect():
        analyzer = TechnicalAnalyzer(mt5_conn, config.config)
        
        # Análise multi-timeframe
        analysis = analyzer.analyze_multi_timeframe()  # Usa timeframes padrão
        
        print(f"   ✅ Timeframes analisados: {len(analysis)}")
        for tf, data in analysis.items():
            indicators = data.get('indicators', {})
            print(f"   📊 {tf}:")
            print(f"      - Preço: {data.get('current_price', 0):.2f}")
            print(f"      - RSI: {indicators.get('RSI', 0):.1f}")
            print(f"      - ADX: {indicators.get('ADX', 0):.1f}")
            print(f"      - MACD: {indicators.get('MACD', {}).get('histogram', 0):.4f}")
        
        mt5_conn.disconnect()
        print("   ✅ Análise técnica OK\n")
    else:
        print("   ❌ Não foi possível conectar ao MT5\n")
except Exception as e:
    print(f"   ❌ ERRO na análise técnica: {e}\n")

# ============================================================================
# 6. TESTE DE ESTRATÉGIAS
# ============================================================================
print("6️⃣ TESTANDO ESTRATÉGIAS...")
try:
    from strategies.strategy_manager import StrategyManager
    
    config = ConfigManager()
    manager = StrategyManager(config.config)
    
    print(f"   ✅ Estratégias carregadas: {len(manager.strategies)}")
    
    # Testar análise de cada estratégia  
    mt5_conn = MT5Connector(config.config)
    if mt5_conn.connect():
        analyzer = TechnicalAnalyzer(mt5_conn, config.config)
        analysis = analyzer.analyze_multi_timeframe()  # Usa timeframes padrão
        
        signals = manager.analyze_all(analysis, {})
        
        print(f"   📡 Sinais gerados: {len(signals)}")
        for signal in signals:
            action = signal.get('action', 'HOLD')
            conf = signal.get('confidence', 0)
            strat = signal.get('strategy', 'unknown')
            if action != 'HOLD':
                print(f"      - {strat}: {action} (confiança: {conf:.1%})")
        
        mt5_conn.disconnect()
        print("   ✅ Estratégias OK\n")
    else:
        print("   ⚠️ Não foi possível testar sinais (MT5 não conectado)\n")
except Exception as e:
    print(f"   ❌ ERRO nas estratégias: {e}\n")

# ============================================================================
# 7. TESTE DE NOTIFICAÇÕES
# ============================================================================
print("7️⃣ TESTANDO NOTIFICAÇÕES TELEGRAM...")
try:
    from notifications.telegram_bot import TelegramNotifier
    
    config = ConfigManager()
    telegram = TelegramNotifier(config.config)
    
    # Testar envio
    success = telegram.send_message("🔍 Teste do sistema completo - " + datetime.now().strftime("%H:%M:%S"))
    
    if success:
        print("   ✅ Telegram OK\n")
    else:
        print("   ⚠️ Telegram configurado mas falhou ao enviar\n")
except Exception as e:
    print(f"   ❌ ERRO no Telegram: {e}\n")

# ============================================================================
# RESUMO FINAL
# ============================================================================
print("=" * 80)
print("📋 RESUMO DOS TESTES")
print("=" * 80)
print("✅ = Funcionando")
print("⚠️ = Funcionando com avisos")  
print("❌ = Com problemas")
print("=" * 80)
print("\nTestes concluídos!")
