"""
Sistema de Machine Learning para Urion Bot
Aprende com trades passados e otimiza estratégias automaticamente
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from loguru import logger
import numpy as np


class StrategyLearner:
    """
    Sistema de aprendizagem para estratégias de trading
    
    Funcionalidades:
    1. Analisa performance histórica de cada estratégia
    2. Identifica padrões de sucesso/falha
    3. Ajusta parâmetros automaticamente (min_confidence, ciclos, etc)
    4. Aprende melhores condições de mercado para cada estratégia
    5. Rankeia estratégias por performance
    """
    
    def __init__(self, db_path: str = "data/strategy_stats.db"):
        self.db_path = Path(db_path)
        self.learning_data_path = Path("data/learning_data.json")
        self.learning_data_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Carregar dados de aprendizagem salvos
        self.learning_data = self._load_learning_data()
        
        # Configurações de aprendizagem
        self.min_trades_to_learn = 10  # Mínimo de trades para começar a aprender
        self.learning_rate = 0.1  # Taxa de ajuste (10%)
        self.confidence_adjustment_threshold = 0.6  # Win rate mínima para aumentar confiança
        
        logger.info("StrategyLearner inicializado")
    
    def _load_learning_data(self) -> Dict:
        """Carrega dados de aprendizagem salvos"""
        if self.learning_data_path.exists():
            try:
                with open(self.learning_data_path, 'r') as f:
                    data = json.load(f)
                    logger.info(f"Dados de aprendizagem carregados: {len(data)} estratégias")
                    return data
            except Exception as e:
                logger.error(f"Erro ao carregar learning_data: {e}")
        
        return {}
    
    def _save_learning_data(self):
        """Salva dados de aprendizagem"""
        try:
            with open(self.learning_data_path, 'w') as f:
                json.dump(self.learning_data, f, indent=2)
            logger.debug("Dados de aprendizagem salvos")
        except Exception as e:
            logger.error(f"Erro ao salvar learning_data: {e}")
    
    def analyze_strategy_performance(self, strategy_name: str, days: int = 7) -> Dict:
        """
        Analisa performance detalhada de uma estratégia
        
        Args:
            strategy_name: Nome da estratégia
            days: Número de dias para análise
            
        Returns:
            Dict com métricas de performance
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            start_date = datetime.now() - timedelta(days=days)
            
            # Buscar todos os trades da estratégia
            cursor.execute("""
                SELECT 
                    profit,
                    signal_confidence,
                    market_conditions,
                    open_time,
                    close_time
                FROM strategy_trades
                WHERE strategy_name = ?
                AND status = 'closed'
                AND close_time >= ?
                ORDER BY close_time DESC
            """, (strategy_name, start_date))
            
            trades = cursor.fetchall()
            conn.close()
            
            if not trades:
                return {
                    'total_trades': 0,
                    'win_rate': 0,
                    'avg_profit': 0,
                    'avg_loss': 0,
                    'profit_factor': 0,
                    'best_confidence_range': None,
                    'consistency': 0
                }
            
            # Calcular métricas
            total_trades = len(trades)
            winning_trades = [t for t in trades if t[0] > 0]
            losing_trades = [t for t in trades if t[0] < 0]
            
            win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
            
            avg_profit = np.mean([t[0] for t in winning_trades]) if winning_trades else 0
            avg_loss = abs(np.mean([t[0] for t in losing_trades])) if losing_trades else 0
            
            total_profit = sum(t[0] for t in winning_trades)
            total_loss = abs(sum(t[0] for t in losing_trades))
            profit_factor = total_profit / total_loss if total_loss > 0 else 0
            
            # Analisar melhores níveis de confiança
            best_confidence_range = self._find_best_confidence_range(trades)
            
            # Calcular consistência (desvio padrão dos resultados)
            results = [t[0] for t in trades]
            consistency = 1 / (1 + np.std(results)) if len(results) > 1 else 0
            
            return {
                'total_trades': total_trades,
                'win_rate': win_rate,
                'avg_profit': avg_profit,
                'avg_loss': avg_loss,
                'profit_factor': profit_factor,
                'best_confidence_range': best_confidence_range,
                'consistency': consistency,
                'recent_trend': self._calculate_trend(trades[:10])  # Últimos 10 trades
            }
            
        except Exception as e:
            logger.error(f"Erro ao analisar performance de {strategy_name}: {e}")
            return {}
    
    def _find_best_confidence_range(self, trades: List[Tuple]) -> Optional[Tuple[float, float]]:
        """
        Identifica faixa de confiança com melhor performance
        
        Args:
            trades: Lista de trades (profit, confidence, ...)
            
        Returns:
            Tupla (min_confidence, max_confidence) com melhor win rate
        """
        if len(trades) < self.min_trades_to_learn:
            return None
        
        # Dividir trades por faixas de confiança
        ranges = [
            (0.0, 0.5),
            (0.5, 0.6),
            (0.6, 0.7),
            (0.7, 0.8),
            (0.8, 1.0)
        ]
        
        best_range = None
        best_win_rate = 0
        
        for min_conf, max_conf in ranges:
            range_trades = [
                t for t in trades
                if t[1] is not None and min_conf <= t[1] <= max_conf
            ]
            
            if len(range_trades) >= 5:  # Mínimo 5 trades na faixa
                wins = sum(1 for t in range_trades if t[0] > 0)
                win_rate = wins / len(range_trades)
                
                if win_rate > best_win_rate:
                    best_win_rate = win_rate
                    best_range = (min_conf, max_conf)
        
        return best_range
    
    def _calculate_trend(self, recent_trades: List[Tuple]) -> str:
        """
        Calcula tendência recente (melhorando/piorando)
        
        Args:
            recent_trades: Trades recentes
            
        Returns:
            'improving', 'declining' ou 'stable'
        """
        if len(recent_trades) < 5:
            return 'stable'
        
        # Calcular win rate das duas metades
        mid = len(recent_trades) // 2
        first_half = recent_trades[:mid]
        second_half = recent_trades[mid:]
        
        first_wr = sum(1 for t in first_half if t[0] > 0) / len(first_half)
        second_wr = sum(1 for t in second_half if t[0] > 0) / len(second_half)
        
        diff = second_wr - first_wr
        
        if diff > 0.1:
            return 'improving'
        elif diff < -0.1:
            return 'declining'
        else:
            return 'stable'
    
    def suggest_confidence_adjustment(self, strategy_name: str) -> Optional[float]:
        """
        Sugere ajuste no min_confidence baseado em performance
        
        Args:
            strategy_name: Nome da estratégia
            
        Returns:
            Novo valor de min_confidence ou None
        """
        performance = self.analyze_strategy_performance(strategy_name)
        
        if performance['total_trades'] < self.min_trades_to_learn:
            logger.debug(f"[{strategy_name}] Poucos trades para aprender ({performance['total_trades']})")
            return None
        
        current_confidence = self.learning_data.get(strategy_name, {}).get('min_confidence', 0.5)
        
        # Lógica de ajuste
        if performance['win_rate'] >= 0.7:
            # Excelente performance → diminuir threshold para operar mais
            suggested = max(0.4, current_confidence - self.learning_rate)
            logger.info(
                f"[{strategy_name}] 🎯 Alta performance (WR: {performance['win_rate']:.1%}) "
                f"→ Sugerindo diminuir confiança: {current_confidence:.2f} → {suggested:.2f}"
            )
            return suggested
            
        elif performance['win_rate'] < 0.5:
            # Performance ruim → aumentar threshold para ser mais seletivo
            suggested = min(0.8, current_confidence + self.learning_rate)
            logger.info(
                f"[{strategy_name}] ⚠️ Baixa performance (WR: {performance['win_rate']:.1%}) "
                f"→ Sugerindo aumentar confiança: {current_confidence:.2f} → {suggested:.2f}"
            )
            return suggested
        
        # Performance OK → manter
        return None
    
    def learn_from_trade(self, strategy_name: str, trade_data: Dict):
        """
        Aprende com um trade individual
        
        Args:
            strategy_name: Nome da estratégia
            trade_data: Dados do trade (profit, confidence, conditions, etc)
        """
        try:
            # Inicializar dados da estratégia se não existir
            if strategy_name not in self.learning_data:
                self.learning_data[strategy_name] = {
                    'total_trades': 0,
                    'wins': 0,
                    'losses': 0,
                    'min_confidence': 0.5,
                    'best_conditions': [],
                    'last_adjustment': None
                }
            
            strategy_data = self.learning_data[strategy_name]
            
            # Atualizar contadores
            strategy_data['total_trades'] += 1
            if trade_data.get('profit', 0) > 0:
                strategy_data['wins'] += 1
            else:
                strategy_data['losses'] += 1
            
            # Salvar condições de mercado se trade foi bem-sucedido
            if trade_data.get('profit', 0) > 0 and trade_data.get('market_conditions'):
                strategy_data['best_conditions'].append({
                    'conditions': trade_data['market_conditions'],
                    'confidence': trade_data.get('signal_confidence', 0),
                    'profit': trade_data.get('profit', 0)
                })
                
                # Limitar histórico de melhores condições
                if len(strategy_data['best_conditions']) > 50:
                    # Manter apenas as 50 com melhor profit
                    strategy_data['best_conditions'].sort(
                        key=lambda x: x['profit'],
                        reverse=True
                    )
                    strategy_data['best_conditions'] = strategy_data['best_conditions'][:50]
            
            self._save_learning_data()
            
            # Verificar se é hora de ajustar parâmetros
            if strategy_data['total_trades'] % 20 == 0:  # A cada 20 trades
                self._auto_adjust_strategy(strategy_name)
            
        except Exception as e:
            logger.error(f"Erro ao aprender com trade de {strategy_name}: {e}")
    
    def _auto_adjust_strategy(self, strategy_name: str):
        """
        Ajusta automaticamente parâmetros da estratégia
        
        Args:
            strategy_name: Nome da estratégia
        """
        suggested_confidence = self.suggest_confidence_adjustment(strategy_name)
        
        if suggested_confidence:
            self.learning_data[strategy_name]['min_confidence'] = suggested_confidence
            self.learning_data[strategy_name]['last_adjustment'] = datetime.now().isoformat()
            self._save_learning_data()
            
            logger.success(
                f"[{strategy_name}] 🤖 Parâmetros ajustados automaticamente! "
                f"Novo min_confidence: {suggested_confidence:.2f}"
            )
    
    def get_strategy_ranking(self, days: int = 7) -> List[Dict]:
        """
        Rankeia estratégias por performance
        
        Args:
            days: Número de dias para análise
            
        Returns:
            Lista de estratégias ordenadas por score
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Buscar todas as estratégias com trades
            cursor.execute("""
                SELECT DISTINCT strategy_name
                FROM strategy_trades
                WHERE close_time >= ?
            """, (datetime.now() - timedelta(days=days),))
            
            strategies = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            ranking = []
            
            for strategy_name in strategies:
                performance = self.analyze_strategy_performance(strategy_name, days)
                
                if performance['total_trades'] > 0:
                    # Calcular score composto
                    score = (
                        performance['win_rate'] * 0.4 +
                        (performance['profit_factor'] / 3) * 0.3 +  # Normalizar
                        performance['consistency'] * 0.2 +
                        (1 if performance['recent_trend'] == 'improving' else 0.5) * 0.1
                    )
                    
                    ranking.append({
                        'strategy': strategy_name,
                        'score': score,
                        'win_rate': performance['win_rate'],
                        'profit_factor': performance['profit_factor'],
                        'total_trades': performance['total_trades'],
                        'trend': performance['recent_trend']
                    })
            
            # Ordenar por score
            ranking.sort(key=lambda x: x['score'], reverse=True)
            
            return ranking
            
        except Exception as e:
            logger.error(f"Erro ao calcular ranking: {e}")
            return []
    
    def get_learned_confidence(self, strategy_name: str) -> float:
        """
        Retorna o min_confidence aprendido para uma estratégia
        
        Args:
            strategy_name: Nome da estratégia
            
        Returns:
            Valor de min_confidence aprendido
        """
        return self.learning_data.get(strategy_name, {}).get('min_confidence', 0.5)
    
    def print_learning_status(self):
        """Exibe status de aprendizagem de todas as estratégias"""
        logger.info("=" * 80)
        logger.info("📚 STATUS DE APRENDIZAGEM")
        logger.info("=" * 80)
        
        if not self.learning_data:
            logger.info("Nenhum dado de aprendizagem ainda")
            return
        
        for strategy_name, data in self.learning_data.items():
            total = data['total_trades']
            wins = data['wins']
            win_rate = wins / total if total > 0 else 0
            confidence = data['min_confidence']
            
            logger.info(
                f"\n{strategy_name}:"
                f"\n  Trades: {total} | Win Rate: {win_rate:.1%}"
                f"\n  Min Confidence: {confidence:.2f}"
                f"\n  Último ajuste: {data.get('last_adjustment', 'Nunca')}"
            )
        
        logger.info("=" * 80)
