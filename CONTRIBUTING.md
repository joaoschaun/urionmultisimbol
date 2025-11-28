# Contributing to Urion Multi-Symbol Trading Bot

Obrigado por considerar contribuir para o Urion! 🎉

## Como Contribuir

### 🐛 Reportando Bugs

1. Verifique se o bug já não foi reportado nas [Issues](https://github.com/joaoschaun/urionmultisimbol/issues)
2. Se não existir, crie uma nova issue com:
   - **Título claro** e descritivo
   - **Descrição detalhada** do problema
   - **Passos para reproduzir**
   - **Comportamento esperado** vs **comportamento atual**
   - **Screenshots** se aplicável
   - **Ambiente** (OS, Python version, MT5 version)

### ✨ Sugerindo Features

1. Crie uma issue com tag `enhancement`
2. Descreva claramente:
   - O problema que a feature resolve
   - Como você imagina que funcione
   - Por que seria útil para outros usuários

### 🔧 Pull Requests

1. **Fork** o repositório
2. **Clone** seu fork localmente
3. **Crie uma branch** para sua feature:
   ```bash
   git checkout -b feature/nome-da-feature
   ```
4. **Faça suas alterações** seguindo os padrões do projeto
5. **Teste** suas alterações
6. **Commit** com mensagens claras:
   ```bash
   git commit -m "feat: adiciona suporte para BTC"
   ```
7. **Push** para seu fork:
   ```bash
   git push origin feature/nome-da-feature
   ```
8. Abra um **Pull Request**

### 📝 Padrões de Código

#### Python Style Guide

- Siga [PEP 8](https://pep8.org/)
- Use type hints quando possível
- Docstrings para classes e funções públicas
- Máximo de 100 caracteres por linha

#### Commits Semânticos

Use prefixos:
- `feat:` - Nova funcionalidade
- `fix:` - Correção de bug
- `docs:` - Apenas documentação
- `style:` - Formatação (sem mudança de código)
- `refactor:` - Refatoração de código
- `test:` - Adiciona/modifica testes
- `chore:` - Manutenção

Exemplos:
```
feat: adiciona estratégia de arbitragem
fix: corrige cálculo de stop loss no scalping
docs: atualiza README com exemplos
```

### 🧪 Testes

- Adicione testes para novas features
- Garanta que testes existentes passem
- Execute antes de commitar:
  ```bash
  pytest tests/
  ```

### 📚 Documentação

- Atualize README.md se necessário
- Adicione docstrings para código novo
- Atualize CHANGELOG.md

### 🔍 Code Review

Seu PR será revisado considerando:
- ✅ Qualidade do código
- ✅ Testes adequados
- ✅ Documentação clara
- ✅ Sem quebra de funcionalidades existentes
- ✅ Performance

### 💡 Áreas que Precisam de Ajuda

- [ ] Testes unitários
- [ ] Documentação de estratégias
- [ ] Tradução para outros idiomas
- [ ] Otimização de performance
- [ ] Interface web
- [ ] Backtesting

### 📞 Dúvidas?

- Abra uma issue com tag `question`
- Participe das [Discussions](https://github.com/joaoschaun/urionmultisimbol/discussions)

## Código de Conduta

- Seja respeitoso e profissional
- Aceite feedback construtivo
- Foque no melhor para o projeto

---

**Obrigado por contribuir! 🚀**
