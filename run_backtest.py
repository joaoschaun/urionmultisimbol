# -*- coding: utf-8 -*-
"""
URION Trading Bot - Backtesting Mode
=====================================
Executa backtesting completo com todos os módulos avançados.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from loguru import logger
import pandas as pd

# Adicionar src ao path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

from core.config_manager import ConfigManager
from core.logger import setup_logger
from backtesting.engine import BacktestEngine
from backtesting.data_manager import DataManager, Timeframe

# Configurar
config_manager = ConfigManager()
config = config_manager.config
setup_logger(config)


def run_backtesting():
    """Executa backtesting completo"""
    
    logger.info("=" * 80)
    logger.info("URION TRADING BOT - BACKTESTING MODE")
    logger.info("Professional Edition v2.0")
    logger.info("=" * 80)
    
    # Configurações do backtest
    symbol = "XAUUSD"
    timeframe_str = "M15"
    timeframe = Timeframe.M15
    
    # Período: últimos 30 dias
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    logger.info(f"Símbolo: {symbol}")
    logger.info(f"Timeframe: {timeframe_str}")
    logger.info(f"Período: {start_date.strftime('%Y-%m-%d')} a {end_date.strftime('%Y-%m-%d')}")
    logger.info("=" * 80)
    
    try:
        # Inicializar Data Manager
        logger.info("\n[1/4] Carregando dados históricos...")
        data_manager = DataManager(data_dir="data/historical")
        data = None
        
        # Tentar carregar dados salvos
        try:
            data = data_manager.load_data(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date
            )
            logger.info(f"  ✓ Dados carregados do cache")
        except FileNotFoundError:
            logger.warning("Dados não encontrados em cache, tentando baixar do MT5...")
            
            # Tentar baixar do MT5
            try:
                import MetaTrader5 as mt5
                if mt5.initialize():
                    # Mapear timeframe
                    tf_map = {
                        'M1': mt5.TIMEFRAME_M1,
                        'M5': mt5.TIMEFRAME_M5,
                        'M15': mt5.TIMEFRAME_M15,
                        'M30': mt5.TIMEFRAME_M30,
                        'H1': mt5.TIMEFRAME_H1,
                        'H4': mt5.TIMEFRAME_H4,
                        'D1': mt5.TIMEFRAME_D1
                    }
                    mt5_tf = tf_map.get(timeframe_str, mt5.TIMEFRAME_M15)
                    
                    # Baixar dados
                    rates = mt5.copy_rates_range(symbol, mt5_tf, start_date, end_date)
                    if rates is not None and len(rates) > 0:
                        data = pd.DataFrame(rates)
                        data['time'] = pd.to_datetime(data['time'], unit='s')
                        data.set_index('time', inplace=True)
                        
                        # Salvar para cache (save_data espera: df, symbol, timeframe)
                        data_manager.save_data(data.reset_index(), symbol, timeframe)
                        logger.info(f"  ✓ {len(data)} candles baixados do MT5 e salvos")
                    
                    mt5.shutdown()
                else:
                    logger.warning("Não foi possível inicializar MT5")
            except Exception as e:
                logger.warning(f"MT5 não disponível: {e}")
        
        if data is None or len(data) == 0:
            logger.warning("Não foi possível obter dados históricos")
            logger.info("Gerando dados sintéticos para demonstração...")
            
            # Gerar dados sintéticos para demonstração
            data = generate_synthetic_data(start_date, end_date, timeframe.minutes)
        
        logger.info(f"  ✓ {len(data)} candles carregados")
        
        # Inicializar Engine de Backtest
        logger.info("\n[2/4] Inicializando engine de backtest...")
        
        # Configurações do backtest
        initial_balance = 10000.0
        
        engine = BacktestEngine(
            initial_balance=initial_balance,
            commission=0.0001,      # 0.01%
            spread_pips=2.5,        # Spread XAUUSD
            slippage_pips=0.5,
            pip_value=10,           # XAUUSD pip value
            leverage=100,
            max_positions=5,
            risk_per_trade=0.02     # 2% risco
        )
        
        logger.info(f"  ✓ Capital inicial: ${initial_balance:,.2f}")
        
        # Carregar estratégias ativas
        logger.info("\n[3/4] Carregando estratégias...")
        strategies_enabled = config.get('strategies', {}).get('enabled', [])
        logger.info(f"  ✓ Estratégias ativas: {', '.join(strategies_enabled)}")
        
        # Executar backtest simples
        logger.info("\n[4/4] Executando backtest...")
        logger.info("-" * 40)
        
        results = run_simple_backtest(engine, data, symbol)
        
        # Exibir resultados
        display_results(results)
        
        return results
        
    except Exception as e:
        logger.error(f"Erro no backtesting: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def generate_synthetic_data(start_date: datetime, end_date: datetime, interval_minutes: int) -> pd.DataFrame:
    """Gera dados sintéticos para demonstração"""
    import numpy as np
    
    # Calcular número de candles
    total_minutes = int((end_date - start_date).total_seconds() / 60)
    num_candles = total_minutes // interval_minutes
    
    # Gerar timestamps
    timestamps = pd.date_range(start=start_date, periods=num_candles, freq=f'{interval_minutes}min')
    
    # Preço base XAUUSD
    base_price = 2650.0
    
    # Gerar movimento de preço com random walk
    np.random.seed(42)
    returns = np.random.normal(0, 0.001, num_candles)  # Retornos diários
    prices = base_price * np.exp(np.cumsum(returns))
    
    # Gerar OHLC
    high_factor = 1 + np.random.uniform(0, 0.003, num_candles)
    low_factor = 1 - np.random.uniform(0, 0.003, num_candles)
    
    data = pd.DataFrame({
        'time': timestamps,
        'open': prices,
        'high': prices * high_factor,
        'low': prices * low_factor,
        'close': prices * (1 + np.random.uniform(-0.002, 0.002, num_candles)),
        'tick_volume': np.random.randint(100, 1000, num_candles),
        'spread': np.random.uniform(20, 40, num_candles),
        'real_volume': np.random.randint(1000, 10000, num_candles)
    })
    
    data.set_index('time', inplace=True)
    
    return data


def run_simple_backtest(engine: BacktestEngine, data: pd.DataFrame, symbol: str) -> dict:
    """
    Executa um backtest simples baseado em médias móveis
    """
    from analysis.technical_analyzer import TechnicalAnalyzer
    
    # Inicializar analisador técnico
    try:
        analyzer = TechnicalAnalyzer({})
    except:
        analyzer = None
    
    # Calcular indicadores manualmente se necessário
    data['ema_fast'] = data['close'].ewm(span=12, adjust=False).mean()
    data['ema_slow'] = data['close'].ewm(span=26, adjust=False).mean()
    data['rsi'] = calculate_rsi(data['close'], 14)
    data['atr'] = calculate_atr(data, 14)
    
    # Simular trades
    trades = []
    position = None
    
    for i in range(50, len(data)):
        current = data.iloc[i]
        prev = data.iloc[i-1]
        
        # Condições de entrada
        ema_cross_up = prev['ema_fast'] <= prev['ema_slow'] and current['ema_fast'] > current['ema_slow']
        ema_cross_down = prev['ema_fast'] >= prev['ema_slow'] and current['ema_fast'] < current['ema_slow']
        
        rsi_ok_buy = 30 < current['rsi'] < 70
        rsi_ok_sell = 30 < current['rsi'] < 70
        
        if position is None:
            # Sinal de compra
            if ema_cross_up and rsi_ok_buy:
                position = {
                    'type': 'BUY',
                    'entry_price': current['close'],
                    'entry_time': current.name,
                    'sl': current['close'] - current['atr'] * 2,
                    'tp': current['close'] + current['atr'] * 3
                }
            # Sinal de venda
            elif ema_cross_down and rsi_ok_sell:
                position = {
                    'type': 'SELL',
                    'entry_price': current['close'],
                    'entry_time': current.name,
                    'sl': current['close'] + current['atr'] * 2,
                    'tp': current['close'] - current['atr'] * 3
                }
        else:
            # Verificar saída
            should_close = False
            exit_reason = ""
            
            if position['type'] == 'BUY':
                # SL/TP para compra
                if current['low'] <= position['sl']:
                    should_close = True
                    exit_reason = "Stop Loss"
                    exit_price = position['sl']
                elif current['high'] >= position['tp']:
                    should_close = True
                    exit_reason = "Take Profit"
                    exit_price = position['tp']
                elif ema_cross_down:  # Sinal oposto
                    should_close = True
                    exit_reason = "Signal Reversal"
                    exit_price = current['close']
            else:
                # SL/TP para venda
                if current['high'] >= position['sl']:
                    should_close = True
                    exit_reason = "Stop Loss"
                    exit_price = position['sl']
                elif current['low'] <= position['tp']:
                    should_close = True
                    exit_reason = "Take Profit"
                    exit_price = position['tp']
                elif ema_cross_up:  # Sinal oposto
                    should_close = True
                    exit_reason = "Signal Reversal"
                    exit_price = current['close']
            
            if should_close:
                # Calcular P&L
                if position['type'] == 'BUY':
                    pnl_pips = (exit_price - position['entry_price']) / 0.01  # Pip = 0.01 para XAUUSD
                else:
                    pnl_pips = (position['entry_price'] - exit_price) / 0.01
                
                pnl = pnl_pips * 1  # $1 por pip com lote de 0.01
                
                trades.append({
                    'type': position['type'],
                    'entry_price': position['entry_price'],
                    'exit_price': exit_price,
                    'entry_time': position['entry_time'],
                    'exit_time': current.name,
                    'pnl': pnl,
                    'pnl_pips': pnl_pips,
                    'exit_reason': exit_reason
                })
                
                position = None
    
    # Calcular métricas
    return calculate_metrics(trades, engine.initial_balance)


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Calcula RSI"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def calculate_atr(data: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calcula ATR"""
    high_low = data['high'] - data['low']
    high_close = abs(data['high'] - data['close'].shift())
    low_close = abs(data['low'] - data['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def calculate_metrics(trades: list, initial_balance: float) -> dict:
    """Calcula métricas de performance"""
    if not trades:
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'total_pnl': 0,
            'gross_profit': 0,
            'gross_loss': 0,
            'profit_factor': 0,
            'max_drawdown': 0,
            'sharpe_ratio': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'expectancy': 0
        }
    
    pnls = [t['pnl'] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    
    total_pnl = sum(pnls)
    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0
    
    # Drawdown
    cumulative = []
    running = initial_balance
    peak = initial_balance
    max_dd = 0
    
    for pnl in pnls:
        running += pnl
        cumulative.append(running)
        if running > peak:
            peak = running
        dd = (peak - running) / peak
        if dd > max_dd:
            max_dd = dd
    
    # Sharpe (simplificado)
    import numpy as np
    returns = np.array(pnls) / initial_balance
    sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
    
    return {
        'total_trades': len(trades),
        'winning_trades': len(wins),
        'losing_trades': len(losses),
        'win_rate': len(wins) / len(trades) if trades else 0,
        'total_pnl': total_pnl,
        'gross_profit': gross_profit,
        'gross_loss': gross_loss,
        'profit_factor': gross_profit / gross_loss if gross_loss > 0 else float('inf'),
        'max_drawdown': max_dd,
        'sharpe_ratio': sharpe,
        'avg_win': np.mean(wins) if wins else 0,
        'avg_loss': np.mean(losses) if losses else 0,
        'expectancy': total_pnl / len(trades) if trades else 0,
        'recovery_factor': total_pnl / (max_dd * initial_balance) if max_dd > 0 else 0,
        'trades': trades
    }


def display_results(results: dict):
    """Exibe resultados formatados"""
    logger.info("\n" + "=" * 80)
    logger.info("RESULTADOS DO BACKTEST")
    logger.info("=" * 80)
    
    if not results or results.get('total_trades', 0) == 0:
        logger.warning("Nenhum trade executado no período")
        return
    
    logger.info(f"\n📊 MÉTRICAS DE PERFORMANCE:")
    logger.info(f"  • Total de trades: {results.get('total_trades', 0)}")
    logger.info(f"  • Trades vencedores: {results.get('winning_trades', 0)}")
    logger.info(f"  • Trades perdedores: {results.get('losing_trades', 0)}")
    logger.info(f"  • Win Rate: {results.get('win_rate', 0):.1%}")
    
    logger.info(f"\n💰 RESULTADOS FINANCEIROS:")
    logger.info(f"  • Lucro/Prejuízo Total: ${results.get('total_pnl', 0):,.2f}")
    logger.info(f"  • Lucro Bruto: ${results.get('gross_profit', 0):,.2f}")
    logger.info(f"  • Prejuízo Bruto: ${results.get('gross_loss', 0):,.2f}")
    logger.info(f"  • Profit Factor: {results.get('profit_factor', 0):.2f}")
    
    logger.info(f"\n📈 ANÁLISE DE RISCO:")
    logger.info(f"  • Max Drawdown: {results.get('max_drawdown', 0):.2%}")
    logger.info(f"  • Sharpe Ratio: {results.get('sharpe_ratio', 0):.2f}")
    logger.info(f"  • Recovery Factor: {results.get('recovery_factor', 0):.2f}")
    
    logger.info(f"\n🎯 MÉDIAS:")
    logger.info(f"  • Média de ganho: ${results.get('avg_win', 0):,.2f}")
    logger.info(f"  • Média de perda: ${results.get('avg_loss', 0):,.2f}")
    logger.info(f"  • Expectativa: ${results.get('expectancy', 0):,.2f}")
    
    # Últimos trades
    trades = results.get('trades', [])
    if trades:
        logger.info(f"\n📝 ÚLTIMOS 5 TRADES:")
        for trade in trades[-5:]:
            emoji = "✅" if trade['pnl'] > 0 else "❌"
            logger.info(f"  {emoji} {trade['type']} | P&L: ${trade['pnl']:.2f} | {trade['exit_reason']}")
    
    logger.info("\n" + "=" * 80)
    logger.success("BACKTESTING FINALIZADO COM SUCESSO!")
    logger.info("=" * 80)


if __name__ == "__main__":
    results = run_backtesting()
