"""
Historical Data Manager
Download e cache de dados históricos do MT5

Features:
- Download de dados de qualquer símbolo/timeframe
- Cache local em Parquet/CSV
- Atualização incremental
- Múltiplas fontes de dados
"""
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List, Tuple, Any
from loguru import logger
from enum import Enum
import MetaTrader5 as mt5


class Timeframe(Enum):
    """Timeframes suportados"""
    M1 = (mt5.TIMEFRAME_M1, "1min", 1)
    M5 = (mt5.TIMEFRAME_M5, "5min", 5)
    M15 = (mt5.TIMEFRAME_M15, "15min", 15)
    M30 = (mt5.TIMEFRAME_M30, "30min", 30)
    H1 = (mt5.TIMEFRAME_H1, "1H", 60)
    H4 = (mt5.TIMEFRAME_H4, "4H", 240)
    D1 = (mt5.TIMEFRAME_D1, "1D", 1440)
    W1 = (mt5.TIMEFRAME_W1, "1W", 10080)
    MN1 = (mt5.TIMEFRAME_MN1, "1M", 43200)
    
    @property
    def mt5_value(self) -> int:
        return self.value[0]
    
    @property
    def label(self) -> str:
        return self.value[1]
    
    @property
    def minutes(self) -> int:
        return self.value[2]


class DataManager:
    """
    Gerenciador de Dados Históricos
    
    Features:
    - Download do MT5
    - Cache em Parquet (eficiente)
    - Atualização incremental
    - Validação de dados
    - Múltiplos timeframes
    """
    
    def __init__(self, data_dir: str = "data/historical"):
        """
        Inicializa o Data Manager
        
        Args:
            data_dir: Diretório para armazenar dados
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self._cache: Dict[str, pd.DataFrame] = {}
        self._metadata: Dict[str, Dict] = {}
        
        logger.info(f"📂 Data Manager inicializado | Dir: {self.data_dir}")
    
    def _get_file_path(self, symbol: str, timeframe: Timeframe) -> Path:
        """Retorna caminho do arquivo de dados"""
        return self.data_dir / f"{symbol}_{timeframe.label}.parquet"
    
    def _get_cache_key(self, symbol: str, timeframe: Timeframe) -> str:
        """Retorna chave do cache"""
        return f"{symbol}_{timeframe.label}"
    
    def download_from_mt5(
        self,
        symbol: str,
        timeframe: Timeframe,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        max_bars: int = 100000
    ) -> pd.DataFrame:
        """
        Baixa dados do MT5
        
        Args:
            symbol: Símbolo do ativo
            timeframe: Timeframe
            start_date: Data inicial
            end_date: Data final (padrão: agora)
            max_bars: Máximo de barras
            
        Returns:
            DataFrame com dados OHLCV
        """
        if end_date is None:
            end_date = datetime.now()
        
        # Inicializar MT5
        if not mt5.initialize():
            raise RuntimeError("Falha ao inicializar MT5")
        
        try:
            # Verificar símbolo
            if not mt5.symbol_select(symbol, True):
                raise ValueError(f"Símbolo não encontrado: {symbol}")
            
            # Baixar dados
            rates = mt5.copy_rates_range(
                symbol,
                timeframe.mt5_value,
                start_date,
                end_date
            )
            
            if rates is None or len(rates) == 0:
                raise ValueError(f"Sem dados para {symbol} {timeframe.label}")
            
            # Converter para DataFrame
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df = df.rename(columns={
                'tick_volume': 'volume',
                'real_volume': 'real_volume'
            })
            
            # Manter apenas colunas necessárias
            columns = ['time', 'open', 'high', 'low', 'close', 'volume']
            if 'real_volume' in df.columns:
                columns.append('real_volume')
            df = df[columns]
            
            # Ordenar por tempo
            df = df.sort_values('time').reset_index(drop=True)
            
            logger.info(
                f"📥 Baixado {len(df)} barras de {symbol} {timeframe.label} | "
                f"{df['time'].iloc[0].date()} a {df['time'].iloc[-1].date()}"
            )
            
            return df
            
        finally:
            pass  # Não desconectar MT5 aqui para não interferir com o bot
    
    def save_data(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: Timeframe,
        format: str = "parquet"
    ):
        """
        Salva dados em arquivo
        
        Args:
            df: DataFrame com dados
            symbol: Símbolo
            timeframe: Timeframe
            format: 'parquet' ou 'csv'
        """
        if format == "parquet":
            file_path = self.data_dir / f"{symbol}_{timeframe.label}.parquet"
            df.to_parquet(file_path, index=False)
        else:
            file_path = self.data_dir / f"{symbol}_{timeframe.label}.csv"
            df.to_csv(file_path, index=False)
        
        logger.info(f"💾 Dados salvos: {file_path}")
        
        # Atualizar metadata
        cache_key = self._get_cache_key(symbol, timeframe)
        self._metadata[cache_key] = {
            'symbol': symbol,
            'timeframe': timeframe.label,
            'bars': len(df),
            'start_date': df['time'].iloc[0].isoformat(),
            'end_date': df['time'].iloc[-1].isoformat(),
            'updated_at': datetime.now().isoformat()
        }
    
    def load_data(
        self,
        symbol: str,
        timeframe: Timeframe,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Carrega dados do cache ou arquivo
        
        Args:
            symbol: Símbolo
            timeframe: Timeframe
            start_date: Filtrar a partir de
            end_date: Filtrar até
            use_cache: Usar cache em memória
            
        Returns:
            DataFrame com dados
        """
        cache_key = self._get_cache_key(symbol, timeframe)
        
        # Verificar cache em memória
        if use_cache and cache_key in self._cache:
            df = self._cache[cache_key].copy()
        else:
            # Carregar do arquivo
            parquet_path = self.data_dir / f"{symbol}_{timeframe.label}.parquet"
            csv_path = self.data_dir / f"{symbol}_{timeframe.label}.csv"
            
            if parquet_path.exists():
                df = pd.read_parquet(parquet_path)
            elif csv_path.exists():
                df = pd.read_csv(csv_path, parse_dates=['time'])
            else:
                raise FileNotFoundError(f"Dados não encontrados para {symbol} {timeframe.label}")
            
            # Atualizar cache
            if use_cache:
                self._cache[cache_key] = df.copy()
        
        # Filtrar por data
        if start_date:
            df = df[df['time'] >= start_date]
        if end_date:
            df = df[df['time'] <= end_date]
        
        return df.reset_index(drop=True)
    
    def update_data(
        self,
        symbol: str,
        timeframe: Timeframe
    ) -> pd.DataFrame:
        """
        Atualiza dados incrementalmente
        
        Args:
            symbol: Símbolo
            timeframe: Timeframe
            
        Returns:
            DataFrame atualizado
        """
        try:
            # Carregar dados existentes
            existing_df = self.load_data(symbol, timeframe, use_cache=False)
            last_date = existing_df['time'].iloc[-1]
            
            # Baixar novos dados
            new_df = self.download_from_mt5(
                symbol,
                timeframe,
                start_date=last_date + timedelta(minutes=1),
                end_date=datetime.now()
            )
            
            if len(new_df) > 0:
                # Concatenar
                df = pd.concat([existing_df, new_df], ignore_index=True)
                df = df.drop_duplicates(subset=['time']).sort_values('time').reset_index(drop=True)
                
                # Salvar
                self.save_data(df, symbol, timeframe)
                
                logger.info(f"📈 Dados atualizados: +{len(new_df)} barras para {symbol} {timeframe.label}")
                
                return df
            else:
                return existing_df
                
        except FileNotFoundError:
            # Se não existir, baixar tudo
            logger.info(f"📥 Dados não existem, baixando histórico completo...")
            return self.download_full_history(symbol, timeframe)
    
    def download_full_history(
        self,
        symbol: str,
        timeframe: Timeframe,
        years: int = 5
    ) -> pd.DataFrame:
        """
        Baixa histórico completo
        
        Args:
            symbol: Símbolo
            timeframe: Timeframe
            years: Anos de histórico
            
        Returns:
            DataFrame com dados
        """
        start_date = datetime.now() - timedelta(days=years * 365)
        
        df = self.download_from_mt5(
            symbol,
            timeframe,
            start_date=start_date
        )
        
        self.save_data(df, symbol, timeframe)
        
        return df
    
    def get_available_data(self) -> List[Dict]:
        """Lista dados disponíveis"""
        available = []
        
        for file_path in self.data_dir.glob("*.parquet"):
            parts = file_path.stem.split('_')
            if len(parts) >= 2:
                symbol = parts[0]
                timeframe = parts[1]
                
                df = pd.read_parquet(file_path)
                
                available.append({
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'bars': len(df),
                    'start_date': df['time'].iloc[0].isoformat(),
                    'end_date': df['time'].iloc[-1].isoformat(),
                    'file_size_mb': file_path.stat().st_size / (1024 * 1024)
                })
        
        return available
    
    def validate_data(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Valida integridade dos dados
        
        Returns:
            Dict com informações de validação
        """
        issues = []
        
        # Verificar valores nulos
        nulls = df.isnull().sum()
        if nulls.any():
            issues.append(f"Valores nulos encontrados: {nulls.to_dict()}")
        
        # Verificar duplicatas
        duplicates = df.duplicated(subset=['time']).sum()
        if duplicates > 0:
            issues.append(f"{duplicates} timestamps duplicados")
        
        # Verificar gaps
        df_sorted = df.sort_values('time')
        time_diff = df_sorted['time'].diff()
        
        # Encontrar gaps maiores que o esperado (considerando fins de semana)
        expected_gap = df_sorted['time'].iloc[1] - df_sorted['time'].iloc[0]
        large_gaps = time_diff[time_diff > expected_gap * 10]
        
        if len(large_gaps) > 0:
            issues.append(f"{len(large_gaps)} gaps maiores que esperado")
        
        # Verificar preços inválidos
        invalid_prices = (
            (df['high'] < df['low']).sum() +
            (df['close'] > df['high']).sum() +
            (df['close'] < df['low']).sum() +
            (df['open'] > df['high']).sum() +
            (df['open'] < df['low']).sum()
        )
        if invalid_prices > 0:
            issues.append(f"{invalid_prices} barras com preços inválidos")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'bars': len(df),
            'start_date': df['time'].min(),
            'end_date': df['time'].max()
        }
    
    def prepare_for_backtest(
        self,
        symbol: str,
        timeframe: Timeframe,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        add_features: bool = True
    ) -> pd.DataFrame:
        """
        Prepara dados para backtest
        
        Args:
            symbol: Símbolo
            timeframe: Timeframe
            start_date: Data inicial
            end_date: Data final
            add_features: Adicionar features técnicas
            
        Returns:
            DataFrame preparado
        """
        df = self.load_data(symbol, timeframe, start_date, end_date)
        
        if add_features:
            # Adicionar features básicas
            
            # ATR
            high_low = df['high'] - df['low']
            high_close = abs(df['high'] - df['close'].shift())
            low_close = abs(df['low'] - df['close'].shift())
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            df['atr_14'] = tr.rolling(14).mean()
            
            # SMAs
            df['sma_20'] = df['close'].rolling(20).mean()
            df['sma_50'] = df['close'].rolling(50).mean()
            df['sma_200'] = df['close'].rolling(200).mean()
            
            # RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            df['rsi_14'] = 100 - (100 / (1 + rs))
            
            # MACD
            exp1 = df['close'].ewm(span=12).mean()
            exp2 = df['close'].ewm(span=26).mean()
            df['macd'] = exp1 - exp2
            df['macd_signal'] = df['macd'].ewm(span=9).mean()
            
            # Bollinger Bands
            df['bb_middle'] = df['close'].rolling(20).mean()
            df['bb_std'] = df['close'].rolling(20).std()
            df['bb_upper'] = df['bb_middle'] + 2 * df['bb_std']
            df['bb_lower'] = df['bb_middle'] - 2 * df['bb_std']
            
            # Returns
            df['returns'] = df['close'].pct_change()
            df['log_returns'] = np.log(df['close'] / df['close'].shift())
        
        return df.dropna().reset_index(drop=True)
    
    def clear_cache(self):
        """Limpa cache em memória"""
        self._cache.clear()
        logger.info("🗑️ Cache limpo")


# Singleton
_data_manager: Optional[DataManager] = None


def get_data_manager(data_dir: str = "data/historical") -> DataManager:
    """Obtém instância singleton do Data Manager"""
    global _data_manager
    if _data_manager is None:
        _data_manager = DataManager(data_dir)
    return _data_manager


# Exemplo de uso:
"""
from backtesting.data_manager import get_data_manager, Timeframe

dm = get_data_manager()

# Baixar dados
df = dm.download_from_mt5('EURUSD', Timeframe.H1, datetime(2020, 1, 1))
dm.save_data(df, 'EURUSD', Timeframe.H1)

# Carregar dados
df = dm.load_data('EURUSD', Timeframe.H1)

# Atualizar dados
df = dm.update_data('EURUSD', Timeframe.H1)

# Preparar para backtest
df = dm.prepare_for_backtest('EURUSD', Timeframe.H1, add_features=True)
"""
