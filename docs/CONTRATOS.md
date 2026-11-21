# Contratos de Integração (Core Python e Interfaces CLI / Web)

Este documento define as interfaces oficiais do projeto. O módulo `core/` atua como **única fonte da verdade** para todas as regras de gerência de memória: nem a CLI (`cli/`) nem a interface visual (`web/`) devem reimplementar lógica de busca, coalescência ou compactação.

---

## 1. Regras de Domínio Garantidas pelo `core/`

1. **Invariante da Lista de Blocos:** `MemoryManager.blocks` é uma lista contígua e ordenada por endereço inicial (`start`), cobrindo exatamente o intervalo $[0, \text{total\_size})$ sem lacunas ou sobreposições.
2. **Coalescência Imediata:** Dois blocos livres (`free=True`) adjacentes nunca coexistem na lista. Toda operação `free_id` ou `free_addr` funde imediatamente buracos vizinhos à esquerda e/ou à direita.
3. **Alocação e Sobras:** O bloco alocado ocupa sempre o início do buraco escolhido (`chosen_hole.start`). Se houver sobra (`hole.size > requested_size`), cria-se um novo bloco livre imediatamente após o bloco alocado.
4. **Identificadores (`id`):** Sequenciais a partir de `1`, nunca reutilizados. Falhas de alocação não incrementam `next_id`. Apenas `init` reinicia `next_id = 1`.
5. **Ponteiro do Next Fit (`next_fit_ptr`):**
   * Inicia em `0` após `init` ou `defrag`.
   * Em `alloc ... next`, a busca inicia no primeiro buraco com `hole.end > next_fit_ptr` (examinando o buraco inteiro, mesmo que `hole.start < next_fit_ptr`), percorre até o fim da memória e faz *wrap-around* para o endereço `0`.
   * Atualiza para `allocated_block.end` somente quando `alloc` com `next` é bem-sucedido.
   * Liberações (`freeid`, `freeaddr`), alocações com outros algoritmos ou alocações que falham **não** alteram `next_fit_ptr`.
6. **Critério de Desempate:** Em `first`, `best`, `worst` e `next`, empates são resolvidos pelo buraco de **menor endereço inicial**.
7. **Mensagem de Erro de Alocação:**
   ```text
   Erro: sem espaço contíguo para <N> bytes (livre total: X, maior buraco: Y)
   ```

---

## 2. Contrato da API Python (`core/manager.py`)

Todos os métodos mutadores de `MemoryManager` retornam um objeto `StepResult`:

* `init(size: int) -> StepResult`
* `alloc(size: int, alg: FitAlg) -> StepResult`
* `free_id(block_id: int) -> StepResult`
* `free_addr(addr: int) -> StepResult`
* `defrag(option: DefragOption) -> StepResult`
* `stats() -> MemoryStats`
* `snapshot() -> Snapshot`

### Requisitos do `defrag(option: DefragOption)` 
Ao concluir `defrag`, o método deve retornar um `StepResult` com:
* `snapshot`: memória compactada e `next_fit_ptr = 0`.
* `event.action`: `"defrag"`.
* `event.moved_blocks_count`: quantidade de blocos alocados cujo `start` foi alterado.
* `event.displaced_bytes`: soma dos tamanhos (`size`) apenas dos blocos que mudaram de endereço inicial.
* `event.affected_blocks`: lista de dicionários descrevendo cada bloco movido no formato:
  ```python
  {"id": block.id, "old_start": antigo_end, "new_start": novo_end, "size": block.size}
  ```

---

## 3. Contrato HTTP / JSON (`server.py` e `web/app.js`)

### Endpoint de Simulação
* **Rota:** `POST /api/simulate`
* **Request Body (`application/json`):**
  ```json
  {
    "script": "init 32\nalloc 8 next\n..."
  }
  ```
* **Regras de Parsing (`core/runner.py`):**
  * Linhas em branco e linhas iniciadas por `#` são ignoradas.
  * Comandos `show` e `stats` são ignorados (não geram passos na timeline visual).
  * Cada comando restante válido gera um item em `steps`.

### Response Body (`200 OK` — `application/json`)

```json
{
  "steps": [
    {
      "step_index": 1,
      "total_steps": 7,
      "command": "init 32",
      "snapshot": {
        "total_size": 32,
        "next_fit_ptr": 0,
        "next_id": 1,
        "blocks": [
          {
            "id": null,
            "start": 0,
            "size": 32,
            "end": 32,
            "free": true
          }
        ],
        "stats": {
          "total_size": 32,
          "used_bytes": 0,
          "free_bytes": 32,
          "holes_count": 1,
          "largest_hole": 32,
          "effective_usage": 0.0
        }
      },
      "event": {
        "action": "init",
        "examined_holes": [],
        "chosen_hole": null,
        "affected_blocks": [
          { "id": null, "start": 0, "size": 32, "end": 32, "free": true }
        ],
        "moved_blocks_count": 0,
        "displaced_bytes": 0,
        "error": null
      }
    }
  ]
}
```

### Como o Frontend (`web/app.js`) deve consumir cada campo:
* **Estado Anterior ao Passo 1 (Botão Reiniciar):** Antes de executar `step_index: 1`, a interface pode exibir o estado "Passo 0 de N (Aguardando início)" e, ao clicar em **Reiniciar**, retornar exatamente a esse ponto inicial.
* **Botão Voltar:** Basta decrementar o índice atual (`currentIndex - 1`) e renderizar `steps[currentIndex].snapshot`. Como cada passo carrega uma cópia completa da memória, `next_id` e `next_fit_ptr`, a restauração de estado é exata.
* **Destaque de Busca (`alloc`):**
  * `event.examined_holes`: lista ordenada dos buracos avaliados durante a busca (permite destacar visualmente o percurso do First, Best, Worst e o *wrap-around* do Next Fit).
  * `event.chosen_hole`: buraco selecionado para receber o bloco (`null` se houve falha).
* **Destaque de Mudanças:** `event.affected_blocks` indica o bloco recém-alocado, o bloco liberado/fundido (flag `"coalesced": true`) ou os blocos deslocados pelo `defrag`.
* **Erros:** Quando `event.error` não for `null`, exibir a mensagem em destaque na tela sem interromper a navegação pelos passos.