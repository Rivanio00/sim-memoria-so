from __future__ import annotations
from typing import List, Optional
from .models import (
    Block,
    DefragOption,
    FitAlg,
    MemoryStats,
    Snapshot,
    StepEvent,
    StepResult,
)


class MemoryManager:
    def __init__(self) -> None:
        self.total_size: int = 0
        self.blocks: List[Block] = []
        self.next_id: int = 1
        self.next_fit_ptr: int = 0

    def _ensure_initialized(self) -> None:
        if self.total_size <= 0 or not self.blocks:
            raise RuntimeError("Erro: memória não inicializada. Execute 'init <tamanho>' primeiro.")

    def stats(self) -> MemoryStats:
        used = sum(b.size for b in self.blocks if not b.free)
        holes = [b for b in self.blocks if b.free]
        free = sum(h.size for h in holes)
        largest = max((h.size for h in holes), default=0)
        usage = (used / self.total_size * 100.0) if self.total_size > 0 else 0.0
        return MemoryStats(
            total_size=self.total_size,
            used_bytes=used,
            free_bytes=free,
            holes_count=len(holes),
            largest_hole=largest,
            effective_usage=round(usage, 2),
        )

    def snapshot(self) -> Snapshot:
        copied_blocks = [
            Block(id=b.id, start=b.start, size=b.size, free=b.free)
            for b in self.blocks
        ]
        return Snapshot(
            total_size=self.total_size,
            next_fit_ptr=self.next_fit_ptr,
            next_id=self.next_id,
            blocks=copied_blocks,
            stats=self.stats(),
        )

    def init(self, size: int) -> StepResult:
        if size <= 0:
            raise ValueError("Erro: tamanho da memória deve ser maior que zero.")
        self.total_size = size
        self.blocks = [Block(id=None, start=0, size=size, free=True)]
        self.next_id = 1
        self.next_fit_ptr = 0

        event = StepEvent(
            action="init",
            affected_blocks=[self.blocks[0].to_dict()],
        )
        return StepResult(command=f"init {size}", snapshot=self.snapshot(), event=event)

    def alloc(self, size: int, alg: FitAlg) -> StepResult:
        self._ensure_initialized()
        cmd = f"alloc {size} {alg.value}"

        if size <= 0:
            err = f"Erro: tamanho inválido ({size} bytes)."
            return StepResult(cmd, self.snapshot(), StepEvent(action="alloc", error=err))

        holes_with_idx = [(idx, b) for idx, b in enumerate(self.blocks) if b.free]
        examined: List[Block] = []
        chosen_idx: Optional[int] = None
        chosen_hole: Optional[Block] = None

        if alg == FitAlg.FIRST:
            for idx, hole in holes_with_idx:
                examined.append(hole)
                if hole.size >= size:
                    chosen_idx, chosen_hole = idx, hole
                    break

        elif alg == FitAlg.BEST:
            best_size = None
            for idx, hole in holes_with_idx:
                examined.append(hole)
                if hole.size >= size and (best_size is None or hole.size < best_size):
                    best_size = hole.size
                    chosen_idx, chosen_hole = idx, hole

        elif alg == FitAlg.WORST:
            worst_size = None
            for idx, hole in holes_with_idx:
                examined.append(hole)
                if hole.size >= size and (worst_size is None or hole.size > worst_size):
                    worst_size = hole.size
                    chosen_idx, chosen_hole = idx, hole

        elif alg == FitAlg.NEXT:
            if holes_with_idx:
                start_pos = next(
                    (i for i, (_, h) in enumerate(holes_with_idx) if h.end > self.next_fit_ptr),
                    0,
                )
                ordered = holes_with_idx[start_pos:] + holes_with_idx[:start_pos]
                for idx, hole in ordered:
                    examined.append(hole)
                    if hole.size >= size:
                        chosen_idx, chosen_hole = idx, hole
                        break

        if chosen_idx is None or chosen_hole is None:
            st = self.stats()
            err = (
                f"Erro: sem espaço contíguo para {size} bytes "
                f"(livre total: {st.free_bytes}, maior buraco: {st.largest_hole})"
            )
            event = StepEvent(
                action="alloc",
                examined_holes=[h.to_dict() for h in examined],
                error=err,
            )
            return StepResult(cmd, self.snapshot(), event)

        chosen_dict = chosen_hole.to_dict()
        allocated_block = Block(
            id=self.next_id,
            start=chosen_hole.start,
            size=size,
            free=False,
        )
        self.next_id += 1

        remainder_size = chosen_hole.size - size
        new_slice: List[Block] = [allocated_block]
        if remainder_size > 0:
            new_slice.append(
                Block(
                    id=None,
                    start=chosen_hole.start + size,
                    size=remainder_size,
                    free=True,
                )
            )

        self.blocks[chosen_idx : chosen_idx + 1] = new_slice

        if alg == FitAlg.NEXT:
            self.next_fit_ptr = allocated_block.end

        event = StepEvent(
            action="alloc",
            examined_holes=[h.to_dict() for h in examined],
            chosen_hole=chosen_dict,
            affected_blocks=[allocated_block.to_dict()],
        )
        return StepResult(cmd, self.snapshot(), event)

    def free_id(self, block_id: int) -> StepResult:
        self._ensure_initialized()
        cmd = f"freeid {block_id}"
        target_idx = next(
            (i for i, b in enumerate(self.blocks) if not b.free and b.id == block_id),
            None,
        )
        if target_idx is None:
            err = f"Erro: bloco com id={block_id} não encontrado."
            return StepResult(cmd, self.snapshot(), StepEvent(action="freeid", error=err))
        return self._free_at_index(target_idx, cmd, "freeid")

    def free_addr(self, addr: int) -> StepResult:
        self._ensure_initialized()
        cmd = f"freeaddr {addr}"
        target_idx = next(
            (i for i, b in enumerate(self.blocks) if not b.free and b.start == addr),
            None,
        )
        if target_idx is None:
            err = f"Erro: nenhum bloco alocado inicia no endereço {addr}."
            return StepResult(cmd, self.snapshot(), StepEvent(action="freeaddr", error=err))
        return self._free_at_index(target_idx, cmd, "freeaddr")

    def _free_at_index(self, idx: int, cmd: str, action: str) -> StepResult:
        target = self.blocks[idx]
        freed_info = target.to_dict()
        target.id = None
        target.free = True

        # Coalescência com vizinhos livres
        start_merge = idx
        end_merge = idx
        if start_merge > 0 and self.blocks[start_merge - 1].free:
            start_merge -= 1
        if end_merge + 1 < len(self.blocks) and self.blocks[end_merge + 1].free:
            end_merge += 1

        merged_start = self.blocks[start_merge].start
        merged_size = sum(self.blocks[i].size for i in range(start_merge, end_merge + 1))
        coalesced_block = Block(id=None, start=merged_start, size=merged_size, free=True)
        self.blocks[start_merge : end_merge + 1] = [coalesced_block]

        affected = [freed_info]
        if end_merge > start_merge:
            affected.append({**coalesced_block.to_dict(), "coalesced": True})

        event = StepEvent(action=action, affected_blocks=affected)
        return StepResult(cmd, self.snapshot(), event)

    def defrag(self, option: DefragOption) -> StepResult:
        """
        Compacta a memória mantendo a ordem relativa e os ids dos blocos.

        INIT: blocos alocados colados no fim, buraco no início.
        END:  blocos alocados colados no início, buraco no fim.
        OPT:  escolhe o corte k que minimiza os bytes deslocados, deixando os
              k primeiros blocos no início e os demais no fim. Em empate,
              vence o maior k.

        O ponteiro do Next Fit volta para 0 em qualquer opção. Um bloco só é
        contabilizado como movido quando seu endereço inicial realmente muda.
        """
        self._ensure_initialized()
        if not isinstance(option, DefragOption):
            try:
                option = DefragOption(option)
            except ValueError as exc:
                raise ValueError(
                    f"Opção de defrag inválida: '{option}'. Use init, end ou opt."
                ) from exc

        allocated = [b for b in self.blocks if not b.free]
        old_starts = {b.id: b.start for b in allocated}

        if option is DefragOption.INIT:
            new_blocks = self._layout_init(allocated, self.total_size)
        elif option is DefragOption.END:
            new_blocks = self._layout_end(allocated, self.total_size)
        else:
            new_blocks = self._layout_opt(allocated, self.total_size)

        self.blocks = new_blocks
        self.next_fit_ptr = 0

        moved = []
        for block in new_blocks:
            if block.free:
                continue
            old_start = old_starts[block.id]
            if old_start != block.start:
                moved.append({
                    "id": block.id,
                    "old_start": old_start,
                    "new_start": block.start,
                    "size": block.size,
                })

        event = StepEvent(
            action="defrag",
            affected_blocks=moved,
            moved_blocks_count=len(moved),
            displaced_bytes=sum(item["size"] for item in moved),
        )
        return StepResult(
            command=f"defrag {option.value}",
            snapshot=self.snapshot(),
            event=event,
        )

    @staticmethod
    def _layout_end(allocated: List[Block], total: int) -> List[Block]:
        """Blocos colados no início e um único buraco no fim."""
        blocks: List[Block] = []
        cursor = 0
        for block in allocated:
            blocks.append(Block(id=block.id, start=cursor, size=block.size, free=False))
            cursor += block.size
        if cursor < total:
            blocks.append(Block(id=None, start=cursor, size=total - cursor, free=True))
        return blocks

    @staticmethod
    def _layout_init(allocated: List[Block], total: int) -> List[Block]:
        """Blocos colados no fim e um único buraco no início."""
        placed: List[Block] = []
        cursor = total
        for block in reversed(allocated):
            cursor -= block.size
            placed.append(Block(id=block.id, start=cursor, size=block.size, free=False))
        placed.reverse()

        blocks: List[Block] = []
        if cursor > 0:
            blocks.append(Block(id=None, start=0, size=cursor, free=True))
        blocks.extend(placed)
        return blocks

    @staticmethod
    def _layout_opt(allocated: List[Block], total: int) -> List[Block]:
        """
        Para cada corte k, calcula os bytes deslocados supondo:
          * blocos 0..k-1 colados no início: start = prefix[i];
          * blocos k..n-1 colados no fim: start = total - (used - prefix[i]).

        O buraco único fica entre os dois grupos. Escolhe o menor custo e,
        em caso de empate, o maior k (a iteração é crescente e usa <=).
        """
        n = len(allocated)
        prefix = [0] * (n + 1)
        for i, block in enumerate(allocated):
            prefix[i + 1] = prefix[i] + block.size
        used = prefix[n]
        hole_size = total - used

        best_k = 0
        best_cost: Optional[int] = None
        for k in range(n + 1):
            cost = 0
            for i in range(k):
                if prefix[i] != allocated[i].start:
                    cost += allocated[i].size
            for i in range(k, n):
                new_start = total - (used - prefix[i])
                if new_start != allocated[i].start:
                    cost += allocated[i].size
            if best_cost is None or cost <= best_cost:
                best_cost = cost
                best_k = k

        blocks: List[Block] = []
        for i in range(best_k):
            blocks.append(
                Block(id=allocated[i].id, start=prefix[i], size=allocated[i].size, free=False)
            )
        if hole_size > 0:
            blocks.append(Block(id=None, start=prefix[best_k], size=hole_size, free=True))
        for i in range(best_k, n):
            new_start = total - (used - prefix[i])
            blocks.append(
                Block(id=allocated[i].id, start=new_start, size=allocated[i].size, free=False)
            )
        return blocks
