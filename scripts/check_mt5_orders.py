"""
Script para verificar ordens e posições no MT5
"""
import MetaTrader5 as mt5
from datetime import datetime
import pytz

# Inicializar MT5
if not mt5.initialize():
    print("❌ Erro ao inicializar MT5")
    exit()

try:
    # Obter informações da conta
    account_info = mt5.account_info()
    
    print("\n" + "="*70)
    print("         MT5 - STATUS DE ORDENS E POSIÇÕES")
    print("="*70)
    
    print(f"\n💼 CONTA:")
    print(f"   Login: {account_info.login}")
    print(f"   Balance: ${account_info.balance:,.2f}")
    print(f"   Equity: ${account_info.equity:,.2f}")
    print(f"   Margin Free: ${account_info.margin_free:,.2f}")
    print(f"   Profit: ${account_info.profit:,.2f}")
    
    # Verificar posições abertas
    positions = mt5.positions_get(symbol="XAUUSD")
    
    print(f"\n📊 POSIÇÕES ABERTAS (XAUUSD): {len(positions) if positions else 0}")
    
    if positions:
        for pos in positions:
            print(f"\n   Ticket: #{pos.ticket}")
            print(f"   Tipo: {'BUY' if pos.type == 0 else 'SELL'}")
            print(f"   Volume: {pos.volume}")
            print(f"   Preço Abertura: {pos.price_open:.2f}")
            print(f"   Preço Atual: {pos.price_current:.2f}")
            print(f"   SL: {pos.sl:.2f}")
            print(f"   TP: {pos.tp:.2f}")
            print(f"   Profit: ${pos.profit:.2f}")
            print(f"   Magic: {pos.magic}")
            
            # Calcular tempo aberto
            open_time = datetime.fromtimestamp(pos.time, tz=pytz.UTC)
            now = datetime.now(pytz.UTC)
            duration = now - open_time
            hours = duration.total_seconds() / 3600
            print(f"   Tempo Aberto: {hours:.1f}h")
    else:
        print("   ⚠️ Nenhuma posição aberta")
    
    # Verificar ordens pendentes
    orders = mt5.orders_get(symbol="XAUUSD")
    
    print(f"\n⏳ ORDENS PENDENTES (XAUUSD): {len(orders) if orders else 0}")
    
    if orders:
        for order in orders:
            print(f"\n   Ticket: #{order.ticket}")
            print(f"   Tipo: {order.type}")
            print(f"   Volume: {order.volume}")
            print(f"   Preço: {order.price_open:.2f}")
            print(f"   SL: {order.sl:.2f}")
            print(f"   TP: {order.tp:.2f}")
    else:
        print("   ⚠️ Nenhuma ordem pendente")
    
    # Verificar histórico recente (últimas 24h)
    from datetime import timedelta
    from_date = datetime.now() - timedelta(days=1)
    
    deals = mt5.history_deals_get(from_date, datetime.now())
    
    if deals:
        # Filtrar apenas XAUUSD
        xauusd_deals = [d for d in deals if d.symbol == "XAUUSD"]
        
        print(f"\n📜 HISTÓRICO 24H (XAUUSD): {len(xauusd_deals)} operações")
        
        # Mostrar últimas 5 operações
        recent_deals = sorted(xauusd_deals, key=lambda x: x.time, reverse=True)[:5]
        
        for deal in recent_deals:
            deal_time = datetime.fromtimestamp(deal.time, tz=pytz.UTC)
            est_time = deal_time.astimezone(pytz.timezone('America/New_York'))
            
            print(f"\n   Ticket: #{deal.order}")
            print(f"   Tipo: {'BUY' if deal.type == 0 else 'SELL'}")
            print(f"   Volume: {deal.volume}")
            print(f"   Preço: {deal.price:.2f}")
            print(f"   Profit: ${deal.profit:.2f}")
            print(f"   Horário: {est_time.strftime('%Y-%m-%d %H:%M:%S')} EST")
    else:
        print(f"\n📜 HISTÓRICO 24H: Nenhuma operação")
    
    # Verificar se há erros
    last_error = mt5.last_error()
    print(f"\n🔍 ÚLTIMO ERRO MT5:")
    print(f"   Code: {last_error[0]}")
    print(f"   Message: {last_error[1]}")
    
    # Verificar status do símbolo
    symbol_info = mt5.symbol_info("XAUUSD")
    
    print(f"\n⚙️ STATUS DO SÍMBOLO (XAUUSD):")
    print(f"   Selecionado: {'✅ SIM' if symbol_info.visible else '❌ NÃO'}")
    print(f"   Trade Allowed: {'✅ SIM' if symbol_info.trade_mode == mt5.SYMBOL_TRADE_MODE_FULL else '❌ NÃO'}")
    print(f"   Lot Mínimo: {symbol_info.volume_min}")
    print(f"   Lot Máximo: {symbol_info.volume_max}")
    print(f"   Lot Step: {symbol_info.volume_step}")
    print(f"   Bid: {symbol_info.bid:.2f}")
    print(f"   Ask: {symbol_info.ask:.2f}")
    print(f"   Spread: {(symbol_info.ask - symbol_info.bid) * 10:.1f} pips")
    
    # Verificar permissões de trading
    terminal_info = mt5.terminal_info()
    
    print(f"\n🖥️ TERMINAL:")
    print(f"   Trading Allowed: {'✅ SIM' if terminal_info.trade_allowed else '❌ NÃO'}")
    print(f"   Auto Trading: {'✅ SIM' if terminal_info.mqid else '❌ NÃO'}")
    print(f"   Connected: {'✅ SIM' if terminal_info.connected else '❌ NÃO'}")
    
    print("\n" + "="*70 + "\n")

finally:
    mt5.shutdown()
