# 🚀 Guia de Launchers - Urion Trading Bot

## 📁 Arquivos Executáveis

### 1. `start_bot.ps1` ⭐ RECOMENDADO

**Menu interativo completo em PowerShell**

#### Como usar:
1. Duplo clique em `start_bot.ps1`
2. Se aparecer aviso de segurança, clique em "Executar mesmo assim"
3. Navegue pelo menu usando números 1-6

#### Funcionalidades:
- ✅ Verificação automática de Python
- ✅ Criação automática de ambiente virtual
- ✅ Instalação automática de dependências
- ✅ Verificação de .env (cria se não existir)
- ✅ Interface colorida e moderna
- ✅ Feedback visual detalhado

#### Menu:
```
1. Verificar Setup      - Executa verify_setup.py
2. Executar Bot         - Inicia main.py
3. Ver Logs            - Logs em tempo real
4. Editar Configurações - Abre config.yaml
5. Editar Credenciais  - Abre .env
6. Sair                - Encerra
```

#### Primeira Execução:
```powershell
# O launcher faz automaticamente:
1. Verifica Python instalado
2. Cria venv se necessário
3. Ativa ambiente virtual
4. Instala dependências
5. Verifica .env
   - Se não existir, copia .env.example
   - Abre notepad para configurar
6. Mostra menu principal
```

---

### 2. `start_bot.bat`

**Menu interativo em CMD (Prompt de Comando)**

#### Como usar:
1. Duplo clique em `start_bot.bat`
2. Navegue pelo menu usando números 1-6

#### Funcionalidades:
Mesmas do PowerShell, mas em interface CMD tradicional.

#### Quando usar:
- Se start_bot.ps1 não funcionar
- Preferência por interface CMD
- Ambientes onde PowerShell está bloqueado

---

### 3. `run_bot.bat`

**Execução direta e rápida**

#### Como usar:
1. Duplo clique em `run_bot.bat`
2. Bot inicia imediatamente

#### O que faz:
```batch
1. Ativa ambiente virtual
2. Executa python main.py
3. Pausa ao final (mostra saída)
```

#### Quando usar:
- Uso diário rápido
- Quando setup já está OK
- Não precisa do menu

#### ⚠️ Atenção:
Assume que venv e dependências já estão instaladas.
Use start_bot.ps1 na primeira vez!

---

## 🎯 Qual Usar?

### Primeira Vez → `start_bot.ps1`
**Por quê?**
- Verifica e configura tudo
- Interface amigável
- Detecta problemas

### Uso Diário → `run_bot.bat`
**Por quê?**
- Mais rápido
- Direto ao ponto
- Menos cliques

### Problemas → `start_bot.ps1`
**Por quê?**
- Menu com diagnóstico
- Ver logs em tempo real
- Editar configurações facilmente

---

## 🔧 Resolução de Problemas

### Erro: "Scripts desabilitados no PowerShell"

**Solução:**
```powershell
# Execute como Administrador:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Ou execute assim:
powershell -ExecutionPolicy Bypass -File start_bot.ps1
```

### Erro: "Python não encontrado"

**Solução:**
1. Instale Python 3.11+ de python.org
2. Marque "Add to PATH" durante instalação
3. Reinicie terminal/computador
4. Teste: `python --version`

### Erro: ".env não configurado"

**Solução:**
1. Execute `start_bot.ps1`
2. Escolha opção 5 (Editar Credenciais)
3. Configure:
   ```
   MT5_LOGIN=seu_login
   MT5_PASSWORD=sua_senha
   MT5_SERVER=Pepperstone-Demo
   MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe
   TELEGRAM_BOT_TOKEN=seu_token
   TELEGRAM_CHAT_ID=seu_chat_id
   ```
4. Salve e feche

### Bot não conecta ao MT5

**Verificar:**
1. MT5 está instalado?
2. MT5_PATH correto no .env?
3. Login/senha corretos?
4. É conta DEMO (para testes)?
5. MT5 está aberto?

**Dica:** Use opção 1 do menu (Verificar Setup)

---

## 📊 Fluxo Recomendado

### Primeira Vez (Setup Completo)

```
1. Duplo clique start_bot.ps1
   ↓
2. Aguarda verificação automática
   ↓
3. Configura .env quando solicitado
   ↓
4. Executa novamente start_bot.ps1
   ↓
5. Escolhe opção 1 (Verificar Setup)
   ↓
6. Escolhe opção 2 (Executar Bot)
   ↓
7. Monitora primeira execução
```

### Uso Diário

```
1. Duplo clique run_bot.bat
   ↓
2. Bot inicia e opera
   ↓
3. Monitora via Telegram
```

### Verificar Logs

```
1. Duplo clique start_bot.ps1
   ↓
2. Escolhe opção 3 (Ver Logs)
   ↓
3. Logs em tempo real
   ↓
4. Ctrl+C para voltar ao menu
```

### Ajustar Configurações

```
1. Duplo clique start_bot.ps1
   ↓
2. Escolhe opção 4 (Config) ou 5 (.env)
   ↓
3. Edita no Notepad
   ↓
4. Salva e reinicia bot
```

---

## 💡 Dicas

### 1. Atalho na Área de Trabalho
```
Clique direito em start_bot.ps1
→ Enviar para → Área de trabalho (criar atalho)
```

### 2. Executar ao Iniciar Windows
```
Windows + R → shell:startup
→ Cole atalho de run_bot.bat
```

### 3. Monitoramento Remoto
```
Telegram configurado?
→ Monitore de qualquer lugar
→ Comandos: /status, /balance, /positions
```

### 4. Múltiplas Contas
```
Crie pastas separadas:
urion_conta1/
urion_conta2/
Cada uma com .env diferente
```

---

## 🎓 Comandos Úteis

### Verificar Status
```powershell
# Via launcher
start_bot.ps1 → Opção 1

# Via Python
python verify_setup.py
```

### Ver Logs Manualmente
```powershell
# Logs gerais
Get-Content logs\urion.log -Wait -Tail 50

# Apenas erros
Get-Content logs\error.log -Wait -Tail 20
```

### Parar Bot
```
Ctrl + C no terminal
ou
Fechar janela do terminal
```

### Limpar Cache
```powershell
# Remover ambiente virtual
Remove-Item -Recurse -Force venv

# Reinstalar
start_bot.ps1 → cria novo venv automaticamente
```

---

## 📋 Checklist de Primeira Execução

- [ ] Python 3.11+ instalado
- [ ] Git instalado (opcional)
- [ ] MT5 instalado (conta demo)
- [ ] Bot do Telegram criado (@BotFather)
- [ ] .env configurado
- [ ] Duplo clique em start_bot.ps1
- [ ] Opção 1: Verificar Setup ✅
- [ ] Todos os checks passaram ✅
- [ ] Opção 2: Executar Bot
- [ ] Recebeu mensagem no Telegram ✅
- [ ] Bot está operando ✅

---

## 🆘 Suporte

### Problemas?

1. **Execute:** `start_bot.ps1` → Opção 1 (Verificar Setup)
2. **Leia:** `COMECAR_AQUI.md` (problemas comuns)
3. **Consulte:** `PROXIMOS_PASSOS.md` (guia completo)
4. **Verifique:** `logs/error.log` (erros específicos)

### Documentação Completa

- `COMECAR_AQUI.md` - Resumo executivo
- `PROXIMOS_PASSOS.md` - Guia completo de testes
- `README.md` - Visão geral
- `docs/QUICKSTART.md` - Início rápido detalhado

---

## 🎉 Pronto para Usar!

**Início Rápido:**
1. Duplo clique em `start_bot.ps1`
2. Configure .env quando solicitado
3. Escolha opção 2 (Executar Bot)
4. Monitore via Telegram

**Uso Diário:**
1. Duplo clique em `run_bot.bat`
2. Bot inicia automaticamente
3. Monitore via Telegram

**Boa sorte! 🚀📈**

---

**Última Atualização:** 18 de novembro de 2025  
**Versão:** 1.0  
**Sistema:** Windows 10/11
