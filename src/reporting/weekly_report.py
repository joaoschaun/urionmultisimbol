"""
Weekly Report Generator
Gera relatório semanal automático aos domingos 23:59
"""

from datetime import datetime, timedelta, timezone
from typing import Dict
from loguru import logger

from database.strategy_stats import StrategyStatsDB


class WeeklyReportGenerator:
    """Gerador de relatórios semanais"""
    
    def __init__(self, stats_db: StrategyStatsDB, telegram=None):
        self.stats_db = stats_db
        self.telegram = telegram
    
    def generate_report(self, end_date=None) -> Dict:
        """Gera relatório da semana"""
        if end_date is None:
            end_date = datetime.now(timezone.utc).date()
        
        # 7 dias atrás
        start_date = end_date - timedelta(days=7)
        
        logger.info(f"📊 Gerando relatório semanal: {start_date} até {end_date}...")
        
        # Buscar trades da semana
        conn = self.stats_db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                strategy_name,
                profit,
                signal_confidence,
                close_time
            FROM strategy_trades
            WHERE date(close_time) >= ? AND date(close_time) <= ?
            AND status = 'closed'
        """, (start_date, end_date))
        
        trades = cursor.fetchall()
        conn.close()
        
        if not trades:
            return {'total_trades': 0}
        
        # Processar dados
        report = {
            'start_date': start_date,
            'end_date': end_date,
            'total_trades': len(trades),
            'wins': sum(1 for t in trades if t[1] > 0),
            'losses': sum(1 for t in trades if t[1] < 0),
            'total_profit': sum(t[1] for t in trades),
            'win_rate': 0.0,
            'by_strategy': {}
        }
        
        # Win rate
        if report['total_trades'] > 0:
            report['win_rate'] = (report['wins'] / report['total_trades']) * 100
        
        # Por estratégia
        for strategy, profit, conf, close_time in trades:
            if strategy not in report['by_strategy']:
                report['by_strategy'][strategy] = {
                    'trades': 0,
                    'profit': 0.0
                }
            report['by_strategy'][strategy]['trades'] += 1
            report['by_strategy'][strategy]['profit'] += profit
        
        return report
    
    def format_report(self, report: Dict) -> str:
        """Formata relatório semanal com análise detalhada em português"""
        if report['total_trades'] == 0:
            return (
                f"📊 **RELATÓRIO SEMANAL COMPLETO**\n\n"
                f"⏸️ Nenhum trade na semana.\n\n"
                f"ℹ️ *Possíveis motivos:*\n"
                f"• Mercado fora do horário de operação\n"
                f"• Feriados prolongados\n"
                f"• Volatilidade insuficiente\n"
                f"• Todas as posições ainda abertas\n"
            )
        
        # Análise da semana
        win_rate = report['win_rate']
        if win_rate >= 65:
            wr_status = "🟢 Excelente"
            wr_analysis = "Semana excepcional! Taxa de acerto muito alta."
        elif win_rate >= 50:
            wr_status = "🟡 Boa"
            wr_analysis = "Semana positiva com taxa de acerto saudável."
        elif win_rate >= 35:
            wr_status = "🟠 Regular"
            wr_analysis = "Taxa de acerto abaixo do ideal. Revisar estratégias."
        else:
            wr_status = "🔴 Baixa"
            wr_analysis = "Taxa muito baixa. Ajustes urgentes necessários."
        
        # Análise de lucro
        total_profit = report['total_profit']
        avg_per_trade = total_profit / report['total_trades'] if report['total_trades'] > 0 else 0
        
        profit_emoji = "🟢" if total_profit > 0 else "🔴"
        
        text = (
            f"📊 **RELATÓRIO SEMANAL COMPLETO**\n"
            f"📅 {report['start_date'].strftime('%d/%m')} - {report['end_date'].strftime('%d/%m/%Y')}\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"📈 **VISÃO GERAL DA SEMANA**\n"
            f"🎯 Total de Operações: `{report['total_trades']}`\n"
            f"✅ Vitórias: `{report['wins']}` | ❌ Derrotas: `{report['losses']}`\n\n"
            f"📊 **Taxa de Vitória:** `{win_rate:.1f}%` {wr_status}\n"
            f"ℹ️ {wr_analysis}\n\n"
            f"{profit_emoji} **Resultado Semanal:** `${total_profit:+.2f}`\n"
            f"💵 **Média por Trade:** `${avg_per_trade:+.2f}`\n\n"
        )
        
        # Análise do desempenho
        if total_profit > 0:
            text += (
                f"✅ **SEMANA POSITIVA!**\n"
                f"Parabéns! A semana fechou no lucro.\n\n"
                f"📊 *Análise:*\n"
            )
            if win_rate >= 50:
                text += f"• Taxa de acerto boa ({win_rate:.1f}%)\n"
                text += f"• Média de ${avg_per_trade:.2f} por operação\n"
                text += f"• Continue com a mesma disciplina\n\n"
            else:
                text += f"• Win rate baixo mas lucro positivo\n"
                text += f"• Indica boa gestão de risco (TP/SL eficazes)\n"
                text += f"• Ganhos grandes compensam perdas pequenas\n\n"
        else:
            abs_loss = abs(total_profit)
            text += (
                f"⚠️ **SEMANA NEGATIVA**\n"
                f"Perda de ${abs_loss:.2f} na semana.\n\n"
                f"📊 *Análise e ações:*\n"
            )
            if win_rate >= 50:
                text += (
                    f"• Win rate ok ({win_rate:.1f}%) mas resultado negativo\n"
                    f"• Problema: Perdas grandes ou ganhos pequenos\n"
                    f"• **Ação:** Revisar Take Profit e Stop Loss\n"
                    f"• Considere aumentar TP ou reduzir SL\n\n"
                )
            else:
                text += (
                    f"• Win rate baixo ({win_rate:.1f}%)\n"
                    f"• **Ação:** Revisar critérios de entrada\n"
                    f"• Aguarde sinais mais fortes antes de entrar\n"
                    f"• Considere reduzir tamanho de posição temporariamente\n\n"
                )
        
        # Comparação com média esperada
        text += (
            f"📐 **ANÁLISE ESTATÍSTICA**\n"
            f"• Com {report['total_trades']} trades na semana\n"
        )
        
        if report['total_trades'] < 10:
            text += (
                f"⚠️ Poucas operações. Amostra pequena para análise robusta.\n"
                f"Aguarde mais trades para conclusões definitivas.\n\n"
            )
        elif report['total_trades'] < 30:
            text += (
                f"✅ Volume razoável de operações.\n"
                f"Amostra começa a ser significativa estatisticamente.\n\n"
            )
        else:
            text += (
                f"✅ Ótimo volume de operações!\n"
                f"Amostra estatisticamente significativa.\n\n"
            )
        
        # Top estratégias com análise
        if report['by_strategy']:
            text += "🎯 **RANKING DE ESTRATÉGIAS DA SEMANA**\n\n"
            sorted_strat = sorted(
                report['by_strategy'].items(),
                key=lambda x: x[1]['profit'],
                reverse=True
            )
            
            # Top 3 melhores
            text += "🏆 **TOP 3 MELHORES:**\n"
            for i, (strategy, data) in enumerate(sorted_strat[:3], 1):
                emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉"
                avg_strat = data['profit'] / data['trades'] if data['trades'] > 0 else 0
                text += (
                    f"{emoji} **`{strategy}`**\n"
                    f"   {data['trades']} trades | ${data['profit']:+.2f}\n"
                    f"   Média: ${avg_strat:+.2f} por trade\n"
                )
            
            # Piores (se existirem com prejuízo)
            worst = [s for s in sorted_strat if s[1]['profit'] < 0]
            if worst:
                text += f"\n⚠️ **ESTRATÉGIAS COM PREJUÍZO:**\n"
                for strategy, data in worst[-2:]:  # 2 piores
                    avg_strat = data['profit'] / data['trades'] if data['trades'] > 0 else 0
                    text += (
                        f"🔴 `{strategy}`\n"
                        f"   {data['trades']} trades | ${data['profit']:.2f}\n"
                        f"   Média: ${avg_strat:.2f} por trade\n"
                        f"   💡 *Sugestão:* Revisar parâmetros ou pausar temporariamente\n"
                    )
            
            text += "\n"
        
        # Rodapé com dicas
        text += (
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💡 **RECOMENDAÇÕES PARA PRÓXIMA SEMANA:**\n\n"
        )
        
        if total_profit > 0 and win_rate >= 50:
            text += (
                f"✅ Estratégias funcionando bem!\n"
                f"• Mantenha a disciplina\n"
                f"• Não aumente risco por estar ganhando\n"
                f"• Continue estudando os melhores trades\n"
            )
        elif total_profit > 0 and win_rate < 50:
            text += (
                f"⚡ Lucro com win rate baixo:\n"
                f"• Boa gestão de risco (parabéns!)\n"
                f"• Tente melhorar critérios de entrada\n"
                f"• Foque em qualidade > quantidade\n"
            )
        else:
            text += (
                f"⚠️ Semana de prejuízo:\n"
                f"• NÃO aumente tamanho de posição\n"
                f"• Revise TODAS as entradas perdedoras\n"
                f"• Considere operar apenas as melhores estratégias\n"
                f"• Foque em preservar capital\n"
            )
        
        text += (
            f"\n📊 Use /stats para ver estatísticas gerais\n"
            f"📈 Veja relatório mensal para visão mais ampla\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        
        return text
    
    def send_report(self, report: Dict):
        """Envia relatório via Telegram"""
        if not self.telegram:
            return
        
        try:
            self.telegram.send_message_sync(self.format_report(report))
            logger.success("📱 Relatório semanal enviado!")
        except Exception as e:
            logger.error(f"Erro ao enviar relatório semanal: {e}")
