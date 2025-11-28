"""
Daily Report Generator
Gera relatório diário automático às 23:59
"""

import schedule
from datetime import datetime, timedelta, timezone
from typing import Dict, List
from loguru import logger

from database.strategy_stats import StrategyStatsDB

# 📊 NOVO: Importar métricas avançadas
try:
    from src.reporting.advanced_metrics import AdvancedMetrics
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    logger.warning("AdvancedMetrics não disponível")


class DailyReportGenerator:
    """Gerador de relatórios diários"""
    
    def __init__(self, stats_db: StrategyStatsDB, telegram=None):
        """
        Inicializa gerador de relatórios
        
        Args:
            stats_db: Database de estratégias
            telegram: Notificador Telegram (opcional)
        """
        self.stats_db = stats_db
        self.telegram = telegram
        self.last_report_date = None
    
    def generate_report(self, date=None) -> Dict:
        """
        Gera relatório do dia
        
        Args:
            date: Data específica (default: hoje)
            
        Returns:
            Dict com dados do relatório
        """
        if date is None:
            date = datetime.now(timezone.utc).date()
        
        # Evitar duplicação
        if self.last_report_date == date:
            logger.warning(f"Relatório já gerado para {date}")
            return {}
        
        logger.info(f"📊 Gerando relatório diário para {date}...")
        
        # Período do dia
        start_time = datetime.combine(date, datetime.min.time())
        end_time = datetime.combine(date, datetime.max.time())
        
        # Buscar trades do dia
        conn = self.stats_db.get_connection()
        cursor = conn.cursor()
        
        # Trades fechados no dia
        cursor.execute("""
            SELECT 
                strategy_name,
                ticket,
                entry_price,
                close_price,
                profit,
                signal_confidence,
                duration_minutes,
                close_time
            FROM strategy_trades
            WHERE close_time >= ? AND close_time <= ?
            AND status = 'closed'
            ORDER BY close_time
        """, (start_time, end_time))
        
        trades = cursor.fetchall()
        conn.close()
        
        if not trades:
            logger.info("Nenhum trade fechado hoje")
            return self._generate_empty_report(date)
        
        # Processar trades
        report_data = {
            'date': date,
            'total_trades': len(trades),
            'wins': 0,
            'losses': 0,
            'breakeven': 0,
            'total_profit': 0.0,
            'win_rate': 0.0,
            'best_trade': None,
            'worst_trade': None,
            'by_strategy': {},
            'avg_duration': 0.0,
            'avg_confidence': 0.0,
        }
        
        durations = []
        confidences = []
        
        for trade in trades:
            strategy, ticket, entry, close, profit, confidence, duration, close_time = trade
            
            # Contadores gerais
            report_data['total_profit'] += profit
            
            if profit > 0:
                report_data['wins'] += 1
            elif profit < 0:
                report_data['losses'] += 1
            else:
                report_data['breakeven'] += 1
            
            # Melhor e pior trade
            if report_data['best_trade'] is None or profit > report_data['best_trade']['profit']:
                report_data['best_trade'] = {
                    'ticket': ticket,
                    'strategy': strategy,
                    'profit': profit,
                    'close_time': close_time
                }
            
            if report_data['worst_trade'] is None or profit < report_data['worst_trade']['profit']:
                report_data['worst_trade'] = {
                    'ticket': ticket,
                    'strategy': strategy,
                    'profit': profit,
                    'close_time': close_time
                }
            
            # Por estratégia
            if strategy not in report_data['by_strategy']:
                report_data['by_strategy'][strategy] = {
                    'trades': 0,
                    'wins': 0,
                    'losses': 0,
                    'profit': 0.0,
                    'win_rate': 0.0
                }
            
            strat_data = report_data['by_strategy'][strategy]
            strat_data['trades'] += 1
            strat_data['profit'] += profit
            if profit > 0:
                strat_data['wins'] += 1
            elif profit < 0:
                strat_data['losses'] += 1
            
            # Médias
            if duration:
                durations.append(duration)
            if confidence:
                confidences.append(confidence if confidence <= 1 else confidence / 100)
        
        # Calcular win rate
        if report_data['total_trades'] > 0:
            report_data['win_rate'] = (report_data['wins'] / report_data['total_trades']) * 100
        
        # Calcular win rate por estratégia
        for strategy, data in report_data['by_strategy'].items():
            if data['trades'] > 0:
                data['win_rate'] = (data['wins'] / data['trades']) * 100
        
        # Médias
        if durations:
            report_data['avg_duration'] = sum(durations) / len(durations)
        if confidences:
            report_data['avg_confidence'] = sum(confidences) / len(confidences)
        
        # 📊 NOVO: Calcular métricas avançadas (se disponível)
        if METRICS_AVAILABLE and len(trades) >= 10:
            try:
                # Preparar dados para métricas
                trade_results = [t[4] for t in trades]  # profits
                
                metrics = AdvancedMetrics(trade_results)
                report_data['advanced_metrics'] = {
                    'sharpe': metrics.sharpe_ratio(),
                    'sortino': metrics.sortino_ratio(),
                    'calmar': metrics.calmar_ratio(),
                    'profit_factor': metrics.profit_factor(),
                    'recovery_factor': metrics.recovery_factor(),
                    'expectancy': metrics.expectancy(),
                }
                logger.info("📊 Métricas avançadas calculadas")
            except Exception as e:
                logger.debug(f"Erro ao calcular métricas: {e}")
                report_data['advanced_metrics'] = None
        else:
            report_data['advanced_metrics'] = None
        
        # Salvar data do relatório
        self.last_report_date = date
        
        logger.success(f"✅ Relatório gerado: {report_data['total_trades']} trades, ${report_data['total_profit']:.2f}")
        
        return report_data
    
    def _generate_empty_report(self, date) -> Dict:
        """Gera relatório vazio"""
        return {
            'date': date,
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'breakeven': 0,
            'total_profit': 0.0,
            'win_rate': 0.0,
            'best_trade': None,
            'worst_trade': None,
            'by_strategy': {},
            'avg_duration': 0.0,
            'avg_confidence': 0.0,
        }
    
    def format_report(self, report_data: Dict) -> str:
        """
        Formata relatório em texto com explicações detalhadas em português
        
        Args:
            report_data: Dados do relatório
            
        Returns:
            String formatada com explicações educativas
        """
        if report_data['total_trades'] == 0:
            return (
                f"📊 **RELATÓRIO DIÁRIO COMPLETO**\n"
                f"📅 {report_data['date'].strftime('%d/%m/%Y')}\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"⏸️ **Nenhum trade fechado hoje**\n\n"
                f"ℹ️ *O que isso significa?*\n"
                f"Sem operações finalizadas no período. Isso pode ocorrer por:\n"
                f"• Mercado fora do horário de operação\n"
                f"• Condições de mercado não favoráveis\n"
                f"• Todas as posições ainda abertas\n\n"
                f"💡 *Próximos passos:*\n"
                f"• Verificar posições abertas com /positions\n"
                f"• Aguardar condições de mercado melhorarem\n"
            )
        
        # Análise da taxa de vitória
        win_rate = report_data['win_rate']
        if win_rate >= 70:
            wr_status = "🟢 Excelente"
            wr_explanation = "Taxa acima de 70% indica estratégias muito eficientes!"
        elif win_rate >= 55:
            wr_status = "🟡 Boa"
            wr_explanation = "Taxa entre 55-70% é saudável para a maioria das estratégias."
        elif win_rate >= 40:
            wr_status = "🟠 Regular"
            wr_explanation = "Taxa entre 40-55% requer gestão de risco cuidadosa."
        else:
            wr_status = "🔴 Baixa"
            wr_explanation = "Taxa abaixo de 40% indica necessidade de revisão das estratégias."
        
        # Cabeçalho com explicações
        profit_emoji = "🟢" if report_data['total_profit'] > 0 else "🔴"
        text = (
            f"📊 **RELATÓRIO DIÁRIO COMPLETO**\n"
            f"📅 {report_data['date'].strftime('%d/%m/%Y')}\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"📈 **DESEMPENHO GERAL**\n"
            f"🎯 Total de Operações: `{report_data['total_trades']}`\n"
            f"✅ Vitórias: `{report_data['wins']}` | "
            f"❌ Derrotas: `{report_data['losses']}` | "
            f"⚖️ Empates: `{report_data['breakeven']}`\n\n"
            f"📊 **Taxa de Vitória:** `{win_rate:.1f}%` {wr_status}\n"
            f"ℹ️ {wr_explanation}\n\n"
            f"{profit_emoji} **Resultado Líquido:** `${report_data['total_profit']:+.2f}`\n"
        )
        
        # Explicação do resultado
        if report_data['total_profit'] > 0:
            text += (
                f"✅ *Dia positivo!* O saldo aumentou ${report_data['total_profit']:.2f}\n"
                f"Continue mantendo a disciplina e gestão de risco.\n\n"
            )
        elif report_data['total_profit'] < 0:
            abs_loss = abs(report_data['total_profit'])
            text += (
                f"⚠️ *Dia negativo.* Perda de ${abs_loss:.2f}\n"
                f"Dias negativos são normais no trading. O importante é:\n"
                f"• Manter o risco controlado\n"
                f"• Não aumentar tamanho de posição para recuperar\n"
                f"• Revisar as operações que deram errado\n\n"
            )
        else:
            text += f"⚖️ *Dia neutro.* Sem ganhos ou perdas significativas.\n\n"
        
        # Métricas operacionais com explicações
        text += (
            f"⏱️ **Duração Média:** `{report_data['avg_duration']:.1f} minutos`\n"
            f"ℹ️ Tempo médio que as operações ficaram abertas.\n"
            f"Operações mais curtas (<30min) são scalping/day trade.\n\n"
            f"🎯 **Confiança Média:** `{report_data['avg_confidence']*100:.0f}%`\n"
            f"ℹ️ Nível médio de certeza das estratégias ao abrir posições.\n"
            f"Confiança >70% geralmente indica sinais mais fortes.\n\n"
        )
        
        # Melhor e pior trade com análise
        if report_data['best_trade']:
            best = report_data['best_trade']
            text += (
                f"🏆 **MELHOR TRADE DO DIA**\n"
                f"Ticket: `{best['ticket']}`\n"
                f"Estratégia: `{best['strategy']}`\n"
                f"💰 Lucro: `${best['profit']:.2f}`\n"
                f"ℹ️ *Análise:* Esta foi a operação mais lucrativa do dia.\n"
                f"Estude o que deu certo para replicar em futuras operações.\n\n"
            )
        
        if report_data['worst_trade']:
            worst = report_data['worst_trade']
            text += (
                f"💔 **PIOR TRADE DO DIA**\n"
                f"Ticket: `{worst['ticket']}`\n"
                f"Estratégia: `{worst['strategy']}`\n"
                f"📉 Perda: `${worst['profit']:.2f}`\n"
                f"ℹ️ *Análise:* Esta operação teve o maior prejuízo.\n"
                f"Revise: entrada, stop loss, condições de mercado.\n\n"
            )
        
        # Por estratégia com análise detalhada
        if report_data['by_strategy']:
            text += f"🎯 **DESEMPENHO POR ESTRATÉGIA**\n\n"
            
            # Ordenar por profit
            sorted_strategies = sorted(
                report_data['by_strategy'].items(),
                key=lambda x: x[1]['profit'],
                reverse=True
            )
            
            for strategy, data in sorted_strategies:
                emoji = "🟢" if data['profit'] > 0 else "🔴"
                wr_emoji = "✅" if data['win_rate'] >= 50 else "⚠️"
                
                text += (
                    f"{emoji} **`{strategy}`**\n"
                    f"  Operações: {data['trades']} | {wr_emoji} WR: {data['win_rate']:.0f}%\n"
                    f"  Resultado: ${data['profit']:+.2f}\n"
                )
                
                # Análise da estratégia
                if data['profit'] > 0 and data['win_rate'] >= 60:
                    text += f"  ✅ *Excelente desempenho hoje*\n"
                elif data['profit'] > 0:
                    text += f"  ✅ *Positivo, mas win rate pode melhorar*\n"
                elif data['win_rate'] >= 50:
                    text += f"  ⚠️ *Win rate ok, mas resultado negativo - revisar TP/SL*\n"
                else:
                    text += f"  ⚠️ *Precisa de atenção - considere ajustes*\n"
                text += "\n"
            
            text += (
                f"ℹ️ **Sobre as estratégias:**\n"
                f"• WR (Win Rate) = Taxa de acerto\n"
                f"• Estratégias com WR >50% e lucro positivo são ideais\n"
                f"• WR baixo mas lucro alto = boa gestão de risco (grandes ganhos)\n\n"
            )
        
        # 📊 Métricas avançadas com explicações detalhadas
        if report_data.get('advanced_metrics'):
            metrics = report_data['advanced_metrics']
            text += f"\n📊 **MÉTRICAS AVANÇADAS EXPLICADAS**\n\n"
            
            # Sharpe Ratio
            sharpe = metrics.get('sharpe')
            if sharpe:
                sharpe_emoji = "🟢" if sharpe > 1.0 else "🟡" if sharpe > 0.5 else "🔴"
                text += f"{sharpe_emoji} **Sharpe Ratio:** `{sharpe:.2f}`"
                if sharpe > 2.0:
                    text += " (Excelente!)\n"
                    text += "ℹ️ Retorno muito superior ao risco. Estratégias excepcionais!\n"
                elif sharpe > 1.0:
                    text += " (Bom)\n"
                    text += "ℹ️ Bom equilíbrio entre retorno e risco.\n"
                elif sharpe > 0:
                    text += " (Regular)\n"
                    text += "ℹ️ Retorno positivo mas com volatilidade alta.\n"
                else:
                    text += " (Ruim)\n"
                    text += "⚠️ Retorno não compensa o risco assumido.\n"
                text += "📚 *O que é?* Mede retorno ajustado ao risco. >1.0 é bom.\n\n"
            
            # Sortino Ratio
            sortino = metrics.get('sortino')
            if sortino:
                sortino_emoji = "🟢" if sortino > 1.5 else "🟡" if sortino > 0.8 else "🔴"
                text += f"{sortino_emoji} **Sortino Ratio:** `{sortino:.2f}`"
                if sortino > 2.0:
                    text += " (Excelente!)\n"
                    text += "ℹ️ Perdas muito bem controladas!\n"
                elif sortino > 1.0:
                    text += " (Bom)\n"
                    text += "ℹ️ Gestão de perdas adequada.\n"
                else:
                    text += "\n"
                text += "📚 *O que é?* Similar ao Sharpe, mas foca apenas em volatilidade negativa.\n"
                text += "Mede o retorno em relação ao risco de quedas. >1.5 é ótimo.\n\n"
            
            # Profit Factor
            pf = metrics.get('profit_factor')
            if pf:
                pf_emoji = "🟢" if pf > 1.5 else "🟡" if pf > 1.0 else "🔴"
                text += f"{pf_emoji} **Profit Factor:** `{pf:.2f}`"
                if pf > 2.0:
                    text += " (Excelente!)\n"
                    text += "ℹ️ Lucros são o dobro das perdas ou mais!\n"
                elif pf > 1.5:
                    text += " (Muito Bom)\n"
                    text += "ℹ️ Lucros superam bem as perdas.\n"
                elif pf > 1.0:
                    text += " (Positivo)\n"
                    text += "ℹ️ Lucros maiores que perdas, mas margem pequena.\n"
                else:
                    text += " (Negativo)\n"
                    text += "⚠️ Perdas maiores que lucros. Revisar estratégias urgente!\n"
                text += "📚 *O que é?* Lucro bruto ÷ Perda bruta. Mínimo 1.5 recomendado.\n\n"
            
            # Expectancy
            exp = metrics.get('expectancy')
            if exp:
                exp_emoji = "🟢" if exp > 0 else "🔴"
                text += f"{exp_emoji} **Expectancy:** `${exp:.2f}` por trade\n"
                if exp > 0:
                    text += f"✅ Em média, cada operação gera ${exp:.2f} de lucro.\n"
                    text += f"Com 100 trades, expectativa de ganho: ${exp*100:.2f}\n"
                else:
                    text += f"⚠️ Em média, cada operação perde ${abs(exp):.2f}.\n"
                    text += "Estratégias precisam de ajustes urgentes!\n"
                text += "📚 *O que é?* Ganho/perda média esperada por operação.\n"
                text += "Deve ser sempre positiva para estratégia lucrativa.\n\n"
        
        # Rodapé com dicas
        text += (
            f"\n━━━━━━━━━━━━━━━━━━\n"
            f"💡 **DICAS DO DIA:**\n"
        )
        
        if report_data['total_profit'] > 0:
            text += (
                f"✅ Dia positivo! Mantenha a disciplina\n"
                f"• Não aumente o risco por estar ganhando\n"
                f"• Revise o que funcionou bem\n"
            )
        else:
            text += (
                f"⚠️ Dia negativo ou neutro:\n"
                f"• NUNCA tente recuperar perdas rapidamente\n"
                f"• Revise os erros cometidos\n"
                f"• Reduza tamanho de posição se necessário\n"
            )
        
        if win_rate < 50:
            text += (
                f"• Win Rate abaixo de 50% - analise entradas\n"
                f"• Considere aguardar sinais mais fortes\n"
            )
        
        text += f"\n📊 Use /stats para estatísticas gerais"
        text += f"\n📈 Use /positions para ver posições abertas"
        text += "\n━━━━━━━━━━━━━━━━━━"
        
        return text
    
    def send_report(self, report_data: Dict):
        """
        Envia relatório via Telegram
        
        Args:
            report_data: Dados do relatório
        """
        if not self.telegram:
            logger.warning("Telegram não configurado")
            return
        
        try:
            formatted_text = self.format_report(report_data)
            self.telegram.send_message_sync(formatted_text)
            logger.success("📱 Relatório diário enviado!")
        except Exception as e:
            logger.error(f"Erro ao enviar relatório: {e}")
    
    def schedule_daily_report(self, time_str: str = "23:59"):
        """
        Agenda relatório diário
        
        Args:
            time_str: Hora no formato HH:MM
        """
        def job():
            try:
                report_data = self.generate_report()
                if report_data:
                    self.send_report(report_data)
            except Exception as e:
                logger.error(f"Erro ao gerar relatório agendado: {e}")
        
        schedule.every().day.at(time_str).do(job)
        logger.info(f"📅 Relatório diário agendado para {time_str}")
