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
from analysis.technical_analyzer import TechnicalAnalyzer
from notifications.telegram_bot import TelegramNotifier


class OrderManager:
    """
    Gerenciador de ordens abertas
    Monitora posições e aplica trailing stop, break-even, etc
    """
    
    def __init__(self):
        """Inicializa Order Manager"""
        
        # Carregar configurações
        self.config_manager = ConfigManager()
        self.config = self.config_manager.config
        
        # Configurações do manager
        self.manager_config = self.config.get('order_manager', {})
        self.enabled = self.manager_config.get('enabled', True)
        self.cycle_interval = self.manager_config.get(
            'cycle_interval_seconds', 60
        )  # 1 minuto
        
        # Inicializar componentes
        self.mt5 = MT5Connector(self.config)
        self.risk_manager = RiskManager(self.config, self.mt5)
        self.technical_analyzer = TechnicalAnalyzer(self.mt5, self.config)
        self.telegram = TelegramNotifier(self.config)
        
        # Estado
        self.running = False
        self.monitored_positions = {}  # ticket: position_data
        
        logger.info("OrderManager inicializado")
        logger.info(f"Ciclo: {self.cycle_interval}s")
    
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
        
        # Usar Risk Manager para decidir
        should_move = self.risk_manager.should_move_to_breakeven(
            position,
            position['price_current']
        )
        
        if should_move:
            # Novo SL = preço de abertura (breakeven)
            new_sl = position['price_open']
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
        
        # Usar Risk Manager para calcular
        new_sl = self.risk_manager.calculate_trailing_stop(
            position,
            position['price_current']
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
        
        # Calcular lucro em pips
        price_open = position['price_open']
        price_current = position['price_current']
        position_type = position['type']
        
        if position_type == 'BUY':
            profit_pips = (price_current - price_open) * 10000
        else:
            profit_pips = (price_open - price_current) * 10000
        
        # Verificar se atingiu objetivo de fechamento parcial
        target_pips = partial_config.get('target_pips', 50)
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
            # Fechamento total apenas (parcial não implementado)
            result = self.mt5.close_position(ticket)
            
            if result:
                logger.success(f"Posição {ticket} fechada")
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
                        f"Break-even aplicado na posição {ticket}"
                    )
                    
                    # Notificar
                    self.telegram.send_message_sync(
                        f"🔒 Break-even aplicado\n"
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
                        f"Trailing stop atualizado para posição {ticket}: "
                        f"{new_sl}"
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
