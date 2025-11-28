import MetaTrader5 as mt5
import sqlite3
from datetime import datetime, timedelta

print("\n" + "="*80)
print("CORREÇÃO: Recalcular profits de trades fechados usando history_deals_get")
print("="*80 + "\n")

# Conectar MT5
if not mt5.initialize():
    print("❌ Erro ao inicializar MT5")
    exit(1)

# Conectar banco
conn = sqlite3.connect('data/strategy_stats.db')
c = conn.cursor()

# Buscar todos os trades fechados com profit = 0 ou NULL
c.execute("""
    SELECT id, ticket, strategy_name, open_time, close_time, profit, status
    FROM strategy_trades
    WHERE (profit IS NULL OR profit = 0.0)
      AND close_time IS NOT NULL
      AND status = 'closed'
    ORDER BY close_time DESC
    LIMIT 1000
""")

trades = c.fetchall()

print(f"📊 Encontrados {len(trades)} trades fechados com profit=0 ou NULL\n")
print(f"{'Ticket':<12} {'Estratégia':<20} {'Profit Antigo':<15} {'Profit Novo':<15} {'Status'}")
print("-" * 80)

corrigidos = 0
nao_encontrados = 0
sem_alteracao = 0

for trade in trades:
    db_id, ticket, strategy, open_time, close_time, old_profit, status = trade
    
    # Tentar buscar profit real do MT5 usando history_deals_get
    try:
        # Buscar nas últimas 24 horas (ou desde open_time se disponível)
        if open_time:
            try:
                start_date = datetime.fromisoformat(str(open_time).replace('Z', '+00:00'))
                start_date = start_date - timedelta(hours=1)  # 1h antes da abertura
            except:
                start_date = datetime.now() - timedelta(hours=24)
        else:
            start_date = datetime.now() - timedelta(hours=24)
        
        history_deals = mt5.history_deals_get(
            start_date,
            datetime.now(),
            position=ticket
        )
        
        if history_deals and len(history_deals) > 0:
            # Somar profit de todos os deals OUT (entry type = 1)
            total_profit = 0.0
            for deal in history_deals:
                if hasattr(deal, 'profit') and hasattr(deal, 'entry'):
                    if deal.entry == 1:  # OUT (fechamento)
                        total_profit += deal.profit
            
            # Só atualizar se o profit for diferente
            if abs(total_profit - (old_profit or 0)) > 0.01:
                c.execute("""
                    UPDATE strategy_trades
                    SET profit = ?
                    WHERE id = ?
                """, (total_profit, db_id))
                
                print(f"{ticket:<12} {strategy:<20} ${old_profit or 0:<14.2f} ${total_profit:<14.2f} ✅ Corrigido")
                corrigidos += 1
            else:
                sem_alteracao += 1
        else:
            nao_encontrados += 1
            print(f"{ticket:<12} {strategy:<20} ${old_profit or 0:<14.2f} {'N/A':<14} ⚠️ Não encontrado no MT5")
    
    except Exception as e:
        print(f"{ticket:<12} {strategy:<20} ${old_profit or 0:<14.2f} {'ERRO':<14} ❌ {type(e).__name__}")

# Commit e fechar
conn.commit()
conn.close()
mt5.shutdown()

print("\n" + "="*80)
print(f"✅ Trades corrigidos: {corrigidos}")
print(f"⚠️ Não encontrados no MT5: {nao_encontrados}")
print(f"⏭️ Sem alteração: {sem_alteracao}")
print("="*80 + "\n")

print("🔄 Reinicie o bot para que o OrderManager use o novo método!")
