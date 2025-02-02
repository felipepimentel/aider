# Integração Aider com StackSpot AI

Este documento descreve a integração entre o Aider (assistente de programação em IA) e o StackSpot AI, permitindo que você use os modelos do StackSpot para pair programming e assistência no desenvolvimento de código.

## Visão Geral

A integração permite que você use três modelos especializados do StackSpot AI:

1. **stackspot-ai-chat**: Modelo de chat geral para conversas e planejamento
2. **stackspot-ai-code**: Modelo otimizado para tarefas de código
3. **stackspot-ai-assistant**: Modelo especializado em assistência ao desenvolvimento

## Instalação e Configuração

### Método Automático (Recomendado)

Use o script de configuração automática:

```bash
# Clone o repositório
git clone https://github.com/felipepimentel/aider.git
cd aider

# Execute o script de configuração
./scripts/setup_stackspot.sh
```

O script irá:
- Solicitar sua chave API do StackSpot
- Configurar as variáveis de ambiente necessárias
- Criar os arquivos de configuração dos modelos
- Configurar as permissões adequadas

### Configuração Manual

1. Configure a chave API:
   ```bash
   # Linux/Mac
   export STACKSPOT_API_KEY=sua-chave-aqui
   
   # Windows
   setx STACKSPOT_API_KEY sua-chave-aqui
   ```

2. Crie o arquivo de configuração `.aider.model.settings.yml`:
   ```yaml
   - name: stackspot-ai-chat
     edit_format: diff
     use_repo_map: true
     send_undo_reply: true
     examples_as_sys_msg: true
     extra_params:
       max_tokens: 8192
       model_type: chat

   - name: stackspot-ai-code
     edit_format: diff
     use_repo_map: true
     send_undo_reply: true
     examples_as_sys_msg: true
     extra_params:
       max_tokens: 8192
       model_type: code

   - name: stackspot-ai-assistant
     edit_format: diff
     use_repo_map: true
     send_undo_reply: true
     examples_as_sys_msg: true
     extra_params:
       max_tokens: 8192
       model_type: assistant
   ```

## Uso

### Comandos Básicos

```bash
# Usar o modelo de código (recomendado para programação)
aider --model stackspot-ai-code

# Usar o modelo de chat
aider --model stackspot-ai-chat

# Usar o modelo assistente
aider --model stackspot-ai-assistant

# Listar modelos disponíveis
aider --list-models stackspot
```

### Aliases Disponíveis

Para maior conveniência, você pode usar os seguintes aliases:
```bash
aider --model stackspot      # Equivalente a stackspot-ai-chat
aider --model stackspot-code # Equivalente a stackspot-ai-code
aider --model stackspot-assistant # Equivalente a stackspot-ai-assistant
```

## Características dos Modelos

### StackSpot AI Chat
- Otimizado para conversas naturais e planejamento
- Contexto: 16K tokens
- Melhor para:
  - Discussões sobre arquitetura
  - Planejamento de features
  - Explicações conceituais

### StackSpot AI Code
- Especializado em tarefas de código
- Contexto: 16K tokens
- Melhor para:
  - Geração de código
  - Refatoração
  - Debug
  - Implementação de features
  - Testes unitários

### StackSpot AI Assistant
- Focado em assistência ao desenvolvimento
- Contexto: 16K tokens
- Melhor para:
  - Gerenciamento de projeto
  - Documentação
  - Code reviews
  - Análise de dependências

## Recursos Suportados

Todos os modelos do StackSpot AI suportam:
- Edição de múltiplos arquivos
- Formato diff para edições eficientes
- Streaming de respostas
- Mapa do repositório para melhor contexto
- Integração com git para commits automáticos
- Suporte a imagens e URLs
- Comandos de voz

## Configurações Avançadas

### Personalização do Modelo

Você pode personalizar as configurações de cada modelo editando o arquivo `.aider.model.settings.yml`. Principais parâmetros:

```yaml
edit_format: Formato de edição (diff, whole)
use_repo_map: Usar mapa do repositório
max_tokens: Limite de tokens por resposta
temperature: Temperatura para geração (0.0 - 1.0)
```

### Variáveis de Ambiente

- `STACKSPOT_API_KEY`: Sua chave API do StackSpot
- `STACKSPOT_API_BASE`: URL base da API (opcional)

## Melhores Práticas

1. **Escolha do Modelo**:
   - Use `stackspot-ai-code` para tarefas de programação
   - Use `stackspot-ai-chat` para discussões e planejamento
   - Use `stackspot-ai-assistant` para documentação e gerenciamento

2. **Organização do Código**:
   - Adicione apenas os arquivos relevantes à sessão
   - Use o mapa do repositório para contexto adicional
   - Faça commits frequentes

3. **Prompts Efetivos**:
   - Seja específico nas solicitações
   - Forneça contexto suficiente
   - Use comentários AI para edições in-line

## Troubleshooting

### Problemas Comuns

1. **Erro de Autenticação**:
   ```
   STACKSPOT_API_KEY environment variable not set
   ```
   Solução: Configure a variável de ambiente com sua chave API

2. **Modelo não Encontrado**:
   ```
   Unknown model: model-name
   ```
   Solução: Verifique se está usando um dos modelos suportados

3. **Erro de Contexto**:
   ```
   Token limit exceeded
   ```
   Solução: Reduza a quantidade de arquivos ou use o formato diff

## Recursos Adicionais

- [Documentação do StackSpot AI](https://docs.stackspot.com/en/ai)
- [Documentação do Aider](https://aider.chat/docs)
- [Repositório do Projeto](https://github.com/felipepimentel/aider)

## Contribuindo

Para contribuir com melhorias na integração:

1. Fork o repositório
2. Crie uma branch para sua feature
3. Faça suas alterações
4. Envie um pull request

## Suporte

Para suporte:
- Abra uma issue no GitHub
- Consulte a documentação do StackSpot
- Entre em contato com o suporte do StackSpot 