"""
Order Generator
Módulo independente para análise e geração de ordens
Ciclo de execução: 5 minutos
"""

import time
from datetime import datetime, timezone
from typing import Dict, Optional
from loguru import logger

from core.mt5_connector import MT5Connector
from core.config_manager import ConfigManager
from core.risk_manager import RiskManager
from technical.technical_analyzer import TechnicalAnalyzer
from news.news_analyzer import NewsAnalyzer
from strategies.strategy_manager import StrategyManager
from notifications.telegram_notifier import TelegramNotifier


class OrderGenerator:
    """
    Gerador de ordens de trading
    Executa a cada 5 minutos e decide se deve abrir posição
    """
    
    def __init__(self):
        """Inicializa Order Generator"""
        
        # Carregar configurações
        self.config_manager = ConfigManager()
        self.config = self.config_manager.config
        
        # Configurações do generator
        self.generator_config = self.config.get('order_generator', {})
        self.enabled = self.generator_config.get('enabled', True)
        self.cycle_interval = self.generator_config.get(
            'cycle_interval_seconds', 300
        )  # 5 minutos
        
        # Horário de trading (UTC)
        self.trading_hours = self.generator_config.get('trading_hours', {})
        self.start_hour = self.trading_hours.get('start_hour', 18)
        self.start_minute = self.trading_hours.get('start_minute', 30)
        self.end_hour = self.trading_hours.get('end_hour', 16)
        self.end_minute = self.trading_hours.get('end_minute', 30)
        
        # Inicializar componentes
        self.mt5 = MT5Connector()
        self.risk_manager = RiskManager(self.config)
        self.technical_analyzer = TechnicalAnalyzer(self.config)
        self.news_analyzer = NewsAnalyzer(self.config)
        self.strategy_manager = StrategyManager(self.config)
        self.telegram = TelegramNotifier(self.config)
        
        # Estado
        self.running = False
        self.last_execution = None
        
        logger.info("OrderGenerator inicializado")
        logger.info(
            f"Ciclo: {self.cycle_interval}s | "
            f"Horário: {self.start_hour:02d}:{self.start_minute:02d} - "
            f"{self.end_hour:02d}:{self.end_minute:02d} UTC"
        )
    
    def is_trading_hours(self) -> bool:
        """
        Verifica se está dentro do horário de trading
        
        Returns:
            True se pode operar
        """
        now = datetime.now(timezone.utc)
        current_time = now.hour * 60 + now.minute
        
        # Converter horários para minutos
        start_time = self.start_hour * 60 + self.start_minute
        end_time = self.end_hour * 60 + self.end_minute
        
        # Horário cruza meia-noite (ex: 18:30 até 16:30 do dia seguinte)
        if start_time > end_time:
            return current_time >= start_time or current_time <= end_time
        else:
            return start_time <= current_time <= end_time
    
    def should_skip_cycle(self) -> tuple[bool, str]:
        """
        Verifica se deve pular este ciclo
        
        Returns:
            (should_skip, reason)
        """
        
        # Verificar se está habilitado
        if not self.enabled:
            return True, "OrderGenerator desabilitado"
        
        # Verificar horário de trading
        if not self.is_trading_hours():
            return True, "Fora do horário de trading"
        
        # Verificar conexão MT5
        if not self.mt5.is_connected():
            logger.warning("MT5 desconectado, tentando reconectar...")
            if not self.mt5.connect():
                return True, "MT5 desconectado"
        
        # Verificar se há janela de bloqueio de notícias
        if self.news_analyzer.is_news_blocking_window():
            return True, "Janela de bloqueio de notícias ativa"
        
        return False, ""
    
    def gather_analysis_data(self) -> Optional[Dict]:
        """
        Coleta dados de análise técnica e notícias
        
        Returns:
            Dicionário com análises ou None se falhar
        """
        try:
            # Análise técnica multi-timeframe
            technical_analysis = self.technical_analyzer.analyze_multi_timeframe()
            
            if not technical_analysis:
                logger.warning("Falha ao obter análise técnica")
                return None
            
            # Análise de notícias
            news_analysis = self.news_analyzer.get_news_signal()
            
            return {
                'technical': technical_analysis,
                'news': news_analysis,
                'timestamp': datetime.now(timezone.utc)
            }
            
        except Exception as e:
            logger.error(f"Erro ao coletar análises: {e}")
            return None
    
    def execute_strategies(self, analysis_data: Dict) -> Optional[Dict]:
        """
        Executa estratégias e retorna sinal de consenso
        
        Args:
            analysis_data: Dados de análise (técnica + notícias)
            
        Returns:
            Sinal de trading ou None
        """
        try:
            technical = analysis_data.get('technical')
            news = analysis_data.get('news')
            
            # Buscar consenso entre estratégias
            signal = self.strategy_manager.get_consensus_signal(
                technical, news
            )
            
            if signal:
                logger.info(
                    f"Sinal gerado: {signal['action']} "
                    f"(confiança: {signal['confidence']:.2%}) - "
                    f"{signal['strategy']}"
                )
            
            return signal
            
        except Exception as e:
            logger.error(f"Erro ao executar estratégias: {e}")
            return None
    
    def validate_with_risk_manager(self, signal: Dict) -> Optional[Dict]:
        """
        Valida sinal com Risk Manager
        
        Args:
            signal: Sinal de trading
            
        Returns:
            Parâmetros da ordem ou None se rejeitado
        """
        try:
            action = signal.get('action')
            
            # Verificar se pode abrir posição
            if not self.risk_manager.can_open_position(action):
                logger.info(
                    f"Risk Manager rejeitou abertura de posição {action}"
                )
                return None
            
            # Calcular tamanho da posição
            volume = self.risk_manager.calculate_position_size()
            
            if volume <= 0:
                logger.warning("Volume calculado inválido")
                return None
            
            # Calcular Stop Loss e Take Profit
            sl = self.risk_manager.calculate_stop_loss(action)
            tp = self.risk_manager.calculate_take_profit(action)
            
            if sl is None or tp is None:
                logger.warning("Falha ao calcular SL/TP")
                return None
            
            return {
                'action': action,
                'volume': volume,
                'stop_loss': sl,
                'take_profit': tp,
                'confidence': signal.get('confidence', 0),
                'strategy': signal.get('strategy', 'Unknown'),
                'reason': signal.get('reason', ''),
                'details': signal.get('details', {})
            }
            
        except Exception as e:
            logger.error(f"Erro na validação com Risk Manager: {e}")
            return None
    
    def place_order(self, order_params: Dict) -> bool:
        """
        Executa ordem no MT5
        
        Args:
            order_params: Parâmetros da ordem
            
        Returns:
            True se ordem executada com sucesso
        """
        try:
            action = order_params['action']
            volume = order_params['volume']
            sl = order_params['stop_loss']
            tp = order_params['take_profit']
            
            # Comentário com informações da estratégia
            comment = (
                f"{order_params['strategy']} - "
                f"Conf: {order_params['confidence']:.1%}"
            )
            
            # Executar ordem
            result = self.mt5.place_order(
                action=action,
                volume=volume,
                stop_loss=sl,
                take_profit=tp,
                comment=comment[:31]  # MT5 limite de 31 caracteres
            )
            
            if result['success']:
                logger.success(
                    f"Ordem {action} executada: Ticket {result['ticket']} | "
                    f"Volume: {volume} | SL: {sl} | TP: {tp}"
                )
                
                # Notificar via Telegram
                self.telegram.send_trade_signal(
                    action=action,
                    price=result.get('price', 0),
                    volume=volume,
                    stop_loss=sl,
                    take_profit=tp,
                    confidence=order_params['confidence'],
                    strategy=order_params['strategy'],
                    reason=order_params['reason']
                )
                
                return True
            else:
                logger.error(f"Falha ao executar ordem: {result['error']}")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao executar ordem: {e}")
            return False
    
    def execute_cycle(self):
        """Executa um ciclo completo de análise e geração de ordem"""
        
        logger.info("=" * 60)
        logger.info(f"Iniciando ciclo - {datetime.now(timezone.utc)}")
        
        # Verificar se deve pular
        should_skip, reason = self.should_skip_cycle()
        if should_skip:
            logger.info(f"Ciclo pulado: {reason}")
            return
        
        # 1. Coletar análises
        logger.info("Coletando análises técnicas e notícias...")
        analysis_data = self.gather_analysis_data()
        
        if not analysis_data:
            logger.warning("Falha ao coletar análises, pulando ciclo")
            return
        
        # 2. Executar estratégias
        logger.info("Executando estratégias...")
        signal = self.execute_strategies(analysis_data)
        
        if not signal or signal.get('action') == 'HOLD':
            logger.info("Nenhum sinal de trading válido gerado")
            return
        
        # 3. Validar com Risk Manager
        logger.info("Validando com Risk Manager...")
        order_params = self.validate_with_risk_manager(signal)
        
        if not order_params:
            logger.info("Ordem rejeitada pelo Risk Manager")
            return
        
        # 4. Executar ordem
        logger.info(
            f"Executando ordem {order_params['action']} "
            f"(volume: {order_params['volume']})..."
        )
        success = self.place_order(order_params)
        
        if success:
            logger.success("Ciclo concluído com sucesso - Ordem executada")
        else:
            logger.error("Ciclo concluído - Falha ao executar ordem")
        
        self.last_execution = datetime.now(timezone.utc)
    
    def start(self):
        """Inicia loop de execução"""
        
        if self.running:
            logger.warning("OrderGenerator já está executando")
            return
        
        logger.info("Iniciando OrderGenerator...")
        self.running = True
        
        try:
            while self.running:
                try:
                    self.execute_cycle()
                except Exception as e:
                    logger.error(f"Erro no ciclo: {e}")
                
                # Aguardar próximo ciclo
                logger.info(f"Aguardando {self.cycle_interval}s...")
                time.sleep(self.cycle_interval)
                
        except KeyboardInterrupt:
            logger.info("Interrupção pelo usuário")
        finally:
            self.stop()
    
    def stop(self):
        """Para execução"""
        logger.info("Parando OrderGenerator...")
        self.running = False
        
        # Desconectar MT5
        if self.mt5.is_connected():
            self.mt5.disconnect()
        
        logger.info("OrderGenerator parado")


if __name__ == "__main__":
    # Executar Order Generator
    generator = OrderGenerator()
    generator.start()
