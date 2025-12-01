"""
Urion Trading Bot - Machine Learning Module

Módulos:
- FinBertAnalyzer: Análise de sentimento com FinBERT
- TransformerPredictor: Predições com Transformers
- MLValidator: Validação robusta de modelos ML
"""

# FinBERT Analyzer
try:
    from .finbert_analyzer import FinBERTAnalyzer, get_finbert_analyzer
    FinBertAnalyzer = FinBERTAnalyzer  # Alias
except ImportError:
    FinBERTAnalyzer = None
    FinBertAnalyzer = None
    get_finbert_analyzer = None

# Transformer Predictor
try:
    from .transformer_predictor import MarketTransformer, get_transformer_predictor
    TransformerPredictor = MarketTransformer  # Alias
except ImportError:
    MarketTransformer = None
    TransformerPredictor = None
    get_transformer_predictor = None

# ML Validator
try:
    from .ml_validator import (
        MLValidator,
        MLValidationResult as ValidationResult
    )
except ImportError:
    MLValidator = None
    ValidationResult = None

def get_ml_validator(config=None):
    """Retorna instância do MLValidator"""
    if MLValidator is None:
        return None
    return MLValidator(config or {})

__all__ = [
    # Análise de Sentimento
    'FinBERTAnalyzer',
    'FinBertAnalyzer',
    'get_finbert_analyzer',
    # Transformers
    'MarketTransformer',
    'TransformerPredictor', 
    'get_transformer_predictor',
    # Validação ML
    'MLValidator',
    'ValidationResult',
    'get_ml_validator'
]
