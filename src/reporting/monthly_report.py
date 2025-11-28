"""
Monthly Report Generator
Gera relatório mensal automático no último dia do mês 23:59
"""

from datetime import datetime, timezone
from typing import Dict
from loguru import logger

from database.strategy_stats import StrategyStatsDB


class MonthlyReportGenerator:
    """Gerador de relatórios mensais"""
    
    def __init__(self, stats_db: StrategyStatsDB, telegram=None):
        self.stats_db = stats_db
        self.telegram = telegram
    
    def generate_report(self, month=None, year=None) -> Dict:
        """Gera relatório do mês"""
        now = datetime.now(timezone.utc)
        if month is None:
            month = now.month
        if year is None:
            year = now.year
        
        logger.info(f"📊 Gerando relatório mensal: {month}/{year}...")
        
        # Buscar trades do mês
        conn = self.stats_db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                strategy_name,
                profit,
                duration_minutes,
                close_time
            FROM strategy_trades
            WHERE strftime('%m', close_time) = ? 
            AND strftime('%Y', close_time) = ?
            AND status = 'closed'
        """, (f"{month:02d}", str(year)))
        
        trades = cursor.fetchall()
        conn.close()
        
        if not trades:
            return {'total_trades': 0}
        
        # Processar dados
        report = {
            'month': month,
            'year': year,
            'total_trades': len(trades),
            'wins': sum(1 for t in trades if t[1] > 0),
            'losses': sum(1 for t in trades if t[1] < 0),
            'total_profit': sum(t[1] for t in trades),
            'win_rate': 0.0,
            'avg_duration': sum(t[2] or 0 for t in trades) / len(trades),
            'best_day_profit': 0.0,
            'worst_day_profit': 0.0,
        }
        
        # Win rate
        if report['total_trades'] > 0:
            report['win_rate'] = (report['wins'] / report['total_trades']) * 100
        
        # Melhor/pior dia
        daily_profits = {}
        for strategy, profit, duration, close_time in trades:
            day = datetime.fromisoformat(close_time).date()
            if day not in daily_profits:
                daily_profits[day] = 0.0
            daily_profits[day] += profit
        
        if daily_profits:
            report['best_day_profit'] = max(daily_profits.values())
            report['worst_day_profit'] = min(daily_profits.values())
        
        return report
    
    def format_report(self, report: Dict) -> str:
        """Formata relatório mensal com análise profunda em português"""
        months = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                  'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
        month_name = months[report['month'] - 1]
        
        if report['total_trades'] == 0:
            return (
                f"📊 **RELATÓRIO MENSAL COMPLETO**\n"
                f"📅 {month_name}/{report['year']}\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"⏸️ Nenhum trade no mês.\n\n"
                f"ℹ️ *Possíveis causas:*\n"
                f"• Sistema pausado durante o mês\n"
                f"• Feriados e períodos sem operação\n"
                f"• Mercado extremamente volátil (proteção ativa)\n"
                f"• Problemas técnicos ou de conexão\n"
            )
        
        # Análise mensal detalhada
        win_rate = report['win_rate']
        total_profit = report['total_profit']
        total_trades = report['total_trades']
        
        # Classificação de desempenho
        if win_rate >= 65 and total_profit > 0:
            performance = "🌟 EXCEPCIONAL"
            performance_desc = "Mês extraordinário! Win rate e lucro excepcionais."
        elif win_rate >= 55 and total_profit > 0:
            performance = "🟢 EXCELENTE"
            performance_desc = "Ótimo mês! Estratégias performando muito bem."
        elif win_rate >= 45 and total_profit > 0:
            performance = "🟡 BOM"
            performance_desc = "Mês positivo. Há espaço para melhorias."
        elif total_profit > 0:
            performance = "🟠 POSITIVO"
            performance_desc = "Lucro alcançado, mas win rate precisa melhorar."
        elif win_rate >= 50 and total_profit < 0:
            performance = "🟠 INCONSISTENTE"
            performance_desc = "Win rate ok, mas gestão de risco precisa ajustes."
        else:
            performance = "🔴 DEFICITÁRIO"
            performance_desc = "Mês negativo. Revisão completa necessária."
        
        # Cálculos adicionais
        avg_per_trade = total_profit / total_trades if total_trades > 0 else 0
        avg_per_day = total_profit / 30  # Aproximado
        
        profit_emoji = "🟢" if total_profit > 0 else "🔴"
        
        text = (
            f"📊 **RELATÓRIO MENSAL COMPLETO**\n"
            f"📅 {month_name}/{report['year']}\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"🎯 **DESEMPENHO GERAL: {performance}**\n"
            f"ℹ️ {performance_desc}\n\n"
            f"📈 **ESTATÍSTICAS DO MÊS**\n"
            f"🎯 Total de Operações: `{total_trades}`\n"
            f"✅ Vitórias: `{report['wins']}` ({report['wins']/total_trades*100:.1f}%)\n"
            f"❌ Derrotas: `{report['losses']}` ({report['losses']/total_trades*100:.1f}%)\n"
            f"⚖️ Taxa de Vitória: `{win_rate:.1f}%`\n\n"
            f"{profit_emoji} **Resultado Mensal:** `${total_profit:+.2f}`\n"
            f"💵 **Média por Trade:** `${avg_per_trade:+.2f}`\n"
            f"📅 **Média por Dia:** `${avg_per_day:+.2f}`\n"
            f"⏱️ **Duração Média:** `{report['avg_duration']:.1f} minutos`\n\n"
        )
        
        # Análise de extremos
        text += (
            f"🎢 **ANÁLISE DE VOLATILIDADE**\n"
            f"🏆 **Melhor Dia:** `${report['best_day_profit']:+.2f}`\n"
        )
        
        if report['best_day_profit'] > total_profit * 0.5:
            text += (
                f"⚠️ *Atenção:* Melhor dia representa >50% do lucro total.\n"
                f"Resultado depende muito de poucos dias excepcionais.\n"
            )
        else:
            text += f"✅ *Positivo:* Lucros bem distribuídos ao longo do mês.\n"
        
        text += f"\n💔 **Pior Dia:** `${report['worst_day_profit']:+.2f}`\n"
        
        if abs(report['worst_day_profit']) > total_profit * 0.3 and total_profit > 0:
            text += (
                f"⚠️ *Atenção:* Pior dia consumiu >30% do lucro.\n"
                f"Revisar o que aconteceu nesse dia específico.\n\n"
            )
        elif report['worst_day_profit'] < 0:
            text += (
                f"ℹ️ Perda máxima diária de ${abs(report['worst_day_profit']):.2f}.\n"
                f"Controle de risco diário está funcionando.\n\n"
            )
        else:
            text += f"✅ Mesmo no pior dia, não houve prejuízo significativo.\n\n"
        
        # Análise por volume
        text += f"📊 **ANÁLISE DE VOLUME**\n"
        
        if total_trades < 30:
            text += (
                f"⚠️ **Volume Baixo:** {total_trades} trades/mês\n"
                f"• Menos de 1 trade/dia em média\n"
                f"• Amostra pequena para análise estatística robusta\n"
                f"• Considere: mais símbolos ou timeframes menores\n\n"
            )
        elif total_trades < 100:
            text += (
                f"✅ **Volume Moderado:** {total_trades} trades/mês\n"
                f"• Aproximadamente {total_trades/30:.1f} trades/dia\n"
                f"• Volume adequado para análise estatística\n"
                f"• Quantidade saudável para gestão de risco\n\n"
            )
        else:
            text += (
                f"🚀 **Volume Alto:** {total_trades} trades/mês\n"
                f"• Aproximadamente {total_trades/30:.1f} trades/dia\n"
                f"• Excelente para análise estatística\n"
                f"• ⚠️ Verifique: custos de spread e comissão\n\n"
            )
        
        # Análise da consistência
        text += f"🎯 **ANÁLISE DE CONSISTÊNCIA**\n"
        
        consistency_score = (win_rate / 100) * min(total_trades / 50, 1.0)
        if total_profit > 0:
            consistency_score += 0.3
        if report['best_day_profit'] < total_profit * 2:
            consistency_score += 0.2
        
        if consistency_score >= 0.8:
            text += (
                f"🟢 **Alta Consistência**\n"
                f"Resultados previsíveis e confiáveis ao longo do mês.\n"
                f"Sistema operando de forma estável e madura.\n\n"
            )
        elif consistency_score >= 0.5:
            text += (
                f"🟡 **Consistência Moderada**\n"
                f"Alguns altos e baixos, mas dentro do esperado.\n"
                f"Continue monitorando o desempenho.\n\n"
            )
        else:
            text += (
                f"🔴 **Baixa Consistência**\n"
                f"Resultados muito variáveis e imprevisíveis.\n"
                f"⚠️ **Ação:** Revisar estratégias e parâmetros.\n\n"
            )
        
        # Projeções e metas
        if total_profit > 0:
            monthly_return_pct = (total_profit / 10000) * 100  # Assumindo capital de $10k
            annual_projection = total_profit * 12
            text += (
                f"📈 **PROJEÇÕES E METAS**\n"
                f"Retorno Mensal: `~{monthly_return_pct:.2f}%` (base $10k)\n"
                f"Projeção Anual: `${annual_projection:+.2f}`\n"
                f"ℹ️ *Atenção:* Projeções assumem desempenho constante.\n"
                f"Mercados variam - use apenas como referência.\n\n"
            )
        
        # Recomendações finais
        text += (
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💡 **RECOMENDAÇÕES PARA PRÓXIMO MÊS:**\n\n"
        )
        
        if total_profit > 0 and win_rate >= 55:
            text += (
                f"🌟 **Mês excelente! Mantenha o curso:**\n"
                f"✅ Estratégias estão funcionando\n"
                f"✅ Gestão de risco adequada\n"
                f"✅ Disciplina sendo mantida\n\n"
                f"📚 *Foco:* Documentar o que está funcionando bem\n"
                f"para replicar o sucesso.\n"
            )
        elif total_profit > 0 and win_rate < 55:
            text += (
                f"🟡 **Mês positivo mas com ressalvas:**\n"
                f"✅ Boa gestão de risco (lucro apesar de WR baixo)\n"
                f"⚠️ Win rate precisa melhorar\n\n"
                f"📚 *Foco para próximo mês:*\n"
                f"• Melhorar critérios de entrada\n"
                f"• Aguardar sinais mais fortes\n"
                f"• Estudar padrões das entradas perdedoras\n"
            )
        elif win_rate >= 50:
            text += (
                f"⚠️ **Win rate ok, mas resultado negativo:**\n"
                f"O problema não está nas entradas, mas na gestão:\n\n"
                f"📚 *Ações urgentes:*\n"
                f"• Revisar Take Profit (pode estar muito baixo)\n"
                f"• Revisar Stop Loss (pode estar muito próximo)\n"
                f"• Analisar relação risco/recompensa\n"
                f"• Considerar trailing stop para proteger lucros\n"
            )
        else:
            text += (
                f"🔴 **Mês deficitário - revisão necessária:**\n\n"
                f"⚠️ **PRIORIDADES URGENTES:**\n"
                f"1. PAUSAR estratégias com pior desempenho\n"
                f"2. REDUZIR tamanho de posição pela metade\n"
                f"3. REVISAR todos os parâmetros\n"
                f"4. Operar apenas sinais com >80% confiança\n"
                f"5. Focar em PRESERVAR CAPITAL\n\n"
                f"📚 Considere:\n"
                f"• Voltar ao backtest das estratégias\n"
                f"• Testar em conta demo antes de retomar\n"
                f"• Buscar ajuda de traders experientes\n"
            )
        
        # Métricas educacionais
        text += (
            f"\n━━━━━━━━━━━━━━━━━━\n"
            f"📚 **GLOSSÁRIO - ENTENDENDO AS MÉTRICAS:**\n\n"
            f"**Win Rate (Taxa de Vitória)**\n"
            f"% de trades lucrativos. >50% é positivo.\n\n"
            f"**Média por Trade**\n"
            f"Lucro/perda média em cada operação.\n"
            f"Deve ser sempre positiva.\n\n"
            f"**Duração Média**\n"
            f"Tempo médio das operações abertas.\n"
            f"<30min = scalping | >4h = swing trade\n\n"
            f"**Consistência**\n"
            f"Capacidade de gerar resultados previsíveis.\n"
            f"Alta = mais confiável, Baixa = arriscado\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 Próximo relatório: {months[(report['month'] % 12)]}/{report['year'] if report['month'] < 12 else report['year']+1}\n"
            f"💬 Use /stats para ver estatísticas gerais\n"
            f"📈 Acompanhe os relatórios diários e semanais!"
        )
        
        return text
    
    def send_report(self, report: Dict):
        """Envia relatório via Telegram"""
        if not self.telegram:
            return
        
        try:
            self.telegram.send_message_sync(self.format_report(report))
            logger.success("📱 Relatório mensal enviado!")
        except Exception as e:
            logger.error(f"Erro ao enviar relatório mensal: {e}")
