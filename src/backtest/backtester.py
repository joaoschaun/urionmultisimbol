"""
Backtester
Sistema de backtesting para validação de estratégias
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import pandas as pd
import numpy as np
from loguru import logger


@dataclass
class BacktestTrade:
    """Representa um trade no backtest"""
    entry_time: datetime
    exit_time: datetime
    symbol: str
    direction: str
    entry_price: float
    exit_price: float
    lot_size: float
    sl: float
    tp: float
    profit: float
    profit_pips: float
    strategy: str
    exit_reason: str


@dataclass
class BacktestResult:
    """Resultado consolidado do backtest"""
    strategy: str
    symbol: str
    period_start: datetime
    period_end: datetime
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_profit: float
    total_profit_pips: float
    max_drawdown: float
    max_drawdown_pct: float
    profit_factor: float
    sharpe_ratio: float
    avg_trade_duration: float
    avg_profit_per_trade: float
    best_trade: float
    worst_trade: float
    consecutive_wins: int
    consecutive_losses: int
    trades: List[BacktestTrade]


class Backtester:
    """Sistema de backtesting para estratégias"""
    
    def __init__(self, mt5_connector, config: dict):
        """Inicializa Backtester"""
        self.mt5 = mt5_connector
        self.config = config
        self.initial_balance = 10000.0
        
        logger.info("Backtester inicializado")
    
    def run(
        self,
        strategy,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: str = 'M15',
        initial_balance: float = 10000.0
    ) -> BacktestResult:
        """Executa backtest de uma estratégia"""
        logger.info(f"Iniciando backtest: {strategy.name} @ {symbol}")
        logger.info(f"Período: {start_date} a {end_date}")
        
        self.initial_balance = initial_balance
        
        # Obter dados históricos
        rates = self._get_historical_data(symbol, timeframe, start_date, end_date)
        
        if rates is None or len(rates) < 100:
            logger.error("Dados históricos insuficientes")
            return None
        
        logger.info(f"Dados carregados: {len(rates)} candles")
        
        # Variáveis de simulação
        balance = initial_balance
        equity_curve = [initial_balance]
        trades: List[BacktestTrade] = []
        open_position = None
        
        # Iterar sobre os dados
        for i in range(100, len(rates)):
            current_bar = rates.iloc[i]
            historical_data = rates.iloc[:i+1]
            
            # Se há posição aberta, verificar saída
            if open_position:
                exit_result = self._check_exit(
                    open_position, current_bar, historical_data, strategy
                )
                
                if exit_result:
                    trade = self._close_position(
                        open_position, current_bar, exit_result['reason']
                    )
                    trades.append(trade)
                    balance += trade.profit
                    equity_curve.append(balance)
                    open_position = None
            
            # Se não há posição, verificar entrada
            if not open_position:
                signal = self._check_entry(historical_data, strategy, symbol)
                
                if signal and signal['confidence'] >= strategy.min_confidence:
                    open_position = self._open_position(
                        current_bar, signal, symbol, strategy.name, balance
                    )
        
        # Fechar posição pendente no final
        if open_position:
            trade = self._close_position(
                open_position, rates.iloc[-1], 'END_OF_TEST'
            )
            trades.append(trade)
            balance += trade.profit
        
        # Calcular métricas
        result = self._calculate_metrics(
            trades, equity_curve, strategy.name, symbol, start_date, end_date
        )
        
        logger.success(
            f"Backtest concluído: {len(trades)} trades, "
            f"Profit: ${result.total_profit:.2f}"
        )
        
        return result
    
    def _get_historical_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> Optional[pd.DataFrame]:
        """Obtém dados históricos do MT5"""
        try:
            tf_map = {
                'M1': 1, 'M5': 5, 'M15': 15, 'M30': 30,
                'H1': 60, 'H4': 240, 'D1': 1440
            }
            tf_minutes = tf_map.get(timeframe, 15)
            
            delta = end_date - start_date
            num_bars = int(delta.total_seconds() / 60 / tf_minutes) + 100
            
            rates = self.mt5.get_rates(symbol, timeframe, num_bars)
            
            if rates is not None and len(rates) > 0:
                rates = rates[
                    (rates['time'] >= start_date) & 
                    (rates['time'] <= end_date)
                ]
                return rates
            
            return None
            
        except Exception as e:
            logger.error(f"Erro ao obter dados históricos: {e}")
            return None
    
    def _check_entry(
        self,
        data: pd.DataFrame,
        strategy,
        symbol: str
    ) -> Optional[Dict]:
        """Verifica sinal de entrada"""
        try:
            analysis_data = {
                'rates': {'M15': data.tail(100)},
                'indicators': self._calculate_indicators(data),
                'symbol': symbol
            }
            
            signal = strategy.analyze(analysis_data)
            return signal
            
        except Exception as e:
            logger.debug(f"Erro ao verificar entrada: {e}")
            return None
    
    def _check_exit(
        self,
        position: Dict,
        current_bar: pd.Series,
        data: pd.DataFrame,
        strategy
    ) -> Optional[Dict]:
        """Verifica condições de saída"""
        
        if position['direction'] == 'BUY':
            if current_bar['low'] <= position['sl']:
                return {'reason': 'SL', 'price': position['sl']}
            if current_bar['high'] >= position['tp']:
                return {'reason': 'TP', 'price': position['tp']}
        else:
            if current_bar['high'] >= position['sl']:
                return {'reason': 'SL', 'price': position['sl']}
            if current_bar['low'] <= position['tp']:
                return {'reason': 'TP', 'price': position['tp']}
        
        if hasattr(current_bar, 'time'):
            duration = current_bar['time'] - position['entry_time']
            if duration > timedelta(hours=24):
                return {'reason': 'TIMEOUT', 'price': current_bar['close']}
        
        return None
    
    def _open_position(
        self,
        bar: pd.Series,
        signal: Dict,
        symbol: str,
        strategy_name: str,
        current_balance: float
    ) -> Dict:
        """Abre posição simulada"""
        
        direction = signal['direction']
        entry_price = bar['close']
        
        atr = signal.get('atr', 0.001)
        
        if direction == 'BUY':
            sl = entry_price - (atr * 2)
            tp = entry_price + (atr * 3)
        else:
            sl = entry_price + (atr * 2)
            tp = entry_price - (atr * 3)
        
        risk_amount = current_balance * 0.02
        sl_pips = abs(entry_price - sl)
        
        if sl_pips > 0:
            lot_size = min(risk_amount / (sl_pips * 100000), 1.0)
        else:
            lot_size = 0.01
        
        return {
            'entry_time': bar['time'] if 'time' in bar else datetime.now(),
            'entry_price': entry_price,
            'direction': direction,
            'symbol': symbol,
            'strategy': strategy_name,
            'sl': sl,
            'tp': tp,
            'lot_size': round(lot_size, 2),
            'confidence': signal['confidence']
        }
    
    def _close_position(
        self,
        position: Dict,
        bar: pd.Series,
        reason: str
    ) -> BacktestTrade:
        """Fecha posição e calcula resultado"""
        
        exit_price = bar['close']
        exit_time = bar['time'] if 'time' in bar else datetime.now()
        
        if reason == 'SL':
            exit_price = position['sl']
        elif reason == 'TP':
            exit_price = position['tp']
        
        if position['direction'] == 'BUY':
            profit_pips = (exit_price - position['entry_price']) * 10000
        else:
            profit_pips = (position['entry_price'] - exit_price) * 10000
        
        profit = profit_pips * position['lot_size'] * 10
        
        return BacktestTrade(
            entry_time=position['entry_time'],
            exit_time=exit_time,
            symbol=position['symbol'],
            direction=position['direction'],
            entry_price=position['entry_price'],
            exit_price=exit_price,
            lot_size=position['lot_size'],
            sl=position['sl'],
            tp=position['tp'],
            profit=round(profit, 2),
            profit_pips=round(profit_pips, 1),
            strategy=position['strategy'],
            exit_reason=reason
        )
    
    def _calculate_indicators(self, data: pd.DataFrame) -> Dict:
        """Calcula indicadores básicos para backtest"""
        close = data['close']
        high = data['high']
        low = data['low']
        
        ema9 = close.ewm(span=9).mean()
        ema21 = close.ewm(span=21).mean()
        ema50 = close.ewm(span=50).mean()
        
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        tr = pd.concat([
            high - low,
            abs(high - close.shift()),
            abs(low - close.shift())
        ], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9).mean()
        
        return {
            'ema9': ema9.iloc[-1],
            'ema21': ema21.iloc[-1],
            'ema50': ema50.iloc[-1],
            'rsi': rsi.iloc[-1],
            'atr': atr.iloc[-1],
            'macd': macd.iloc[-1],
            'macd_signal': signal.iloc[-1]
        }
    
    def _calculate_metrics(
        self,
        trades: List[BacktestTrade],
        equity_curve: List[float],
        strategy_name: str,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> BacktestResult:
        """Calcula métricas do backtest"""
        
        if not trades:
            return BacktestResult(
                strategy=strategy_name,
                symbol=symbol,
                period_start=start_date,
                period_end=end_date,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0,
                total_profit=0,
                total_profit_pips=0,
                max_drawdown=0,
                max_drawdown_pct=0,
                profit_factor=0,
                sharpe_ratio=0,
                avg_trade_duration=0,
                avg_profit_per_trade=0,
                best_trade=0,
                worst_trade=0,
                consecutive_wins=0,
                consecutive_losses=0,
                trades=[]
            )
        
        winning = [t for t in trades if t.profit > 0]
        losing = [t for t in trades if t.profit <= 0]
        
        win_rate = len(winning) / len(trades) if trades else 0
        
        total_profit = sum(t.profit for t in trades)
        total_profit_pips = sum(t.profit_pips for t in trades)
        
        peak = self.initial_balance
        max_dd = 0
        max_dd_pct = 0
        
        for equity in equity_curve:
            if equity > peak:
                peak = equity
            dd = peak - equity
            dd_pct = dd / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
                max_dd_pct = dd_pct
        
        gross_profit = sum(t.profit for t in winning)
        gross_loss = abs(sum(t.profit for t in losing))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        returns = [t.profit for t in trades]
        if len(returns) > 1:
            avg_return = np.mean(returns)
            std_return = np.std(returns)
            sharpe = (avg_return / std_return) * np.sqrt(252) if std_return > 0 else 0
        else:
            sharpe = 0
        
        durations = []
        for t in trades:
            if isinstance(t.entry_time, datetime) and isinstance(t.exit_time, datetime):
                dur = (t.exit_time - t.entry_time).total_seconds() / 60
                durations.append(dur)
        avg_duration = np.mean(durations) if durations else 0
        
        max_consec_wins = 0
        max_consec_losses = 0
        current_wins = 0
        current_losses = 0
        
        for t in trades:
            if t.profit > 0:
                current_wins += 1
                current_losses = 0
                max_consec_wins = max(max_consec_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_consec_losses = max(max_consec_losses, current_losses)
        
        return BacktestResult(
            strategy=strategy_name,
            symbol=symbol,
            period_start=start_date,
            period_end=end_date,
            total_trades=len(trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            win_rate=round(win_rate * 100, 2),
            total_profit=round(total_profit, 2),
            total_profit_pips=round(total_profit_pips, 1),
            max_drawdown=round(max_dd, 2),
            max_drawdown_pct=round(max_dd_pct * 100, 2),
            profit_factor=round(profit_factor, 2),
            sharpe_ratio=round(sharpe, 2),
            avg_trade_duration=round(avg_duration, 1),
            avg_profit_per_trade=round(total_profit / len(trades), 2),
            best_trade=max(t.profit for t in trades),
            worst_trade=min(t.profit for t in trades),
            consecutive_wins=max_consec_wins,
            consecutive_losses=max_consec_losses,
            trades=trades
        )
    
    def generate_report(self, result: BacktestResult, output_path: str = None) -> str:
        """Gera relatório do backtest"""
        
        report = f"""
================================================================================
                         RELATÓRIO DE BACKTEST
================================================================================

Estratégia: {result.strategy}
Símbolo: {result.symbol}
Período: {result.period_start} a {result.period_end}

--------------------------------------------------------------------------------
                              RESUMO
--------------------------------------------------------------------------------

Total de Trades:     {result.total_trades}
Trades Vencedores:   {result.winning_trades}
Trades Perdedores:   {result.losing_trades}
Win Rate:            {result.win_rate}%

Lucro Total:         ${result.total_profit}
Lucro em Pips:       {result.total_profit_pips}
Lucro Médio/Trade:   ${result.avg_profit_per_trade}

Melhor Trade:        ${result.best_trade}
Pior Trade:          ${result.worst_trade}

--------------------------------------------------------------------------------
                           MÉTRICAS DE RISCO
--------------------------------------------------------------------------------

Max Drawdown:        ${result.max_drawdown} ({result.max_drawdown_pct}%)
Profit Factor:       {result.profit_factor}
Sharpe Ratio:        {result.sharpe_ratio}

Vitórias Consec.:    {result.consecutive_wins}
Derrotas Consec.:    {result.consecutive_losses}

Duração Média:       {result.avg_trade_duration} minutos

================================================================================
"""
        
        if output_path:
            with open(output_path, 'w') as f:
                f.write(report)
            
            json_path = output_path.replace('.txt', '.json')
            with open(json_path, 'w') as f:
                json.dump(asdict(result), f, indent=2, default=str)
        
        return report
