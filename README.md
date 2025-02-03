# StackSpot AI Integration

Este projeto é uma integração simplificada do StackSpot AI com o LiteLLM, permitindo usar os modelos do StackSpot de forma fácil e eficiente.

## Modelos Disponíveis

- **stackspot-ai-chat**: Modelo para chat geral
- **stackspot-ai-code**: Modelo otimizado para código
- **stackspot-ai-assistant**: Modelo para assistência ao desenvolvimento

## Instalação

```bash
# Instalar dependências
pip install -r requirements.txt

# Configurar API key
export STACKSPOT_API_KEY=<sua-chave-api>  # Linux/Mac
setx STACKSPOT_API_KEY <sua-chave-api>    # Windows
```

## Uso

```python
from aider.providers.stackspot.config import StackSpotProvider

# Inicializar provider
provider = StackSpotProvider()
provider.configure()

# Fazer uma requisição
response = provider.completion(
    model="stackspot-ai-code",
    messages=[{"role": "user", "content": "Crie uma função que soma dois números"}],
    temperature=0.7
)

print(response.choices[0].message.content)
```

## Configuração

O arquivo `.litellm.config.yaml` contém as configurações dos modelos. Você pode ajustar parâmetros como:

- `max_tokens`
- `temperature`
- `api_base`
- Outros parâmetros específicos do modelo

## Testes

```bash
# Instalar dependências de teste
pip install -r requirements/test.txt

# Executar testes
pytest tests/
```

## Contribuindo

1. Fork o projeto
2. Crie sua feature branch (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -am 'Adiciona nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Crie um Pull Request
