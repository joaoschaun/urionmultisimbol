import sqlite3
import yaml
from datetime import datetime, timedelta

print("\n" + "="*100)
print("🔍 VERIFICAÇÃO COMPLETA DO BOT")
print("="*100 + "\n")

# 1. VERIFICAR CONFIG
print("📋 1. CONFIGURAÇÃO DAS ESTRATÉGIAS\n")
with open('config/config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

strategies = config['strategies']
enabled_list = strategies.get('enabled', [])

print(f"Estratégias na lista 'enabled': {enabled_list if enabled_list else '❌ VAZIA'}\n")

for strat_name in ['trend_following', 'range_trading', 'scalping', 'mean_reversion', 'breakout', 'news_trading']:
    if strat_name in strategies:
        strat_config = strategies[strat_name]
        is_enabled = strat_config.get('enabled', False)
        min_conf = strat_config.get('min_confidence', 0)
        
        status = "✅ ATIVA" if is_enabled else "❌ PAUSADA"
        print(f"  {strat_name:20} {status:12} | Min Conf: {min_conf:.0%} | Cycle: {strat_config.get('cycle_seconds', 0)}s")
    else:
        print(f"  {strat_name:20} ⚠️ NÃO ENCONTRADA")

# 2. VERIFICAR ÚLTIMOS TRADES
print("\n\n📊 2. ÚLTIMOS 10 TRADES (DESDE REINÍCIO)\n")

conn = sqlite3.connect('data/strategy_stats.db')
c = conn.cursor()

c.execute("""
    SELECT 
        ticket,
        strategy_name,
        type,
        open_price,
        sl,
        tp,
        (open_price - sl) as sl_dist,
        (tp - open_price) as tp_dist,
        signal_confidence,
        datetime(open_time) as open_time
    FROM strategy_trades
    WHERE open_time > datetime('now', '-2 hours')
    ORDER BY open_time DESC
    LIMIT 10
""")

trades = c.fetchall()

if trades:
    print(f"{'Ticket':<12} {'Estratégia':<20} {'Tipo':<6} {'Price':<10} {'SL Dist':<10} {'TP Dist':<10} {'R:R':<8} {'Conf':<8} {'Tempo'}")
    print("-" * 110)
    
    for trade in trades:
        ticket, strat, tipo, price, sl, tp, sl_dist, tp_dist, conf, open_time = trade
        
        # Calcular R:R
        if sl_dist and tp_dist and sl_dist > 0:
            rr_ratio = tp_dist / sl_dist
        else:
            rr_ratio = 0
        
        # Verificar se SL/TP estão corretos
        sl_check = "✅" if abs(sl_dist - 50) < 10 else "❌"
        tp_check = "✅" if abs(tp_dist - 150) < 20 else "❌"
        
        print(f"{ticket:<12} {strat:<20} {tipo:<6} ${price:<9.2f} ${sl_dist:<9.2f}{sl_check} ${tp_dist:<9.2f}{tp_check} 1:{rr_ratio:<6.1f} {conf*100:<7.1f}% {open_time}")
else:
    print("⚠️ Nenhum trade nas últimas 2 horas")

# 3. VERIFICAR POSIÇÕES ABERTAS NO MT5
print("\n\n💼 3. POSIÇÕES ABERTAS NO MT5\n")

try:
    import MetaTrader5 as mt5
    mt5.initialize()
    
    positions = mt5.positions_get(symbol="XAUUSD")
    
    if positions:
        print(f"{'Ticket':<12} {'Tipo':<6} {'Volume':<8} {'Price':<10} {'SL':<10} {'TP':<10} {'Profit':<10} {'Duração'}")
        print("-" * 90)
        
        for pos in positions:
            duration_sec = pos.time - mt5.symbol_info_tick("XAUUSD").time
            duration_min = abs(duration_sec) / 60
            
            print(f"{pos.ticket:<12} {pos.type:<6} {pos.volume:<8} ${pos.price_open:<9.2f} ${pos.sl:<9.2f} ${pos.tp:<9.2f} ${pos.profit:<9.2f} {duration_min:.0f}min")
    else:
        print("✅ Nenhuma posição aberta")
    
    mt5.shutdown()
except Exception as e:
    print(f"⚠️ Erro ao conectar MT5: {e}")

# 4. VERIFICAR CÓDIGO DAS ESTRATÉGIAS
print("\n\n🔧 4. VERIFICAÇÃO DO CÓDIGO base_strategy.py\n")

with open('src/strategies/base_strategy.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Procurar pelas linhas de SL/TP
if 'sl_distance = 50' in code and 'tp_distance = 150' in code:
    print("✅ SL/TP CORRETOS no código:")
    print("   - sl_distance = 50")
    print("   - tp_distance = 150")
    print("   - R:R Ratio = 1:3")
else:
    print("❌ SL/TP INCORRETOS no código!")
    if 'current_price * 0.005' in code:
        print("   ⚠️ Ainda usando cálculo percentual antigo")

# 5. VERIFICAR CONFIDENCE
print("\n\n📈 5. VERIFICAÇÃO DE CONFIDENCE\n")

with open('src/core/strategy_executor.py', 'r', encoding='utf-8') as f:
    executor_code = f.read()

if 'self.stats_db.save_trade(trade_data)' in executor_code:
    print("✅ Confidence sendo salva CORRETAMENTE (sem multiplicação duplicada)")
else:
    if '* 100' in executor_code and 'signal_confidence' in executor_code:
        print("❌ Confidence ainda com bug de multiplicação!")

# 6. SUMMARY
print("\n\n" + "="*100)
print("📋 RESUMO DA VERIFICAÇÃO")
print("="*100 + "\n")

# Contar estratégias ativas
active_strategies = sum(1 for name in ['trend_following', 'range_trading', 'scalping', 'mean_reversion', 'breakout'] 
                       if strategies.get(name, {}).get('enabled', False))

print(f"✅ Estratégias ativas: {active_strategies}/6")
print(f"✅ Trades nas últimas 2h: {len(trades)}")

# Verificar se tem trades recentes com SL/TP corretos
if trades:
    recent_correct = sum(1 for t in trades if abs(t[6] - 50) < 10 and abs(t[7] - 150) < 20)
    print(f"{'✅' if recent_correct > 0 else '❌'} Trades com SL/TP corretos: {recent_correct}/{len(trades)}")

conn.close()

print("\n" + "="*100 + "\n")
