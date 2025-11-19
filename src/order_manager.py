"""
Order Manager
Gerencia posições abertas em tempo real
Ciclo de execução: 1 minuto
"""

import time
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
        
        # Remover posições fechadas
        closed_tickets = set(self.monitored_positions.keys()) - current_tickets
        for ticket in closed_tickets:
            logger.info(f"Posição {ticket} foi fechada")
            del self.monitored_positions[ticket]
        
        # Adicionar novas posições
        for position in current_positions:
            ticket = position['ticket']
            if ticket not in self.monitored_positions:
                self.monitored_positions[ticket] = {
                    'ticket': ticket,
                    'type': position['type'],
                    'volume': position['volume'],
                    'price_open': position['price_open'],
                    'sl': position['sl'],
                    'tp': position['tp'],
                    'profit': position['profit'],
                    'first_seen': datetime.now(timezone.utc),
                    'breakeven_applied': False,
                    'trailing_active': False,
                    'highest_profit': position['profit'],
                    'lowest_profit': position['profit']
                }
                logger.info(
                    f"Nova posição monitorada: {ticket} | "
                    f"Tipo: {position['type']} | Volume: {position['volume']}"
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
    
    def modify_position(self, ticket: int, new_sl: float,
                       new_tp: Optional[float] = None) -> bool:
        """
        Modifica SL/TP de uma posição
        
        Args:
            ticket: Ticket da posição
            new_sl: Novo Stop Loss
            new_tp: Novo Take Profit (opcional)
            
        Returns:
            True se modificado com sucesso
        """
        try:
            result = self.mt5.modify_position(ticket, new_sl, new_tp)
            
            if result:
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
            # Buscar dados da posição antes de fechar (para aprendizagem)
            position_info = self.monitored_positions.get(ticket, {})
            
            # Fechamento total apenas (parcial não implementado)
            result = self.mt5.close_position(ticket)
            
            if result:
                logger.success(f"Posição {ticket} fechada")
                
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
        
        # 1. Verificar break-even
        if not monitored['breakeven_applied']:
            should_move, new_sl = self.should_move_to_breakeven(
                ticket, position
            )
            
            if should_move:
                if self.modify_position(ticket, new_sl):
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
        
        logger.info("Iniciando OrderManager...")
        self.running = True
        
        try:
            while self.running:
                try:
                    self.execute_cycle()
                except Exception as e:
                    logger.error(f"Erro no ciclo: {e}")
                
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
