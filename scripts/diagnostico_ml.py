"""
Diagnóstico completo do sistema de ML e logs
"""
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import json

print("\n" + "="*80)
print("🔍 DIAGNÓSTICO DO SISTEMA DE ML E APRENDIZAGEM")
print("="*80)

# 1. Verificar database
db_path = Path("data/strategy_stats.db")
print(f"\n📊 DATABASE: {db_path}")
print(f"   Existe: {'✅ SIM' if db_path.exists() else '❌ NÃO'}")

if db_path.exists():
    print(f"   Tamanho: {db_path.stat().st_size / 1024:.2f} KB")
    print(f"   Última modificação: {datetime.fromtimestamp(db_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Conectar e verificar trades
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Total de trades
        cursor.execute("SELECT COUNT(*) FROM strategy_trades")
        total_trades = cursor.fetchone()[0]
        print(f"\n   📈 Total de Trades Salvos: {total_trades}")
        
        # Trades por estratégia
        cursor.execute("""
            SELECT strategy_name, COUNT(*), 
                   SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
                   SUM(CASE WHEN profit <= 0 THEN 1 ELSE 0 END) as losses,
                   SUM(profit) as total_profit
            FROM strategy_trades
            WHERE status = 'closed'
            GROUP BY strategy_name
        """)
        
        print("\n   📊 TRADES POR ESTRATÉGIA:")
        for row in cursor.fetchall():
            strategy, count, wins, losses, profit = row
            win_rate = (wins / count * 100) if count > 0 else 0
            print(f"      {strategy}:")
            print(f"         Total: {count} | Wins: {wins} | Losses: {losses}")
            print(f"         Win Rate: {win_rate:.1f}% | Profit: ${profit:.2f}")
        
        # Últimos 10 trades
        cursor.execute("""
            SELECT strategy_name, ticket, profit, signal_confidence, 
                   datetime(close_time, 'unixepoch', 'localtime')
            FROM strategy_trades
            WHERE status = 'closed'
            ORDER BY close_time DESC
            LIMIT 10
        """)
        
        print("\n   📜 ÚLTIMOS 10 TRADES:")
        recent_trades = cursor.fetchall()
        if recent_trades:
            for trade in recent_trades:
                strategy, ticket, profit, conf, close_time = trade
                emoji = "✅" if profit > 0 else "❌"
                print(f"      {emoji} {strategy} | Ticket: {ticket} | ${profit:.2f} | Conf: {conf:.2f} | {close_time}")
        else:
            print("      ⚠️ Nenhum trade fechado ainda")
        
        conn.close()
        
    except Exception as e:
        print(f"   ❌ Erro ao ler database: {e}")

# 2. Verificar learning_data.json
learning_path = Path("data/learning_data.json")
print(f"\n🧠 LEARNING DATA: {learning_path}")
print(f"   Existe: {'✅ SIM' if learning_path.exists() else '❌ NÃO'}")

if learning_path.exists():
    print(f"   Tamanho: {learning_path.stat().st_size} bytes")
    print(f"   Última modificação: {datetime.fromtimestamp(learning_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        with open(learning_path, 'r') as f:
            learning_data = json.load(f)
        
        print(f"\n   📚 DADOS DE APRENDIZAGEM:")
        if learning_data:
            for strategy, data in learning_data.items():
                print(f"\n      {strategy}:")
                print(f"         Total Trades: {data.get('total_trades', 0)}")
                print(f"         Wins: {data.get('wins', 0)} | Losses: {data.get('losses', 0)}")
                if data.get('total_trades', 0) > 0:
                    wr = data.get('wins', 0) / data.get('total_trades', 1) * 100
                    print(f"         Win Rate: {wr:.1f}%")
                print(f"         Min Confidence: {data.get('min_confidence', 0):.2f}")
                print(f"         Último Ajuste: {data.get('last_adjustment', 'Nunca')}")
                print(f"         Melhores Condições: {len(data.get('best_conditions', []))} registradas")
        else:
            print("      ⚠️ Arquivo vazio - bot ainda não aprendeu nada")
    
    except Exception as e:
        print(f"   ❌ Erro ao ler learning_data: {e}")

# 3. Verificar logs
log_path = Path("logs/urion.log")
print(f"\n📝 LOGS: {log_path}")
print(f"   Existe: {'✅ SIM' if log_path.exists() else '❌ NÃO'}")

if log_path.exists():
    print(f"   Tamanho: {log_path.stat().st_size / 1024:.2f} KB")
    last_mod = datetime.fromtimestamp(log_path.stat().st_mtime)
    print(f"   Última modificação: {last_mod.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Verificar se está desatualizado
    age = (datetime.now() - last_mod).total_seconds()
    if age > 300:  # Mais de 5 minutos
        print(f"   ⚠️ LOG DESATUALIZADO! ({age/60:.1f} minutos atrás)")
        print("      Bot pode estar travado ou crashado")
    else:
        print(f"   ✅ Log atualizado (há {age:.0f} segundos)")
    
    # Últimas linhas com erro
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        print("\n   🔍 ÚLTIMOS ERROS/WARNINGS:")
        error_lines = [l for l in lines[-200:] if 'ERROR' in l or 'WARNING' in l][-10:]
        if error_lines:
            for line in error_lines:
                print(f"      {line.strip()}")
        else:
            print("      ✅ Nenhum erro recente")
        
        # Verificar aprendizagem
        learn_lines = [l for l in lines if 'learn' in l.lower() or 'StrategyLearner' in l][-5:]
        print("\n   🤖 ÚLTIMAS LINHAS DE APRENDIZAGEM:")
        if learn_lines:
            for line in learn_lines:
                print(f"      {line.strip()}")
        else:
            print("      ⚠️ Nenhuma atividade de aprendizagem nos logs")
    
    except Exception as e:
        print(f"   ❌ Erro ao ler logs: {e}")

# 4. Diagnóstico final
print("\n" + "="*80)
print("📋 DIAGNÓSTICO FINAL")
print("="*80)

issues = []

if not db_path.exists():
    issues.append("❌ Database não existe - bot não está salvando trades")
elif total_trades == 0:
    issues.append("⚠️ Database existe mas sem trades - bot não operou ainda")

if not learning_path.exists():
    issues.append("⚠️ Learning data não existe - aprendizagem não iniciada")
elif not learning_data:
    issues.append("⚠️ Learning data vazio - bot ainda não aprendeu nada")

if log_path.exists() and age > 300:
    issues.append("❌ Logs desatualizados - bot provavelmente travado")

if issues:
    print("\n⚠️ PROBLEMAS ENCONTRADOS:")
    for issue in issues:
        print(f"   {issue}")
else:
    print("\n✅ SISTEMA FUNCIONANDO NORMALMENTE")

print("\n" + "="*80)
