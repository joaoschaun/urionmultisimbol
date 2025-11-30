# -*- coding: utf-8 -*-
"""
Redis Client
============
Cliente Redis para caching, pub/sub e rate limiting.
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from loguru import logger
import json
import pickle

try:
    import redis
except ImportError:
    redis = None


class RedisClient:
    """
    Cliente Redis para o bot de trading.
    
    Funcionalidades:
    - Cache de dados (preços, indicadores)
    - Pub/Sub para eventos em tempo real
    - Rate limiting para APIs
    - Locks distribuídos
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.redis_config = config.get('infrastructure', {}).get('redis', {})
        
        self.host = self.redis_config.get('host', 'localhost')
        self.port = self.redis_config.get('port', 6379)
        self.db = self.redis_config.get('db', 0)
        self.password = self.redis_config.get('password', '') or None
        self.default_ttl = self.redis_config.get('cache_ttl', 300)
        
        self._client: Optional['redis.Redis'] = None
        self._pubsub: Optional['redis.client.PubSub'] = None
        self._connected = False
        
        logger.info(f"RedisClient inicializado para {self.host}:{self.port}")
    
    def connect(self) -> bool:
        """Conecta ao Redis"""
        if redis is None:
            logger.warning("redis-py não instalado. Use: pip install redis")
            return False
        
        try:
            self._client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            
            # Testar conexão
            self._client.ping()
            self._connected = True
            
            logger.success(f"Redis conectado: {self.host}:{self.port}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao conectar Redis: {e}")
            self._connected = False
            return False
    
    @property
    def is_connected(self) -> bool:
        """Verifica se está conectado"""
        if not self._connected or not self._client:
            return False
        
        try:
            self._client.ping()
            return True
        except:
            self._connected = False
            return False
    
    def close(self):
        """Fecha conexão"""
        if self._pubsub:
            self._pubsub.close()
        if self._client:
            self._client.close()
        self._connected = False
        logger.info("Redis desconectado")
    
    # ==========================================
    # CACHE OPERATIONS
    # ==========================================
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """
        Define um valor no cache
        """
        if not self.is_connected:
            return False
        
        try:
            ttl = ttl or self.default_ttl
            
            # Serializar valor
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            
            self._client.setex(key, ttl, value)
            return True
            
        except Exception as e:
            logger.error(f"Erro ao setar cache: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Obtém um valor do cache
        """
        if not self.is_connected:
            return default
        
        try:
            value = self._client.get(key)
            
            if value is None:
                return default
            
            # Tentar deserializar JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
                
        except Exception as e:
            logger.error(f"Erro ao obter cache: {e}")
            return default
    
    def delete(self, key: str) -> bool:
        """Remove uma chave"""
        if not self.is_connected:
            return False
        
        try:
            self._client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Erro ao deletar cache: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Verifica se chave existe"""
        if not self.is_connected:
            return False
        
        try:
            return self._client.exists(key) > 0
        except:
            return False
    
    def get_or_set(self, key: str, func, ttl: int = None) -> Any:
        """
        Obtém do cache ou executa função e armazena
        """
        value = self.get(key)
        
        if value is not None:
            return value
        
        # Executar função e cachear
        value = func()
        self.set(key, value, ttl)
        
        return value
    
    # ==========================================
    # RATE LIMITING
    # ==========================================
    
    def rate_limit(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """
        Verifica rate limit usando sliding window.
        Retorna True se permitido, False se limitado.
        """
        if not self.is_connected:
            return True  # Permitir se Redis não disponível
        
        try:
            current = int(datetime.now().timestamp())
            window_start = current - window_seconds
            
            pipe = self._client.pipeline()
            
            # Remover entradas antigas
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Contar requisições na janela
            pipe.zcard(key)
            
            # Adicionar nova requisição
            pipe.zadd(key, {str(current): current})
            
            # Definir TTL
            pipe.expire(key, window_seconds)
            
            results = pipe.execute()
            request_count = results[1]
            
            return request_count < max_requests
            
        except Exception as e:
            logger.error(f"Erro no rate limit: {e}")
            return True
    
    # ==========================================
    # PUB/SUB
    # ==========================================
    
    def publish(self, channel: str, message: Any) -> bool:
        """Publica mensagem em um canal"""
        if not self.is_connected:
            return False
        
        try:
            if isinstance(message, (dict, list)):
                message = json.dumps(message)
            
            self._client.publish(channel, message)
            return True
            
        except Exception as e:
            logger.error(f"Erro ao publicar: {e}")
            return False
    
    def subscribe(self, channels: List[str], callback):
        """
        Assina canais e processa mensagens
        """
        if not self.is_connected:
            return
        
        try:
            self._pubsub = self._client.pubsub()
            self._pubsub.subscribe(**{ch: callback for ch in channels})
            
            logger.info(f"Inscrito em canais: {channels}")
            
        except Exception as e:
            logger.error(f"Erro ao assinar canais: {e}")
    
    # ==========================================
    # LOCKS DISTRIBUÍDOS
    # ==========================================
    
    def acquire_lock(self, lock_name: str, timeout: int = 10) -> bool:
        """Adquire um lock distribuído"""
        if not self.is_connected:
            return True  # Permitir se Redis não disponível
        
        try:
            lock_key = f"lock:{lock_name}"
            acquired = self._client.set(lock_key, "locked", nx=True, ex=timeout)
            return acquired is not None
            
        except Exception as e:
            logger.error(f"Erro ao adquirir lock: {e}")
            return True
    
    def release_lock(self, lock_name: str) -> bool:
        """Libera um lock"""
        if not self.is_connected:
            return True
        
        try:
            lock_key = f"lock:{lock_name}"
            self._client.delete(lock_key)
            return True
            
        except Exception as e:
            logger.error(f"Erro ao liberar lock: {e}")
            return False


# Singleton
_redis_client = None

def get_redis_client(config: Dict = None) -> RedisClient:
    """Retorna instância singleton"""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient(config or {})
    return _redis_client
