"""
Script para Corrigir Trades Antigos
Busca trades com close_time=NULL e tenta recuperar dados do histórico MT5
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

import sqlite3
from datetime import datetime, timedelta, timezone
import MetaTrader5 as mt5
from loguru import logger

logger.add("logs/corrigir_trades.log", rotation="10 MB")

print("=" * 80)
print("🔧 CORREÇÃO DE TRADES ANTIGOS")
print("=" * 80)

# Conectar MT5
print("\n1️⃣ Conectando ao MT5...")
if not mt5.initialize():
    print("❌ Falha ao inicializar MT5")
    sys.exit(1)

print(f"✅ MT5 conectado")

# Conectar banco
print("\n2️⃣ Conectando ao banco de dados...")
conn = sqlite3.connect('data/strategy_stats.db')
cursor = conn.cursor()

# Buscar trades com close_time NULL
cursor.execute("""
    SELECT ticket, strategy_name, open_time, open_price, type
    FROM strategy_trades
    WHERE close_time IS NULL
    ORDER BY open_time DESC
""")

trades_null = cursor.fetchall()
print(f"✅ Encontrados {len(trades_null)} trades com close_time=NULL")

# Estatísticas
corrigidos = 0
nao_encontrados = 0
erros = 0

print("\n3️⃣ Processando trades...")
print("-" * 80)

for ticket, strategy, open_time_str, open_price, trade_type in trades_null[:100]:  # Limitar a 100 por vez
    try:
        # Converter open_time
        if isinstance(open_time_str, str):
            open_time = datetime.fromisoformat(open_time_str.replace('Z', '+00:00'))
        else:
            open_time = datetime.fromtimestamp(open_time_str, tz=timezone.utc)
        
        # Buscar no histórico MT5 (últimos 30 dias)
        start_time = open_time
        end_time = datetime.now(timezone.utc)
        
        # Buscar ordens associadas a essa posição
        history = mt5.history_orders_get(
            start_time,
            end_time,
            position=ticket
        )
        
        if history and len(history) > 0:
            # Encontrou no histórico!
            total_profit = 0.0
            close_price = 0
            close_time = None
            
            for order in history:
                if hasattr(order, 'profit'):
                    total_profit += order.profit
                if hasattr(order, 'price_current') and order.price_current > 0:
                    close_price = order.price_current
                if hasattr(order, 'time_done') and order.time_done > 0:
                    close_time = datetime.fromtimestamp(order.time_done, tz=timezone.utc)
            
            # Atualizar banco
            if close_time:
                cursor.execute("""
                    UPDATE strategy_trades
                    SET close_price = ?, close_time = ?, profit = ?, status = 'closed'
                    WHERE ticket = ?
                """, (close_price or open_price, close_time, total_profit, ticket))
                
                emoji = "🟢" if total_profit > 0 else "🔴"
                print(f"{emoji} #{ticket} ({strategy}): ${total_profit:.2f} - {close_time.strftime('%Y-%m-%d %H:%M')}")
                corrigidos += 1
            else:
                # Encontrou ordens mas sem time_done
                nao_encontrados += 1
        else:
            # Não encontrou no histórico
            # Marcar como 'lost_data' para não tentar novamente
            cursor.execute("""
                UPDATE strategy_trades
                SET status = 'lost_data'
                WHERE ticket = ?
            """, (ticket,))
            nao_encontrados += 1
    
    except Exception as e:
        logger.error(f"Erro ao processar ticket {ticket}: {e}")
        erros += 1

# Commit
conn.commit()
print("-" * 80)
print(f"\n4️⃣ RESUMO:")
print(f"   ✅ Corrigidos: {corrigidos}")
print(f"   ⚠️ Não encontrados: {nao_encontrados}")
print(f"   ❌ Erros: {erros}")

# Verificar resultado
cursor.execute("SELECT COUNT(*) FROM strategy_trades WHERE close_time IS NOT NULL")
total_com_close = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM strategy_trades WHERE close_time IS NULL AND status != 'lost_data'")
total_sem_close = cursor.fetchone()[0]

print(f"\n5️⃣ ESTADO FINAL DO BANCO:")
print(f"   📊 Trades com close_time: {total_com_close}")
print(f"   📊 Trades ainda sem close_time: {total_sem_close}")

conn.close()
mt5.shutdown()

print("\n" + "=" * 80)
print("✅ CORREÇÃO CONCLUÍDA!")
print("=" * 80)
