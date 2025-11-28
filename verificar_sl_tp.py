"""
Script para verificar SL/TP reais nas operações
Valida se os valores configurados estão sendo aplicados corretamente
"""

import sys
import sqlite3
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from datetime import datetime, timedelta, timezone
from database.strategy_stats import StrategyStatsDB
from core.config_manager import ConfigManager
from loguru import logger


def verificar_sl_tp():
    """Verifica SL/TP dos últimos trades"""
    
    logger.info("=" * 80)
    logger.info("VERIFICAÇÃO DE SL/TP REAIS")
    logger.info("=" * 80)
    
    # Carregar config
    config = ConfigManager().config
    risk_config = config.get('risk', {})
    
    sl_pips_config = risk_config.get('stop_loss_pips', 50)
    tp_pips_config = risk_config.get('take_profit_pips', 100)
    
    logger.info(f"📋 Configuração:")
    logger.info(f"  SL esperado: {sl_pips_config} pips ($50 aprox)")
    logger.info(f"  TP esperado: {tp_pips_config} pips ($150 aprox)")
    logger.info("")
    
    # Conectar database
    stats_db = StrategyStatsDB()
    conn = sqlite3.connect(stats_db.db_path)
    cursor = conn.cursor()
    
    # Buscar últimos 50 trades
    cursor.execute("""
        SELECT 
            ticket,
            strategy_name,
            entry_price,
            sl_price,
            tp_price,
            close_price,
            profit,
            entry_type,
            status,
            open_time
        FROM strategy_trades
        ORDER BY open_time DESC
        LIMIT 50
    """)
    
    trades = cursor.fetchall()
    conn.close()
    
    if not trades:
        logger.warning("⚠️ Nenhum trade encontrado no database")
        return
    
    logger.info(f"✅ Analisando {len(trades)} trades...\n")
    
    # Análise
    discrepancias_sl = []
    discrepancias_tp = []
    sem_sl = []
    sem_tp = []
    
    for trade in trades:
        ticket, strategy, entry, sl, tp, close, profit, entry_type, status, open_time = trade
        
        # Verificar se tem SL/TP
        if sl == 0 or sl is None:
            sem_sl.append((ticket, strategy))
            continue
        
        if tp == 0 or tp is None:
            sem_tp.append((ticket, strategy))
            continue
        
        # Calcular distâncias em pips
        if entry_type == 'BUY':
            sl_pips = (entry - sl) * 10000
            tp_pips = (tp - entry) * 10000
        else:  # SELL
            sl_pips = (sl - entry) * 10000
            tp_pips = (entry - tp) * 10000
        
        # Verificar discrepâncias (tolerância de ±5 pips)
        if abs(sl_pips - sl_pips_config) > 5:
            discrepancias_sl.append({
                'ticket': ticket,
                'strategy': strategy,
                'esperado': sl_pips_config,
                'real': sl_pips,
                'diff': sl_pips - sl_pips_config
            })
        
        if abs(tp_pips - tp_pips_config) > 5:
            discrepancias_tp.append({
                'ticket': ticket,
                'strategy': strategy,
                'esperado': tp_pips_config,
                'real': tp_pips,
                'diff': tp_pips - tp_pips_config
            })
    
    # Relatório
    logger.info("📊 RESULTADOS:\n")
    
    if not discrepancias_sl and not discrepancias_tp and not sem_sl and not sem_tp:
        logger.success("✅ TODOS OS TRADES ESTÃO CORRETOS!")
        logger.success(f"   SL: {sl_pips_config} pips")
        logger.success(f"   TP: {tp_pips_config} pips")
        return
    
    if sem_sl:
        logger.error(f"❌ {len(sem_sl)} trades SEM STOP LOSS:")
        for ticket, strategy in sem_sl[:5]:
            logger.error(f"   Ticket {ticket} [{strategy}]")
        if len(sem_sl) > 5:
            logger.error(f"   ... e mais {len(sem_sl) - 5}")
        logger.error("")
    
    if sem_tp:
        logger.warning(f"⚠️ {len(sem_tp)} trades SEM TAKE PROFIT:")
        for ticket, strategy in sem_tp[:5]:
            logger.warning(f"   Ticket {ticket} [{strategy}]")
        if len(sem_tp) > 5:
            logger.warning(f"   ... e mais {len(sem_tp) - 5}")
        logger.warning("")
    
    if discrepancias_sl:
        logger.warning(f"⚠️ {len(discrepancias_sl)} discrepâncias no SL:")
        for disc in discrepancias_sl[:5]:
            logger.warning(
                f"   Ticket {disc['ticket']} [{disc['strategy']}]: "
                f"{disc['real']:.1f} pips (esperado: {disc['esperado']} pips) "
                f"[{disc['diff']:+.1f} pips]"
            )
        if len(discrepancias_sl) > 5:
            logger.warning(f"   ... e mais {len(discrepancias_sl) - 5}")
        logger.warning("")
    
    if discrepancias_tp:
        logger.warning(f"⚠️ {len(discrepancias_tp)} discrepâncias no TP:")
        for disc in discrepancias_tp[:5]:
            logger.warning(
                f"   Ticket {disc['ticket']} [{disc['strategy']}]: "
                f"{disc['real']:.1f} pips (esperado: {disc['esperado']} pips) "
                f"[{disc['diff']:+.1f} pips]"
            )
        if len(discrepancias_tp) > 5:
            logger.warning(f"   ... e mais {len(discrepancias_tp) - 5}")
    
    # Resumo
    logger.info("\n" + "=" * 80)
    logger.info("RESUMO:")
    corretos = len(trades) - len(discrepancias_sl) - len(discrepancias_tp) - len(sem_sl) - len(sem_tp)
    logger.info(f"✅ Corretos: {corretos}/{len(trades)} ({corretos/len(trades)*100:.0f}%)")
    if sem_sl or sem_tp or discrepancias_sl or discrepancias_tp:
        logger.warning(f"⚠️ Problemas: {len(sem_sl) + len(sem_tp) + len(discrepancias_sl) + len(discrepancias_tp)}")
    logger.info("=" * 80)


if __name__ == "__main__":
    verificar_sl_tp()
