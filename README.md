# Simulador de Gerência de Memória — Sistemas Operacionais

Simulador didático de alocação contígua de memória desenvolvido para a disciplina de **Sistemas Operacionais**. O projeto implementa os algoritmos **First Fit**, **Best Fit**, **Worst Fit** e **Next Fit**, além de coalescência de buracos adjacentes, compactação de memória (`defrag`) e análise de fragmentação externa.

A arquitetura separa o núcleo de simulação (em **Python**, sem dependências externas) das interfaces de apresentação: uma **CLI interativa** no terminal e uma **Simulação Visual passo a passo** na web (**HTML/CSS/JavaScript**).

---

## Estrutura do Repositório

```text
sim-memoria-so/
├── cli/                        # Interface de linha de comando (modo interativo, show e stats)
│   ├── __init__.py
│   └── main.py
├── core/                       # Núcleo da simulação (alocação, coalescência, defrag e snapshots)
│   ├── __init__.py
│   ├── manager.py
│   ├── models.py
│   └── runner.py
├── docs/                       # Documentação técnica e contratos de integração da equipe
│   ├── CONTRATOS.md
│   └── DECISOES_PROJETO.md
├── scripts/                    # Roteiros de teste (.cmd) para CLI e simulação visual
├── tests/                      # Testes unitários automatizados do núcleo
│   ├── __init__.py
│   └── test_core.py
├── web/                        # Interface visual passo a passo (HTML, CSS e JavaScript)
│   ├── app.js
│   ├── index.html
│   ├── sample_trace.json
│   └── styles.css
├── README.md                   # Guia geral do projeto e instruções de execução
└── server.py                   # Servidor HTTP local que integra o núcleo Python com a web
```

---

## Pré-requisitos

* **Python 3.10+** (utiliza apenas a biblioteca padrão, sem necessidade de `pip install`).
* Navegador web moderno (Chrome, Firefox, Edge) para a simulação visual.

---

## Como Executar

### 1. Rodar os Testes Automatizados do Núcleo
Na raiz do projeto, execute:
```bash
python3 -m unittest discover -s tests -v
```

### 2. Executar a Interface de Linha de Comando (CLI)

**Modo interativo:**
```bash
python3 -m cli.main
```

**Executando um roteiro `.cmd` diretamente na CLI:**
```bash
python3 -m cli.main scripts/exemplo_nextfit.cmd
```

### 3. Executar a Simulação Visual Passo a Passo

1. Inicie o servidor local na raiz do repositório:
   ```bash
   python3 server.py
   ```
2. Abra o navegador em `http://127.0.0.1:8000`.
3. Clique em **Carregar Roteiro (.cmd)** e selecione qualquer arquivo da pasta `scripts/` (ex.: `scripts/exemplo_nextfit.cmd`).
4. Utilize os controles **Avançar**, **Voltar**, **Reproduzir / Pausar** (com intervalo configurável em segundos, ex.: `0.5`) e **Reiniciar**.

---

## Comandos Suportados (CLI e Roteiros `.cmd`)

| Comando | Descrição |
| :--- | :--- |
| `init <tamanho>` | Inicializa ou reinicia a memória com `<tamanho>` bytes livres, reseta IDs para `1` e o ponteiro do Next Fit para `0`. |
| `alloc <tam> <alg>` | Aloca `<tam>` bytes usando `first`, `best`, `worst` ou `next`. IDs são sequenciais e nunca reaproveitados. |
| `freeid <id>` | Libera o bloco identificado por `<id>` e realiza coalescência com buracos vizinhos. |
| `freeaddr <end>` | Libera o bloco que inicia no endereço `<end>` e realiza coalescência com buracos vizinhos. |
| `show` | Exibe o mapa textual de duas linhas (`#/.` e IDs) e a lista de blocos ativos (ignorado na simulação visual). |
| `stats` | Exibe tamanho total, ocupado, livre, número de buracos, maior buraco livre e uso efetivo (ignorado na simulação visual). |
| `defrag <modo>` | Compacta a memória mantendo ordem relativa e IDs (`init`, `end` ou `opt`) e reseta o ponteiro do Next Fit para `0`. |

---

## Documentação Adicional

* [`docs/CONTRATOS.md`](docs/CONTRATOS.md): Especificação da API interna entre o núcleo Python e as interfaces CLI e Web.
* [`docs/DECISOES_PROJETO.md`](docs/DECISOES_PROJETO.md): Detalhamento das classes, estruturas de dados, algoritmos e decisões de arquitetura.