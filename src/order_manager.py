"""
Order Manager
Gerencia posições abertas em tempo real
Ciclo de execução: 5 segundos (configurável)
"""

import time
import threading
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional
from loguru import logger

from core.mt5_connector import MT5Connector
from core.config_manager import ConfigManager
from core.risk_manager import RiskManager
from core.market_hours import MarketHoursManager, ForexMarketHours
from core.adaptive_spread_manager import AdaptiveSpreadManager
from analysis.technical_analyzer import TechnicalAnalyzer
from notifications.telegram_bot import TelegramNotifier
from database.strategy_stats import StrategyStatsDB
from ml.strategy_learner import StrategyLearner

# 🚀 NOVAS MELHORIAS: Importar análise macro
try:
    from analysis.macro_context_analyzer import MacroContextAnalyzer
    MACRO_AVAILABLE = True
except ImportError:
    MACRO_AVAILABLE = False
    logger.debug("MacroContextAnalyzer não disponível")


class OrderManager:
    """
    Gerenciador de ordens abertas
    Monitora posições e aplica trailing stop, break-even, etc
    """
    
    def __init__(self, config=None, telegram=None, market_hours=None):
        """
        Inicializa Order Manager
        
        Args:
            config: Configuração global (opcional)
            telegram: Notificador Telegram (opcional)
            market_hours: Gerenciador de horários (opcional, cria automático se None)
        """
        
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
        
        # 🆕 Adaptive Spread Manager - Adapta estratégias ao spread
        self.spread_manager = AdaptiveSpreadManager(self.config)
        
        # 🆕 Usar market_hours customizado ou criar padrão (XAUUSD)
        self.market_hours = market_hours if market_hours else MarketHoursManager(self.config)
        
        self.technical_analyzer = TechnicalAnalyzer(self.mt5, self.config)
        self.telegram = telegram if telegram else TelegramNotifier(self.config)
        self.stats_db = StrategyStatsDB()
        
        # Sistema de aprendizagem
        self.learner = StrategyLearner()
        
        # 🚀 MELHORIA: Inicializar analisador macro
        self.macro_analyzer = MacroContextAnalyzer() if MACRO_AVAILABLE else None
        
        # 🚀 NOVAS MELHORIAS: Proteção contra fechamento prematuro
        self.MIN_TRADE_DURATION = {
            'scalping': 2,           # 2 minutos
            'range_trading': 5,      # 5 minutos
            'mean_reversion': 8,     # 8 minutos
            'trend_following': 15,   # 15 minutos
            'breakout': 10,          # 10 minutos
            'news_trading': 3        # 3 minutos
        }
        
        # 🎯 CONFIGURAÇÕES ESPECÍFICAS POR ESTRATÉGIA
        self.strategy_configs = {
            'scalping': {
                'trailing_stop_distance': 5,    # 5 pips (muito agressivo)
                'partial_close_at': 0.3,        # Fecha 30% do TP
                'partial_close_volume': 0.5,    # Fecha 50% da posição
                'breakeven_at': 0.2,            # Move SL para BE em 20% do TP
                'max_hold_time': 300,           # 5 minutos máximo
                'aggressive_trailing': True,    # Trailing mais agressivo
            },
            'range_trading': {
                'trailing_stop_distance': 10,   # 10 pips
                'partial_close_at': 0.5,        # Fecha 50% do TP
                'partial_close_volume': 0.5,
                'breakeven_at': 0.3,            # 30% do TP
                'max_hold_time': 3600,          # 1 hora
                'aggressive_trailing': False,
            },
            'trend_following': {
                'trailing_stop_distance': 20,   # 20 pips (deixa correr)
                'partial_close_at': 0.7,        # Aguarda mais (70% do TP)
                'partial_close_volume': 0.3,    # Fecha apenas 30%
                'breakeven_at': 0.4,            # 40% do TP
                'max_hold_time': None,          # Sem limite
                'aggressive_trailing': False,
            },
            'breakout': {
                'trailing_stop_distance': 15,
                'partial_close_at': 0.6,        # 60% do TP
                'partial_close_volume': 0.4,    # Fecha 40%
                'breakeven_at': 0.5,            # 50% do TP
                'max_hold_time': 7200,          # 2 horas
                'aggressive_trailing': True,    # Agressivo após breakout
            },
            'mean_reversion': {
                'trailing_stop_distance': 8,
                'partial_close_at': 0.4,        # Fecha rápido (40% do TP)
                'partial_close_volume': 0.6,    # Fecha 60%
                'breakeven_at': 0.2,            # Rápido para BE
                'max_hold_time': 1800,          # 30 minutos
                'aggressive_trailing': False,
            },
            'news_trading': {
                'trailing_stop_distance': 25,   # Volatilidade alta
                'partial_close_at': 0.5,
                'partial_close_volume': 0.5,
                'breakeven_at': 0.3,
                'max_hold_time': 900,           # 15 minutos
                'aggressive_trailing': True,    # Movimentos rápidos
            },
        }
        
        # Mapa de magic numbers para estratégias (para configuração customizada)
        self.strategy_map = self._build_strategy_map()
        
        # Estado
        self.running = False
        self.monitored_positions = {}  # ticket: position_data
        self.last_market_close_check = None
        
        # 🔒 THREAD SAFETY: Lock para proteger acesso ao estado compartilhado
        self.positions_lock = threading.Lock()
        
        # 🚨 NOVO: Controle de modificações (evitar spam)
        self.last_modification = {}  # ticket: datetime
        self.min_modification_interval = 30  # segundos (não modificar antes disso)
        self.min_sl_change_pips = 2  # Mínimo de 2 pips de mudança
        
        # 🎯 SISTEMA DE ESTADOS DE GESTÃO POR POSIÇÃO
        # Estados: 0=ABERTA, 1=BREAKEVEN, 2=PARCIAL_FEITA, 3=TRAILING_ATIVO, 4=FINALIZANDO
        self.position_states = {}  # ticket: {'stage': int, 'max_profit': float, 'max_rr': float}
        
        # 📊 Rastreamento de performance por posição
        self.position_performance = {}  # ticket: {'max_profit': float, 'max_drawdown': float, 'entry_time': datetime}
        
        # 💾 PERSISTÊNCIA DE ESTADOS (evita perda de informação ao reiniciar)
        self.state_file = Path("data/position_states.json")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_states()  # Carregar estados salvos
        
        logger.info("OrderManager inicializado")
        logger.info(f"Ciclo: {self.cycle_interval}s")
        logger.info(f"Configuração customizada por estratégia: {len(self.strategy_map)} estratégias")
        
        # Verificar se recuperou estados
        if self.position_states:
            logger.info(f"📂 {len(self.position_states)} estados recuperados do arquivo")
    
    def _load_states(self):
        """Carrega estados salvos de arquivo JSON"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    
                    # Converter chaves de string para int (tickets)
                    self.position_states = {
                        int(k): v for k, v in data.get('position_states', {}).items()
                    }
                    self.position_performance = {
                        int(k): v for k, v in data.get('position_performance', {}).items()
                    }
                    
                    logger.success(f"💾 Estados carregados: {len(self.position_states)} posições")
        except Exception as e:
            logger.warning(f"⚠️  Erro ao carregar estados: {e}")
            self.position_states = {}
            self.position_performance = {}
    
    def _save_states(self):
        """Salva estados em arquivo JSON"""
        try:
            with self.positions_lock:
                data = {
                    'position_states': {str(k): v for k, v in self.position_states.items()},
                    'position_performance': {str(k): v for k, v in self.position_performance.items()},
                    'last_update': datetime.now(timezone.utc).isoformat()
                }
                
                with open(self.state_file, 'w') as f:
                    json.dump(data, f, indent=2, default=str)
                    
        except Exception as e:
            logger.error(f"❌ Erro ao salvar estados: {e}")
    
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
            Dict com configuração específica da estratégia
        """
        # Buscar nome da estratégia pelo magic number
        strategy_info = self.strategy_map.get(magic_number, {'name': 'unknown'})
        strategy_name = strategy_info.get('name', 'unknown')
        
        # Retornar config específica ou padrão
        config = self.strategy_configs.get(strategy_name, {
            'trailing_stop_distance': 15,
            'partial_close_at': 0.5,
            'partial_close_volume': 0.5,
            'breakeven_at': 0.3,
            'max_hold_time': None,
            'aggressive_trailing': False,
        })
        
        # Adicionar nome para log
        config['strategy_name'] = strategy_name
        return config
    
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
                                    
                                    logger.info(f"🤖 Iniciando busca de profit para {ticket} ({strategy_name})")
                                    
                                    # 🚨 BUSCAR PROFIT REAL: tentar pegar do histórico de posições
                                    final_profit = 0.0
                                    close_price = 0.0
                                    try:
                                        # Buscar DEALS (não ORDERS!) dos últimos 24h
                                        from datetime import timedelta
                                        
                                        logger.info(f"🤖 Buscando deals para ticket {ticket}...")
                                        
                                        # Buscar TODOS os deals recentes
                                        all_deals = mt5.history_deals_get(
                                            datetime.now() - timedelta(hours=24),
                                            datetime.now()
                                        )
                                        
                                        if not all_deals:
                                            logger.warning(f"⚠️ Nenhum deal encontrado nos últimos 24h")
                                            final_profit = monitored.get('profit', 0.0) + monitored.get('profit_realizado', 0.0)
                                        else:
                                            # Filtrar deals desta posição específica
                                            position_deals = [d for d in all_deals if d.position_id == ticket]
                                            
                                            logger.info(f"🤖 Total de deals: {len(all_deals)}, desta posição: {len(position_deals)}")
                                            
                                            if position_deals:
                                                # Somar profit de TODOS os deals (IN + OUT + parciais)
                                                for deal in position_deals:
                                                    final_profit += deal.profit
                                                    logger.debug(f"  Deal {deal.ticket}: entry={deal.entry}, profit=${deal.profit:.2f}")
                                                    
                                                    # Pegar close_price do último deal OUT
                                                    if deal.entry == 1:  # OUT (fechamento)
                                                        close_price = deal.price
                                                
                                                logger.success(f"✅ Profit do histórico MT5: ${final_profit:.2f} ({len(position_deals)} deals)")
                                            else:
                                                # Nenhum deal encontrado, usar monitorado
                                                final_profit = monitored.get('profit', 0.0) + monitored.get('profit_realizado', 0.0)
                                                logger.warning(f"⚠️ Nenhum deal encontrado para ticket {ticket}, usando monitorado: ${final_profit:.2f}")
                                    except Exception as hist_error:
                                        # Se falhar, usar profit monitorado
                                        final_profit = monitored.get('profit', 0.0) + monitored.get('profit_realizado', 0.0)
                                        logger.error(f"❌ ERRO ao buscar deals: {type(hist_error).__name__}: {hist_error}")
                                        logger.warning(f"🤖 Usando profit monitorado: ${final_profit:.2f}")
                                    
                                    # Preparar dados
                                    trade_data = {
                                        'profit': final_profit,
                                        'signal_confidence': monitored.get('confidence', 0.5),
                                        'market_conditions': monitored.get('conditions', ''),
                                        'volume': monitored.get('volume_inicial', trade_info.get('volume', 0.05)),
                                        'duration_minutes': duration_minutes
                                    }
                                    
                                    logger.info(f"🤖 [{strategy_name}] Profit final calculado: ${final_profit:.2f}")
                                    
                                    # Se não conseguiu pegar close_price dos deals, usar last_price monitorado
                                    if close_price == 0.0:
                                        close_price = monitored.get('last_price', trade_info.get('open_price', 0))
                                    
                                    # 🆕 ATUALIZAR BANCO DE DADOS COM CLOSE_TIME E PROFIT
                                    try:
                                        close_data = {
                                            'close_price': close_price,
                                            'close_time': datetime.now(timezone.utc),
                                            'profit': final_profit,
                                            'commission': 0,  # MT5 já inclui na profit
                                            'swap': 0,  # MT5 já inclui na profit
                                            'status': 'closed',
                                            'strategy_name': strategy_name
                                        }
                                        self.stats_db.update_trade_close(ticket, close_data)
                                        logger.success(f"✅ Banco atualizado: Ticket {ticket}, Close: {close_price:.2f}, Profit ${final_profit:.2f}")
                                    except Exception as update_error:
                                        logger.error(f"❌ Erro ao atualizar banco: {update_error}")
                                    
                                    # Aprender!
                                    self.learner.learn_from_trade(strategy_name, trade_data)
                                    
                                    emoji = "🟢" if trade_data['profit'] > 0 else "🔴"
                                    logger.info(
                                        f"🤖 [{strategy_name}] Aprendeu com trade (via database): "
                                        f"{emoji} ${trade_data['profit']:.2f} "
                                        f"(duração: {duration_minutes:.1f}min)"
                                    )
                                    
                                    # 📱 NOTIFICAÇÃO TELEGRAM (WINS E LOSSES)
                                    try:
                                        if final_profit > 0:
                                            result_emoji = "✅"
                                            result_text = "WIN"
                                            result_color = "🟢"
                                        elif final_profit < 0:
                                            result_emoji = "❌"
                                            result_text = "LOSS"
                                            result_color = "🔴"
                                        else:
                                            result_emoji = "⚪"
                                            result_text = "BREAK-EVEN"
                                            result_color = "⚪"
                                        
                                        # Enviar notificação
                                        self.telegram.send_message_sync(
                                            f"{result_emoji} **{result_text}** {result_emoji}\n"
                                            f"━━━━━━━━━━━━━━━━━━\n"
                                            f"🎯 **Estratégia:** `{strategy_name}`\n"
                                            f"🎫 **Ticket:** `{ticket}`\n"
                                            f"{result_color} **Resultado:** `${final_profit:+.2f}`\n"
                                            f"⏱️ **Duração:** `{duration_minutes:.1f} min`\n"
                                            f"📊 **Confiança:** `{trade_data['signal_confidence']*100:.0f}%`\n"
                                            f"━━━━━━━━━━━━━━━━━━"
                                        )
                                        logger.info(f"📱 Notificação enviada: {result_text} ${final_profit:+.2f}")
                                    except Exception as telegram_error:
                                        logger.error(f"❌ Erro ao enviar notificação Telegram: {telegram_error}")
                                    
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
        
        # Adicionar novas posições (FORA do loop de fechadas)
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
                
                # 🔥 FASE 1: Extrair SL/TP mental do comment
                # Formato ULTRA compacto: "S|4172.8|4096.7" (apenas SL|TP)
                # Formatos antigos: "U_TR|4172.8|4096.7" ou "URION_strategy|SL:xxxx|TP:yyyy"
                mental_sl = None
                mental_tp = None
                comment = position.get('comment', '')
                
                # Tentar formato ULTRA COMPACTO: "S|sl|tp"
                if comment.startswith('S|') and comment.count('|') >= 2:
                    try:
                        parts = comment.split('|')
                        if len(parts) >= 3:
                            mental_sl = float(parts[1])
                            mental_tp = float(parts[2])
                            logger.info(f"🛡️  SL/TP mental extraído: SL={mental_sl}, TP={mental_tp}")
                    except Exception as parse_error:
                        logger.warning(f"Erro ao extrair SL/TP mental (ultra-compacto): {parse_error}")
                
                # Fallback 1: Formato compacto "U_XX|sl|tp"
                elif comment.startswith('U_') and comment.count('|') >= 2:
                    try:
                        parts = comment.split('|')
                        if len(parts) >= 3:
                            mental_sl = float(parts[1])
                            mental_tp = float(parts[2])
                            logger.info(f"🛡️  SL/TP mental extraído (compacto): SL={mental_sl}, TP={mental_tp}")
                    except Exception as parse_error:
                        logger.warning(f"Erro ao extrair SL/TP mental (compacto): {parse_error}")
                
                # Fallback 2: Formato antigo "URION_strategy|SL:xxxx|TP:yyyy"
                elif '|SL:' in comment and '|TP:' in comment:
                    try:
                        parts = comment.split('|')
                        for part in parts:
                            if part.startswith('SL:'):
                                mental_sl = float(part.replace('SL:', ''))
                            elif part.startswith('TP:'):
                                mental_tp = float(part.replace('TP:', ''))
                        logger.info(f"🛡️  SL/TP mental extraído (antigo): SL={mental_sl}, TP={mental_tp}")
                    except Exception as parse_error:
                        logger.warning(f"Erro ao extrair SL/TP mental (antigo): {parse_error}")
                
                self.monitored_positions[ticket] = {
                    'ticket': ticket,
                    'type': position['type'],
                    'volume': position['volume'],
                    'volume_inicial': position['volume'],  # 🚨 NOVO: rastrear volume inicial
                    'price_open': position['price_open'],
                    'sl': position['sl'],
                    'tp': position['tp'],
                    'mental_sl': mental_sl,  # 🔥 FASE 1: SL mental para gerenciamento
                    'mental_tp': mental_tp,  # 🔥 FASE 1: TP mental para gerenciamento
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
        
        # Breakeven trigger como % do TP (específico da estratégia)
        breakeven_at = strategy_config.get('breakeven_at', 0.3)  # 30% do TP
        
        # Calcular lucro atual e TP total
        entry_price = position['price_open']
        current_price = position['price_current']
        tp_price = position['tp']
        current_sl = position['sl']
        position_type = position['type']
        
        if position_type == 'BUY':
            profit_distance = current_price - entry_price
            total_tp_distance = tp_price - entry_price if tp_price > 0 else 100 * 0.0001
            tp_percentage = profit_distance / total_tp_distance if total_tp_distance > 0 else 0
            
            # Mover para break-even se atingiu % do TP e SL ainda abaixo da entrada
            if tp_percentage >= breakeven_at and current_sl < entry_price:
                new_sl = entry_price
                logger.info(
                    f"[{strategy_config.get('strategy_name')}] "
                    f"Movendo para BE: {tp_percentage*100:.0f}% do TP atingido"
                )
                return True, new_sl
        else:  # SELL
            profit_distance = entry_price - current_price
            total_tp_distance = entry_price - tp_price if tp_price > 0 else 100 * 0.0001
            tp_percentage = profit_distance / total_tp_distance if total_tp_distance > 0 else 0
            
            # Mover para break-even se atingiu % do TP e SL ainda acima da entrada
            if tp_percentage >= breakeven_at and (current_sl > entry_price or current_sl == 0):
                new_sl = entry_price
                logger.info(
                    f"[{strategy_config.get('strategy_name')}] "
                    f"Movendo para BE: {tp_percentage*100:.0f}% do TP atingido"
                )
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
        tp_price = position['tp']
        position_type = position['type']
        
        # 🔥 FIX: Usar TP mental se TP real for 0 (gerenciamento mental)
        if tp_price == 0:
            # Extrair TP mental do comment
            comment = position.get('comment', '')
            if comment.startswith('S|') and comment.count('|') >= 2:
                try:
                    parts = comment.split('|')
                    if len(parts) >= 3:
                        tp_price = float(parts[2])  # TP é o terceiro elemento
                        logger.debug(f"🛡️  Usando TP mental para cálculo parcial: {tp_price}")
                except (ValueError, IndexError):
                    pass
        
        if position_type == 'BUY':
            profit_pips = (price_current - price_open) * 10000
            total_tp_pips = (tp_price - price_open) * 10000 if tp_price > 0 else 100
        else:
            profit_pips = (price_open - price_current) * 10000
            total_tp_pips = (price_open - tp_price) * 10000 if tp_price > 0 else 100
        
        # Calcular % do TP atingido
        tp_percentage = profit_pips / total_tp_pips if total_tp_pips > 0 else 0
        
        # Verificar se atingiu trigger de fechamento parcial (específico da estratégia)
        partial_close_at = strategy_config.get('partial_close_at', 0.5)  # % do TP
        partial_close_volume = strategy_config.get('partial_close_volume', 0.5)  # % da posição
        
        # Só fecha parcial se atingiu X% do TP
        if tp_percentage >= partial_close_at:
            # Fechar porcentagem específica da posição
            volume_to_close = position['volume'] * partial_close_volume
            
            # Arredondar para 0.01 (mínimo MT5)
            volume_to_close = round(volume_to_close, 2)
            
            if volume_to_close >= 0.01:
                logger.info(
                    f"[{strategy_config.get('strategy_name')}] "
                    f"Fechamento parcial: {tp_percentage*100:.0f}% do TP | "
                    f"Fechando {partial_close_volume*100:.0f}% da posição"
                )
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
            
            # 🎯 NOVA LÓGICA: Usar Adaptive Spread Manager
            can_modify, reason = self.spread_manager.should_modify_position(spread_pips)
            
            if not can_modify:
                logger.warning(reason)
                return False
            
            # Log apenas se spread não for normal
            spread_level = self.spread_manager.classify_spread(spread_pips)
            if spread_level != 'normal':
                logger.info(reason)
            
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
        
        # 🔥 FIX: Se current_sl == 0, é primeira vez colocando SL (mental → real)
        # Permitir modificação independente da mudança de pips
        if current_sl == 0 or current_sl is None:
            logger.debug(
                f"Primeira aplicação de SL/TP real para #{ticket} "
                f"(current_sl={current_sl}) - permitindo modificação"
            )
            return True
        
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
    
    def _initialize_position_state(self, ticket: int, position: Dict, strategy_config: Dict):
        """
        Inicializa estado de gestão para uma nova posição
        
        Args:
            ticket: Ticket da posição
            position: Dados da posição
            strategy_config: Configuração da estratégia
        """
        if ticket not in self.position_states:
            # Calcular R (risco) baseado no SL
            entry_price = position['price_open']
            sl = position['sl']
            volume = position['volume']
            
            # Calcular risco em dólares (1R)
            risk_dollars = abs(entry_price - sl) * volume
            
            self.position_states[ticket] = {
                'stage': 0,  # 0 = Recém-aberta
                'max_profit': position['profit'],
                'max_rr': 0.0,  # Quantos R já alcançou
                'risk_1r': risk_dollars,  # Valor de 1R em dólares
                'entry_time': datetime.now(timezone.utc),
                'stage_history': ['ABERTA'],  # Histórico de estágios
            }
            
            self.position_performance[ticket] = {
                'max_profit': position['profit'],
                'max_drawdown': 0.0,
                'entry_time': datetime.now(timezone.utc),
                'entry_price': entry_price,
            }
            
            logger.debug(f"[{strategy_config['strategy_name']}] Estado inicializado para #{ticket} | 1R = ${risk_dollars:.2f}")
    
    def _calculate_current_rr(self, ticket: int, current_profit: float) -> float:
        """
        Calcula quantos R (risco/recompensa) a posição já atingiu
        
        Args:
            ticket: Ticket da posição
            current_profit: Lucro atual em dólares
            
        Returns:
            Valor em R (ex.: 1.5R, 2.0R)
        """
        state = self.position_states.get(ticket)
        if not state or state['risk_1r'] == 0:
            return 0.0
        
        return current_profit / state['risk_1r']
    
    def _update_position_performance(self, ticket: int, position: Dict):
        """
        Atualiza métricas de performance da posição
        
        Args:
            ticket: Ticket da posição
            position: Dados atuais da posição
        """
        if ticket not in self.position_performance:
            return
        
        perf = self.position_performance[ticket]
        current_profit = position['profit']
        
        # Atualizar máximo lucro
        if current_profit > perf['max_profit']:
            perf['max_profit'] = current_profit
        
        # Atualizar máximo drawdown (retração do pico)
        if perf['max_profit'] > 0:
            current_drawdown = perf['max_profit'] - current_profit
            if current_drawdown > perf['max_drawdown']:
                perf['max_drawdown'] = current_drawdown
    
    def _is_action_already_applied(self, ticket: int, action_type: str) -> bool:
        """
        🚨 NOVO: Verifica se uma ação já foi aplicada para evitar reaplicação
        
        Verifica o histórico de stages para detectar se:
        - BREAKEVEN já foi aplicado
        - PARCIAL já foi fechada
        - TRAILING já foi ativado
        
        Args:
            ticket: Ticket da posição
            action_type: Tipo de ação ('BREAKEVEN', 'PARCIAL', 'TRAILING')
            
        Returns:
            True se já foi aplicado, False caso contrário
        """
        state = self.position_states.get(ticket)
        if not state:
            return False
        
        stage_history = state.get('stage_history', [])
        
        # Verificar no histórico de stages
        for entry in stage_history:
            if action_type in entry:
                logger.debug(f"#{ticket} {action_type} já foi aplicado: {entry}")
                return True
        
        return False
    
    def _verify_sl_not_already_at_breakeven(self, ticket: int, position: Dict) -> bool:
        """
        🚨 NOVO: Verifica se SL já está no breakeven antes de tentar mover
        
        Args:
            ticket: Ticket da posição
            position: Dados da posição
            
        Returns:
            True se SL JÁ está no BE (não precisa mover), False se pode mover
        """
        entry_price = position['price_open']
        current_sl = position['sl']
        
        # Tolerância de 5 pips para considerar "no breakeven"
        tolerance = 0.0001 * 5  # 5 pips para XAU
        
        if abs(current_sl - entry_price) < tolerance:
            logger.debug(f"#{ticket} SL já no BE ({current_sl:.5f} ≈ {entry_price:.5f})")
            return True
        
        return False
    
    def _should_allow_close(self, ticket: int, position: Dict, strategy_name: str) -> bool:
        """
        🚀 MELHORIA 1: Verifica se posição pode ser fechada
        
        Regra: Não fechar antes do tempo mínimo EXCETO se:
        - Prejuízo > 80% do stop loss (emergência)
        - Take profit atingido
        
        Args:
            ticket: Ticket da posição
            position: Dados da posição
            strategy_name: Nome da estratégia
            
        Returns:
            True se pode fechar
        """
        # Calcular idade da posição
        open_time = position.get('time')
        if not open_time:
            return True  # Sem dados, permitir
        
        # Garantir que ambos datetime tenham timezone
        now = datetime.now(timezone.utc)
        if open_time.tzinfo is None:
            # Se open_time não tem timezone, assumir UTC
            open_time = open_time.replace(tzinfo=timezone.utc)
        
        age_seconds = (now - open_time).total_seconds()
        age_minutes = age_seconds / 60
        
        # Tempo mínimo para esta estratégia
        min_duration = self.MIN_TRADE_DURATION.get(strategy_name, 5)
        
        # Se passou do tempo mínimo, pode fechar
        if age_minutes >= min_duration:
            return True
        
        # Ainda não passou do tempo mínimo
        current_profit = position.get('profit', 0)
        sl_price = position.get('sl', 0)
        entry_price = position.get('price_open', 0)
        
        if sl_price and entry_price:
            # Calcular distância do SL
            sl_distance = abs(entry_price - sl_price)
            
            # Se prejuízo > 80% do SL = EMERGÊNCIA, permitir fechar
            emergency_threshold = -0.8 * sl_distance * position.get('volume', 1) * 100
            
            if current_profit < emergency_threshold:
                logger.warning(
                    f"⚠️ #{ticket} [{strategy_name}] Fechamento EMERGENCIAL permitido "
                    f"(prejuízo {current_profit:.2f} > 80% SL)"
                )
                return True
        
        # Bloquear fechamento
        logger.info(
            f"🛑 #{ticket} [{strategy_name}] Bloqueado: Apenas {age_minutes:.1f}min "
            f"(mínimo {min_duration}min)"
        )
        return False
    
    def _should_allow_manage(self, ticket: int, position: Dict, strategy_name: str) -> bool:
        """
        🔥 FASE 1: Gerenciamento manual com SL mental antes do tempo mínimo
        
        Verifica se passou o tempo mínimo para ativar SL/TP real.
        Se não passou, gerencia manualmente com SL mental.
        
        Args:
            ticket: Ticket da posição
            position: Dados da posição
            strategy_name: Nome da estratégia
            
        Returns:
            True se pode usar gerenciamento normal (SL/TP reais)
            False se deve usar apenas SL mental
        """
        # Buscar dados monitored
        monitored = self.monitored_positions.get(ticket)
        if not monitored:
            return True  # Sem dados, permitir gerenciamento normal
        
        # Calcular idade da posição
        first_seen = monitored.get('first_seen')
        if not first_seen:
            return True
        
        now = datetime.now(timezone.utc)
        age_seconds = (now - first_seen).total_seconds()
        age_minutes = age_seconds / 60
        
        # Tempo mínimo para esta estratégia
        min_duration = self.MIN_TRADE_DURATION.get(strategy_name, 5)
        
        # Se passou do tempo mínimo, ativar gerenciamento normal
        if age_minutes >= min_duration:
            # Verificar se já colocamos o SL/TP real
            if not monitored.get('real_sl_set', False):
                mental_sl = monitored.get('mental_sl')
                mental_tp = monitored.get('mental_tp')
                
                if mental_sl and mental_tp:
                    # 🔍 DEBUG: Log valores antes de enviar ao MT5
                    current_price = position.get('price_current', 0)
                    position_type = position.get('type')
                    spread_pips = position.get('spread', 0)
                    
                    # 🎯 ADAPTAÇÃO DE SPREAD: Ajustar SL/TP se spread estiver alto
                    adapted = self.spread_manager.get_adapted_parameters(
                        strategy_name=strategy_name,
                        spread_pips=spread_pips,
                        original_sl=mental_sl,
                        original_tp=mental_tp,
                        entry_price=monitored.get('entry_price', current_price),
                        position_type=position_type,
                        confidence=1.0  # Já passou do tempo mínimo
                    )
                    
                    # Usar valores adaptados se spread não for normal
                    final_sl = adapted['adapted_sl']
                    final_tp = adapted['adapted_tp']
                    
                    # Modificar posição para adicionar SL/TP
                    modify_result = self.modify_position(ticket, final_sl, final_tp)
                    
                    if modify_result:
                        monitored['real_sl_set'] = True
                        monitored['sl'] = final_sl
                        monitored['tp'] = final_tp
                        
                        # Log de sucesso com adaptação de spread (se houver)
                        if adapted['spread_level'] != 'normal':
                            logger.success(
                                f"✅ #{ticket} [{strategy_name}] SL/TP real ativado (idade: {age_minutes:.1f}min) | "
                                f"SL: {final_sl:.2f} | TP: {final_tp:.2f} | "
                                f"Spread: {adapted['spread_level'].upper()}"
                            )
                        else:
                            logger.success(
                                f"✅ #{ticket} [{strategy_name}] SL/TP real ativado (idade: {age_minutes:.1f}min) | "
                                f"SL: {final_sl:.2f} | TP: {final_tp:.2f}"
                            )
                    # Não logar erro se modify_position retornou False por intervalo/spread
                    # modify_position já loga internamente os motivos
            
            return True  # Permitir gerenciamento normal
        
        # Ainda não passou do tempo mínimo - gerenciar com SL mental
        mental_sl = monitored.get('mental_sl')
        current_price = position.get('price_current', 0)
        current_profit = position.get('profit', 0)
        position_type = position.get('type')  # 0=BUY, 1=SELL
        
        # 🔥 FIX: Validar position_type ANTES de verificar SL
        if position_type not in [0, 1]:
            logger.error(
                f"❌ #{ticket} [{strategy_name}] position_type INVÁLIDO: {position_type} "
                f"(esperado 0=BUY ou 1=SELL)"
            )
            return False  # Não gerenciar posição inválida
        
        if mental_sl and current_price:
            # Verificar se atingiu o SL mental
            sl_hit = False
            if position_type == 0:  # BUY
                sl_hit = current_price <= mental_sl
            elif position_type == 1:  # SELL
                sl_hit = current_price >= mental_sl
            
            if sl_hit:
                logger.warning(
                    f"⚠️ #{ticket} [{strategy_name}] SL MENTAL atingido! "
                    f"Preço: {current_price} | SL mental: {mental_sl} | "
                    f"Idade: {age_minutes:.1f}min (mínimo {min_duration}min)"
                )
                
                # Fechar posição (emergência - SL atingido)
                if self.close_position(ticket):
                    logger.warning(
                        f"🚨 #{ticket} Fechado por SL mental | "
                        f"Prejuízo: ${current_profit:.2f}"
                    )
                
                return False  # Não continuar gerenciamento
        
        # Apenas monitorar, não aplicar trailing/breakeven ainda
        logger.debug(
            f"🛡️  #{ticket} [{strategy_name}] Proteção mental ativa | "
            f"Idade: {age_minutes:.1f}min/{min_duration}min | "
            f"Profit: ${current_profit:.2f}"
        )
        
        return False  # Bloquear gerenciamento normal
    
    def _verify_macro_before_close(self, ticket: int, position: Dict) -> bool:
        """
        🚀 MELHORIA 4: Verifica macro context antes de fechar
        
        Se macro mudou A FAVOR da posição, cancela fechamento
        
        Args:
            ticket: Ticket da posição  
            position: Dados da posição
            
        Returns:
            True se pode fechar (macro neutro ou contra)
            False se deve manter aberta (macro virou a favor)
        """
        if not self.macro_analyzer:
            return True  # Sem macro analyzer, permitir
        
        try:
            macro = self.macro_analyzer.analyze()
            if not macro:
                return True  # Sem dados macro, permitir
            
            position_type = position.get('type')
            
            # BUY: verificar se macro virou BULLISH
            if position_type == 0:  # BUY
                if macro.gold_bias == "BULLISH" and macro.confidence >= 0.6:
                    logger.warning(
                        f"🛑 #{ticket} Cancelando fechamento: "
                        f"Macro virou BULLISH ({macro.confidence*100:.0f}%)"
                    )
                    return False
            
            # SELL: verificar se macro virou BEARISH
            elif position_type == 1:  # SELL
                if macro.gold_bias == "BEARISH" and macro.confidence >= 0.6:
                    logger.warning(
                        f"🛑 #{ticket} Cancelando fechamento: "
                        f"Macro virou BEARISH ({macro.confidence*100:.0f}%)"
                    )
                    return False
            
            return True
            
        except Exception as e:
            logger.debug(f"Erro ao verificar macro: {e}")
            return True  # Em caso de erro, permitir
    
    def manage_position_with_stages(self, position: Dict):
        """
        🎯 GESTÃO INTELIGENTE POR ESTÁGIOS
        
        Gerencia posição baseado em estados progressivos:
        - Stage 0: ABERTA (aguardando atingir primeiro objetivo)
        - Stage 1: BREAKEVEN (SL movido para entry)
        - Stage 2: PARCIAL_FEITA (parte da posição realizada)
        - Stage 3: TRAILING_ATIVO (trailing stop gerenciando)
        - Stage 4: FINALIZANDO (próximo ao TP ou saída manual)
        
        Args:
            position: Dados da posição
        """
        ticket = position['ticket']
        magic_number = position.get('magic', 0)
        strategy_config = self.get_strategy_config(magic_number)
        strategy_name = strategy_config['strategy_name']
        
        
        # 🔥 DEBUG: Log magic number e estratégia identificada
        if strategy_name == 'unknown':
            logger.error(
                f"❌ #{ticket} magic_number {magic_number} NÃO MAPEADO! "
                f"Estratégias conhecidas: {list(self.strategy_map.keys())}"
            )
        
        # � FASE 1: Verificar tempo mínimo e gerenciar com SL mental
        if not self._should_allow_manage(ticket, position, strategy_name):
            # Posição muito nova, gerenciar apenas com SL mental
            return
        
        # Inicializar estado se necessário
        self._initialize_position_state(ticket, position, strategy_config)
        
        # Atualizar performance
        self._update_position_performance(ticket, position)
        
        # Obter estado atual
        state = self.position_states[ticket]
        current_stage = state['stage']
        current_profit = position['profit']
        current_rr = self._calculate_current_rr(ticket, current_profit)
        
        # Atualizar max RR alcançado
        if current_rr > state['max_rr']:
            state['max_rr'] = current_rr
            self._save_states()  # 💾 Salvar após atualização importante
        
        # 🎯 LÓGICA POR ESTRATÉGIA
        
        if strategy_name == 'trend_following':
            self._manage_trend_following_stages(ticket, position, state, current_rr, strategy_config)
        
        elif strategy_name == 'range_trading':
            self._manage_range_trading_stages(ticket, position, state, current_rr, strategy_config)
        
        elif strategy_name == 'scalping':
            self._manage_scalping_stages(ticket, position, state, current_rr, strategy_config)
        
        elif strategy_name == 'breakout':
            self._manage_breakout_stages(ticket, position, state, current_rr, strategy_config)
        
        elif strategy_name == 'mean_reversion':
            self._manage_mean_reversion_stages(ticket, position, state, current_rr, strategy_config)
        
        elif strategy_name == 'news_trading':
            self._manage_news_trading_stages(ticket, position, state, current_rr, strategy_config)
        
        else:
            # Estratégia desconhecida - usar gestão padrão
            self.manage_position(position)
    
    def _manage_trend_following_stages(self, ticket: int, position: Dict, state: Dict, current_rr: float, config: Dict):
        """
        Gestão específica para TREND_FOLLOWING
        
        Fluxo:
        - Em +1.0R: Move SL para breakeven
        - Em +1.5R: Fecha 50% da posição
        - Em +2.0R: Ativa trailing stop agressivo
        """
        stage = state['stage']
        
        # Stage 0 → 1: Breakeven em +1.0R
        if stage == 0 and current_rr >= 1.0:
            # 🚨 Verificar se já foi aplicado
            if self._is_action_already_applied(ticket, 'BREAKEVEN'):
                return
            if self._verify_sl_not_already_at_breakeven(ticket, position):
                state['stage'] = 1  # Atualizar stage mesmo que não modificou
                self._save_states()
                return
            
            entry_price = position['price_open']
            if self.modify_position(ticket, entry_price):
                state['stage'] = 1
                state['stage_history'].append('BREAKEVEN @ +1.0R')
                self._save_states()  # 💾 Salvar após mudança de stage
                logger.success(f"[trend_following] #{ticket} → BREAKEVEN | +1.0R alcançado")
                self.telegram.send_message_sync(
                    f"🔒 BREAKEVEN [trend_following]\n"
                    f"Ticket: {ticket}\n"
                    f"Profit: +{current_rr:.2f}R"
                )
        
        # Stage 1 → 2: Parcial em +1.5R
        elif stage == 1 and current_rr >= 1.5:
            # 🚨 Verificar se já foi aplicado
            if self._is_action_already_applied(ticket, 'PARCIAL'):
                return
            
            # 🚀 MELHORIA 4: Verificar macro antes de fechar parcial
            if not self._verify_macro_before_close(ticket, position):
                logger.info(f"#{ticket} Parcial CANCELADA: Macro favorável")
                return
            
            partial_volume = position['volume'] * 0.5  # 50%
            if self.close_position(ticket, partial_volume):
                state['stage'] = 2
                state['stage_history'].append('PARCIAL_50% @ +1.5R')
                self._save_states()  # 💾 Salvar após mudança de stage
                logger.success(f"[trend_following] #{ticket} → PARCIAL 50% | +1.5R alcançado")
                self.telegram.send_message_sync(
                    f"💰 PARCIAL 50% [trend_following]\n"
                    f"Ticket: {ticket}\n"
                    f"Profit: +{current_rr:.2f}R"
                )
        
        # Stage 2 → 3: Trailing em +2.0R
        elif stage == 2 and current_rr >= 2.0:
            # 🚨 Verificar se já foi aplicado
            if self._is_action_already_applied(ticket, 'TRAILING'):
                # Já está em trailing, continuar aplicando
                self._apply_trailing_stop(ticket, position, distance_pips=20)
                return
            
            state['stage'] = 3
            state['stage_history'].append('TRAILING @ +2.0R')
            self._save_states()  # 💾 Salvar após mudança de stage
            logger.success(f"[trend_following] #{ticket} → TRAILING ATIVO | +2.0R alcançado")
            
            # Calcular trailing stop (deixa correr)
            self._apply_trailing_stop(ticket, position, distance_pips=20)
        
        # Stage 3: Continuar trailing
        elif stage == 3:
            self._apply_trailing_stop(ticket, position, distance_pips=20)
    
    def _manage_range_trading_stages(self, ticket: int, position: Dict, state: Dict, current_rr: float, config: Dict):
        """
        Gestão específica para RANGE_TRADING
        
        Fluxo (mais conservador):
        - Em +0.7R: Fecha 30%
        - Em +1.0R: Move SL para breakeven
        - Em +1.5R: Encerra restante ou trailing curto
        """
        stage = state['stage']
        
        # Stage 0 → 1: Parcial em +0.7R
        if stage == 0 and current_rr >= 0.7:
            partial_volume = position['volume'] * 0.3  # 30%
            if self.close_position(ticket, partial_volume):
                state['stage'] = 1
                state['stage_history'].append('PARCIAL_30% @ +0.7R')
                logger.success(f"[range_trading] #{ticket} → PARCIAL 30% | +0.7R alcançado")
        
        # Stage 1 → 2: Breakeven em +1.0R
        elif stage == 1 and current_rr >= 1.0:
            entry_price = position['price_open']
            if self.modify_position(ticket, entry_price):
                state['stage'] = 2
                state['stage_history'].append('BREAKEVEN @ +1.0R')
                logger.success(f"[range_trading] #{ticket} → BREAKEVEN | +1.0R alcançado")
        
        # Stage 2 → 3: Encerrar em +1.5R
        elif stage == 2 and current_rr >= 1.5:
            if self.close_position(ticket):
                state['stage'] = 4
                state['stage_history'].append('ENCERRADO @ +1.5R')
                logger.success(f"[range_trading] #{ticket} → ENCERRADO | +1.5R alcançado")
    
    def _manage_scalping_stages(self, ticket: int, position: Dict, state: Dict, current_rr: float, config: Dict):
        """
        Gestão específica para SCALPING (muito agressivo)
        
        Fluxo:
        - Em +0.5R: Breakeven
        - Em +0.8R: Parcial 50%
        - Em +1.2R: Encerrar tudo
        """
        stage = state['stage']
        
        # Stage 0 → 1: Breakeven rápido em +0.5R
        if stage == 0 and current_rr >= 0.5:
            entry_price = position['price_open']
            if self.modify_position(ticket, entry_price):
                state['stage'] = 1
                state['stage_history'].append('BREAKEVEN @ +0.5R')
                logger.success(f"[scalping] #{ticket} → BREAKEVEN | +0.5R alcançado")
        
        # Stage 1 → 2: Parcial em +0.8R
        elif stage == 1 and current_rr >= 0.8:
            partial_volume = position['volume'] * 0.5
            if self.close_position(ticket, partial_volume):
                state['stage'] = 2
                state['stage_history'].append('PARCIAL_50% @ +0.8R')
                logger.success(f"[scalping] #{ticket} → PARCIAL 50% | +0.8R alcançado")
        
        # Stage 2 → 4: Encerrar em +1.2R
        elif stage == 2 and current_rr >= 1.2:
            if self.close_position(ticket):
                state['stage'] = 4
                state['stage_history'].append('ENCERRADO @ +1.2R')
                logger.success(f"[scalping] #{ticket} → ENCERRADO | +1.2R alcançado")
    
    def _manage_breakout_stages(self, ticket: int, position: Dict, state: Dict, current_rr: float, config: Dict):
        """Gestão para BREAKOUT - similar a trend mas mais agressivo no início"""
        stage = state['stage']
        
        if stage == 0 and current_rr >= 0.8:
            entry_price = position['price_open']
            if self.modify_position(ticket, entry_price):
                state['stage'] = 1
                state['stage_history'].append('BREAKEVEN @ +0.8R')
                logger.success(f"[breakout] #{ticket} → BREAKEVEN | +0.8R alcançado")
        
        elif stage == 1 and current_rr >= 1.3:
            partial_volume = position['volume'] * 0.4
            if self.close_position(ticket, partial_volume):
                state['stage'] = 2
                state['stage_history'].append('PARCIAL_40% @ +1.3R')
                logger.success(f"[breakout] #{ticket} → PARCIAL 40% | +1.3R alcançado")
        
        elif stage == 2 and current_rr >= 2.0:
            state['stage'] = 3
            state['stage_history'].append('TRAILING @ +2.0R')
            self._apply_trailing_stop(ticket, position, distance_pips=15)
        
        elif stage == 3:
            self._apply_trailing_stop(ticket, position, distance_pips=15)
    
    def _manage_mean_reversion_stages(self, ticket: int, position: Dict, state: Dict, current_rr: float, config: Dict):
        """Gestão para MEAN_REVERSION - realiza lucro rapidamente"""
        stage = state['stage']
        
        if stage == 0 and current_rr >= 0.4:
            partial_volume = position['volume'] * 0.6
            if self.close_position(ticket, partial_volume):
                state['stage'] = 1
                state['stage_history'].append('PARCIAL_60% @ +0.4R')
                logger.success(f"[mean_reversion] #{ticket} → PARCIAL 60% | +0.4R alcançado")
        
        elif stage == 1 and current_rr >= 0.7:
            if self.close_position(ticket):
                state['stage'] = 4
                state['stage_history'].append('ENCERRADO @ +0.7R')
                logger.success(f"[mean_reversion] #{ticket} → ENCERRADO | +0.7R alcançado")
    
    def _manage_news_trading_stages(self, ticket: int, position: Dict, state: Dict, current_rr: float, config: Dict):
        """Gestão para NEWS_TRADING - volátil, realiza rápido"""
        stage = state['stage']
        
        if stage == 0 and current_rr >= 0.6:
            entry_price = position['price_open']
            if self.modify_position(ticket, entry_price):
                state['stage'] = 1
                state['stage_history'].append('BREAKEVEN @ +0.6R')
                logger.success(f"[news_trading] #{ticket} → BREAKEVEN | +0.6R alcançado")
        
        elif stage == 1 and current_rr >= 1.0:
            partial_volume = position['volume'] * 0.5
            if self.close_position(ticket, partial_volume):
                state['stage'] = 2
                state['stage_history'].append('PARCIAL_50% @ +1.0R')
                logger.success(f"[news_trading] #{ticket} → PARCIAL 50% | +1.0R alcançado")
        
        elif stage == 2 and current_rr >= 1.5:
            if self.close_position(ticket):
                state['stage'] = 4
                state['stage_history'].append('ENCERRADO @ +1.5R')
                logger.success(f"[news_trading] #{ticket} → ENCERRADO | +1.5R alcançado")
    
    def _apply_trailing_stop(self, ticket: int, position: Dict, distance_pips: int):
        """
        Aplica trailing stop com distância específica
        
        Args:
            ticket: Ticket da posição
            position: Dados da posição
            distance_pips: Distância em pips do preço atual
        """
        current_price = position['price_current']
        position_type = position['type']
        current_sl = position['sl']
        
        # Calcular novo SL
        pip_value = 0.01  # Para XAUUSD
        
        if position_type == 'BUY':
            new_sl = current_price - (distance_pips * pip_value)
            if new_sl > current_sl:  # Só move se melhorar
                self.modify_position(ticket, new_sl)
        else:  # SELL
            new_sl = current_price + (distance_pips * pip_value)
            if new_sl < current_sl:  # Só move se melhorar
                self.modify_position(ticket, new_sl)
    
    def manage_position(self, position: Dict):
        """
        Gerencia uma posição individual (MÉTODO LEGADO - mantido para compatibilidade)
        
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
        # 🚨 VERIFICAR SE POSIÇÃO AINDA EXISTE ANTES DE TENTAR FECHAR
        current_positions = self.get_open_positions()
        position_exists = any(p['ticket'] == ticket for p in current_positions)
        
        if not position_exists:
            logger.debug(f"Posição {ticket} não está mais aberta, pulando fechamento parcial")
            return  # Sair da função - posição já fechada
        
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
            logger.debug("OrderManager desabilitado no config")
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
        logger.debug("🔍 Atualizando lista de posições monitoradas...")
        self.update_monitored_positions()
        
        logger.debug(f"📊 Posições monitoradas: {len(self.monitored_positions)}")
        
        if not self.monitored_positions:
            logger.debug("⚠️  Nenhuma posição para monitorar")
            return  # Nenhuma posição para monitorar
        
        # Obter posições atuais
        logger.debug("🔍 Obtendo posições atuais do MT5...")
        current_positions = self.get_open_positions()
        logger.debug(f"📊 Posições atuais no MT5: {len(current_positions)}")
        
        # Gerenciar cada posição COM SISTEMA DE ESTADOS
        for position in current_positions:
            try:
                self.manage_position_with_stages(position)  # 🎯 NOVO SISTEMA DE GESTÃO
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
