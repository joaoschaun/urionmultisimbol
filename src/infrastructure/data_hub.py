# -*- coding: utf-8 -*-
"""
Data Hub
========
Central de dados que integra várias fontes.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from loguru import logger

from .redis_client import get_redis_client
from .influxdb_client import get_influxdb_client


class DataHub:
    """
    Central de dados para o bot de trading.
    Integra Redis (cache) e InfluxDB (métricas).
    """
    
    def __init__(self, config: Dict):
        self.config = config
        
        # Obter clientes
        self.redis = get_redis_client(config)
        self.influxdb = get_influxdb_client(config)
        
        logger.info("DataHub inicializado")
    
    def connect_all(self) -> Dict[str, bool]:
        """Conecta a todos os serviços"""
        results = {}
        
        results['redis'] = self.redis.connect()
        results['influxdb'] = self.influxdb.connect()
        
        return results
    
    def close_all(self):
        """Fecha todas as conexões"""
        self.redis.close()
        self.influxdb.close()
    
    @property
    def status(self) -> Dict:
        """Retorna status de todas as conexões"""
        return {
            'redis': self.redis.is_connected,
            'influxdb': self.influxdb.is_connected
        }
    
    # ==========================================
    # CACHE COM FALLBACK
    # ==========================================
    
    def get_cached(self, key: str, fetch_func, ttl: int = 300) -> Any:
        """
        Obtém do cache ou busca e cacheia
        """
        # Tentar cache Redis
        cached = self.redis.get(key)
        if cached is not None:
            return cached
        
        # Buscar dados frescos
        data = fetch_func()
        
        # Cachear se Redis disponível
        if data is not None:
            self.redis.set(key, data, ttl)
        
        return data
    
    # ==========================================
    # MÉTRICAS
    # ==========================================
    
    def record_price(self, symbol: str, price: float, spread: float = 0):
        """Registra preço (cache + persistência)"""
        # Cache para acesso rápido
        self.redis.set(f"price:{symbol}", {
            'price': price,
            'spread': spread,
            'timestamp': datetime.now().isoformat()
        }, ttl=60)
        
        # Persistir em InfluxDB
        self.influxdb.write_price(symbol, price, spread)
    
    def record_trade(self, trade_data: Dict):
        """Registra trade completado"""
        self.influxdb.write_trade(trade_data)
    
    def get_price(self, symbol: str) -> Optional[Dict]:
        """Obtém preço cacheado"""
        return self.redis.get(f"price:{symbol}")


# Singleton
_data_hub = None

def get_data_hub(config: Dict = None) -> DataHub:
    """Retorna instância singleton"""
    global _data_hub
    if _data_hub is None:
        _data_hub = DataHub(config or {})
    return _data_hub
