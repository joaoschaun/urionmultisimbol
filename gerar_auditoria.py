"""
Gerador de Documentação de Auditoria em PDF
Cria relatório completo do sistema URION Trading Bot
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime
import os
import json


class AuditoriaBot:
    """Gerador de documentação de auditoria do bot"""
    
    def __init__(self):
        self.filename = f"URION_Auditoria_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        self.doc = SimpleDocTemplate(
            self.filename,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        self.styles = getSampleStyleSheet()
        self._criar_estilos_customizados()
        
        self.story = []
        self.width, self.height = A4
    
    def _criar_estilos_customizados(self):
        """Cria estilos customizados para o documento"""
        
        # Título principal
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Subtítulo
        self.styles.add(ParagraphStyle(
            name='CustomSubtitle',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#2c5aa0'),
            spaceAfter=12,
            spaceBefore=20,
            fontName='Helvetica-Bold'
        ))
        
        # Seção
        self.styles.add(ParagraphStyle(
            name='CustomSection',
            parent=self.styles['Heading3'],
            fontSize=12,
            textColor=colors.HexColor('#1a5490'),
            spaceAfter=10,
            spaceBefore=15,
            fontName='Helvetica-Bold'
        ))
        
        # Corpo de texto
        self.styles.add(ParagraphStyle(
            name='CustomBody',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#333333'),
            spaceAfter=8,
            alignment=TA_JUSTIFY,
            leading=14
        ))
        
        # Destaque
        self.styles.add(ParagraphStyle(
            name='Highlight',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#0066cc'),
            spaceAfter=8,
            fontName='Helvetica-Bold'
        ))
        
        # Código
        self.styles.add(ParagraphStyle(
            name='CustomCode',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#d73a49'),
            fontName='Courier',
            leftIndent=20,
            rightIndent=20,
            spaceAfter=10
        ))
    
    def _adicionar_capa(self):
        """Adiciona página de capa"""
        
        # Logo/Título
        titulo = Paragraph(
            "<b>URION TRADING BOT</b>",
            self.styles['CustomTitle']
        )
        self.story.append(titulo)
        self.story.append(Spacer(1, 0.3*inch))
        
        # Subtítulo
        subtitulo = Paragraph(
            "Documentação de Auditoria Técnica",
            self.styles['CustomSubtitle']
        )
        self.story.append(subtitulo)
        self.story.append(Spacer(1, 0.2*inch))
        
        # Informações do documento
        info_data = [
            ['Data:', datetime.now().strftime('%d/%m/%Y %H:%M:%S')],
            ['Versão:', '2.0.0'],
            ['Sistema:', 'Automated Trading System'],
            ['Ativo:', 'XAUUSD (Gold)'],
            ['Plataforma:', 'MetaTrader 5'],
        ]
        
        info_table = Table(info_data, colWidths=[4*cm, 10*cm])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f4f8')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#333333')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        
        self.story.append(Spacer(1, 1*inch))
        self.story.append(info_table)
        self.story.append(PageBreak())
    
    def _adicionar_indice(self):
        """Adiciona índice"""
        
        titulo = Paragraph("ÍNDICE", self.styles['CustomSubtitle'])
        self.story.append(titulo)
        self.story.append(Spacer(1, 0.2*inch))
        
        indice_data = [
            ['1.', 'Visão Geral do Sistema', '3'],
            ['2.', 'Arquitetura e Componentes', '4'],
            ['3.', 'Estratégias de Trading', '6'],
            ['4.', 'Sistema de Machine Learning', '9'],
            ['5.', 'Gerenciamento de Risco', '11'],
            ['6.', 'Análise Técnica e Fundamental', '12'],
            ['7.', 'Execução e Monitoramento', '13'],
            ['8.', 'Integrações Externas', '14'],
            ['9.', 'Configurações e Parâmetros', '15'],
            ['10.', 'Logs e Auditoria', '16'],
        ]
        
        indice_table = Table(indice_data, colWidths=[1*cm, 12*cm, 2*cm])
        indice_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ]))
        
        self.story.append(indice_table)
        self.story.append(PageBreak())
    
    def _adicionar_visao_geral(self):
        """Adiciona seção de visão geral"""
        
        titulo = Paragraph("1. VISÃO GERAL DO SISTEMA", self.styles['CustomSubtitle'])
        self.story.append(titulo)
        
        texto = Paragraph(
            """
            O <b>URION Trading Bot</b> é um sistema automatizado de trading profissional desenvolvido 
            para operar no mercado de Gold (XAUUSD) através da plataforma MetaTrader 5. O sistema 
            utiliza múltiplas estratégias quantitativas combinadas com machine learning para 
            identificar oportunidades de trading com alta probabilidade de sucesso.
            """,
            self.styles['CustomBody']
        )
        self.story.append(texto)
        self.story.append(Spacer(1, 0.2*inch))
        
        # Características principais
        secao = Paragraph("1.1 Características Principais", self.styles['CustomSection'])
        self.story.append(secao)
        
        caracteristicas = [
            ['✓', '<b>6 Estratégias Profissionais</b>', 'Trend Following, Mean Reversion, Breakout, News Trading, Scalping, Range Trading'],
            ['✓', '<b>Machine Learning Integrado</b>', 'Sistema auto-otimizável que aprende com cada trade executado'],
            ['✓', '<b>Gerenciamento de Risco Avançado</b>', 'Stop Loss, Take Profit, Trailing Stop, Break-even automático'],
            ['✓', '<b>Análise Multi-dimensional</b>', '8+ indicadores técnicos, 3 fontes de notícias, análise de mercado em tempo real'],
            ['✓', '<b>Execução Automática 24/7</b>', 'Operação contínua com gestão de horários de mercado'],
            ['✓', '<b>Notificações em Tempo Real</b>', 'Telegram bot para acompanhamento remoto'],
        ]
        
        carac_table = Table(caracteristicas, colWidths=[1*cm, 5*cm, 9*cm])
        carac_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f4f8')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.green),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ]))
        
        self.story.append(carac_table)
        self.story.append(Spacer(1, 0.2*inch))
        
        # Métricas de performance
        secao = Paragraph("1.2 Métricas de Performance Target", self.styles['CustomSection'])
        self.story.append(secao)
        
        metricas = [
            ['Win Rate Objetivo', '≥ 60%', 'Sistema ajusta automaticamente para manter'],
            ['Risk:Reward Ratio', '1:3', 'Stop Loss 0.5% | Take Profit 1.5%'],
            ['Exposição Máxima', '2% por trade', 'Definido no Risk Manager'],
            ['Drawdown Máximo', '10%', 'Proteção de capital'],
            ['Tempo de Operação', '24/7', 'Exceto finais de semana'],
        ]
        
        metricas_table = Table(metricas, colWidths=[5*cm, 3*cm, 7*cm])
        metricas_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        
        self.story.append(metricas_table)
        self.story.append(PageBreak())
    
    def _adicionar_arquitetura(self):
        """Adiciona seção de arquitetura"""
        
        titulo = Paragraph("2. ARQUITETURA E COMPONENTES", self.styles['CustomSubtitle'])
        self.story.append(titulo)
        
        texto = Paragraph(
            """
            O sistema é construído com arquitetura modular, separando responsabilidades em 
            componentes especializados que comunicam entre si através de interfaces bem definidas.
            """,
            self.styles['CustomBody']
        )
        self.story.append(texto)
        self.story.append(Spacer(1, 0.2*inch))
        
        # Estrutura de diretórios
        secao = Paragraph("2.1 Estrutura de Diretórios", self.styles['CustomSection'])
        self.story.append(secao)
        
        estrutura = """
<font name="Courier" size="8">
urion/
├── src/
│   ├── core/                    # Núcleo do sistema
│   │   ├── mt5_connector.py     # Conexão MetaTrader 5
│   │   ├── strategy_executor.py # Executor de estratégias
│   │   ├── risk_manager.py      # Gerenciamento de risco
│   │   └── market_hours.py      # Controle de horários
│   ├── strategies/              # Estratégias de trading
│   │   ├── base_strategy.py     # Classe base
│   │   ├── trend_following.py   # Seguidor de tendência
│   │   ├── mean_reversion.py    # Reversão à média
│   │   ├── breakout.py          # Rompimento
│   │   ├── news_trading.py      # Baseada em notícias
│   │   ├── scalping.py          # Scalping rápido
│   │   └── range_trading.py     # Trading lateral
│   ├── ml/                      # Machine Learning
│   │   └── strategy_learner.py  # Sistema de aprendizagem
│   ├── analysis/                # Análises
│   │   ├── technical_analyzer.py # Análise técnica
│   │   └── news_analyzer.py     # Análise de notícias
│   ├── database/                # Persistência
│   │   └── strategy_stats.py    # Estatísticas
│   ├── notifications/           # Notificações
│   │   └── telegram_bot.py      # Bot Telegram
│   ├── order_generator.py       # Gerador de ordens (5 min)
│   └── order_manager.py         # Gerenciador (1 min)
├── config/                      # Configurações
│   └── config.yaml              # Arquivo principal
├── data/                        # Dados persistentes
│   └── learning_data.json       # Aprendizagem ML
├── logs/                        # Logs do sistema
│   ├── urion.log               # Log principal
│   └── error.log               # Erros
└── main.py                     # Entry point
</font>
        """
        
        self.story.append(Paragraph(estrutura, self.styles['CustomCode']))
        self.story.append(Spacer(1, 0.2*inch))
        
        # Componentes principais
        secao = Paragraph("2.2 Componentes Principais", self.styles['CustomSection'])
        self.story.append(secao)
        
        componentes = [
            ['<b>Order Generator</b>', 'Ciclo: 5 minutos', 'Analisa mercado, executa estratégias, gera sinais e abre posições'],
            ['<b>Order Manager</b>', 'Ciclo: 1 minuto', 'Monitora posições abertas, aplica trailing stop, break-even e fecha trades'],
            ['<b>MT5 Connector</b>', 'On-demand', 'Interface com MetaTrader 5, execução de ordens, consulta de dados'],
            ['<b>Strategy Executor</b>', 'On-demand', 'Executa estratégias, valida sinais, integra ML para decisões'],
            ['<b>Risk Manager</b>', 'On-demand', 'Valida exposição, calcula position size, gerencia SL/TP'],
            ['<b>Technical Analyzer</b>', 'On-demand', 'Calcula indicadores técnicos (RSI, MACD, Bollinger, etc)'],
            ['<b>News Analyzer</b>', 'On-demand', 'Coleta e analisa notícias de mercado (3 APIs)'],
            ['<b>Strategy Learner</b>', 'On-demand', 'Sistema ML que aprende e otimiza estratégias'],
            ['<b>Telegram Notifier</b>', 'On-demand', 'Envia notificações de trades e eventos'],
        ]
        
        comp_table = Table(componentes, colWidths=[4.5*cm, 3*cm, 7.5*cm])
        comp_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ]))
        
        self.story.append(comp_table)
        self.story.append(PageBreak())
    
    def _adicionar_estrategias(self):
        """Adiciona seção de estratégias"""
        
        titulo = Paragraph("3. ESTRATÉGIAS DE TRADING", self.styles['CustomSubtitle'])
        self.story.append(titulo)
        
        texto = Paragraph(
            """
            O sistema implementa 6 estratégias quantitativas profissionais, cada uma otimizada 
            para diferentes condições de mercado. Todas as estratégias são baseadas em análise 
            técnica e fundamentada em princípios matemáticos comprovados.
            """,
            self.styles['CustomBody']
        )
        self.story.append(texto)
        self.story.append(Spacer(1, 0.2*inch))
        
        estrategias = [
            {
                'nome': '3.1 Trend Following (Seguidor de Tendência)',
                'descricao': 'Identifica e opera na direção de tendências estabelecidas',
                'condicoes': [
                    'ADX > 25 (tendência forte)',
                    'EMA 20 cruza EMA 50',
                    'RSI confirma direção (>50 buy, <50 sell)',
                    'MACD histogram positivo/negativo',
                    'Volume acima da média'
                ],
                'timeframe': 'H1 (1 hora)',
                'ciclo': '300s (5 minutos)',
                'magic': '100541',
                'rr': '1:3 (Stop 0.5%, Target 1.5%)'
            },
            {
                'nome': '3.2 Mean Reversion (Reversão à Média)',
                'descricao': 'Opera em reversões quando preço se afasta muito da média',
                'condicoes': [
                    'Bollinger Bands: preço toca banda extrema',
                    'RSI sobrecomprado (>70) ou sobrevendido (<30)',
                    'Preço > 2 desvios padrão da média',
                    'Momentum indica exaustão',
                    'Volume confirma reversão'
                ],
                'timeframe': 'M30 (30 minutos)',
                'ciclo': '180s (3 minutos)',
                'magic': '100512',
                'rr': '1:2 (Stop 0.5%, Target 1.0%)'
            },
            {
                'nome': '3.3 Breakout (Rompimento)',
                'descricao': 'Identifica e opera rompimentos de níveis-chave',
                'condicoes': [
                    'Preço rompe resistência/suporte com força',
                    'Volume > 150% da média (confirmação)',
                    'ATR aumentando (volatilidade)',
                    'Consolidação prévia identificada',
                    'False breakout filter ativo'
                ],
                'timeframe': 'M15 (15 minutos)',
                'ciclo': '240s (4 minutos)',
                'magic': '100517',
                'rr': '1:3 (Stop 0.4%, Target 1.2%)'
            },
            {
                'nome': '3.4 News Trading (Baseada em Notícias)',
                'descricao': 'Opera baseada em eventos de notícias de alto impacto',
                'condicoes': [
                    'Notícia de alto impacto detectada',
                    'Sentimento claro (>0.3 positivo ou <-0.3 negativo)',
                    'Múltiplas fontes confirmam (2+ APIs)',
                    'Momentum técnico alinhado',
                    'Volatilidade adequada'
                ],
                'timeframe': 'M5 (5 minutos)',
                'ciclo': '120s (2 minutos)',
                'magic': '100540',
                'rr': '1:2 (Stop 0.3%, Target 0.6%)'
            },
            {
                'nome': '3.5 Scalping (Operações Rápidas)',
                'descricao': 'Captura pequenos movimentos em alta frequência',
                'condicoes': [
                    'RSI neutro (40-60) com momentum',
                    'Price action favorável (candlesticks)',
                    'Spread baixo (<5 pips)',
                    'Liquidez alta (volume)',
                    'Rápida entrada e saída'
                ],
                'timeframe': 'M5 (5 minutos)',
                'ciclo': '60s (1 minuto)',
                'magic': '100531',
                'rr': '1:1.5 (Stop 0.2%, Target 0.3%)'
            },
            {
                'nome': '3.6 Range Trading (Mercado Lateral)',
                'descricao': 'Opera em mercados laterais entre suporte e resistência',
                'condicoes': [
                    'ADX < 25 (sem tendência definida)',
                    'Preço entre bandas de Bollinger',
                    'RSI neutro (30-70)',
                    'Compra no suporte, vende na resistência',
                    'Mean reversion em range definido'
                ],
                'timeframe': 'M30 (30 minutos)',
                'ciclo': '180s (3 minutos)',
                'magic': '100525',
                'rr': '1:2 (Stop 0.5%, Target 1.0%)'
            }
        ]
        
        for est in estrategias:
            # Nome da estratégia
            nome_para = Paragraph(f"<b>{est['nome']}</b>", self.styles['CustomSection'])
            self.story.append(nome_para)
            
            # Descrição
            desc_para = Paragraph(est['descricao'], self.styles['CustomBody'])
            self.story.append(desc_para)
            self.story.append(Spacer(1, 0.1*inch))
            
            # Detalhes técnicos
            detalhes = [
                ['Timeframe', est['timeframe']],
                ['Ciclo de Análise', est['ciclo']],
                ['Magic Number', est['magic']],
                ['Risk:Reward', est['rr']],
            ]
            
            det_table = Table(detalhes, colWidths=[4*cm, 11*cm])
            det_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f5f5f5')),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ]))
            
            self.story.append(det_table)
            self.story.append(Spacer(1, 0.1*inch))
            
            # Condições de entrada
            cond_para = Paragraph("<b>Condições de Entrada:</b>", self.styles['Highlight'])
            self.story.append(cond_para)
            
            for cond in est['condicoes']:
                bullet = Paragraph(f"• {cond}", self.styles['CustomBody'])
                self.story.append(bullet)
            
            self.story.append(Spacer(1, 0.15*inch))
        
        self.story.append(PageBreak())
    
    def _adicionar_machine_learning(self):
        """Adiciona seção de ML"""
        
        titulo = Paragraph("4. SISTEMA DE MACHINE LEARNING", self.styles['CustomSubtitle'])
        self.story.append(titulo)
        
        texto = Paragraph(
            """
            O sistema integra um motor de machine learning que aprende continuamente com 
            os resultados dos trades executados, ajustando automaticamente os parâmetros 
            das estratégias para otimizar a performance ao longo do tempo.
            """,
            self.styles['CustomBody']
        )
        self.story.append(texto)
        self.story.append(Spacer(1, 0.2*inch))
        
        # Arquitetura ML
        secao = Paragraph("4.1 Arquitetura do Sistema de Aprendizagem", self.styles['CustomSection'])
        self.story.append(secao)
        
        texto = Paragraph(
            """
            <b>Componente Principal:</b> <font color="#0066cc">StrategyLearner</font> (400+ linhas)<br/>
            <b>Localização:</b> src/ml/strategy_learner.py<br/>
            <b>Armazenamento:</b> data/learning_data.json<br/>
            <b>Integrado em:</b> Order Generator (pré-trade) e Order Manager (pós-trade)
            """,
            self.styles['CustomBody']
        )
        self.story.append(texto)
        self.story.append(Spacer(1, 0.15*inch))
        
        # Ciclo de aprendizagem
        secao = Paragraph("4.2 Ciclo de Aprendizagem Completo", self.styles['CustomSection'])
        self.story.append(secao)
        
        fases = [
            ['<b>FASE 1: PRÉ-TRADE</b>', 'Order Generator', 
             '1. Estratégia detecta sinal\n2. Learner consulta histórico\n3. Se ≥10 trades: usa min_confidence aprendido\n4. Decide se executa\n5. Abre posição se aprovado'],
            ['<b>FASE 2: DURANTE</b>', 'Order Manager',
             '1. Monitora posição (ciclo 1 min)\n2. Aplica break-even automático\n3. Aplica trailing stop\n4. Registra métricas em tempo real'],
            ['<b>FASE 3: PÓS-TRADE</b>', 'Order Manager',
             '1. Trade fecha (TP/SL/manual)\n2. Busca resultado no histórico MT5\n3. Extrai: profit, confidence, duração\n4. Chama learner.learn_from_trade()\n5. Atualiza estatísticas\n6. A cada 20 trades: AUTO-AJUSTA\n7. Salva em learning_data.json'],
        ]
        
        fases_table = Table(fases, colWidths=[3*cm, 3*cm, 9*cm])
        fases_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#e8f4f8')),
            ('BACKGROUND', (0, 1), (1, 1), colors.HexColor('#fff3cd')),
            ('BACKGROUND', (0, 2), (1, 2), colors.HexColor('#d4edda')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        
        self.story.append(fases_table)
        self.story.append(Spacer(1, 0.2*inch))
        
        # Algoritmo de auto-ajuste
        secao = Paragraph("4.3 Algoritmo de Auto-ajuste", self.styles['CustomSection'])
        self.story.append(secao)
        
        algoritmo = """
<font name="Courier" size="8">
A cada 20 trades:
  
  SE win_rate > 70%:
      min_confidence -= 5%
      # Estratégia está boa, pode ser menos seletiva
      # Opera mais trades
  
  SE win_rate < 50%:
      min_confidence += 5%
      # Estratégia precisa melhorar, fica mais seletiva
      # Opera apenas sinais muito fortes
  
  SENÃO:
      # Win rate entre 50-70%, mantém configuração
      pass

Limites: min_confidence entre 40% e 80%
</font>
        """
        
        self.story.append(Paragraph(algoritmo, self.styles['CustomCode']))
        self.story.append(Spacer(1, 0.2*inch))
        
        # Métricas aprendidas
        secao = Paragraph("4.4 Métricas e Dados Aprendidos", self.styles['CustomSection'])
        self.story.append(secao)
        
        metricas_ml = [
            ['Total de Trades', 'Contador de execuções por estratégia'],
            ['Win Rate', 'Percentual de trades vencedores'],
            ['Profit Factor', 'Razão entre lucros e prejuízos'],
            ['Avg Profit/Loss', 'Média de lucro e prejuízo por trade'],
            ['Best Confidence Range', 'Faixa ótima de confidence para operar'],
            ['Market Conditions', 'Condições de mercado mais favoráveis'],
            ['Time Analysis', 'Melhores horários para cada estratégia'],
            ['Consistency Score', 'Estabilidade da performance'],
        ]
        
        metricas_ml_table = Table(metricas_ml, colWidths=[5*cm, 10*cm])
        metricas_ml_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f8ff')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ]))
        
        self.story.append(metricas_ml_table)
        self.story.append(PageBreak())
    
    def _adicionar_risk_management(self):
        """Adiciona seção de gerenciamento de risco"""
        
        titulo = Paragraph("5. GERENCIAMENTO DE RISCO", self.styles['CustomSubtitle'])
        self.story.append(titulo)
        
        texto = Paragraph(
            """
            O sistema implementa múltiplas camadas de proteção de capital, desde validação 
            pré-trade até gerenciamento ativo de posições abertas.
            """,
            self.styles['CustomBody']
        )
        self.story.append(texto)
        self.story.append(Spacer(1, 0.2*inch))
        
        # Parâmetros de risco
        secao = Paragraph("5.1 Parâmetros de Risco", self.styles['CustomSection'])
        self.story.append(secao)
        
        parametros = [
            ['Exposição Máxima por Trade', '2%', 'Do capital total da conta'],
            ['Lot Fixo', '0.01', 'Tamanho padronizado de posição'],
            ['Stop Loss Padrão', '0.5%', 'Distância do preço de entrada'],
            ['Take Profit Padrão', '1.5%', 'Risk:Reward de 1:3'],
            ['Máximo de Posições Simultâneas', '5', 'Limite de exposição total'],
            ['Drawdown Máximo Permitido', '10%', 'Sistema alerta se ultrapassar'],
        ]
        
        param_table = Table(parametros, colWidths=[6*cm, 3*cm, 6*cm])
        param_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#dc3545')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        
        self.story.append(param_table)
        self.story.append(Spacer(1, 0.2*inch))
        
        # Funcionalidades de proteção
        secao = Paragraph("5.2 Funcionalidades de Proteção", self.styles['CustomSection'])
        self.story.append(secao)
        
        protecoes = [
            ['<b>Break-even Automático</b>',
             'Move SL para preço de entrada quando trade atinge 50% do TP, garantindo que não há perda'],
            ['<b>Trailing Stop</b>',
             'Acompanha o preço favorável, protegendo lucros acumulados e deixando o trade correr'],
            ['<b>Fechamento por Horário</b>',
             'Fecha todas posições antes do fechamento do mercado (Sexta 16:30 GMT)'],
            ['<b>Validação Pré-trade</b>',
             'Verifica margem disponível, exposição total e condições de mercado antes de abrir posição'],
            ['<b>Fechamento Parcial</b>',
             'Pode fechar parte da posição ao atingir objetivos intermediários (configurável)'],
        ]
        
        prot_table = Table(protecoes, colWidths=[5*cm, 10*cm])
        prot_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ]))
        
        self.story.append(prot_table)
        self.story.append(PageBreak())
    
    def _adicionar_analises(self):
        """Adiciona seção de análises"""
        
        titulo = Paragraph("6. ANÁLISE TÉCNICA E FUNDAMENTAL", self.styles['CustomSubtitle'])
        self.story.append(titulo)
        
        # Análise Técnica
        secao = Paragraph("6.1 Indicadores Técnicos Utilizados", self.styles['CustomSection'])
        self.story.append(secao)
        
        indicadores = [
            ['RSI', 'Relative Strength Index', 'Sobrecompra/sobrevenda, período 14'],
            ['MACD', 'Moving Average Convergence Divergence', 'Tendência e momentum, 12/26/9'],
            ['Bollinger Bands', 'Bandas de Bollinger', 'Volatilidade, 20 períodos, 2 desvios'],
            ['EMA', 'Exponential Moving Average', 'Médias 20 e 50 períodos'],
            ['ADX', 'Average Directional Index', 'Força da tendência, período 14'],
            ['ATR', 'Average True Range', 'Volatilidade, período 14'],
            ['Volume', 'Volume de negociação', 'Confirmação de movimentos'],
            ['Stochastic', 'Oscilador Estocástico', 'Momentum, %K(14) %D(3)'],
        ]
        
        ind_table = Table(indicadores, colWidths=[3*cm, 5*cm, 7*cm])
        ind_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#17a2b8')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        
        self.story.append(ind_table)
        self.story.append(Spacer(1, 0.2*inch))
        
        # Análise Fundamental
        secao = Paragraph("6.2 Análise de Notícias (News Analysis)", self.styles['CustomSection'])
        self.story.append(secao)
        
        texto = Paragraph(
            """
            O sistema integra 3 APIs de notícias financeiras para análise fundamental em tempo real:
            """,
            self.styles['CustomBody']
        )
        self.story.append(texto)
        self.story.append(Spacer(1, 0.1*inch))
        
        apis_news = [
            ['Alpha Vantage', 'Notícias de mercado global', 'Cobertura ampla, dados históricos'],
            ['Finnhub', 'Notícias específicas de Gold/Forex', 'Alta frequência, baixa latência'],
            ['Finazon', 'Análise de sentimento', 'NLP para sentimento do mercado'],
        ]
        
        apis_table = Table(apis_news, colWidths=[4*cm, 5*cm, 6*cm])
        apis_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ]))
        
        self.story.append(apis_table)
        self.story.append(Spacer(1, 0.15*inch))
        
        texto = Paragraph(
            """
            <b>Processamento de Notícias:</b> O sistema coleta notícias a cada ciclo, analisa o 
            sentimento (positivo/negativo/neutro), pondera por relevância e combina com análise 
            técnica para decisões de trading mais informadas.
            """,
            self.styles['CustomBody']
        )
        self.story.append(texto)
        self.story.append(PageBreak())
    
    def _adicionar_execucao(self):
        """Adiciona seção de execução"""
        
        titulo = Paragraph("7. EXECUÇÃO E MONITORAMENTO", self.styles['CustomSubtitle'])
        self.story.append(titulo)
        
        # Order Generator
        secao = Paragraph("7.1 Order Generator (Gerador de Ordens)", self.styles['CustomSection'])
        self.story.append(secao)
        
        texto = Paragraph(
            """
            <b>Arquivo:</b> src/order_generator.py<br/>
            <b>Ciclo:</b> 5 minutos (300 segundos)<br/>
            <b>Função:</b> Analisa mercado e abre novas posições
            """,
            self.styles['CustomBody']
        )
        self.story.append(texto)
        self.story.append(Spacer(1, 0.1*inch))
        
        fluxo_gen = [
            '1. Verifica conexão MT5',
            '2. Consulta Market Hours (horário de operação)',
            '3. Para cada estratégia ativa:',
            '   • Executa análise técnica',
            '   • Executa análise de notícias (se aplicável)',
            '   • Gera sinal de trading',
            '   • Consulta ML Learner (usa confidence aprendido)',
            '   • Valida com Risk Manager',
            '4. Se sinal aprovado: abre posição no MT5',
            '5. Envia notificação Telegram',
            '6. Salva trade no database',
            '7. Aguarda próximo ciclo (5 min)',
        ]
        
        for item in fluxo_gen:
            p = Paragraph(item, self.styles['CustomBody'])
            self.story.append(p)
        
        self.story.append(Spacer(1, 0.2*inch))
        
        # Order Manager
        secao = Paragraph("7.2 Order Manager (Gerenciador de Ordens)", self.styles['CustomSection'])
        self.story.append(secao)
        
        texto = Paragraph(
            """
            <b>Arquivo:</b> src/order_manager.py<br/>
            <b>Ciclo:</b> 1 minuto (60 segundos)<br/>
            <b>Função:</b> Monitora e gerencia posições abertas
            """,
            self.styles['CustomBody']
        )
        self.story.append(texto)
        self.story.append(Spacer(1, 0.1*inch))
        
        fluxo_man = [
            '1. Verifica conexão MT5',
            '2. Obtém todas posições abertas',
            '3. Atualiza lista de posições monitoradas',
            '4. Para cada posição:',
            '   • Verifica se deve aplicar break-even',
            '   • Calcula e aplica trailing stop',
            '   • Verifica fechamento parcial (se habilitado)',
            '   • Atualiza métricas (lucro máx/mín)',
            '5. Verifica horário de fechamento de mercado',
            '6. Se trade fechou: chama ML Learner',
            '7. Aguarda próximo ciclo (1 min)',
        ]
        
        for item in fluxo_man:
            p = Paragraph(item, self.styles['CustomBody'])
            self.story.append(p)
        
        self.story.append(PageBreak())
    
    def _adicionar_integracoes(self):
        """Adiciona seção de integrações"""
        
        titulo = Paragraph("8. INTEGRAÇÕES EXTERNAS", self.styles['CustomSubtitle'])
        self.story.append(titulo)
        
        # MetaTrader 5
        secao = Paragraph("8.1 MetaTrader 5 (MT5)", self.styles['CustomSection'])
        self.story.append(secao)
        
        texto = Paragraph(
            """
            <b>Biblioteca:</b> MetaTrader5 (Python)<br/>
            <b>Conexão:</b> Via credenciais (.env): LOGIN, PASSWORD, SERVER, PATH<br/>
            <b>Operações:</b>
            """,
            self.styles['CustomBody']
        )
        self.story.append(texto)
        
        mt5_ops = [
            '• Consulta de cotações (bid/ask)',
            '• Consulta de histórico de preços (OHLCV)',
            '• Abertura de ordens (market, limit, stop)',
            '• Modificação de posições (SL/TP)',
            '• Fechamento de posições',
            '• Consulta de conta (balance, equity, margin)',
            '• Consulta de histórico de trades',
        ]
        
        for op in mt5_ops:
            p = Paragraph(op, self.styles['CustomBody'])
            self.story.append(p)
        
        self.story.append(Spacer(1, 0.2*inch))
        
        # Telegram
        secao = Paragraph("8.2 Telegram Bot", self.styles['CustomSection'])
        self.story.append(secao)
        
        texto = Paragraph(
            """
            <b>Bot:</b> @Sinal_Analista_Virtus_Bot<br/>
            <b>Biblioteca:</b> python-telegram-bot<br/>
            <b>Funcionalidades:</b>
            """,
            self.styles['CustomBody']
        )
        self.story.append(texto)
        
        telegram_funcs = [
            '• Notificação de abertura de trades',
            '• Notificação de fechamento de trades',
            '• Alertas de break-even aplicado',
            '• Alertas de fechamento parcial',
            '• Avisos de fechamento de mercado',
            '• Relatórios de performance',
            '• Comandos interativos (status, posições, etc)',
        ]
        
        for func in telegram_funcs:
            p = Paragraph(func, self.styles['CustomBody'])
            self.story.append(p)
        
        self.story.append(Spacer(1, 0.2*inch))
        
        # Database
        secao = Paragraph("8.3 Database (SQLite)", self.styles['CustomSection'])
        self.story.append(secao)
        
        texto = Paragraph(
            """
            <b>Arquivo:</b> data/trading.db<br/>
            <b>Tabelas:</b> strategy_stats, trades, performance_metrics<br/>
            <b>Uso:</b> Persistência de histórico, estatísticas e métricas de performance
            """,
            self.styles['CustomBody']
        )
        self.story.append(texto)
        
        self.story.append(PageBreak())
    
    def _adicionar_configuracoes(self):
        """Adiciona seção de configurações"""
        
        titulo = Paragraph("9. CONFIGURAÇÕES E PARÂMETROS", self.styles['CustomSubtitle'])
        self.story.append(titulo)
        
        texto = Paragraph(
            """
            O sistema é altamente configurável através do arquivo <b>config/config.yaml</b>. 
            Abaixo estão as principais seções:
            """,
            self.styles['CustomBody']
        )
        self.story.append(texto)
        self.story.append(Spacer(1, 0.15*inch))
        
        config_sections = [
            ['<b>trading</b>', 'Symbol, timeframe, max_positions, lot_size'],
            ['<b>risk_management</b>', 'Max_risk_per_trade, max_daily_loss, default_sl_pct, default_tp_pct'],
            ['<b>strategies</b>', 'Habilitação, ciclos e parâmetros de cada estratégia'],
            ['<b>order_generator</b>', 'Enabled, cycle_interval, min_confidence'],
            ['<b>order_manager</b>', 'Enabled, cycle_interval, break_even, trailing_stop, partial_close'],
            ['<b>market_hours</b>', 'Trading hours, pre_close_minutes'],
            ['<b>telegram</b>', 'Bot token, chat_id, notifications enabled'],
            ['<b>apis</b>', 'Keys para Alpha Vantage, Finnhub, Finazon'],
            ['<b>database</b>', 'Path do arquivo SQLite'],
            ['<b>logging</b>', 'Level, formato, arquivos de log'],
        ]
        
        config_table = Table(config_sections, colWidths=[4*cm, 11*cm])
        config_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ]))
        
        self.story.append(config_table)
        self.story.append(Spacer(1, 0.2*inch))
        
        # Variáveis de ambiente
        secao = Paragraph("9.1 Variáveis de Ambiente (.env)", self.styles['CustomSection'])
        self.story.append(secao)
        
        env_vars = [
            ['MT5_LOGIN', 'Login da conta MetaTrader 5'],
            ['MT5_PASSWORD', 'Senha da conta MT5'],
            ['MT5_SERVER', 'Servidor da corretora'],
            ['MT5_PATH', 'Caminho para terminal64.exe'],
            ['TELEGRAM_BOT_TOKEN', 'Token do bot Telegram'],
            ['TELEGRAM_CHAT_ID', 'ID do chat para notificações'],
            ['ALPHA_VANTAGE_API_KEY', 'Key da API Alpha Vantage'],
            ['FINNHUB_API_KEY', 'Key da API Finnhub'],
            ['FINAZON_API_KEY', 'Key da API Finazon'],
        ]
        
        env_table = Table(env_vars, colWidths=[5*cm, 10*cm])
        env_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#fff3cd')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        
        self.story.append(env_table)
        self.story.append(PageBreak())
    
    def _adicionar_logs_auditoria(self):
        """Adiciona seção de logs"""
        
        titulo = Paragraph("10. LOGS E AUDITORIA", self.styles['CustomSubtitle'])
        self.story.append(titulo)
        
        texto = Paragraph(
            """
            O sistema mantém logs detalhados de todas as operações para auditoria 
            e troubleshooting. Utiliza a biblioteca <b>loguru</b> para logging estruturado.
            """,
            self.styles['CustomBody']
        )
        self.story.append(texto)
        self.story.append(Spacer(1, 0.15*inch))
        
        # Arquivos de log
        secao = Paragraph("10.1 Arquivos de Log", self.styles['CustomSection'])
        self.story.append(secao)
        
        log_files = [
            ['logs/urion.log', 'Log principal do sistema', 'Todas operações, INFO e superior'],
            ['logs/error.log', 'Log de erros', 'Apenas erros e exceções, ERROR e CRITICAL'],
            ['logs/trades.log', 'Log específico de trades', 'Aberturas e fechamentos de posições'],
        ]
        
        log_table = Table(log_files, colWidths=[4*cm, 5*cm, 6*cm])
        log_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6c757d')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        
        self.story.append(log_table)
        self.story.append(Spacer(1, 0.2*inch))
        
        # Níveis de log
        secao = Paragraph("10.2 Níveis de Log Utilizados", self.styles['CustomSection'])
        self.story.append(secao)
        
        log_levels = [
            ['DEBUG', 'Informações detalhadas para debugging', 'Análises técnicas, validações'],
            ['INFO', 'Eventos normais do sistema', 'Ciclos, conexões, sinais'],
            ['SUCCESS', 'Operações bem-sucedidas', 'Trades executados, posições fechadas'],
            ['WARNING', 'Avisos não-críticos', 'Reconexões, sinais rejeitados'],
            ['ERROR', 'Erros que não param execução', 'Falhas em APIs, timeouts'],
            ['CRITICAL', 'Erros críticos do sistema', 'Falha de conexão MT5, erros fatais'],
        ]
        
        levels_table = Table(log_levels, colWidths=[3*cm, 5*cm, 7*cm])
        levels_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ]))
        
        self.story.append(levels_table)
        self.story.append(Spacer(1, 0.2*inch))
        
        # Auditoria
        secao = Paragraph("10.3 Rastreabilidade e Auditoria", self.styles['CustomSection'])
        self.story.append(secao)
        
        texto = Paragraph(
            """
            Cada trade executado possui rastreabilidade completa:
            """,
            self.styles['CustomBody']
        )
        self.story.append(texto)
        
        audit_items = [
            '• Timestamp de abertura e fechamento',
            '• Estratégia que gerou o sinal',
            '• Confidence score do sinal',
            '• Condições de mercado (indicadores)',
            '• Notícias consideradas (se aplicável)',
            '• Preço de entrada, SL e TP',
            '• Modificações aplicadas (break-even, trailing)',
            '• Resultado final (lucro/prejuízo)',
            '• Dados salvos no database e logs',
            '• Aprendizagem registrada no ML system',
        ]
        
        for item in audit_items:
            p = Paragraph(item, self.styles['CustomBody'])
            self.story.append(p)
        
        self.story.append(Spacer(1, 0.3*inch))
        
        # Conclusão
        conclusao = Paragraph(
            """
            <b>Este documento fornece uma visão completa do sistema URION Trading Bot.</b><br/><br/>
            O sistema é robusto, altamente configurável e implementa as melhores práticas de 
            trading automatizado, com múltiplas camadas de proteção de capital e capacidade 
            de aprendizagem contínua através de machine learning.<br/><br/>
            Para mais informações técnicas, consulte o código-fonte e documentação inline 
            nos arquivos Python.
            """,
            self.styles['CustomBody']
        )
        self.story.append(conclusao)
    
    def gerar(self):
        """Gera o PDF completo"""
        
        print("\n🔧 Gerando documentação de auditoria em PDF...\n")
        
        # Adicionar todas as seções
        self._adicionar_capa()
        self._adicionar_indice()
        self._adicionar_visao_geral()
        self._adicionar_arquitetura()
        self._adicionar_estrategias()
        self._adicionar_machine_learning()
        self._adicionar_risk_management()
        self._adicionar_analises()
        self._adicionar_execucao()
        self._adicionar_integracoes()
        self._adicionar_configuracoes()
        self._adicionar_logs_auditoria()
        
        # Construir PDF
        self.doc.build(self.story)
        
        print(f"✅ PDF gerado com sucesso: {self.filename}\n")
        print(f"📄 Total de páginas: ~16-18 páginas")
        print(f"📊 Tamanho estimado: ~500-800 KB\n")
        
        return self.filename


if __name__ == "__main__":
    # Gerar auditoria
    auditoria = AuditoriaBot()
    filename = auditoria.gerar()
    
    print(f"🎉 Documento de auditoria pronto para sua equipe!")
    print(f"📁 Localização: {os.path.abspath(filename)}")
