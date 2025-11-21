"""
Order Manager
Gerencia posições abertas em tempo real
Ciclo de execução: 1 minuto
"""

import time
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional
from loguru import logger

from core.mt5_connector import MT5Connector
from core.config_manager import ConfigManager
from core.risk_manager import RiskManager
from core.market_hours import MarketHoursManager
from analysis.technical_analyzer import TechnicalAnalyzer
from notifications.telegram_bot import TelegramNotifier
from database.strategy_stats import StrategyStatsDB
from ml.strategy_learner import StrategyLearner


class OrderManager:
    """
    Gerenciador de ordens abertas
    Monitora posições e aplica trailing stop, break-even, etc
    """
    
    def __init__(self, config=None, telegram=None):
        """Inicializa Order Manager"""
        
        # Carregar configurações
        if config is None:
            self.config_manager = ConfigManager()
            self.config = self.config_manager.config
        else:
            self.config = config
        
        # Configurações do manager
        self.manager_config = self.config.get('order_manager', {})
        self.enabled = self.manager_config.get('enabled', True)
        self.cycle_interval = self.manager_config.get(
            'cycle_interval_seconds', 60
        )  # 1 minuto
        
        # Inicializar componentes
        self.mt5 = MT5Connector(self.config)
        self.risk_manager = RiskManager(self.config, self.mt5)
        self.market_hours = MarketHoursManager(self.config)
        self.technical_analyzer = TechnicalAnalyzer(self.mt5, self.config)
        self.telegram = telegram if telegram else TelegramNotifier(self.config)
        self.stats_db = StrategyStatsDB()
        
        # Sistema de aprendizagem
        self.learner = StrategyLearner()
        
        # Mapa de magic numbers para estratégias (para configuração customizada)
        self.strategy_map = self._build_strategy_map()
        
        # Estado
        self.running = False
        self.monitored_positions = {}  # ticket: position_data
        self.last_market_close_check = None
        
        # � THREAD SAFETY: Lock para proteger acesso ao estado compartilhado
        self.positions_lock = threading.Lock()
        
        # �🚨 NOVO: Controle de modificações (evitar spam)
        self.last_modification = {}  # ticket: datetime
        self.min_modification_interval = 30  # segundos (não modificar antes disso)
        self.min_sl_change_pips = 2  # Mínimo de 2 pips de mudança
        
        logger.info("OrderManager inicializado")
        logger.info(f"Ciclo: {self.cycle_interval}s")
        logger.info(f"Configuração customizada por estratégia: {len(self.strategy_map)} estratégias")
    
    def _build_strategy_map(self) -> Dict[int, Dict]:
        """
        Constrói mapa de magic numbers para configurações de estratégia
        
        Returns:
            Dict com magic_number: config_da_estrategia
        """
        strategy_map = {}
        
        # Magic numbers base (mesmo cálculo do StrategyExecutor)
        base_magic = 100000
        strategies = self.config.get('strategies', {})
        
        for strategy_name, strategy_config in strategies.items():
            if strategy_name == 'enabled':
                continue
            
            # Calcular magic number (mesmo algoritmo do StrategyExecutor)
            name_hash = sum(ord(c) for c in strategy_name[:5])
            magic_number = base_magic + name_hash
            
            # Extrair configurações de OrderManager da estratégia
            strategy_map[magic_number] = {
                'name': strategy_name,
                'trailing_stop_distance': strategy_config.get('trailing_stop_distance', 15),
                'break_even_trigger': strategy_config.get('break_even_trigger', 20),
                'partial_close_trigger': strategy_config.get('partial_close_trigger', 30)
            }
            
            logger.debug(
                f"Strategy '{strategy_name}' (magic: {magic_number}): "
                f"Trailing={strategy_config.get('trailing_stop_distance', 15)}pips, "
                f"BE={strategy_config.get('break_even_trigger', 20)}pips"
            )
        
        return strategy_map
    
    def get_strategy_config(self, magic_number: int) -> Dict:
        """
        Obtém configuração da estratégia baseado no magic number
        
        Args:
            magic_number: Magic number da posição
            
        Returns:
            Dict com configuração ou valores padrão
        """
        return self.strategy_map.get(magic_number, {
            'name': 'unknown',
            'trailing_stop_distance': 15,
            'break_even_trigger': 20,
            'partial_close_trigger': 30
        })
    
    def get_open_positions(self) -> List[Dict]:
        """
        Obtém todas as posições abertas
        
        Returns:
            Lista de posições
        """
        try:
            positions = self.mt5.get_positions()
            return positions if positions else []
        except Exception as e:
            logger.error(f"Erro ao obter posições: {e}")
            return []
    
    def update_monitored_positions(self):
        """Atualiza lista de posições monitoradas"""
        
        current_positions = self.get_open_positions()
        current_tickets = {pos['ticket'] for pos in current_positions}
        
        # 🔒 THREAD SAFETY: Proteger acesso ao estado compartilhado
        with self.positions_lock:
            # Remover posições fechadas
            closed_tickets = set(self.monitored_positions.keys()) - current_tickets
            
        # 🚨 PROCESSAMENTO FORA DO LOCK (evitar deadlock em chamadas MT5)
        for ticket in closed_tickets:
            logger.info(f"Posição {ticket} foi fechada")
            
            # 🤖 APRENDIZAGEM: Aprender com posições fechadas
            try:
                # 🔒 Obter dados monitorados (dentro de lock)
                with self.positions_lock:
                    monitored = self.monitored_positions.get(ticket)
                
                if not monitored:
                    logger.warning(f"🤖 Ticket {ticket} não encontrado em monitored_positions")
                    # NÃO usar continue - precisa remover do dict mesmo assim
                else:
                    # Buscar dados completos do trade no histórico MT5
                    import MetaTrader5 as mt5
                    from datetime import timedelta
                    
                    logger.debug(f"🤖 Buscando deal para ticket {ticket} no histórico MT5...")
                    
                    # Buscar trade fechado nos últimos 10 minutos (aumentado de 5)
                    deals = mt5.history_deals_get(
                        datetime.now() - timedelta(minutes=10),
                        datetime.now()
                    )
                    
                    if not deals:
                        logger.warning(f"🤖 Nenhum deal encontrado no histórico dos últimos 10min")
                        # NÃO usar continue - tentar fallback
                    else:
                        logger.debug(f"🤖 Encontrados {len(deals)} deals no histórico")
                    
                    deal_found = False
                    if deals:
                        for deal in deals:
                            # Procurar o deal correspondente ao ticket
                            if deal.position_id == ticket:
                                deal_found = True
                                logger.debug(f"🤖 Deal encontrado! Magic: {deal.magic}, Profit: {deal.profit}")
                                
                                # Identificar estratégia pelo magic number
                                magic = deal.magic
                                
                                # Mapear magic → estratégia
                                strategy_map = {
                                    100541: 'trend_following',
                                    100512: 'mean_reversion',
                                    100517: 'breakout',
                                    100540: 'news_trading',
                                    100531: 'scalping',
                                    100525: 'range_trading'
                                }
                                
                                strategy_name = strategy_map.get(magic, 'Unknown')
                                logger.debug(f"🤖 Magic {magic} → Estratégia: {strategy_name}")
                                
                                if strategy_name and strategy_name != 'Unknown':
                                    # Calcular duração do trade
                                    duration = datetime.now(timezone.utc) - monitored['first_seen']
                                    duration_minutes = duration.total_seconds() / 60
                                    
                                    # Preparar dados para aprendizagem
                                    trade_data = {
                                        'profit': deal.profit + monitored.get('profit_realizado', 0.0),
                                        'signal_confidence': monitored.get('confidence', 0.5),
                                        'market_conditions': monitored.get('conditions', ''),
                                        'volume': monitored.get('volume_inicial', deal.volume),
                                        'duration_minutes': duration_minutes
                                    }
                                    
                                    logger.debug(f"🤖 Chamando learner.learn_from_trade({strategy_name}, {trade_data})")
                                    
                                    # Aprender!
                                    self.learner.learn_from_trade(strategy_name, trade_data)
                                    
                                    emoji = "🟢" if trade_data['profit'] > 0 else "🔴"
                                    logger.info(
                                        f"🤖 [{strategy_name}] Aprendeu com trade: "
                                        f"{emoji} ${trade_data['profit']:.2f} "
                                        f"(duração: {duration_minutes:.1f}min)"
                                    )
                                else:
                                    logger.warning(f"🤖 Magic {magic} não mapeado para estratégia conhecida")
                                
                                break
                    
                    if not deal_found:
                        logger.warning(
                            f"🤖 Deal não encontrado no histórico MT5 para ticket {ticket} "
                            f"(verificados {len(deals) if deals else 0} deals). Tentando buscar no database..."
                        )
                        
                        # FALLBACK: Buscar dados do database
                        try:
                            trade_info = self.stats_db.get_trade_by_ticket(ticket)
                            if trade_info:
                                strategy_name = trade_info.get('strategy_name')
                                
                                if strategy_name:
                                    # Calcular duração
                                    duration = datetime.now(timezone.utc) - monitored['first_seen']
                                    duration_minutes = duration.total_seconds() / 60
                                    
                                    # 🚨 BUSCAR PROFIT REAL: tentar pegar do histórico de posições
                                    final_profit = 0.0
                                    try:
                                        # Buscar posição fechada no histórico
                                        from datetime import timedelta
                                        history = mt5.history_orders_get(
                                            datetime.now() - timedelta(minutes=10),
                                            datetime.now(),
                                            position=ticket
                                        )
                                        
                                        if history and len(history) > 0:
                                            # Somar profit de todas as ordens dessa posição
                                            for order in history:
                                                if hasattr(order, 'profit'):
                                                    final_profit += order.profit
                                            
                                            logger.debug(f"🤖 Profit do histórico MT5: ${final_profit:.2f}")
                                        else:
                                            # Fallback: usar último profit conhecido + parciais
                                            final_profit = monitored.get('profit', 0.0) + monitored.get('profit_realizado', 0.0)
                                            logger.debug(f"🤖 Usando profit monitorado: ${final_profit:.2f}")
                                    except Exception as hist_error:
                                        # Se falhar, usar profit monitorado
                                        final_profit = monitored.get('profit', 0.0) + monitored.get('profit_realizado', 0.0)
                                        logger.debug(f"🤖 Erro ao buscar histórico, usando monitorado: ${final_profit:.2f}")
                                    
                                    # Preparar dados
                                    trade_data = {
                                        'profit': final_profit,
                                        'signal_confidence': monitored.get('confidence', 0.5),
                                        'market_conditions': monitored.get('conditions', ''),
                                        'volume': monitored.get('volume_inicial', trade_info.get('volume', 0.05)),
                                        'duration_minutes': duration_minutes
                                    }
                                    
                                    logger.debug(f"🤖 Dados encontrados no database: {strategy_name}, profit: ${final_profit:.2f}")
                                    
                                    # Aprender!
                                    self.learner.learn_from_trade(strategy_name, trade_data)
                                    
                                    emoji = "🟢" if trade_data['profit'] > 0 else "🔴"
                                    logger.info(
                                        f"🤖 [{strategy_name}] Aprendeu com trade (via database): "
                                        f"{emoji} ${trade_data['profit']:.2f} "
                                        f"(duração: {duration_minutes:.1f}min)"
                                    )
                                else:
                                    logger.warning(f"🤖 Strategy_name não encontrado no database para {ticket}")
                            else:
                                logger.warning(f"🤖 Trade {ticket} não encontrado no database")
                        except Exception as db_error:
                            logger.error(f"🤖 Erro ao buscar no database: {db_error}")
            
            except Exception as learn_error:
                logger.error(f"🤖 ERRO na aprendizagem para ticket {ticket}: {learn_error}")
                import traceback
                logger.error(traceback.format_exc())
            
            finally:
                # 🚨 SEMPRE REMOVER DA LISTA (mesmo com erro)
                with self.positions_lock:
                    if ticket in self.monitored_positions:
                        del self.monitored_positions[ticket]
                        logger.debug(f"🤖 Ticket {ticket} removido de monitored_positions")
            
            # Adicionar novas posições
            for position in current_positions:
                ticket = position['ticket']
                if ticket not in self.monitored_positions:
                    # 🤖 Buscar dados do trade no database para aprendizagem
                    confidence = 0.5
                    conditions = ''
                    
                    try:
                        # Buscar no database
                        trade_info = self.stats_db.get_trade_by_ticket(ticket)
                        if trade_info:
                            confidence = trade_info.get('signal_confidence', 0.5)
                            # Normalizar confiança (database salva como %, aprendizagem usa 0-1)
                            if confidence > 1:
                                confidence = confidence / 100.0
                            conditions = trade_info.get('market_conditions', '')
                    except Exception as e:
                        logger.debug(f"Não foi possível buscar dados do trade {ticket}: {e}")
                    
                    self.monitored_positions[ticket] = {
                        'ticket': ticket,
                        'type': position['type'],
                        'volume': position['volume'],
                        'volume_inicial': position['volume'],  # 🚨 NOVO: rastrear volume inicial
                        'price_open': position['price_open'],
                        'sl': position['sl'],
                        'tp': position['tp'],
                        'profit': position['profit'],
                        'profit_realizado': 0.0,  # 🚨 NOVO: lucro já realizado com parciais
                        'first_seen': datetime.now(timezone.utc),
                        'breakeven_applied': False,
                        'trailing_active': False,
                        'highest_profit': position['profit'],
                        'lowest_profit': position['profit'],
                        'confidence': confidence,  # 🤖 Para aprendizagem
                        'conditions': conditions   # 🤖 Para aprendizagem
                    }
                    logger.info(
                        f"Nova posição monitorada: {ticket} | "
                        f"Tipo: {position['type']} | Volume: {position['volume']}"
                    )
                else:
                    # 🚨 ATUALIZAR DADOS DA POSIÇÃO EXISTENTE
                    monitored = self.monitored_positions[ticket]
                    
                    # Atualizar profit atual
                    monitored['profit'] = position['profit']
                    monitored['sl'] = position['sl']
                    monitored['tp'] = position['tp']
                    
                    # 🚨 DETECTAR FECHAMENTO PARCIAL (volume diminuiu)
                    if position['volume'] < monitored['volume']:
                        # Houve fechamento parcial!
                        volume_fechado = monitored['volume'] - position['volume']
                        
                        # Calcular lucro realizado (aproximado)
                        if position['volume'] > 0:
                            profit_per_lot = position['profit'] / position['volume']
                            profit_fechado = profit_per_lot * volume_fechado
                        else:
                            profit_fechado = 0.0
                        
                        monitored['profit_realizado'] = monitored.get('profit_realizado', 0.0) + profit_fechado
                        monitored['volume'] = position['volume']
                        
                        logger.success(
                            f"✅ Fechamento parcial detectado | "
                            f"Ticket: {ticket} | "
                            f"Volume fechado: {volume_fechado} | "
                            f"Lucro realizado: ${profit_fechado:.2f} | "
                            f"Total realizado: ${monitored['profit_realizado']:.2f}"
                        )
                        
                        # Notificar
                        self.telegram.send_message_sync(
                            f"✅ LUCRO REALIZADO\n\n"
                            f"Ticket: {ticket}\n"
                            f"Volume fechado: {volume_fechado} lotes\n"
                            f"Lucro: ${profit_fechado:.2f}\n"
                            f"Total realizado: ${monitored['profit_realizado']:.2f}\n"
                            f"Ainda aberto: {position['volume']} lotes"
                        )
    
    def should_move_to_breakeven(self, ticket: int,
                                  position: Dict) -> tuple[bool, float]:
        """
        Verifica se deve mover SL para breakeven
        
        Args:
            ticket: Ticket da posição
            position: Dados atuais da posição
            
        Returns:
            (should_move, new_sl)
        """
        
        # ✅ VERIFICAR SE BREAK-EVEN ESTÁ HABILITADO GLOBALMENTE
        risk_config = self.config.get('risk', {})
        if not risk_config.get('break_even_enabled', True):
            return False, 0.0  # Break-even desativado globalmente
        
        # 🔒 THREAD SAFETY: Leitura protegida
        with self.positions_lock:
            # Verificar se já foi aplicado
            monitored = self.monitored_positions.get(ticket)
            if not monitored or monitored['breakeven_applied']:
                return False, 0.0
        
        # Obter configuração específica da estratégia
        magic_number = position.get('magic', 0)
        strategy_config = self.get_strategy_config(magic_number)
        
        # Break-even trigger em pips (específico da estratégia)
        be_trigger_pips = strategy_config.get('break_even_trigger', 20)
        
        # Converter para distância de preço
        point = 0.0001  # Para pares forex
        be_trigger_distance = be_trigger_pips * point * 10
        
        # Calcular lucro atual
        entry_price = position['price_open']
        current_price = position['price_current']
        current_sl = position['sl']
        position_type = position['type']
        
        if position_type == 'BUY':
            profit_distance = current_price - entry_price
            # Mover para break-even se em lucro e SL ainda abaixo da entrada
            if profit_distance >= be_trigger_distance and current_sl < entry_price:
                new_sl = entry_price
                return True, new_sl
        else:  # SELL
            profit_distance = entry_price - current_price
            # Mover para break-even se em lucro e SL ainda acima da entrada
            if profit_distance >= be_trigger_distance and \
               (current_sl > entry_price or current_sl == 0):
                new_sl = entry_price
                return True, new_sl
        
        return False, 0.0
    
    def calculate_trailing_stop(self, ticket: int,
                                position: Dict) -> Optional[float]:
        """
        Calcula novo Stop Loss com trailing stop
        
        Args:
            ticket: Ticket da posição
            position: Dados atuais da posição
            
        Returns:
            Novo SL ou None
        """
        
        # ✅ VERIFICAR SE TRAILING STOP ESTÁ HABILITADO GLOBALMENTE
        risk_config = self.config.get('risk', {})
        if not risk_config.get('trailing_stop_enabled', True):
            return None  # Trailing stop desativado globalmente
        
        # 🔒 THREAD SAFETY: Leitura protegida
        with self.positions_lock:
            monitored = self.monitored_positions.get(ticket)
            if not monitored:
                return None
        
        # Obter configuração específica da estratégia
        magic_number = position.get('magic', 0)
        strategy_config = self.get_strategy_config(magic_number)
        
        # Distância de trailing stop em pips (específica da estratégia)
        trailing_pips = strategy_config.get('trailing_stop_distance', 15)
        
        # Converter pips para distância de preço
        point = 0.0001  # Para pares forex
        trailing_distance = trailing_pips * point * 10
        
        # Usar Risk Manager para calcular com distância customizada
        new_sl = self.risk_manager.calculate_trailing_stop(
            position,
            position['price_current'],
            trailing_distance
        )
        
        return new_sl
    
    def should_partial_close(self, ticket: int,
                            position: Dict) -> tuple[bool, float]:
        """
        Verifica se deve fazer fechamento parcial
        
        Args:
            ticket: Ticket da posição
            position: Dados atuais da posição
            
        Returns:
            (should_close, volume_to_close)
        """
        
        # 🔒 THREAD SAFETY: Leitura protegida
        with self.positions_lock:
            monitored = self.monitored_positions.get(ticket)
            if not monitored:
                return False, 0.0
        
        # Configuração de fechamento parcial
        partial_config = self.manager_config.get('partial_close', {})
        enabled = partial_config.get('enabled', False)
        
        if not enabled:
            return False, 0.0
        
        # Obter configuração específica da estratégia
        magic_number = position.get('magic', 0)
        strategy_config = self.get_strategy_config(magic_number)
        
        # Calcular lucro em pips
        price_open = position['price_open']
        price_current = position['price_current']
        position_type = position['type']
        
        if position_type == 'BUY':
            profit_pips = (price_current - price_open) * 10000
        else:
            profit_pips = (price_open - price_current) * 10000
        
        # Verificar se atingiu objetivo de fechamento parcial (específico da estratégia)
        target_pips = strategy_config.get('partial_close_trigger', 50)
        close_percentage = partial_config.get('close_percentage', 0.5)
        
        if profit_pips >= target_pips:
            # Fechar porcentagem da posição
            volume_to_close = position['volume'] * close_percentage
            
            # Arredondar para 0.01 (mínimo MT5)
            volume_to_close = round(volume_to_close, 2)
            
            if volume_to_close >= 0.01:
                return True, volume_to_close
        
        return False, 0.0
    
    def _validate_spread_before_modify(self, symbol: str) -> bool:
        """
        Valida se spread está aceitável antes de modificar posição
        
        Args:
            symbol: Símbolo da posição
            
        Returns:
            True se spread OK, False se muito alto
        """
        try:
            symbol_info = self.mt5.get_symbol_info(symbol)
            if not symbol_info:
                logger.warning(f"Não foi possível obter info para {symbol}")
                return False
            
            # Spread já vem em pips do MT5Connector (após fix)
            spread_pips = symbol_info['spread']
            
            # Obter threshold do config (em pips)
            spread_threshold_pips = self.config.get('trading', {}).get('spread_threshold', 5)
            
            if spread_pips > spread_threshold_pips:
                logger.warning(
                    f"⚠️ Spread muito alto para modificar posição: "
                    f"{spread_pips:.1f} pips (max: {spread_threshold_pips} pips)"
                )
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao validar spread: {e}")
            return False
    
    def should_modify_position(self, ticket: int, new_sl: float, current_sl: float) -> bool:
        """
        Valida se deve realmente modificar (evitar modificações excessivas)
        
        Args:
            ticket: Ticket da posição
            new_sl: Novo stop loss proposto
            current_sl: Stop loss atual
            
        Returns:
            True se deve modificar
        """
        
        # Verificar tempo desde última modificação
        last_mod = self.last_modification.get(ticket)
        if last_mod:
            seconds_since = (datetime.now(timezone.utc) - last_mod).total_seconds()
            if seconds_since < self.min_modification_interval:
                logger.debug(
                    f"Modificação muito recente para {ticket} "
                    f"({seconds_since:.0f}s < {self.min_modification_interval}s)"
                )
                return False
        
        # Verificar se mudança é significativa (mínimo 2 pips)
        sl_change_pips = abs(new_sl - current_sl) * 10000
        
        if sl_change_pips < self.min_sl_change_pips:
            logger.debug(
                f"Mudança de SL muito pequena: {sl_change_pips:.1f} pips "
                f"(mínimo: {self.min_sl_change_pips})"
            )
            return False
        
        return True
    
    def modify_position(self, ticket: int, new_sl: float,
                       new_tp: Optional[float] = None) -> bool:
        """
        Modifica SL/TP de uma posição (com validações de spread e frequência)
        
        Args:
            ticket: Ticket da posição
            new_sl: Novo Stop Loss
            new_tp: Novo Take Profit (opcional)
            
        Returns:
            True se modificado com sucesso
        """
        try:
            # Buscar posição
            position = next(
                (p for p in self.get_open_positions() if p['ticket'] == ticket),
                None
            )
            
            if not position:
                logger.error(f"Posição {ticket} não encontrada")
                return False
            
            # 🚨 VALIDAÇÃO 1: Verificar se deve modificar (frequência + mudança mínima)
            if not self.should_modify_position(ticket, new_sl, position['sl']):
                return False
            
            symbol = position['symbol']
            
            # 🚨 VALIDAÇÃO 2: Verificar spread
            if not self._validate_spread_before_modify(symbol):
                logger.warning(
                    f"⚠️ Modificação adiada (spread alto) | Ticket: {ticket}"
                )
                return False
            
            # Prosseguir com modificação
            result = self.mt5.modify_position(ticket, new_sl, new_tp)
            
            if result:
                # 🚨 REGISTRAR MODIFICAÇÃO
                self.last_modification[ticket] = datetime.now(timezone.utc)
                
                logger.success(
                    f"Posição {ticket} modificada | "
                    f"Novo SL: {new_sl}" +
                    (f" | Novo TP: {new_tp}" if new_tp else "")
                )
                return True
            else:
                logger.error(
                    f"Falha ao modificar posição {ticket}"
                )
                return False
                
        except Exception as e:
            logger.error(f"Erro ao modificar posição {ticket}: {e}")
            return False
    
    def close_position(self, ticket: int,
                      volume: Optional[float] = None) -> bool:
        """
        Fecha posição (total ou parcial)
        
        Args:
            ticket: Ticket da posição
            volume: Volume a fechar (None = total)
            
        Returns:
            True se fechado com sucesso
        """
        try:
            # 🔒 THREAD SAFETY: Leitura protegida
            with self.positions_lock:
                # Buscar dados da posição antes de fechar (para aprendizagem)
                position_info = self.monitored_positions.get(ticket, {})
            
            if volume is None:
                # Fechamento total
                result = self.mt5.close_position(ticket)
            else:
                # 🚨 FECHAMENTO PARCIAL (IMPLEMENTADO)
                position = next(
                    (p for p in self.get_open_positions() if p['ticket'] == ticket),
                    None
                )
                
                if not position:
                    logger.error(f"Posição {ticket} não encontrada para fechamento parcial")
                    return False
                
                # Validar volume
                if volume > position['volume']:
                    logger.error(
                        f"Volume parcial ({volume}) > volume total ({position['volume']})"
                    )
                    return False
                
                if volume < 0.01:
                    logger.error(f"Volume mínimo é 0.01 (solicitado: {volume})")
                    return False
                
                # Fechar parcialmente usando método correto do MT5
                logger.info(
                    f"Fechando parcialmente {ticket} | "
                    f"Volume: {volume}/{position['volume']} | "
                    f"Restante: {position['volume'] - volume}"
                )
                
                # 🚨 CORREÇÃO: Usar close_position_partial em vez de place_order
                result = self.mt5.close_position_partial(
                    ticket=ticket,
                    volume=volume
                )
                
                if result:
                    logger.success(
                        f"✅ Fechamento parcial: {ticket} | "
                        f"Volume fechado: {volume} | "
                        f"Restante: {result['remaining_volume']}"
                    )
                    
                    # 🔒 THREAD SAFETY: Atualização protegida
                    with self.positions_lock:
                        # Atualizar volume monitorado
                        monitored = self.monitored_positions.get(ticket)
                        if monitored:
                            # Calcular lucro realizado (aproximado)
                            profit_per_lot = position['profit'] / position['volume']
                            profit_fechado = profit_per_lot * volume
                            
                            monitored['profit_realizado'] = monitored.get('profit_realizado', 0.0) + profit_fechado
                            monitored['volume'] = position['volume'] - volume
                            
                            # Notificar
                            self.telegram.send_message_sync(
                                f"✅ FECHAMENTO PARCIAL\n\n"
                                f"Ticket: {ticket}\n"
                                f"Volume fechado: {volume} lotes\n"
                                f"Lucro: ${profit_fechado:.2f}\n"
                                f"Total realizado: ${monitored['profit_realizado']:.2f}\n"
                                f"Ainda aberto: {position['volume'] - volume} lotes"
                            )
                    
                    return True
            
            # Fechamento total (se chegou aqui, volume era None)
            if result:
                logger.success(f"Posição {ticket} fechada (total)")
                
                # 🤖 APRENDIZAGEM: Aprender com o resultado do trade
                try:
                    # Buscar dados completos do trade no histórico
                    import MetaTrader5 as mt5
                    from datetime import timedelta
                    
                    # Buscar trade fechado nos últimos 5 minutos
                    deals = mt5.history_deals_get(
                        datetime.now() - timedelta(minutes=5),
                        datetime.now()
                    )
                    
                    if deals:
                        for deal in deals:
                            if deal.order == ticket:
                                # Identificar estratégia pelo magic number
                                magic = deal.magic
                                strategy_name = None
                                
                                # Mapear magic → estratégia
                                # (Este mapeamento deveria vir do executor)
                                strategy_map = {
                                    100541: 'trend_following',
                                    100512: 'mean_reversion',
                                    100517: 'breakout',
                                    100540: 'news_trading',
                                    100531: 'scalping',
                                    100525: 'range_trading'
                                }
                                
                                strategy_name = strategy_map.get(magic, 'Unknown')
                                
                                if strategy_name and strategy_name != 'Unknown':
                                    # Preparar dados para aprendizagem
                                    trade_data = {
                                        'profit': deal.profit,
                                        'signal_confidence': position_info.get('confidence', 0.5),
                                        'market_conditions': position_info.get('conditions', ''),
                                        'volume': deal.volume,
                                        'duration_minutes': position_info.get('duration_minutes', 0)
                                    }
                                    
                                    # Aprender!
                                    self.learner.learn_from_trade(strategy_name, trade_data)
                                    
                                    emoji = "🟢" if deal.profit > 0 else "🔴"
                                    logger.info(
                                        f"🤖 [{strategy_name}] Aprendeu com trade: "
                                        f"{emoji} ${deal.profit:.2f}"
                                    )
                                
                                break
                
                except Exception as learn_error:
                    logger.debug(f"Erro na aprendizagem (não crítico): {learn_error}")
                
                return True
            else:
                logger.error(f"Falha ao fechar posição {ticket}")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao fechar posição {ticket}: {e}")
            return False
    
    def manage_position(self, position: Dict):
        """
        Gerencia uma posição individual
        
        Args:
            position: Dados da posição
        """
        
        ticket = position['ticket']
        
        # 🔒 THREAD SAFETY: Leitura e atualização protegidas
        with self.positions_lock:
            monitored = self.monitored_positions.get(ticket)
            
            if not monitored:
                return
            
            # Obter configuração da estratégia para logging
            magic_number = position.get('magic', 0)
            strategy_config = self.get_strategy_config(magic_number)
            strategy_name = strategy_config.get('name', 'Unknown')
            
            # Atualizar lucro máximo/mínimo
            current_profit = position['profit']
            monitored['highest_profit'] = max(
                monitored['highest_profit'], current_profit
            )
            monitored['lowest_profit'] = min(
                monitored['lowest_profit'], current_profit
            )
            
            # Guardar flags para uso fora do lock
            breakeven_applied = monitored['breakeven_applied']
        
        # 1. Verificar break-even
        if not breakeven_applied:
            should_move, new_sl = self.should_move_to_breakeven(
                ticket, position
            )
            
            if should_move:
                if self.modify_position(ticket, new_sl):
                    # 🔒 THREAD SAFETY: Atualizar estado protegido
                    with self.positions_lock:
                        monitored = self.monitored_positions.get(ticket)
                        if monitored:
                            monitored['breakeven_applied'] = True
                            monitored['sl'] = new_sl
                    
                    logger.info(
                        f"[{strategy_name}] Break-even aplicado | "
                        f"Ticket: {ticket} | Trigger: {strategy_config.get('break_even_trigger')}pips"
                    )
                    
                    # Notificar
                    self.telegram.send_message_sync(
                        f"🔒 Break-even aplicado [{strategy_name}]\n"
                        f"Ticket: {ticket}\n"
                        f"Novo SL: {new_sl}"
                    )
                return  # Aguardar próximo ciclo para trailing
        
        # 2. Verificar trailing stop
        new_sl = self.calculate_trailing_stop(ticket, position)
        
        if new_sl and new_sl != position['sl']:
            # Verificar se novo SL é melhor que o atual
            position_type = position['type']
            current_sl = position['sl']
            
            should_update = False
            if position_type == 'BUY' and new_sl > current_sl:
                should_update = True
            elif position_type == 'SELL' and new_sl < current_sl:
                should_update = True
            
            if should_update:
                if self.modify_position(ticket, new_sl):
                    monitored['sl'] = new_sl
                    monitored['trailing_active'] = True
                    logger.info(
                        f"[{strategy_name}] Trailing stop atualizado | "
                        f"Ticket: {ticket} | Distância: {strategy_config.get('trailing_stop_distance')}pips | "
                        f"Novo SL: {new_sl:.5f}"
                    )
        
        # 3. Verificar fechamento parcial
        should_close, volume = self.should_partial_close(ticket, position)
        
        if should_close:
            if self.close_position(ticket, volume):
                logger.info(
                    f"Fechamento parcial executado: {ticket} "
                    f"({volume} lotes)"
                )
                
                # Notificar
                self.telegram.send_message_sync(
                    f"📊 Fechamento Parcial\n"
                    f"Ticket: {ticket}\n"
                    f"Volume: {volume} lotes\n"
                    f"Lucro: ${position['profit']:.2f}"
                )
                
                # Atualizar volume monitorado
                monitored['volume'] -= volume
    
    def execute_cycle(self):
        """Executa um ciclo de monitoramento"""
        
        # Verificar se está habilitado
        if not self.enabled:
            return
        
        # Verificar conexão MT5
        if not self.mt5.is_connected():
            logger.warning("MT5 desconectado, tentando reconectar...")
            if not self.mt5.connect():
                logger.error("Falha ao reconectar MT5")
                return
        
        # VERIFICAR HORÁRIO DE FECHAMENTO DO MERCADO
        market_status = self.market_hours.get_market_status()
        
        if market_status['should_close_positions']:
            logger.warning("⚠️  FECHAMENTO DO MERCADO SE APROXIMA!")
            logger.warning("Fechando TODAS as posições abertas...")
            
            # Fechar todas as posições
            current_positions = self.get_open_positions()
            for position in current_positions:
                ticket = position['ticket']
                logger.warning(f"Fechando posição {ticket} (mercado fechando)")
                self.close_position(ticket)
            
            # Notificar
            self.telegram.send_message_sync(
                f"⚠️ FECHAMENTO AUTOMÁTICO\n\n"
                f"Mercado fechando em breve!\n"
                f"Todas as {len(current_positions)} posições foram fechadas.\n\n"
                f"Próxima abertura: {market_status['next_event']['datetime'].strftime('%d/%m %H:%M')}"
            )
            
            # Salvar timestamp para não repetir
            self.last_market_close_check = datetime.now()
            return
        
        # Atualizar lista de posições
        self.update_monitored_positions()
        
        if not self.monitored_positions:
            return  # Nenhuma posição para monitorar
        
        # Obter posições atuais
        current_positions = self.get_open_positions()
        
        # Gerenciar cada posição
        for position in current_positions:
            try:
                self.manage_position(position)
            except Exception as e:
                logger.error(
                    f"Erro ao gerenciar posição {position['ticket']}: {e}"
                )
    
    def start(self):
        """Inicia loop de monitoramento"""
        
        if self.running:
            logger.warning("OrderManager já está executando")
            return
        
        import sys
        import threading
        thread_name = threading.current_thread().name
        
        # Log explícito com flush forçado
        logger.info(f"🚀 OrderManager INICIANDO no thread: {thread_name}")
        sys.stdout.flush()
        
        self.running = True
        
        try:
            cycle_count = 0
            while self.running:
                try:
                    cycle_count += 1
                    logger.info(f"🔄 OrderManager - Ciclo #{cycle_count} iniciado")
                    sys.stdout.flush()
                    
                    self.execute_cycle()
                    
                    logger.info(f"✅ OrderManager - Ciclo #{cycle_count} concluído")
                    sys.stdout.flush()
                except Exception as e:
                    logger.error(f"❌ Erro no ciclo #{cycle_count}: {e}")
                    sys.stdout.flush()
                
                # Aguardar próximo ciclo
                time.sleep(self.cycle_interval)
                
        except KeyboardInterrupt:
            logger.info("Interrupção pelo usuário")
        finally:
            self.stop()
    
    def stop(self):
        """Para execução"""
        logger.info("Parando OrderManager...")
        self.running = False
        
        logger.info("OrderManager parado")


if __name__ == "__main__":
    # Executar Order Manager
    manager = OrderManager()
    manager.start()
