# -*- coding: utf-8 -*-
"""
Walk-Forward Optimization Integration
======================================
Modulo para integracao com otimizacao walk-forward.
Permite validar estrategias de forma robusta antes de usar em producao.

Conceito Walk-Forward:
1. Divide dados em janelas (in-sample e out-of-sample)
2. Otimiza parametros no in-sample
3. Valida no out-of-sample
4. Repete movendo a janela
5. Combina resultados para avaliar robustez
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from loguru import logger
import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
import itertools


class WalkForwardStatus(Enum):
    """Status da otimizacao"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class OptimizationWindow:
    """Uma janela de otimizacao"""
    id: int
    in_sample_start: datetime
    in_sample_end: datetime
    out_sample_start: datetime
    out_sample_end: datetime
    
    # Resultados
    best_params: Dict = field(default_factory=dict)
    in_sample_metrics: Dict = field(default_factory=dict)
    out_sample_metrics: Dict = field(default_factory=dict)
    
    status: WalkForwardStatus = WalkForwardStatus.PENDING


@dataclass
class WalkForwardResult:
    """Resultado completo da otimizacao walk-forward"""
    strategy_name: str
    windows: List[OptimizationWindow] = field(default_factory=list)
    
    # Metricas agregadas
    avg_out_sample_return: float = 0.0
    avg_out_sample_sharpe: float = 0.0
    avg_out_sample_max_dd: float = 0.0
    
    # Robustez
    win_rate: float = 0.0  # % de janelas lucrativas
    stability_ratio: float = 0.0  # IS performance / OOS performance
    parameter_stability: float = 0.0  # Variacao dos parametros otimos
    
    # Parametros recomendados (media ou mais estavel)
    recommended_params: Dict = field(default_factory=dict)
    
    created_at: datetime = field(default_factory=datetime.now)


class WalkForwardOptimizer:
    """
    Otimizador Walk-Forward
    """
    
    def __init__(self, config: Dict, data_dir: str = None):
        self.config = config
        self.wf_config = config.get('walk_forward', {})
        
        # Configuracoes
        self.in_sample_ratio = self.wf_config.get('in_sample_ratio', 0.7)
        self.num_windows = self.wf_config.get('num_windows', 5)
        self.min_trades_per_window = self.wf_config.get('min_trades', 30)
        self.optimization_metric = self.wf_config.get('metric', 'sharpe')
        
        # Diretorio para salvar resultados
        self.data_dir = data_dir or 'data/walk_forward'
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Resultados
        self._results: Dict[str, WalkForwardResult] = {}
        
        logger.info("WalkForwardOptimizer inicializado")
    
    def create_windows(self, start_date: datetime, end_date: datetime,
                      num_windows: int = None) -> List[OptimizationWindow]:
        """
        Cria janelas de otimizacao
        """
        num_windows = num_windows or self.num_windows
        
        total_days = (end_date - start_date).days
        window_size = total_days // num_windows
        
        in_sample_days = int(window_size * self.in_sample_ratio)
        out_sample_days = window_size - in_sample_days
        
        windows = []
        current_start = start_date
        
        for i in range(num_windows):
            in_sample_start = current_start
            in_sample_end = in_sample_start + timedelta(days=in_sample_days)
            out_sample_start = in_sample_end
            out_sample_end = out_sample_start + timedelta(days=out_sample_days)
            
            window = OptimizationWindow(
                id=i + 1,
                in_sample_start=in_sample_start,
                in_sample_end=in_sample_end,
                out_sample_start=out_sample_start,
                out_sample_end=out_sample_end
            )
            
            windows.append(window)
            current_start = out_sample_start  # Proxima janela comeca apos out-sample
        
        logger.info(f"Criadas {len(windows)} janelas de otimizacao")
        
        return windows
    
    def optimize_window(self, window: OptimizationWindow,
                       data: pd.DataFrame,
                       strategy_func: Callable,
                       param_grid: Dict) -> OptimizationWindow:
        """
        Otimiza uma janela individual
        """
        window.status = WalkForwardStatus.RUNNING
        
        try:
            # Filtrar dados para in-sample
            in_sample_data = data[
                (data.index >= window.in_sample_start) &
                (data.index < window.in_sample_end)
            ]
            
            # Filtrar dados para out-of-sample
            out_sample_data = data[
                (data.index >= window.out_sample_start) &
                (data.index < window.out_sample_end)
            ]
            
            if len(in_sample_data) < 100 or len(out_sample_data) < 30:
                logger.warning(f"Janela {window.id}: dados insuficientes")
                window.status = WalkForwardStatus.FAILED
                return window
            
            # Grid search no in-sample
            best_score = float('-inf')
            best_params = {}
            
            # Gerar todas as combinacoes de parametros
            param_combinations = self._generate_param_combinations(param_grid)
            
            for params in param_combinations:
                try:
                    # Executar estrategia com esses parametros
                    trades = strategy_func(in_sample_data, params)
                    
                    if len(trades) < self.min_trades_per_window:
                        continue
                    
                    # Calcular metrica de otimizacao
                    metrics = self._calculate_metrics(trades)
                    score = metrics.get(self.optimization_metric, 0)
                    
                    if score > best_score:
                        best_score = score
                        best_params = params
                        window.in_sample_metrics = metrics
                        
                except Exception as e:
                    logger.debug(f"Erro testando params {params}: {e}")
                    continue
            
            if not best_params:
                logger.warning(f"Janela {window.id}: nenhum parametro valido encontrado")
                window.status = WalkForwardStatus.FAILED
                return window
            
            window.best_params = best_params
            
            # Validar no out-of-sample
            out_trades = strategy_func(out_sample_data, best_params)
            window.out_sample_metrics = self._calculate_metrics(out_trades)
            
            window.status = WalkForwardStatus.COMPLETED
            
            logger.info(f"Janela {window.id} completa: IS Sharpe={window.in_sample_metrics.get('sharpe', 0):.2f}, OOS Sharpe={window.out_sample_metrics.get('sharpe', 0):.2f}")
            
        except Exception as e:
            logger.error(f"Erro na janela {window.id}: {e}")
            window.status = WalkForwardStatus.FAILED
        
        return window
    
    def run_walk_forward(self, strategy_name: str,
                        data: pd.DataFrame,
                        strategy_func: Callable,
                        param_grid: Dict,
                        start_date: datetime = None,
                        end_date: datetime = None) -> WalkForwardResult:
        """
        Executa otimizacao walk-forward completa
        """
        logger.info(f"Iniciando Walk-Forward para {strategy_name}")
        
        # Determinar periodo
        start_date = start_date or data.index.min()
        end_date = end_date or data.index.max()
        
        # Criar janelas
        windows = self.create_windows(start_date, end_date)
        
        result = WalkForwardResult(
            strategy_name=strategy_name,
            windows=windows
        )
        
        # Otimizar cada janela
        for window in windows:
            self.optimize_window(window, data, strategy_func, param_grid)
        
        # Calcular metricas agregadas
        self._calculate_aggregate_metrics(result)
        
        # Salvar resultado
        self._save_result(result)
        self._results[strategy_name] = result
        
        logger.info(f"Walk-Forward completo: Win Rate={result.win_rate:.1%}, Stability={result.stability_ratio:.2f}")
        
        return result
    
    def _generate_param_combinations(self, param_grid: Dict) -> List[Dict]:
        """Gera todas as combinacoes de parametros"""
        keys = param_grid.keys()
        values = param_grid.values()
        
        combinations = []
        for combo in itertools.product(*values):
            combinations.append(dict(zip(keys, combo)))
        
        return combinations
    
    def _calculate_metrics(self, trades: List[Dict]) -> Dict:
        """Calcula metricas de performance"""
        if not trades:
            return {}
        
        returns = [t.get('pnl_percent', 0) for t in trades]
        
        total_return = sum(returns)
        avg_return = np.mean(returns) if returns else 0
        std_return = np.std(returns) if len(returns) > 1 else 0
        
        # Sharpe (anualizado, assumindo trades diarios)
        sharpe = (avg_return / std_return) * np.sqrt(252) if std_return > 0 else 0
        
        # Win rate
        wins = [r for r in returns if r > 0]
        win_rate = len(wins) / len(returns) if returns else 0
        
        # Max drawdown
        cumulative = np.cumsum(returns)
        peak = np.maximum.accumulate(cumulative)
        drawdown = peak - cumulative
        max_dd = np.max(drawdown) if len(drawdown) > 0 else 0
        
        # Profit factor
        gross_profit = sum([r for r in returns if r > 0])
        gross_loss = abs(sum([r for r in returns if r < 0]))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        return {
            'total_return': total_return,
            'avg_return': avg_return,
            'sharpe': sharpe,
            'win_rate': win_rate,
            'max_drawdown': max_dd,
            'profit_factor': profit_factor,
            'num_trades': len(trades)
        }
    
    def _calculate_aggregate_metrics(self, result: WalkForwardResult):
        """Calcula metricas agregadas do walk-forward"""
        completed_windows = [w for w in result.windows if w.status == WalkForwardStatus.COMPLETED]
        
        if not completed_windows:
            return
        
        # Metricas OOS
        oos_returns = [w.out_sample_metrics.get('total_return', 0) for w in completed_windows]
        oos_sharpes = [w.out_sample_metrics.get('sharpe', 0) for w in completed_windows]
        oos_dds = [w.out_sample_metrics.get('max_drawdown', 0) for w in completed_windows]
        
        result.avg_out_sample_return = np.mean(oos_returns)
        result.avg_out_sample_sharpe = np.mean(oos_sharpes)
        result.avg_out_sample_max_dd = np.mean(oos_dds)
        
        # Win rate (% de janelas com retorno positivo OOS)
        positive_windows = [r for r in oos_returns if r > 0]
        result.win_rate = len(positive_windows) / len(oos_returns)
        
        # Stability ratio (OOS / IS performance)
        is_returns = [w.in_sample_metrics.get('total_return', 0) for w in completed_windows]
        avg_is = np.mean(is_returns) if is_returns else 0
        result.stability_ratio = result.avg_out_sample_return / avg_is if avg_is != 0 else 0
        
        # Parameter stability (variacao nos parametros otimos)
        result.parameter_stability = self._calculate_param_stability(completed_windows)
        
        # Parametros recomendados (media ou mais frequente)
        result.recommended_params = self._get_recommended_params(completed_windows)
    
    def _calculate_param_stability(self, windows: List[OptimizationWindow]) -> float:
        """Calcula estabilidade dos parametros (0-1, maior = mais estavel)"""
        if len(windows) < 2:
            return 1.0
        
        # Coletar todos os parametros
        all_params = [w.best_params for w in windows if w.best_params]
        
        if not all_params:
            return 0.0
        
        # Para cada parametro, calcular coeficiente de variacao
        param_keys = all_params[0].keys()
        cv_scores = []
        
        for key in param_keys:
            values = [p.get(key, 0) for p in all_params if isinstance(p.get(key), (int, float))]
            if values and len(values) > 1:
                mean_val = np.mean(values)
                std_val = np.std(values)
                cv = std_val / mean_val if mean_val != 0 else 1
                cv_scores.append(1 - min(cv, 1))  # Inverter para que maior = mais estavel
        
        return np.mean(cv_scores) if cv_scores else 0.5
    
    def _get_recommended_params(self, windows: List[OptimizationWindow]) -> Dict:
        """Retorna parametros recomendados baseado em todas as janelas"""
        all_params = [w.best_params for w in windows if w.best_params]
        
        if not all_params:
            return {}
        
        # Para parametros numericos, usar media
        # Para categoricos, usar moda
        recommended = {}
        param_keys = all_params[0].keys()
        
        for key in param_keys:
            values = [p.get(key) for p in all_params]
            
            if all(isinstance(v, (int, float)) for v in values):
                # Numerico - usar mediana (mais robusto que media)
                recommended[key] = float(np.median(values))
            else:
                # Categorico - usar moda
                from collections import Counter
                counter = Counter(values)
                recommended[key] = counter.most_common(1)[0][0]
        
        return recommended
    
    def _save_result(self, result: WalkForwardResult):
        """Salva resultado em disco"""
        filename = f"{result.strategy_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(self.data_dir, filename)
        
        # Converter para dict serializavel
        data = {
            'strategy_name': result.strategy_name,
            'created_at': result.created_at.isoformat(),
            'avg_out_sample_return': result.avg_out_sample_return,
            'avg_out_sample_sharpe': result.avg_out_sample_sharpe,
            'avg_out_sample_max_dd': result.avg_out_sample_max_dd,
            'win_rate': result.win_rate,
            'stability_ratio': result.stability_ratio,
            'parameter_stability': result.parameter_stability,
            'recommended_params': result.recommended_params,
            'windows': []
        }
        
        for w in result.windows:
            data['windows'].append({
                'id': w.id,
                'in_sample_start': w.in_sample_start.isoformat(),
                'in_sample_end': w.in_sample_end.isoformat(),
                'out_sample_start': w.out_sample_start.isoformat(),
                'out_sample_end': w.out_sample_end.isoformat(),
                'status': w.status.value,
                'best_params': w.best_params,
                'in_sample_metrics': w.in_sample_metrics,
                'out_sample_metrics': w.out_sample_metrics
            })
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Resultado salvo em {filepath}")
    
    def get_result(self, strategy_name: str) -> Optional[WalkForwardResult]:
        """Retorna resultado de uma estrategia"""
        return self._results.get(strategy_name)
    
    def is_strategy_robust(self, strategy_name: str,
                          min_win_rate: float = 0.6,
                          min_stability: float = 0.5) -> bool:
        """
        Verifica se uma estrategia e robusta o suficiente para producao
        """
        result = self.get_result(strategy_name)
        
        if not result:
            return False
        
        # Criterios de robustez
        checks = [
            result.win_rate >= min_win_rate,
            result.stability_ratio >= min_stability,
            result.avg_out_sample_sharpe > 0,
            result.parameter_stability >= 0.5
        ]
        
        return all(checks)
    
    def get_robustness_report(self, strategy_name: str) -> Dict:
        """Gera relatorio de robustez"""
        result = self.get_result(strategy_name)
        
        if not result:
            return {'error': 'Estrategia nao encontrada'}
        
        return {
            'strategy': strategy_name,
            'windows_completed': len([w for w in result.windows if w.status == WalkForwardStatus.COMPLETED]),
            'windows_total': len(result.windows),
            'metrics': {
                'win_rate': f"{result.win_rate:.1%}",
                'avg_oos_return': f"{result.avg_out_sample_return:.2%}",
                'avg_oos_sharpe': f"{result.avg_out_sample_sharpe:.2f}",
                'avg_oos_max_dd': f"{result.avg_out_sample_max_dd:.2%}",
                'stability_ratio': f"{result.stability_ratio:.2f}",
                'parameter_stability': f"{result.parameter_stability:.2f}"
            },
            'is_robust': self.is_strategy_robust(strategy_name),
            'recommended_params': result.recommended_params,
            'recommendation': self._get_recommendation(result)
        }
    
    def _get_recommendation(self, result: WalkForwardResult) -> str:
        """Gera recomendacao baseada nos resultados"""
        if result.win_rate >= 0.7 and result.stability_ratio >= 0.7:
            return "EXCELENTE - Estrategia altamente robusta, pronta para producao"
        elif result.win_rate >= 0.6 and result.stability_ratio >= 0.5:
            return "BOA - Estrategia robusta, pode ser usada com monitoramento"
        elif result.win_rate >= 0.5 and result.stability_ratio >= 0.3:
            return "MODERADA - Estrategia precisa de mais validacao"
        else:
            return "FRACA - Estrategia possivelmente overfitted, nao recomendada para producao"


# Singleton
_optimizer = None

def get_walk_forward_optimizer(config: Dict = None) -> WalkForwardOptimizer:
    """Retorna instancia singleton"""
    global _optimizer
    if _optimizer is None:
        _optimizer = WalkForwardOptimizer(config or {})
    return _optimizer
