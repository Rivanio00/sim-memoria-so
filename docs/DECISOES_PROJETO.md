# Documento de Decisões de Implementação

## 1. Arquitetura Geral

O sistema foi dividido em três camadas desacopladas para facilitar o desenvolvimento paralelo, os testes unitários e a reutilização da lógica de negócio:

1. **Núcleo de Simulação (`core/`):** Implementado em Python puro (biblioteca padrão), concentra toda a representação da memória física, os algoritmos de alocação, a coalescência de buracos, o cálculo de métricas e a compactação (`defrag`).
2. **Interface de Linha de Comando (`cli/`):** Camada de interação textual que interpreta comandos do usuário ou arquivos de roteiro `.cmd`, delega a execução ao `core/` e formata o mapa ASCII (`show`) e as estatísticas (`stats`).
3. **Simulação Visual Web (`web/` + `server.py`):** Um servidor HTTP nativo em Python (`http.server`) serve os arquivos estáticos da interface web e expõe a rota `POST /api/simulate`, que processa um roteiro `.cmd` e retorna uma linha do tempo completa de *snapshots* em JSON para renderização interativa em JavaScript.

---

## 2. Estruturas de Dados e Classes Principais

### 2.1 Estrutura de Controle de Bloco (`Block`)
Em vez de representar a memória como um vetor de bytes individuais (o que tornaria buscas e coalescências $O(N)$ no tamanho da memória), adotou-se uma **lista ordenada de descritores de blocos contíguos** (`List[Block]`), onde cada elemento mapeia uma partição variável da memória:

* `id: Optional[int]` — Identificador único sequencial (iniciado em `1`) quando o bloco está alocado; `None` quando representa um buraco livre.
* `start: int` — Endereço inicial (offset em bytes) do bloco na memória física simulada.
* `size: int` — Tamanho do bloco em bytes.
* `free: bool` — Indicador de estado (`True` para buraco livre, `False` para bloco ocupado).
* `end` *(propriedade derivada)* — Retorna `start + size`, delimitando o endereço exclusivo de término do bloco.

Como o simulador não utiliza alinhamento nem paginação, não há fragmentação interna: todo o espaço de um bloco alocado corresponde ao espaço efetivamente utilizado.

### 2.2 Gerenciador de Memória (`MemoryManager`)
Classe central responsável por manter o estado da simulação:
* `total_size: int` — Capacidade total configurada pelo comando `init`.
* `blocks: List[Block]` — Lista ordenada por `start` cobrindo toda a extensão $[0, \text{total\_size})$.
* `next_id: int` — Contador monotônico crescente de identificadores (nunca decrementado ou reutilizado).
* `next_fit_ptr: int` — Ponteiro de busca circular utilizado exclusivamente pelo algoritmo Next Fit.

### 2.3 Modelos de Histórico e Eventos (`Snapshot`, `StepEvent`, `StepResult`)
Para atender aos requisitos da simulação visual passo a passo (como desfazer passos exatamente e destacar buracos examinados), cada operação gera um `StepResult` composto por:
* `Snapshot`: Cópia profunda (*deep copy* explícita) da lista de blocos, do `next_fit_ptr`, do `next_id` e das estatísticas (`MemoryStats`) após o comando.
* `StepEvent`: Registro semântico da operação contendo `examined_holes`, `chosen_hole`, `affected_blocks`, métricas de deslocamento do `defrag` e eventual mensagem de erro.

---

## 3. Decisões sobre os Algoritmos

### 3.1 Algoritmos de Alocação (`First`, `Best`, `Worst`, `Next Fit`)
* **First Fit:** Percorre `blocks` em ordem crescente de endereço e seleciona o primeiro bloco com `free == True` e `size >= pedido`, interrompendo a varredura imediatamente.
* **Best Fit e Worst Fit:** Varrem todos os buracos livres disponíveis para encontrar, respectivamente, o menor buraco que comporta o pedido (`size >= pedido`) e o maior buraco disponível. O uso de comparação estrita (`<` para Best Fit e `>` para Worst Fit) garante naturalmente o desempate pelo **menor endereço inicial**, já que a lista está ordenada por `start`.
* **Next Fit:** Localiza o índice do primeiro buraco livre cuja extremidade final seja estritamente maior que o ponteiro (`hole.end > next_fit_ptr`). A lista de buracos candidatos é rotacionada a partir desse índice (`holes[pos:] + holes[:pos]`), implementando a busca circular (*wrap-around*) até o fim da memória e retornando ao endereço `0`. Ao alocar, o ponteiro é atualizado para o fim do novo bloco (`allocated_block.end`).

### 3.2 Liberação e Coalescência (`free_id` / `free_addr`)
Ao liberar um bloco no índice $i$, seu estado muda para `free = True` (`id = None`). Em seguida, verifica-se apenas os vizinhos imediatos $i - 1$ e $i + 1$: caso algum esteja livre, os blocos adjacentes são fundidos em um único `Block` livre cuja soma de tamanhos preserva a contiguidade da memória.

### 3.3 Compactação de Memória (`defrag`)
*(A ser detalhado pelo responsável pela implementação de `INIT`, `END` e `OPT`, descrevendo a escolha do ponto de corte $k$ que minimiza $\sum \text{size}$ dos blocos deslocados).*

---

## 4. Padrões de Projeto Aplicados

* **Memento / Snapshot Pattern:** Utilizado na geração de `Snapshot` imutáveis a cada comando executado. Isso permite que a interface visual navegue livremente para frente (`Avançar`) e para trás (`Voltar`) na linha do tempo sem precisar reexecutar comandos ou manter lógica inversa de alocação/coalescência.
* **Strategy (implícito via Enum `FitAlg` e seleção de política):** A política de escolha de buracos é encapsulada na etapa de seleção de `alloc`, mantendo idêntica a etapa posterior de particionamento do buraco e atualização de metadados.
* **Command / Script Runner (`core/runner.py`):** Cada linha de comando é interpretada e convertida em uma invocação padronizada ao `MemoryManager`, permitindo que o mesmo arquivo `.cmd` alimente tanto a CLI quanto a simulação visual.

---

## 5. Decisões da Interface Visual (`web/`)
*(A ser preenchido pelo responsável pelo frontend Web: estratégia de renderização proporcional do mapa de memória, paleta de cores determinística por `id`, exibição da régua de endereços e controle de temporização da reprodução automática).*