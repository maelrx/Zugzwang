"""Chess tasks (design §14.6).

Tasks define how episodes are built and how observations/metrics are shaped.
The runtime owns execution; tasks own episode semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from zugzwang_core.domain.events import JsonValue

from ..environment.standard import START_FEN


@dataclass(frozen=True, slots=True)
class MoveSelectionTaskSpec:
    """One fixed position; the model selects a move (free or grounded)."""

    task_id = "chess.move-selection"
    version = "0.1.0"

    fen: str = START_FEN
    move_prefix: tuple[str, ...] = ()
    single_player: bool = True

    def episode_config(self, seed: int) -> dict[str, JsonValue]:
        return {
            "start_fen": self.fen,
            "move_prefix": list(self.move_prefix),
            "seed": seed,
        }


@dataclass(frozen=True, slots=True)
class FullGameTaskSpec:
    """A full game between white and black actors."""

    task_id = "chess.full-game"
    version = "0.1.0"

    openings: tuple[str, ...] = (START_FEN,)
    paired_colors: bool = False
    max_plies: int = 240
    single_player: bool = False

    def episode_config(
        self, opening_index: int, seed: int, color: str = "white"
    ) -> dict[str, JsonValue]:
        return {
            "start_fen": self.openings[opening_index % len(self.openings)],
            "max_plies": self.max_plies,
            "seed": seed,
            "model_color": color,
        }


@dataclass(frozen=True, slots=True)
class StateReconstructionTaskSpec:
    """The model reconstructs state from a move sequence."""

    task_id = "chess.state-reconstruction"
    version = "0.1.0"

    move_sequences: tuple[tuple[str, ...], ...] = ()
    single_player: bool = True

    def episode_config(self, index: int, seed: int) -> dict[str, JsonValue]:
        sequence = self.move_sequences[index % len(self.move_sequences)]
        return {
            "move_prefix": list(sequence),
            "start_fen": START_FEN,
            "seed": seed,
        }


@dataclass(frozen=True, slots=True)
class OpeningSuite:
    """Paired openings: each opening played with colors swapped (FR-030)."""

    suite_id: str
    version: str
    fens: tuple[str, ...] = field(default_factory=tuple)

    def paired_slots(self) -> tuple[tuple[str, str], ...]:
        """Return (opening_fen, model_color) pairs with both colors."""
        slots: list[tuple[str, str]] = []
        for fen in self.fens:
            slots.append((fen, "white"))
            slots.append((fen, "black"))
        return tuple(slots)
