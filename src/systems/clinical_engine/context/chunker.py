"""Splitting a long list of turns into token-bounded chunks."""
from __future__ import annotations

from collections.abc import Sequence

from .models import Turn
from .token_counter import TokenCounter
from .turn_formatter import TurnFormatter


class TokenBudgetChunker:
    """Splits turns into consecutive chunks that fit a token budget.

    Guarantees:
      * a turn is never cut: a turn larger than the budget gets a chunk of its own;
      * consecutive chunks share up to ``overlap_turns`` turns, so a statement
        answering a question near a boundary keeps its context;
      * the overlap is capped at a quarter of the budget, and every chunk moves
        forward by at least one turn, so the split always terminates.
    """

    def __init__(
        self,
        counter: TokenCounter,
        formatter: TurnFormatter,
        max_tokens: int,
        overlap_turns: int,
    ) -> None:
        self._counter = counter
        self._formatter = formatter
        self._max_tokens = max_tokens
        self._overlap_turns = overlap_turns

    def split(self, turns: Sequence[Turn]) -> list[list[Turn]]:
        """Returns the chunks in chronological order (empty input gives no chunks)."""
        if not turns:
            return []

        costs = [self._counter.count(self._formatter.format_turn(turn)) for turn in turns]
        chunks: list[list[Turn]] = []
        start = 0
        used = 0
        for index, cost in enumerate(costs):
            if index > start and used + cost > self._max_tokens:
                chunks.append(list(turns[start:index]))
                start = self._overlap_start(costs, start, index)
                used = sum(costs[start:index])
            used += cost
        chunks.append(list(turns[start:]))
        return chunks

    def _overlap_start(self, costs: Sequence[int], chunk_start: int, chunk_end: int) -> int:
        """Finds where the next chunk begins so that it repeats the previous tail."""
        overlap_cap = self._max_tokens // 4
        begin = chunk_end
        tail_cost = 0
        # `begin > chunk_start + 1` keeps at least one turn of the old chunk out of
        # the overlap, which guarantees forward progress.
        while begin > chunk_start + 1 and chunk_end - begin < self._overlap_turns:
            candidate_cost = costs[begin - 1]
            if tail_cost + candidate_cost > overlap_cap:
                break
            begin -= 1
            tail_cost += candidate_cost
        return begin
