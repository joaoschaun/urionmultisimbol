"""
Análise completa do sistema para verificar se está tudo correto
"""

import MetaTrader5 as mt5
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path

def verificar_conexao_mt5():
    """Verifica conexão com MT5"""
    print("=" * 80)
    print("1. VERIFICANDO CONEXÃO MT5")
    print("=" * 80)
    
    if not mt5.initialize():
        print(f"❌ Erro ao conectar MT5: {mt5.last_error()}")
        return False
    
    account_info = mt5.account_info()
    print(f"✅ Conectado ao MT5")
    print(f"   Conta: {account_info.login}")
    print(f"   Servidor: {account_info.server}")
    print(f"   Balance: ${account_info.balance:.2f}")
    print(f"   Equity: ${account_info.equity:.2f}")
    print(f"   Margin Free: ${account_info.margin_free:.2f}")
    return True

def verificar_database():
    """Verifica estrutura e dados do database"""
    print("\n" + "=" * 80)
    print("2. VERIFICANDO DATABASE")
    print("=" * 80)
    
    db_path = Path('data/strategy_stats.db')
    if not db_path.exists():
        print("❌ Database não encontrado!")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Contar trades
    cursor.execute("SELECT COUNT(*) FROM strategy_trades WHERE close_time IS NOT NULL")
    total_trades = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM strategy_trades WHERE close_time IS NULL")
    open_trades = cursor.fetchone()[0]
    
    print(f"✅ Database OK")
    print(f"   Trades fechados: {total_trades}")
    print(f"   Trades abertos: {open_trades}")
    
    # Últimos 5 trades
    print(f"\n   📊 Últimos 5 trades fechados:")
    cursor.execute("""
        SELECT ticket, strategy_name, open_price, close_price, profit, close_time
        FROM strategy_trades
        WHERE close_time IS NOT NULL
        ORDER BY close_time DESC
        LIMIT 5
    """)
    
    for trade in cursor.fetchall():
        ticket, strategy, open_p, close_p, profit, close_time = trade
        print(f"      Ticket {ticket} | {strategy} | Profit: ${profit:.2f} | {close_time}")
    
    conn.close()
    return True

def verificar_learning_data():
    """Verifica dados de aprendizado ML"""
    print("\n" + "=" * 80)
    print("3. VERIFICANDO ML LEARNING DATA")
    print("=" * 80)
    
    learning_path = Path('data/learning_data.json')
    if not learning_path.exists():
        print("⚠️ Arquivo learning_data.json não existe ainda")
        return True
    
    with open(learning_path, 'r') as f:
        data = json.load(f)
    
    if not data:
        print("✅ Learning data limpo (aguardando novos trades)")
        return True
    
    print(f"✅ Learning data carregado")
    for strategy, info in data.items():
        total = info.get('total_trades', 0)
        wins = info.get('wins', 0)
        losses = info.get('losses', 0)
        win_rate = wins / total * 100 if total > 0 else 0
        min_conf = info.get('min_confidence', 0.5)
        
        print(f"\n   📈 {strategy}:")
        print(f"      Trades: {total} | Wins: {wins} | Losses: {losses}")
        print(f"      Win Rate: {win_rate:.1f}%")
        print(f"      Min Confidence: {min_conf:.2f}")
    
    return True

def verificar_discrepancias_profit():
    """Verifica se há discrepâncias entre DB e MT5"""
    print("\n" + "=" * 80)
    print("4. VERIFICANDO DISCREPÂNCIAS DE PROFIT (DB vs MT5)")
    print("=" * 80)
    
    conn = sqlite3.connect('data/strategy_stats.db')
    cursor = conn.cursor()
    
    # Buscar últimos 10 trades fechados
    cursor.execute("""
        SELECT ticket, strategy_name, profit, close_time
        FROM strategy_trades
        WHERE close_time IS NOT NULL
        ORDER BY close_time DESC
        LIMIT 10
    """)
    
    trades_db = cursor.fetchall()
    conn.close()
    
    if not trades_db:
        print("⚠️ Nenhum trade fechado para verificar")
        return True
    
    discrepancias = []
    
    for ticket, strategy, profit_db, close_time in trades_db:
        # Buscar deal no MT5
        from_date = datetime.now() - timedelta(days=7)
        deals = mt5.history_deals_get(from_date, datetime.now())
        
        if not deals:
            continue
        
        # Encontrar deal de saída deste ticket
        deal_exit = None
        for deal in deals:
            if deal.position_id == ticket and deal.entry == 1:  # Entry 1 = saída
                deal_exit = deal
                break
        
        if deal_exit:
            profit_mt5 = deal_exit.profit + deal_exit.commission + deal_exit.swap
            diff = abs(profit_db - profit_mt5)
            
            if diff > 0.5:  # Tolerância de $0.50
                discrepancias.append({
                    'ticket': ticket,
                    'strategy': strategy,
                    'profit_db': profit_db,
                    'profit_mt5': profit_mt5,
                    'diferenca': diff
                })
    
    if discrepancias:
        print(f"⚠️ {len(discrepancias)} discrepâncias encontradas:")
        for disc in discrepancias[:5]:
            print(f"\n   Ticket: {disc['ticket']} | {disc['strategy']}")
            print(f"   DB: ${disc['profit_db']:.2f}")
            print(f"   MT5: ${disc['profit_mt5']:.2f}")
            print(f"   Diferença: ${disc['diferenca']:.2f}")
        return False
    else:
        print("✅ Nenhuma discrepância encontrada! Profits estão corretos.")
        return True

def verificar_configuracoes():
    """Verifica configurações importantes"""
    print("\n" + "=" * 80)
    print("5. VERIFICANDO CONFIGURAÇÕES")
    print("=" * 80)
    
    config_path = Path('config/config.yaml')
    if not config_path.exists():
        print("❌ Config.yaml não encontrado!")
        return False
    
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Verificar configurações críticas
    checks = {
        'market_analysis enabled': 'enabled: true' in content and 'market_analysis' in content,
        'reporting enabled': 'reporting:' in content,
        'min_confidence configurado': 'min_confidence:' in content,
    }
    
    for check, status in checks.items():
        status_icon = "✅" if status else "⚠️"
        print(f"   {status_icon} {check}")
    
    return all(checks.values())

def verificar_posicoes_abertas():
    """Verifica posições atualmente abertas"""
    print("\n" + "=" * 80)
    print("6. VERIFICANDO POSIÇÕES ABERTAS")
    print("=" * 80)
    
    positions = mt5.positions_get(symbol="XAUUSD")
    
    if not positions:
        print("✅ Nenhuma posição aberta no momento")
        return True
    
    print(f"📊 {len(positions)} posição(ões) aberta(s):")
    
    for pos in positions:
        profit = pos.profit + pos.commission + pos.swap
        print(f"\n   Ticket: {pos.ticket}")
        print(f"   Tipo: {'BUY' if pos.type == 0 else 'SELL'}")
        print(f"   Volume: {pos.volume}")
        print(f"   Entry: ${pos.price_open:.2f}")
        print(f"   Current: ${pos.price_current:.2f}")
        print(f"   SL: ${pos.sl:.2f}")
        print(f"   TP: ${pos.tp:.2f}")
        print(f"   Profit: ${profit:.2f}")
        print(f"   Magic: {pos.magic}")
    
    return True

def verificar_arquivos_criticos():
    """Verifica se todos os arquivos críticos existem"""
    print("\n" + "=" * 80)
    print("7. VERIFICANDO ARQUIVOS CRÍTICOS")
    print("=" * 80)
    
    arquivos = {
        'main.py': Path('main.py'),
        'order_manager.py': Path('src/order_manager.py'),
        'order_generator.py': Path('src/order_generator.py'),
        'strategy_executor.py': Path('src/core/strategy_executor.py'),
        'market_condition_analyzer.py': Path('src/analysis/market_condition_analyzer.py'),
        'strategy_learner.py': Path('src/ml/strategy_learner.py'),
        'config.yaml': Path('config/config.yaml'),
        'database': Path('data/strategy_stats.db'),
    }
    
    todos_ok = True
    for nome, path in arquivos.items():
        if path.exists():
            print(f"   ✅ {nome}")
        else:
            print(f"   ❌ {nome} - NÃO ENCONTRADO!")
            todos_ok = False
    
    return todos_ok

def main():
    """Executa análise completa"""
    print("\n" + "=" * 80)
    print("🔍 ANÁLISE COMPLETA DO SISTEMA URION")
    print("=" * 80)
    print(f"Data/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80 + "\n")
    
    resultados = []
    
    # 1. Verificar MT5
    resultados.append(("Conexão MT5", verificar_conexao_mt5()))
    
    # 2. Verificar Database
    resultados.append(("Database", verificar_database()))
    
    # 3. Verificar Learning Data
    resultados.append(("ML Learning", verificar_learning_data()))
    
    # 4. Verificar Discrepâncias
    resultados.append(("Profits DB vs MT5", verificar_discrepancias_profit()))
    
    # 5. Verificar Configurações
    resultados.append(("Configurações", verificar_configuracoes()))
    
    # 6. Verificar Posições
    resultados.append(("Posições Abertas", verificar_posicoes_abertas()))
    
    # 7. Verificar Arquivos
    resultados.append(("Arquivos Críticos", verificar_arquivos_criticos()))
    
    # Resumo final
    print("\n" + "=" * 80)
    print("📋 RESUMO DA ANÁLISE")
    print("=" * 80)
    
    total_checks = len(resultados)
    passed_checks = sum(1 for _, status in resultados if status)
    
    for nome, status in resultados:
        status_icon = "✅" if status else "❌"
        print(f"{status_icon} {nome}")
    
    print("\n" + "=" * 80)
    if passed_checks == total_checks:
        print("🎉 SISTEMA 100% OK! Tudo funcionando corretamente.")
    else:
        print(f"⚠️ {total_checks - passed_checks} problema(s) encontrado(s).")
    print("=" * 80)
    
    mt5.shutdown()

if __name__ == "__main__":
    main()
