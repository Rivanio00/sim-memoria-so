from __future__ import annotations
from typing import List, Dict, Any
from .manager import MemoryManager
from .models import DefragOption, FitAlg, StepResult


class CommandError(ValueError):
    """Erro de sintaxe ou de argumentos em um comando da CLI/roteiro."""


def _expect_args(parts: List[str], count: int, usage: str) -> None:
    if len(parts) != count + 1:
        raise CommandError(f"Uso: {usage}")


def _parse_int(value: str, label: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise CommandError(f"Valor inválido para {label}: '{value}'.") from exc


def execute_command_line(manager: MemoryManager, raw_line: str) -> StepResult:
    """
    Executa um comando que altera o estado da memória (init, alloc, freeid,
    freeaddr ou defrag). Comandos de visualização (show/stats) são tratados
    pela interface que consome o núcleo.

    Erros de sintaxe/argumentos geram CommandError (subclasse de ValueError).
    Erros de simulação (ex.: memória não inicializada) propagam RuntimeError.
    """
    parts = raw_line.strip().split()
    if not parts:
        raise CommandError("Comando vazio.")
    op = parts[0].lower()

    if op == "init":
        _expect_args(parts, 1, "init <tamanho>")
        return manager.init(_parse_int(parts[1], "tamanho"))

    if op == "alloc":
        _expect_args(parts, 2, "alloc <tamanho> <first|best|worst|next>")
        size = _parse_int(parts[1], "tamanho")
        try:
            alg = FitAlg(parts[2].lower())
        except ValueError as exc:
            raise CommandError(
                f"Algoritmo inválido: '{parts[2]}'. Use first, best, worst ou next."
            ) from exc
        return manager.alloc(size, alg)

    if op == "freeid":
        _expect_args(parts, 1, "freeid <id>")
        return manager.free_id(_parse_int(parts[1], "id"))

    if op == "freeaddr":
        _expect_args(parts, 1, "freeaddr <endereço>")
        return manager.free_addr(_parse_int(parts[1], "endereço"))

    if op == "defrag":
        _expect_args(parts, 1, "defrag <init|end|opt>")
        try:
            option = DefragOption(parts[1].lower())
        except ValueError as exc:
            raise CommandError(
                f"Opção de defrag inválida: '{parts[1]}'. Use init, end ou opt."
            ) from exc
        return manager.defrag(option)

    raise CommandError(f"Comando desconhecido: '{parts[0]}'.")


def build_simulation_trace(script_text: str) -> Dict[str, Any]:
    """
    Lê o conteúdo de um arquivo .cmd, ignora comentários (#), linhas vazias,
    'show' e 'stats', e devolve o trace completo para a simulação visual.
    """
    manager = MemoryManager()
    valid_commands: List[str] = []

    for line in script_text.lstrip("\ufeff").splitlines():
        clean = line.split("#", 1)[0].strip()
        if not clean:
            continue
        op = clean.split()[0].lower()
        if op == "eof":
            break
        if op in ("show", "stats"):
            continue
        valid_commands.append(clean)

    results: List[StepResult] = []
    for cmd in valid_commands:
        results.append(execute_command_line(manager, cmd))

    total_steps = len(results)
    steps_payload = []
    for idx, res in enumerate(results, start=1):
        steps_payload.append({
            "step_index": idx,
            "total_steps": total_steps,
            **res.to_dict(),
        })

    return {"steps": steps_payload}
