# -*- coding: utf-8 -*-
"""
Correlation Analyzer
====================
Análise de correlação entre múltiplos símbolos para diversificação
e gestão de risco de portfólio.

Funcionalidades:
- Matriz de correlação rolling
- Detecção de mudanças de regime
- Score de diversificação
- Alertas de correlação

Autor: Urion Trading Bot
Versão: 2.0
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from loguru import logger

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False


class CorrelationStrength(Enum):
    """Força da correlação"""
    VERY_STRONG_POSITIVE = "very_strong_positive"   # > 0.8
    STRONG_POSITIVE = "strong_positive"             # 0.6 to 0.8
    MODERATE_POSITIVE = "moderate_positive"         # 0.4 to 0.6
    WEAK_POSITIVE = "weak_positive"                 # 0.2 to 0.4
    NEGLIGIBLE = "negligible"                       # -0.2 to 0.2
    WEAK_NEGATIVE = "weak_negative"                 # -0.4 to -0.2
    MODERATE_NEGATIVE = "moderate_negative"         # -0.6 to -0.4
    STRONG_NEGATIVE = "strong_negative"             # -0.8 to -0.6
    VERY_STRONG_NEGATIVE = "very_strong_negative"   # < -0.8


@dataclass
class CorrelationPair:
    """Par de correlação entre dois símbolos"""
    symbol1: str
    symbol2: str
    correlation: float
    strength: CorrelationStrength
    p_value: float
    sample_size: int
    window_days: int
    last_updated: datetime


@dataclass
class CorrelationAlert:
    """Alerta de mudança de correlação"""
    symbol1: str
    symbol2: str
    old_correlation: float
    new_correlation: float
    change: float
    alert_type: str  # 'regime_change', 'breakdown', 'strengthening'
    timestamp: datetime


class CorrelationAnalyzer:
    """
    Analisador de correlação entre símbolos
    
    Uso:
    - Identificar símbolos altamente correlacionados para evitar concentração
    - Detectar mudanças de regime (correlação mudando)
    - Calcular score de diversificação do portfólio
    """
    
    # Símbolos padrão para análise
    DEFAULT_SYMBOLS = ['XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY']
    
    # Thresholds de correlação
    CORRELATION_THRESHOLDS = {
        'very_strong': 0.8,
        'strong': 0.6,
        'moderate': 0.4,
        'weak': 0.2
    }
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Inicializa o analisador
        
        Args:
            config: Configurações opcionais
        """
        self.config = config or {}
        
        # Símbolos a monitorar
        self.symbols = self.config.get('symbols', self.DEFAULT_SYMBOLS)
        
        # Configurações de janela
        self.rolling_windows = self.config.get(
            'rolling_windows', [20, 50, 100]
        )  # dias
        
        # Cache de dados
        self._price_cache: Dict[str, pd.DataFrame] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_timeout = timedelta(minutes=15)
        
        # Cache de correlações
        self._correlation_cache: Dict[int, pd.DataFrame] = {}
        
        # Histórico para detecção de mudanças
        self._correlation_history: Dict[str, List[float]] = {}
        
        # Alertas ativos
        self._active_alerts: List[CorrelationAlert] = []
        
        logger.info(
            f"CorrelationAnalyzer inicializado | "
            f"Símbolos: {self.symbols} | "
            f"Windows: {self.rolling_windows}"
        )
    
    def _get_symbol_strength(self, correlation: float) -> CorrelationStrength:
        """Classifica força da correlação"""
        if correlation > 0.8:
            return CorrelationStrength.VERY_STRONG_POSITIVE
        elif correlation > 0.6:
            return CorrelationStrength.STRONG_POSITIVE
        elif correlation > 0.4:
            return CorrelationStrength.MODERATE_POSITIVE
        elif correlation > 0.2:
            return CorrelationStrength.WEAK_POSITIVE
        elif correlation > -0.2:
            return CorrelationStrength.NEGLIGIBLE
        elif correlation > -0.4:
            return CorrelationStrength.WEAK_NEGATIVE
        elif correlation > -0.6:
            return CorrelationStrength.MODERATE_NEGATIVE
        elif correlation > -0.8:
            return CorrelationStrength.STRONG_NEGATIVE
        else:
            return CorrelationStrength.VERY_STRONG_NEGATIVE
    
    def fetch_prices(self, 
                     symbols: List[str] = None,
                     days: int = 100,
                     timeframe: int = None) -> Dict[str, pd.Series]:
        """
        Busca preços de fechamento dos símbolos
        
        Args:
            symbols: Lista de símbolos (usa default se None)
            days: Número de dias de histórico
            timeframe: Timeframe MT5 (default H1)
            
        Returns:
            Dict de symbol -> Series de preços
        """
        symbols = symbols or self.symbols
        
        if not MT5_AVAILABLE:
            logger.warning("MT5 não disponível, usando dados sintéticos")
            return self._generate_synthetic_prices(symbols, days)
        
        # Verificar cache
        if (self._cache_timestamp and 
            datetime.now() - self._cache_timestamp < self._cache_timeout):
            return self._price_cache
        
        timeframe = timeframe or mt5.TIMEFRAME_H1
        
        prices = {}
        
        for symbol in symbols:
            try:
                # Buscar dados do MT5
                rates = mt5.copy_rates_from_pos(
                    symbol, 
                    timeframe, 
                    0, 
                    days * 24  # Candles por dia
                )
                
                if rates is not None and len(rates) > 0:
                    df = pd.DataFrame(rates)
                    df['time'] = pd.to_datetime(df['time'], unit='s')
                    df.set_index('time', inplace=True)
                    
                    # Resample para diário
                    daily = df['close'].resample('D').last().dropna()
                    prices[symbol] = daily
                    
                    logger.debug(f"{symbol}: {len(daily)} dias de dados")
                else:
                    logger.warning(f"Sem dados para {symbol}")
                    
            except Exception as e:
                logger.error(f"Erro ao buscar {symbol}: {e}")
        
        if prices:
            self._price_cache = prices
            self._cache_timestamp = datetime.now()
        
        return prices
    
    def _generate_synthetic_prices(self, 
                                    symbols: List[str], 
                                    days: int) -> Dict[str, pd.Series]:
        """Gera preços sintéticos para testes"""
        np.random.seed(42)
        
        # Preços base
        base_prices = {
            'XAUUSD': 1900,
            'EURUSD': 1.10,
            'GBPUSD': 1.25,
            'USDJPY': 145
        }
        
        # Correlações aproximadas reais
        # Gold correlacionado negativamente com USD
        # EUR e GBP correlacionados positivamente
        
        dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
        prices = {}
        
        # Gerar fatores comuns
        market_factor = np.cumsum(np.random.normal(0, 0.01, days))
        usd_factor = np.cumsum(np.random.normal(0, 0.005, days))
        
        for symbol in symbols:
            base = base_prices.get(symbol, 100)
            
            if symbol == 'XAUUSD':
                # Gold: inverso do USD
                returns = -0.7 * usd_factor + 0.3 * np.random.normal(0, 0.01, days)
            elif symbol == 'EURUSD':
                # EUR: inverso do USD
                returns = -0.8 * usd_factor + 0.2 * np.random.normal(0, 0.01, days)
            elif symbol == 'GBPUSD':
                # GBP: correlacionado com EUR, inverso USD
                returns = -0.75 * usd_factor + 0.25 * np.random.normal(0, 0.01, days)
            elif symbol == 'USDJPY':
                # JPY: positivo com USD
                returns = 0.6 * usd_factor + 0.4 * np.random.normal(0, 0.01, days)
            else:
                returns = market_factor + np.random.normal(0, 0.01, days)
            
            price_series = base * (1 + returns)
            prices[symbol] = pd.Series(price_series, index=dates, name=symbol)
        
        return prices
    
    def calculate_correlation_matrix(self, 
                                      window: int = 50,
                                      symbols: List[str] = None) -> pd.DataFrame:
        """
        Calcula matriz de correlação
        
        Args:
            window: Janela em dias
            symbols: Lista de símbolos
            
        Returns:
            DataFrame com matriz de correlação
        """
        symbols = symbols or self.symbols
        prices = self.fetch_prices(symbols, days=window + 50)
        
        if not prices:
            logger.warning("Sem dados para calcular correlação")
            return pd.DataFrame()
        
        # Criar DataFrame com retornos
        returns_df = pd.DataFrame()
        
        for symbol, price_series in prices.items():
            # Calcular retornos logarítmicos
            returns = np.log(price_series / price_series.shift(1)).dropna()
            returns_df[symbol] = returns
        
        # Alinhar datas
        returns_df = returns_df.dropna()
        
        # Usar apenas últimos N dias
        returns_df = returns_df.tail(window)
        
        # Calcular correlação
        corr_matrix = returns_df.corr()
        
        # Atualizar cache
        self._correlation_cache[window] = corr_matrix
        
        logger.debug(f"Matriz de correlação calculada (window={window})")
        
        return corr_matrix
    
    def get_correlation_pairs(self, 
                               window: int = 50,
                               min_correlation: float = 0.0) -> List[CorrelationPair]:
        """
        Retorna pares de correlação ordenados
        
        Args:
            window: Janela em dias
            min_correlation: Correlação mínima (absoluta)
            
        Returns:
            Lista de CorrelationPair ordenada por força
        """
        corr_matrix = self.calculate_correlation_matrix(window)
        
        if corr_matrix.empty:
            return []
        
        pairs = []
        
        # Iterar sobre pares únicos (triangular superior)
        for i, symbol1 in enumerate(corr_matrix.columns):
            for j, symbol2 in enumerate(corr_matrix.columns):
                if j <= i:  # Evitar duplicatas e diagonal
                    continue
                
                correlation = corr_matrix.loc[symbol1, symbol2]
                
                if abs(correlation) >= min_correlation:
                    pairs.append(CorrelationPair(
                        symbol1=symbol1,
                        symbol2=symbol2,
                        correlation=float(correlation),
                        strength=self._get_symbol_strength(correlation),
                        p_value=0.0,  # Calcular se necessário
                        sample_size=window,
                        window_days=window,
                        last_updated=datetime.now()
                    ))
        
        # Ordenar por força absoluta
        pairs.sort(key=lambda x: abs(x.correlation), reverse=True)
        
        return pairs
    
    def get_diversification_score(self, 
                                   portfolio_symbols: List[str],
                                   window: int = 50) -> Dict:
        """
        Calcula score de diversificação do portfólio
        
        Score alto = boa diversificação (baixa correlação média)
        Score baixo = concentração (alta correlação)
        
        Args:
            portfolio_symbols: Símbolos no portfólio
            window: Janela em dias
            
        Returns:
            Dict com score e análise
        """
        if len(portfolio_symbols) < 2:
            return {
                'score': 1.0,
                'interpretation': 'single_asset',
                'message': 'Apenas um ativo, não há correlação para analisar'
            }
        
        corr_matrix = self.calculate_correlation_matrix(
            window, 
            symbols=portfolio_symbols
        )
        
        if corr_matrix.empty:
            return {'score': 0.5, 'interpretation': 'no_data'}
        
        # Calcular correlação média absoluta (excluindo diagonal)
        n = len(corr_matrix)
        total_corr = 0
        count = 0
        
        for i in range(n):
            for j in range(i + 1, n):
                total_corr += abs(corr_matrix.iloc[i, j])
                count += 1
        
        avg_correlation = total_corr / count if count > 0 else 0
        
        # Score de diversificação (inverso da correlação média)
        # 0 = perfeitamente correlacionado (ruim)
        # 1 = sem correlação (ótimo para diversificação)
        diversification_score = 1 - avg_correlation
        
        # Identificar pares problemáticos
        high_corr_pairs = []
        for i in range(n):
            for j in range(i + 1, n):
                corr = corr_matrix.iloc[i, j]
                if abs(corr) > 0.7:
                    high_corr_pairs.append({
                        'pair': f"{corr_matrix.index[i]}/{corr_matrix.columns[j]}",
                        'correlation': float(corr)
                    })
        
        # Interpretação
        if diversification_score >= 0.7:
            interpretation = 'excellent'
            message = 'Portfólio bem diversificado'
        elif diversification_score >= 0.5:
            interpretation = 'good'
            message = 'Diversificação adequada'
        elif diversification_score >= 0.3:
            interpretation = 'moderate'
            message = 'Alguma concentração de risco'
        else:
            interpretation = 'poor'
            message = 'Alta concentração! Considere diversificar'
        
        return {
            'score': round(diversification_score, 4),
            'interpretation': interpretation,
            'message': message,
            'avg_correlation': round(avg_correlation, 4),
            'high_correlation_pairs': high_corr_pairs,
            'portfolio_size': len(portfolio_symbols),
            'window_days': window
        }
    
    def detect_regime_change(self, 
                              symbol1: str, 
                              symbol2: str,
                              short_window: int = 20,
                              long_window: int = 100,
                              threshold: float = 0.3) -> Optional[CorrelationAlert]:
        """
        Detecta mudança de regime na correlação
        
        Compara correlação de curto prazo vs longo prazo
        
        Args:
            symbol1: Primeiro símbolo
            symbol2: Segundo símbolo
            short_window: Janela curta
            long_window: Janela longa
            threshold: Mudança mínima para alerta
            
        Returns:
            CorrelationAlert se mudança detectada, None caso contrário
        """
        # Calcular correlações
        corr_short = self.calculate_correlation_matrix(
            short_window, 
            symbols=[symbol1, symbol2]
        )
        
        corr_long = self.calculate_correlation_matrix(
            long_window, 
            symbols=[symbol1, symbol2]
        )
        
        if corr_short.empty or corr_long.empty:
            return None
        
        short_corr = corr_short.loc[symbol1, symbol2]
        long_corr = corr_long.loc[symbol1, symbol2]
        
        change = short_corr - long_corr
        
        if abs(change) >= threshold:
            # Determinar tipo de alerta
            if short_corr > long_corr + threshold:
                alert_type = 'strengthening'
            elif short_corr < long_corr - threshold:
                alert_type = 'breakdown'
            else:
                alert_type = 'regime_change'
            
            alert = CorrelationAlert(
                symbol1=symbol1,
                symbol2=symbol2,
                old_correlation=float(long_corr),
                new_correlation=float(short_corr),
                change=float(change),
                alert_type=alert_type,
                timestamp=datetime.now()
            )
            
            self._active_alerts.append(alert)
            
            logger.warning(
                f"🔄 Regime Change: {symbol1}/{symbol2} | "
                f"Correlação: {long_corr:.2f} → {short_corr:.2f} "
                f"({change:+.2f})"
            )
            
            return alert
        
        return None
    
    def check_all_regime_changes(self, threshold: float = 0.3) -> List[CorrelationAlert]:
        """
        Verifica mudanças de regime em todos os pares
        
        Returns:
            Lista de alertas
        """
        alerts = []
        
        for i, symbol1 in enumerate(self.symbols):
            for j, symbol2 in enumerate(self.symbols):
                if j <= i:
                    continue
                
                alert = self.detect_regime_change(
                    symbol1, symbol2, 
                    threshold=threshold
                )
                
                if alert:
                    alerts.append(alert)
        
        return alerts
    
    def get_gold_correlations(self, window: int = 50) -> Dict:
        """
        Retorna correlações específicas do Gold com outros ativos
        
        Importante para:
        - DXY/USD: Correlação geralmente negativa
        - Yields: Correlação geralmente negativa
        - EUR/USD: Correlação geralmente positiva
        
        Returns:
            Dict com correlações do Gold
        """
        pairs = self.get_correlation_pairs(window, min_correlation=0.0)
        
        gold_corrs = {}
        
        for pair in pairs:
            if 'XAU' in pair.symbol1 or 'GOLD' in pair.symbol1.upper():
                gold_corrs[pair.symbol2] = {
                    'correlation': pair.correlation,
                    'strength': pair.strength.value,
                    'interpretation': self._interpret_gold_correlation(
                        pair.symbol2, pair.correlation
                    )
                }
            elif 'XAU' in pair.symbol2 or 'GOLD' in pair.symbol2.upper():
                gold_corrs[pair.symbol1] = {
                    'correlation': pair.correlation,
                    'strength': pair.strength.value,
                    'interpretation': self._interpret_gold_correlation(
                        pair.symbol1, pair.correlation
                    )
                }
        
        return {
            'timestamp': datetime.now().isoformat(),
            'window_days': window,
            'correlations': gold_corrs
        }
    
    def _interpret_gold_correlation(self, symbol: str, correlation: float) -> str:
        """Interpreta correlação específica com Gold"""
        symbol_upper = symbol.upper()
        
        # Correlações esperadas baseadas em teoria econômica
        expected = {
            'EURUSD': 'positive',   # EUR forte = USD fraco = Gold sobe
            'GBPUSD': 'positive',   # Mesmo raciocínio
            'AUDUSD': 'positive',   # Australia é produtor de Gold
            'USDJPY': 'negative',   # USD forte = Gold cai
            'USDCHF': 'negative',   # CHF e Gold são safe havens
            'DXY': 'negative'       # Dólar Index
        }
        
        expected_direction = expected.get(symbol_upper, 'unknown')
        
        if expected_direction == 'unknown':
            return 'Correlação não padrão, monitorar'
        
        actual_direction = 'positive' if correlation > 0.1 else (
            'negative' if correlation < -0.1 else 'neutral'
        )
        
        if expected_direction == actual_direction:
            return f"Normal - {symbol_upper} {actual_direction} com Gold como esperado"
        elif actual_direction == 'neutral':
            return f"Descorrelação - {symbol_upper} neutro, atípico"
        else:
            return f"⚠️ Invertida - {symbol_upper} deveria ser {expected_direction}"
    
    def get_analysis_summary(self) -> Dict:
        """Retorna resumo completo da análise de correlação"""
        # Matriz de correlação
        corr_matrix = self.calculate_correlation_matrix(50)
        
        # Pares mais correlacionados
        top_pairs = self.get_correlation_pairs(50, min_correlation=0.5)
        
        # Diversificação
        diversification = self.get_diversification_score(self.symbols)
        
        # Correlações do Gold
        gold_corrs = self.get_gold_correlations()
        
        # Alertas
        alerts = self.check_all_regime_changes(threshold=0.25)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'symbols_analyzed': self.symbols,
            'correlation_matrix': corr_matrix.to_dict() if not corr_matrix.empty else {},
            'top_correlated_pairs': [
                {
                    'pair': f"{p.symbol1}/{p.symbol2}",
                    'correlation': p.correlation,
                    'strength': p.strength.value
                }
                for p in top_pairs[:5]
            ],
            'diversification': diversification,
            'gold_correlations': gold_corrs,
            'regime_change_alerts': [
                {
                    'pair': f"{a.symbol1}/{a.symbol2}",
                    'change': a.change,
                    'type': a.alert_type
                }
                for a in alerts
            ]
        }


# Singleton
_analyzer: Optional[CorrelationAnalyzer] = None


def get_correlation_analyzer(config: Optional[Dict] = None) -> CorrelationAnalyzer:
    """Retorna instância singleton"""
    global _analyzer
    if _analyzer is None:
        _analyzer = CorrelationAnalyzer(config)
    return _analyzer


# Exemplo de uso
if __name__ == "__main__":
    logger.add(lambda msg: print(msg), level="INFO")
    
    analyzer = get_correlation_analyzer()
    
    print("\n=== Correlation Analyzer ===\n")
    
    # Matriz de correlação
    print("1. Matriz de Correlação (50 dias):")
    corr_matrix = analyzer.calculate_correlation_matrix(50)
    print(corr_matrix.round(3))
    
    # Pares correlacionados
    print("\n2. Pares Mais Correlacionados:")
    pairs = analyzer.get_correlation_pairs(50, min_correlation=0.3)
    for pair in pairs:
        print(f"   {pair.symbol1}/{pair.symbol2}: {pair.correlation:.3f} ({pair.strength.value})")
    
    # Diversificação
    print("\n3. Score de Diversificação:")
    div = analyzer.get_diversification_score(['XAUUSD', 'EURUSD', 'GBPUSD'])
    print(f"   Score: {div['score']:.2f} - {div['message']}")
    
    # Correlações do Gold
    print("\n4. Correlações do Gold:")
    gold = analyzer.get_gold_correlations()
    for symbol, data in gold['correlations'].items():
        print(f"   {symbol}: {data['correlation']:.3f} - {data['interpretation']}")
