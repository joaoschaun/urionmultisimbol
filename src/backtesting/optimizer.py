"""
Hyperparameter Optimization
Otimização de parâmetros de estratégias com Optuna

Features:
- Integração com Optuna
- Múltiplos algoritmos de otimização
- Walk-forward analysis
- Visualização de resultados
- Pruning de trials ruins
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Callable, Type
from dataclasses import dataclass
from loguru import logger

try:
    import optuna
    from optuna.pruners import MedianPruner, HyperbandPruner
    from optuna.samplers import TPESampler, CmaEsSampler
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False
    logger.warning("Optuna não instalado. Instale com: pip install optuna")

from .engine import BacktestEngine, BaseStrategy, BacktestResult


@dataclass
class OptimizationResult:
    """Resultado da otimização"""
    best_params: Dict[str, Any]
    best_value: float
    all_trials: List[Dict]
    study_name: str
    n_trials: int
    optimization_time: float
    
    def summary(self) -> str:
        return f"""
╔══════════════════════════════════════════╗
║      OPTIMIZATION RESULT SUMMARY         ║
╠══════════════════════════════════════════╣
║ Study: {self.study_name}
║ Trials: {self.n_trials}
║ Time: {self.optimization_time:.1f}s
║ Best Value: {self.best_value:.4f}
╠══════════════════════════════════════════╣
║ Best Parameters:
"""+ '\n'.join([f"║   {k}: {v}" for k, v in self.best_params.items()]) + """
╚══════════════════════════════════════════╝
"""


class StrategyOptimizer:
    """
    Otimizador de Estratégias usando Optuna
    
    Features:
    - TPE (Tree-structured Parzen Estimator)
    - CMA-ES
    - Pruning automático
    - Walk-forward validation
    """
    
    def __init__(
        self,
        strategy_class: Type[BaseStrategy],
        param_space: Dict[str, Any],
        data: pd.DataFrame,
        symbol: str = "EURUSD",
        initial_balance: float = 10000,
        metric: str = "sharpe",  # sharpe, sortino, profit_factor, sqn, pnl
        direction: str = "maximize"
    ):
        """
        Inicializa o otimizador
        
        Args:
            strategy_class: Classe da estratégia a otimizar
            param_space: Espaço de parâmetros
            data: Dados para backtest
            symbol: Símbolo
            initial_balance: Saldo inicial
            metric: Métrica a otimizar
            direction: 'maximize' ou 'minimize'
        """
        if not OPTUNA_AVAILABLE:
            raise ImportError("Optuna não está instalado")
        
        self.strategy_class = strategy_class
        self.param_space = param_space
        self.data = data
        self.symbol = symbol
        self.initial_balance = initial_balance
        self.metric = metric
        self.direction = direction
        
        self._study: Optional[optuna.Study] = None
        self._best_result: Optional[BacktestResult] = None
        
        logger.info(
            f"🔬 Optimizer inicializado | "
            f"Strategy: {strategy_class.__name__} | "
            f"Metric: {metric} | "
            f"Params: {len(param_space)}"
        )
    
    def _sample_params(self, trial: optuna.Trial) -> Dict[str, Any]:
        """Amostra parâmetros do espaço de busca"""
        params = {}
        
        for name, config in self.param_space.items():
            if isinstance(config, tuple) and len(config) == 2:
                # Range numérico (min, max)
                if isinstance(config[0], int) and isinstance(config[1], int):
                    params[name] = trial.suggest_int(name, config[0], config[1])
                else:
                    params[name] = trial.suggest_float(name, config[0], config[1])
            
            elif isinstance(config, tuple) and len(config) == 3:
                # Range com step
                if isinstance(config[2], int):
                    params[name] = trial.suggest_int(name, config[0], config[1], step=config[2])
                else:
                    params[name] = trial.suggest_float(name, config[0], config[1], step=config[2])
            
            elif isinstance(config, list):
                # Categorical
                params[name] = trial.suggest_categorical(name, config)
            
            elif isinstance(config, dict):
                # Configuração detalhada
                param_type = config.get('type', 'float')
                
                if param_type == 'int':
                    params[name] = trial.suggest_int(
                        name,
                        config['low'],
                        config['high'],
                        step=config.get('step', 1),
                        log=config.get('log', False)
                    )
                elif param_type == 'float':
                    params[name] = trial.suggest_float(
                        name,
                        config['low'],
                        config['high'],
                        step=config.get('step'),
                        log=config.get('log', False)
                    )
                elif param_type == 'categorical':
                    params[name] = trial.suggest_categorical(name, config['choices'])
        
        return params
    
    def _objective(self, trial: optuna.Trial) -> float:
        """Função objetivo para Optuna"""
        # Amostrar parâmetros
        params = self._sample_params(trial)
        
        try:
            # Criar estratégia com parâmetros
            strategy = self.strategy_class(**params)
            
            # Executar backtest
            engine = BacktestEngine(initial_balance=self.initial_balance)
            result = engine.run(strategy, self.data, self.symbol)
            
            # Obter métrica
            if self.metric == "sharpe":
                value = result.sharpe_ratio
            elif self.metric == "sortino":
                value = result.sortino_ratio
            elif self.metric == "profit_factor":
                value = result.profit_factor
            elif self.metric == "sqn":
                value = result.sqn
            elif self.metric == "pnl":
                value = result.total_pnl
            elif self.metric == "win_rate":
                value = result.win_rate
            elif self.metric == "calmar":
                value = result.calmar_ratio
            else:
                value = result.sharpe_ratio
            
            # Penalizar se poucos trades
            if result.total_trades < 10:
                value *= 0.5
            
            # Registrar métricas adicionais
            trial.set_user_attr("total_trades", result.total_trades)
            trial.set_user_attr("win_rate", result.win_rate)
            trial.set_user_attr("total_pnl", result.total_pnl)
            trial.set_user_attr("max_drawdown", result.max_drawdown_pct)
            
            return value
            
        except Exception as e:
            logger.warning(f"Trial falhou: {e}")
            return float('-inf') if self.direction == "maximize" else float('inf')
    
    def optimize(
        self,
        n_trials: int = 100,
        timeout: Optional[float] = None,
        n_jobs: int = 1,
        show_progress_bar: bool = True,
        sampler: str = "tpe",
        pruner: str = "hyperband"
    ) -> OptimizationResult:
        """
        Executa otimização
        
        Args:
            n_trials: Número de trials
            timeout: Timeout em segundos
            n_jobs: Número de jobs paralelos
            show_progress_bar: Mostrar barra de progresso
            sampler: 'tpe' ou 'cmaes'
            pruner: 'median' ou 'hyperband'
            
        Returns:
            OptimizationResult
        """
        start_time = datetime.now()
        
        # Criar sampler
        if sampler == "cmaes":
            optuna_sampler = CmaEsSampler()
        else:
            optuna_sampler = TPESampler(n_startup_trials=10)
        
        # Criar pruner
        if pruner == "median":
            optuna_pruner = MedianPruner()
        else:
            optuna_pruner = HyperbandPruner()
        
        # Criar estudo
        study_name = f"{self.strategy_class.__name__}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self._study = optuna.create_study(
            study_name=study_name,
            direction=self.direction,
            sampler=optuna_sampler,
            pruner=optuna_pruner
        )
        
        # Otimizar
        logger.info(f"🚀 Iniciando otimização | Trials: {n_trials} | Sampler: {sampler}")
        
        self._study.optimize(
            self._objective,
            n_trials=n_trials,
            timeout=timeout,
            n_jobs=n_jobs,
            show_progress_bar=show_progress_bar
        )
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        # Coletar resultados
        all_trials = []
        for trial in self._study.trials:
            trial_info = {
                'number': trial.number,
                'value': trial.value,
                'params': trial.params,
                'state': trial.state.name,
            }
            trial_info.update(trial.user_attrs)
            all_trials.append(trial_info)
        
        result = OptimizationResult(
            best_params=self._study.best_params,
            best_value=self._study.best_value,
            all_trials=all_trials,
            study_name=study_name,
            n_trials=len(self._study.trials),
            optimization_time=elapsed
        )
        
        logger.success(
            f"✅ Otimização concluída em {elapsed:.1f}s | "
            f"Best {self.metric}: {result.best_value:.4f}"
        )
        
        return result
    
    def walk_forward_optimize(
        self,
        n_splits: int = 5,
        train_ratio: float = 0.7,
        n_trials_per_split: int = 50
    ) -> List[OptimizationResult]:
        """
        Walk-Forward Optimization
        
        Divide dados em janelas treino/teste e otimiza em cada uma
        
        Args:
            n_splits: Número de divisões
            train_ratio: Proporção de treino
            n_trials_per_split: Trials por divisão
            
        Returns:
            Lista de resultados por divisão
        """
        results = []
        n_samples = len(self.data)
        split_size = n_samples // n_splits
        
        logger.info(f"🔄 Walk-Forward Optimization | Splits: {n_splits}")
        
        for i in range(n_splits):
            start_idx = i * split_size
            end_idx = min((i + 2) * split_size, n_samples)
            
            # Divisão treino/teste
            split_data = self.data.iloc[start_idx:end_idx].copy()
            train_end = int(len(split_data) * train_ratio)
            
            train_data = split_data.iloc[:train_end]
            test_data = split_data.iloc[train_end:]
            
            logger.info(f"Split {i+1}/{n_splits} | Train: {len(train_data)} | Test: {len(test_data)}")
            
            # Otimizar em treino
            original_data = self.data
            self.data = train_data
            
            result = self.optimize(
                n_trials=n_trials_per_split,
                show_progress_bar=False
            )
            
            # Validar em teste
            strategy = self.strategy_class(**result.best_params)
            engine = BacktestEngine(initial_balance=self.initial_balance)
            test_result = engine.run(strategy, test_data, self.symbol)
            
            logger.info(
                f"Split {i+1} | Train {self.metric}: {result.best_value:.4f} | "
                f"Test Sharpe: {test_result.sharpe_ratio:.4f}"
            )
            
            results.append(result)
            self.data = original_data
        
        return results
    
    def get_importance(self) -> Dict[str, float]:
        """Retorna importância de cada parâmetro"""
        if self._study is None:
            return {}
        
        try:
            importance = optuna.importance.get_param_importances(self._study)
            return importance
        except:
            return {}
    
    def plot_optimization_history(self):
        """Plota histórico de otimização"""
        if self._study is None:
            return
        
        try:
            optuna.visualization.plot_optimization_history(self._study)
        except:
            pass
    
    def plot_param_importances(self):
        """Plota importância dos parâmetros"""
        if self._study is None:
            return
        
        try:
            optuna.visualization.plot_param_importances(self._study)
        except:
            pass


# ==================== Espaço de Parâmetros Pré-definidos ====================

PARAM_SPACES = {
    "sma_crossover": {
        "fast_period": (5, 50),
        "slow_period": (20, 200),
        "atr_period": (7, 21),
        "atr_sl_mult": (1.0, 3.0, 0.5),
        "atr_tp_mult": (1.5, 5.0, 0.5),
    },
    
    "rsi_strategy": {
        "rsi_period": (7, 21),
        "rsi_oversold": (20, 40),
        "rsi_overbought": (60, 80),
        "atr_period": (7, 21),
    },
    
    "macd_strategy": {
        "fast_period": (8, 16),
        "slow_period": (21, 32),
        "signal_period": (7, 12),
    },
    
    "bollinger_strategy": {
        "period": (10, 30),
        "std_dev": (1.5, 3.0, 0.25),
        "atr_period": (10, 20),
    },
    
    "trend_following": {
        "trend_period": (50, 200, 10),
        "entry_period": (10, 30),
        "atr_period": (10, 20),
        "atr_mult": (1.5, 3.0, 0.5),
    }
}


def get_param_space(strategy_type: str) -> Dict[str, Any]:
    """Retorna espaço de parâmetros para tipo de estratégia"""
    return PARAM_SPACES.get(strategy_type, {})


# Exemplo de uso:
"""
from backtesting.optimizer import StrategyOptimizer, get_param_space
from backtesting.engine import SMAStrategy

# Preparar dados
data = dm.prepare_for_backtest('EURUSD', Timeframe.H1)

# Definir espaço de parâmetros
param_space = {
    'fast_period': (5, 30),
    'slow_period': (20, 100),
    'atr_period': (10, 20),
}

# Criar otimizador
optimizer = StrategyOptimizer(
    strategy_class=SMAStrategy,
    param_space=param_space,
    data=data,
    metric='sharpe'
)

# Otimizar
result = optimizer.optimize(n_trials=100)
print(result.summary())

# Walk-forward
results = optimizer.walk_forward_optimize(n_splits=5)
"""
