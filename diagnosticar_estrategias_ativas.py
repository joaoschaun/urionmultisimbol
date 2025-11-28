import sqlite3

conn = sqlite3.connect('data/strategy_stats.db')
c = conn.cursor()

print("\n" + "="*80)
print("📊 ANÁLISE: POR QUE SÓ 2 ESTRATÉGIAS ESTÃO OPERANDO?")
print("="*80 + "\n")

# 1. Trades por estratégia
c.execute("""
    SELECT 
        strategy_name, 
        COUNT(*) as total,
        MAX(datetime(open_time)) as last_trade
    FROM strategy_trades 
    GROUP BY strategy_name 
    ORDER BY total DESC
""")

print("1️⃣ TRADES POR ESTRATÉGIA:\n")
print(f"{'Estratégia':<20} {'Total Trades':<15} {'Último Trade'}")
print("-" * 70)

rows = c.fetchall()
for row in rows:
    print(f"{row[0]:<20} {row[1]:<15} {row[2] or 'Nunca'}")

print(f"\n✅ Total de estratégias que JÁ operaram: {len(rows)}\n")

# 2. Estratégias nas últimas 24h
c.execute("""
    SELECT 
        strategy_name, 
        COUNT(*) as total_24h
    FROM strategy_trades 
    WHERE open_time > datetime('now', '-24 hours')
    GROUP BY strategy_name 
    ORDER BY total_24h DESC
""")

print("\n2️⃣ ESTRATÉGIAS ATIVAS (ÚLTIMAS 24 HORAS):\n")
print(f"{'Estratégia':<20} {'Trades 24h'}")
print("-" * 40)

active_strategies = c.fetchall()
if active_strategies:
    for row in active_strategies:
        print(f"{row[0]:<20} {row[1]}")
    print(f"\n✅ Estratégias ativas nas últimas 24h: {len(active_strategies)}")
else:
    print("⚠️ NENHUMA estratégia operou nas últimas 24 horas!")

conn.close()

print("\n" + "="*80)
print("📋 ANÁLISE DO CONFIG:")
print("="*80 + "\n")

import yaml

with open('config/config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

strategies_config = config.get('strategies', {})
enabled_list = strategies_config.get('enabled', [])

print(f"Lista 'enabled' no config: {enabled_list}")
print()

print("STATUS DE CADA ESTRATÉGIA:\n")
print(f"{'Estratégia':<20} {'Config Enabled':<15} {'Na Lista'}")
print("-" * 60)

for strategy in ['trend_following', 'mean_reversion', 'breakout', 
                 'news_trading', 'scalping', 'range_trading']:
    strat_config = strategies_config.get(strategy, {})
    enabled_flag = strat_config.get('enabled', False)
    in_list = strategy in enabled_list
    
    status = "✅" if (enabled_flag and in_list) else "❌"
    print(f"{strategy:<20} {str(enabled_flag):<15} {str(in_list):<15} {status}")

print("\n" + "="*80)
print("🔍 DIAGNÓSTICO:")
print("="*80 + "\n")

# Contar quantas estão ativas
active_count = 0
for strategy in ['trend_following', 'mean_reversion', 'breakout', 
                 'news_trading', 'scalping', 'range_trading']:
    strat_config = strategies_config.get(strategy, {})
    enabled_flag = strat_config.get('enabled', False)
    in_list = strategy in enabled_list
    if enabled_flag and in_list:
        active_count += 1

print(f"⚙️ Estratégias HABILITADAS no config: {active_count}")
print(f"📊 Estratégias que JÁ GERARAM trades (histórico): {len(rows)}")
print(f"🔥 Estratégias ATIVAS (últimas 24h): {len(active_strategies) if active_strategies else 0}")

print("\n💡 EXPLICAÇÃO:\n")
if active_count == 0:
    print("❌ NENHUMA estratégia está habilitada!")
    print("   Todas foram PAUSADAS na auditoria anterior.")
    print("   Para reativar, mude 'enabled: true' no config.yaml")
elif active_count > 0:
    print(f"✅ {active_count} estratégia(s) habilitada(s)")
    if len(active_strategies) < active_count:
        print(f"⚠️ MAS apenas {len(active_strategies)} operou recentemente")
        print("   Possíveis causas:")
        print("   • Condições de mercado não atendem critérios")
        print("   • min_confidence muito alto")
        print("   • Filtros muito restritivos")

print("\n" + "="*80 + "\n")
