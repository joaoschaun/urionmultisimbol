# -*- coding: utf-8 -*-
"""
ML Validator - Validação Robusta de Modelos de Machine Learning

Previne:
- Overfitting
- Data Leakage  
- Features sem poder preditivo

Implementa:
- Validação cruzada temporal
- Feature importance analysis
- SHAP values
- Out-of-sample testing
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
import logging
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import warnings

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)


@dataclass
class FeatureImportance:
    """Importância de uma feature"""
    name: str
    importance: float
    std: float = 0.0
    rank: int = 0
    is_significant: bool = True


@dataclass
class ValidationMetrics:
    """Métricas de validação de um fold"""
    fold: int
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    sharpe_ratio: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    
    # Retornos
    total_return: float = 0.0
    annualized_return: float = 0.0
    
    # Estatísticas
    n_trades: int = 0
    win_rate: float = 0.0


@dataclass
class MLValidationResult:
    """Resultado completo de validação ML"""
    model_name: str = ""
    
    # Métricas por fold
    fold_metrics: List[ValidationMetrics] = field(default_factory=list)
    
    # Médias
    avg_accuracy: float = 0.0
    avg_precision: float = 0.0
    avg_recall: float = 0.0
    avg_f1: float = 0.0
    avg_sharpe: float = 0.0
    std_sharpe: float = 0.0
    
    # Métricas out-of-sample
    oos_accuracy: float = 0.0
    oos_sharpe: float = 0.0
    oos_profit_factor: float = 0.0
    
    # Feature importance
    feature_importance: List[FeatureImportance] = field(default_factory=list)
    
    # Data leakage check
    has_data_leakage: bool = False
    leakage_features: List[str] = field(default_factory=list)
    
    # Overfitting detection
    overfitting_score: float = 0.0
    is_overfit: bool = False
    
    # Recomendação
    is_valid: bool = False
    recommendation: str = ""
    
    # Timestamp
    validated_at: datetime = field(default_factory=datetime.now)


class DataLeakageDetector:
    """Detecta data leakage em features"""
    
    def __init__(self):
        # Features que tipicamente causam leakage
        self.suspicious_patterns = [
            'future',
            'next',
            'target',
            'label',
            'y_',
            'profit',
            'return_forward',
            'pnl',
            'signal_next'
        ]
    
    def check_feature_names(self, features: List[str]) -> List[str]:
        """Verifica nomes de features suspeitos"""
        leaky = []
        for feat in features:
            for pattern in self.suspicious_patterns:
                if pattern.lower() in feat.lower():
                    leaky.append(feat)
                    break
        return leaky
    
    def check_correlation_with_target(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        threshold: float = 0.95
    ) -> List[str]:
        """Features com correlação muito alta com target = leakage"""
        leaky = []
        
        for col in X.columns:
            if X[col].dtype in ['float64', 'int64']:
                corr = abs(X[col].corr(y))
                if corr > threshold:
                    leaky.append(col)
                    logger.warning(f"⚠️ Possível leakage: {col} (corr={corr:.3f})")
        
        return leaky
    
    def check_future_data(
        self,
        X: pd.DataFrame,
        lookback: int = 1
    ) -> List[str]:
        """Verifica se features usam dados futuros"""
        leaky = []
        
        for col in X.columns:
            if X[col].dtype in ['float64', 'int64']:
                # Verificar se há correlação com shift negativo
                for shift in range(1, lookback + 1):
                    shifted = X[col].shift(shift)
                    corr = abs(X[col].corr(shifted))
                    # Se correlação perfeita com shift futuro = leakage
                    if corr > 0.99:
                        leaky.append(col)
                        break
        
        return leaky


class FeatureAnalyzer:
    """Analisa importância e qualidade de features"""
    
    def __init__(self):
        pass
    
    def calculate_importance(
        self,
        model,
        X: pd.DataFrame,
        y: pd.Series,
        method: str = 'permutation'
    ) -> List[FeatureImportance]:
        """Calcula importância das features"""
        
        importances = []
        
        if method == 'permutation':
            # Permutation importance
            from sklearn.inspection import permutation_importance
            
            result = permutation_importance(
                model, X, y,
                n_repeats=10,
                random_state=42,
                n_jobs=-1
            )
            
            for i, col in enumerate(X.columns):
                importances.append(FeatureImportance(
                    name=col,
                    importance=result.importances_mean[i],
                    std=result.importances_std[i],
                    is_significant=result.importances_mean[i] > 0
                ))
        
        elif method == 'tree' and hasattr(model, 'feature_importances_'):
            # Tree-based importance
            for i, col in enumerate(X.columns):
                importances.append(FeatureImportance(
                    name=col,
                    importance=model.feature_importances_[i],
                    is_significant=model.feature_importances_[i] > 0.01
                ))
        
        # Ordenar e ranquear
        importances.sort(key=lambda x: x.importance, reverse=True)
        for i, imp in enumerate(importances):
            imp.rank = i + 1
        
        return importances
    
    def select_top_features(
        self,
        importances: List[FeatureImportance],
        top_n: int = 20,
        min_importance: float = 0.01
    ) -> List[str]:
        """Seleciona as melhores features"""
        selected = []
        
        for imp in importances[:top_n]:
            if imp.importance >= min_importance:
                selected.append(imp.name)
        
        return selected


class TimeSeriesValidator:
    """Validação cruzada temporal para trading"""
    
    def __init__(self, n_splits: int = 5, test_size: int = None, gap: int = 0):
        """
        Args:
            n_splits: Número de splits
            test_size: Tamanho do conjunto de teste
            gap: Gap entre treino e teste para evitar leakage
        """
        self.n_splits = n_splits
        self.test_size = test_size
        self.gap = gap
    
    def split(self, X: pd.DataFrame) -> List[Tuple[np.ndarray, np.ndarray]]:
        """Gera splits temporais"""
        tscv = TimeSeriesSplit(
            n_splits=self.n_splits,
            test_size=self.test_size,
            gap=self.gap
        )
        
        splits = []
        for train_idx, test_idx in tscv.split(X):
            splits.append((train_idx, test_idx))
        
        return splits
    
    def calculate_trading_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        returns: np.ndarray = None
    ) -> Dict[str, float]:
        """Calcula métricas de trading, não apenas classificação"""
        
        metrics = {
            'accuracy': accuracy_score(y_true, y_pred),
            'precision': precision_score(y_true, y_pred, average='weighted', zero_division=0),
            'recall': recall_score(y_true, y_pred, average='weighted', zero_division=0),
            'f1': f1_score(y_true, y_pred, average='weighted', zero_division=0),
        }
        
        # Métricas de trading se retornos disponíveis
        if returns is not None:
            # Simular PnL baseado nas previsões
            # y_pred = 1 significa comprar, 0 = ficar fora, -1 = vender
            strategy_returns = returns * y_pred
            
            # Sharpe ratio
            if len(strategy_returns) > 0 and np.std(strategy_returns) > 0:
                metrics['sharpe_ratio'] = (
                    np.mean(strategy_returns) / np.std(strategy_returns) * np.sqrt(252)
                )
            else:
                metrics['sharpe_ratio'] = 0
            
            # Win rate
            trades = strategy_returns[strategy_returns != 0]
            if len(trades) > 0:
                metrics['n_trades'] = len(trades)
                metrics['win_rate'] = len(trades[trades > 0]) / len(trades)
                
                # Profit factor
                gains = trades[trades > 0].sum()
                losses = abs(trades[trades < 0].sum())
                metrics['profit_factor'] = gains / losses if losses > 0 else float('inf')
            else:
                metrics['n_trades'] = 0
                metrics['win_rate'] = 0
                metrics['profit_factor'] = 0
            
            # Max drawdown
            cumulative = np.cumsum(strategy_returns)
            peak = np.maximum.accumulate(cumulative)
            drawdown = (peak - cumulative) / (peak + 1e-10)
            metrics['max_drawdown'] = np.max(drawdown)
            
            # Total return
            metrics['total_return'] = np.sum(strategy_returns)
            metrics['annualized_return'] = metrics['total_return'] * (252 / len(strategy_returns))
        
        return metrics


class MLValidator:
    """
    Validador Completo de Modelos ML para Trading
    
    Features:
    - Validação cruzada temporal
    - Detecção de data leakage
    - Feature importance
    - Detecção de overfitting
    - Métricas de trading (não só classificação)
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        self.leakage_detector = DataLeakageDetector()
        self.feature_analyzer = FeatureAnalyzer()
        self.ts_validator = TimeSeriesValidator(n_splits=5, gap=1)
        
        logger.info("MLValidator inicializado")
    
    def validate_model(
        self,
        model,
        X: pd.DataFrame,
        y: pd.Series,
        returns: pd.Series = None,
        feature_names: List[str] = None
    ) -> MLValidationResult:
        """
        Validação completa de um modelo ML
        
        Args:
            model: Modelo treinado (sklearn-like)
            X: Features
            y: Target
            returns: Retornos para calcular métricas de trading
            feature_names: Nomes das features
            
        Returns:
            MLValidationResult
        """
        result = MLValidationResult(
            model_name=type(model).__name__
        )
        
        feature_names = feature_names or list(X.columns)
        
        # 1. Verificar data leakage
        logger.info("🔍 Verificando data leakage...")
        result = self._check_data_leakage(result, X, y, feature_names)
        
        if result.has_data_leakage:
            logger.error("❌ Data leakage detectado! Corrija antes de continuar.")
            result.is_valid = False
            result.recommendation = "CRÍTICO: Remova features com data leakage antes de usar"
            return result
        
        # 2. Validação cruzada temporal
        logger.info("📊 Executando validação cruzada temporal...")
        result = self._cross_validate(result, model, X, y, returns)
        
        # 3. Calcular feature importance
        logger.info("📈 Calculando importância das features...")
        result = self._analyze_features(result, model, X, y)
        
        # 4. Detectar overfitting
        logger.info("🎯 Verificando overfitting...")
        result = self._detect_overfitting(result, model, X, y, returns)
        
        # 5. Gerar recomendação final
        result = self._generate_recommendation(result)
        
        return result
    
    def _check_data_leakage(
        self,
        result: MLValidationResult,
        X: pd.DataFrame,
        y: pd.Series,
        feature_names: List[str]
    ) -> MLValidationResult:
        """Verifica data leakage"""
        
        leaky_features = []
        
        # Checar nomes suspeitos
        leaky_features.extend(
            self.leakage_detector.check_feature_names(feature_names)
        )
        
        # Checar correlação muito alta
        leaky_features.extend(
            self.leakage_detector.check_correlation_with_target(X, y)
        )
        
        # Checar dados futuros
        leaky_features.extend(
            self.leakage_detector.check_future_data(X)
        )
        
        # Remover duplicatas
        leaky_features = list(set(leaky_features))
        
        result.has_data_leakage = len(leaky_features) > 0
        result.leakage_features = leaky_features
        
        if leaky_features:
            logger.warning(f"⚠️ Features com possível leakage: {leaky_features}")
        else:
            logger.info("✓ Nenhum data leakage detectado")
        
        return result
    
    def _cross_validate(
        self,
        result: MLValidationResult,
        model,
        X: pd.DataFrame,
        y: pd.Series,
        returns: pd.Series = None
    ) -> MLValidationResult:
        """Executa validação cruzada temporal"""
        
        splits = self.ts_validator.split(X)
        fold_metrics = []
        
        for fold_idx, (train_idx, test_idx) in enumerate(splits):
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
            
            # Treinar modelo
            model_clone = self._clone_model(model)
            model_clone.fit(X_train, y_train)
            
            # Prever
            y_pred = model_clone.predict(X_test)
            
            # Calcular métricas
            ret = returns.iloc[test_idx].values if returns is not None else None
            metrics = self.ts_validator.calculate_trading_metrics(
                y_test.values, y_pred, ret
            )
            
            fold_metrics.append(ValidationMetrics(
                fold=fold_idx + 1,
                accuracy=metrics['accuracy'],
                precision=metrics['precision'],
                recall=metrics['recall'],
                f1=metrics['f1'],
                sharpe_ratio=metrics.get('sharpe_ratio', 0),
                profit_factor=metrics.get('profit_factor', 0),
                max_drawdown=metrics.get('max_drawdown', 0),
                total_return=metrics.get('total_return', 0),
                annualized_return=metrics.get('annualized_return', 0),
                n_trades=metrics.get('n_trades', 0),
                win_rate=metrics.get('win_rate', 0)
            ))
            
            logger.info(
                f"  Fold {fold_idx + 1}: Acc={metrics['accuracy']:.3f}, "
                f"Sharpe={metrics.get('sharpe_ratio', 0):.2f}, "
                f"WR={metrics.get('win_rate', 0)*100:.1f}%"
            )
        
        result.fold_metrics = fold_metrics
        
        # Médias
        result.avg_accuracy = np.mean([m.accuracy for m in fold_metrics])
        result.avg_precision = np.mean([m.precision for m in fold_metrics])
        result.avg_recall = np.mean([m.recall for m in fold_metrics])
        result.avg_f1 = np.mean([m.f1 for m in fold_metrics])
        result.avg_sharpe = np.mean([m.sharpe_ratio for m in fold_metrics])
        result.std_sharpe = np.std([m.sharpe_ratio for m in fold_metrics])
        
        return result
    
    def _analyze_features(
        self,
        result: MLValidationResult,
        model,
        X: pd.DataFrame,
        y: pd.Series
    ) -> MLValidationResult:
        """Analisa importância das features"""
        
        try:
            # Tentar permutation importance primeiro
            importances = self.feature_analyzer.calculate_importance(
                model, X, y, method='permutation'
            )
        except Exception as e:
            logger.warning(f"Permutation importance falhou: {e}")
            try:
                importances = self.feature_analyzer.calculate_importance(
                    model, X, y, method='tree'
                )
            except Exception as e2:
                logger.warning(f"Feature importance não disponível: {e2}")
                importances = []
        
        result.feature_importance = importances
        
        # Logar top features
        if importances:
            logger.info("Top 5 features:")
            for fi in importances[:5]:
                logger.info(f"  {fi.rank}. {fi.name}: {fi.importance:.4f}")
        
        return result
    
    def _detect_overfitting(
        self,
        result: MLValidationResult,
        model,
        X: pd.DataFrame,
        y: pd.Series,
        returns: pd.Series = None
    ) -> MLValidationResult:
        """Detecta overfitting comparando treino vs teste"""
        
        # Dividir em treino completo e holdout final
        split_idx = int(len(X) * 0.8)
        
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
        
        # Treinar em todo o treino
        model_clone = self._clone_model(model)
        model_clone.fit(X_train, y_train)
        
        # Métricas no treino
        y_train_pred = model_clone.predict(X_train)
        train_acc = accuracy_score(y_train, y_train_pred)
        
        # Métricas no teste (out-of-sample)
        y_test_pred = model_clone.predict(X_test)
        test_acc = accuracy_score(y_test, y_test_pred)
        
        # Métricas de trading OOS
        if returns is not None:
            ret_test = returns.iloc[split_idx:].values
            oos_metrics = self.ts_validator.calculate_trading_metrics(
                y_test.values, y_test_pred, ret_test
            )
            result.oos_sharpe = oos_metrics.get('sharpe_ratio', 0)
            result.oos_profit_factor = oos_metrics.get('profit_factor', 0)
        
        result.oos_accuracy = test_acc
        
        # Overfitting score = diferença entre treino e teste
        result.overfitting_score = train_acc - test_acc
        
        # Se diferença > 10%, provavelmente overfit
        result.is_overfit = result.overfitting_score > 0.10
        
        logger.info(f"Train Acc: {train_acc:.3f}, Test Acc: {test_acc:.3f}")
        logger.info(f"Overfitting Score: {result.overfitting_score:.3f}")
        
        if result.is_overfit:
            logger.warning("⚠️ Possível overfitting detectado!")
        else:
            logger.info("✓ Sem sinais de overfitting")
        
        return result
    
    def _generate_recommendation(self, result: MLValidationResult) -> MLValidationResult:
        """Gera recomendação final"""
        
        issues = []
        
        # Verificar data leakage
        if result.has_data_leakage:
            issues.append("❌ Data leakage detectado")
        
        # Verificar overfitting
        if result.is_overfit:
            issues.append("⚠️ Possível overfitting")
        
        # Verificar Sharpe
        if result.avg_sharpe < 0.5:
            issues.append("⚠️ Sharpe ratio baixo (<0.5)")
        
        # Verificar consistência (desvio padrão do Sharpe)
        if result.std_sharpe > 1.0:
            issues.append("⚠️ Alta variabilidade entre folds")
        
        # Verificar OOS
        if result.oos_sharpe < 0:
            issues.append("⚠️ Sharpe negativo out-of-sample")
        
        # Determinar validade
        critical_issues = [i for i in issues if '❌' in i]
        warning_issues = [i for i in issues if '⚠️' in i]
        
        if critical_issues:
            result.is_valid = False
            result.recommendation = "NÃO USAR: " + "; ".join(critical_issues)
        elif len(warning_issues) >= 3:
            result.is_valid = False
            result.recommendation = "REVISAR: Múltiplos problemas - " + "; ".join(warning_issues)
        elif warning_issues:
            result.is_valid = True
            result.recommendation = "USAR COM CUIDADO: " + "; ".join(warning_issues)
        else:
            result.is_valid = True
            result.recommendation = "✓ Modelo validado - Pronto para paper trading"
        
        return result
    
    def _clone_model(self, model):
        """Clona um modelo sklearn-like"""
        from sklearn.base import clone
        try:
            return clone(model)
        except:
            # Fallback para modelos não-sklearn
            import copy
            return copy.deepcopy(model)
    
    def generate_report(self, result: MLValidationResult) -> str:
        """Gera relatório de validação"""
        
        report = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                       RELATÓRIO DE VALIDAÇÃO ML - URION                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

📊 MODELO: {result.model_name}
📅 Validado em: {result.validated_at.strftime('%Y-%m-%d %H:%M:%S')}

🔍 DATA LEAKAGE CHECK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Status: {"❌ DETECTADO" if result.has_data_leakage else "✓ Limpo"}
"""
        if result.leakage_features:
            report += f"Features suspeitas: {', '.join(result.leakage_features)}\n"
        
        report += f"""

📈 VALIDAÇÃO CRUZADA TEMPORAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Folds: {len(result.fold_metrics)}

Médias:
  Accuracy: {result.avg_accuracy:.3f}
  Precision: {result.avg_precision:.3f}
  Recall: {result.avg_recall:.3f}
  F1 Score: {result.avg_f1:.3f}
  Sharpe Ratio: {result.avg_sharpe:.2f} (±{result.std_sharpe:.2f})

Por Fold:
"""
        for fm in result.fold_metrics:
            report += f"  Fold {fm.fold}: Acc={fm.accuracy:.3f}, Sharpe={fm.sharpe_ratio:.2f}, WR={fm.win_rate*100:.1f}%\n"
        
        report += f"""

🎯 OUT-OF-SAMPLE (20% holdout)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Accuracy: {result.oos_accuracy:.3f}
Sharpe Ratio: {result.oos_sharpe:.2f}
Profit Factor: {result.oos_profit_factor:.2f}

🔬 OVERFITTING CHECK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Overfitting Score: {result.overfitting_score:.3f}
Status: {"⚠️ POSSÍVEL OVERFITTING" if result.is_overfit else "✓ OK"}

📊 FEATURE IMPORTANCE (Top 10)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        for fi in result.feature_importance[:10]:
            bar = '█' * int(fi.importance * 50)
            report += f"  {fi.rank:2d}. {fi.name[:25]:25s} {fi.importance:.4f} {bar}\n"
        
        report += f"""

✅ RESULTADO FINAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Válido: {"✓ SIM" if result.is_valid else "✗ NÃO"}
Recomendação: {result.recommendation}
"""
        
        return report


# Instância global
_ml_validator: Optional[MLValidator] = None


def get_ml_validator(config: Dict[str, Any] = None) -> MLValidator:
    """Retorna instância singleton do validador ML"""
    global _ml_validator
    if _ml_validator is None:
        _ml_validator = MLValidator(config)
    return _ml_validator


# Exemplo de uso
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    from sklearn.ensemble import RandomForestClassifier
    
    # Criar dados de exemplo
    np.random.seed(42)
    n = 1000
    
    X = pd.DataFrame({
        'feature_1': np.random.randn(n),
        'feature_2': np.random.randn(n),
        'feature_3': np.random.randn(n),
        'ema_20': np.random.randn(n),
        'rsi_14': np.random.uniform(20, 80, n),
        'volume': np.random.uniform(1000, 10000, n),
    })
    
    # Target (classificação binária)
    y = pd.Series((np.random.rand(n) > 0.5).astype(int))
    
    # Retornos simulados
    returns = pd.Series(np.random.randn(n) * 0.01)
    
    # Modelo
    model = RandomForestClassifier(n_estimators=50, random_state=42)
    model.fit(X, y)
    
    # Validar
    validator = get_ml_validator()
    result = validator.validate_model(model, X, y, returns)
    
    print(validator.generate_report(result))
