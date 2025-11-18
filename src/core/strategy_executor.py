"""
Strategy Executor
Executa uma estratégia em thread independente com ciclo próprio
"""

import time
import threading
from datetime import datetime, timezone
from typing import Dict, Optional
from loguru import logger

from core.mt5_connector import MT5Connector
from core.config_manager import ConfigManager
from core.risk_manager import RiskManager
from analysis.technical_analyzer import TechnicalAnalyzer
from analysis.news_analyzer import NewsAnalyzer


class StrategyExecutor:
    """
    Executa uma estratégia de forma independente
    Cada estratégia tem seu próprio ciclo e limite de posições
    """
    
    def __init__(self, strategy_name: str, strategy_instance,
                 config: Dict, mt5: MT5Connector,
                 risk_manager: RiskManager,
                 technical_analyzer: TechnicalAnalyzer,
                 news_analyzer: NewsAnalyzer):
        """
        Inicializa executor de estratégia
        
        Args:
            strategy_name: Nome da estratégia
            strategy_instance: Instância da estratégia
            config: Configuração completa
            mt5: Conector MT5
            risk_manager: Gerenciador de risco
            technical_analyzer: Analisador técnico
            news_analyzer: Analisador de notícias
        """
        self.strategy_name = strategy_name
        self.strategy = strategy_instance
        self.config = config
        self.mt5 = mt5
        self.risk_manager = risk_manager
        self.technical_analyzer = technical_analyzer
        self.news_analyzer = news_analyzer
        
        # Configuração da estratégia
        strategy_config = config.get('strategies', {}).get(
            strategy_name, {}
        )
        
        self.enabled = strategy_config.get('enabled', True)
        self.cycle_seconds = strategy_config.get('cycle_seconds', 300)
        self.max_positions = strategy_config.get('max_positions', 2)
        self.min_confidence = strategy_config.get('min_confidence', 0.6)
        
        # Magic number único para identificar ordens desta estratégia
        # Base: 100000 + hash dos primeiros 5 chars do nome
        base_magic = 100000
        name_hash = sum(ord(c) for c in strategy_name[:5])
        self.magic_number = base_magic + name_hash
        
        # Estado
        self.running = False
        self.thread = None
        self.last_execution = None
        
        logger.info(
            f"StrategyExecutor [{strategy_name}] inicializado: "
            f"ciclo={self.cycle_seconds}s, max_pos={self.max_positions}, "
            f"magic={self.magic_number}"
        )
    
    def start(self):
        """Inicia thread de execução"""
        if self.running:
            logger.warning(
                f"[{self.strategy_name}] já está executando"
            )
            return
        
        self.running = True
        self.thread = threading.Thread(
            target=self._run_loop,
            name=f"Executor-{self.strategy_name}",
            daemon=True
        )
        self.thread.start()
        logger.info(f"[{self.strategy_name}] Thread iniciada")
    
    def stop(self):
        """Para thread de execução"""
        if not self.running:
            return
        
        logger.info(f"[{self.strategy_name}] Parando...")
        self.running = False
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        
        logger.success(f"[{self.strategy_name}] Parado")
    
    def _run_loop(self):
        """Loop principal de execução"""
        logger.info(
            f"[{self.strategy_name}] Loop iniciado "
            f"(ciclo: {self.cycle_seconds}s)"
        )
        
        while self.running:
            try:
                if self.enabled:
                    self._execute_cycle()
                else:
                    logger.debug(
                        f"[{self.strategy_name}] Desabilitada"
                    )
                
                # Aguardar próximo ciclo
                time.sleep(self.cycle_seconds)
                
            except Exception as e:
                logger.error(
                    f"[{self.strategy_name}] Erro no loop: {e}"
                )
                time.sleep(60)  # Aguardar 1 min em caso de erro
    
    def _execute_cycle(self):
        """Executa um ciclo de análise e trading"""
        try:
            logger.info(
                f"[{self.strategy_name}] "
                f"═══════════════════════════════════"
            )
            logger.info(
                f"[{self.strategy_name}] Iniciando ciclo - "
                f"{datetime.now(timezone.utc)}"
            )
            
            # 1. Verificar se pode operar
            if not self._can_trade():
                logger.info(
                    f"[{self.strategy_name}] "
                    f"Não pode operar neste momento"
                )
                return
            
            # 2. Verificar limite de posições
            current_positions = self._count_strategy_positions()
            if current_positions >= self.max_positions:
                logger.info(
                    f"[{self.strategy_name}] "
                    f"Limite atingido: {current_positions}/{self.max_positions}"
                )
                return
            
            # 3. Coletar análises
            technical = self.technical_analyzer.analyze_multi_timeframe()
            news = self.news_analyzer.analyze()
            
            # 4. Executar estratégia
            signal = self.strategy.analyze(technical, news)
            
            if not signal or signal.get('action') == 'HOLD':
                logger.debug(
                    f"[{self.strategy_name}] Sem sinal válido"
                )
                return
            
            confidence = signal.get('confidence', 0)
            if confidence < self.min_confidence:
                logger.info(
                    f"[{self.strategy_name}] "
                    f"Confiança baixa: {confidence:.1%} < {self.min_confidence:.1%}"
                )
                return
            
            # 5. Validar com Risk Manager
            action = signal.get('action')
            if not self.risk_manager.can_open_position(action):
                logger.warning(
                    f"[{self.strategy_name}] "
                    f"Risk Manager rejeitou {action}"
                )
                return
            
            # 6. Calcular parâmetros da ordem
            order_params = self._calculate_order_params(signal)
            
            if not order_params:
                logger.warning(
                    f"[{self.strategy_name}] "
                    f"Falha ao calcular parâmetros"
                )
                return
            
            # 7. Executar ordem
            self._execute_order(order_params)
            
            self.last_execution = datetime.now(timezone.utc)
            
        except Exception as e:
            logger.error(
                f"[{self.strategy_name}] Erro no ciclo: {e}"
            )
    
    def _can_trade(self) -> bool:
        """Verifica se pode operar"""
        # Verificar MT5
        if not self.mt5.is_connected():
            return False
        
        # Verificar janela de notícias
        if self.news_analyzer.is_news_blocking_window(0)[0]:
            return False
        
        return True
    
    def _count_strategy_positions(self) -> int:
        """Conta posições abertas desta estratégia"""
        try:
            positions = self.mt5.get_open_positions()
            
            # Filtrar por magic number
            strategy_positions = [
                p for p in positions
                if p.get('magic', 0) == self.magic_number
            ]
            
            return len(strategy_positions)
            
        except Exception as e:
            logger.error(
                f"[{self.strategy_name}] "
                f"Erro ao contar posições: {e}"
            )
            return self.max_positions  # Assumir máximo em caso de erro
    
    def _calculate_order_params(self, signal: Dict) -> Optional[Dict]:
        """Calcula parâmetros da ordem"""
        try:
            action = signal.get('action')
            
            # Calcular volume
            volume = self.risk_manager.calculate_position_size()
            if volume <= 0:
                return None
            
            # Calcular SL/TP
            sl, tp = self.risk_manager.calculate_sl_tp(action)
            
            return {
                'action': action,
                'volume': volume,
                'sl': sl,
                'tp': tp,
                'magic': self.magic_number,
                'comment': f"URION_{self.strategy_name}",
                'signal': signal
            }
            
        except Exception as e:
            logger.error(
                f"[{self.strategy_name}] "
                f"Erro ao calcular parâmetros: {e}"
            )
            return None
    
    def _execute_order(self, params: Dict):
        """Executa ordem no MT5"""
        try:
            action = params['action']
            volume = params['volume']
            sl = params['sl']
            tp = params['tp']
            magic = params['magic']
            comment = params['comment']
            
            logger.info(
                f"[{self.strategy_name}] "
                f"🚀 EXECUTANDO ORDEM: {action} {volume} lots"
            )
            logger.info(
                f"[{self.strategy_name}] "
                f"   SL: {sl} | TP: {tp} | Magic: {magic}"
            )
            
            # Executar ordem
            result = self.mt5.place_order(
                action=action,
                volume=volume,
                sl=sl,
                tp=tp,
                magic=magic,
                comment=comment
            )
            
            if result:
                ticket = result.get('ticket', 'N/A')
                logger.success(
                    f"[{self.strategy_name}] "
                    f"✅ Ordem executada! Ticket: {ticket}"
                )
            else:
                logger.error(
                    f"[{self.strategy_name}] "
                    f"❌ Falha na execução"
                )
                
        except Exception as e:
            logger.error(
                f"[{self.strategy_name}] "
                f"Erro ao executar ordem: {e}"
            )
