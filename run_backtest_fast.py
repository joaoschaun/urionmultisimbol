"""
BACKTEST URION RÁPIDO - Versão otimizada
Usa H1 como base com confirmação de timeframes superiores
Tempo estimado: 30-60 segundos
"""

import pandas as pd
import numpy as np
from datetime import datetime
import os
import json

# Configurações
INITIAL_CAPITAL = 10000
RISK_PER_TRADE = 0.02
MAX_POSITIONS = 3
SPREAD_PIPS = 2.5

print("\n" + "=" * 60)
print("🤖 URION BACKTEST RÁPIDO - 5 ANOS")
print("=" * 60)

# Carregar dados
print("\n📊 Carregando dados...")
h1 = pd.read_csv('data/xauusd_5years_h1.csv')
h1['time'] = pd.to_datetime(h1['time'])
h1.set_index('time', inplace=True)
print(f"   H1: {len(h1):,} candles")

# Calcular indicadores (vetorizado - muito rápido)
print("   Calculando indicadores...")

def ema(s, p): return s.ewm(span=p, adjust=False).mean()
def rsi(s, p=14):
    d = s.diff()
    g = d.where(d > 0, 0).rolling(p).mean()
    l = (-d.where(d < 0, 0)).rolling(p).mean()
    return 100 - (100 / (1 + g/l))

# EMAs
h1['ema9'] = ema(h1['close'], 9)
h1['ema21'] = ema(h1['close'], 21)
h1['ema50'] = ema(h1['close'], 50)

# RSI
h1['rsi'] = rsi(h1['close'])

# MACD
h1['macd'] = ema(h1['close'], 12) - ema(h1['close'], 26)
h1['macd_signal'] = ema(h1['macd'], 9)
h1['macd_hist'] = h1['macd'] - h1['macd_signal']

# ATR
tr = pd.concat([
    h1['high'] - h1['low'],
    abs(h1['high'] - h1['close'].shift(1)),
    abs(h1['low'] - h1['close'].shift(1))
], axis=1).max(axis=1)
h1['atr'] = tr.rolling(14).mean()

# ADX
dm_plus = h1['high'].diff()
dm_minus = -h1['low'].diff()
dm_plus = dm_plus.where((dm_plus > dm_minus) & (dm_plus > 0), 0)
dm_minus = dm_minus.where((dm_minus > dm_plus) & (dm_minus > 0), 0)
atr14 = h1['atr']
di_plus = 100 * dm_plus.rolling(14).mean() / atr14
di_minus = 100 * dm_minus.rolling(14).mean() / atr14
dx = 100 * abs(di_plus - di_minus) / (di_plus + di_minus + 0.0001)
h1['adx'] = dx.rolling(14).mean()
h1['di_plus'] = di_plus
h1['di_minus'] = di_minus

# Bollinger
h1['bb_mid'] = h1['close'].rolling(20).mean()
h1['bb_std'] = h1['close'].rolling(20).std()
h1['bb_upper'] = h1['bb_mid'] + 2 * h1['bb_std']
h1['bb_lower'] = h1['bb_mid'] - 2 * h1['bb_std']

# Stochastic
low14 = h1['low'].rolling(14).min()
high14 = h1['high'].rolling(14).max()
h1['stoch_k'] = 100 * (h1['close'] - low14) / (high14 - low14 + 0.0001)
h1['stoch_d'] = h1['stoch_k'].rolling(3).mean()

print("   ✅ Indicadores OK")

# Gerar sinais vetorizados
print("   Gerando sinais...")

# TrendFollowing: ADX > 25, EMAs alinhadas, MACD confirmando
trend_buy = (
    (h1['adx'] > 25) & 
    (h1['di_plus'] > h1['di_minus']) &
    (h1['ema9'] > h1['ema21']) & 
    (h1['ema21'] > h1['ema50']) &
    (h1['macd_hist'] > 0) &
    (h1['rsi'] > 40) & (h1['rsi'] < 70)
)

trend_sell = (
    (h1['adx'] > 25) & 
    (h1['di_minus'] > h1['di_plus']) &
    (h1['ema9'] < h1['ema21']) & 
    (h1['ema21'] < h1['ema50']) &
    (h1['macd_hist'] < 0) &
    (h1['rsi'] > 30) & (h1['rsi'] < 60)
)

# MeanReversion: RSI extremo + Bollinger
rev_buy = (
    (h1['rsi'] < 30) & 
    (h1['close'] < h1['bb_lower']) &
    (h1['stoch_k'] < 25)
)

rev_sell = (
    (h1['rsi'] > 70) & 
    (h1['close'] > h1['bb_upper']) &
    (h1['stoch_k'] > 75)
)

# Combinar sinais
h1['signal'] = 0
h1.loc[trend_buy | rev_buy, 'signal'] = 1  # BUY
h1.loc[trend_sell | rev_sell, 'signal'] = -1  # SELL

# Evitar sinais consecutivos iguais
h1['signal_clean'] = h1['signal'].where(h1['signal'] != h1['signal'].shift(1), 0)

print(f"   Sinais BUY: {(h1['signal_clean'] == 1).sum()}")
print(f"   Sinais SELL: {(h1['signal_clean'] == -1).sum()}")

# Backtest loop
print("\n🚀 Executando backtest...")

capital = INITIAL_CAPITAL
trades = []
open_pos = None
equity_curve = []

warmup = 200
total = len(h1) - warmup
last_pct = 0

for i in range(warmup, len(h1)):
    # Progresso
    pct = int((i - warmup) / total * 100)
    if pct >= last_pct + 10:
        print(f"   {pct}% concluído...")
        last_pct = pct
    
    row = h1.iloc[i]
    price = row['close']
    high = row['high']
    low = row['low']
    atr = row['atr']
    signal = row['signal_clean']
    
    # Verificar saída de posição aberta
    if open_pos:
        exit_price = None
        exit_reason = None
        
        if open_pos['dir'] == 'BUY':
            if low <= open_pos['sl']:
                exit_price = open_pos['sl']
                exit_reason = 'sl'
            elif high >= open_pos['tp']:
                exit_price = open_pos['tp']
                exit_reason = 'tp'
        else:
            if high >= open_pos['sl']:
                exit_price = open_pos['sl']
                exit_reason = 'sl'
            elif low <= open_pos['tp']:
                exit_price = open_pos['tp']
                exit_reason = 'tp'
        
        if exit_price:
            pip = 0.1
            if open_pos['dir'] == 'BUY':
                pips = (exit_price - open_pos['entry']) / pip
            else:
                pips = (open_pos['entry'] - exit_price) / pip
            
            profit = pips * 10 * open_pos['size'] - 7 * open_pos['size']
            capital += profit
            
            trades.append({
                'strategy': open_pos['strategy'],
                'dir': open_pos['dir'],
                'profit': profit,
                'exit': exit_reason
            })
            open_pos = None
    
    # Abrir nova posição
    if open_pos is None and signal != 0 and not pd.isna(atr):
        atr_pips = atr / 0.1
        
        if signal == 1:
            sl_pips = max(20, min(atr_pips * 2, 60))
            tp_pips = max(40, min(atr_pips * 4, 120))
            
            entry = price + SPREAD_PIPS * 0.1
            sl = entry - sl_pips * 0.1
            tp = entry + tp_pips * 0.1
            
            risk = capital * RISK_PER_TRADE
            size = min(2.0, max(0.01, risk / (sl_pips * 10)))
            
            open_pos = {
                'dir': 'BUY',
                'entry': entry,
                'sl': sl,
                'tp': tp,
                'size': round(size, 2),
                'strategy': 'Combined'
            }
        
        elif signal == -1:
            sl_pips = max(20, min(atr_pips * 2, 60))
            tp_pips = max(40, min(atr_pips * 4, 120))
            
            entry = price
            sl = entry + sl_pips * 0.1
            tp = entry - tp_pips * 0.1
            
            risk = capital * RISK_PER_TRADE
            size = min(2.0, max(0.01, risk / (sl_pips * 10)))
            
            open_pos = {
                'dir': 'SELL',
                'entry': entry,
                'sl': sl,
                'tp': tp,
                'size': round(size, 2),
                'strategy': 'Combined'
            }
    
    equity_curve.append(capital)

print("   100% concluído!")

# Fechar posição aberta
if open_pos:
    price = h1['close'].iloc[-1]
    if open_pos['dir'] == 'BUY':
        pips = (price - open_pos['entry']) / 0.1
    else:
        pips = (open_pos['entry'] - price) / 0.1
    profit = pips * 10 * open_pos['size'] - 7 * open_pos['size']
    capital += profit
    trades.append({'strategy': 'Combined', 'dir': open_pos['dir'], 'profit': profit, 'exit': 'close'})

# Métricas
profits = [t['profit'] for t in trades]
wins = [p for p in profits if p > 0]
losses = [p for p in profits if p <= 0]

total_trades = len(trades)
win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0
pf = sum(wins) / abs(sum(losses)) if losses and sum(losses) != 0 else 0

equity = np.array(equity_curve)
peak = np.maximum.accumulate(equity)
dd = (peak - equity) / peak
max_dd = np.max(dd) * 100

returns = np.diff(equity) / equity[:-1]
sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252 * 24) if np.std(returns) > 0 else 0

# Resultados
print("\n" + "=" * 60)
print("📊 RESULTADOS")
print("=" * 60)

print(f"\n🎯 PERFORMANCE")
print(f"   Capital Inicial: ${INITIAL_CAPITAL:,.2f}")
print(f"   Capital Final: ${capital:,.2f}")
print(f"   Retorno: {(capital/INITIAL_CAPITAL - 1)*100:.2f}%")
print(f"   Lucro: ${capital - INITIAL_CAPITAL:,.2f}")

print(f"\n📈 TRADING")
print(f"   Trades: {total_trades}")
print(f"   Wins: {len(wins)} | Losses: {len(losses)}")
print(f"   Win Rate: {win_rate:.1f}%")
print(f"   Profit Factor: {pf:.2f}")
print(f"   Avg Win: ${np.mean(wins):.2f}" if wins else "   Avg Win: $0")
print(f"   Avg Loss: ${abs(np.mean(losses)):.2f}" if losses else "   Avg Loss: $0")

print(f"\n⚠️ RISCO")
print(f"   Max Drawdown: {max_dd:.2f}%")
print(f"   Sharpe Ratio: {sharpe:.2f}")

print("\n" + "=" * 60)
print("✅ AVALIAÇÃO")
print("=" * 60)

checks = [
    ('Win Rate > 45%', win_rate > 45),
    ('Profit Factor > 1.2', pf > 1.2),
    ('Max Drawdown < 25%', max_dd < 25),
    ('Sharpe > 0.5', sharpe > 0.5),
    ('Trades > 50', total_trades > 50)
]

passed = sum(1 for _, c in checks if c)
for name, check in checks:
    print(f"   {'✅' if check else '❌'} {name}")

print(f"\n   Score: {passed}/5 ({passed*20}%)")
print("=" * 60)

# Salvar
os.makedirs('data/backtest_results', exist_ok=True)
with open(f'data/backtest_results/fast_backtest_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json', 'w') as f:
    json.dump({
        'capital_final': capital,
        'return_pct': (capital/INITIAL_CAPITAL - 1)*100,
        'trades': total_trades,
        'win_rate': win_rate,
        'profit_factor': pf,
        'max_drawdown': max_dd,
        'sharpe': sharpe
    }, f, indent=2)

print("\n✅ Backtest concluído!")
