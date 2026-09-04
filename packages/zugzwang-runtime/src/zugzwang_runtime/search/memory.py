"""Endogenous search memory: deterministic retrieval over one workspace."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from zugzwang_core.domain.errors import SecurityError

from .workspace import SearchWorkspace


@dataclass(frozen=True, slots=True)
class RetrievalQuery:
    node_id: str
    text: str = ""


@dataclass(frozen=True, slots=True)
class RetrievalBudget:
    max_items: int = 8


@dataclass(frozen=True, slots=True)
class MemoryItem:
    memory_id: str
    kind: str
    content: str
    source_node_ids: tuple[str, ...]
    generated_by: str
    created_at_index: int
    source_position_keys: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    retriever: str
    items: tuple[MemoryItem, ...]


class SearchRetriever(Protocol):
    name: str

    def retrieve(
        self,
        query: RetrievalQuery,
        workspace: SearchWorkspace,
        memories: tuple[MemoryItem, ...],
        budget: RetrievalBudget,
    ) -> RetrievalResult: ...


class SearchMemoryFabric:
    """SQLite-ready in-memory facade for model-generated search evidence."""

    def __init__(
        self,
        workspace: SearchWorkspace,
        *,
        initial_items: tuple[MemoryItem, ...] = (),
    ) -> None:
        self.workspace = workspace
        self._items: list[MemoryItem] = list(initial_items)

    @property
    def items(self) -> tuple[MemoryItem, ...]:
        return tuple(self._items)

    def record(
        self,
        *,
        node_id: str,
        kind: str,
        content: str,
        generated_by: str,
        source_node_ids: tuple[str, ...] | None = None,
    ) -> MemoryItem:
        self.workspace.state(node_id)
        lowered = f"{kind} {content} {generated_by}".lower()
        if (
            "evaluation://" in lowered
            or "stockfish" in lowered
            or "tablebase" in lowered
            or "engine evaluation" in lowered
        ):
            raise SecurityError("external engine evidence cannot enter Search Memory")
        source_ids = source_node_ids or (node_id,)
        source_positions = tuple(
            self.workspace.nodes[source].position_key
            for source in source_ids
            if source in self.workspace.nodes
        )
        item = MemoryItem(
            memory_id=f"memory_{len(self._items):08d}",
            kind=kind,
            content=content,
            source_node_ids=source_ids,
            generated_by=generated_by,
            created_at_index=len(self._items),
            source_position_keys=source_positions,
        )
        self._items.append(item)
        return item

    def retrieve(
        self,
        retriever: str,
        node_id: str,
        budget: RetrievalBudget,
        *,
        text: str = "",
    ) -> RetrievalResult:
        if budget.max_items < 0:
            raise ValueError("retrieval budget must not be negative")
        query = RetrievalQuery(node_id=node_id, text=text)
        selected = _retriever(retriever).retrieve(query, self.workspace, self.items, budget)
        self.workspace.record_retrieval_event(
            retriever,
            node_id,
            len(selected.items),
            result_memory_ids=tuple(item.memory_id for item in selected.items),
            budget=budget.max_items,
        )
        return selected


class _ExactStateRetriever:
    name = "exact_state"

    def retrieve(
        self,
        query: RetrievalQuery,
        workspace: SearchWorkspace,
        memories: tuple[MemoryItem, ...],
        budget: RetrievalBudget,
    ) -> RetrievalResult:
        position = workspace.nodes[query.node_id].position_key
        return RetrievalResult(
            self.name,
            tuple(
                item
                for item in memories
                if position in item.source_position_keys
                or any(
                    node in workspace.nodes and workspace.nodes[node].position_key == position
                    for node in item.source_node_ids
                )
            )[: budget.max_items],
        )


class _AncestorRetriever:
    name = "ancestors"

    def retrieve(
        self,
        query: RetrievalQuery,
        workspace: SearchWorkspace,
        memories: tuple[MemoryItem, ...],
        budget: RetrievalBudget,
    ) -> RetrievalResult:
        ancestors: set[str] = set()
        current = workspace.nodes[query.node_id]
        while current.parent_id is not None:
            ancestors.add(current.parent_id)
            current = workspace.nodes[current.parent_id]
        return RetrievalResult(
            self.name,
            tuple(item for item in memories if ancestors.intersection(item.source_node_ids))[
                : budget.max_items
            ],
        )


class _SiblingRetriever:
    name = "siblings"

    def retrieve(
        self,
        query: RetrievalQuery,
        workspace: SearchWorkspace,
        memories: tuple[MemoryItem, ...],
        budget: RetrievalBudget,
    ) -> RetrievalResult:
        parent_id = workspace.nodes[query.node_id].parent_id
        if parent_id is None:
            return RetrievalResult(self.name, ())
        siblings = {
            edge.child_node_id
            for edge in workspace.edges
            if edge.parent_node_id == parent_id and edge.child_node_id is not None
        }
        return RetrievalResult(
            self.name,
            tuple(item for item in memories if siblings.intersection(item.source_node_ids))[
                : budget.max_items
            ],
        )


class _TextRetriever:
    def __init__(self, name: str, *, kinds: tuple[str, ...] = ()) -> None:
        self.name = name
        self._kinds = kinds

    def retrieve(
        self,
        query: RetrievalQuery,
        workspace: SearchWorkspace,
        memories: tuple[MemoryItem, ...],
        budget: RetrievalBudget,
    ) -> RetrievalResult:
        terms = set(query.text.lower().split())
        matches: list[MemoryItem] = []
        for item in reversed(memories):
            if self._kinds and item.kind not in self._kinds:
                continue
            if not terms or terms.intersection(item.content.lower().split()):
                matches.append(item)
        return RetrievalResult(self.name, tuple(matches[: budget.max_items]))


def _retriever(name: str) -> SearchRetriever:
    builtins: dict[str, SearchRetriever] = {
        "exact_state": _ExactStateRetriever(),
        "ancestors": _AncestorRetriever(),
        "siblings": _SiblingRetriever(),
        "root_move": _TextRetriever("root_move", kinds=("candidate",)),
        "refutation": _TextRetriever("refutation", kinds=("refutation",)),
        "failure": _TextRetriever("failure", kinds=("failure",)),
        "frontier": _TextRetriever("frontier", kinds=("frontier",)),
        "disagreement": _TextRetriever("disagreement", kinds=("disagreement",)),
        "transposition": _ExactStateRetriever(),
    }
    try:
        return builtins[name]
    except KeyError as exc:
        raise ValueError(f"unknown endogenous search retriever {name!r}") from exc
