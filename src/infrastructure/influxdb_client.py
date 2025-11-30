# -*- coding: utf-8 -*-
"""
InfluxDB Client
===============
Cliente InfluxDB para armazenar métricas de trading.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from loguru import logger

try:
    from influxdb_client import InfluxDBClient as InfluxDB, Point, WritePrecision
    from influxdb_client.client.write_api import SYNCHRONOUS
except ImportError:
    InfluxDB = None
    Point = None


class InfluxDBClient:
    """
    Cliente InfluxDB para métricas de trading.
    
    Armazena:
    - Preços e spreads
    - Performance de trades
    - Métricas do sistema
    - Indicadores técnicos
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.influx_config = config.get('infrastructure', {}).get('influxdb', {})
        
        self.url = self.influx_config.get('url', 'http://localhost:8086')
        self.token = self.influx_config.get('token', '')
        self.org = self.influx_config.get('org', 'urion')
        self.bucket = self.influx_config.get('bucket', 'trading')
        
        self._client = None
        self._write_api = None
        self._query_api = None
        self._connected = False
        
        logger.info(f"InfluxDBClient inicializado para {self.url}")
    
    def connect(self) -> bool:
        """Conecta ao InfluxDB"""
        if InfluxDB is None:
            logger.warning("influxdb-client não instalado. Use: pip install influxdb-client")
            return False
        
        try:
            self._client = InfluxDB(
                url=self.url,
                token=self.token,
                org=self.org
            )
            
            # Verificar conexão
            health = self._client.health()
            
            if health.status == "pass":
                self._write_api = self._client.write_api(write_options=SYNCHRONOUS)
                self._query_api = self._client.query_api()
                self._connected = True
                
                logger.success(f"InfluxDB conectado: {self.url}")
                return True
            else:
                logger.error(f"InfluxDB unhealthy: {health.message}")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao conectar InfluxDB: {e}")
            self._connected = False
            return False
    
    @property
    def is_connected(self) -> bool:
        """Verifica se está conectado"""
        return self._connected and self._client is not None
    
    def close(self):
        """Fecha conexão"""
        if self._client:
            self._client.close()
        self._connected = False
        logger.info("InfluxDB desconectado")
    
    # ==========================================
    # WRITE OPERATIONS
    # ==========================================
    
    def write_price(self, symbol: str, price: float, spread: float = 0,
                   volume: float = 0, timestamp: datetime = None):
        """Escreve dados de preço"""
        if not self.is_connected:
            return False
        
        try:
            point = Point("price") \
                .tag("symbol", symbol) \
                .field("price", float(price)) \
                .field("spread", float(spread)) \
                .field("volume", float(volume)) \
                .time(timestamp or datetime.utcnow(), WritePrecision.MS)
            
            self._write_api.write(bucket=self.bucket, record=point)
            return True
            
        except Exception as e:
            logger.error(f"Erro ao escrever preço: {e}")
            return False
    
    def write_trade(self, trade_data: Dict):
        """Escreve dados de trade"""
        if not self.is_connected:
            return False
        
        try:
            point = Point("trade") \
                .tag("symbol", trade_data.get('symbol', 'UNKNOWN')) \
                .tag("strategy", trade_data.get('strategy', 'UNKNOWN')) \
                .tag("direction", trade_data.get('direction', 'UNKNOWN')) \
                .field("profit", float(trade_data.get('profit', 0))) \
                .field("profit_pips", float(trade_data.get('profit_pips', 0))) \
                .field("volume", float(trade_data.get('volume', 0))) \
                .field("duration_minutes", int(trade_data.get('duration_minutes', 0))) \
                .time(datetime.utcnow(), WritePrecision.MS)
            
            self._write_api.write(bucket=self.bucket, record=point)
            return True
            
        except Exception as e:
            logger.error(f"Erro ao escrever trade: {e}")
            return False
    
    def write_metric(self, measurement: str, tags: Dict, fields: Dict,
                    timestamp: datetime = None):
        """Escreve métrica genérica"""
        if not self.is_connected:
            return False
        
        try:
            point = Point(measurement)
            
            for key, value in tags.items():
                point = point.tag(key, str(value))
            
            for key, value in fields.items():
                if isinstance(value, (int, float)):
                    point = point.field(key, float(value))
                else:
                    point = point.field(key, str(value))
            
            point = point.time(timestamp or datetime.utcnow(), WritePrecision.MS)
            
            self._write_api.write(bucket=self.bucket, record=point)
            return True
            
        except Exception as e:
            logger.error(f"Erro ao escrever métrica: {e}")
            return False
    
    # ==========================================
    # QUERY OPERATIONS
    # ==========================================
    
    def query(self, flux_query: str) -> List[Dict]:
        """Executa query Flux"""
        if not self.is_connected:
            return []
        
        try:
            tables = self._query_api.query(flux_query, org=self.org)
            
            results = []
            for table in tables:
                for record in table.records:
                    results.append(record.values)
            
            return results
            
        except Exception as e:
            logger.error(f"Erro na query: {e}")
            return []
    
    def get_recent_prices(self, symbol: str, minutes: int = 60) -> List[Dict]:
        """Obtém preços recentes"""
        query = f'''
        from(bucket: "{self.bucket}")
            |> range(start: -{minutes}m)
            |> filter(fn: (r) => r["_measurement"] == "price")
            |> filter(fn: (r) => r["symbol"] == "{symbol}")
            |> sort(columns: ["_time"])
        '''
        
        return self.query(query)
    
    def get_trade_stats(self, strategy: str = None, hours: int = 24) -> Dict:
        """Obtém estatísticas de trades"""
        filter_strategy = f'|> filter(fn: (r) => r["strategy"] == "{strategy}")' if strategy else ''
        
        query = f'''
        from(bucket: "{self.bucket}")
            |> range(start: -{hours}h)
            |> filter(fn: (r) => r["_measurement"] == "trade")
            {filter_strategy}
            |> filter(fn: (r) => r["_field"] == "profit")
        '''
        
        results = self.query(query)
        
        if not results:
            return {}
        
        profits = [r.get('_value', 0) for r in results]
        
        return {
            'count': len(profits),
            'total_profit': sum(profits),
            'avg_profit': sum(profits) / len(profits) if profits else 0,
            'wins': len([p for p in profits if p > 0]),
            'losses': len([p for p in profits if p < 0])
        }


# Singleton
_influxdb_client = None

def get_influxdb_client(config: Dict = None) -> InfluxDBClient:
    """Retorna instância singleton"""
    global _influxdb_client
    if _influxdb_client is None:
        _influxdb_client = InfluxDBClient(config or {})
    return _influxdb_client
