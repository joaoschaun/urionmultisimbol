# 🚀 Launchers do Urion Trading Bot

Este diretório contém **4 formas diferentes** de iniciar o bot com o ambiente virtual (venv) ativado automaticamente.

---

## 📁 Arquivos Disponíveis

### 1️⃣ **start.ps1** (RECOMENDADO) ✨
**Launcher PowerShell simples e rápido**

```powershell
.\start.ps1
```

**Características:**
- ✅ Ativa venv automaticamente
- ✅ Verifica dependências
- ✅ Interface limpa e colorida
- ✅ Cria venv se não existir
- ✅ Tratamento de erros
- ⚡ **Mais rápido e moderno**

---

### 2️⃣ **start_urion.bat** 
**Launcher .bat simples (compatível com Windows antigo)**

```cmd
start_urion.bat
```

**Características:**
- ✅ Ativa venv automaticamente
- ✅ Interface básica
- ✅ Funciona em qualquer Windows
- 💻 Bom para atalhos na área de trabalho

---

### 3️⃣ **urion_launcher.bat**
**Launcher .bat com MENU INTERATIVO**

```cmd
urion_launcher.bat
```

**Características:**
- ✅ Menu com 7 opções
- ✅ Verificar status do sistema
- ✅ Ver logs em tempo real
- ✅ Parar bot
- ✅ Instalar dependências
- ✅ Abrir dashboard
- 🎯 **Melhor para gerenciamento completo**

**Menu:**
```
1. Iniciar Bot (com VENV)
2. Verificar Status do Sistema
3. Ver Logs em Tempo Real
4. Parar Bot
5. Instalar/Atualizar Dependencias
6. Abrir Dashboard Web
7. Sair
```

---

### 4️⃣ **start_bot.ps1** (Já existente)
**Launcher PowerShell completo com menu**

```powershell
.\start_bot.ps1
```

**Características:**
- ✅ Menu completo
- ✅ Verificação de setup
- ✅ Monitor em tempo real
- ✅ Edição de configs
- ✅ Edição de .env
- 📊 **Mais completo e profissional**

---

## 🎯 Qual Usar?

| Situação | Arquivo Recomendado |
|----------|---------------------|
| **Iniciar rápido** | `start.ps1` |
| **Atalho desktop** | `start_urion.bat` |
| **Menu simples** | `urion_launcher.bat` |
| **Gerenciamento completo** | `start_bot.ps1` |
| **Windows antigo** | `start_urion.bat` |

---

## 📝 Criar Atalho na Área de Trabalho

### Windows (.bat):
1. Clique com botão direito em `start_urion.bat`
2. Enviar para → Desktop (criar atalho)
3. Renomear para "Urion Bot"
4. Clicar duas vezes para iniciar

### PowerShell (.ps1):
1. Clique com botão direito no Desktop → Novo → Atalho
2. Localização: 
   ```
   powershell.exe -ExecutionPolicy Bypass -File "C:\Users\Administrator\Desktop\urion\start.ps1"
   ```
3. Nome: "Urion Trading Bot"
4. Clicar duas vezes para iniciar

---

## ⚙️ Configuração Automática de Política

Se aparecer erro de execução do PowerShell:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Ou execute sempre com:
```powershell
powershell -ExecutionPolicy Bypass -File start.ps1
```

---

## 🔍 O Que Cada Launcher Faz

**Todos os launchers:**
1. ✅ Verificam se o venv existe
2. ✅ Ativam o venv automaticamente
3. ✅ Verificam se Python existe
4. ✅ Iniciam o bot com `python src\main.py`
5. ✅ Mostram mensagens coloridas

**Diferenças:**
- `.ps1` = PowerShell (moderno, colorido, funcional)
- `.bat` = Batch (simples, compatível, básico)
- `*_launcher.bat` = Menu interativo
- `start_bot.ps1` = Menu completo + verificações

---

## 🚨 Solução de Problemas

### Erro: "venv não encontrado"
**Solução:**
```powershell
python -m venv venv
```

### Erro: "Python não encontrado"
**Solução:**
- Instale Python 3.10+
- Ou use o caminho completo no launcher

### Erro: "Dependências não instaladas"
**Solução:**
```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Erro: "Não pode executar scripts"
**Solução:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## 📦 Estrutura de Arquivos

```
urion/
├── venv/                    # Ambiente virtual (criado automaticamente)
├── src/
│   └── main.py             # Script principal do bot
├── start.ps1               # ⭐ Launcher rápido (RECOMENDADO)
├── start_urion.bat         # Launcher simples .bat
├── urion_launcher.bat      # Launcher com menu
├── start_bot.ps1           # Launcher completo
└── LAUNCHER_README.md      # Este arquivo
```

---

## 💡 Dicas

1. **Primeira execução**: Use `urion_launcher.bat` opção 5 para instalar dependências
2. **Uso diário**: Use `start.ps1` para iniciar rápido
3. **Verificação**: Use `urion_launcher.bat` opção 2 para ver status
4. **Logs**: Use `urion_launcher.bat` opção 3 para ver logs em tempo real
5. **Atalho**: Crie atalho de `start_urion.bat` na área de trabalho

---

## ✅ Benefícios do Venv

- ✅ Isolamento completo
- ✅ 68 pacotes (vs 170+ globais)
- ✅ Sem conflitos com outros projetos
- ✅ Fácil backup e deploy
- ✅ Reproduzível em qualquer máquina

---

**🎯 Desenvolvido por Virtus Investimentos**
