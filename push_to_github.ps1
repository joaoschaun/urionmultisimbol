# Script para fazer push para GitHub
# Execute este script após criar o repositório no GitHub

param(
    [Parameter(Mandatory=$true)]
    [string]$RepoUrl
)

Write-Host "🔧 Configurando repositório remoto..." -ForegroundColor Cyan
git remote remove origin 2>$null
git remote add origin $RepoUrl

Write-Host "✅ Remote configurado: $RepoUrl" -ForegroundColor Green

Write-Host "`n📤 Enviando código para GitHub..." -ForegroundColor Cyan
git push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ Código enviado com sucesso para o GitHub!" -ForegroundColor Green
    Write-Host "🌐 Repositório: $RepoUrl" -ForegroundColor Cyan
} else {
    Write-Host "`n❌ Erro ao enviar código. Verifique suas credenciais." -ForegroundColor Red
    Write-Host "💡 Dica: Você pode precisar autenticar com token do GitHub" -ForegroundColor Yellow
}
