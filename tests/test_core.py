import unittest
from core.manager import MemoryManager
from core.models import FitAlg


class TestMemoryManagerPDFExamples(unittest.TestCase):
    def test_next_fit_pdf_example(self):
        mm = MemoryManager()
        mm.init(32)
        mm.alloc(8, FitAlg.NEXT)
        mm.alloc(8, FitAlg.NEXT)
        mm.alloc(8, FitAlg.NEXT)
        mm.free_id(1)
        mm.alloc(4, FitAlg.NEXT)
        res = mm.alloc(6, FitAlg.NEXT)

        # Verifica buracos examinados no último alloc (wrap-around)
        examined_starts = [h["start"] for h in res.event.examined_holes]
        self.assertEqual(examined_starts, [28, 0])
        self.assertEqual(res.event.chosen_hole["start"], 0)
        self.assertEqual(mm.next_fit_ptr, 6)

        st = mm.stats()
        self.assertEqual(st.used_bytes, 26)
        self.assertEqual(st.free_bytes, 6)
        self.assertEqual(st.holes_count, 2)
        self.assertEqual(st.largest_hole, 4)
        self.assertEqual(st.effective_usage, 81.25)

    def test_alloc_failure_preserves_id_and_pointer(self):
        mm = MemoryManager()
        mm.init(16)
        mm.alloc(10, FitAlg.NEXT)  # id=1, ptr=10
        fail = mm.alloc(8, FitAlg.NEXT)

        self.assertIsNotNone(fail.event.error)
        self.assertIn("Erro: sem espaço contíguo para 8 bytes (livre total: 6, maior buraco: 6)", fail.event.error)
        self.assertEqual(mm.next_id, 2)
        self.assertEqual(mm.next_fit_ptr, 10)


if __name__ == "__main__":
    unittest.main()