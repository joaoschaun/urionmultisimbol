# -*- coding: utf-8 -*-
"""
Paper Trading Engine - Simulação de Trading em Tempo Real

Simula condições reais de mercado:
- Latência realista
- Slippage de mercado
- Rejeição de ordens
- Partial fills
- Spread variável
- Execução assíncrona
"""

import asyncio
import random
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import threading
import logging
from collections import deque
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class OrderStatus(Enum):
    """Status de uma ordem"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class OrderType(Enum):
    """Tipos de ordem"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


@dataclass
class PaperOrder:
    """Ordem no paper trading"""
    order_id: str
    symbol: str
    order_type: OrderType
    direction: str  # 'buy' ou 'sell'
    volume: float
    price: float = 0.0  # Para limit orders
    stop_price: float = 0.0  # Para stop orders
    
    # Status
    status: OrderStatus = OrderStatus.PENDING
    filled_volume: float = 0.0
    avg_fill_price: float = 0.0
    
    # Timing
    created_at: datetime = field(default_factory=datetime.now)
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    
    # Execução
    latency_ms: float = 0.0
    slippage: float = 0.0
    rejection_reason: str = ""
    
    # Meta
    strategy: str = ""
    magic: int = 0


@dataclass
class PaperPosition:
    """Posição aberta no paper trading"""
    position_id: str
    symbol: str
    direction: str
    volume: float
    entry_price: float
    entry_time: datetime
    
    # P&L
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    
    # Stops
    stop_loss: float = 0.0
    take_profit: float = 0.0
    
    # Meta
    strategy: str = ""
    magic: int = 0


@dataclass
class PaperTrade:
    """Trade fechado no paper trading"""
    trade_id: str
    symbol: str
    direction: str
    volume: float
    
    entry_price: float = 0.0
    exit_price: float = 0.0
    entry_time: datetime = None
    exit_time: datetime = None
    
    # P&L
    gross_profit: float = 0.0
    commission: float = 0.0
    swap: float = 0.0
    slippage_cost: float = 0.0
    net_profit: float = 0.0
    
    # Meta
    strategy: str = ""
    exit_reason: str = ""


@dataclass
class MarketConditions:
    """Condições de mercado simuladas"""
    symbol: str
    bid: float = 0.0
    ask: float = 0.0
    spread: float = 0.0
    volatility: float = 0.0  # ATR%
    liquidity: float = 1.0  # 0-1, afeta fills
    
    # Horário
    session: str = "london"  # london, ny, asia, off
    is_news_time: bool = False
    
    last_update: datetime = field(default_factory=datetime.now)


class MarketSimulator:
    """Simula condições de mercado realistas"""
    
    def __init__(self):
        # Spreads base por símbolo (em pips)
        self.base_spreads = {
            'XAUUSD': 0.30,
            'EURUSD': 0.10,
            'GBPUSD': 0.15,
            'USDJPY': 0.10,
            'BTCUSD': 50.0,
        }
        
        # Multiplicadores de spread por sessão
        self.session_spread_mult = {
            'london': 1.0,
            'ny': 1.0,
            'asia': 1.5,
            'off': 3.0,  # Fora de horário
        }
        
        # Latência base (ms)
        self.base_latency = 50
        self.latency_std = 30
        
        # Probabilidade de rejeição
        self.rejection_rate = 0.01  # 1%
    
    def get_current_session(self) -> str:
        """Determina sessão atual"""
        hour = datetime.now().hour
        
        if 8 <= hour < 16:  # London
            return 'london'
        elif 13 <= hour < 21:  # NY overlap
            return 'ny'
        elif 0 <= hour < 8:  # Asia
            return 'asia'
        else:
            return 'off'
    
    def simulate_spread(self, symbol: str, volatility: float = 0.0) -> float:
        """Simula spread realista"""
        base = self.base_spreads.get(symbol, 0.20)
        session = self.get_current_session()
        
        # Multiplicadores
        session_mult = self.session_spread_mult[session]
        volatility_mult = 1 + volatility * 2  # Alta vol = spread maior
        random_mult = random.uniform(0.8, 1.2)  # Variação aleatória
        
        spread = base * session_mult * volatility_mult * random_mult
        
        return spread
    
    def simulate_latency(self, is_high_volatility: bool = False) -> float:
        """Simula latência de execução"""
        base = self.base_latency
        
        if is_high_volatility:
            base *= 2
        
        latency = max(10, random.gauss(base, self.latency_std))
        
        return latency
    
    def simulate_slippage(
        self, 
        symbol: str, 
        volume: float, 
        volatility: float = 0.0
    ) -> float:
        """Simula slippage em pips"""
        # Slippage base
        base_slippage = 0.1  # 0.1 pip
        
        # Aumenta com volume
        volume_mult = 1 + (volume / 10)  # Maior volume = mais slippage
        
        # Aumenta com volatilidade
        vol_mult = 1 + volatility * 5
        
        # Random component
        random_mult = random.uniform(0, 2)
        
        slippage = base_slippage * volume_mult * vol_mult * random_mult
        
        return slippage
    
    def should_reject_order(
        self, 
        order: PaperOrder, 
        liquidity: float = 1.0
    ) -> Tuple[bool, str]:
        """Determina se ordem deve ser rejeitada"""
        
        # Taxa base de rejeição
        if random.random() < self.rejection_rate:
            reasons = [
                "Market closed",
                "Price expired",
                "Insufficient liquidity",
                "Connection timeout",
            ]
            return True, random.choice(reasons)
        
        # Rejeição por volume alto em baixa liquidez
        if order.volume > 1.0 and liquidity < 0.5:
            if random.random() < 0.3:  # 30% chance
                return True, "Insufficient liquidity for size"
        
        return False, ""
    
    def simulate_fill_probability(
        self, 
        order: PaperOrder, 
        current_price: float,
        volatility: float = 0.0
    ) -> float:
        """Probabilidade de fill para limit orders"""
        
        if order.order_type == OrderType.MARKET:
            return 1.0  # Market orders sempre preenchem
        
        if order.order_type == OrderType.LIMIT:
            # Distância do preço atual
            if order.direction == 'buy':
                distance = current_price - order.price
            else:
                distance = order.price - current_price
            
            # Quanto mais longe, menor a chance
            if distance > 0:
                prob = max(0, 1 - distance / (current_price * 0.01))
            else:
                prob = 1.0
            
            return prob
        
        return 0.5


class PaperTradingEngine:
    """
    Engine de Paper Trading
    
    Simula execução em tempo real com:
    - Latência realista
    - Slippage de mercado
    - Rejeição de ordens
    - Partial fills
    - P&L em tempo real
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Estado
        self.initial_balance = self.config.get('paper_trading', {}).get('initial_balance', 10000)
        self.balance = self.initial_balance
        self.equity = self.initial_balance
        
        # Ordens e posições
        self.orders: Dict[str, PaperOrder] = {}
        self.positions: Dict[str, PaperPosition] = {}
        self.closed_trades: List[PaperTrade] = []
        
        # Preços de mercado (simulados ou de API)
        self.market_prices: Dict[str, Dict[str, float]] = {}
        
        # Simulador
        self.market_sim = MarketSimulator()
        
        # Callbacks
        self.on_order_update: Optional[Callable] = None
        self.on_trade_closed: Optional[Callable] = None
        self.on_position_update: Optional[Callable] = None
        
        # Threading
        self.running = False
        self._update_thread: Optional[threading.Thread] = None
        self._order_counter = 0
        self._trade_counter = 0
        self._position_counter = 0
        
        # Histórico
        self.equity_history: List[Tuple[datetime, float]] = []
        self.balance_history: List[Tuple[datetime, float]] = []
        
        # Persistência
        self.data_dir = Path(self.config.get('data_dir', 'data/paper_trading'))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"PaperTradingEngine inicializado com ${self.initial_balance}")
    
    def start(self):
        """Inicia o engine"""
        if self.running:
            return
        
        self.running = True
        
        # Thread de atualização
        self._update_thread = threading.Thread(
            target=self._update_loop,
            daemon=True,
            name="PaperTradingUpdate"
        )
        self._update_thread.start()
        
        # Carregar estado anterior
        self._load_state()
        
        logger.info("Paper Trading Engine iniciado")
    
    def stop(self):
        """Para o engine"""
        self.running = False
        
        # Salvar estado
        self._save_state()
        
        logger.info("Paper Trading Engine parado")
    
    def update_price(self, symbol: str, bid: float, ask: float):
        """Atualiza preço de mercado"""
        self.market_prices[symbol] = {
            'bid': bid,
            'ask': ask,
            'mid': (bid + ask) / 2,
            'spread': ask - bid,
            'time': datetime.now()
        }
        
        # Atualizar posições abertas
        self._update_positions(symbol)
    
    async def submit_order(
        self,
        symbol: str,
        direction: str,
        volume: float,
        order_type: OrderType = OrderType.MARKET,
        price: float = 0.0,
        stop_loss: float = 0.0,
        take_profit: float = 0.0,
        strategy: str = "",
        magic: int = 0
    ) -> PaperOrder:
        """
        Submete uma ordem ao paper trading
        
        Args:
            symbol: Símbolo do ativo
            direction: 'buy' ou 'sell'
            volume: Volume em lotes
            order_type: Tipo de ordem
            price: Preço para limit/stop orders
            stop_loss: Stop loss
            take_profit: Take profit
            strategy: Nome da estratégia
            magic: Magic number
            
        Returns:
            PaperOrder
        """
        self._order_counter += 1
        order_id = f"P{self._order_counter:08d}"
        
        order = PaperOrder(
            order_id=order_id,
            symbol=symbol,
            order_type=order_type,
            direction=direction,
            volume=volume,
            price=price,
            strategy=strategy,
            magic=magic
        )
        
        self.orders[order_id] = order
        
        # Simular processamento assíncrono
        asyncio.create_task(self._process_order(order, stop_loss, take_profit))
        
        return order
    
    async def _process_order(
        self, 
        order: PaperOrder,
        stop_loss: float = 0.0,
        take_profit: float = 0.0
    ):
        """Processa uma ordem de forma assíncrona"""
        
        # Simular latência
        latency = self.market_sim.simulate_latency()
        order.latency_ms = latency
        await asyncio.sleep(latency / 1000)
        
        order.submitted_at = datetime.now()
        order.status = OrderStatus.SUBMITTED
        
        # Verificar rejeição
        should_reject, reason = self.market_sim.should_reject_order(order)
        
        if should_reject:
            order.status = OrderStatus.REJECTED
            order.rejection_reason = reason
            logger.warning(f"Ordem {order.order_id} rejeitada: {reason}")
            
            if self.on_order_update:
                self.on_order_update(order)
            return
        
        # Obter preço atual
        prices = self.market_prices.get(order.symbol, {})
        if not prices:
            order.status = OrderStatus.REJECTED
            order.rejection_reason = "No price available"
            return
        
        # Determinar preço de execução
        if order.order_type == OrderType.MARKET:
            if order.direction == 'buy':
                base_price = prices['ask']
            else:
                base_price = prices['bid']
            
            # Aplicar slippage
            slippage = self.market_sim.simulate_slippage(order.symbol, order.volume)
            order.slippage = slippage
            
            if order.direction == 'buy':
                fill_price = base_price + slippage
            else:
                fill_price = base_price - slippage
            
            # Fill imediato para market orders
            order.filled_volume = order.volume
            order.avg_fill_price = fill_price
            order.status = OrderStatus.FILLED
            order.filled_at = datetime.now()
            
            # Criar posição
            self._create_position(order, stop_loss, take_profit)
            
        elif order.order_type == OrderType.LIMIT:
            # Limit orders podem não preencher imediatamente
            fill_prob = self.market_sim.simulate_fill_probability(
                order, prices['mid']
            )
            
            if random.random() < fill_prob:
                order.filled_volume = order.volume
                order.avg_fill_price = order.price
                order.status = OrderStatus.FILLED
                order.filled_at = datetime.now()
                
                self._create_position(order, stop_loss, take_profit)
            else:
                # Ordem fica pendente
                order.status = OrderStatus.SUBMITTED
        
        logger.info(
            f"Ordem {order.order_id}: {order.status.value} @ "
            f"{order.avg_fill_price:.5f} (latency: {order.latency_ms:.0f}ms, "
            f"slippage: {order.slippage:.2f} pips)"
        )
        
        if self.on_order_update:
            self.on_order_update(order)
    
    def _create_position(
        self, 
        order: PaperOrder,
        stop_loss: float = 0.0,
        take_profit: float = 0.0
    ):
        """Cria posição a partir de ordem preenchida"""
        
        self._position_counter += 1
        position_id = f"PP{self._position_counter:08d}"
        
        position = PaperPosition(
            position_id=position_id,
            symbol=order.symbol,
            direction=order.direction,
            volume=order.filled_volume,
            entry_price=order.avg_fill_price,
            entry_time=order.filled_at,
            current_price=order.avg_fill_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy=order.strategy,
            magic=order.magic
        )
        
        self.positions[position_id] = position
        
        logger.info(f"Posição {position_id} aberta: {order.direction} {order.volume} @ {order.avg_fill_price:.5f}")
        
        if self.on_position_update:
            self.on_position_update(position)
    
    def close_position(
        self, 
        position_id: str, 
        reason: str = "manual"
    ) -> Optional[PaperTrade]:
        """Fecha uma posição"""
        
        if position_id not in self.positions:
            logger.warning(f"Posição {position_id} não encontrada")
            return None
        
        position = self.positions[position_id]
        prices = self.market_prices.get(position.symbol, {})
        
        if not prices:
            logger.error(f"Sem preço para {position.symbol}")
            return None
        
        # Preço de saída
        if position.direction == 'buy':
            exit_price = prices['bid']
        else:
            exit_price = prices['ask']
        
        # Aplicar slippage
        slippage = self.market_sim.simulate_slippage(position.symbol, position.volume)
        if position.direction == 'buy':
            exit_price -= slippage
        else:
            exit_price += slippage
        
        # Calcular P&L
        if position.direction == 'buy':
            points = exit_price - position.entry_price
        else:
            points = position.entry_price - exit_price
        
        gross_profit = points * position.volume * 100  # Simplificado
        
        # Custos
        commission = 7.0 * position.volume  # $7/lot roundtrip
        slippage_cost = slippage * position.volume * 10
        
        # Swap (simplificado)
        holding_hours = (datetime.now() - position.entry_time).total_seconds() / 3600
        swap = -0.5 * position.volume * (holding_hours / 24)  # Estimado
        
        net_profit = gross_profit - commission - slippage_cost + swap
        
        # Criar trade
        self._trade_counter += 1
        trade = PaperTrade(
            trade_id=f"PT{self._trade_counter:08d}",
            symbol=position.symbol,
            direction=position.direction,
            volume=position.volume,
            entry_price=position.entry_price,
            exit_price=exit_price,
            entry_time=position.entry_time,
            exit_time=datetime.now(),
            gross_profit=gross_profit,
            commission=commission,
            swap=swap,
            slippage_cost=slippage_cost,
            net_profit=net_profit,
            strategy=position.strategy,
            exit_reason=reason
        )
        
        self.closed_trades.append(trade)
        
        # Atualizar balance
        self.balance += net_profit
        
        # Remover posição
        del self.positions[position_id]
        
        logger.info(
            f"Trade {trade.trade_id} fechado: {net_profit:+.2f} "
            f"({reason}) - Balance: ${self.balance:.2f}"
        )
        
        if self.on_trade_closed:
            self.on_trade_closed(trade)
        
        return trade
    
    def _update_positions(self, symbol: str):
        """Atualiza P&L das posições abertas"""
        
        prices = self.market_prices.get(symbol, {})
        if not prices:
            return
        
        for pos_id, position in list(self.positions.items()):
            if position.symbol != symbol:
                continue
            
            # Atualizar preço atual
            if position.direction == 'buy':
                position.current_price = prices['bid']
                pnl = (position.current_price - position.entry_price) * position.volume * 100
            else:
                position.current_price = prices['ask']
                pnl = (position.entry_price - position.current_price) * position.volume * 100
            
            position.unrealized_pnl = pnl
            
            # Verificar SL/TP
            if position.stop_loss > 0:
                if position.direction == 'buy' and position.current_price <= position.stop_loss:
                    self.close_position(pos_id, "stop_loss")
                    continue
                elif position.direction == 'sell' and position.current_price >= position.stop_loss:
                    self.close_position(pos_id, "stop_loss")
                    continue
            
            if position.take_profit > 0:
                if position.direction == 'buy' and position.current_price >= position.take_profit:
                    self.close_position(pos_id, "take_profit")
                    continue
                elif position.direction == 'sell' and position.current_price <= position.take_profit:
                    self.close_position(pos_id, "take_profit")
                    continue
        
        # Atualizar equity
        total_unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        self.equity = self.balance + total_unrealized
    
    def _update_loop(self):
        """Loop de atualização em background"""
        while self.running:
            try:
                # Atualizar posições
                for symbol in self.market_prices:
                    self._update_positions(symbol)
                
                # Registrar histórico
                now = datetime.now()
                self.equity_history.append((now, self.equity))
                self.balance_history.append((now, self.balance))
                
                # Limitar histórico a 1 semana
                cutoff = now - timedelta(days=7)
                self.equity_history = [(t, e) for t, e in self.equity_history if t > cutoff]
                self.balance_history = [(t, b) for t, b in self.balance_history if t > cutoff]
                
            except Exception as e:
                logger.error(f"Erro no update loop: {e}")
            
            time.sleep(1)  # Atualizar a cada segundo
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do paper trading"""
        
        trades = self.closed_trades
        
        if not trades:
            return {
                'balance': self.balance,
                'equity': self.equity,
                'initial_balance': self.initial_balance,
                'total_trades': 0,
                'message': 'Nenhum trade fechado ainda'
            }
        
        profits = [t.net_profit for t in trades]
        wins = [p for p in profits if p > 0]
        losses = [p for p in profits if p < 0]
        
        # Calcular drawdown
        peak = self.initial_balance
        max_dd = 0
        equity_curve = [self.initial_balance]
        
        for t in trades:
            equity_curve.append(equity_curve[-1] + t.net_profit)
            if equity_curve[-1] > peak:
                peak = equity_curve[-1]
            dd = (peak - equity_curve[-1]) / peak
            max_dd = max(max_dd, dd)
        
        return {
            'balance': self.balance,
            'equity': self.equity,
            'initial_balance': self.initial_balance,
            'total_return': (self.balance - self.initial_balance) / self.initial_balance * 100,
            'total_trades': len(trades),
            'winning_trades': len(wins),
            'losing_trades': len(losses),
            'win_rate': len(wins) / len(trades) * 100 if trades else 0,
            'total_profit': sum(profits),
            'avg_profit': np.mean(profits) if profits else 0,
            'avg_win': np.mean(wins) if wins else 0,
            'avg_loss': np.mean(losses) if losses else 0,
            'profit_factor': sum(wins) / abs(sum(losses)) if losses else float('inf'),
            'max_drawdown': max_dd * 100,
            'open_positions': len(self.positions),
            'unrealized_pnl': sum(p.unrealized_pnl for p in self.positions.values()),
            
            # Por estratégia
            'by_strategy': self._get_stats_by_strategy(),
        }
    
    def _get_stats_by_strategy(self) -> Dict[str, Dict]:
        """Estatísticas por estratégia"""
        stats = {}
        
        for trade in self.closed_trades:
            strat = trade.strategy or 'Unknown'
            if strat not in stats:
                stats[strat] = {'trades': 0, 'profit': 0, 'wins': 0}
            
            stats[strat]['trades'] += 1
            stats[strat]['profit'] += trade.net_profit
            if trade.net_profit > 0:
                stats[strat]['wins'] += 1
        
        for strat in stats:
            if stats[strat]['trades'] > 0:
                stats[strat]['win_rate'] = stats[strat]['wins'] / stats[strat]['trades'] * 100
        
        return stats
    
    def _save_state(self):
        """Salva estado para disco"""
        state = {
            'balance': self.balance,
            'equity': self.equity,
            'positions': {
                pid: {
                    'symbol': p.symbol,
                    'direction': p.direction,
                    'volume': p.volume,
                    'entry_price': p.entry_price,
                    'entry_time': p.entry_time.isoformat(),
                    'stop_loss': p.stop_loss,
                    'take_profit': p.take_profit,
                    'strategy': p.strategy,
                    'magic': p.magic
                }
                for pid, p in self.positions.items()
            },
            'trades': [
                {
                    'trade_id': t.trade_id,
                    'symbol': t.symbol,
                    'direction': t.direction,
                    'volume': t.volume,
                    'entry_price': t.entry_price,
                    'exit_price': t.exit_price,
                    'entry_time': t.entry_time.isoformat() if t.entry_time else None,
                    'exit_time': t.exit_time.isoformat() if t.exit_time else None,
                    'net_profit': t.net_profit,
                    'strategy': t.strategy,
                    'exit_reason': t.exit_reason
                }
                for t in self.closed_trades
            ],
            'saved_at': datetime.now().isoformat()
        }
        
        state_file = self.data_dir / 'paper_state.json'
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)
        
        logger.info(f"Estado salvo em {state_file}")
    
    def _load_state(self):
        """Carrega estado do disco"""
        state_file = self.data_dir / 'paper_state.json'
        
        if not state_file.exists():
            logger.info("Nenhum estado anterior encontrado")
            return
        
        try:
            with open(state_file, 'r') as f:
                state = json.load(f)
            
            self.balance = state.get('balance', self.initial_balance)
            self.equity = state.get('equity', self.balance)
            
            # Restaurar posições
            for pid, pdata in state.get('positions', {}).items():
                self.positions[pid] = PaperPosition(
                    position_id=pid,
                    symbol=pdata['symbol'],
                    direction=pdata['direction'],
                    volume=pdata['volume'],
                    entry_price=pdata['entry_price'],
                    entry_time=datetime.fromisoformat(pdata['entry_time']),
                    stop_loss=pdata.get('stop_loss', 0),
                    take_profit=pdata.get('take_profit', 0),
                    strategy=pdata.get('strategy', ''),
                    magic=pdata.get('magic', 0)
                )
            
            # Restaurar trades
            for tdata in state.get('trades', []):
                self.closed_trades.append(PaperTrade(
                    trade_id=tdata['trade_id'],
                    symbol=tdata['symbol'],
                    direction=tdata['direction'],
                    volume=tdata['volume'],
                    entry_price=tdata['entry_price'],
                    exit_price=tdata['exit_price'],
                    entry_time=datetime.fromisoformat(tdata['entry_time']) if tdata.get('entry_time') else None,
                    exit_time=datetime.fromisoformat(tdata['exit_time']) if tdata.get('exit_time') else None,
                    net_profit=tdata['net_profit'],
                    strategy=tdata.get('strategy', ''),
                    exit_reason=tdata.get('exit_reason', '')
                ))
            
            logger.info(f"Estado restaurado: ${self.balance:.2f}, {len(self.positions)} posições, {len(self.closed_trades)} trades")
            
        except Exception as e:
            logger.error(f"Erro ao carregar estado: {e}")
    
    def generate_report(self) -> str:
        """Gera relatório do paper trading"""
        stats = self.get_stats()
        
        report = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    RELATÓRIO DE PAPER TRADING - URION                        ║
╚══════════════════════════════════════════════════════════════════════════════╝

💰 CAPITAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Capital Inicial: ${stats['initial_balance']:,.2f}
Balance Atual: ${stats['balance']:,.2f}
Equity Atual: ${stats['equity']:,.2f}
Retorno Total: {stats['total_return']:+.2f}%

📊 PERFORMANCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total de Trades: {stats['total_trades']}
Trades Vencedores: {stats['winning_trades']} ({stats['win_rate']:.1f}%)
Trades Perdedores: {stats['losing_trades']}

Lucro Total: ${stats['total_profit']:,.2f}
Lucro Médio: ${stats['avg_profit']:,.2f}
Média Ganhos: ${stats['avg_win']:,.2f}
Média Perdas: ${stats['avg_loss']:,.2f}
Profit Factor: {stats['profit_factor']:.2f}

📉 RISCO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Max Drawdown: {stats['max_drawdown']:.2f}%

📈 POSIÇÕES ABERTAS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Posições Abertas: {stats['open_positions']}
P&L Não Realizado: ${stats['unrealized_pnl']:,.2f}

📊 POR ESTRATÉGIA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        for strat, s in stats['by_strategy'].items():
            report += f"  {strat}: {s['trades']} trades, ${s['profit']:+.2f}, WR: {s.get('win_rate', 0):.1f}%\n"
        
        return report


# Instância global
_paper_trading: Optional[PaperTradingEngine] = None


def get_paper_trading(config: Dict[str, Any] = None) -> PaperTradingEngine:
    """Retorna instância singleton do paper trading"""
    global _paper_trading
    if _paper_trading is None:
        _paper_trading = PaperTradingEngine(config)
    return _paper_trading


# Exemplo de uso
if __name__ == "__main__":
    import asyncio
    
    logging.basicConfig(level=logging.INFO)
    
    async def main():
        # Criar engine
        engine = get_paper_trading({'paper_trading': {'initial_balance': 10000}})
        engine.start()
        
        # Simular preços
        engine.update_price('XAUUSD', 2650.00, 2650.30)
        
        # Submeter ordem
        order = await engine.submit_order(
            symbol='XAUUSD',
            direction='buy',
            volume=0.1,
            order_type=OrderType.MARKET,
            stop_loss=2640.00,
            take_profit=2670.00,
            strategy='test_strategy'
        )
        
        # Aguardar processamento
        await asyncio.sleep(1)
        
        # Atualizar preço (simular movimento)
        engine.update_price('XAUUSD', 2655.00, 2655.30)
        
        await asyncio.sleep(1)
        
        # Fechar posição
        for pos_id in list(engine.positions.keys()):
            engine.close_position(pos_id, 'test')
        
        # Relatório
        print(engine.generate_report())
        
        engine.stop()
    
    asyncio.run(main())
