"""
Testar captura de profit em tempo real
"""
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import sqlite3

print("=" * 80)
print("TESTE DE CAPTURA DE PROFIT")
print("=" * 80)
print()

# Conectar MT5
if not mt5.initialize():
    print("❌ Erro ao conectar MT5")
    exit()

print("✅ MT5 conectado")
print()

# Buscar histórico dos últimos 30 minutos
print("1. BUSCANDO HISTÓRICO DE DEALS (últimos 30 min)...")
start_time = datetime.now() - timedelta(minutes=30)
deals = mt5.history_deals_get(start_time, datetime.now())

if deals:
    print(f"✅ Encontrados {len(deals)} deals")
    print()
    print("Últimos 10 deals:")
    print(f"{'Ticket':<12} {'Position':<12} {'Type':<8} {'Profit':<12} {'Time'}")
    print("-" * 80)
    for deal in deals[-10:]:
        deal_type = "IN" if deal.entry == 0 else "OUT" if deal.entry == 1 else "INOUT"
        deal_time = datetime.fromtimestamp(deal.time)
        print(f"{deal.ticket:<12} {deal.position_id:<12} {deal_type:<8} ${deal.profit:<11.2f} {deal_time}")
else:
    print("⚠️  Nenhum deal encontrado")

print()

# Buscar histórico de ordens
print("2. BUSCANDO HISTÓRICO DE ORDERS (últimos 30 min)...")
orders = mt5.history_orders_get(start_time, datetime.now())

if orders:
    print(f"✅ Encontrados {len(orders)} orders")
    print()
    print("Últimas 10 ordens:")
    print(f"{'Ticket':<12} {'Position':<12} {'State':<10} {'Type':<10} {'Time Done'}")
    print("-" * 80)
    for order in orders[-10:]:
        order_time = datetime.fromtimestamp(order.time_done) if order.time_done > 0 else "N/A"
        states = {0: 'STARTED', 1: 'PLACED', 2: 'CANCELED', 3: 'PARTIAL', 4: 'FILLED', 5: 'REJECTED', 6: 'EXPIRED', 7: 'REQUEST_ADD', 8: 'REQUEST_MODIFY', 9: 'REQUEST_CANCEL'}
        state = states.get(order.state, f'UNKNOWN({order.state})')
        print(f"{order.ticket:<12} {order.position_id:<12} {state:<10} {order.type:<10} {order_time}")
else:
    print("⚠️  Nenhuma order encontrada")

print()

# Comparar com banco de dados
print("3. COMPARANDO COM BANCO DE DADOS...")
conn = sqlite3.connect('data/strategy_stats.db')
c = conn.cursor()

c.execute("""
    SELECT ticket, strategy_name, profit, close_time
    FROM strategy_trades
    WHERE open_time > datetime('now', '-30 minutes')
    ORDER BY open_time DESC
    LIMIT 20
""")

db_trades = c.fetchall()
print(f"Trades no banco (últimos 30 min): {len(db_trades)}")

if db_trades:
    print()
    print(f"{'Ticket':<12} {'Estratégia':<20} {'Profit':<12} {'Close Time'}")
    print("-" * 80)
    for row in db_trades:
        profit_str = f"${row[2]:.2f}" if row[2] is not None else "NULL"
        close_str = row[3] if row[3] else "NULL"
        print(f"{row[0]:<12} {row[1]:<20} {profit_str:<12} {close_str}")

print()

# Análise de discrepância
print("4. ANÁLISE DE DISCREPÂNCIA...")
if deals and db_trades:
    deal_positions = {deal.position_id for deal in deals if deal.entry == 1}  # Saídas
    db_tickets = {row[0] for row in db_trades}
    
    # Deals que não estão no banco
    missing_in_db = deal_positions - db_tickets
    if missing_in_db:
        print(f"⚠️  {len(missing_in_db)} posições fechadas no MT5 mas não no banco:")
        for pos_id in list(missing_in_db)[:5]:
            print(f"   Position ID: {pos_id}")
    
    # Trades no banco sem deal
    db_with_null = {row[0] for row in db_trades if row[2] is None or row[2] == 0}
    print(f"⚠️  {len(db_with_null)} trades no banco com profit NULL ou 0")
    
    # Verificar se há overlap
    overlap = deal_positions & db_tickets
    print(f"✅ {len(overlap)} trades aparecem em ambos (MT5 e DB)")

conn.close()
mt5.shutdown()

print()
print("=" * 80)
print("TESTE CONCLUÍDO")
print("=" * 80)
