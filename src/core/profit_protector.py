"""
Profit Protector - Sistema Inteligente de Proteção de Lucros
============================================================

🎯 OBJETIVO:
Garantir que trades lucrativos NÃO voltem para prejuízo.
Nunca devolver mais de X% do lucro máximo alcançado.

📐 REGRAS PRINCIPAIS:
1. Rastreia lucro máximo de cada posição
2. Calcula SL dinâmico para proteger % do lucro
3. Aperta SL progressivamente conforme lucro aumenta
4. Detecta recuo de lucro e age preventivamente

🔧 NÍVEIS DE PROTEÇÃO:
- Bronze: Lucro > 0.5R → Protege 50% do lucro
- Prata:  Lucro > 1.0R → Protege 60% do lucro
- Ouro:   Lucro > 1.5R → Protege 70% do lucro
- Platina: Lucro > 2.0R → Protege 80% do lucro
- Diamante: Lucro > 3.0R → Protege 90% do lucro

Autor: João Schaun / Claude
Versão: 1.0
Data: 01/12/2025
"""

from typing import Dict, Optional, Tuple, List
from datetime import datetime, timezone
from loguru import logger
from dataclasses import dataclass, field
from enum import Enum


class ProtectionLevel(Enum):
    """Níveis de proteção de lucro"""
    NONE = "none"
    BRONZE = "bronze"      # 50% proteção
    SILVER = "silver"      # 60% proteção
    GOLD = "gold"          # 70% proteção
    PLATINUM = "platinum"  # 80% proteção
    DIAMOND = "diamond"    # 90% proteção


@dataclass
class PositionProfit:
    """Rastreamento de lucro de uma posição"""
    ticket: int
    symbol: str
    entry_price: float
    current_price: float
    position_type: str  # 'BUY' ou 'SELL'
    volume: float
    
    # Rastreamento de lucro
    current_profit: float = 0.0
    max_profit: float = 0.0
    min_profit: float = 0.0
    
    # Rastreamento de R (risk-reward)
    initial_risk: float = 0.0  # Distância do entry ao SL original em $
    current_rr: float = 0.0
    max_rr: float = 0.0
    
    # Proteção aplicada
    protection_level: ProtectionLevel = ProtectionLevel.NONE
    protected_profit: float = 0.0  # Lucro mínimo garantido
    protected_sl: float = 0.0      # SL para garantir protected_profit
    
    # Timestamps
    first_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    max_profit_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_update: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Flags
    sl_tightened: bool = False
    profit_locked: bool = False


class ProfitProtector:
    """
    Sistema de Proteção de Lucros
    
    Monitora posições abertas e protege lucros conquistados.
    """
    
    def __init__(self, config: Dict = None):
        """
        Inicializa Profit Protector
        
        Args:
            config: Configurações do sistema
        """
        self.config = config or {}
        
        # Configurações de proteção
        protection_config = self.config.get('profit_protection', {})
        
        # Habilitado?
        self.enabled = protection_config.get('enabled', True)
        
        # Níveis de proteção (em múltiplos de R)
        self.levels = {
            ProtectionLevel.BRONZE: {
                'min_rr': protection_config.get('bronze_min_rr', 0.5),
                'protection_pct': protection_config.get('bronze_protection', 0.50)
            },
            ProtectionLevel.SILVER: {
                'min_rr': protection_config.get('silver_min_rr', 1.0),
                'protection_pct': protection_config.get('silver_protection', 0.60)
            },
            ProtectionLevel.GOLD: {
                'min_rr': protection_config.get('gold_min_rr', 1.5),
                'protection_pct': protection_config.get('gold_protection', 0.70)
            },
            ProtectionLevel.PLATINUM: {
                'min_rr': protection_config.get('platinum_min_rr', 2.0),
                'protection_pct': protection_config.get('platinum_protection', 0.80)
            },
            ProtectionLevel.DIAMOND: {
                'min_rr': protection_config.get('diamond_min_rr', 3.0),
                'protection_pct': protection_config.get('diamond_protection', 0.90)
            }
        }
        
        # Configurações de recuo
        self.drawdown_alert_pct = protection_config.get('drawdown_alert_pct', 0.20)  # Alerta em 20% de recuo
        self.drawdown_action_pct = protection_config.get('drawdown_action_pct', 0.30)  # Ação em 30% de recuo
        
        # Configurações de SL mínimo
        self.min_sl_distance_pips = protection_config.get('min_sl_distance_pips', 3.0)
        
        # Cache de posições
        self.positions: Dict[int, PositionProfit] = {}
        
        logger.info(
            f"🛡️ ProfitProtector inicializado | "
            f"Enabled: {self.enabled} | "
            f"Níveis: {len(self.levels)}"
        )
    
    def _get_pip_value(self, symbol: str) -> float:
        """Retorna valor do pip para o símbolo"""
        if 'JPY' in symbol:
            return 0.01
        elif 'XAU' in symbol:
            return 0.1  # Gold: 0.1 = 1 pip (10 pontos)
        else:
            return 0.0001
    
    def _calculate_sl_for_profit(self, position: PositionProfit, 
                                   target_profit: float) -> float:
        """
        Calcula o SL necessário para garantir um lucro mínimo
        
        Args:
            position: Dados da posição
            target_profit: Lucro mínimo a garantir ($)
            
        Returns:
            Preço do SL
        """
        pip = self._get_pip_value(position.symbol)
        
        # Calcular distância em pips necessária
        # profit = (price_diff) * volume * pip_value_per_lot
        # Para simplificar, assumimos que profit é linear com preço
        
        if position.volume <= 0:
            return position.entry_price
        
        # Profit atual por pip (aproximado)
        current_profit = position.current_profit
        current_price = position.current_price
        entry_price = position.entry_price
        
        if position.position_type == 'BUY':
            price_diff = current_price - entry_price
        else:
            price_diff = entry_price - current_price
        
        if abs(price_diff) < pip:
            # Muito perto do entry, usar cálculo padrão
            return position.entry_price
        
        # Profit por unidade de preço
        profit_per_price = current_profit / price_diff if price_diff != 0 else 0
        
        if profit_per_price <= 0:
            return position.entry_price
        
        # Distância necessária do entry para garantir target_profit
        required_distance = target_profit / profit_per_price
        
        # Calcular SL
        if position.position_type == 'BUY':
            # Para BUY, SL é abaixo do entry + required_distance
            new_sl = entry_price + required_distance
            
            # Garantir distância mínima do preço atual
            min_sl = current_price - (self.min_sl_distance_pips * pip)
            new_sl = min(new_sl, min_sl)
            
        else:  # SELL
            # Para SELL, SL é acima do entry - required_distance
            new_sl = entry_price - required_distance
            
            # Garantir distância mínima do preço atual
            min_sl = current_price + (self.min_sl_distance_pips * pip)
            new_sl = max(new_sl, min_sl)
        
        return new_sl
    
    def _determine_protection_level(self, current_rr: float) -> ProtectionLevel:
        """
        Determina nível de proteção baseado no RR atual
        
        Args:
            current_rr: Risk-reward ratio atual
            
        Returns:
            Nível de proteção apropriado
        """
        # Ordenar níveis por min_rr decrescente
        for level in [ProtectionLevel.DIAMOND, ProtectionLevel.PLATINUM, 
                      ProtectionLevel.GOLD, ProtectionLevel.SILVER, 
                      ProtectionLevel.BRONZE]:
            if current_rr >= self.levels[level]['min_rr']:
                return level
        
        return ProtectionLevel.NONE
    
    def update_position(self, ticket: int, position_data: Dict) -> PositionProfit:
        """
        Atualiza dados de uma posição
        
        Args:
            ticket: Ticket da posição
            position_data: Dados atuais da posição do MT5
            
        Returns:
            PositionProfit atualizado
        """
        now = datetime.now(timezone.utc)
        
        if ticket not in self.positions:
            # Nova posição
            pos = PositionProfit(
                ticket=ticket,
                symbol=position_data.get('symbol', ''),
                entry_price=position_data.get('price_open', 0),
                current_price=position_data.get('price_current', 0),
                position_type='BUY' if position_data.get('type') == 'BUY' else 'SELL',
                volume=position_data.get('volume', 0),
                current_profit=position_data.get('profit', 0),
                first_seen=now
            )
            
            # Calcular risco inicial (distância do entry ao SL em $)
            sl = position_data.get('sl', 0)
            if sl > 0:
                pip = self._get_pip_value(pos.symbol)
                sl_distance = abs(pos.entry_price - sl)
                sl_distance_pips = sl_distance / pip
                
                # Estimar valor do pip por lote (aproximado)
                # Para forex majors: ~$10 por pip por lote standard
                # Para Gold: ~$10 por pip por lote
                if 'XAU' in pos.symbol:
                    pip_value = 10.0  # $10 por 0.1 movimento
                elif 'JPY' in pos.symbol:
                    pip_value = 10.0 / 100  # Ajuste para JPY
                else:
                    pip_value = 10.0  # Forex majors
                
                pos.initial_risk = sl_distance_pips * pos.volume * pip_value
            else:
                # Sem SL definido, estimar baseado no profit atual ou padrão
                if pos.current_profit < 0:
                    pos.initial_risk = abs(pos.current_profit)
                else:
                    # Usar 1% da posição como risco padrão
                    pos.initial_risk = pos.current_profit if pos.current_profit > 0 else 50.0
            
            self.positions[ticket] = pos
            logger.debug(f"🛡️ Nova posição rastreada: #{ticket} | Risk: ${pos.initial_risk:.2f}")
        
        else:
            pos = self.positions[ticket]
        
        # Atualizar dados atuais
        pos.current_price = position_data.get('price_current', pos.current_price)
        pos.current_profit = position_data.get('profit', 0)
        pos.volume = position_data.get('volume', pos.volume)
        pos.last_update = now
        
        # Atualizar máximos/mínimos
        if pos.current_profit > pos.max_profit:
            pos.max_profit = pos.current_profit
            pos.max_profit_time = now
        
        if pos.current_profit < pos.min_profit:
            pos.min_profit = pos.current_profit
        
        # Calcular RR atual
        if pos.initial_risk > 0:
            pos.current_rr = pos.current_profit / pos.initial_risk
            if pos.current_rr > pos.max_rr:
                pos.max_rr = pos.current_rr
        
        return pos
    
    def analyze_position(self, ticket: int, position_data: Dict) -> Dict:
        """
        Analisa posição e retorna recomendação de proteção
        
        Args:
            ticket: Ticket da posição
            position_data: Dados atuais
            
        Returns:
            Dict com análise e recomendações
        """
        if not self.enabled:
            return {'action': 'NONE', 'reason': 'protection_disabled'}
        
        # Atualizar posição
        pos = self.update_position(ticket, position_data)
        
        # Resultado padrão
        result = {
            'action': 'HOLD',
            'reason': 'no_action_needed',
            'ticket': ticket,
            'current_profit': pos.current_profit,
            'max_profit': pos.max_profit,
            'current_rr': pos.current_rr,
            'max_rr': pos.max_rr,
            'protection_level': pos.protection_level.value,
            'new_sl': None,
            'protected_profit': pos.protected_profit
        }
        
        # Se não está em lucro, não proteger
        if pos.current_profit <= 0 or pos.max_profit <= 0:
            return result
        
        # Determinar nível de proteção
        new_level = self._determine_protection_level(pos.max_rr)
        
        # Se subiu de nível, atualizar proteção
        if new_level.value != ProtectionLevel.NONE.value:
            level_order = [ProtectionLevel.NONE, ProtectionLevel.BRONZE, 
                          ProtectionLevel.SILVER, ProtectionLevel.GOLD,
                          ProtectionLevel.PLATINUM, ProtectionLevel.DIAMOND]
            
            current_idx = level_order.index(pos.protection_level)
            new_idx = level_order.index(new_level)
            
            if new_idx > current_idx:
                # Subiu de nível!
                pos.protection_level = new_level
                protection_pct = self.levels[new_level]['protection_pct']
                pos.protected_profit = pos.max_profit * protection_pct
                
                # Calcular novo SL
                new_sl = self._calculate_sl_for_profit(pos, pos.protected_profit)
                pos.protected_sl = new_sl
                
                result['action'] = 'UPGRADE_PROTECTION'
                result['reason'] = f'level_up_to_{new_level.value}'
                result['new_sl'] = new_sl
                result['protection_level'] = new_level.value
                result['protected_profit'] = pos.protected_profit
                
                logger.info(
                    f"🛡️ #{ticket} UPGRADE → {new_level.value.upper()} | "
                    f"Protegendo ${pos.protected_profit:.2f} ({protection_pct*100:.0f}% de ${pos.max_profit:.2f})"
                )
                
                return result
        
        # Verificar recuo de lucro (drawdown do max)
        if pos.max_profit > 0:
            drawdown_pct = (pos.max_profit - pos.current_profit) / pos.max_profit
            
            # Alerta de recuo
            if drawdown_pct >= self.drawdown_alert_pct:
                result['drawdown_alert'] = True
                result['drawdown_pct'] = drawdown_pct
                
                logger.warning(
                    f"⚠️ #{ticket} Recuo de {drawdown_pct*100:.1f}% do lucro máximo! "
                    f"(${pos.max_profit:.2f} → ${pos.current_profit:.2f})"
                )
            
            # Ação de recuo (apertar SL)
            if drawdown_pct >= self.drawdown_action_pct and pos.protection_level != ProtectionLevel.NONE:
                # Apertar SL para proteger lucro atual
                # Proteger 80% do lucro ATUAL (não do máximo)
                emergency_protection = pos.current_profit * 0.8
                
                if emergency_protection > 0:
                    new_sl = self._calculate_sl_for_profit(pos, emergency_protection)
                    
                    # Só atualiza se for mais apertado
                    if pos.position_type == 'BUY':
                        if new_sl > pos.protected_sl:
                            pos.protected_sl = new_sl
                            result['action'] = 'TIGHTEN_SL'
                            result['reason'] = f'drawdown_{drawdown_pct*100:.0f}pct'
                            result['new_sl'] = new_sl
                            result['protected_profit'] = emergency_protection
                            
                            logger.warning(
                                f"🔒 #{ticket} SL APERTADO por recuo | "
                                f"Novo SL: {new_sl:.5f} | Protegendo: ${emergency_protection:.2f}"
                            )
                    else:  # SELL
                        if new_sl < pos.protected_sl or pos.protected_sl == 0:
                            pos.protected_sl = new_sl
                            result['action'] = 'TIGHTEN_SL'
                            result['reason'] = f'drawdown_{drawdown_pct*100:.0f}pct'
                            result['new_sl'] = new_sl
                            result['protected_profit'] = emergency_protection
                            
                            logger.warning(
                                f"🔒 #{ticket} SL APERTADO por recuo | "
                                f"Novo SL: {new_sl:.5f} | Protegendo: ${emergency_protection:.2f}"
                            )
        
        return result
    
    def should_tighten_sl(self, ticket: int, position_data: Dict) -> Tuple[bool, Optional[float], str]:
        """
        Verifica se deve apertar o SL
        
        Args:
            ticket: Ticket da posição
            position_data: Dados atuais
            
        Returns:
            (should_tighten, new_sl, reason)
        """
        analysis = self.analyze_position(ticket, position_data)
        
        if analysis['action'] in ['UPGRADE_PROTECTION', 'TIGHTEN_SL']:
            return True, analysis['new_sl'], analysis['reason']
        
        return False, None, 'no_action'
    
    def get_protection_status(self, ticket: int) -> Optional[Dict]:
        """
        Retorna status de proteção de uma posição
        
        Args:
            ticket: Ticket da posição
            
        Returns:
            Dict com status ou None
        """
        if ticket not in self.positions:
            return None
        
        pos = self.positions[ticket]
        
        return {
            'ticket': pos.ticket,
            'symbol': pos.symbol,
            'current_profit': pos.current_profit,
            'max_profit': pos.max_profit,
            'current_rr': round(pos.current_rr, 2),
            'max_rr': round(pos.max_rr, 2),
            'protection_level': pos.protection_level.value,
            'protected_profit': pos.protected_profit,
            'protected_sl': pos.protected_sl,
            'profit_locked': pos.profit_locked,
            'drawdown_from_max': round((pos.max_profit - pos.current_profit) / pos.max_profit * 100, 1) if pos.max_profit > 0 else 0
        }
    
    def remove_position(self, ticket: int):
        """Remove posição do rastreamento"""
        if ticket in self.positions:
            del self.positions[ticket]
            logger.debug(f"🛡️ Posição #{ticket} removida do ProfitProtector")
    
    def get_summary(self) -> Dict:
        """Retorna resumo de todas as posições protegidas"""
        total_protected = 0
        positions_by_level = {level.value: 0 for level in ProtectionLevel}
        
        for pos in self.positions.values():
            if pos.protection_level != ProtectionLevel.NONE:
                total_protected += pos.protected_profit
                positions_by_level[pos.protection_level.value] += 1
        
        return {
            'total_positions': len(self.positions),
            'total_protected_profit': total_protected,
            'positions_by_level': positions_by_level,
            'enabled': self.enabled
        }
