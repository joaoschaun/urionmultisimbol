import sqlite3

print("\n" + "="*80)
print("🔧 CORREÇÃO: Recalcular signal_confidence no banco de dados")
print("="*80 + "\n")

conn = sqlite3.connect('data/strategy_stats.db')
c = conn.cursor()

# Verificar situação atual
c.execute("""
    SELECT 
        COUNT(*) as total,
        MIN(signal_confidence) as min_conf,
        MAX(signal_confidence) as max_conf,
        AVG(signal_confidence) as avg_conf
    FROM strategy_trades
    WHERE signal_confidence IS NOT NULL
""")

row = c.fetchone()
print(f"📊 ANTES DA CORREÇÃO:")
print(f"   Total registros: {row[0]}")
print(f"   Confidence MIN: {row[1]:.2f}")
print(f"   Confidence MAX: {row[2]:.2f}")
print(f"   Confidence AVG: {row[3]:.2f}")
print()

# Corrigir: dividir por 100 se > 1
print("🔧 Aplicando correção: signal_confidence / 100 onde > 1.0\n")

c.execute("""
    UPDATE strategy_trades
    SET signal_confidence = signal_confidence / 100.0
    WHERE signal_confidence > 1.0
""")

affected = c.rowcount
print(f"✅ {affected} registros corrigidos\n")

# Verificar após correção
c.execute("""
    SELECT 
        COUNT(*) as total,
        MIN(signal_confidence) as min_conf,
        MAX(signal_confidence) as max_conf,
        AVG(signal_confidence) as avg_conf
    FROM strategy_trades
    WHERE signal_confidence IS NOT NULL
""")

row = c.fetchone()
print(f"📊 APÓS CORREÇÃO:")
print(f"   Total registros: {row[0]}")
print(f"   Confidence MIN: {row[1]:.4f} ({row[1]*100:.2f}%)")
print(f"   Confidence MAX: {row[2]:.4f} ({row[2]*100:.2f}%)")
print(f"   Confidence AVG: {row[3]:.4f} ({row[3]*100:.2f}%)")
print()

conn.commit()
conn.close()

print("="*80)
print("✅ CORREÇÃO COMPLETA!")
print("="*80 + "\n")
