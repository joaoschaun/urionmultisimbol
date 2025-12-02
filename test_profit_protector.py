"""
Teste do ProfitProtector
"""
import sys
sys.path.insert(0, 'src')

from core.profit_protector import ProfitProtector

# Criar instância
pp = ProfitProtector({})

print("=== TESTE PROFIT PROTECTOR ===\n")

# Simular uma posição BUY
position = {
    'ticket': 12345,
    'symbol': 'EURUSD',
    'type': 'BUY',
    'price_open': 1.05000,
    'price_current': 1.05100,  # +10 pips
    'sl': 1.04900,  # -10 pips (risco = $100)
    'volume': 0.1,
    'profit': 100.0  # $100 de lucro = 1R
}

# 1. Primeiro update
result = pp.analyze_position(12345, position)
print(f"1. Lucro: ${position['profit']:.2f}")
print(f"   RR: {result['current_rr']:.2f}")
print(f"   Level: {result['protection_level']}")
print()

# 2. Simular lucro maior (+2R)
position['price_current'] = 1.05200
position['profit'] = 200.0
result = pp.analyze_position(12345, position)
print(f"2. Lucro aumentou: ${position['profit']:.2f}")
print(f"   RR: {result['current_rr']:.2f}")
print(f"   Level: {result['protection_level']}")
print(f"   Action: {result['action']}")
print(f"   Protected: ${result['protected_profit']:.2f}")
print()

# 3. Simular recuo de lucro (de 200 para 140 = -30%)
position['price_current'] = 1.05140
position['profit'] = 140.0
result = pp.analyze_position(12345, position)
print(f"3. Lucro recuou: ${position['profit']:.2f} (-30%)")
print(f"   Action: {result['action']}")
print(f"   Reason: {result['reason']}")
print()

# Status final
status = pp.get_protection_status(12345)
print("Status Final:")
print(f"  Max Profit: ${status['max_profit']:.2f}")
print(f"  Current RR: {status['current_rr']:.2f}")
print(f"  Max RR: {status['max_rr']:.2f}")
print(f"  Level: {status['protection_level']}")
print(f"  Protected: ${status['protected_profit']:.2f}")
print(f"  Drawdown: {status['drawdown_from_max']:.1f}%")

print("\n✅ TESTE CONCLUÍDO!")
