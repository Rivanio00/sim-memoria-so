import unittest

from core.manager import MemoryManager
from core.models import DefragOption, FitAlg


def active_blocks(mm: MemoryManager):
    return [(b.id, b.start, b.size) for b in mm.blocks if not b.free]


def free_blocks(mm: MemoryManager):
    return [(b.start, b.size) for b in mm.blocks if b.free]


class TestDefragPDFExamples(unittest.TestCase):
    """Casos extraídos da tabela de defrag do enunciado (memória de 64 B)."""

    def build_pdf_state(self) -> MemoryManager:
        mm = MemoryManager()
        mm.init(64)
        mm.alloc(10, FitAlg.FIRST)
        mm.alloc(8, FitAlg.FIRST)
        mm.alloc(6, FitAlg.FIRST)
        mm.free_id(2)
        # Estado: id=1 @0 +10B, buraco @10 +54B, id=3 @18 +6B
        return mm

    def test_defrag_init_moves_blocks_to_end(self):
        mm = self.build_pdf_state()
        result = mm.defrag(DefragOption.INIT)

        self.assertEqual(active_blocks(mm), [(1, 48, 10), (3, 58, 6)])
        self.assertEqual(free_blocks(mm), [(0, 48)])
        self.assertEqual(result.event.action, "defrag")
        self.assertEqual(result.event.moved_blocks_count, 2)
        self.assertEqual(result.event.displaced_bytes, 16)
        self.assertEqual(result.event.affected_blocks, [
            {"id": 1, "old_start": 0, "new_start": 48, "size": 10},
            {"id": 3, "old_start": 18, "new_start": 58, "size": 6},
        ])
        self.assertEqual(mm.next_fit_ptr, 0)

    def test_defrag_end_moves_blocks_to_start(self):
        mm = self.build_pdf_state()
        result = mm.defrag(DefragOption.END)

        self.assertEqual(active_blocks(mm), [(1, 0, 10), (3, 10, 6)])
        self.assertEqual(free_blocks(mm), [(16, 48)])
        self.assertEqual(result.event.moved_blocks_count, 1)
        self.assertEqual(result.event.displaced_bytes, 6)
        self.assertEqual(result.event.affected_blocks, [
            {"id": 3, "old_start": 18, "new_start": 10, "size": 6},
        ])
        self.assertEqual(mm.next_fit_ptr, 0)

    def test_defrag_opt_matches_pdf_example(self):
        mm = self.build_pdf_state()
        result = mm.defrag(DefragOption.OPT)

        self.assertEqual(active_blocks(mm), [(1, 0, 10), (3, 10, 6)])
        self.assertEqual(free_blocks(mm), [(16, 48)])
        self.assertEqual(result.event.moved_blocks_count, 1)
        self.assertEqual(result.event.displaced_bytes, 6)
        self.assertEqual(result.event.affected_blocks, [
            {"id": 3, "old_start": 18, "new_start": 10, "size": 6},
        ])
        self.assertEqual(mm.next_fit_ptr, 0)


class TestDefragOPT(unittest.TestCase):
    def test_opt_tie_prefers_larger_k(self):
        mm = MemoryManager()
        mm.init(32)
        mm.alloc(4, FitAlg.FIRST)   # id=1 @0
        mm.alloc(4, FitAlg.FIRST)   # id=2 @4
        mm.alloc(4, FitAlg.FIRST)   # id=3 @8
        mm.free_id(2)               # buraco @4 +4B

        result = mm.defrag(DefragOption.OPT)

        # k=1 (id=1 no início, id=3 no fim) e k=2 (id=1 e id=3 no início)
        # custam 4B; o desempate pelo maior k escolhe k=2.
        self.assertEqual(active_blocks(mm), [(1, 0, 4), (3, 4, 4)])
        self.assertEqual(free_blocks(mm), [(8, 24)])
        self.assertEqual(result.event.moved_blocks_count, 1)
        self.assertEqual(result.event.displaced_bytes, 4)

    def test_opt_can_leave_blocks_untouched(self):
        mm = MemoryManager()
        mm.init(32)
        mm.alloc(4, FitAlg.FIRST)   # id=1 @0
        mm.alloc(24, FitAlg.FIRST)  # id=2 @4
        mm.alloc(4, FitAlg.FIRST)   # id=3 @28
        mm.free_id(2)               # buraco @4 +24B

        result = mm.defrag(DefragOption.OPT)

        # k=1 mantém id=1 @0 e id=3 @28: nenhum bloco precisa se mover.
        self.assertEqual(active_blocks(mm), [(1, 0, 4), (3, 28, 4)])
        self.assertEqual(free_blocks(mm), [(4, 24)])
        self.assertEqual(result.event.moved_blocks_count, 0)
        self.assertEqual(result.event.displaced_bytes, 0)


class TestDefragEdgeCases(unittest.TestCase):
    def test_defrag_empty_memory(self):
        mm = MemoryManager()
        mm.init(16)
        result = mm.defrag(DefragOption.OPT)

        self.assertEqual(free_blocks(mm), [(0, 16)])
        self.assertEqual(result.event.moved_blocks_count, 0)
        self.assertEqual(result.event.displaced_bytes, 0)
        self.assertEqual(mm.next_fit_ptr, 0)

    def test_defrag_full_memory(self):
        mm = MemoryManager()
        mm.init(16)
        mm.alloc(16, FitAlg.FIRST)
        result = mm.defrag(DefragOption.INIT)

        self.assertEqual(active_blocks(mm), [(1, 0, 16)])
        self.assertEqual(free_blocks(mm), [])
        self.assertEqual(result.event.moved_blocks_count, 0)
        self.assertEqual(result.event.displaced_bytes, 0)

    def test_defrag_resets_next_fit_pointer(self):
        mm = MemoryManager()
        mm.init(32)
        mm.alloc(8, FitAlg.NEXT)
        self.assertEqual(mm.next_fit_ptr, 8)

        mm.defrag(DefragOption.END)
        self.assertEqual(mm.next_fit_ptr, 0)

        result = mm.alloc(8, FitAlg.NEXT)
        self.assertEqual(result.event.chosen_hole["start"], 8)
        self.assertEqual(mm.next_fit_ptr, 16)

    def test_invalid_defrag_option(self):
        mm = MemoryManager()
        mm.init(8)
        with self.assertRaises(ValueError):
            mm.defrag("foo")


if __name__ == "__main__":
    unittest.main()
