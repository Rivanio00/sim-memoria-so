"""Interface de linha de comando (CLI) do simulador de memória.

A CLI é apenas uma camada de apresentação: toda a lógica de alocação,
coalescência e desfragmentação fica em ``core/``. Este módulo cuida de:

* ler comandos do teclado (modo interativo) ou de um roteiro ``.cmd``;
* chamar ``core.runner.execute_command_line`` para os comandos mutadores;
* formatar o mapa, os blocos ativos, as estatísticas e o resumo do defrag.

Uso:
    .venv/bin/python -m cli.main                  # modo interativo
    .venv/bin/python -m cli.main roteiro.cmd      # executa um roteiro
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, TextIO

from core.manager import MemoryManager
from core.models import StepResult
from core.runner import execute_command_line


class MemoryCLI:
    """Sessão de CLI com um ``MemoryManager`` e um fluxo de saída."""

    def __init__(
        self,
        manager: Optional[MemoryManager] = None,
        out: Optional[TextIO] = None,
    ) -> None:
        self.manager = manager if manager is not None else MemoryManager()
        self.out = out if out is not None else sys.stdout
        self.echo_commands = True

    # ------------------------------------------------------------------
    # Saída formatada
    # ------------------------------------------------------------------
    def _usage_line(self) -> str:
        """Linha de uso físico: '#' para cada byte ocupado, '.' para livre."""
        cells = []
        for block in self.manager.blocks:
            cells.append(("." if block.free else "#") * block.size)
        return "[" + "".join(cells) + "]"

    def _ids_line(self) -> str:
        """
        Linha de identificadores, com um caractere por byte.

        Como a linha tem exatamente um caractere por byte, ids com mais de um
        dígito são representados pelo seu último dígito (ex.: id=12 -> '2').
        Os blocos livres continuam representados por '.'.
        """
        cells = []
        for block in self.manager.blocks:
            if block.free:
                cells.append("." * block.size)
            else:
                cells.append(str(block.id)[-1] * block.size)
        return "[" + "".join(cells) + "]"

    def print_map(self) -> None:
        total = self.manager.total_size
        separator = "-" * (total + 2)
        print(f"Mapa de Memória ({total} bytes)", file=self.out)
        print(separator, file=self.out)
        print(self._usage_line(), file=self.out)
        print(self._ids_line(), file=self.out)
        print(separator, file=self.out)

    def print_active_blocks(self) -> None:
        active = [b for b in self.manager.blocks if not b.free]
        if not active:
            print("Blocos ativos: (nenhum)", file=self.out)
            return
        parts = [
            f"[id={b.id}] @{b.start} +{b.size}B (usado={b.size}B)"
            for b in active
        ]
        print("Blocos ativos: " + " | ".join(parts), file=self.out)

    def print_stats(self) -> None:
        st = self.manager.stats()
        print("== Estatísticas ==", file=self.out)
        print(f"Tamanho total: {st.total_size} bytes", file=self.out)
        print(
            f"Ocupado: {st.used_bytes} bytes | Livre: {st.free_bytes} bytes",
            file=self.out,
        )
        print(f"Buracos (fragmentação externa): {st.holes_count}", file=self.out)
        print(f"Maior buraco livre: {st.largest_hole} bytes", file=self.out)
        print(f"Uso efetivo: {st.effective_usage:.2f}%", file=self.out)

    def print_show(self) -> None:
        """Mapa + blocos ativos + estatísticas (formato do exemplo do PDF)."""
        self.print_map()
        print(file=self.out)
        self.print_active_blocks()
        self.print_stats()

    def print_help(self) -> None:
        print("Comandos disponíveis:", file=self.out)
        print("  init <tamanho>                 Inicializa/reinicia a memória.", file=self.out)
        print("  alloc <tamanho> <algoritmo>    Aloca usando first, best, worst ou next.", file=self.out)
        print("  freeid <id>                    Libera o bloco com o id informado.", file=self.out)
        print("  freeaddr <endereço>            Libera o bloco que inicia no endereço.", file=self.out)
        print("  show                           Exibe mapa, blocos ativos e estatísticas.", file=self.out)
        print("  stats                          Exibe apenas as estatísticas.", file=self.out)
        print("  defrag <init|end|opt>          Compacta a memória e mostra o resumo.", file=self.out)
        print("  help                           Exibe esta ajuda.", file=self.out)
        print("  exit | quit | sair             Encerra a CLI.", file=self.out)

    # ------------------------------------------------------------------
    # Mensagens de resultado
    # ------------------------------------------------------------------
    def _print_error(self, exc: BaseException) -> None:
        message = str(exc)
        if not message.startswith(("Erro:", "Uso:")):
            message = f"Erro: {message}"
        print(message, file=self.out)

    def _require_initialized(self) -> bool:
        if self.manager.total_size <= 0:
            print(
                "Erro: memória não inicializada. Execute 'init <tamanho>' primeiro.",
                file=self.out,
            )
            return False
        return True

    def _print_alloc(self, result: StepResult) -> None:
        block = result.event.affected_blocks[0]
        alg = result.command.split()[-1]
        line = f"Alocado [id={block['id']}] @{block['start']} +{block['size']}B ({alg})."
        if alg == "next":
            line += f" Ponteiro Next Fit -> @{result.snapshot.next_fit_ptr}."
        print(line, file=self.out)

    def _print_free(self, result: StepResult) -> None:
        freed = next(
            (b for b in result.event.affected_blocks if not b.get("coalesced")),
            None,
        )
        coalesced = next(
            (b for b in result.event.affected_blocks if b.get("coalesced")),
            None,
        )
        if freed is None:
            print("Bloco liberado.", file=self.out)
            return

        line = f"Liberado [id={freed['id']}] @{freed['start']} +{freed['size']}B."
        if coalesced is not None:
            line += (
                f" Buracos unidos em @{coalesced['start']} "
                f"+{coalesced['size']}B."
            )
        print(line, file=self.out)

    def _print_defrag(self, result: StepResult) -> None:
        event = result.event
        option = result.command.split()[-1].upper()
        moved_count = event.moved_blocks_count
        displaced = event.displaced_bytes

        block_word = "bloco" if moved_count == 1 else "blocos"
        moved_word = "movido" if moved_count == 1 else "movidos"
        byte_word = "byte" if displaced == 1 else "bytes"
        displaced_word = "deslocado" if displaced == 1 else "deslocados"
        print(
            f"Defrag {option}: {moved_count} {block_word} {moved_word}, "
            f"{displaced} {byte_word} {displaced_word}.",
            file=self.out,
        )

        if event.affected_blocks:
            print("Blocos movidos:", file=self.out)
            for block in event.affected_blocks:
                print(
                    f"  [id={block['id']}] @{block['old_start']} -> "
                    f"@{block['new_start']} ({block['size']}B)",
                    file=self.out,
                )

        # Mostra o resultado compactado, como o 'show' faria.
        print(file=self.out)
        self.print_show()

    # ------------------------------------------------------------------
    # Execução de comandos
    # ------------------------------------------------------------------
    def execute_line(self, raw_line: str) -> bool:
        """
        Executa uma linha de comando e devolve ``False`` quando a CLI deve
        encerrar (comando exit/quit/sair), ou ``True`` para continuar.

        Comentários iniciados por '#' são ignorados. Erros de sintaxe, de
        argumentos e de simulação são impressos sem interromper a sessão.
        """
        clean = raw_line.split("#", 1)[0].strip()
        if not clean:
            return True

        parts = clean.split()
        op = parts[0].lower()

        if op in ("exit", "quit", "sair"):
            if len(parts) != 1:
                print("Uso: exit", file=self.out)
                return True
            return False

        if op == "help":
            if len(parts) != 1:
                print("Uso: help", file=self.out)
            else:
                self.print_help()
            return True

        if op == "show":
            if len(parts) != 1:
                print("Uso: show", file=self.out)
            elif self._require_initialized():
                self.print_show()
            return True

        if op == "stats":
            if len(parts) != 1:
                print("Uso: stats", file=self.out)
            elif self._require_initialized():
                self.print_stats()
            return True

        try:
            result = execute_command_line(self.manager, clean)
        except (ValueError, RuntimeError) as exc:
            self._print_error(exc)
            return True

        if result.event.error:
            print(result.event.error, file=self.out)
            return True

        if result.event.action == "init":
            print(
                f"Memória inicializada com {self.manager.total_size} bytes.",
                file=self.out,
            )
        elif result.event.action == "alloc":
            self._print_alloc(result)
        elif result.event.action in ("freeid", "freeaddr"):
            self._print_free(result)
        elif result.event.action == "defrag":
            self._print_defrag(result)

        return True

    # ------------------------------------------------------------------
    # Modos de execução
    # ------------------------------------------------------------------
    def run_script(self, path: str | Path) -> bool:
        """
        Executa um roteiro ``.cmd`` na CLI.

        Linhas em branco e comentários são ignorados; ``EOF`` encerra o
        roteiro. ``show`` e ``stats`` são executados normalmente (ao contrário
        da simulação visual, que os ignora). Devolve ``False`` apenas quando o
        arquivo não pode ser lido.
        """
        script_path = Path(path)
        try:
            text = script_path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            print(
                f"Erro: não foi possível ler o roteiro '{script_path}': {exc}",
                file=self.out,
            )
            return False

        for line in text.splitlines():
            clean = line.split("#", 1)[0].strip()
            if not clean:
                continue
            if clean.lower() == "eof":
                break
            if self.echo_commands:
                print(f"> {clean}", file=self.out)
            if not self.execute_line(clean):
                break

        return True

    def interactive(self) -> None:
        """Loop interativo com o prompt '> '."""
        print("Simulador de Memória — CLI", file=self.out)
        print(
            "Digite 'help' para listar os comandos ou 'exit' para sair.",
            file=self.out,
        )
        while True:
            try:
                raw_line = input("> ")
            except (EOFError, KeyboardInterrupt):
                print(file=self.out)
                break
            if not self.execute_line(raw_line):
                break


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m cli.main",
        description="Simulador de gerência de memória (First, Best, Worst e Next Fit).",
    )
    parser.add_argument(
        "roteiro",
        nargs="?",
        help="Arquivo .cmd a executar; se omitido, abre o modo interativo.",
    )
    parser.add_argument(
        "--no-echo",
        action="store_true",
        help="Não ecoa os comandos ao executar um roteiro.",
    )
    args = parser.parse_args(argv)

    cli = MemoryCLI()
    if args.roteiro:
        cli.echo_commands = not args.no_echo
        return 0 if cli.run_script(args.roteiro) else 1

    cli.interactive()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
