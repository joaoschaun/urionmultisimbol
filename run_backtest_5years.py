# -*- coding: utf-8 -*-
"""
Backtest 5 Anos - Urion Trading Bot

Executa backtest completo com:
- 5 anos de dados históricos
- Walk-forward analysis
- Monte Carlo simulation
- Métricas detalhadas
"""

import sys
import os
sys.path.insert(0, 'src')

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
from pathlib import Path

# Tentar importar o backtest engine
try:
    from src.backtesting.backtest_engine import BacktestEngine, BacktestResult
except ImportError:
    from backtesting.backtest_engine import BacktestEngine, BacktestResult


def download_historical_data(
    symbol: str,
    timeframe: int,
    years: int = 5
) -> pd.DataFrame:
    """Baixa dados históricos do MT5"""
    
    print(f"\n📊 Baixando {years} anos de dados para {symbol}...")
    
    if not mt5.initialize():
        raise Exception("Falha ao inicializar MT5")
    
    # Calcular datas
    end_date = datetime.now()
    start_date = end_date - timedelta(days=years * 365)
    
    # Baixar dados
    rates = mt5.copy_rates_range(symbol, timeframe, start_date, end_date)
    
    if rates is None or len(rates) == 0:
        mt5.shutdown()
        raise Exception(f"Nenhum dado retornado para {symbol}")
    
    # Converter para DataFrame
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # Renomear colunas
    df = df.rename(columns={
        'tick_volume': 'volume'
    })
    
    mt5.shutdown()
    
    print(f"   ✅ {len(df):,} candles baixados")
    print(f"   📅 De: {df['time'].min()}")
    print(f"   📅 Até: {df['time'].max()}")
    
    return df


def create_simple_strategy():
    """Cria uma estratégia simples para backtest"""
    
    class SimpleScalpingStrategy:
        """Estratégia de scalping baseada em RSI e médias móveis"""
        
        def __init__(self):
            self.name = "SimpleScalping"
            self.rsi_period = 14
            self.ema_fast = 9
            self.ema_slow = 21
            self.rsi_oversold = 30
            self.rsi_overbought = 70
        
        def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
            """Calcula indicadores"""
            df = df.copy()
            
            # EMAs
            df['ema_fast'] = df['close'].ewm(span=self.ema_fast).mean()
            df['ema_slow'] = df['close'].ewm(span=self.ema_slow).mean()
            
            # RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # ATR para stops
            high_low = df['high'] - df['low']
            high_close = abs(df['high'] - df['close'].shift())
            low_close = abs(df['low'] - df['close'].shift())
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            df['atr'] = tr.rolling(window=14).mean()
            
            return df
        
        def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
            """Gera sinais de trading"""
            df = self.calculate_indicators(df)
            
            # Inicializar sinais
            df['signal'] = 0
            df['direction'] = 'hold'
            
            # Condições de compra
            buy_condition = (
                (df['ema_fast'] > df['ema_slow']) &  # Tendência de alta
                (df['rsi'] < self.rsi_oversold + 10) &  # RSI não muito alto
                (df['rsi'] > self.rsi_oversold)  # RSI saindo de oversold
            )
            
            # Condições de venda
            sell_condition = (
                (df['ema_fast'] < df['ema_slow']) &  # Tendência de baixa
                (df['rsi'] > self.rsi_overbought - 10) &  # RSI não muito baixo
                (df['rsi'] < self.rsi_overbought)  # RSI saindo de overbought
            )
            
            df.loc[buy_condition, 'signal'] = 1
            df.loc[buy_condition, 'direction'] = 'buy'
            df.loc[sell_condition, 'signal'] = -1
            df.loc[sell_condition, 'direction'] = 'sell'
            
            # Stop loss e take profit baseados em ATR
            df['stop_loss_pips'] = df['atr'] * 1.5
            df['take_profit_pips'] = df['atr'] * 2.5
            
            return df
    
    return SimpleScalpingStrategy()


def run_backtest(
    df: pd.DataFrame,
    symbol: str,
    initial_capital: float = 10000,
    risk_per_trade: float = 0.02
) -> Dict:
    """Executa o backtest"""
    
    print(f"\n🚀 Iniciando backtest...")
    print(f"   Capital inicial: ${initial_capital:,.2f}")
    print(f"   Risco por trade: {risk_per_trade*100:.1f}%")
    
    # Criar estratégia
    strategy = create_simple_strategy()
    
    # Gerar sinais
    df_signals = strategy.generate_signals(df)
    
    # Simular trades
    trades = []
    capital = initial_capital
    position = None
    equity_curve = [initial_capital]
    
    for i in range(1, len(df_signals)):
        row = df_signals.iloc[i]
        prev_row = df_signals.iloc[i-1]
        
        # Se temos posição aberta, verificar saída
        if position is not None:
            current_price = row['close']
            
            # Verificar stop loss
            if position['direction'] == 'buy':
                if current_price <= position['stop_loss']:
                    # Stop loss atingido
                    pnl = (position['stop_loss'] - position['entry_price']) * position['volume'] * 100
                    capital += pnl
                    trades.append({
                        'entry_time': position['entry_time'],
                        'exit_time': row['time'],
                        'direction': position['direction'],
                        'entry_price': position['entry_price'],
                        'exit_price': position['stop_loss'],
                        'volume': position['volume'],
                        'pnl': pnl,
                        'exit_reason': 'stop_loss'
                    })
                    position = None
                elif current_price >= position['take_profit']:
                    # Take profit atingido
                    pnl = (position['take_profit'] - position['entry_price']) * position['volume'] * 100
                    capital += pnl
                    trades.append({
                        'entry_time': position['entry_time'],
                        'exit_time': row['time'],
                        'direction': position['direction'],
                        'entry_price': position['entry_price'],
                        'exit_price': position['take_profit'],
                        'volume': position['volume'],
                        'pnl': pnl,
                        'exit_reason': 'take_profit'
                    })
                    position = None
            else:  # sell
                if current_price >= position['stop_loss']:
                    # Stop loss atingido
                    pnl = (position['entry_price'] - position['stop_loss']) * position['volume'] * 100
                    capital += pnl
                    trades.append({
                        'entry_time': position['entry_time'],
                        'exit_time': row['time'],
                        'direction': position['direction'],
                        'entry_price': position['entry_price'],
                        'exit_price': position['stop_loss'],
                        'volume': position['volume'],
                        'pnl': pnl,
                        'exit_reason': 'stop_loss'
                    })
                    position = None
                elif current_price <= position['take_profit']:
                    # Take profit atingido
                    pnl = (position['entry_price'] - position['take_profit']) * position['volume'] * 100
                    capital += pnl
                    trades.append({
                        'entry_time': position['entry_time'],
                        'exit_time': row['time'],
                        'direction': position['direction'],
                        'entry_price': position['entry_price'],
                        'exit_price': position['take_profit'],
                        'volume': position['volume'],
                        'pnl': pnl,
                        'exit_reason': 'take_profit'
                    })
                    position = None
        
        # Se não temos posição, verificar entrada
        if position is None and row['signal'] != 0:
            # Calcular tamanho da posição
            risk_amount = capital * risk_per_trade
            atr = row['atr'] if not pd.isna(row['atr']) else 2.0
            stop_distance = atr * 1.5
            
            if stop_distance > 0:
                volume = risk_amount / (stop_distance * 100)
                volume = max(0.01, min(volume, 1.0))  # Limitar entre 0.01 e 1.0 lote
                
                entry_price = row['close']
                
                if row['direction'] == 'buy':
                    stop_loss = entry_price - stop_distance
                    take_profit = entry_price + (stop_distance * 1.67)  # RR 1:1.67
                else:
                    stop_loss = entry_price + stop_distance
                    take_profit = entry_price - (stop_distance * 1.67)
                
                position = {
                    'entry_time': row['time'],
                    'direction': row['direction'],
                    'entry_price': entry_price,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'volume': volume
                }
        
        equity_curve.append(capital)
    
    # Calcular métricas
    trades_df = pd.DataFrame(trades) if trades else pd.DataFrame()
    
    if len(trades_df) > 0:
        winning_trades = trades_df[trades_df['pnl'] > 0]
        losing_trades = trades_df[trades_df['pnl'] < 0]
        
        total_profit = trades_df['pnl'].sum()
        win_rate = len(winning_trades) / len(trades_df) * 100
        
        avg_win = winning_trades['pnl'].mean() if len(winning_trades) > 0 else 0
        avg_loss = abs(losing_trades['pnl'].mean()) if len(losing_trades) > 0 else 0
        
        profit_factor = (winning_trades['pnl'].sum() / abs(losing_trades['pnl'].sum())) if len(losing_trades) > 0 and losing_trades['pnl'].sum() != 0 else 0
        
        # Max drawdown
        equity_series = pd.Series(equity_curve)
        rolling_max = equity_series.cummax()
        drawdown = (equity_series - rolling_max) / rolling_max
        max_drawdown = abs(drawdown.min()) * 100
        
        # Sharpe Ratio (simplificado)
        returns = equity_series.pct_change().dropna()
        sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0
        
        # Calmar Ratio
        annual_return = ((capital / initial_capital) ** (1 / 5) - 1) * 100  # 5 anos
        calmar = annual_return / max_drawdown if max_drawdown > 0 else 0
        
    else:
        total_profit = 0
        win_rate = 0
        avg_win = 0
        avg_loss = 0
        profit_factor = 0
        max_drawdown = 0
        sharpe = 0
        calmar = 0
    
    results = {
        'symbol': symbol,
        'period_years': 5,
        'initial_capital': initial_capital,
        'final_capital': capital,
        'total_profit': total_profit,
        'total_return_pct': ((capital / initial_capital) - 1) * 100,
        'total_trades': len(trades_df),
        'winning_trades': len(trades_df[trades_df['pnl'] > 0]) if len(trades_df) > 0 else 0,
        'losing_trades': len(trades_df[trades_df['pnl'] < 0]) if len(trades_df) > 0 else 0,
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'profit_factor': profit_factor,
        'max_drawdown_pct': max_drawdown,
        'sharpe_ratio': sharpe,
        'calmar_ratio': calmar,
        'trades': trades_df.to_dict('records') if len(trades_df) > 0 else [],
        'equity_curve': equity_curve
    }
    
    return results


def run_walk_forward(
    df: pd.DataFrame,
    symbol: str,
    n_splits: int = 12,
    train_ratio: float = 0.7
) -> Dict:
    """Executa walk-forward analysis"""
    
    print(f"\n📈 Walk-Forward Analysis ({n_splits} splits)...")
    
    total_size = len(df)
    split_size = total_size // n_splits
    
    oos_results = []  # Out-of-sample results
    
    for i in range(n_splits):
        # Dividir dados
        start_idx = i * split_size
        end_idx = min((i + 2) * split_size, total_size)  # 2 splits por vez
        
        if end_idx > total_size:
            break
        
        split_df = df.iloc[start_idx:end_idx].reset_index(drop=True)
        train_size = int(len(split_df) * train_ratio)
        
        train_df = split_df.iloc[:train_size]
        test_df = split_df.iloc[train_size:]
        
        if len(test_df) < 100:
            continue
        
        # Backtest no período de teste (out-of-sample)
        result = run_backtest(test_df, symbol, initial_capital=10000)
        
        oos_results.append({
            'split': i + 1,
            'test_start': test_df['time'].iloc[0],
            'test_end': test_df['time'].iloc[-1],
            'trades': result['total_trades'],
            'win_rate': result['win_rate'],
            'profit_factor': result['profit_factor'],
            'total_return': result['total_return_pct'],
            'max_drawdown': result['max_drawdown_pct']
        })
        
        print(f"   Split {i+1}/{n_splits}: WR={result['win_rate']:.1f}% PF={result['profit_factor']:.2f} DD={result['max_drawdown_pct']:.1f}%")
    
    # Resumo
    if oos_results:
        avg_wr = np.mean([r['win_rate'] for r in oos_results])
        avg_pf = np.mean([r['profit_factor'] for r in oos_results])
        avg_dd = np.mean([r['max_drawdown'] for r in oos_results])
        
        return {
            'n_splits': n_splits,
            'oos_results': oos_results,
            'avg_win_rate': avg_wr,
            'avg_profit_factor': avg_pf,
            'avg_max_drawdown': avg_dd,
            'consistency': len([r for r in oos_results if r['profit_factor'] > 1.0]) / len(oos_results) * 100
        }
    
    return {'error': 'Não foi possível executar walk-forward'}


def run_monte_carlo(
    trades: List[Dict],
    n_simulations: int = 1000,
    initial_capital: float = 10000
) -> Dict:
    """Executa simulação Monte Carlo"""
    
    print(f"\n🎲 Monte Carlo Simulation ({n_simulations} iterações)...")
    
    if not trades:
        return {'error': 'Sem trades para simulação'}
    
    pnls = [t['pnl'] for t in trades]
    
    final_capitals = []
    max_drawdowns = []
    
    for _ in range(n_simulations):
        # Shuffle dos trades
        shuffled_pnls = np.random.permutation(pnls)
        
        # Simular equity curve
        capital = initial_capital
        equity = [capital]
        peak = capital
        max_dd = 0
        
        for pnl in shuffled_pnls:
            capital += pnl
            equity.append(capital)
            
            if capital > peak:
                peak = capital
            
            dd = (peak - capital) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        
        final_capitals.append(capital)
        max_drawdowns.append(max_dd * 100)
    
    # Estatísticas
    final_capitals = np.array(final_capitals)
    max_drawdowns = np.array(max_drawdowns)
    
    return {
        'n_simulations': n_simulations,
        'final_capital': {
            'mean': np.mean(final_capitals),
            'median': np.median(final_capitals),
            'std': np.std(final_capitals),
            'min': np.min(final_capitals),
            'max': np.max(final_capitals),
            'p5': np.percentile(final_capitals, 5),
            'p95': np.percentile(final_capitals, 95)
        },
        'max_drawdown': {
            'mean': np.mean(max_drawdowns),
            'median': np.median(max_drawdowns),
            'p95': np.percentile(max_drawdowns, 95),
            'max': np.max(max_drawdowns)
        },
        'ruin_probability': len(final_capitals[final_capitals < initial_capital * 0.5]) / n_simulations * 100
    }


def print_results(results: Dict, wf_results: Dict, mc_results: Dict):
    """Imprime resultados formatados"""
    
    print("\n" + "="*70)
    print("📊 RESULTADOS DO BACKTEST - 5 ANOS")
    print("="*70)
    
    print(f"\n🎯 PERFORMANCE GERAL")
    print(f"   Símbolo: {results['symbol']}")
    print(f"   Período: {results['period_years']} anos")
    print(f"   Capital Inicial: ${results['initial_capital']:,.2f}")
    print(f"   Capital Final: ${results['final_capital']:,.2f}")
    print(f"   Retorno Total: {results['total_return_pct']:.2f}%")
    print(f"   Lucro Total: ${results['total_profit']:,.2f}")
    
    print(f"\n📈 MÉTRICAS DE TRADING")
    print(f"   Total de Trades: {results['total_trades']}")
    print(f"   Trades Vencedores: {results['winning_trades']}")
    print(f"   Trades Perdedores: {results['losing_trades']}")
    print(f"   Win Rate: {results['win_rate']:.2f}%")
    print(f"   Profit Factor: {results['profit_factor']:.2f}")
    print(f"   Média Ganho: ${results['avg_win']:.2f}")
    print(f"   Média Perda: ${results['avg_loss']:.2f}")
    
    print(f"\n⚠️ MÉTRICAS DE RISCO")
    print(f"   Max Drawdown: {results['max_drawdown_pct']:.2f}%")
    print(f"   Sharpe Ratio: {results['sharpe_ratio']:.2f}")
    print(f"   Calmar Ratio: {results['calmar_ratio']:.2f}")
    
    if 'avg_win_rate' in wf_results:
        print(f"\n🔄 WALK-FORWARD ANALYSIS")
        print(f"   Splits: {wf_results['n_splits']}")
        print(f"   Win Rate Médio OOS: {wf_results['avg_win_rate']:.2f}%")
        print(f"   Profit Factor Médio OOS: {wf_results['avg_profit_factor']:.2f}")
        print(f"   Max Drawdown Médio OOS: {wf_results['avg_max_drawdown']:.2f}%")
        print(f"   Consistência: {wf_results['consistency']:.1f}% dos splits lucrativos")
    
    if 'final_capital' in mc_results:
        print(f"\n🎲 MONTE CARLO SIMULATION")
        print(f"   Simulações: {mc_results['n_simulations']}")
        print(f"   Capital Final Médio: ${mc_results['final_capital']['mean']:,.2f}")
        print(f"   Capital Final P5-P95: ${mc_results['final_capital']['p5']:,.2f} - ${mc_results['final_capital']['p95']:,.2f}")
        print(f"   Max Drawdown Médio: {mc_results['max_drawdown']['mean']:.2f}%")
        print(f"   Max Drawdown P95: {mc_results['max_drawdown']['p95']:.2f}%")
        print(f"   Probabilidade de Ruína: {mc_results['ruin_probability']:.2f}%")
    
    # Avaliação
    print("\n" + "="*70)
    print("✅ AVALIAÇÃO PARA PRODUÇÃO")
    print("="*70)
    
    checks = []
    
    # Win Rate > 50%
    if results['win_rate'] >= 50:
        checks.append(("Win Rate > 50%", "✅ PASS", results['win_rate']))
    else:
        checks.append(("Win Rate > 50%", "❌ FAIL", results['win_rate']))
    
    # Profit Factor > 1.3
    if results['profit_factor'] >= 1.3:
        checks.append(("Profit Factor > 1.3", "✅ PASS", results['profit_factor']))
    else:
        checks.append(("Profit Factor > 1.3", "❌ FAIL", results['profit_factor']))
    
    # Max Drawdown < 20%
    if results['max_drawdown_pct'] <= 20:
        checks.append(("Max Drawdown < 20%", "✅ PASS", results['max_drawdown_pct']))
    else:
        checks.append(("Max Drawdown < 20%", "❌ FAIL", results['max_drawdown_pct']))
    
    # Sharpe > 1.0
    if results['sharpe_ratio'] >= 1.0:
        checks.append(("Sharpe Ratio > 1.0", "✅ PASS", results['sharpe_ratio']))
    else:
        checks.append(("Sharpe Ratio > 1.0", "❌ FAIL", results['sharpe_ratio']))
    
    # Walk-forward consistency > 60%
    if 'consistency' in wf_results and wf_results['consistency'] >= 60:
        checks.append(("WF Consistency > 60%", "✅ PASS", wf_results['consistency']))
    elif 'consistency' in wf_results:
        checks.append(("WF Consistency > 60%", "❌ FAIL", wf_results['consistency']))
    
    # Monte Carlo ruin < 5%
    if 'ruin_probability' in mc_results and mc_results['ruin_probability'] <= 5:
        checks.append(("MC Ruin Prob < 5%", "✅ PASS", mc_results['ruin_probability']))
    elif 'ruin_probability' in mc_results:
        checks.append(("MC Ruin Prob < 5%", "❌ FAIL", mc_results['ruin_probability']))
    
    for name, status, value in checks:
        print(f"   {status} {name}: {value:.2f}")
    
    passed = len([c for c in checks if "PASS" in c[1]])
    total = len(checks)
    
    print(f"\n   Score: {passed}/{total} ({passed/total*100:.0f}%)")
    
    if passed == total:
        print("\n   🚀 APROVADO PARA PAPER TRADING!")
    elif passed >= total * 0.7:
        print("\n   ⚠️ PRECISA MELHORIAS ANTES DE PRODUÇÃO")
    else:
        print("\n   ❌ NÃO APROVADO - REVISAR ESTRATÉGIA")
    
    print("="*70)


def save_results(results: Dict, wf_results: Dict, mc_results: Dict, symbol: str):
    """Salva resultados em arquivo"""
    
    output_dir = Path("data/backtest_results")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Salvar JSON (sem equity curve completo para economizar espaço)
    results_copy = results.copy()
    results_copy['equity_curve'] = f"{len(results['equity_curve'])} points"
    results_copy['trades'] = f"{len(results.get('trades', []))} trades"
    
    output = {
        'timestamp': timestamp,
        'backtest': results_copy,
        'walk_forward': wf_results,
        'monte_carlo': mc_results
    }
    
    output_file = output_dir / f"backtest_{symbol}_{timestamp}.json"
    
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"\n💾 Resultados salvos em: {output_file}")


def main():
    """Função principal"""
    
    print("\n" + "="*70)
    print("🤖 URION TRADING BOT - BACKTEST 5 ANOS")
    print("="*70)
    
    # Configurações
    symbol = "XAUUSD"
    timeframe = mt5.TIMEFRAME_H1  # 1 hora
    years = 5
    initial_capital = 10000
    
    try:
        # 1. Baixar dados históricos
        df = download_historical_data(symbol, timeframe, years)
        
        # 2. Executar backtest principal
        results = run_backtest(df, symbol, initial_capital)
        
        # 3. Walk-forward analysis
        wf_results = run_walk_forward(df, symbol, n_splits=12)
        
        # 4. Monte Carlo simulation
        mc_results = run_monte_carlo(results.get('trades', []), n_simulations=1000, initial_capital=initial_capital)
        
        # 5. Imprimir resultados
        print_results(results, wf_results, mc_results)
        
        # 6. Salvar resultados
        save_results(results, wf_results, mc_results, symbol)
        
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
