# -*- coding: utf-8 -*-
"""
Execution Algorithms
====================
Algoritmos de execucao avancados para minimizar slippage e impacto de mercado.

Algoritmos implementados:
- TWAP (Time Weighted Average Price)
- VWAP (Volume Weighted Average Price)
- Iceberg Orders (ordens ocultas)
- Smart Order Router
- Adaptive Execution
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from loguru import logger
import threading
import time
import asyncio

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None


class ExecutionAlgorithm(Enum):
    """Tipos de algoritmos de execucao"""
    MARKET = "market"       # Ordem de mercado simples
    TWAP = "twap"          # Time Weighted Average Price
    VWAP = "vwap"          # Volume Weighted Average Price
    ICEBERG = "iceberg"    # Ordens ocultas
    ADAPTIVE = "adaptive"  # Adaptativo ao mercado
    SNIPER = "sniper"      # Espera momento otimo


class OrderStatus(Enum):
    """Status da ordem"""
    PENDING = "pending"
    EXECUTING = "executing"
    PARTIAL_FILL = "partial_fill"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class ExecutionOrder:
    """Ordem de execucao"""
    id: str
    symbol: str
    side: str  # 'buy' ou 'sell'
    total_volume: float
    algorithm: ExecutionAlgorithm
    
    # Parametros do algoritmo
    params: Dict = field(default_factory=dict)
    
    # Estado
    status: OrderStatus = OrderStatus.PENDING
    filled_volume: float = 0.0
    average_price: float = 0.0
    slices: List[Dict] = field(default_factory=list)
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Metricas
    expected_price: float = 0.0
    slippage: float = 0.0


@dataclass
class ExecutionSlice:
    """Fatia de uma ordem grande"""
    volume: float
    scheduled_time: datetime
    executed: bool = False
    execution_price: float = 0.0
    ticket: int = 0


class ExecutionAlgorithmManager:
    """
    Gerenciador de Algoritmos de Execucao
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.exec_config = config.get('execution', {})
        
        # Configuracoes
        self.default_algorithm = ExecutionAlgorithm(
            self.exec_config.get('default_algorithm', 'market')
        )
        self.max_slippage_pips = self.exec_config.get('max_slippage', 5)
        self.min_slice_volume = self.exec_config.get('min_slice_volume', 0.01)
        
        # Ordens ativas
        self._active_orders: Dict[str, ExecutionOrder] = {}
        self._order_lock = threading.Lock()
        
        # Thread de execucao
        self._running = False
        self._executor_thread = None
        
        # Callbacks
        self._on_fill_callbacks: List[Callable] = []
        
        logger.info("ExecutionAlgorithmManager inicializado")
    
    def start(self):
        """Inicia o executor"""
        if self._running:
            return
        
        self._running = True
        self._executor_thread = threading.Thread(target=self._executor_loop, daemon=True)
        self._executor_thread.start()
        logger.info("Execution Algorithm Manager iniciado")
    
    def stop(self):
        """Para o executor"""
        self._running = False
        if self._executor_thread:
            self._executor_thread.join(timeout=5)
        logger.info("Execution Algorithm Manager parado")
    
    def register_on_fill(self, callback: Callable):
        """Registra callback para quando ordem e preenchida"""
        self._on_fill_callbacks.append(callback)
    
    def submit_order(self, symbol: str, side: str, volume: float,
                    algorithm: ExecutionAlgorithm = None,
                    params: Dict = None) -> str:
        """
        Submete uma ordem para execucao
        Retorna ID da ordem
        """
        algorithm = algorithm or self.default_algorithm
        params = params or {}
        
        # Gerar ID
        order_id = f"{symbol}_{side}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        
        # Obter preco atual para referencia
        tick = mt5.symbol_info_tick(symbol) if mt5 else None
        expected_price = tick.ask if side == 'buy' else tick.bid if tick else 0
        
        order = ExecutionOrder(
            id=order_id,
            symbol=symbol,
            side=side,
            total_volume=volume,
            algorithm=algorithm,
            params=params,
            expected_price=expected_price
        )
        
        # Preparar slices baseado no algoritmo
        if algorithm == ExecutionAlgorithm.TWAP:
            order.slices = self._prepare_twap_slices(order)
        elif algorithm == ExecutionAlgorithm.VWAP:
            order.slices = self._prepare_vwap_slices(order)
        elif algorithm == ExecutionAlgorithm.ICEBERG:
            order.slices = self._prepare_iceberg_slices(order)
        else:
            # Market order - uma unica slice
            order.slices = [{'volume': volume, 'scheduled_time': datetime.now()}]
        
        with self._order_lock:
            self._active_orders[order_id] = order
        
        logger.info(f"Ordem submetida: {order_id}, Algo: {algorithm.value}, Vol: {volume}")
        
        return order_id
    
    def _prepare_twap_slices(self, order: ExecutionOrder) -> List[Dict]:
        """
        Prepara slices para TWAP
        Divide a ordem igualmente ao longo do tempo
        """
        duration_minutes = order.params.get('duration_minutes', 60)
        num_slices = order.params.get('num_slices', 10)
        
        slice_volume = order.total_volume / num_slices
        slice_volume = max(slice_volume, self.min_slice_volume)
        
        # Recalcular numero de slices se volume minimo foi aplicado
        actual_slices = int(order.total_volume / slice_volume)
        remainder = order.total_volume - (actual_slices * slice_volume)
        
        interval = timedelta(minutes=duration_minutes / actual_slices)
        slices = []
        
        current_time = datetime.now()
        for i in range(actual_slices):
            vol = slice_volume
            if i == actual_slices - 1:
                vol += remainder  # Adicionar remainder na ultima slice
            
            slices.append({
                'volume': round(vol, 2),
                'scheduled_time': current_time + (interval * i),
                'executed': False
            })
        
        return slices
    
    def _prepare_vwap_slices(self, order: ExecutionOrder) -> List[Dict]:
        """
        Prepara slices para VWAP
        Distribui baseado no perfil de volume historico
        """
        duration_minutes = order.params.get('duration_minutes', 60)
        num_slices = order.params.get('num_slices', 10)
        
        # Obter perfil de volume (simplificado - em producao usaria dados reais)
        # Simula um perfil U-shape tipico (mais volume no inicio e fim)
        volume_profile = self._get_volume_profile(order.symbol, num_slices)
        
        # Normalizar perfil
        total_weight = sum(volume_profile)
        normalized = [v / total_weight for v in volume_profile]
        
        interval = timedelta(minutes=duration_minutes / num_slices)
        slices = []
        
        current_time = datetime.now()
        for i, weight in enumerate(normalized):
            vol = round(order.total_volume * weight, 2)
            vol = max(vol, self.min_slice_volume)
            
            slices.append({
                'volume': vol,
                'scheduled_time': current_time + (interval * i),
                'executed': False
            })
        
        return slices
    
    def _prepare_iceberg_slices(self, order: ExecutionOrder) -> List[Dict]:
        """
        Prepara slices para Iceberg
        Mostra apenas uma pequena parte da ordem de cada vez
        """
        visible_volume = order.params.get('visible_volume', order.total_volume * 0.1)
        visible_volume = max(visible_volume, self.min_slice_volume)
        
        num_slices = int(np.ceil(order.total_volume / visible_volume))
        remainder = order.total_volume - (num_slices - 1) * visible_volume
        
        slices = []
        for i in range(num_slices):
            vol = visible_volume if i < num_slices - 1 else remainder
            
            slices.append({
                'volume': round(vol, 2),
                'scheduled_time': datetime.now(),  # Executa quando a anterior completar
                'executed': False
            })
        
        return slices
    
    def _get_volume_profile(self, symbol: str, num_buckets: int) -> List[float]:
        """Obtem perfil de volume historico (simplificado)"""
        # Em producao, buscaria dados reais de volume por periodo
        # Aqui usamos um perfil U-shape tipico
        profile = []
        for i in range(num_buckets):
            # U-shape: mais alto nas pontas, mais baixo no meio
            position = abs(i - num_buckets / 2) / (num_buckets / 2)
            weight = 0.5 + 0.5 * position
            profile.append(weight)
        
        return profile
    
    def _executor_loop(self):
        """Loop principal de execucao"""
        while self._running:
            try:
                with self._order_lock:
                    orders = list(self._active_orders.values())
                
                for order in orders:
                    if order.status in [OrderStatus.PENDING, OrderStatus.EXECUTING, OrderStatus.PARTIAL_FILL]:
                        self._process_order(order)
                
                time.sleep(1)  # Verificar a cada segundo
                
            except Exception as e:
                logger.error(f"Erro no executor: {e}")
                time.sleep(5)
    
    def _process_order(self, order: ExecutionOrder):
        """Processa uma ordem"""
        if order.status == OrderStatus.PENDING:
            order.status = OrderStatus.EXECUTING
            order.started_at = datetime.now()
        
        now = datetime.now()
        
        for slice_data in order.slices:
            if slice_data.get('executed', False):
                continue
            
            # Verificar se e hora de executar
            scheduled = slice_data.get('scheduled_time', now)
            if now >= scheduled:
                success = self._execute_slice(order, slice_data)
                
                if success:
                    slice_data['executed'] = True
                    order.filled_volume += slice_data['volume']
                    
                    # Atualizar preco medio
                    if order.filled_volume > 0:
                        exec_price = slice_data.get('execution_price', order.expected_price)
                        old_value = order.average_price * (order.filled_volume - slice_data['volume'])
                        new_value = exec_price * slice_data['volume']
                        order.average_price = (old_value + new_value) / order.filled_volume
                    
                    # Verificar se completou
                    if order.filled_volume >= order.total_volume * 0.99:  # 99% threshold
                        order.status = OrderStatus.FILLED
                        order.completed_at = datetime.now()
                        order.slippage = abs(order.average_price - order.expected_price)
                        
                        logger.info(f"Ordem completada: {order.id}, Preco medio: {order.average_price:.5f}, Slippage: {order.slippage:.5f}")
                        
                        # Notificar callbacks
                        for callback in self._on_fill_callbacks:
                            try:
                                callback(order)
                            except Exception as e:
                                logger.error(f"Erro no callback: {e}")
                    else:
                        order.status = OrderStatus.PARTIAL_FILL
                
                # Para Iceberg, nao executa proxima slice ate esta completar
                if order.algorithm == ExecutionAlgorithm.ICEBERG:
                    break
    
    def _execute_slice(self, order: ExecutionOrder, slice_data: Dict) -> bool:
        """Executa uma slice da ordem"""
        if not mt5:
            logger.warning("MT5 nao disponivel")
            slice_data['execution_price'] = order.expected_price
            return True
        
        symbol = order.symbol
        volume = slice_data['volume']
        
        # Verificar spread antes de executar
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            logger.error(f"Nao foi possivel obter tick para {symbol}")
            return False
        
        spread_pips = (tick.ask - tick.bid) / mt5.symbol_info(symbol).point
        
        # Cancelar se spread muito alto
        if spread_pips > self.max_slippage_pips * 2:
            logger.warning(f"Spread muito alto ({spread_pips:.1f} pips), adiando execucao")
            return False
        
        # Preparar request
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return False
        
        price = tick.ask if order.side == 'buy' else tick.bid
        order_type = mt5.ORDER_TYPE_BUY if order.side == 'buy' else mt5.ORDER_TYPE_SELL
        
        request = {
            'action': mt5.TRADE_ACTION_DEAL,
            'symbol': symbol,
            'volume': volume,
            'type': order_type,
            'price': price,
            'deviation': int(self.max_slippage_pips),
            'magic': 123456,
            'comment': f'algo_{order.algorithm.value}',
            'type_time': mt5.ORDER_TIME_GTC,
            'type_filling': mt5.ORDER_FILLING_IOC,
        }
        
        # Executar
        result = mt5.order_send(request)
        
        if result is None:
            logger.error(f"Erro ao enviar ordem: {mt5.last_error()}")
            return False
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Ordem rejeitada: {result.comment}")
            return False
        
        slice_data['execution_price'] = result.price
        slice_data['ticket'] = result.order
        
        logger.debug(f"Slice executada: {volume} @ {result.price}")
        
        return True
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancela uma ordem"""
        with self._order_lock:
            if order_id not in self._active_orders:
                return False
            
            order = self._active_orders[order_id]
            order.status = OrderStatus.CANCELLED
            
            logger.info(f"Ordem cancelada: {order_id}, Volume executado: {order.filled_volume}")
            
            return True
    
    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """Retorna status de uma ordem"""
        with self._order_lock:
            if order_id not in self._active_orders:
                return None
            
            order = self._active_orders[order_id]
            
            return {
                'id': order.id,
                'symbol': order.symbol,
                'side': order.side,
                'algorithm': order.algorithm.value,
                'status': order.status.value,
                'total_volume': order.total_volume,
                'filled_volume': order.filled_volume,
                'fill_percentage': (order.filled_volume / order.total_volume) * 100,
                'average_price': order.average_price,
                'expected_price': order.expected_price,
                'slippage': order.slippage,
                'remaining_slices': len([s for s in order.slices if not s.get('executed', False)])
            }
    
    def get_active_orders(self) -> List[Dict]:
        """Retorna todas as ordens ativas"""
        with self._order_lock:
            return [
                self.get_order_status(order_id)
                for order_id in self._active_orders
                if self._active_orders[order_id].status in [
                    OrderStatus.PENDING, OrderStatus.EXECUTING, OrderStatus.PARTIAL_FILL
                ]
            ]


class SmartOrderRouter:
    """
    Smart Order Router
    Decide o melhor algoritmo baseado nas condicoes de mercado
    """
    
    def __init__(self, execution_manager: ExecutionAlgorithmManager, config: Dict):
        self.execution_manager = execution_manager
        self.config = config
        
        # Thresholds
        self.large_order_threshold = config.get('large_order_threshold', 1.0)  # lotes
        self.high_spread_threshold = config.get('high_spread_pips', 5)
        self.high_volatility_threshold = config.get('high_volatility_atr', 50)
        
        logger.info("SmartOrderRouter inicializado")
    
    def route_order(self, symbol: str, side: str, volume: float,
                   urgency: str = 'normal') -> str:
        """
        Roteia ordem para o melhor algoritmo
        """
        algorithm = self._select_algorithm(symbol, volume, urgency)
        params = self._get_algorithm_params(algorithm, volume, urgency)
        
        order_id = self.execution_manager.submit_order(
            symbol=symbol,
            side=side,
            volume=volume,
            algorithm=algorithm,
            params=params
        )
        
        logger.info(f"Ordem roteada: {symbol} {side} {volume} via {algorithm.value}")
        
        return order_id
    
    def _select_algorithm(self, symbol: str, volume: float, urgency: str) -> ExecutionAlgorithm:
        """Seleciona o melhor algoritmo"""
        # Se urgencia alta, usa market order
        if urgency == 'high':
            return ExecutionAlgorithm.MARKET
        
        # Se volume grande, usa TWAP ou VWAP
        if volume >= self.large_order_threshold:
            # VWAP em horarios de alto volume
            hour = datetime.now().hour
            if 8 <= hour <= 12 or 14 <= hour <= 18:  # Horarios de alto volume
                return ExecutionAlgorithm.VWAP
            else:
                return ExecutionAlgorithm.TWAP
        
        # Verificar spread
        if mt5:
            tick = mt5.symbol_info_tick(symbol)
            if tick:
                symbol_info = mt5.symbol_info(symbol)
                if symbol_info:
                    spread_pips = (tick.ask - tick.bid) / symbol_info.point
                    
                    if spread_pips > self.high_spread_threshold:
                        # Spread alto - usar TWAP para minimizar impacto
                        return ExecutionAlgorithm.TWAP
        
        # Ordem pequena em condicoes normais - market order
        return ExecutionAlgorithm.MARKET
    
    def _get_algorithm_params(self, algorithm: ExecutionAlgorithm, 
                             volume: float, urgency: str) -> Dict:
        """Retorna parametros para o algoritmo"""
        if algorithm == ExecutionAlgorithm.TWAP:
            duration = 30 if urgency == 'normal' else 10
            return {
                'duration_minutes': duration,
                'num_slices': min(10, int(volume / 0.1))
            }
        
        elif algorithm == ExecutionAlgorithm.VWAP:
            return {
                'duration_minutes': 60 if urgency == 'normal' else 20,
                'num_slices': min(12, int(volume / 0.1))
            }
        
        elif algorithm == ExecutionAlgorithm.ICEBERG:
            return {
                'visible_volume': min(0.1, volume * 0.2)
            }
        
        return {}


# Singletons
_execution_manager = None
_smart_router = None

def get_execution_manager(config: Dict = None) -> ExecutionAlgorithmManager:
    """Retorna instancia singleton"""
    global _execution_manager
    if _execution_manager is None:
        _execution_manager = ExecutionAlgorithmManager(config or {})
    return _execution_manager

def get_smart_router(config: Dict = None) -> SmartOrderRouter:
    """Retorna instancia singleton"""
    global _smart_router
    if _smart_router is None:
        exec_mgr = get_execution_manager(config)
        _smart_router = SmartOrderRouter(exec_mgr, config or {})
    return _smart_router
