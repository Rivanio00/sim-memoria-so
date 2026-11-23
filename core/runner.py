from __future__ import annotations
from typing import List, Dict, Any
from .manager import MemoryManager
from .models import DefragOption, FitAlg, StepResult


def execute_command_line(manager: MemoryManager, raw_line: str) -> StepResult:
    parts = raw_line.strip().split()
    op = parts[0].lower()

    if op == "init":
        return manager.init(int(parts[1]))
    if op == "alloc":
        return manager.alloc(int(parts[1]), FitAlg(parts[2].lower()))
    if op == "freeid":
        return manager.free_id(int(parts[1]))
    if op == "freeaddr":
        return manager.free_addr(int(parts[1]))
    if op == "defrag":
        return manager.defrag(DefragOption(parts[1].lower()))

    raise ValueError(f"Comando desconhecido no roteiro: '{raw_line}'")


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