# Simulador de Gerência de Memória — Sistemas Operacionais

Simulador didático de alocação contígua de memória desenvolvido para a disciplina de **Sistemas Operacionais**. O projeto implementa os algoritmos **First Fit**, **Best Fit**, **Worst Fit** e **Next Fit**, além de coalescência de buracos adjacentes, compactação de memória (`defrag`) e análise de fragmentação externa.

A arquitetura separa o núcleo de simulação (em **Python**, sem dependências externas) das interfaces de apresentação: uma **CLI interativa** no terminal e uma **Simulação Visual passo a passo** na web (**HTML/CSS/JavaScript**).

---

## Estrutura do Repositório

```text
sim-memoria-so/
├── cli/                        # Interface de linha de comando (modo interativo e roteiros)
│   ├── __init__.py
│   ├── __main__.py             # Permite executar com "python -m cli"
│   └── main.py                 # Prompt, formatação de show/stats e resumo do defrag
├── core/                       # Núcleo da simulação (alocação, coalescência, defrag e snapshots)
│   ├── __init__.py
│   ├── manager.py
│   ├── models.py
│   └── runner.py
├── docs/                       # Documentação técnica e contratos de integração da equipe
│   ├── CONTRATOS.md
│   └── DECISOES_PROJETO.md
├── scripts/                    # Roteiros de teste (.cmd) e script de criação da .venv
│   ├── exemplo_defrag.cmd
│   ├── exemplo_geral.cmd
│   ├── exemplo_nextfit.cmd
│   └── setup_venv.sh
├── tests/                      # Testes unitários automatizados do núcleo e da CLI
│   ├── __init__.py
│   ├── test_cli.py
│   ├── test_core.py
│   └── test_defrag.py
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

## Ambiente Virtual (`.venv`)

Todos os comandos Python do projeto devem ser executados dentro da `.venv` criada na raiz do repositório:

```bash
python3 -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\Activate.ps1     # Windows PowerShell
```

Com a `.venv` ativada, use `python` normalmente. Se preferir não ativá-la, substitua `python` por `.venv/bin/python` nos comandos abaixo.

Para automatizar a criação e a validação do ambiente, use:

```bash
./scripts/setup_venv.sh
```

O script cria ou reutiliza a `.venv`, valida a sintaxe com `compileall` e executa a suíte de testes. O Python do host é usado apenas para criar a própria `.venv`; os comandos do projeto rodam com `.venv/bin/python`.

---

## Como Executar

### 1. Rodar os Testes Automatizados

Na raiz do projeto, com a `.venv` ativada:

```bash
python -m unittest discover -s tests -v
```

Os testes cobrem os exemplos do enunciado (Next Fit e as três opções de `defrag`), as regras de alocação/liberação e a saída da CLI.

### 2. Executar a Interface de Linha de Comando (CLI)

**Modo interativo:**

```bash
python -m cli.main
# ou, equivalentemente:
python -m cli
```

O prompt é `> `. Digite `help` para ver os comandos e `exit` (ou `quit`/`sair`) para encerrar.

**Executando um roteiro `.cmd` diretamente na CLI:**

```bash
python -m cli.main scripts/exemplo_nextfit.cmd
```

Por padrão, a CLI ecoa cada comando do roteiro (`> comando`) antes da saída. Use `--no-echo` para suprimir o eco:

```bash
python -m cli.main --no-echo scripts/exemplo_geral.cmd
```

O roteiro [`scripts/exemplo_defrag.cmd`](scripts/exemplo_defrag.cmd) reinicia a memória e compara as três opções de compactação (`init`, `end` e `opt`) a partir do mesmo estado:

```bash
python -m cli.main scripts/exemplo_defrag.cmd
```

Exemplo de sessão com compactação:

```text
> init 64
> alloc 10 first
> alloc 8 first
> alloc 6 first
> freeid 2
Liberado [id=2] @10 +8B.
> defrag end
Defrag END: 1 bloco movido, 6 bytes deslocados.
Blocos movidos:
  [id=3] @18 -> @10 (6B)

Mapa de Memória (64 bytes)
------------------------------------------------------------------
[################................................................]
[1111111111333333................................................]
------------------------------------------------------------------

Blocos ativos: [id=1] @0 +10B (usado=10B) | [id=3] @10 +6B (usado=6B)
== Estatísticas ==
Tamanho total: 64 bytes
Ocupado: 16 bytes | Livre: 48 bytes
Buracos (fragmentação externa): 1
Maior buraco livre: 48 bytes
Uso efetivo: 25.00%
```

### 3. Executar a Simulação Visual Passo a Passo

1. Inicie o servidor local na raiz do repositório, com a `.venv` ativada:
   ```bash
   python server.py
   ```
2. Abra o navegador em `http://127.0.0.1:8000`.
3. Clique em **Carregar Roteiro (.cmd)** e selecione qualquer arquivo da pasta `scripts/` (ex.: `scripts/exemplo_nextfit.cmd` ou `scripts/exemplo_defrag.cmd`).
4. Utilize os controles **Avançar**, **Voltar**, **Reproduzir / Pausar** (com intervalo configurável em segundos, ex.: `0.5`) e **Reiniciar**.

---

## Comandos Suportados (CLI e Roteiros `.cmd`)

| Comando | Descrição |
| :--- | :--- |
| `init <tamanho>` | Inicializa ou reinicia a memória com `<tamanho>` bytes livres, reseta IDs para `1` e o ponteiro do Next Fit para `0`. |
| `alloc <tam> <alg>` | Aloca `<tam>` bytes usando `first`, `best`, `worst` ou `next`. IDs são sequenciais e nunca reaproveitados. |
| `freeid <id>` | Libera o bloco identificado por `<id>` e realiza coalescência com buracos vizinhos. |
| `freeaddr <end>` | Libera o bloco que inicia no endereço `<end>` e realiza coalescência com buracos vizinhos. |
| `show` | Exibe o mapa textual de duas linhas (`#/.` e IDs), a lista de blocos ativos e as estatísticas. |
| `stats` | Exibe apenas as estatísticas (tamanho total, ocupado, livre, buracos, maior buraco e uso efetivo). |
| `defrag <modo>` | Compacta a memória mantendo ordem relativa e IDs (`init`, `end` ou `opt`), mostra blocos movidos/bytes deslocados e o mapa resultante, e reseta o ponteiro do Next Fit para `0`. |
| `help` | (Somente modo interativo) Lista os comandos disponíveis. |
| `exit` / `quit` / `sair` | (Somente modo interativo) Encerra a CLI. |

Em roteiros `.cmd`, linhas em branco e trechos iniciados por `#` são ignorados, e a linha `EOF` encerra a leitura. `show` e `stats` são executados normalmente na CLI; na simulação visual eles são ignorados, pois a tela já exibe o mapa e as estatísticas.

> **Observação sobre o mapa:** a linha de identificadores usa exatamente um caractere por byte. Por isso, IDs com mais de um dígito aparecem representados pelo último dígito (ex.: `id=12` vira `2`); a lista `Blocos ativos` sempre mostra o ID completo.

---

## Documentação Adicional

* [`docs/CONTRATOS.md`](docs/CONTRATOS.md): Especificação da API interna entre o núcleo Python e as interfaces CLI e Web.
* [`docs/DECISOES_PROJETO.md`](docs/DECISOES_PROJETO.md): Detalhamento das classes, estruturas de dados, algoritmos e decisões de arquitetura.
