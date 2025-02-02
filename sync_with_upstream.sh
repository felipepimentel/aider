#!/bin/bash

# Cores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Sincronizando fork com o repositório principal do Aider...${NC}\n"

# Verifica se o remote upstream existe
if ! git remote | grep -q "upstream"; then
    echo -e "${RED}Remote 'upstream' não encontrado!${NC}"
    echo -e "Adicionando remote 'upstream'..."
    git remote add upstream https://github.com/Aider-AI/aider.git
fi

# Salva o branch atual
current_branch=$(git symbolic-ref --short HEAD)

echo -e "${GREEN}1. Buscando alterações do upstream...${NC}"
git fetch upstream

echo -e "\n${GREEN}2. Verificando se existem commits locais não enviados...${NC}"
if ! git diff --quiet @{u}; then
    echo -e "${YELLOW}ATENÇÃO: Existem commits locais que não foram enviados para o remote.${NC}"
    echo -e "Por favor, faça commit das suas alterações ou stash antes de sincronizar."
    exit 1
fi

echo -e "\n${GREEN}3. Realizando rebase com o branch principal do upstream...${NC}"
git rebase upstream/main

if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}4. Enviando alterações para seu fork (origin)...${NC}"
    git push origin $current_branch
    echo -e "\n${GREEN}✓ Sincronização concluída com sucesso!${NC}"
else
    echo -e "\n${RED}Erro durante o rebase!${NC}"
    echo -e "Por favor, resolva os conflitos manualmente e depois execute:"
    echo -e "git rebase --continue"
    echo -e "git push origin $current_branch"
fi 