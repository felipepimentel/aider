#!/bin/bash

# Cores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Configurando integração com StackSpot AI...${NC}\n"

# Verifica se a chave API já está configurada
if [ -z "$STACKSPOT_API_KEY" ]; then
    echo -e "${RED}STACKSPOT_API_KEY não encontrada!${NC}"
    echo -e "Por favor, insira sua chave API do StackSpot:"
    read -r api_key
    
    # Adiciona a chave ao arquivo de ambiente
    echo "export STACKSPOT_API_KEY=$api_key" >> ~/.bashrc
    echo "export STACKSPOT_API_KEY=$api_key" >> ~/.zshrc
    
    # Carrega a chave no ambiente atual
    export STACKSPOT_API_KEY=$api_key
fi

# Cria diretório de configuração se não existir
config_dir="$HOME/.aider"
mkdir -p "$config_dir"

# Cria arquivo de configuração do modelo
cat > "$config_dir/stackspot.model.settings.yml" << EOL
- name: stackspot-ai-chat
  edit_format: diff
  weak_model_name: null
  use_repo_map: true
  send_undo_reply: true
  lazy: false
  reminder: user
  examples_as_sys_msg: true
  extra_params:
    max_tokens: 8192
    model_type: chat

- name: stackspot-ai-code
  edit_format: diff
  weak_model_name: null
  use_repo_map: true
  send_undo_reply: true
  lazy: false
  reminder: user
  examples_as_sys_msg: true
  extra_params:
    max_tokens: 8192
    model_type: code

- name: stackspot-ai-assistant
  edit_format: diff
  weak_model_name: null
  use_repo_map: true
  send_undo_reply: true
  lazy: false
  reminder: user
  examples_as_sys_msg: true
  extra_params:
    max_tokens: 8192
    model_type: assistant
EOL

echo -e "\n${GREEN}✓ Configuração concluída!${NC}"
echo -e "\nPara usar o StackSpot AI, execute um dos comandos:"
echo -e "  aider --model stackspot-ai-chat     # Para chat geral"
echo -e "  aider --model stackspot-ai-code     # Para tarefas de código"
echo -e "  aider --model stackspot-ai-assistant # Para assistência ao desenvolvimento"

# Torna o script executável
chmod +x "$0" 