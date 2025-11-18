"""
Dashboard de Performance de Estratégias
Visualização interativa com ranking e estatísticas
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from database.strategy_stats import StrategyStatsDB
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich import box
from loguru import logger
import time

console = Console()


def create_ranking_table(ranking: List[Dict]) -> Table:
    """Cria tabela de ranking"""
    table = Table(
        title="🏆 RANKING DE ESTRATÉGIAS",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan"
    )
    
    table.add_column("#", style="bold yellow", justify="center", width=3)
    table.add_column("Estratégia", style="bold", width=18)
    table.add_column("Score", justify="center", width=8)
    table.add_column("Trades", justify="center", width=8)
    table.add_column("Win%", justify="center", width=8)
    table.add_column("P.Factor", justify="center", width=9)
    table.add_column("Lucro", justify="right", width=10)
    table.add_column("Status", justify="center", width=10)
    
    for strategy in ranking:
        # Cores baseadas no score
        if strategy['score'] >= 70:
            status = "[green]🟢 Excelente[/green]"
        elif strategy['score'] >= 50:
            status = "[yellow]🟡 Bom[/yellow]"
        elif strategy['score'] >= 30:
            status = "[orange1]🟠 Regular[/orange1]"
        else:
            status = "[red]🔴 Fraco[/red]"
        
        # Cor do lucro
        profit_color = "green" if strategy['net_profit'] >= 0 else "red"
        profit_str = f"[{profit_color}]${strategy['net_profit']:.2f}[/{profit_color}]"
        
        # Cor do win rate
        wr_color = "green" if strategy['win_rate'] >= 55 else "yellow" if strategy['win_rate'] >= 45 else "red"
        wr_str = f"[{wr_color}]{strategy['win_rate']:.1f}%[/{wr_color}]"
        
        # Cor do profit factor
        pf_color = "green" if strategy['profit_factor'] >= 1.5 else "yellow" if strategy['profit_factor'] >= 1.0 else "red"
        pf_str = f"[{pf_color}]{strategy['profit_factor']:.2f}[/{pf_color}]"
        
        table.add_row(
            f"{strategy['rank']}",
            strategy['strategy_name'],
            f"[bold]{strategy['score']:.1f}[/bold]",
            str(strategy['total_trades']),
            wr_str,
            pf_str,
            profit_str,
            status
        )
    
    return table


def create_detailed_stats_table(stats: Dict) -> Table:
    """Cria tabela de estatísticas detalhadas"""
    table = Table(
        title=f"📊 Detalhes: {stats['strategy_name']}",
        box=box.SIMPLE,
        show_header=False,
        width=60
    )
    
    table.add_column("Métrica", style="cyan", width=25)
    table.add_column("Valor", width=35)
    
    # Determinar cor baseado em performance
    profit_color = "green" if stats['net_profit'] >= 0 else "red"
    wr_color = "green" if stats['win_rate'] >= 55 else "yellow" if stats['win_rate'] >= 45 else "red"
    
    table.add_row("Total de Trades", f"[white]{stats['total_trades']}[/white]")
    table.add_row("Trades Ganhos", f"[green]{stats['winning_trades']}[/green]")
    table.add_row("Trades Perdidos", f"[red]{stats['losing_trades']}[/red]")
    table.add_row("", "")
    table.add_row("Win Rate", f"[{wr_color}]{stats['win_rate']:.2f}%[/{wr_color}]")
    table.add_row("Profit Factor", f"[white]{stats['profit_factor']:.2f}[/white]")
    table.add_row("", "")
    table.add_row("Lucro Líquido", f"[{profit_color}]${stats['net_profit']:.2f}[/{profit_color}]")
    table.add_row("Média de Ganho", f"[green]${stats['avg_win']:.2f}[/green]")
    table.add_row("Média de Perda", f"[red]${stats['avg_loss']:.2f}[/red]")
    table.add_row("", "")
    table.add_row("Maior Ganho", f"[green bold]${stats['largest_win']:.2f}[/green bold]")
    table.add_row("Maior Perda", f"[red bold]${stats['largest_loss']:.2f}[/red bold]")
    table.add_row("", "")
    table.add_row("Confiança Média", f"[cyan]{stats['avg_confidence']:.1f}%[/cyan]")
    
    return table


def show_dashboard(days: int = 7):
    """
    Mostra dashboard completo
    
    Args:
        days: Número de dias para análise
    """
    db = StrategyStatsDB()
    
    console.clear()
    
    # Header
    console.print()
    console.print("═" * 100, style="cyan")
    console.print(
        f"{'📈 DASHBOARD DE PERFORMANCE DE ESTRATÉGIAS':^100}",
        style="bold yellow"
    )
    console.print(
        f"{'Período: Últimos ' + str(days) + ' dias':^100}",
        style="white"
    )
    console.print(
        f"{'Atualizado: ' + datetime.now().strftime('%d/%m/%Y %H:%M:%S'):^100}",
        style="dim"
    )
    console.print("═" * 100, style="cyan")
    console.print()
    
    # Ranking
    ranking = db.get_all_strategies_ranking(days=days)
    console.print(create_ranking_table(ranking))
    console.print()
    
    # Top 3 detalhes
    console.print("🌟 TOP 3 ESTRATÉGIAS - ANÁLISE DETALHADA", style="bold cyan")
    console.print()
    
    for i, strategy in enumerate(ranking[:3], 1):
        stats = db.get_strategy_stats(strategy['strategy_name'], days=days)
        
        # Emoji baseado no rank
        emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉"
        
        console.print(f"{emoji} #{i} - {strategy['strategy_name']}", style="bold yellow")
        console.print(create_detailed_stats_table(stats))
        console.print()
    
    # Resumo geral
    total_trades = sum(s['total_trades'] for s in ranking)
    total_profit = sum(s['net_profit'] for s in ranking)
    avg_score = sum(s['score'] for s in ranking) / len(ranking)
    
    summary = f"""
    📊 RESUMO GERAL ({days} dias):
    
    Total de Trades: {total_trades}
    Lucro Total: ${total_profit:.2f}
    Score Médio: {avg_score:.1f}/100
    
    Melhor Estratégia: {ranking[0]['strategy_name']} (Score: {ranking[0]['score']:.1f})
    Pior Estratégia: {ranking[-1]['strategy_name']} (Score: {ranking[-1]['score']:.1f})
    """
    
    profit_color = "green" if total_profit >= 0 else "red"
    console.print(Panel(summary, border_style=profit_color, title="💰 Resumo"))
    console.print()
    
    # Recomendações
    console.print("💡 RECOMENDAÇÕES", style="bold cyan")
    console.print()
    
    # Estratégias com score < 30
    weak_strategies = [s for s in ranking if s['score'] < 30]
    if weak_strategies:
        console.print("🔴 Estratégias FRACAS (considere desativar):", style="bold red")
        for s in weak_strategies:
            console.print(f"   • {s['strategy_name']} (Score: {s['score']:.1f})", style="red")
        console.print()
    
    # Estratégias com score > 70
    strong_strategies = [s for s in ranking if s['score'] >= 70]
    if strong_strategies:
        console.print("🟢 Estratégias EXCELENTES (mantenha ativas):", style="bold green")
        for s in strong_strategies:
            console.print(f"   • {s['strategy_name']} (Score: {s['score']:.1f})", style="green")
        console.print()
    
    # Estratégias com poucos trades
    low_activity = [s for s in ranking if s['total_trades'] < 5]
    if low_activity:
        console.print("⚠️  Estratégias com BAIXA ATIVIDADE:", style="bold yellow")
        for s in low_activity:
            console.print(f"   • {s['strategy_name']} ({s['total_trades']} trades)", style="yellow")
        console.print()
    
    console.print("═" * 100, style="cyan")
    console.print()


def show_historical_comparison(weeks: int = 4):
    """Mostra comparação histórica"""
    db = StrategyStatsDB()
    
    console.clear()
    console.print()
    console.print("═" * 100, style="cyan")
    console.print(
        f"{'📅 EVOLUÇÃO HISTÓRICA - ÚLTIMAS ' + str(weeks) + ' SEMANAS':^100}",
        style="bold yellow"
    )
    console.print("═" * 100, style="cyan")
    console.print()
    
    rankings = db.get_historical_rankings(weeks=weeks)
    
    if not rankings:
        console.print("⚠️  Sem dados históricos disponíveis", style="yellow")
        return
    
    # Agrupar por semana
    weeks_data = {}
    for rank in rankings:
        week_key = f"{rank['week_start']} - {rank['week_end']}"
        if week_key not in weeks_data:
            weeks_data[week_key] = []
        weeks_data[week_key].append(rank)
    
    # Mostrar cada semana
    for week, data in sorted(weeks_data.items(), reverse=True):
        console.print(f"📆 Semana: {week}", style="bold cyan")
        
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
        table.add_column("#", justify="center", width=3)
        table.add_column("Estratégia", width=18)
        table.add_column("Trades", justify="center", width=8)
        table.add_column("Win%", justify="center", width=8)
        table.add_column("Lucro", justify="right", width=12)
        table.add_column("Score", justify="center", width=8)
        
        for strategy in sorted(data, key=lambda x: x['rank']):
            profit_color = "green" if strategy['net_profit'] >= 0 else "red"
            
            table.add_row(
                str(strategy['rank']),
                strategy['strategy_name'],
                str(strategy['total_trades']),
                f"{strategy['win_rate']:.1f}%",
                f"[{profit_color}]${strategy['net_profit']:.2f}[/{profit_color}]",
                f"{strategy['score']:.1f}"
            )
        
        console.print(table)
        console.print()
    
    console.print("═" * 100, style="cyan")
    console.print()


def main_menu():
    """Menu principal do dashboard"""
    while True:
        console.clear()
        console.print()
        console.print("╔═══════════════════════════════════════════════════╗", style="cyan")
        console.print("║  📊 DASHBOARD DE ESTRATÉGIAS - MENU PRINCIPAL  ║", style="bold yellow")
        console.print("╚═══════════════════════════════════════════════════╝", style="cyan")
        console.print()
        console.print("1. 📈 Ver Ranking Atual (7 dias)", style="white")
        console.print("2. 📊 Ver Ranking (30 dias)", style="white")
        console.print("3. 📅 Evolução Histórica (4 semanas)", style="white")
        console.print("4. 💾 Salvar Ranking Semanal", style="white")
        console.print("5. 🔄 Atualizar (Auto-refresh)", style="white")
        console.print("6. 🚪 Sair", style="white")
        console.print()
        
        choice = console.input("[bold cyan]Escolha uma opção: [/bold cyan]")
        
        if choice == "1":
            show_dashboard(days=7)
            console.input("\n[dim]Pressione ENTER para voltar ao menu...[/dim]")
        
        elif choice == "2":
            show_dashboard(days=30)
            console.input("\n[dim]Pressione ENTER para voltar ao menu...[/dim]")
        
        elif choice == "3":
            show_historical_comparison(weeks=4)
            console.input("\n[dim]Pressione ENTER para voltar ao menu...[/dim]")
        
        elif choice == "4":
            db = StrategyStatsDB()
            db.save_weekly_ranking()
            console.print("\n[green]✅ Ranking semanal salvo com sucesso![/green]")
            time.sleep(2)
        
        elif choice == "5":
            console.print("\n[cyan]🔄 Modo auto-refresh ativado (atualiza a cada 30s)[/cyan]")
            console.print("[dim]Pressione Ctrl+C para sair[/dim]\n")
            try:
                while True:
                    show_dashboard(days=7)
                    time.sleep(30)
            except KeyboardInterrupt:
                console.print("\n[yellow]Auto-refresh cancelado[/yellow]")
                time.sleep(1)
        
        elif choice == "6":
            console.print("\n[green]Até logo! 👋[/green]\n")
            break
        
        else:
            console.print("\n[red]Opção inválida![/red]")
            time.sleep(1)


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Dashboard encerrado pelo usuário[/yellow]\n")
    except Exception as e:
        console.print(f"\n[red]Erro: {e}[/red]\n")
        logger.exception("Erro no dashboard")
