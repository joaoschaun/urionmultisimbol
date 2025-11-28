"""
Script para corrigir close_prices ausentes no database
Busca os preços de fechamento reais no histórico do MT5
"""

import sqlite3
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

def conectar_mt5():
    """Conecta ao MT5"""
    if not mt5.initialize():
        print("❌ Erro ao inicializar MT5")
        return False
    
    login = int(os.getenv('MT5_LOGIN'))
    password = os.getenv('MT5_PASSWORD')
    server = os.getenv('MT5_SERVER')
    
    if not mt5.login(login, password, server):
        print(f"❌ Erro ao fazer login: {mt5.last_error()}")
        mt5.shutdown()
        return False
    
    return True


def corrigir_close_prices():
    """Corrige close_prices ausentes buscando no histórico MT5"""
    
    # Conectar MT5
    print("🔌 Conectando ao MT5...")
    if not conectar_mt5():
        return
    
    print("✅ MT5 conectado\n")
    
    # Conectar database
    conn = sqlite3.connect('data/strategy_stats.db')
    cursor = conn.cursor()
    
    # Buscar trades fechados sem close_price
    cursor.execute("""
        SELECT ticket, strategy_name, type, open_price, sl, tp, profit, close_time
        FROM strategy_trades
        WHERE status = 'closed' 
          AND (close_price IS NULL OR close_price = 0)
        ORDER BY id DESC
    """)
    
    trades_sem_close = cursor.fetchall()
    
    print(f"📊 Encontrados {len(trades_sem_close)} trades sem close_price\n")
    
    if not trades_sem_close:
        print("✅ Nenhum trade precisa de correção!")
        conn.close()
        return
    
    corrigidos = 0
    nao_encontrados = 0
    
    for trade in trades_sem_close:
        ticket, strategy, tipo, open_price, sl, tp, profit, close_time = trade
        
        try:
            # Buscar deals da posição (últimos 30 dias)
            deals = mt5.history_deals_get(
                datetime.now() - timedelta(days=30),
                datetime.now(),
                position=ticket
            )
            
            if deals and len(deals) > 0:
                # Procurar último deal OUT (fechamento)
                close_deals = [d for d in deals if hasattr(d, 'entry') and d.entry == 1]
                
                if close_deals:
                    last_close = close_deals[-1]
                    close_price = last_close.price
                    
                    # Atualizar database
                    cursor.execute("""
                        UPDATE strategy_trades
                        SET close_price = ?
                        WHERE ticket = ?
                    """, (close_price, ticket))
                    
                    print(f"✅ {ticket:12} [{strategy:16}] Close: {close_price:.2f} (Profit: ${profit:.2f})")
                    corrigidos += 1
                else:
                    print(f"⚠️  {ticket:12} [{strategy:16}] Sem deal OUT no histórico")
                    nao_encontrados += 1
            else:
                print(f"⚠️  {ticket:12} [{strategy:16}] Sem deals no histórico MT5")
                nao_encontrados += 1
                
        except Exception as e:
            print(f"❌ {ticket:12} Erro: {e}")
            nao_encontrados += 1
    
    # Commit e fechar
    conn.commit()
    conn.close()
    mt5.shutdown()
    
    print("\n" + "="*80)
    print(f"✅ Corrigidos: {corrigidos}")
    print(f"⚠️  Não encontrados: {nao_encontrados}")
    print(f"📊 Total processados: {len(trades_sem_close)}")
    print("="*80)

if __name__ == "__main__":
    corrigir_close_prices()
