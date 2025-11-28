"""
Configuration Manager
Handles loading and managing configuration from YAML and environment variables
"""
import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv
from loguru import logger


class ConfigManager:
    """Manages application configuration"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """
        Initialize Configuration Manager
        
        Args:
            config_path: Path to YAML configuration file
        """
        self.config_path = Path(config_path)
        self.config = {}
        self.load_env()
        self.load_config()
    
    def load_env(self):
        """Load environment variables from .env file"""
        # Tentar múltiplos caminhos para .env
        env_paths = [
            Path(".env"),                           # Diretório atual
            Path(__file__).parent.parent / ".env",  # src/../.env (raiz do projeto)
            Path(__file__).parent.parent.parent / ".env"  # Caso esteja em src/core
        ]
        
        for env_path in env_paths:
            if env_path.exists():
                load_dotenv(env_path)
                logger.debug(f"✅ .env carregado de: {env_path}")
                return
        
        logger.warning("⚠️ Arquivo .env não encontrado em nenhum caminho esperado")
    
    def load_config(self):
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_path}"
            )
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        # Replace environment variable placeholders
        self.config = self._replace_env_vars(self.config)
    
    def _replace_env_vars(self, data: Any) -> Any:
        """
        Recursively replace ${VAR} with environment variables
        
        Args:
            data: Data structure to process
            
        Returns:
            Data with environment variables replaced
        """
        if isinstance(data, dict):
            return {
                key: self._replace_env_vars(value) 
                for key, value in data.items()
            }
        elif isinstance(data, list):
            return [self._replace_env_vars(item) for item in data]
        elif isinstance(data, str) and data.startswith('${') and data.endswith('}'):
            env_var = data[2:-1]
            return os.getenv(env_var, data)
        else:
            return data
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key
        
        Args:
            key: Configuration key (supports dot notation, e.g., 'mt5.login')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        # Check environment variables first
        env_value = os.getenv(key)
        if env_value is not None:
            return env_value
        
        # Navigate nested dictionary
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            
            if value is None:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """
        Set configuration value
        
        Args:
            key: Configuration key (supports dot notation)
            value: Value to set
        """
        keys = key.split('.')
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def save(self, path: Optional[str] = None):
        """
        Save configuration to YAML file
        
        Args:
            path: Optional path to save to (uses original path if not specified)
        """
        save_path = Path(path) if path else self.config_path
        
        with open(save_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)
    
    def reload(self):
        """Reload configuration from file"""
        self.load_config()
    
    def get_all(self) -> Dict:
        """
        Get entire configuration dictionary
        
        Returns:
            Complete configuration dictionary
        """
        return self.config.copy()
