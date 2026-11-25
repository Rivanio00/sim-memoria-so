#!/usr/bin/env bash
#
# Cria (ou reutiliza) a .venv do projeto e valida o ambiente.
#
# Uso:
#   ./scripts/setup_venv.sh
#   PYTHON=/usr/bin/python3.12 ./scripts/setup_venv.sh
#
# O Python do host é usado apenas para criar a própria .venv. A validação e os
# testes são executados com .venv/bin/python.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON="${PYTHON:-python3}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "Erro: '$PYTHON' não encontrado. Defina PYTHON=/caminho/do/python." >&2
    exit 1
fi

if [ ! -d ".venv" ]; then
    echo "Criando .venv com $PYTHON..."
    "$PYTHON" -m venv .venv
else
    echo ".venv já existe; reutilizando."
fi

VENV_PYTHON=".venv/bin/python"
if [ ! -x "$VENV_PYTHON" ]; then
    echo "Erro: $VENV_PYTHON não encontrado ou sem permissão de execução." >&2
    exit 1
fi

echo "Python da .venv: $("$VENV_PYTHON" --version)"
echo "Validando a sintaxe do código..."
"$VENV_PYTHON" -m compileall -q cli core tests server.py

echo "Executando os testes..."
"$VENV_PYTHON" -m unittest discover -s tests -v

echo
echo "Ambiente pronto."
echo "Ative com:      source .venv/bin/activate"
echo "Ou execute com: .venv/bin/python -m cli.main"
