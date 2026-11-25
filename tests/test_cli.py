import io
import tempfile
import unittest
from pathlib import Path

from cli.main import MemoryCLI


class CLITestCase(unittest.TestCase):
    def setUp(self):
        self.out = io.StringIO()
        self.cli = MemoryCLI(out=self.out)

    def run_lines(self, *lines: str) -> str:
        for line in lines:
            self.cli.execute_line(line)
        return self.out.getvalue()

    def test_show_matches_pdf_example(self):
        output = self.run_lines(
            "init 64",
            "alloc 10 first",
            "alloc 8 first",
            "freeid 2",
            "alloc 6 best",
            "show",
        )

        expected_map = (
            "Mapa de Memória (64 bytes)\n"
            + "-" * 66 + "\n"
            + "[################................................................]\n"
            + "[1111111111333333................................................]\n"
            + "-" * 66 + "\n"
        )
        self.assertIn(expected_map, output)
        self.assertIn(
            "Blocos ativos: [id=1] @0 +10B (usado=10B) | "
            "[id=3] @10 +6B (usado=6B)",
            output,
        )
        self.assertIn("Ocupado: 16 bytes | Livre: 48 bytes", output)
        self.assertIn("Buracos (fragmentação externa): 1", output)
        self.assertIn("Maior buraco livre: 48 bytes", output)
        self.assertIn("Uso efetivo: 25.00%", output)

    def test_next_fit_sequence_and_stats(self):
        output = self.run_lines(
            "init 32",
            "alloc 8 next",
            "alloc 8 next",
            "alloc 8 next",
            "freeid 1",
            "alloc 4 next",
            "alloc 6 next",
            "stats",
        )

        self.assertIn(
            "Alocado [id=5] @0 +6B (next). Ponteiro Next Fit -> @6.",
            output,
        )
        self.assertIn("Ocupado: 26 bytes | Livre: 6 bytes", output)
        self.assertIn("Buracos (fragmentação externa): 2", output)
        self.assertIn("Maior buraco livre: 4 bytes", output)
        self.assertIn("Uso efetivo: 81.25%", output)

    def test_stats_output_is_exact(self):
        output = self.run_lines("init 10", "alloc 3 first", "stats")
        expected = (
            "== Estatísticas ==\n"
            "Tamanho total: 10 bytes\n"
            "Ocupado: 3 bytes | Livre: 7 bytes\n"
            "Buracos (fragmentação externa): 1\n"
            "Maior buraco livre: 7 bytes\n"
            "Uso efetivo: 30.00%\n"
        )
        self.assertTrue(output.endswith(expected))

    def test_alloc_failure_message_and_state(self):
        output = self.run_lines("init 16", "alloc 10 first", "alloc 8 first")

        self.assertIn(
            "Erro: sem espaço contíguo para 8 bytes "
            "(livre total: 6, maior buraco: 6)",
            output,
        )
        self.assertEqual(self.cli.manager.next_id, 2)
        active = [b for b in self.cli.manager.blocks if not b.free]
        self.assertEqual(len(active), 1)
        self.assertEqual((active[0].id, active[0].start, active[0].size), (1, 0, 10))

    def test_free_errors_do_not_change_memory(self):
        self.run_lines("init 16", "alloc 4 first")
        before = [b.to_dict() for b in self.cli.manager.blocks]

        output = self.run_lines("freeid 99", "freeaddr 5")

        self.assertIn("Erro: bloco com id=99 não encontrado.", output)
        self.assertIn(
            "Erro: nenhum bloco alocado inicia no endereço 5.",
            output,
        )
        self.assertEqual([b.to_dict() for b in self.cli.manager.blocks], before)

    def test_free_reports_coalescence(self):
        output = self.run_lines(
            "init 32",
            "alloc 8 first",
            "alloc 8 first",
            "freeid 2",
        )
        self.assertIn(
            "Liberado [id=2] @8 +8B. Buracos unidos em @8 +24B.",
            output,
        )

    def test_defrag_end_output(self):
        output = self.run_lines(
            "init 64",
            "alloc 10 first",
            "alloc 8 first",
            "alloc 6 first",
            "freeid 2",
            "defrag end",
        )

        self.assertIn("Defrag END: 1 bloco movido, 6 bytes deslocados.", output)
        self.assertIn("[id=3] @18 -> @10 (6B)", output)
        self.assertIn("Buracos (fragmentação externa): 1", output)
        self.assertEqual(
            [(b.id, b.start, b.size) for b in self.cli.manager.blocks if not b.free],
            [(1, 0, 10), (3, 10, 6)],
        )

    def test_defrag_init_output_plural(self):
        output = self.run_lines(
            "init 64",
            "alloc 10 first",
            "alloc 8 first",
            "alloc 6 first",
            "freeid 2",
            "defrag init",
        )
        self.assertIn("Defrag INIT: 2 blocos movidos, 16 bytes deslocados.", output)
        self.assertIn("[id=1] @0 -> @48 (10B)", output)
        self.assertIn("[id=3] @18 -> @58 (6B)", output)

    def test_init_resets_ids_and_pointer(self):
        self.run_lines("init 32", "alloc 8 next", "alloc 8 first")
        self.cli.execute_line("init 64")

        self.assertEqual(self.cli.manager.next_id, 1)
        self.assertEqual(self.cli.manager.next_fit_ptr, 0)
        self.assertEqual(
            [(b.start, b.size, b.free) for b in self.cli.manager.blocks],
            [(0, 64, True)],
        )

    def test_commands_before_init(self):
        output = self.run_lines("alloc 4 first", "show", "stats", "defrag end")
        message = (
            "Erro: memória não inicializada. "
            "Execute 'init <tamanho>' primeiro."
        )
        self.assertEqual(output.count(message), 4)

    def test_malformed_commands(self):
        output = self.run_lines(
            "init",
            "init 16 extra",
            "init 16",
            "alloc 4",
            "alloc 4 foo",
            "freeid abc",
            "defrag foo",
            "foo",
            "show extra",
            "stats extra",
        )

        self.assertIn("Uso: init <tamanho>", output)
        self.assertIn("Uso: alloc <tamanho> <first|best|worst|next>", output)
        self.assertIn(
            "Erro: Algoritmo inválido: 'foo'. Use first, best, worst ou next.",
            output,
        )
        self.assertIn("Erro: Valor inválido para id: 'abc'.", output)
        self.assertIn(
            "Erro: Opção de defrag inválida: 'foo'. Use init, end ou opt.",
            output,
        )
        self.assertIn("Erro: Comando desconhecido: 'foo'.", output)
        self.assertIn("Uso: show", output)
        self.assertIn("Uso: stats", output)

    def test_comments_are_ignored(self):
        output = self.run_lines(
            "# init 8",
            "init 16 # memória de teste",
            "alloc 4 first # primeiro bloco",
        )
        self.assertIn("Memória inicializada com 16 bytes.", output)
        self.assertEqual(self.cli.manager.next_id, 2)

    def test_show_uses_last_digit_for_multi_digit_ids(self):
        self.cli.execute_line("init 16")
        for _ in range(10):
            self.cli.execute_line("alloc 1 first")
        output = self.run_lines("show")
        self.assertIn("[1234567890......]", output)

    def test_run_script_ignores_comments_and_stops_at_eof(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "roteiro.cmd"
            path.write_text(
                "# comentário\n"
                "init 32\n"
                "alloc 8 next\n"
                "alloc 8 next\n"
                "show\n"
                "EOF\n"
                "alloc 8 next\n",
                encoding="utf-8",
            )
            self.assertTrue(self.cli.run_script(path))

        output = self.out.getvalue()
        self.assertIn("> init 32", output)
        self.assertIn("Mapa de Memória (32 bytes)", output)
        self.assertNotIn("> EOF", output)
        self.assertNotIn("id=3", output)
        self.assertEqual(self.cli.manager.next_id, 3)

    def test_run_script_no_echo(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "roteiro.cmd"
            path.write_text("init 8\nalloc 4 first\n", encoding="utf-8")
            self.cli.echo_commands = False
            self.assertTrue(self.cli.run_script(path))

        output = self.out.getvalue()
        self.assertNotIn("> init 8", output)
        self.assertIn("Alocado [id=1] @0 +4B (first).", output)

    def test_exit_stops_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "roteiro.cmd"
            path.write_text(
                "init 16\nalloc 4 first\nexit\nalloc 4 first\n",
                encoding="utf-8",
            )
            self.assertTrue(self.cli.run_script(path))

        self.assertEqual(self.cli.manager.next_id, 2)

    def test_missing_script_returns_error(self):
        self.assertFalse(self.cli.run_script("/caminho/que/nao/existe.cmd"))
        self.assertIn("Erro: não foi possível ler o roteiro", self.out.getvalue())


if __name__ == "__main__":
    unittest.main()
