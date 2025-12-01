# -*- coding: utf-8 -*-
"""
FinBERT Sentiment Analyzer
==========================
Análise de sentimento financeiro usando FinBERT (ProsusAI/finbert)

FinBERT é um modelo BERT pré-treinado em textos financeiros que
supera TextBlob/VADER em análise de sentimento de notícias financeiras.

Autor: Urion Trading Bot
Versão: 2.0
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from loguru import logger
import threading

# Lazy loading para evitar travamento na importação
transformers = None
torch = None
_model = None
_tokenizer = None
_loaded = False
_loading = False
_lock = threading.Lock()


def _load_finbert():
    """Carrega modelo FinBERT sob demanda"""
    global transformers, torch, _model, _tokenizer, _loaded, _loading
    
    with _lock:
        if _loaded:
            return _model is not None
        
        if _loading:
            return False
        
        _loading = True
    
    try:
        logger.info("Carregando FinBERT (primeira vez pode demorar)...")
        
        # Importar bibliotecas
        import torch as th
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        
        torch = th
        transformers = True  # Flag que importou
        
        # Carregar modelo e tokenizer
        model_name = "ProsusAI/finbert"
        
        _tokenizer = AutoTokenizer.from_pretrained(model_name)
        _model = AutoModelForSequenceClassification.from_pretrained(model_name)
        
        # Colocar em modo de avaliação
        _model.eval()
        
        # Mover para GPU se disponível
        if torch.cuda.is_available():
            _model = _model.cuda()
            logger.info("FinBERT carregado em GPU")
        else:
            logger.info("FinBERT carregado em CPU")
        
        _loaded = True
        return True
        
    except ImportError as e:
        logger.warning(
            f"FinBERT não disponível: {e}. "
            "Instale com: pip install transformers torch"
        )
        _loaded = True
        return False
    except Exception as e:
        logger.error(f"Erro ao carregar FinBERT: {e}")
        _loaded = True
        return False
    finally:
        _loading = False


class FinBERTAnalyzer:
    """
    Analisador de sentimento usando FinBERT
    
    FinBERT é treinado especificamente para textos financeiros e
    classifica em: positive, negative, neutral
    
    Muito mais preciso que TextBlob/VADER para notícias de trading!
    """
    
    # Labels do modelo FinBERT
    LABELS = ['positive', 'negative', 'neutral']
    
    # Mapeamento para nosso sistema
    LABEL_MAP = {
        'positive': 'bullish',
        'negative': 'bearish',
        'neutral': 'neutral'
    }
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Inicializa o analisador
        
        Args:
            config: Configurações opcionais
        """
        self.config = config or {}
        self._is_available = False
        self._batch_size = self.config.get('batch_size', 8)
        
        # Estatísticas
        self._total_analyzed = 0
        self._last_analysis_time = None
        
        # Cache de resultados
        self._cache: Dict[str, Dict] = {}
        self._cache_max_size = 1000
        
        logger.info("FinBERTAnalyzer inicializado (modelo será carregado sob demanda)")
    
    def _ensure_loaded(self) -> bool:
        """Garante que modelo está carregado"""
        if not _loaded:
            self._is_available = _load_finbert()
        else:
            self._is_available = _model is not None
        return self._is_available
    
    @property
    def is_available(self) -> bool:
        """Verifica se FinBERT está disponível"""
        return self._ensure_loaded()
    
    def analyze(self, text: str) -> Dict:
        """
        Analisa sentimento de um texto
        
        Args:
            text: Texto para análise
            
        Returns:
            Dict com sentiment, confidence e scores
        """
        # Verificar cache
        cache_key = hash(text)
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Verificar se modelo disponível
        if not self._ensure_loaded():
            # Fallback para análise básica
            return self._fallback_analyze(text)
        
        try:
            # Tokenizar
            inputs = _tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True
            )
            
            # Mover para GPU se disponível
            if torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}
            
            # Inferência
            with torch.no_grad():
                outputs = _model(**inputs)
                logits = outputs.logits
            
            # Softmax para probabilidades
            probs = torch.softmax(logits, dim=-1)
            probs = probs.cpu().numpy()[0]
            
            # Determinar classe e confiança
            predicted_idx = np.argmax(probs)
            predicted_label = self.LABELS[predicted_idx]
            confidence = float(probs[predicted_idx])
            
            # Calcular score contínuo (-1 a 1)
            # positive - negative (neutral não contribui)
            score = float(probs[0] - probs[1])
            
            result = {
                'sentiment': self.LABEL_MAP[predicted_label],
                'label_raw': predicted_label,
                'confidence': round(confidence, 4),
                'score': round(score, 4),
                'probabilities': {
                    'positive': round(float(probs[0]), 4),
                    'negative': round(float(probs[1]), 4),
                    'neutral': round(float(probs[2]), 4)
                },
                'method': 'finbert',
                'text_length': len(text)
            }
            
            # Atualizar cache
            self._update_cache(cache_key, result)
            
            # Estatísticas
            self._total_analyzed += 1
            self._last_analysis_time = datetime.now()
            
            return result
            
        except Exception as e:
            logger.error(f"Erro na análise FinBERT: {e}")
            return self._fallback_analyze(text)
    
    def analyze_batch(self, texts: List[str]) -> List[Dict]:
        """
        Analisa múltiplos textos em batch (mais eficiente)
        
        Args:
            texts: Lista de textos
            
        Returns:
            Lista de resultados
        """
        if not self._ensure_loaded():
            return [self._fallback_analyze(t) for t in texts]
        
        try:
            results = []
            
            # Processar em batches
            for i in range(0, len(texts), self._batch_size):
                batch = texts[i:i + self._batch_size]
                
                # Tokenizar batch
                inputs = _tokenizer(
                    batch,
                    return_tensors="pt",
                    truncation=True,
                    max_length=512,
                    padding=True
                )
                
                if torch.cuda.is_available():
                    inputs = {k: v.cuda() for k, v in inputs.items()}
                
                # Inferência
                with torch.no_grad():
                    outputs = _model(**inputs)
                    logits = outputs.logits
                
                probs = torch.softmax(logits, dim=-1)
                probs = probs.cpu().numpy()
                
                # Processar resultados
                for j, text in enumerate(batch):
                    p = probs[j]
                    predicted_idx = np.argmax(p)
                    predicted_label = self.LABELS[predicted_idx]
                    
                    result = {
                        'sentiment': self.LABEL_MAP[predicted_label],
                        'label_raw': predicted_label,
                        'confidence': round(float(p[predicted_idx]), 4),
                        'score': round(float(p[0] - p[1]), 4),
                        'probabilities': {
                            'positive': round(float(p[0]), 4),
                            'negative': round(float(p[1]), 4),
                            'neutral': round(float(p[2]), 4)
                        },
                        'method': 'finbert'
                    }
                    results.append(result)
            
            self._total_analyzed += len(texts)
            return results
            
        except Exception as e:
            logger.error(f"Erro no batch FinBERT: {e}")
            return [self._fallback_analyze(t) for t in texts]
    
    def analyze_news(self, news_list: List[Dict]) -> Dict:
        """
        Analisa lista de notícias e retorna sentimento agregado
        
        Args:
            news_list: Lista de dicts com 'title' e opcionalmente 'description'
            
        Returns:
            Dict com sentimento agregado
        """
        if not news_list:
            return {
                'overall_sentiment': 'neutral',
                'score': 0.0,
                'confidence': 0.0,
                'bullish_count': 0,
                'bearish_count': 0,
                'neutral_count': 0,
                'total_analyzed': 0,
                'method': 'finbert'
            }
        
        # Preparar textos
        texts = []
        for news in news_list:
            title = news.get('title', '')
            desc = news.get('description', '')
            text = f"{title}. {desc}".strip()
            if text:
                texts.append(text)
        
        if not texts:
            return {
                'overall_sentiment': 'neutral',
                'score': 0.0,
                'confidence': 0.0,
                'bullish_count': 0,
                'bearish_count': 0,
                'neutral_count': 0,
                'total_analyzed': 0,
                'method': 'finbert'
            }
        
        # Analisar em batch
        results = self.analyze_batch(texts)
        
        # Agregar
        bullish = sum(1 for r in results if r['sentiment'] == 'bullish')
        bearish = sum(1 for r in results if r['sentiment'] == 'bearish')
        neutral = len(results) - bullish - bearish
        
        avg_score = sum(r['score'] for r in results) / len(results)
        avg_confidence = sum(r['confidence'] for r in results) / len(results)
        
        # Determinar sentimento geral
        if avg_score > 0.15:
            overall = 'bullish'
        elif avg_score < -0.15:
            overall = 'bearish'
        else:
            overall = 'neutral'
        
        return {
            'overall_sentiment': overall,
            'score': round(avg_score, 4),
            'confidence': round(avg_confidence, 4),
            'bullish_count': bullish,
            'bearish_count': bearish,
            'neutral_count': neutral,
            'total_analyzed': len(results),
            'method': 'finbert',
            'individual_results': results[:10]  # Primeiros 10 para debug
        }
    
    def _fallback_analyze(self, text: str) -> Dict:
        """
        Análise fallback quando FinBERT não está disponível
        Usa análise léxica simples
        """
        text_lower = text.lower()
        
        # Palavras positivas/negativas para finanças
        positive_words = [
            'bullish', 'surge', 'rally', 'gain', 'rise', 'up', 'high',
            'growth', 'profit', 'positive', 'strong', 'buy', 'outperform',
            'beat', 'exceed', 'upgrade', 'boost', 'soar', 'jump'
        ]
        
        negative_words = [
            'bearish', 'crash', 'fall', 'drop', 'down', 'low', 'loss',
            'decline', 'negative', 'weak', 'sell', 'underperform',
            'miss', 'downgrade', 'plunge', 'sink', 'tumble', 'slump'
        ]
        
        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)
        
        total = pos_count + neg_count
        if total == 0:
            score = 0.0
            sentiment = 'neutral'
            confidence = 0.3
        else:
            score = (pos_count - neg_count) / total
            confidence = min(total / 5, 0.8)  # Max 0.8 para fallback
            
            if score > 0.2:
                sentiment = 'bullish'
            elif score < -0.2:
                sentiment = 'bearish'
            else:
                sentiment = 'neutral'
        
        return {
            'sentiment': sentiment,
            'label_raw': sentiment,
            'confidence': round(confidence, 4),
            'score': round(score, 4),
            'probabilities': {
                'positive': max(0, score),
                'negative': max(0, -score),
                'neutral': 1 - abs(score)
            },
            'method': 'fallback_lexical'
        }
    
    def _update_cache(self, key: int, value: Dict):
        """Atualiza cache com limite de tamanho"""
        if len(self._cache) >= self._cache_max_size:
            # Remover entradas antigas (FIFO simples)
            keys_to_remove = list(self._cache.keys())[:100]
            for k in keys_to_remove:
                del self._cache[k]
        
        self._cache[key] = value
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas do analisador"""
        return {
            'is_available': self._is_available,
            'total_analyzed': self._total_analyzed,
            'cache_size': len(self._cache),
            'last_analysis': self._last_analysis_time.isoformat() if self._last_analysis_time else None,
            'gpu_available': torch.cuda.is_available() if torch else False
        }
    
    def clear_cache(self):
        """Limpa cache"""
        self._cache.clear()
        logger.debug("Cache FinBERT limpo")


# Singleton
_analyzer: Optional[FinBERTAnalyzer] = None


def get_finbert_analyzer(config: Optional[Dict] = None) -> FinBERTAnalyzer:
    """Retorna instância singleton do FinBERTAnalyzer"""
    global _analyzer
    if _analyzer is None:
        _analyzer = FinBERTAnalyzer(config)
    return _analyzer


# Exemplo de uso
if __name__ == "__main__":
    logger.add(lambda msg: print(msg), level="INFO")
    
    analyzer = get_finbert_analyzer()
    
    # Testar com notícias de exemplo
    test_texts = [
        "Gold prices surge as inflation fears mount, investors seek safe haven",
        "Federal Reserve signals aggressive rate hikes, gold tumbles",
        "Markets stable as traders await economic data",
        "XAU/USD rallies to new highs amid geopolitical tensions",
        "Dollar strengthens, putting pressure on precious metals"
    ]
    
    print("\n=== FinBERT Sentiment Analysis ===\n")
    
    for text in test_texts:
        result = analyzer.analyze(text)
        print(f"Text: {text[:60]}...")
        print(f"  → Sentiment: {result['sentiment']} "
              f"(confidence: {result['confidence']:.2f}, "
              f"score: {result['score']:.2f})")
        print()
    
    # Testar análise agregada
    news_list = [{'title': t} for t in test_texts]
    summary = analyzer.analyze_news(news_list)
    
    print("\n=== Aggregated Sentiment ===")
    print(f"Overall: {summary['overall_sentiment']}")
    print(f"Score: {summary['score']:.4f}")
    print(f"Bullish: {summary['bullish_count']}, "
          f"Bearish: {summary['bearish_count']}, "
          f"Neutral: {summary['neutral_count']}")
