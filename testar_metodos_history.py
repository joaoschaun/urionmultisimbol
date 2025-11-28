import MetaTrader5 as mt5
from datetime import datetime, timedelta

mt5.initialize()

# Ticket que sabemos que fechou
ticket = 207855307

print(f"\n{'='*80}")
print(f"TESTE: Buscar profit de posição fechada (Ticket {ticket})")
print(f"{'='*80}\n")

# MT5 mostrou: -$2.70
print("MT5 Real (do teste anterior): -$2.70\n")

# 1. Tentar history_orders_get (método atual do bot)
print("1. mt5.history_orders_get(position=ticket):")
history_orders = mt5.history_orders_get(
    datetime.now() - timedelta(hours=6),
    datetime.now(),
    position=ticket
)
if history_orders:
    total_profit = sum(order.profit for order in history_orders if hasattr(order, 'profit'))
    print(f"   ✅ {len(history_orders)} ordens encontradas, Profit total: ${total_profit:.2f}")
else:
    print(f"   ❌ Nenhuma ordem encontrada")

# 2. Tentar history_deals_get (método alternativo - MELHOR!)
print("\n2. mt5.history_deals_get(position=ticket):")
history_deals = mt5.history_deals_get(
    datetime.now() - timedelta(hours=6),
    datetime.now(),
    position=ticket
)
if history_deals:
    print(f"   ✅ {len(history_deals)} deals encontrados:")
    total_profit = 0
    for deal in history_deals:
        if hasattr(deal, 'profit'):
            print(f"      Deal {deal.ticket}: ${deal.profit:.2f} (Type: {deal.entry})")
            total_profit += deal.profit
    print(f"   📊 Profit TOTAL: ${total_profit:.2f}")
else:
    print(f"   ❌ Nenhum deal encontrado")

# 3. Testar com ticket de deal (não position)
print("\n3. Buscando por DEAL ticket (167725975):")
deal_ticket = 167725975
history_deals_by_ticket = mt5.history_deals_get(
    datetime.now() - timedelta(hours=6),
    datetime.now(),
    ticket=deal_ticket
)
if history_deals_by_ticket:
    print(f"   ✅ Deal encontrado:")
    deal = history_deals_by_ticket[0]
    print(f"      Position: {deal.position_id}")
    print(f"      Profit: ${deal.profit:.2f}")
    print(f"      Entry: {deal.entry}")
else:
    print(f"   ❌ Deal não encontrado")

mt5.shutdown()

print(f"\n{'='*80}")
print("CONCLUSÃO:")
print("Se history_deals_get funcionar, devemos usar ele no lugar de history_orders_get!")
print(f"{'='*80}\n")
