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

A compactação preserva a ordem relativa e os ids dos blocos alocados. Sejam $b_0, \ldots, b_{n-1}$ os blocos alocados em ordem de endereço, $s_i$ o tamanho de $b_i$, $U = \sum_i s_i$ o total ocupado, $M$ o tamanho da memória e $H = M - U$ o espaço livre total. Após qualquer opção, a memória fica com no máximo um buraco livre (ou nenhum, se $H = 0$).

* **END:** os blocos são recolocados a partir do endereço 0, na ordem relativa, e o buraco fica no fim:
  $$new\_start(b_i) = \sum_{j<i} s_j$$
  O buraco começa em $U$ e tem $H$ bytes.
* **INIT:** os blocos são recolocados a partir do fim, na ordem relativa, e o buraco fica no início:
  $$new\_start(b_i) = M - \sum_{j \geq i} s_j$$
  O buraco começa em 0 e tem $H$ bytes.
* **OPT:** para cada corte $k$ ($0 \leq k \leq n$), os $k$ primeiros blocos ficam colados no início e os $n-k$ restantes colados no fim:
  $$new\_start(b_i) = prefix[i] \quad \text{para } i < k$$
  $$new\_start(b_i) = M - (U - prefix[i]) \quad \text{para } i \geq k$$
  onde $prefix[i] = \sum_{j<i} s_j$. O buraco único fica entre os dois grupos, em $prefix[k]$, com $H$ bytes.
  O custo de um corte é a soma dos tamanhos **apenas** dos blocos cujo `new_start` difere do endereço original. O algoritmo avalia todos os $n+1$ cortes, escolhe o de menor custo e, em empate, o maior $k$ (a varredura é crescente e a comparação usa `<=`).

Depois de qualquer opção, `next_fit_ptr` é zerado. O evento retornado preenche `moved_blocks_count` e `displaced_bytes` somente com os blocos que realmente mudaram de endereço inicial; `affected_blocks` contém `{id, old_start, new_start, size}` para cada um deles. Essa definição é importante no exemplo do enunciado: em `OPT`, o bloco `id=1` já está em `@0` e não conta como movido, embora participe do grupo inicial; os cortes `k=1` e `k=2` empatam em 6 B, e o desempate pelo maior `k` escolhe `k=2`.

A complexidade é $O(n^2)$ no número de blocos alocados (para cada um dos $n+1$ cortes, percorre-se até $n$ blocos), o que é adequado ao caráter didático do simulador.

---

## 4. Padrões de Projeto Aplicados

* **Memento / Snapshot Pattern:** Utilizado na geração de `Snapshot` imutáveis a cada comando executado. Isso permite que a interface visual navegue livremente para frente (`Avançar`) e para trás (`Voltar`) na linha do tempo sem precisar reexecutar comandos ou manter lógica inversa de alocação/coalescência.
* **Strategy (implícito via Enum `FitAlg` e seleção de política):** A política de escolha de buracos é encapsulada na etapa de seleção de `alloc`, mantendo idêntica a etapa posterior de particionamento do buraco e atualização de metadados.
* **Command / Script Runner (`core/runner.py`):** Cada linha de comando é interpretada e convertida em uma invocação padronizada ao `MemoryManager`, permitindo que o mesmo arquivo `.cmd` alimente tanto a CLI quanto a simulação visual.

---

## 5. Decisões da Interface Visual (`web/`)

A interface visual foi implementada em **HTML5, CSS3 e JavaScript puro** (sem dependências externas ou *bundlers*), consumindo exclusivamente o contrato HTTP `POST /api/simulate` fornecido por `server.py` e `core/runner.py`:

* **Renderização Proporcional da Memória:** Cada elemento da lista `snapshot.blocks` é renderizado com largura percentual exata `size / total_size * 100%`, acompanhado de uma régua dinâmica de endereços (`@start`, `@end`) e tabela complementar de segmentos para legibilidade mesmo em blocos muito estreitos.
* **Paleta de Cores Determinística por `id`:** Cada bloco alocado recebe uma cor fixa derivada de `(id - 1) % N` sobre uma paleta de alto contraste, garantindo estabilidade visual do mesmo bloco ao longo de todos os passos (inclusive após compactação `defrag`). Buracos livres usam hachura diagonal neutra.
* **Ponteiro do Next Fit e Sobreposição de Eventos:** O ponteiro `next_fit_ptr` é desenhado sobre a barra com marcador proporcional e linha vertical contínua. Uma faixa dedicada abaixo da régua exibe a ordem dos `examined_holes` (evidenciando buscas e *wrap-around*), o `chosen_hole`, coalescência de buracos adjacentes (`coalesced: true`) e deslocamentos do `defrag` (`old_start -> new_start`, `moved_blocks_count`, `displaced_bytes`).
* **Navegação e Reprodução Automática:** Como o `core/` entrega *snapshots* imutáveis para cada passo, `Avançar`, `Voltar` e `Reiniciar` (estado `Passo 0 de N`) restauram exatamente o estado da memória sem lógica inversa no frontend. A reprodução automática usa `setInterval` com intervalo configurável em segundos decimais (ex.: `0.5`), interrompe ao fim do roteiro e é pausada imediatamente em qualquer interação manual (`Avançar`, `Voltar`, `Reiniciar` ou clique na linha do tempo).
---

## 6. Interface de Linha de Comando (`cli/`)

A CLI (`cli/main.py`) é uma camada fina sobre o `core/`: os comandos que alteram a memória (`init`, `alloc`, `freeid`, `freeaddr` e `defrag`) são delegados a `core.runner.execute_command_line`; `show`, `stats`, `help` e `exit` são tratados localmente. Assim, a CLI e a simulação visual compartilham exatamente as mesmas regras de alocação, coalescência e compactação.

* **Modo interativo:** prompt `> `, com mensagens de erro em português que não interrompem a sessão. `init` pode ser repetido para reiniciar a memória, os ids e o ponteiro do Next Fit.
* **Modo roteiro:** lê um arquivo `.cmd` em UTF-8 (inclusive com BOM), ignora linhas em branco e comentários `#`, para na linha `EOF` e ecoa cada comando por padrão; a opção `--no-echo` desativa o eco. Diferentemente da simulação visual, `show` e `stats` são executados na CLI.
* **Formatação do mapa:** um caractere por byte (`#` para ocupado e `.` para livre), com separador de `total_size + 2` caracteres. A linha de identificadores também usa um caractere por byte; como não há espaço para ids com mais de um dígito, ela repete o último dígito do id (ex.: `id=12` aparece como `2`). A lista `Blocos ativos` sempre exibe o id completo, eliminando a ambiguidade.
* **Resumo do `defrag`:** informa quantos blocos mudaram de endereço e quantos bytes foram deslocados, lista cada mudança (`@antigo -> @novo`) e, em seguida, mostra o mapa e as estatísticas resultantes.
* **Validação:** erros de sintaxe/argumentos (`CommandError`) e erros de simulação (`RuntimeError` ou `event.error`) são convertidos em mensagens claras, sem traceback. Uma alocação que falha não consome id; `freeid`/`freeaddr` inválidos não alteram a memória.
