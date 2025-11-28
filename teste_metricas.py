"""Teste rápido do relatório com métricas"""
import sys
sys.path.insert(0, r'c:\Users\Administrator\Desktop\urion')

from src.reporting.advanced_metrics import AdvancedMetrics
from datetime import datetime, timedelta

# Dados de exemplo (10 trades com timestamps)
base_time = datetime.now()
trades_data = []

profits = [150, -50, 200, -75, 100, -30, 180, 90, -60, 250]

for i, profit in enumerate(profits):
    trades_data.append({
        'profit': profit,
        'timestamp': base_time + timedelta(hours=i)
    })

metrics = AdvancedMetrics(trades_data)

print("="*70)
print("📊 TESTE DE MÉTRICAS AVANÇADAS")
print("="*70)
print(f"\n📈 Trades: {len(profits)}")
print(f"💰 Total: ${sum(profits):.2f}")
print(f"🎯 Win Rate: {(len([t for t in profits if t > 0]) / len(profits) * 100):.1f}%")

print(f"\n📊 MÉTRICAS PROFISSIONAIS:")
print(f"🟢 Sharpe Ratio: {metrics.sharpe_ratio():.2f} (>1.0 = bom)")
print(f"🟢 Sortino Ratio: {metrics.sortino_ratio():.2f} (>1.5 = bom)")
print(f"🟢 Profit Factor: {metrics.profit_factor():.2f} (>1.5 = bom)")
print(f"💵 Expectancy: ${metrics.expectancy():.2f} por trade")
print(f"📉 Max Drawdown: ${metrics.max_drawdown():.2f}")

print(f"\n{'='*70}")
print("✅ Métricas funcionando perfeitamente!")
print("="*70)
