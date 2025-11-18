"""
Módulo de Análise Técnica Multi-Timeframe
Responsável por calcular indicadores técnicos e detectar padrões de candlestick
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import MetaTrader5 as mt5
from loguru import logger

# Importar bibliotecas de análise técnica
try:
    import ta
    from ta.trend import EMAIndicator, SMAIndicator, MACD, ADXIndicator
    from ta.momentum import RSIIndicator, StochasticOscillator
    from ta.volatility import BollingerBands, AverageTrueRange
    from ta.volume import OnBalanceVolumeIndicator
except ImportError:
    logger.warning("Biblioteca 'ta' não encontrada. Instale com: pip install ta")

try:
    import pandas_ta as pta
except ImportError:
    logger.warning("Biblioteca 'pandas_ta' não encontrada. Instale com: pip install pandas_ta")


class TechnicalAnalyzer:
    """
    Analisador técnico multi-timeframe para XAUUSD
    """
    
    # Timeframes suportados
    TIMEFRAMES = {
        'M1': mt5.TIMEFRAME_M1,
        'M5': mt5.TIMEFRAME_M5,
        'M15': mt5.TIMEFRAME_M15,
        'M30': mt5.TIMEFRAME_M30,
        'H1': mt5.TIMEFRAME_H1,
        'H4': mt5.TIMEFRAME_H4,
        'D1': mt5.TIMEFRAME_D1
    }
    
    def __init__(self, mt5_connector, config: Dict):
        """
        Inicializa o analisador técnico
        
        Args:
            mt5_connector: Instância do MT5Connector
            config: Configurações do sistema
        """
        self.mt5 = mt5_connector
        self.config = config
        self.symbol = config.get('mt5', {}).get('symbol', 'XAUUSD')
        self.ta_config = config.get('technical_analysis', {})
        
        # Cache de dados
        self._cache: Dict[str, Dict] = {}
        self._cache_timeout = timedelta(seconds=30)
        
        logger.info(f"TechnicalAnalyzer inicializado para {self.symbol}")
    
    def get_market_data(self, timeframe: str, bars: int = 500) -> Optional[pd.DataFrame]:
        """
        Obtém dados de mercado para análise
        
        Args:
            timeframe: Timeframe (M1, M5, M15, etc)
            bars: Número de barras
            
        Returns:
            DataFrame com OHLCV ou None se erro
        """
        try:
            # Verificar cache
            cache_key = f"{timeframe}_{bars}"
            if cache_key in self._cache:
                cache_entry = self._cache[cache_key]
                if datetime.now() - cache_entry['timestamp'] < self._cache_timeout:
                    return cache_entry['data'].copy()
            
            # Obter dados do MT5
            tf = self.TIMEFRAMES.get(timeframe)
            if tf is None:
                logger.error(f"Timeframe inválido: {timeframe}")
                return None
            
            df = self.mt5.get_rates(self.symbol, tf, bars)
            if df is None or len(df) == 0:
                logger.error(f"Erro ao obter dados para {timeframe}")
                return None
            
            # Renomear colunas para padrão (MT5 retorna lowercase)
            df.rename(columns={
                'open': 'Open',
                'high': 'High',
                'low': 'Low',
                'close': 'Close',
                'tick_volume': 'Volume'
            }, inplace=True)
            
            # Atualizar cache
            self._cache[cache_key] = {
                'data': df.copy(),
                'timestamp': datetime.now()
            }
            
            return df
            
        except Exception as e:
            logger.error(f"Erro ao obter dados de mercado: {e}")
            return None
    
    def calculate_ema(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Calcula EMA (Exponential Moving Average)"""
        try:
            ema = EMAIndicator(close=df['Close'], window=period)
            return ema.ema_indicator()
        except:
            return df['Close'].ewm(span=period, adjust=False).mean()
    
    def calculate_sma(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Calcula SMA (Simple Moving Average)"""
        try:
            sma = SMAIndicator(close=df['Close'], window=period)
            return sma.sma_indicator()
        except:
            return df['Close'].rolling(window=period).mean()
    
    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calcula RSI (Relative Strength Index)"""
        try:
            rsi = RSIIndicator(close=df['Close'], window=period)
            return rsi.rsi()
        except:
            # Implementação manual
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            return 100 - (100 / (1 + rs))
    
    def calculate_macd(self, df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        """Calcula MACD (Moving Average Convergence Divergence)"""
        try:
            macd = MACD(close=df['Close'], window_slow=slow, window_fast=fast, window_sign=signal)
            return {
                'macd': macd.macd(),
                'signal': macd.macd_signal(),
                'histogram': macd.macd_diff()
            }
        except:
            # Implementação manual
            ema_fast = df['Close'].ewm(span=fast, adjust=False).mean()
            ema_slow = df['Close'].ewm(span=slow, adjust=False).mean()
            macd_line = ema_fast - ema_slow
            signal_line = macd_line.ewm(span=signal, adjust=False).mean()
            histogram = macd_line - signal_line
            
            return {
                'macd': macd_line,
                'signal': signal_line,
                'histogram': histogram
            }
    
    def calculate_bollinger_bands(self, df: pd.DataFrame, period: int = 20, std: float = 2.0) -> Dict[str, pd.Series]:
        """Calcula Bandas de Bollinger"""
        try:
            bb = BollingerBands(close=df['Close'], window=period, window_dev=std)
            return {
                'upper': bb.bollinger_hband(),
                'middle': bb.bollinger_mavg(),
                'lower': bb.bollinger_lband()
            }
        except:
            # Implementação manual
            sma = df['Close'].rolling(window=period).mean()
            std_dev = df['Close'].rolling(window=period).std()
            
            return {
                'upper': sma + (std_dev * std),
                'middle': sma,
                'lower': sma - (std_dev * std)
            }
    
    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calcula ATR (Average True Range)"""
        try:
            atr = AverageTrueRange(high=df['High'], low=df['Low'], close=df['Close'], window=period)
            return atr.average_true_range()
        except:
            # Implementação manual
            high_low = df['High'] - df['Low']
            high_close = np.abs(df['High'] - df['Close'].shift())
            low_close = np.abs(df['Low'] - df['Close'].shift())
            
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            return tr.rolling(window=period).mean()
    
    def calculate_adx(self, df: pd.DataFrame, period: int = 14) -> Dict[str, pd.Series]:
        """Calcula ADX (Average Directional Index)"""
        try:
            adx = ADXIndicator(high=df['High'], low=df['Low'], close=df['Close'], window=period)
            return {
                'adx': adx.adx(),
                'di_plus': adx.adx_pos(),
                'di_minus': adx.adx_neg()
            }
        except:
            logger.warning("Falha ao calcular ADX com biblioteca 'ta'")
            return {
                'adx': pd.Series([50] * len(df), index=df.index),
                'di_plus': pd.Series([25] * len(df), index=df.index),
                'di_minus': pd.Series([25] * len(df), index=df.index)
            }
    
    def calculate_stochastic(self, df: pd.DataFrame, period: int = 14, smooth: int = 3) -> Dict[str, pd.Series]:
        """Calcula Oscilador Estocástico"""
        try:
            stoch = StochasticOscillator(high=df['High'], low=df['Low'], close=df['Close'], 
                                        window=period, smooth_window=smooth)
            return {
                'k': stoch.stoch(),
                'd': stoch.stoch_signal()
            }
        except:
            # Implementação manual
            low_min = df['Low'].rolling(window=period).min()
            high_max = df['High'].rolling(window=period).max()
            
            k = 100 * ((df['Close'] - low_min) / (high_max - low_min))
            d = k.rolling(window=smooth).mean()
            
            return {'k': k, 'd': d}
    
    def detect_candlestick_patterns(self, df: pd.DataFrame) -> Dict[str, bool]:
        """
        Detecta padrões de candlestick
        
        Returns:
            Dict com padrões detectados e seus valores (True/False)
        """
        if len(df) < 3:
            return {}
        
        patterns = {}
        
        # Última candle
        last = df.iloc[-1]
        prev = df.iloc[-2]
        prev2 = df.iloc[-3] if len(df) >= 3 else None
        
        # Tamanho do corpo
        last_body = abs(last['Close'] - last['Open'])
        prev_body = abs(prev['Close'] - prev['Open'])
        
        # Tamanho da sombra
        last_upper_shadow = last['High'] - max(last['Open'], last['Close'])
        last_lower_shadow = min(last['Open'], last['Close']) - last['Low']
        
        # Padrão: Doji
        # Corpo muito pequeno em relação ao range total
        last_range = last['High'] - last['Low']
        patterns['doji'] = last_body < (last_range * 0.1) and last_range > 0
        
        # Padrão: Hammer (Martelo)
        # Corpo pequeno no topo, sombra inferior longa
        patterns['hammer'] = (
            last_lower_shadow > (last_body * 2) and
            last_upper_shadow < (last_body * 0.5) and
            last['Close'] < prev['Close']  # Em tendência de baixa
        )
        
        # Padrão: Inverted Hammer (Martelo Invertido)
        patterns['inverted_hammer'] = (
            last_upper_shadow > (last_body * 2) and
            last_lower_shadow < (last_body * 0.5) and
            last['Close'] < prev['Close']
        )
        
        # Padrão: Shooting Star (Estrela Cadente)
        patterns['shooting_star'] = (
            last_upper_shadow > (last_body * 2) and
            last_lower_shadow < (last_body * 0.5) and
            last['Close'] > prev['Close']  # Em tendência de alta
        )
        
        # Padrão: Engulfing Bullish (Engolfo de Alta)
        patterns['engulfing_bullish'] = (
            prev['Close'] < prev['Open'] and  # Candle anterior de baixa
            last['Close'] > last['Open'] and  # Candle atual de alta
            last['Open'] <= prev['Close'] and
            last['Close'] >= prev['Open']
        )
        
        # Padrão: Engulfing Bearish (Engolfo de Baixa)
        patterns['engulfing_bearish'] = (
            prev['Close'] > prev['Open'] and  # Candle anterior de alta
            last['Close'] < last['Open'] and  # Candle atual de baixa
            last['Open'] >= prev['Close'] and
            last['Close'] <= prev['Open']
        )
        
        # Padrão: Morning Star (Estrela da Manhã) - 3 candles
        if prev2 is not None:
            patterns['morning_star'] = (
                prev2['Close'] < prev2['Open'] and  # 1ª candle: baixa
                prev_body < (prev2_body := abs(prev2['Close'] - prev2['Open'])) * 0.3 and  # 2ª: corpo pequeno
                last['Close'] > last['Open'] and  # 3ª: alta
                last['Close'] > (prev2['Open'] + prev2['Close']) / 2  # Fecha acima da metade da 1ª
            )
            
            # Padrão: Evening Star (Estrela da Tarde) - 3 candles
            patterns['evening_star'] = (
                prev2['Close'] > prev2['Open'] and  # 1ª candle: alta
                prev_body < prev2_body * 0.3 and  # 2ª: corpo pequeno
                last['Close'] < last['Open'] and  # 3ª: baixa
                last['Close'] < (prev2['Open'] + prev2['Close']) / 2  # Fecha abaixo da metade da 1ª
            )
        
        # Padrão: Pin Bar (Barra de Pin)
        patterns['pin_bar_bullish'] = (
            last_lower_shadow > (last_body * 2) and
            last_upper_shadow < last_body
        )
        
        patterns['pin_bar_bearish'] = (
            last_upper_shadow > (last_body * 2) and
            last_lower_shadow < last_body
        )
        
        return patterns
    
    def analyze_timeframe(self, timeframe: str, bars: int = 500) -> Optional[Dict]:
        """
        Análise completa de um timeframe
        
        Args:
            timeframe: Timeframe a analisar
            bars: Número de barras
            
        Returns:
            Dict com todos os indicadores e padrões
        """
        try:
            # Obter dados
            df = self.get_market_data(timeframe, bars)
            if df is None or len(df) < 50:
                return None
            
            # Configurações dos indicadores
            indicators_config = self.ta_config.get('indicators', [])
            
            # Calcular indicadores
            result = {
                'timeframe': timeframe,
                'last_update': datetime.now().isoformat(),
                'current_price': float(df['Close'].iloc[-1]),
                'current_time': df.index[-1].isoformat(),
            }
            
            # Extrair períodos de indicadores da config (formato lista)
            ema_periods = [9, 21, 50, 200]  # padrão
            sma_periods = [20, 50, 100, 200]  # padrão
            
            if isinstance(indicators_config, list):
                for indicator in indicators_config:
                    if indicator.get('name') == 'EMA':
                        ema_periods = indicator.get('periods', ema_periods)
                    elif indicator.get('name') == 'SMA':
                        sma_periods = indicator.get('periods', sma_periods)
            
            # Médias Móveis
            result['ema'] = {}
            for period in ema_periods:
                if len(df) >= period:
                    ema = self.calculate_ema(df, period)
                    result['ema'][f'ema_{period}'] = float(ema.iloc[-1])
            
            result['sma'] = {}
            for period in sma_periods:
                if len(df) >= period:
                    sma = self.calculate_sma(df, period)
                    result['sma'][f'sma_{period}'] = float(sma.iloc[-1])
            
            # RSI
            rsi = self.calculate_rsi(df, 14)
            result['rsi'] = float(rsi.iloc[-1])
            
            # MACD
            macd = self.calculate_macd(df)
            result['macd'] = {
                'macd': float(macd['macd'].iloc[-1]),
                'signal': float(macd['signal'].iloc[-1]),
                'histogram': float(macd['histogram'].iloc[-1])
            }
            
            # Bollinger Bands
            bb = self.calculate_bollinger_bands(df)
            result['bollinger'] = {
                'upper': float(bb['upper'].iloc[-1]),
                'middle': float(bb['middle'].iloc[-1]),
                'lower': float(bb['lower'].iloc[-1])
            }
            
            # ATR
            atr = self.calculate_atr(df)
            result['atr'] = float(atr.iloc[-1])
            
            # ADX
            adx = self.calculate_adx(df)
            result['adx'] = {
                'adx': float(adx['adx'].iloc[-1]),
                'di_plus': float(adx['di_plus'].iloc[-1]),
                'di_minus': float(adx['di_minus'].iloc[-1])
            }
            
            # Stochastic
            stoch = self.calculate_stochastic(df)
            result['stochastic'] = {
                'k': float(stoch['k'].iloc[-1]),
                'd': float(stoch['d'].iloc[-1])
            }
            
            # Padrões de Candlestick
            result['patterns'] = self.detect_candlestick_patterns(df)
            
            # Análise de tendência
            try:
                result['trend'] = self._analyze_trend(df, result)
            except Exception as trend_error:
                logger.error(f"Erro na análise de tendência: {trend_error}")
                logger.error(f"Tipo indicators['ema']: {type(result.get('ema'))}")
                logger.error(f"Valor indicators['ema']: {result.get('ema')}")
                raise
            
            logger.debug(f"Análise completa para {timeframe}: {len(result)} indicadores")
            return result
            
        except Exception as e:
            logger.error(f"Erro ao analisar timeframe {timeframe}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _analyze_trend(self, df: pd.DataFrame, indicators: Dict) -> Dict:
        """
        Analisa a tendência do mercado
        
        Returns:
            Dict com direção da tendência e força
        """
        trend = {
            'direction': 'neutral',  # bullish, bearish, neutral
            'strength': 0.0,  # 0.0 a 1.0
            'signals': []
        }
        
        bullish_signals = 0
        bearish_signals = 0
        total_signals = 0
        
        current_price = indicators['current_price']
        
        # Análise baseada em EMAs
        if 'ema' in indicators:
            ema_9 = indicators['ema'].get('ema_9')
            ema_21 = indicators['ema'].get('ema_21')
            ema_50 = indicators['ema'].get('ema_50')
            
            if ema_9 and ema_21:
                if ema_9 > ema_21:
                    bullish_signals += 1
                    trend['signals'].append('EMA 9 > 21 (bullish)')
                else:
                    bearish_signals += 1
                    trend['signals'].append('EMA 9 < 21 (bearish)')
                total_signals += 1
            
            if ema_21 and ema_50:
                if ema_21 > ema_50:
                    bullish_signals += 1
                else:
                    bearish_signals += 1
                total_signals += 1
        
        # Análise RSI
        if 'rsi' in indicators:
            rsi = indicators['rsi']
            if rsi > 70:
                bearish_signals += 1
                trend['signals'].append(f'RSI {rsi:.1f} > 70 (sobrecomprado)')
            elif rsi < 30:
                bullish_signals += 1
                trend['signals'].append(f'RSI {rsi:.1f} < 30 (sobrevendido)')
            total_signals += 1
        
        # Análise MACD
        if 'macd' in indicators:
            macd_val = indicators['macd']['macd']
            signal_val = indicators['macd']['signal']
            
            if macd_val > signal_val:
                bullish_signals += 1
                trend['signals'].append('MACD > Signal (bullish)')
            else:
                bearish_signals += 1
                trend['signals'].append('MACD < Signal (bearish)')
            total_signals += 1
        
        # Análise ADX (força da tendência)
        if 'adx' in indicators:
            adx_val = indicators['adx']['adx']
            di_plus = indicators['adx']['di_plus']
            di_minus = indicators['adx']['di_minus']
            
            if adx_val > 25:
                if di_plus > di_minus:
                    bullish_signals += 1
                    trend['signals'].append(f'ADX {adx_val:.1f} + DI+ > DI- (tendência de alta forte)')
                else:
                    bearish_signals += 1
                    trend['signals'].append(f'ADX {adx_val:.1f} + DI- > DI+ (tendência de baixa forte)')
                
                # Força da tendência baseada no ADX
                trend['strength'] = min(adx_val / 100, 1.0)
            total_signals += 1
        
        # Análise Bollinger Bands
        if 'bollinger' in indicators:
            upper = indicators['bollinger']['upper']
            lower = indicators['bollinger']['lower']
            
            if current_price > upper:
                bearish_signals += 1
                trend['signals'].append('Preço acima da banda superior (sobrecomprado)')
            elif current_price < lower:
                bullish_signals += 1
                trend['signals'].append('Preço abaixo da banda inferior (sobrevendido)')
            total_signals += 1
        
        # Determinar direção
        if total_signals > 0:
            bullish_ratio = bullish_signals / total_signals
            bearish_ratio = bearish_signals / total_signals
            
            if bullish_ratio > 0.6:
                trend['direction'] = 'bullish'
                if trend['strength'] == 0.0:
                    trend['strength'] = bullish_ratio
            elif bearish_ratio > 0.6:
                trend['direction'] = 'bearish'
                if trend['strength'] == 0.0:
                    trend['strength'] = bearish_ratio
            else:
                trend['direction'] = 'neutral'
                trend['strength'] = 0.5
        
        return trend
    
    def analyze_multi_timeframe(self, timeframes: Optional[List[str]] = None) -> Dict:
        """
        Análise de múltiplos timeframes
        
        Args:
            timeframes: Lista de timeframes (None = usar todos)
            
        Returns:
            Dict com análises de cada timeframe
        """
        if timeframes is None:
            timeframes = ['M5', 'M15', 'M30', 'H1', 'H4']
        
        results = {}
        
        for tf in timeframes:
            analysis = self.analyze_timeframe(tf)
            if analysis:
                results[tf] = analysis
        
        # Adicionar consenso multi-timeframe
        if results:
            results['consensus'] = self._calculate_consensus(results)
        
        logger.info(f"Análise multi-timeframe completa: {len(results)} timeframes")
        return results
    
    def _calculate_consensus(self, analyses: Dict) -> Dict:
        """
        Calcula consenso entre múltiplos timeframes
        
        Args:
            analyses: Dict com análises de cada timeframe
            
        Returns:
            Dict com consenso geral
        """
        bullish_count = 0
        bearish_count = 0
        neutral_count = 0
        total_strength = 0.0
        count = 0
        
        for tf, data in analyses.items():
            if tf == 'consensus':
                continue
            
            trend = data.get('trend', {})
            direction = trend.get('direction', 'neutral')
            strength = trend.get('strength', 0.0)
            
            if direction == 'bullish':
                bullish_count += 1
            elif direction == 'bearish':
                bearish_count += 1
            else:
                neutral_count += 1
            
            total_strength += strength
            count += 1
        
        if count == 0:
            return {'direction': 'neutral', 'strength': 0.0, 'agreement': 0.0}
        
        # Direção dominante
        max_count = max(bullish_count, bearish_count, neutral_count)
        if bullish_count == max_count:
            direction = 'bullish'
        elif bearish_count == max_count:
            direction = 'bearish'
        else:
            direction = 'neutral'
        
        # Força média
        avg_strength = total_strength / count
        
        # Nível de concordância
        agreement = max_count / count
        
        return {
            'direction': direction,
            'strength': round(avg_strength, 2),
            'agreement': round(agreement, 2),
            'bullish_count': bullish_count,
            'bearish_count': bearish_count,
            'neutral_count': neutral_count
        }
    
    def get_signal(self, timeframe: str = 'M5') -> Optional[Dict]:
        """
        Gera sinal de trading baseado na análise técnica
        
        Args:
            timeframe: Timeframe principal para análise
            
        Returns:
            Dict com sinal (BUY/SELL/HOLD) e confiança
        """
        try:
            # Análise multi-timeframe
            mtf_analysis = self.analyze_multi_timeframe([timeframe, 'M15', 'H1'])
            
            if not mtf_analysis or 'consensus' not in mtf_analysis:
                return None
            
            consensus = mtf_analysis['consensus']
            direction = consensus['direction']
            strength = consensus['strength']
            agreement = consensus['agreement']
            
            # Calcular confiança do sinal
            confidence = (strength + agreement) / 2
            
            # Determinar ação
            if direction == 'bullish' and confidence > 0.6:
                action = 'BUY'
            elif direction == 'bearish' and confidence > 0.6:
                action = 'SELL'
            else:
                action = 'HOLD'
            
            signal = {
                'action': action,
                'confidence': round(confidence, 2),
                'direction': direction,
                'strength': strength,
                'agreement': agreement,
                'timeframe': timeframe,
                'timestamp': datetime.now().isoformat(),
                'analysis': mtf_analysis
            }
            
            logger.info(f"Sinal gerado: {action} (confiança: {confidence:.2f})")
            return signal
            
        except Exception as e:
            logger.error(f"Erro ao gerar sinal: {e}")
            return None
    
    def clear_cache(self):
        """Limpa o cache de dados"""
        self._cache.clear()
        logger.debug("Cache limpo")
