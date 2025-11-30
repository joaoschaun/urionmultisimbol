"""
Correlation Manager
Gerencia correlação entre pares de moedas para evitar overexposure

Correlações importantes:
- EURUSD / GBPUSD: Alta correlação positiva (~0.85)
- EURUSD / USDCHF: Alta correlação negativa (~-0.90)
- EURUSD / USDJPY: Correlação moderada variável
- XAUUSD / USD Index: Alta correlação negativa (~-0.80)
"""
import MetaTrader5 as mt5
import numpy as np
from typing import Dict, Optional, Any, List, Tuple
from datetime import datetime, timedelta
from loguru import logger
from dataclasses import dataclass


@dataclass
class CorrelationPair:
    """Par de correlação"""
    symbol1: str
    symbol2: str
    correlation: float
    period: int
    strength: str  # "strong_positive", "moderate_positive", "weak", "moderate_negative", "strong_negative"


class CorrelationManager:
    """
    Gerenciador de Correlação entre Símbolos
    
    Evita overexposure verificando:
    - Correlação entre pares abertos
    - Exposição total ao USD
    - Posições conflitantes
    """
    
    # Correlações conhecidas (atualizadas dinamicamente)
    KNOWN_CORRELATIONS = {
        ("EURUSD", "GBPUSD"): 0.85,     # Alta positiva
        ("EURUSD", "USDCHF"): -0.90,    # Alta negativa
        ("GBPUSD", "USDCHF"): -0.80,    # Alta negativa
        ("EURUSD", "USDJPY"): 0.30,     # Baixa positiva
        ("GBPUSD", "USDJPY"): 0.40,     # Moderada positiva
        ("XAUUSD", "EURUSD"): 0.60,     # Moderada positiva (ambos vs USD)
        ("XAUUSD", "USDJPY"): -0.40,    # Moderada negativa
    }
    
    # Exposição por moeda (positivo = compra, negativo = venda)
    CURRENCY_EXPOSURE = {
        "EURUSD": {"EUR": 1, "USD": -1},
        "GBPUSD": {"GBP": 1, "USD": -1},
        "USDJPY": {"USD": 1, "JPY": -1},
        "USDCHF": {"USD": 1, "CHF": -1},
        "XAUUSD": {"XAU": 1, "USD": -1},
        "AUDUSD": {"AUD": 1, "USD": -1},
        "NZDUSD": {"NZD": 1, "USD": -1},
        "USDCAD": {"USD": 1, "CAD": -1},
    }
    
    def __init__(self, mt5_connector, config: Optional[Dict] = None):
        """
        Inicializa o gerenciador de correlação
        
        Args:
            mt5_connector: Instância do MT5Connector
            config: Configuração opcional
        """
        self.mt5 = mt5_connector
        self.config = config or {}
        
        # Configurações
        corr_config = self.config.get('correlation', {})
        self.correlation_period = corr_config.get('period', 100)  # Barras para calcular
        self.high_correlation_threshold = corr_config.get('high_threshold', 0.70)
        self.max_correlated_positions = corr_config.get('max_correlated', 2)
        self.max_currency_exposure = corr_config.get('max_exposure', 3.0)  # Em lotes
        
        # Cache de correlações
        self._correlation_cache: Dict[str, Tuple[float, datetime]] = {}
        self._cache_duration = timedelta(hours=1)
        
        logger.info(
            f"🔗 Correlation Manager inicializado | "
            f"Threshold: {self.high_correlation_threshold} | "
            f"Max correlated: {self.max_correlated_positions}"
        )
    
    def calculate_correlation(
        self,
        symbol1: str,
        symbol2: str,
        timeframe: int = mt5.TIMEFRAME_H1,
        period: Optional[int] = None
    ) -> float:
        """
        Calcula correlação de Pearson entre dois símbolos
        
        Args:
            symbol1: Primeiro símbolo
            symbol2: Segundo símbolo
            timeframe: Timeframe para cálculo
            period: Número de barras (usa default se None)
            
        Returns:
            Correlação (-1 a 1)
        """
        try:
            period = period or self.correlation_period
            
            # Verificar cache
            cache_key = f"{symbol1}_{symbol2}_{timeframe}_{period}"
            cache_key_reverse = f"{symbol2}_{symbol1}_{timeframe}_{period}"
            
            if cache_key in self._correlation_cache:
                corr, cached_time = self._correlation_cache[cache_key]
                if datetime.now() - cached_time < self._cache_duration:
                    return corr
            
            if cache_key_reverse in self._correlation_cache:
                corr, cached_time = self._correlation_cache[cache_key_reverse]
                if datetime.now() - cached_time < self._cache_duration:
                    return corr
            
            # Obter dados
            rates1 = mt5.copy_rates_from_pos(symbol1, timeframe, 0, period + 10)
            rates2 = mt5.copy_rates_from_pos(symbol2, timeframe, 0, period + 10)
            
            if rates1 is None or rates2 is None:
                # Usar correlação conhecida como fallback
                return self._get_known_correlation(symbol1, symbol2)
            
            if len(rates1) < period or len(rates2) < period:
                return self._get_known_correlation(symbol1, symbol2)
            
            # Extrair closes
            closes1 = np.array([r['close'] for r in rates1[-period:]])
            closes2 = np.array([r['close'] for r in rates2[-period:]])
            
            # Calcular retornos
            returns1 = np.diff(closes1) / closes1[:-1]
            returns2 = np.diff(closes2) / closes2[:-1]
            
            # Correlação de Pearson
            correlation = np.corrcoef(returns1, returns2)[0, 1]
            
            # Atualizar cache
            self._correlation_cache[cache_key] = (correlation, datetime.now())
            
            return correlation
            
        except Exception as e:
            logger.error(f"Erro ao calcular correlação: {e}")
            return self._get_known_correlation(symbol1, symbol2)
    
    def _get_known_correlation(self, symbol1: str, symbol2: str) -> float:
        """Retorna correlação conhecida ou 0"""
        key = (symbol1, symbol2)
        key_reverse = (symbol2, symbol1)
        
        if key in self.KNOWN_CORRELATIONS:
            return self.KNOWN_CORRELATIONS[key]
        if key_reverse in self.KNOWN_CORRELATIONS:
            return self.KNOWN_CORRELATIONS[key_reverse]
        
        return 0.0
    
    def get_correlation_strength(self, correlation: float) -> str:
        """Classifica força da correlação"""
        abs_corr = abs(correlation)
        
        if abs_corr >= 0.8:
            prefix = "strong"
        elif abs_corr >= 0.5:
            prefix = "moderate"
        else:
            return "weak"
        
        suffix = "positive" if correlation > 0 else "negative"
        return f"{prefix}_{suffix}"
    
    def get_currency_exposure(
        self,
        open_positions: List[Dict]
    ) -> Dict[str, float]:
        """
        Calcula exposição total por moeda
        
        Args:
            open_positions: Lista de posições abertas
            
        Returns:
            Dict com exposição por moeda (em lotes)
        """
        exposure = {}
        
        for pos in open_positions:
            symbol = pos.get('symbol', '')
            volume = pos.get('volume', 0)
            pos_type = pos.get('type', 0)  # 0=BUY, 1=SELL
            
            if symbol not in self.CURRENCY_EXPOSURE:
                continue
            
            currency_map = self.CURRENCY_EXPOSURE[symbol]
            
            # Inverter se SELL
            multiplier = 1 if pos_type == 0 else -1
            
            for currency, factor in currency_map.items():
                if currency not in exposure:
                    exposure[currency] = 0
                exposure[currency] += volume * factor * multiplier
        
        return exposure
    
    def check_correlation_conflict(
        self,
        new_symbol: str,
        new_type: str,  # 'BUY' ou 'SELL'
        open_positions: List[Dict]
    ) -> Dict[str, Any]:
        """
        Verifica se nova posição conflita com posições existentes
        
        Args:
            new_symbol: Símbolo da nova posição
            new_type: 'BUY' ou 'SELL'
            open_positions: Posições abertas
            
        Returns:
            Dict com 'allowed', 'reason', 'conflicts'
        """
        try:
            conflicts = []
            correlated_count = 0
            
            for pos in open_positions:
                pos_symbol = pos.get('symbol', '')
                pos_type_str = 'BUY' if pos.get('type', 0) == 0 else 'SELL'
                
                if pos_symbol == new_symbol:
                    continue
                
                # Calcular correlação
                correlation = self.calculate_correlation(new_symbol, pos_symbol)
                strength = self.get_correlation_strength(correlation)
                
                if abs(correlation) >= self.high_correlation_threshold:
                    correlated_count += 1
                    
                    # Verificar conflito
                    # Alta correlação positiva + mesma direção = overexposure
                    # Alta correlação negativa + direções opostas = overexposure
                    
                    same_direction = new_type == pos_type_str
                    
                    if correlation > 0 and same_direction:
                        conflicts.append({
                            "symbol": pos_symbol,
                            "correlation": round(correlation, 2),
                            "type": "same_direction_positive",
                            "message": f"{new_symbol} e {pos_symbol} são altamente correlacionados ({correlation:.2f}) e você está operando na mesma direção",
                        })
                    
                    elif correlation < 0 and not same_direction:
                        conflicts.append({
                            "symbol": pos_symbol,
                            "correlation": round(correlation, 2),
                            "type": "opposite_direction_negative",
                            "message": f"{new_symbol} e {pos_symbol} são negativamente correlacionados ({correlation:.2f}) e você está operando em direções opostas (equivalente a dobrar a posição)",
                        })
            
            # Verificar limite de posições correlacionadas
            if correlated_count >= self.max_correlated_positions:
                return {
                    "allowed": False,
                    "reason": f"Limite de {self.max_correlated_positions} posições correlacionadas atingido",
                    "conflicts": conflicts,
                    "correlated_count": correlated_count,
                }
            
            # Verificar conflitos graves
            if len([c for c in conflicts if c["correlation"] >= 0.8 or c["correlation"] <= -0.8]) > 0:
                return {
                    "allowed": False,
                    "reason": "Conflito de correlação muito alta detectado",
                    "conflicts": conflicts,
                    "correlated_count": correlated_count,
                }
            
            # Avisar sobre conflitos moderados mas permitir
            if conflicts:
                return {
                    "allowed": True,
                    "reason": "Correlação moderada detectada (permitido com cautela)",
                    "conflicts": conflicts,
                    "correlated_count": correlated_count,
                    "warning": True,
                }
            
            return {
                "allowed": True,
                "reason": "Sem conflitos de correlação",
                "conflicts": [],
                "correlated_count": correlated_count,
            }
            
        except Exception as e:
            logger.error(f"Erro ao verificar correlação: {e}")
            return {"allowed": True, "reason": f"Erro: {e}", "conflicts": []}
    
    def check_currency_exposure(
        self,
        new_symbol: str,
        new_type: str,
        new_volume: float,
        open_positions: List[Dict]
    ) -> Dict[str, Any]:
        """
        Verifica se nova posição excede limite de exposição por moeda
        
        Args:
            new_symbol: Símbolo da nova posição
            new_type: 'BUY' ou 'SELL'
            new_volume: Volume da nova posição
            open_positions: Posições abertas
            
        Returns:
            Dict com 'allowed', 'reason', 'exposure'
        """
        try:
            # Calcular exposição atual
            current_exposure = self.get_currency_exposure(open_positions)
            
            # Adicionar nova posição
            if new_symbol in self.CURRENCY_EXPOSURE:
                currency_map = self.CURRENCY_EXPOSURE[new_symbol]
                multiplier = 1 if new_type == 'BUY' else -1
                
                for currency, factor in currency_map.items():
                    if currency not in current_exposure:
                        current_exposure[currency] = 0
                    current_exposure[currency] += new_volume * factor * multiplier
            
            # Verificar limites
            violations = []
            for currency, exposure in current_exposure.items():
                if abs(exposure) > self.max_currency_exposure:
                    violations.append({
                        "currency": currency,
                        "exposure": round(exposure, 2),
                        "limit": self.max_currency_exposure,
                    })
            
            if violations:
                return {
                    "allowed": False,
                    "reason": f"Exposição máxima excedida para: {', '.join(v['currency'] for v in violations)}",
                    "exposure": current_exposure,
                    "violations": violations,
                }
            
            return {
                "allowed": True,
                "reason": "Exposição dentro dos limites",
                "exposure": current_exposure,
                "violations": [],
            }
            
        except Exception as e:
            logger.error(f"Erro ao verificar exposição: {e}")
            return {"allowed": True, "reason": f"Erro: {e}"}
    
    def can_open_position(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        open_positions: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Verifica se pode abrir nova posição considerando correlação e exposição
        
        Args:
            symbol: Símbolo
            order_type: 'BUY' ou 'SELL'
            volume: Volume
            open_positions: Posições abertas (busca automaticamente se None)
            
        Returns:
            Dict com 'allowed', 'reason', 'details'
        """
        try:
            # Buscar posições se não fornecidas
            if open_positions is None:
                open_positions = self.mt5.get_open_positions()
            
            # Verificar correlação
            corr_check = self.check_correlation_conflict(
                symbol, order_type, open_positions
            )
            
            if not corr_check["allowed"]:
                logger.warning(
                    f"🔗 Posição bloqueada por correlação: {symbol} {order_type} | "
                    f"{corr_check['reason']}"
                )
                return {
                    "allowed": False,
                    "reason": corr_check["reason"],
                    "type": "correlation",
                    "details": corr_check,
                }
            
            # Verificar exposição
            exp_check = self.check_currency_exposure(
                symbol, order_type, volume, open_positions
            )
            
            if not exp_check["allowed"]:
                logger.warning(
                    f"💰 Posição bloqueada por exposição: {symbol} {order_type} | "
                    f"{exp_check['reason']}"
                )
                return {
                    "allowed": False,
                    "reason": exp_check["reason"],
                    "type": "exposure",
                    "details": exp_check,
                }
            
            # Avisos
            if corr_check.get("warning"):
                logger.info(
                    f"⚠️ Aviso de correlação: {symbol} {order_type} | "
                    f"{len(corr_check['conflicts'])} conflitos moderados"
                )
            
            return {
                "allowed": True,
                "reason": "Todas as verificações passaram",
                "correlation_check": corr_check,
                "exposure_check": exp_check,
            }
            
        except Exception as e:
            logger.error(f"Erro ao verificar posição: {e}")
            return {"allowed": True, "reason": f"Erro na verificação: {e}"}
    
    def get_correlation_matrix(
        self,
        symbols: List[str],
        timeframe: int = mt5.TIMEFRAME_H1
    ) -> Dict[str, Dict[str, float]]:
        """
        Gera matriz de correlação para lista de símbolos
        
        Returns:
            Dict de dicts com correlações
        """
        matrix = {}
        
        for sym1 in symbols:
            matrix[sym1] = {}
            for sym2 in symbols:
                if sym1 == sym2:
                    matrix[sym1][sym2] = 1.0
                else:
                    matrix[sym1][sym2] = self.calculate_correlation(sym1, sym2, timeframe)
        
        return matrix
    
    def get_portfolio_summary(
        self,
        open_positions: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Retorna resumo do portfólio atual
        
        Returns:
            Dict com resumo de exposição e correlação
        """
        try:
            if open_positions is None:
                open_positions = self.mt5.get_open_positions()
            
            if not open_positions:
                return {
                    "positions": 0,
                    "exposure": {},
                    "correlations": [],
                    "risk_level": "low",
                }
            
            # Exposição por moeda
            exposure = self.get_currency_exposure(open_positions)
            
            # Correlações entre posições
            symbols = list(set(p.get('symbol') for p in open_positions))
            correlations = []
            
            for i, sym1 in enumerate(symbols):
                for sym2 in symbols[i+1:]:
                    corr = self.calculate_correlation(sym1, sym2)
                    if abs(corr) >= 0.5:
                        correlations.append({
                            "pair": f"{sym1}/{sym2}",
                            "correlation": round(corr, 2),
                            "strength": self.get_correlation_strength(corr),
                        })
            
            # Calcular nível de risco
            max_exposure = max(abs(e) for e in exposure.values()) if exposure else 0
            high_correlations = sum(1 for c in correlations if abs(c["correlation"]) >= 0.7)
            
            if max_exposure > self.max_currency_exposure * 0.8 or high_correlations >= 2:
                risk_level = "high"
            elif max_exposure > self.max_currency_exposure * 0.5 or high_correlations >= 1:
                risk_level = "medium"
            else:
                risk_level = "low"
            
            return {
                "positions": len(open_positions),
                "symbols": symbols,
                "exposure": {k: round(v, 2) for k, v in exposure.items()},
                "correlations": correlations,
                "risk_level": risk_level,
                "max_exposure": round(max_exposure, 2),
                "high_correlations": high_correlations,
            }
            
        except Exception as e:
            logger.error(f"Erro ao gerar resumo: {e}")
            return {"error": str(e)}


# Singleton
_correlation_manager: Optional[CorrelationManager] = None


def get_correlation_manager(
    mt5_connector,
    config: Optional[Dict] = None
) -> CorrelationManager:
    """Obtém instância singleton do Correlation Manager"""
    global _correlation_manager
    if _correlation_manager is None:
        _correlation_manager = CorrelationManager(mt5_connector, config)
    return _correlation_manager


# Exemplo de uso:
"""
from core.correlation_manager import get_correlation_manager

corr_mgr = get_correlation_manager(mt5_connector, config)

# Verificar antes de abrir posição
check = corr_mgr.can_open_position("GBPUSD", "BUY", 0.1)

if not check["allowed"]:
    logger.warning(f"Posição bloqueada: {check['reason']}")
    return

# Ver resumo do portfólio
summary = corr_mgr.get_portfolio_summary()
print(f"Nível de risco: {summary['risk_level']}")
print(f"Exposição USD: {summary['exposure'].get('USD', 0)} lotes")
"""
