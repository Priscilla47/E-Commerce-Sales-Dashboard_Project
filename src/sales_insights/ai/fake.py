"""A scripted client for tests: it answers in order and remembers what it was asked."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sales_insights.ai.llm import Completion, LLMError, Message


@dataclass(frozen=True)
class Call:
    """One call received by the fake."""

    messages: tuple[Message, ...]
    tools: Sequence[Mapping[str, Any]] | None


class FakeLLM:
    """Returns the scripted answers in order.

    Each item of the script is a text, a ``Completion`` or an exception to raise in its turn.
    ``calls`` lists what was received, for assertions.

    Raises:
        TypeError: an item of the script is none of these.
    """

    def __init__(self, script: Sequence[str | Completion | Exception]) -> None:
        for item in script:
            if not isinstance(item, str | Completion | Exception):
                raise TypeError(
                    f"A scripted answer must be text, a Completion or an error: {item!r}"
                )
        self._script = list(script)
        self._next = 0
        self.calls: list[Call] = []

    def complete(
        self, messages: Sequence[Message], tools: Sequence[Mapping[str, Any]] | None = None
    ) -> Completion:
        """Return the next scripted answer.

        Raises:
            LLMError: the script has no answer left (or the next item is an error to raise).
        """
        self.calls.append(Call(tuple(messages), tools))
        if self._next >= len(self._script):
            count = len(self._script)
            word = "answer" if count == 1 else "answers"
            raise LLMError(
                f"FakeLLM was called {len(self.calls)} times but has {count} {word} scripted"
            )
        item = self._script[self._next]
        self._next += 1
        if isinstance(item, Exception):
            raise item
        return item if isinstance(item, Completion) else Completion(item)
