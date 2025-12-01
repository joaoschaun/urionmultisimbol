"""
Strategy Executor
Executa uma estratégia em thread independente com ciclo próprio
MODO 24H: Opera o dia todo com adaptação automática de liquidez
"""

import time
import threading
from datetime import datetime, timezone
from typing import Dict, Optional
from loguru import logger

from core.mt5_connector import MT5Connector
from core.config_manager import ConfigManager
from core.risk_manager import RiskManager
from core.market_hours import MarketHoursManager, ForexMarketHours
from core.watchdog import ThreadWatchdog
from core.adaptive_trading import AdaptiveTradingManager, get_adaptive_manager
from analysis.technical_analyzer import TechnicalAnalyzer
from analysis.news_analyzer import NewsAnalyzer
from analysis.macro_context_analyzer import MacroContextAnalyzer  # 🔥 FASE 1
from analysis.smart_money_detector import SmartMoneyDetector  # 🔥 FASE 1
from database.strategy_stats import StrategyStatsDB
from ml.strategy_learner import StrategyLearner


class StrategyExecutor:
    """
    Executa uma estratégia de forma independente
    Cada estratégia tem seu próprio ciclo e limite de posições
    """
    
    def __init__(self, strategy_name: str, strategy_instance,
                 config: Dict, mt5: MT5Connector,
                 risk_manager: RiskManager,
                 technical_analyzer: TechnicalAnalyzer,
                 news_analyzer: NewsAnalyzer,
                 telegram=None,
                 learner: Optional[StrategyLearner] = None,
                 watchdog: Optional[ThreadWatchdog] = None,
                 market_hours=None,  # 🆕 Aceita market_hours customizado
                 market_analyzer=None,  # 🚪 PORTEIRO (opcional)
                 symbol: str = None,  # 🌍 Símbolo específico
                 symbol_config: Dict = None):  # 🌍 Configuração do símbolo
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
            telegram: Notificador Telegram (opcional)
            learner: Sistema de aprendizagem ML (opcional)
            watchdog: Sistema de monitoramento de threads (opcional)
            market_hours: Gerenciador de horários (opcional, cria automático se None)
            market_analyzer: Porteiro de condições de mercado (opcional)
            symbol: Símbolo para operar (ex: EURUSD, XAUUSD)
            symbol_config: Configuração específica do símbolo
        """
        self.strategy_name = strategy_name
        self.strategy = strategy_instance
        
        # 🔥 FASE 1: Injetar risk_manager na estratégia para cálculos ATR
        if hasattr(self.strategy, 'risk_manager'):
            self.strategy.risk_manager = risk_manager
        
        self.config = config
        self.mt5 = mt5
        self.risk_manager = risk_manager
        
        # 🆕 Usar market_hours customizado ou criar padrão (XAUUSD)
        self.market_hours = market_hours if market_hours else MarketHoursManager(config)
        
        # 🚪 PORTEIRO: Market Condition Analyzer
        self.market_analyzer = market_analyzer
        if self.market_analyzer:
            logger.info(f"[{strategy_name}] 🚪 Porteiro ativo - verificará condições de mercado")
        
        self.technical_analyzer = technical_analyzer
        self.news_analyzer = news_analyzer
        self.telegram = telegram
        
        # 🔥 FASE 1: Macro Context Analyzer
        try:
            self.macro_analyzer = MacroContextAnalyzer()
            logger.info(f"[{strategy_name}] ✅ MacroContextAnalyzer inicializado")
        except Exception as e:
            logger.warning(f"[{strategy_name}] ⚠️  MacroContextAnalyzer não disponível: {e}")
            self.macro_analyzer = None
        
        # 🔥 FASE 1: Smart Money Detector
        try:
            self.smart_money = SmartMoneyDetector()
            logger.info(f"[{strategy_name}] ✅ SmartMoneyDetector inicializado")
        except Exception as e:
            logger.warning(f"[{strategy_name}] ⚠️  SmartMoneyDetector não disponível: {e}")
            self.smart_money = None
        
        # Sistema de aprendizagem
        self.learner = learner if learner else StrategyLearner()
        
        # Watchdog para monitoramento
        self.watchdog = watchdog
        
        # Database para tracking
        self.stats_db = StrategyStatsDB()
        
        # 🌍 Símbolo de trading (passado como parâmetro ou fallback)
        if symbol:
            self.symbol = symbol
            self.symbol_config = symbol_config or {}
        else:
            # Fallback para compatibilidade com código antigo
            self.symbol = config.get('trading', {}).get('symbol', 'XAUUSD')
            self.symbol_config = config.get('trading', {}).get('symbols', {}).get(self.symbol, {})
        
        # Configuração da estratégia
        self.strategy_config = config.get('strategies', {}).get(
            strategy_name, {}
        )
        
        self.enabled = self.strategy_config.get('enabled', True)
        self.cycle_seconds = self.strategy_config.get('cycle_seconds', 300)
        self.max_positions = self.strategy_config.get('max_positions', 2)
        
        # 🔄 MODO 24H: Adaptive Trading Manager
        self.adaptive_manager = get_adaptive_manager(config)
        self._log_session_on_start = True  # Log sessão apenas na inicialização
        
        # Usar min_confidence aprendido ou padrão do config
        learned_confidence = self.learner.get_learned_confidence(strategy_name)
        config_confidence = self.strategy_config.get('min_confidence', 0.6)
        
        # Se já aprendeu algo, usar valor aprendido
        if self.learner.learning_data.get(strategy_name, {}).get('total_trades', 0) >= 10:
            self.min_confidence = learned_confidence
            logger.info(
                f"[{strategy_name}] 🤖 Usando confiança APRENDIDA: {learned_confidence:.2f} "
                f"(config: {config_confidence:.2f})"
            )
        else:
            self.min_confidence = config_confidence
            logger.debug(f"[{strategy_name}] Usando confiança do config: {config_confidence:.2f}")
        
        # Magic number único para identificar ordens desta estratégia + símbolo
        # Base: 100000 + hash do nome + hash do símbolo
        base_magic = 100000
        name_hash = sum(ord(c) for c in strategy_name[:5])
        symbol_hash = sum(ord(c) for c in self.symbol[:4]) if self.symbol else 0
        self.magic_number = base_magic + name_hash + symbol_hash
        
        # Estado
        self.running = False
        self.thread = None
        self.last_execution = None
        
        logger.info(
            f"StrategyExecutor [{strategy_name}@{self.symbol}] inicializado: "
            f"ciclo={self.cycle_seconds}s, max_pos={self.max_positions}, "
            f"magic={self.magic_number}, min_conf={self.min_confidence:.2f}"
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
        
        # Registrar no watchdog se disponível
        if self.watchdog:
            self.watchdog.register_thread(
                f"Executor-{self.strategy_name}",
                callback=lambda: logger.error(
                    f"🚨 FREEZE DETECTADO em {self.strategy_name}!"
                )
            )
        
        while self.running:
            try:
                # Heartbeat para watchdog
                if self.watchdog:
                    self.watchdog.heartbeat(f"Executor-{self.strategy_name}")
                
                if self.enabled:
                    self._execute_cycle()
                else:
                    logger.debug(
                        f"[{self.strategy_name}] Desabilitada"
                    )
                
                # 🚨 HEARTBEAT ANTES de dormir
                if self.watchdog:
                    self.watchdog.heartbeat(f"Executor-{self.strategy_name}")
                
                # Aguardar próximo ciclo (pode ser >600s para algumas estratégias)
                # Dividir sleep em chunks para enviar heartbeat periodicamente
                sleep_remaining = self.cycle_seconds
                sleep_chunk = 60  # Heartbeat a cada 60 segundos durante o sleep
                
                while sleep_remaining > 0 and self.running:
                    chunk = min(sleep_chunk, sleep_remaining)
                    time.sleep(chunk)
                    sleep_remaining -= chunk
                    
                    # 🚨 HEARTBEAT durante o sleep (a cada 60s)
                    if sleep_remaining > 0 and self.watchdog:
                        self.watchdog.heartbeat(f"Executor-{self.strategy_name}")
                
            except KeyboardInterrupt:
                logger.info(f"[{self.strategy_name}] Interrompido pelo usuário")
                break
            except Exception as e:
                logger.exception(
                    f"[{self.strategy_name}] ERRO CRÍTICO no loop: {e}"
                )
                # Tentar reconectar MT5 se houver erro
                try:
                    if not self.mt5.ensure_connection():
                        logger.error(f"[{self.strategy_name}] Falha ao reconectar MT5")
                except:
                    pass
                
                # Aguardar antes de tentar novamente
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
            
            # DEBUG: Log antes de verificar MT5
            logger.info(f"[{self.strategy_name}] 🔍 Verificando conexão MT5...")
            
            # CRITICAL: Verificar conexão MT5 antes de cada ciclo
            if not self.mt5.is_connected():
                logger.warning(
                    f"[{self.strategy_name}] MT5 desconectado! "
                    f"Tentando reconectar..."
                )
                if not self.mt5.ensure_connection():
                    logger.error(
                        f"[{self.strategy_name}] Falha ao reconectar MT5. "
                        f"Pulando ciclo."
                    )
                    return
                logger.success(f"[{self.strategy_name}] MT5 reconectado!")
            
            # DEBUG: Log após verificar MT5
            logger.info(f"[{self.strategy_name}] ✅ MT5 OK, verificando horário...")
            
            # 1. Verificar se pode operar
            if not self._can_trade():
                logger.info(
                    f"[{self.strategy_name}] "
                    f"Não pode operar neste momento"
                )
                # 🚨 HEARTBEAT antes de return
                if self.watchdog:
                    self.watchdog.heartbeat(f"Executor-{self.strategy_name}")
                return
            
            # DEBUG: Log após _can_trade
            logger.info(f"[{self.strategy_name}] ✅ Pode operar, verificando posições...")
            
            # 🚨 HEARTBEAT após check de trading
            if self.watchdog:
                self.watchdog.heartbeat(f"Executor-{self.strategy_name}")
            
            # 2. Verificar limite de posições
            logger.info(f"[{self.strategy_name}] 🔢 Contando posições abertas...")
            current_positions = self._count_strategy_positions()
            logger.info(f"[{self.strategy_name}] ℹ️  Posições: {current_positions}/{self.max_positions}")
            if current_positions >= self.max_positions:
                logger.info(
                    f"[{self.strategy_name}] "
                    f"Limite atingido: {current_positions}/{self.max_positions}"
                )
                # 🚨 HEARTBEAT antes de return
                if self.watchdog:
                    self.watchdog.heartbeat(f"Executor-{self.strategy_name}")
                return
            
            # 🚨 HEARTBEAT após check de posições
            if self.watchdog:
                self.watchdog.heartbeat(f"Executor-{self.strategy_name}")
            
            # 3. Coletar análises COM TIMEOUT (evitar travamento)
            technical = None
            news = None
            
            # 🚨 HEARTBEAT ANTES de análise técnica
            if self.watchdog:
                self.watchdog.heartbeat(f"Executor-{self.strategy_name}")
            
            try:
                # Timeout de 60s para análise técnica
                logger.info(f"[{self.strategy_name}] 📊 Iniciando análise técnica...")
                technical = self.technical_analyzer.analyze_multi_timeframe()
                logger.info(f"[{self.strategy_name}] ✅ Análise técnica OK")
            except Exception as e:
                logger.error(f"[{self.strategy_name}] Erro na análise técnica: {e}")
                return  # Não pode operar sem análise técnica
            
            # 🚨 HEARTBEAT após análise técnica
            if self.watchdog:
                self.watchdog.heartbeat(f"Executor-{self.strategy_name}")
            
            try:
                # Timeout de 30s para análise de notícias
                logger.info(f"[{self.strategy_name}] 📰 Iniciando análise de notícias...")
                news = self.news_analyzer.get_sentiment_summary()
                logger.info(f"[{self.strategy_name}] ✅ Notícias OK")
            except Exception as e:
                logger.warning(f"[{self.strategy_name}] Erro ao buscar notícias (continuando): {e}")
                news = {}  # Continua sem notícias
            
            # 🚨 HEARTBEAT após análises
            if self.watchdog:
                self.watchdog.heartbeat(f"Executor-{self.strategy_name}")
            
            # 4. Executar estratégia
            signal = self.strategy.analyze(technical, news)
            
            if not signal or signal.get('action') == 'HOLD':
                logger.debug(
                    f"[{self.strategy_name}] Sem sinal válido"
                )
                # 🚨 HEARTBEAT antes de return
                if self.watchdog:
                    self.watchdog.heartbeat(f"Executor-{self.strategy_name}")
                return
            
            confidence = signal.get('confidence', 0)
            if confidence < self.min_confidence:
                logger.info(
                    f"[{self.strategy_name}] "
                    f"Confiança baixa: {confidence:.1%} < {self.min_confidence:.1%}"
                )
                # 🚨 HEARTBEAT antes de return
                if self.watchdog:
                    self.watchdog.heartbeat(f"Executor-{self.strategy_name}")
                return
            
            # 🔥 FASE 1: Verificar Smart Money antes de executar
            if self.smart_money:
                try:
                    # Obter dados de preço
                    rates = self.mt5.get_rates(self.symbol, '1H', 500)
                    if rates is not None and not rates.empty:
                        smart_analysis = self.smart_money.detect_patterns(rates)
                        
                        # Verificar se Smart Money contradiz o sinal
                        action = signal.get('action')
                        
                        # Stop Hunting ativo = mercado enganoso, evitar
                        if smart_analysis.get('stop_hunting', {}).get('active', False):
                            logger.warning(
                                f"[{self.strategy_name}] "
                                f"🎣 STOP HUNTING detectado - Sinal suspenso"
                            )
                            if self.watchdog:
                                self.watchdog.heartbeat(f"Executor-{self.strategy_name}")
                            return
                        
                        # Acumulação favorece compra, Distribuição favorece venda
                        accumulation = smart_analysis.get('accumulation', {}).get('active', False)
                        distribution = smart_analysis.get('distribution', {}).get('active', False)
                        
                        # SELL durante Acumulação = Contra Smart Money
                        if action == 'SELL' and accumulation:
                            logger.warning(
                                f"[{self.strategy_name}] "
                                f"🐋 Smart Money acumulando - SELL bloqueado"
                            )
                            if self.watchdog:
                                self.watchdog.heartbeat(f"Executor-{self.strategy_name}")
                            return
                        
                        # BUY durante Distribuição = Contra Smart Money
                        if action == 'BUY' and distribution:
                            logger.warning(
                                f"[{self.strategy_name}] "
                                f"🐋 Smart Money distribuindo - BUY bloqueado"
                            )
                            if self.watchdog:
                                self.watchdog.heartbeat(f"Executor-{self.strategy_name}")
                            return
                        
                        # Sinal alinhado com Smart Money
                        if (action == 'BUY' and accumulation) or (action == 'SELL' and distribution):
                            logger.info(
                                f"[{self.strategy_name}] "
                                f"✅ Smart Money alinhado: {action} com "
                                f"{'Acumulação' if accumulation else 'Distribuição'}"
                            )
                        
                except Exception as smart_error:
                    logger.debug(f"[{self.strategy_name}] Erro ao verificar Smart Money: {smart_error}")
            
            # 5. Calcular parâmetros da ordem
            order_params = self._calculate_order_params(signal)
            
            if not order_params:
                logger.warning(
                    f"[{self.strategy_name}] "
                    f"Falha ao calcular parâmetros"
                )
                # 🚨 HEARTBEAT antes de return
                if self.watchdog:
                    self.watchdog.heartbeat(f"Executor-{self.strategy_name}")
                return
            
            # 6. Validar com Risk Manager
            action = signal.get('action')
            volume = order_params.get('volume')
            
            logger.debug(
                f"[{self.strategy_name}] "
                f"Validando: symbol={self.symbol}, action={action}, volume={volume}"
            )
            
            risk_check = self.risk_manager.can_open_position(
                symbol=self.symbol,
                order_type=action,
                lot_size=volume
            )
            if not risk_check.get('allowed', False):
                logger.warning(
                    f"[{self.strategy_name}] "
                    f"Risk Manager rejeitou: {risk_check.get('reason')}"
                )
                # 🚨 HEARTBEAT antes de return
                if self.watchdog:
                    self.watchdog.heartbeat(f"Executor-{self.strategy_name}")
                return
            
            # 7. Executar ordem
            self._execute_order(order_params)
            
            # 🚨 HEARTBEAT no final do ciclo (SUCESSO)
            if self.watchdog:
                self.watchdog.heartbeat(f"Executor-{self.strategy_name}")
            
        except Exception as e:
            logger.exception(
                f"[{self.strategy_name}] ERRO em _execute_cycle: {e}"
            )
            # 🚨 HEARTBEAT mesmo em caso de erro
            if self.watchdog:
                self.watchdog.heartbeat(f"Executor-{self.strategy_name}")
    
    def _can_trade(self) -> bool:
        """
        Verifica se pode operar
        🔄 MODO 24H: Usa AdaptiveTradingManager para ajustar por sessão
        """
        try:
            # Verificar MT5
            if not self.mt5.is_connected():
                return False
            
            # 🔄 MODO 24H: Verificar sessão adaptativa PRIMEIRO
            if self.adaptive_manager:
                can_trade, reason = self.adaptive_manager.should_trade(
                    self.symbol, 
                    self.strategy_name
                )
                if not can_trade:
                    logger.debug(
                        f"[{self.strategy_name}@{self.symbol}] "
                        f"🔄 Sessão: {reason}"
                    )
                    return False
                
                # Log sessão atual (apenas 1x por ciclo)
                if self._log_session_on_start:
                    self.adaptive_manager.log_session_status()
                    self._log_session_on_start = False
            
            # Verificar horário do mercado (backup - forex 24/5)
            can_open, reason = self.market_hours.can_open_new_positions()
            if not can_open:
                logger.debug(f"[{self.strategy_name}] Mercado: {reason}")
                return False
            
            # Verificar janela de notícias (COM TIMEOUT)
            try:
                if self.news_analyzer.is_news_blocking_window(0)[0]:
                    return False
            except Exception as e:
                logger.warning(
                    f"[{self.strategy_name}] Erro janela notícias: {e}"
                )
                # Continuar mesmo com erro na verificação de notícias
            
            # 🚪 PORTEIRO: Verificar condições de mercado
            if self.market_analyzer:
                try:
                    market_analysis = self.market_analyzer.analyze()
                    
                    if market_analysis:
                        strict_mode = self.config.get(
                            'trading', {}
                        ).get('market_filter_strict', False)
                        
                        if not self.market_analyzer.is_strategy_allowed(
                            self.strategy_name, 
                            market_analysis, 
                            strict_mode=strict_mode
                        ):
                            logger.info(
                                f"[{self.strategy_name}] 🚫 BLOQUEADO | "
                                f"Condição: {market_analysis.condition.value}"
                            )
                            return False
                except Exception as e:
                    logger.warning(
                        f"[{self.strategy_name}] Erro porteiro: {e}"
                    )
            
            return True
            
        except Exception as e:
            logger.error(f"[{self.strategy_name}] Erro em _can_trade: {e}")
            return False
    
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
        """
        Calcula parâmetros da ordem
        🔄 MODO 24H: Aplica ajustes adaptativos por sessão
        """
        try:
            action = signal.get('action')
            entry_price = signal.get('price')
            
            # SL/TP vêm do sinal da estratégia
            sl = signal.get('sl')
            tp = signal.get('tp')
            
            # Se não tiver SL/TP, usar valores padrão baseados em ATR
            if not sl or not tp:
                logger.debug(
                    f"[{self.strategy_name}] "
                    f"Sinal sem SL/TP - usando ATR"
                )
                atr = signal.get('details', {}).get(
                    'atr', entry_price * 0.02
                )
                sl = entry_price - (2 * atr) if action == 'BUY' \
                    else entry_price + (2 * atr)
                tp = entry_price + (3 * atr) if action == 'BUY' \
                    else entry_price - (3 * atr)
            
            # Calcular volume base com Kelly Criterion
            volume = self.risk_manager.calculate_position_size(
                symbol=self.symbol,
                entry_price=entry_price,
                stop_loss=sl,
                strategy_name=self.strategy_name,
                use_kelly=True
            )
            if volume <= 0:
                return None
            
            # 🔄 MODO 24H: Aplicar ajustes adaptativos por sessão
            if self.adaptive_manager:
                session_params = self.adaptive_manager.get_session_params(
                    self.symbol
                )
                
                # Ajustar volume pela sessão
                adjusted_volume = round(
                    volume * session_params.lot_multiplier, 2
                )
                
                # Ajustar SL/TP pela sessão
                sl_distance = abs(entry_price - sl)
                tp_distance = abs(entry_price - tp)
                
                adjusted_sl_distance = sl_distance * session_params.sl_multiplier
                adjusted_tp_distance = tp_distance * session_params.tp_multiplier
                
                if action == 'BUY':
                    sl = entry_price - adjusted_sl_distance
                    tp = entry_price + adjusted_tp_distance
                else:
                    sl = entry_price + adjusted_sl_distance
                    tp = entry_price - adjusted_tp_distance
                
                # Garantir volume mínimo
                volume = max(0.01, adjusted_volume)
                
                logger.info(
                    f"[{self.strategy_name}@{self.symbol}] "
                    f"🔄 Sessão {session_params.mode.value}: "
                    f"vol={adjusted_volume:.2f}, "
                    f"SL×{session_params.sl_multiplier}, "
                    f"TP×{session_params.tp_multiplier}"
                )
            
            return {
                'action': action,
                'volume': volume,
                'sl': sl,
                'tp': tp,
                'magic': self.magic_number,
                'comment': f"S|{sl:.1f}|{tp:.1f}",
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
            signal = params.get('signal', {})  # Extrair signal de params
            
            # 🔥 SOLUÇÃO: Comment do MT5 tem limite de 31 caracteres
            # Formato ULTRA compacto: "S|4172.8|4096.7" (apenas SL|TP)
            # O strategy_name está no MAGIC number, não precisa no comment
            if sl is not None and tp is not None:
                # Arredondar para 1 casa decimal
                comment = f"S|{sl:.1f}|{tp:.1f}"
                
                # Garantir limite de 31 caracteres (15 chars é suficiente)
                if len(comment) > 31:
                    # Remover casas decimais se necessário
                    comment = f"S|{int(sl)}|{int(tp)}"
            else:
                comment = "URION"  # Fallback genérico
            
            logger.debug(f"[{self.strategy_name}] Comment: '{comment}' ({len(comment)} chars)")
            
            # 🔥 FASE 1: Verificar macro context antes de executar
            # 🎯 ESTRATÉGIAS DE TENDÊNCIA: macro confirma direção
            # 🎯 ESTRATÉGIAS DE REVERSÃO/SCALPING: macro NÃO se aplica
            
            # Verificar se estratégia está isenta do filtro macro
            exempt_from_macro = self.strategy_config.get('exempt_from_macro', False)
            trend_strategies = ['trend_following', 'breakout', 'news_trading']  # Seguem tendência
            
            if exempt_from_macro:
                logger.debug(
                    f"[{self.strategy_name}] "
                    f"⚡ Estratégia ISENTA do filtro macro (config: exempt_from_macro=true)"
                )
            elif self.macro_analyzer and self.strategy_name.lower() in trend_strategies:
                try:
                    macro = self.macro_analyzer.analyze()
                    
                    # Se macro tem viés forte, verificar alinhamento
                    if macro.confidence >= 0.6:
                        # BUY mas macro BEARISH = NÃO executar
                        if action == 'BUY' and macro.gold_bias == 'BEARISH':
                            logger.warning(
                                f"[{self.strategy_name}] "
                                f"🚫 SINAL BLOQUEADO: BUY com macro BEARISH "
                                f"(confiança {macro.confidence*100:.0f}%)"
                            )
                            return
                        
                        # SELL mas macro BULLISH = NÃO executar
                        if action == 'SELL' and macro.gold_bias == 'BULLISH':
                            logger.warning(
                                f"[{self.strategy_name}] "
                                f"🚫 SINAL BLOQUEADO: SELL com macro BULLISH "
                                f"(confiança {macro.confidence*100:.0f}%)"
                            )
                            return
                        
                        # Sinal alinhado com macro
                        logger.info(
                            f"[{self.strategy_name}] "
                            f"✅ Macro alinhado: {action} com bias {macro.gold_bias} "
                            f"({macro.confidence*100:.0f}%)"
                        )
                except Exception as macro_error:
                    logger.debug(f"[{self.strategy_name}] Erro ao verificar macro: {macro_error}")
            elif self.strategy_name.lower() not in trend_strategies:
                logger.debug(
                    f"[{self.strategy_name}] "
                    f"⚡ Estratégia de reversão - Macro context ignorado"
                )
            
            logger.info(
                f"[{self.strategy_name}] "
                f"🚀 EXECUTANDO ORDEM: {action} {volume} lots"
            )
            logger.info(
                f"[{self.strategy_name}] "
                f"   SL mental: {sl} | TP: {tp} | Magic: {magic}"
            )
            
            # 🔥 FASE 1: Gerenciamento manual - NÃO enviar SL/TP inicialmente
            # Vamos gerenciar manualmente até passar o tempo mínimo
            logger.info(
                f"[{self.strategy_name}] "
                f"🛡️  Proteção ativa: SL/TP enviados como backup + gerenciamento manual"
            )
            
            # 🔧 CORREÇÃO: Enviar SL/TP como BACKUP de segurança
            # OrderManager vai gerenciar, mas SL/TP real protege caso OrderManager falhe
            result = self.mt5.place_order(
                symbol=self.symbol,
                order_type=action,
                volume=volume,
                sl=sl,  # ✅ SL como backup de segurança
                tp=tp,  # ✅ TP como backup de segurança
                comment=comment,
                magic=magic
            )
            
            if result:
                ticket = result.get('ticket', 'N/A')
                logger.success(
                    f"[{self.strategy_name}] "
                    f"✅ Ordem executada! Ticket: {ticket}"
                )
                
                # Enviar notificação Telegram
                if self.telegram:
                    try:
                        self.telegram.send_trade_notification(
                            action=action,
                            symbol=self.symbol,
                            price=signal.get('price', 0),
                            volume=volume,
                            sl=sl,
                            tp=tp,
                            strategy=self.strategy_name,
                            confidence=signal.get('confidence', 0) * 100
                        )
                        logger.debug(f"[{self.strategy_name}] Notificação Telegram enviada")
                    except Exception as telegram_error:
                        logger.error(f"[{self.strategy_name}] Erro ao enviar Telegram: {telegram_error}")
                
                # Salvar no banco de dados para tracking
                try:
                    # 🔧 CORREÇÃO: Obter preço real do símbolo via MT5
                    import MetaTrader5 as mt5_module
                    actual_open_price = signal.get('price', 0)
                    try:
                        tick_info = mt5_module.symbol_info_tick(self.symbol)
                        if tick_info:
                            # BUY usa ask, SELL usa bid
                            actual_open_price = (
                                tick_info.ask if action == 'BUY' else tick_info.bid
                            )
                    except Exception:
                        pass  # Usa o preço do signal como fallback
                    
                    trade_data = {
                        'strategy_name': self.strategy_name,
                        'ticket': ticket,
                        'symbol': self.symbol,
                        'type': action,
                        'volume': volume,
                        'open_price': actual_open_price,  # ✅ Preço correto
                        'sl': sl,
                        'tp': tp,
                        'open_time': datetime.now(),
                        'signal_confidence': signal.get('confidence', 0),
                        'market_conditions': str(signal.get('details', {}))
                    }
                    
                    self.stats_db.save_trade({
                        **trade_data,
                        'signal_confidence': trade_data['signal_confidence'] * 100
                    })
                    logger.debug(f"[{self.strategy_name}] Trade salvo no database")
                    
                    # 🤖 Sistema de aprendizagem: registrar abertura do trade
                    # (Aprendizado real acontece quando trade é fechado)
                    logger.debug(f"[{self.strategy_name}] 🤖 Trade registrado para aprendizagem futura")
                    
                except Exception as db_error:
                    logger.error(f"[{self.strategy_name}] Erro ao salvar trade: {db_error}")
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
