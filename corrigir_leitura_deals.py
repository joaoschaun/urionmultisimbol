"""
Script para corrigir DEFINITIVAMENTE a leitura de deals do MT5

PROBLEMA IDENTIFICADO:
- Usando history_deals_get com position=ticket (ERRADO!)
- Deals não têm position_id diretamente
- Precisa buscar pelo ORDER ou usar histórico completo

SOLUÇÃO:
1. Buscar histórico de ORDERS primeiro (para pegar ticket)
2. Buscar histórico de DEALS filtrado por position_id
3. Validar com histórico de POSITIONS
"""

import MetaTrader5 as mt5
from datetime import datetime, timedelta
import sqlite3

def testar_leitura_deals():
    """Testa diferentes métodos de leitura de deals"""
    
    if not mt5.initialize():
        print(f"❌ Erro ao conectar MT5: {mt5.last_error()}")
        return
    
    print("✅ Conectado ao MT5\n")
    
    # Buscar últimos 5 trades da conta
    print("=" * 80)
    print("📊 TESTANDO LEITURA DE DEALS")
    print("=" * 80)
    
    # Método 1: History Orders (pegar tickets)
    print("\n1️⃣ Buscando ORDERS dos últimos 7 dias...")
    orders = mt5.history_orders_get(
        datetime.now() - timedelta(days=7),
        datetime.now()
    )
    
    if not orders:
        print("⚠️ Nenhuma ordem encontrada")
        return
    
    print(f"✅ {len(orders)} orders encontradas\n")
    
    # Método 2: History Deals (profit real)
    print("2️⃣ Buscando DEALS dos últimos 7 dias...")
    deals = mt5.history_deals_get(
        datetime.now() - timedelta(days=7),
        datetime.now()
    )
    
    if not deals:
        print("⚠️ Nenhum deal encontrado")
        return
    
    print(f"✅ {len(deals)} deals encontrados\n")
    
    # Método 3: Analisar últimos 10 deals
    print("3️⃣ Analisando estrutura dos últimos 10 DEALS:")
    print("-" * 80)
    
    for i, deal in enumerate(deals[-10:]):
        print(f"\nDeal #{i+1}:")
        print(f"  ticket: {deal.ticket}")
        print(f"  order: {deal.order}")
        print(f"  time: {datetime.fromtimestamp(deal.time)}")
        print(f"  position_id: {deal.position_id}")
        print(f"  volume: {deal.volume}")
        print(f"  price: {deal.price}")
        print(f"  profit: ${deal.profit:.2f}")
        print(f"  swap: ${deal.swap:.2f}")
        print(f"  commission: ${deal.commission:.2f}")
        print(f"  entry: {deal.entry} (0=IN, 1=OUT, 2=INOUT)")
        print(f"  type: {deal.type} (0=BUY, 1=SELL)")
        print(f"  magic: {deal.magic}")
    
    # Método 4: Comparar com database
    print("\n" + "=" * 80)
    print("4️⃣ COMPARANDO COM DATABASE")
    print("=" * 80)
    
    conn = sqlite3.connect('data/strategy_stats.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT ticket, strategy_name, open_price, close_price, profit, status
        FROM strategy_trades 
        WHERE close_time IS NOT NULL
        ORDER BY close_time DESC 
        LIMIT 10
    """)
    
    db_trades = cursor.fetchall()
    
    print(f"\n✅ {len(db_trades)} trades fechados no database:\n")
    
    for ticket, strategy, open_p, close_p, profit, status in db_trades:
        print(f"Ticket: {ticket} | {strategy} | Status: {status}")
        print(f"  Open: {open_p:.2f} → Close: {close_p:.2f} | Profit DB: ${profit:.2f}")
        
        # Buscar deals correspondentes no MT5
        position_deals = [d for d in deals if d.position_id == ticket]
        
        if position_deals:
            # Calcular profit REAL dos deals
            profit_in = sum(d.profit for d in position_deals if d.entry == 0)  # IN
            profit_out = sum(d.profit for d in position_deals if d.entry == 1)  # OUT
            profit_total = profit_in + profit_out
            
            print(f"  Deals MT5: {len(position_deals)} deals")
            print(f"    IN: ${profit_in:.2f} | OUT: ${profit_out:.2f} | TOTAL: ${profit_total:.2f}")
            
            # Comparar
            diff = abs(profit - profit_total)
            if diff > 0.01:
                print(f"  ⚠️ DISCREPÂNCIA: ${diff:.2f}")
            else:
                print(f"  ✅ CORRETO")
        else:
            print(f"  ❌ Nenhum deal encontrado no MT5 para ticket {ticket}")
        
        print()
    
    conn.close()
    
    # Método 5: Propor correção
    print("\n" + "=" * 80)
    print("5️⃣ MÉTODO CORRETO PARA USAR NO BOT")
    print("=" * 80)
    print("""
def get_position_profit(ticket: int) -> float:
    '''Busca profit REAL de uma posição pelo ticket'''
    
    # Buscar DEALS da posição (não ORDERS!)
    deals = mt5.history_deals_get(
        datetime.now() - timedelta(hours=24),  # Janela de 24h
        datetime.now()
    )
    
    if not deals:
        return 0.0
    
    # Filtrar deals dessa posição específica
    position_deals = [d for d in deals if d.position_id == ticket]
    
    if not position_deals:
        # Fallback: buscar por ORDER
        position_deals = [d for d in deals if d.order == ticket]
    
    if not position_deals:
        logger.warning(f"Nenhum deal encontrado para ticket {ticket}")
        return 0.0
    
    # Somar profit de TODOS os deals (IN + OUT + parciais)
    total_profit = sum(d.profit for d in position_deals)
    
    logger.info(f"Ticket {ticket}: {len(position_deals)} deals, profit=${total_profit:.2f}")
    
    return total_profit
    """)
    
    mt5.shutdown()
    print("\n✅ Análise concluída!")

if __name__ == "__main__":
    testar_leitura_deals()
