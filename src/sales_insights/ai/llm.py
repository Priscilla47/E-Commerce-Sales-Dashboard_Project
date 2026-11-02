"""The small interface every language model client has to offer.

The features of the project talk to a ``LLMClient`` and never to a provider, so that the provider
can be chosen or changed later without touching them, and so that tests never call a service.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

ROLES = ("system", "user", "assistant", "tool")


class LLMError(Exception):
    """A call to a language model failed: refused, timed out, or over the limit of calls."""


@dataclass(frozen=True)
class Message:
    """One message of a conversation.

    Raises:
        ValueError: ``role`` is not one of ``system``, ``user``, ``assistant`` or ``tool``.
        TypeError: ``content`` is not text.
    """

    role: str
    content: str

    def __post_init__(self) -> None:
        if self.role not in ROLES:
            raise ValueError(f"role must be one of {', '.join(ROLES)}, not {self.role!r}")
        if not isinstance(self.content, str):
            raise TypeError(f"The content of a message must be text, not {self.content!r}")


@dataclass(frozen=True)
class ToolCall:
    """The model asks for one of the functions it was offered, with these arguments."""

    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Completion:
    """What a model answered: some text, and the tool calls it asks for (none by default)."""

    text: str
    tool_calls: tuple[ToolCall, ...] = ()


@runtime_checkable
class LLMClient(Protocol):
    """Anything that can complete a conversation."""

    def complete(
        self, messages: Sequence[Message], tools: Sequence[Mapping[str, Any]] | None = None
    ) -> Completion:
        """Answer the conversation, optionally offering ``tools``.

        Raises:
            LLMError: the call failed or timed out.
        """
        ...
