# 🌐 Guia de Deploy - Virtus Investimentos

## Configuração do Frontend na KingHost

### 📋 Informações
- **Domínio**: www.virtusinvestimentos.com.br
- **Provedor**: KingHost
- **IP do Backend**: 66.36.233.196:8080

---

## 📁 Arquivos para Upload

Os arquivos do frontend estão em:
```
c:\Users\Administrator\Desktop\urion\frontend\dist\
├── index.html
└── assets/
    ├── index-BEsZ1cyu.js
    └── index-BHkpBfAd.css
```

---

## 🚀 Passo a Passo

### PASSO 1: Acesse o Painel KingHost
1. Acesse https://painel.kinghost.com.br
2. Faça login com suas credenciais

### PASSO 2: Acesse o Gerenciador de Arquivos
1. No painel, clique em **"Gerenciador de Arquivos"** ou **"FTP"**
2. Navegue até a pasta `public_html` ou `www`

### PASSO 3: Faça Upload dos Arquivos
1. Delete os arquivos existentes (se houver)
2. Faça upload de:
   - `index.html` → direto na raiz (`public_html/`)
   - Pasta `assets/` → crie a pasta e faça upload dos arquivos dentro

### PASSO 4: Verifique a Estrutura Final
Sua pasta `public_html` deve ficar assim:
```
public_html/
├── index.html
└── assets/
    ├── index-BEsZ1cyu.js
    └── index-BHkpBfAd.css
```

### PASSO 5: Configure o Redirecionamento (Opcional)
Se quiser que todas as rotas funcionem (SPA), crie um arquivo `.htaccess`:

```apache
<IfModule mod_rewrite.c>
  RewriteEngine On
  RewriteBase /
  RewriteRule ^index\.html$ - [L]
  RewriteCond %{REQUEST_FILENAME} !-f
  RewriteCond %{REQUEST_FILENAME} !-d
  RewriteRule . /index.html [L]
</IfModule>
```

---

## 🖥️ Configuração do Backend (Seu Servidor Windows)

### 1. Iniciar o Backend
Execute no PowerShell:
```powershell
cd c:\Users\Administrator\Desktop\urion
.\venv\Scripts\Activate.ps1
python backend/server.py
```

### 2. Verificar Firewall
A porta 8080 já foi liberada automaticamente.

### 3. Testar Conexão
Acesse no navegador:
- http://66.36.233.196:8080 → Deve retornar JSON
- http://66.36.233.196:8080/docs → Documentação Swagger

---

## ⚠️ Importante: HTTPS

Para produção, recomenda-se usar HTTPS:

### Opção A: Cloudflare (Grátis e Recomendado)
1. Crie conta em https://cloudflare.com
2. Adicione seu domínio
3. Configure DNS para apontar:
   - `virtusinvestimentos.com.br` → Proxy ativo
4. Cloudflare fornece SSL/HTTPS grátis

### Opção B: SSL no Backend
Use certificado Let's Encrypt no seu servidor Windows.

---

## 🔗 URLs Finais

Após configuração:

| Serviço | URL |
|---------|-----|
| **Frontend** | https://virtusinvestimentos.com.br |
| **API REST** | http://66.36.233.196:8080/api |
| **WebSocket** | ws://66.36.233.196:8080/ws |
| **API Docs** | http://66.36.233.196:8080/docs |

---

## 🧪 Teste Rápido

1. Inicie o backend:
```powershell
cd c:\Users\Administrator\Desktop\urion
.\venv\Scripts\Activate.ps1
python backend/server.py
```

2. Acesse o frontend:
- Local: http://localhost:5173 (npm run dev)
- Produção: https://virtusinvestimentos.com.br

---

## 📞 Suporte KingHost

Se precisar de ajuda com FTP/Upload:
- Chat: https://king.host/wiki/
- WhatsApp: 51 4003-5464

---

*Gerado em: 01/12/2025*
*Bot Urion v2.0.0*
