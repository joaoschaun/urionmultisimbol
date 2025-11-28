"""
Script para verificar se SL ($50) e TP ($150) estão sendo aplicados corretamente
nas operações reais do MT5.
"""

import MetaTrader5 as mt5
import sqlite3
from datetime import datetime

def verificar_sl_tp():
    """Verifica últimos 50 trades e compara SL/TP esperados vs reais"""
    
    # Conectar MT5
    if not mt5.initialize():
        print(f"❌ Erro ao conectar MT5: {mt5.last_error()}")
        return
    
    print("✅ Conectado ao MT5\n")
    
    # Buscar últimos 50 trades do banco
    conn = sqlite3.connect('data/strategy_stats.db')
    cursor = conn.cursor()
    
    query = """
        SELECT ticket, strategy_name, open_time, close_time, open_price, 
               close_price, tp, sl, volume, profit, type
        FROM strategy_trades 
        WHERE close_time IS NOT NULL
        ORDER BY close_time DESC 
        LIMIT 50
    """
    
    cursor.execute(query)
    trades = cursor.fetchall()
    
    if not trades:
        print("⚠️ Nenhum trade fechado encontrado no banco")
        conn.close()
        return
    
    print(f"📊 Analisando {len(trades)} trades fechados...\n")
    
    # Analisar cada trade
    discrepancias = []
    sl_corretos = 0
    tp_corretos = 0
    
    for trade in trades:
        ticket, strategy, open_time, close_time, entry, exit, tp, sl, volume, profit, trade_type = trade
        
        # Calcular SL/TP esperados
        if trade_type == 'BUY':
            sl_esperado = entry - 50  # $50 abaixo do entry
            tp_esperado = entry + 150  # $150 acima do entry
        else:  # SELL
            sl_esperado = entry + 50  # $50 acima do entry
            tp_esperado = entry - 150  # $150 abaixo do entry
        
        # Verificar discrepâncias (tolerância de $2 por spread/slippage)
        sl_diff = abs(sl - sl_esperado) if sl else 999
        tp_diff = abs(tp - tp_esperado) if tp else 999
        
        if sl_diff <= 2:
            sl_corretos += 1
        else:
            discrepancias.append({
                'ticket': ticket,
                'strategy': strategy,
                'tipo': 'SL',
                'esperado': sl_esperado,
                'real': sl,
                'diferenca': sl_diff
            })
        
        if tp_diff <= 2:
            tp_corretos += 1
        else:
            discrepancias.append({
                'ticket': ticket,
                'strategy': strategy,
                'tipo': 'TP',
                'esperado': tp_esperado,
                'real': tp,
                'diferenca': tp_diff
            })
    
    # Relatório
    print("=" * 70)
    print("📈 RESULTADO DA ANÁLISE SL/TP")
    print("=" * 70)
    print(f"\nTrades analisados: {len(trades)}")
    print(f"✅ SL corretos: {sl_corretos}/{len(trades)} ({sl_corretos/len(trades)*100:.1f}%)")
    print(f"✅ TP corretos: {tp_corretos}/{len(trades)} ({tp_corretos/len(trades)*100:.1f}%)")
    
    if discrepancias:
        print(f"\n⚠️ {len(discrepancias)} discrepâncias encontradas:\n")
        for disc in discrepancias[:10]:  # Mostrar primeiras 10
            print(f"  Ticket: {disc['ticket']} | {disc['strategy']}")
            print(f"  Tipo: {disc['tipo']}")
            print(f"  Esperado: ${disc['esperado']:.2f}")
            print(f"  Real: ${disc['real']:.2f}")
            print(f"  Diferença: ${disc['diferenca']:.2f}")
            print()
    else:
        print("\n✅ Nenhuma discrepância encontrada! SL/TP configurados corretamente.")
    
    conn.close()
    mt5.shutdown()
    print("\n✅ Análise concluída!")

if __name__ == "__main__":
    verificar_sl_tp()
