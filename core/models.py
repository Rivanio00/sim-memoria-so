from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, List, Dict, Any


class FitAlg(str, Enum):
    FIRST = "first"
    BEST = "best"
    WORST = "worst"
    NEXT = "next"


class DefragOption(str, Enum):
    INIT = "init"
    END = "end"
    OPT = "opt"


@dataclass
class Block:
    id: Optional[int]  # None quando free=True
    start: int
    size: int
    free: bool

    @property
    def end(self) -> int:
        return self.start + self.size

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "start": self.start,
            "size": self.size,
            "end": self.end,
            "free": self.free,
        }


@dataclass
class MemoryStats:
    total_size: int
    used_bytes: int
    free_bytes: int
    holes_count: int
    largest_hole: int
    effective_usage: float  # Percentual (0.0 a 100.0)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Snapshot:
    total_size: int
    next_fit_ptr: int
    next_id: int
    blocks: List[Block]
    stats: MemoryStats

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_size": self.total_size,
            "next_fit_ptr": self.next_fit_ptr,
            "next_id": self.next_id,
            "blocks": [b.to_dict() for b in self.blocks],
            "stats": self.stats.to_dict(),
        }


@dataclass
class StepEvent:
    action: str  # init | alloc | freeid | freeaddr | defrag
    examined_holes: List[Dict[str, Any]] = field(default_factory=list)
    chosen_hole: Optional[Dict[str, Any]] = None
    affected_blocks: List[Dict[str, Any]] = field(default_factory=list)
    moved_blocks_count: int = 0
    displaced_bytes: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StepResult:
    command: str
    snapshot: Snapshot
    event: StepEvent

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command": self.command,
            "snapshot": self.snapshot.to_dict(),
            "event": self.event.to_dict(),
        }