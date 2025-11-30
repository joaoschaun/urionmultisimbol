"""
Backtesting Engine - Motor de Backtesting para Urion
Inspirado em Backtrader e Freqtrade

Features:
- Simulação de trades em dados históricos
- Suporte a múltiplos timeframes
- Cálculo de métricas de performance
- Visualização de resultados
- Walk-forward analysis
- Otimização de parâmetros
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
from loguru import logger
import json
import os


class OrderType(Enum):
    """Tipos de ordem"""
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    """Status da ordem"""
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Order:
    """Representa uma ordem de trading"""
    id: int
    symbol: str
    order_type: OrderType
    volume: float
    price: float
    sl: float = 0
    tp: float = 0
    status: OrderStatus = OrderStatus.PENDING
    fill_price: Optional[float] = None
    fill_time: Optional[datetime] = None
    comment: str = ""


@dataclass
class Position:
    """Representa uma posição aberta"""
    id: int
    symbol: str
    order_type: OrderType
    volume: float
    entry_price: float
    entry_time: datetime
    sl: float = 0
    tp: float = 0
    current_price: float = 0
    unrealized_pnl: float = 0
    comment: str = ""


@dataclass
class Trade:
    """Representa um trade fechado"""
    id: int
    symbol: str
    order_type: OrderType
    volume: float
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    pnl: float
    pnl_pips: float
    commission: float = 0
    swap: float = 0
    sl: float = 0
    tp: float = 0
    exit_reason: str = ""
    comment: str = ""
    
    @property
    def duration(self) -> timedelta:
        """Duração do trade"""
        return self.exit_time - self.entry_time
    
    @property
    def r_multiple(self) -> float:
        """R-Multiple do trade"""
        risk = abs(self.entry_price - self.sl)
        if risk == 0:
            return 0
        reward = self.exit_price - self.entry_price if self.order_type == OrderType.BUY else self.entry_price - self.exit_price
        return reward / risk


@dataclass
class BacktestResult:
    """Resultado de um backtest"""
    start_date: datetime
    end_date: datetime
    initial_balance: float
    final_balance: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    total_pnl: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    sqn: float
    trades: List[Trade]
    equity_curve: pd.Series
    drawdown_curve: pd.Series
    
    def to_dict(self) -> Dict:
        """Converte para dicionário"""
        return {
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'initial_balance': self.initial_balance,
            'final_balance': self.final_balance,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': round(self.win_rate, 2),
            'profit_factor': round(self.profit_factor, 2),
            'total_pnl': round(self.total_pnl, 2),
            'max_drawdown': round(self.max_drawdown, 2),
            'max_drawdown_pct': round(self.max_drawdown_pct, 2),
            'sharpe_ratio': round(self.sharpe_ratio, 2),
            'sortino_ratio': round(self.sortino_ratio, 2),
            'calmar_ratio': round(self.calmar_ratio, 2),
            'sqn': round(self.sqn, 2),
        }
    
    def summary(self) -> str:
        """Retorna resumo formatado"""
        return f"""
╔══════════════════════════════════════════╗
║        BACKTEST RESULT SUMMARY           ║
╠══════════════════════════════════════════╣
║ Period: {self.start_date.date()} to {self.end_date.date()}
║ Initial Balance: ${self.initial_balance:,.2f}
║ Final Balance: ${self.final_balance:,.2f}
║ Total P&L: ${self.total_pnl:,.2f} ({(self.total_pnl/self.initial_balance)*100:.1f}%)
╠══════════════════════════════════════════╣
║ Total Trades: {self.total_trades}
║ Wins: {self.winning_trades} | Losses: {self.losing_trades}
║ Win Rate: {self.win_rate:.1f}%
║ Profit Factor: {self.profit_factor:.2f}
╠══════════════════════════════════════════╣
║ Max Drawdown: ${self.max_drawdown:,.2f} ({self.max_drawdown_pct:.1f}%)
║ Sharpe Ratio: {self.sharpe_ratio:.2f}
║ Sortino Ratio: {self.sortino_ratio:.2f}
║ Calmar Ratio: {self.calmar_ratio:.2f}
║ SQN: {self.sqn:.2f}
╚══════════════════════════════════════════╝
"""


class BaseStrategy(ABC):
    """
    Classe base para estratégias de backtest
    
    Subclasses devem implementar:
    - on_bar(): Lógica de análise a cada barra
    - should_enter(): Condição de entrada
    - should_exit(): Condição de saída
    """
    
    def __init__(self, name: str = "BaseStrategy"):
        self.name = name
        self.params: Dict[str, Any] = {}
        
    @abstractmethod
    def on_bar(self, data: pd.DataFrame, index: int) -> None:
        """
        Chamado a cada nova barra
        
        Args:
            data: DataFrame com dados OHLCV
            index: Índice da barra atual
        """
        pass
    
    @abstractmethod
    def should_enter(self, data: pd.DataFrame, index: int) -> Optional[Dict]:
        """
        Verifica se deve entrar em uma posição
        
        Args:
            data: DataFrame com dados OHLCV
            index: Índice da barra atual
            
        Returns:
            Dict com {type: 'BUY'|'SELL', sl: float, tp: float} ou None
        """
        pass
    
    @abstractmethod
    def should_exit(self, position: Position, data: pd.DataFrame, index: int) -> bool:
        """
        Verifica se deve sair de uma posição
        
        Args:
            position: Posição atual
            data: DataFrame com dados OHLCV
            index: Índice da barra atual
            
        Returns:
            True se deve sair
        """
        pass
    
    def calculate_position_size(self, balance: float, risk_pct: float, sl_distance: float, pip_value: float = 10) -> float:
        """
        Calcula tamanho da posição baseado em risco
        
        Args:
            balance: Saldo da conta
            risk_pct: Porcentagem de risco (0.01 = 1%)
            sl_distance: Distância do SL em pips
            pip_value: Valor do pip por lote
            
        Returns:
            Volume da posição
        """
        if sl_distance <= 0:
            return 0.01
        
        risk_amount = balance * risk_pct
        position_size = risk_amount / (sl_distance * pip_value)
        
        # Limitar entre 0.01 e 10 lotes
        return max(0.01, min(10.0, round(position_size, 2)))


class BacktestEngine:
    """
    Motor de Backtesting
    
    Features:
    - Simulação realista de ordens
    - Spread e comissões configuráveis
    - Slippage simulado
    - Suporte a múltiplas posições
    - Cálculo de métricas avançadas
    """
    
    def __init__(
        self,
        initial_balance: float = 10000,
        commission: float = 0.0001,      # 0.01% por trade
        spread_pips: float = 1.5,        # Spread em pips
        slippage_pips: float = 0.5,      # Slippage máximo
        pip_value: float = 10,           # Valor do pip por lote padrão
        leverage: int = 100,
        max_positions: int = 5,
        risk_per_trade: float = 0.01     # 1% de risco por trade
    ):
        """
        Inicializa o motor de backtest
        
        Args:
            initial_balance: Saldo inicial
            commission: Comissão como fração (0.0001 = 0.01%)
            spread_pips: Spread em pips
            slippage_pips: Slippage máximo em pips
            pip_value: Valor do pip por lote
            leverage: Alavancagem
            max_positions: Número máximo de posições simultâneas
            risk_per_trade: Risco por trade como fração
        """
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.equity = initial_balance
        self.commission = commission
        self.spread_pips = spread_pips
        self.slippage_pips = slippage_pips
        self.pip_value = pip_value
        self.leverage = leverage
        self.max_positions = max_positions
        self.risk_per_trade = risk_per_trade
        
        # Estado
        self._positions: List[Position] = []
        self._trades: List[Trade] = []
        self._orders: List[Order] = []
        self._order_counter = 0
        self._trade_counter = 0
        
        # Histórico
        self._equity_history: List[Tuple[datetime, float]] = []
        self._balance_history: List[Tuple[datetime, float]] = []
        
        logger.info(
            f"📊 Backtest Engine inicializado | "
            f"Balance: ${initial_balance:,.2f} | "
            f"Leverage: 1:{leverage}"
        )
    
    def reset(self):
        """Reseta o estado do engine"""
        self.balance = self.initial_balance
        self.equity = self.initial_balance
        self._positions.clear()
        self._trades.clear()
        self._orders.clear()
        self._equity_history.clear()
        self._balance_history.clear()
        self._order_counter = 0
        self._trade_counter = 0
    
    def _get_pip_size(self, symbol: str) -> float:
        """Retorna tamanho do pip para o símbolo"""
        if 'JPY' in symbol:
            return 0.01
        return 0.0001
    
    def _apply_spread(self, price: float, order_type: OrderType, symbol: str) -> float:
        """Aplica spread ao preço"""
        pip_size = self._get_pip_size(symbol)
        spread = self.spread_pips * pip_size
        
        if order_type == OrderType.BUY:
            return price + spread  # Compra no ask
        else:
            return price  # Vende no bid
    
    def _apply_slippage(self, price: float, order_type: OrderType, symbol: str) -> float:
        """Aplica slippage aleatório"""
        pip_size = self._get_pip_size(symbol)
        slippage = np.random.uniform(0, self.slippage_pips) * pip_size
        
        if order_type == OrderType.BUY:
            return price + slippage
        else:
            return price - slippage
    
    def _calculate_pnl(
        self,
        order_type: OrderType,
        entry_price: float,
        exit_price: float,
        volume: float,
        symbol: str
    ) -> Tuple[float, float]:
        """
        Calcula P&L de um trade
        
        Returns:
            (pnl_money, pnl_pips)
        """
        pip_size = self._get_pip_size(symbol)
        
        if order_type == OrderType.BUY:
            pips = (exit_price - entry_price) / pip_size
        else:
            pips = (entry_price - exit_price) / pip_size
        
        pnl = pips * self.pip_value * volume
        
        # Subtrair comissão
        commission = (entry_price + exit_price) * volume * self.commission * 100000
        pnl -= commission
        
        return pnl, pips
    
    def open_position(
        self,
        symbol: str,
        order_type: OrderType,
        volume: float,
        price: float,
        timestamp: datetime,
        sl: float = 0,
        tp: float = 0,
        comment: str = ""
    ) -> Optional[Position]:
        """
        Abre uma nova posição
        
        Args:
            symbol: Símbolo do ativo
            order_type: BUY ou SELL
            volume: Volume da posição
            price: Preço de entrada
            timestamp: Timestamp da entrada
            sl: Stop Loss
            tp: Take Profit
            comment: Comentário
            
        Returns:
            Position criada ou None se falhar
        """
        # Verificar limite de posições
        if len(self._positions) >= self.max_positions:
            logger.warning("Limite de posições atingido")
            return None
        
        # Verificar margem
        required_margin = (price * volume * 100000) / self.leverage
        if required_margin > self.balance * 0.9:  # 90% máximo
            logger.warning("Margem insuficiente")
            return None
        
        # Aplicar spread e slippage
        fill_price = self._apply_spread(price, order_type, symbol)
        fill_price = self._apply_slippage(fill_price, order_type, symbol)
        
        # Criar posição
        self._order_counter += 1
        position = Position(
            id=self._order_counter,
            symbol=symbol,
            order_type=order_type,
            volume=volume,
            entry_price=fill_price,
            entry_time=timestamp,
            sl=sl,
            tp=tp,
            current_price=fill_price,
            comment=comment
        )
        
        self._positions.append(position)
        
        logger.debug(
            f"📈 Posição aberta | #{position.id} {symbol} {order_type.value} "
            f"{volume} @ {fill_price:.5f}"
        )
        
        return position
    
    def close_position(
        self,
        position: Position,
        price: float,
        timestamp: datetime,
        exit_reason: str = "manual"
    ) -> Trade:
        """
        Fecha uma posição
        
        Args:
            position: Posição a fechar
            price: Preço de saída
            timestamp: Timestamp da saída
            exit_reason: Razão do fechamento
            
        Returns:
            Trade resultante
        """
        # Aplicar spread para saída
        opposite_type = OrderType.SELL if position.order_type == OrderType.BUY else OrderType.BUY
        exit_price = self._apply_spread(price, opposite_type, position.symbol)
        exit_price = self._apply_slippage(exit_price, opposite_type, position.symbol)
        
        # Calcular P&L
        pnl, pips = self._calculate_pnl(
            position.order_type,
            position.entry_price,
            exit_price,
            position.volume,
            position.symbol
        )
        
        # Atualizar balance
        self.balance += pnl
        
        # Criar trade
        self._trade_counter += 1
        trade = Trade(
            id=self._trade_counter,
            symbol=position.symbol,
            order_type=position.order_type,
            volume=position.volume,
            entry_price=position.entry_price,
            exit_price=exit_price,
            entry_time=position.entry_time,
            exit_time=timestamp,
            pnl=pnl,
            pnl_pips=pips,
            sl=position.sl,
            tp=position.tp,
            exit_reason=exit_reason,
            comment=position.comment
        )
        
        self._trades.append(trade)
        self._positions.remove(position)
        
        emoji = "💚" if pnl > 0 else "❌"
        logger.debug(
            f"{emoji} Posição fechada | #{position.id} {position.symbol} | "
            f"P&L: ${pnl:.2f} ({pips:.1f} pips) | Razão: {exit_reason}"
        )
        
        return trade
    
    def check_sl_tp(self, position: Position, high: float, low: float, timestamp: datetime) -> Optional[Trade]:
        """
        Verifica se SL ou TP foram atingidos
        
        Args:
            position: Posição a verificar
            high: Máxima da barra
            low: Mínima da barra
            timestamp: Timestamp atual
            
        Returns:
            Trade se fechou, None caso contrário
        """
        if position.order_type == OrderType.BUY:
            # Check SL
            if position.sl > 0 and low <= position.sl:
                return self.close_position(position, position.sl, timestamp, "stop_loss")
            # Check TP
            if position.tp > 0 and high >= position.tp:
                return self.close_position(position, position.tp, timestamp, "take_profit")
        else:  # SELL
            # Check SL
            if position.sl > 0 and high >= position.sl:
                return self.close_position(position, position.sl, timestamp, "stop_loss")
            # Check TP
            if position.tp > 0 and low <= position.tp:
                return self.close_position(position, position.tp, timestamp, "take_profit")
        
        return None
    
    def update_equity(self, current_prices: Dict[str, float], timestamp: datetime):
        """
        Atualiza equity baseado em preços atuais
        
        Args:
            current_prices: Dict {symbol: price}
            timestamp: Timestamp atual
        """
        unrealized_pnl = 0
        
        for position in self._positions:
            price = current_prices.get(position.symbol, position.current_price)
            position.current_price = price
            
            pnl, _ = self._calculate_pnl(
                position.order_type,
                position.entry_price,
                price,
                position.volume,
                position.symbol
            )
            position.unrealized_pnl = pnl
            unrealized_pnl += pnl
        
        self.equity = self.balance + unrealized_pnl
        
        self._equity_history.append((timestamp, self.equity))
        self._balance_history.append((timestamp, self.balance))
    
    def run(
        self,
        strategy: BaseStrategy,
        data: pd.DataFrame,
        symbol: str = "EURUSD"
    ) -> BacktestResult:
        """
        Executa backtest com uma estratégia
        
        Args:
            strategy: Estratégia a testar
            data: DataFrame com colunas [open, high, low, close, volume, time]
            symbol: Símbolo do ativo
            
        Returns:
            BacktestResult com métricas
        """
        self.reset()
        
        if 'time' not in data.columns:
            data['time'] = pd.date_range(start='2023-01-01', periods=len(data), freq='H')
        
        logger.info(
            f"🚀 Iniciando backtest | {strategy.name} | "
            f"{symbol} | {len(data)} barras"
        )
        
        start_time = datetime.now()
        
        for i in range(len(data)):
            bar = data.iloc[i]
            timestamp = bar['time'] if isinstance(bar['time'], datetime) else pd.to_datetime(bar['time'])
            
            # 1. Chamar on_bar da estratégia
            strategy.on_bar(data, i)
            
            # 2. Verificar SL/TP das posições abertas
            positions_to_check = self._positions.copy()
            for position in positions_to_check:
                self.check_sl_tp(position, bar['high'], bar['low'], timestamp)
            
            # 3. Verificar saídas da estratégia
            positions_to_check = self._positions.copy()
            for position in positions_to_check:
                if strategy.should_exit(position, data, i):
                    self.close_position(position, bar['close'], timestamp, "strategy_exit")
            
            # 4. Verificar entradas
            if len(self._positions) < self.max_positions:
                signal = strategy.should_enter(data, i)
                
                if signal:
                    order_type = OrderType.BUY if signal['type'] == 'BUY' else OrderType.SELL
                    sl = signal.get('sl', 0)
                    tp = signal.get('tp', 0)
                    
                    # Calcular volume baseado em risco
                    if sl > 0:
                        pip_size = self._get_pip_size(symbol)
                        sl_pips = abs(bar['close'] - sl) / pip_size
                        volume = strategy.calculate_position_size(
                            self.balance,
                            self.risk_per_trade,
                            sl_pips,
                            self.pip_value
                        )
                    else:
                        volume = 0.1  # Volume padrão
                    
                    self.open_position(
                        symbol=symbol,
                        order_type=order_type,
                        volume=volume,
                        price=bar['close'],
                        timestamp=timestamp,
                        sl=sl,
                        tp=tp,
                        comment=signal.get('comment', '')
                    )
            
            # 5. Atualizar equity
            self.update_equity({symbol: bar['close']}, timestamp)
        
        # Fechar posições restantes
        for position in self._positions.copy():
            self.close_position(
                position,
                data.iloc[-1]['close'],
                pd.to_datetime(data.iloc[-1]['time']),
                "end_of_backtest"
            )
        
        # Calcular resultado
        result = self._calculate_result(data)
        
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.success(
            f"✅ Backtest concluído em {elapsed:.1f}s | "
            f"Trades: {result.total_trades} | "
            f"P&L: ${result.total_pnl:.2f}"
        )
        
        return result
    
    def _calculate_result(self, data: pd.DataFrame) -> BacktestResult:
        """Calcula métricas do backtest"""
        
        # Básicas
        winning_trades = [t for t in self._trades if t.pnl > 0]
        losing_trades = [t for t in self._trades if t.pnl < 0]
        
        total_trades = len(self._trades)
        win_count = len(winning_trades)
        loss_count = len(losing_trades)
        
        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
        
        total_wins = sum(t.pnl for t in winning_trades)
        total_losses = abs(sum(t.pnl for t in losing_trades))
        profit_factor = (total_wins / total_losses) if total_losses > 0 else 0
        
        total_pnl = self.balance - self.initial_balance
        
        # Equity curve
        equity_series = pd.Series(
            [e[1] for e in self._equity_history],
            index=[e[0] for e in self._equity_history]
        )
        
        # Drawdown
        rolling_max = equity_series.expanding().max()
        drawdown = equity_series - rolling_max
        max_drawdown = abs(drawdown.min()) if len(drawdown) > 0 else 0
        max_drawdown_pct = (max_drawdown / self.initial_balance * 100) if self.initial_balance > 0 else 0
        
        # Retornos para Sharpe/Sortino
        if len(self._trades) > 1:
            returns = pd.Series([t.pnl for t in self._trades])
            avg_return = returns.mean()
            std_return = returns.std()
            
            # Sharpe (assumindo risk-free = 0)
            sharpe = (avg_return / std_return * np.sqrt(252)) if std_return > 0 else 0
            
            # Sortino (só volatilidade negativa)
            negative_returns = returns[returns < 0]
            downside_std = negative_returns.std() if len(negative_returns) > 0 else std_return
            sortino = (avg_return / downside_std * np.sqrt(252)) if downside_std > 0 else 0
            
            # Calmar
            annual_return = total_pnl / self.initial_balance * 100
            calmar = (annual_return / max_drawdown_pct) if max_drawdown_pct > 0 else 0
            
            # SQN
            sqn = (avg_return * np.sqrt(len(returns))) / std_return if std_return > 0 else 0
        else:
            sharpe = sortino = calmar = sqn = 0
        
        return BacktestResult(
            start_date=pd.to_datetime(data.iloc[0]['time']),
            end_date=pd.to_datetime(data.iloc[-1]['time']),
            initial_balance=self.initial_balance,
            final_balance=self.balance,
            total_trades=total_trades,
            winning_trades=win_count,
            losing_trades=loss_count,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_pnl=total_pnl,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            sqn=sqn,
            trades=self._trades.copy(),
            equity_curve=equity_series,
            drawdown_curve=drawdown
        )


# ==================== Exemplo de Estratégia ====================

class SMAStrategy(BaseStrategy):
    """Estratégia simples de cruzamento de médias móveis"""
    
    def __init__(self, fast_period: int = 10, slow_period: int = 20, atr_period: int = 14):
        super().__init__("SMA Crossover")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.atr_period = atr_period
        
        self._sma_fast: Optional[pd.Series] = None
        self._sma_slow: Optional[pd.Series] = None
        self._atr: Optional[pd.Series] = None
    
    def on_bar(self, data: pd.DataFrame, index: int):
        """Calcula indicadores"""
        if index < self.slow_period:
            return
        
        # Calcular SMAs
        self._sma_fast = data['close'].rolling(self.fast_period).mean()
        self._sma_slow = data['close'].rolling(self.slow_period).mean()
        
        # Calcular ATR
        high_low = data['high'] - data['low']
        high_close = abs(data['high'] - data['close'].shift())
        low_close = abs(data['low'] - data['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        self._atr = tr.rolling(self.atr_period).mean()
    
    def should_enter(self, data: pd.DataFrame, index: int) -> Optional[Dict]:
        """Verifica condição de entrada"""
        if index < self.slow_period + 1:
            return None
        
        if self._sma_fast is None or self._sma_slow is None:
            return None
        
        # Cruzamento para cima
        if (self._sma_fast.iloc[index] > self._sma_slow.iloc[index] and
            self._sma_fast.iloc[index-1] <= self._sma_slow.iloc[index-1]):
            
            atr = self._atr.iloc[index] if self._atr is not None else data['close'].iloc[index] * 0.01
            
            return {
                'type': 'BUY',
                'sl': data['close'].iloc[index] - atr * 2,
                'tp': data['close'].iloc[index] + atr * 3,
                'comment': 'SMA Crossover UP'
            }
        
        # Cruzamento para baixo
        if (self._sma_fast.iloc[index] < self._sma_slow.iloc[index] and
            self._sma_fast.iloc[index-1] >= self._sma_slow.iloc[index-1]):
            
            atr = self._atr.iloc[index] if self._atr is not None else data['close'].iloc[index] * 0.01
            
            return {
                'type': 'SELL',
                'sl': data['close'].iloc[index] + atr * 2,
                'tp': data['close'].iloc[index] - atr * 3,
                'comment': 'SMA Crossover DOWN'
            }
        
        return None
    
    def should_exit(self, position: Position, data: pd.DataFrame, index: int) -> bool:
        """Verifica condição de saída"""
        if self._sma_fast is None or self._sma_slow is None:
            return False
        
        # Sair no cruzamento oposto
        if position.order_type == OrderType.BUY:
            if self._sma_fast.iloc[index] < self._sma_slow.iloc[index]:
                return True
        else:
            if self._sma_fast.iloc[index] > self._sma_slow.iloc[index]:
                return True
        
        return False


# Exemplo de uso:
"""
from backtesting.engine import BacktestEngine, SMAStrategy
import pandas as pd

# Carregar dados
data = pd.read_csv('EURUSD_H1.csv')

# Criar engine
engine = BacktestEngine(
    initial_balance=10000,
    spread_pips=1.5,
    risk_per_trade=0.01
)

# Criar estratégia
strategy = SMAStrategy(fast_period=10, slow_period=20)

# Executar backtest
result = engine.run(strategy, data, symbol='EURUSD')

# Ver resultado
print(result.summary())

# Exportar trades
trades_df = pd.DataFrame([t.__dict__ for t in result.trades])
trades_df.to_csv('backtest_trades.csv')
"""
