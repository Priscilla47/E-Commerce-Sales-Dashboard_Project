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
class ToolCall:
    """The model asks for one of the functions it was offered, with these arguments.

    ``id`` pairs the request with its result; a provider gives one, and ``ask`` gives one to a
    request that has none.
    """

    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    id: str = ""


@dataclass(frozen=True)
class Message:
    """One message of a conversation.

    An ``assistant`` message may carry the ``tool_calls`` it made, and a ``tool`` message the
    ``tool_call_id`` of the request it answers, so that a provider can pair them.

    Raises:
        ValueError: ``role`` is not one of ``system``, ``user``, ``assistant`` or ``tool``, or
            ``tool_calls`` or ``tool_call_id`` is given to another role.
        TypeError: ``content`` is not text, ``tool_calls`` is not a tuple of ``ToolCall`` or
            ``tool_call_id`` is not text.
    """

    role: str
    content: str
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None

    def __post_init__(self) -> None:
        if self.role not in ROLES:
            raise ValueError(f"role must be one of {', '.join(ROLES)}, not {self.role!r}")
        if not isinstance(self.content, str):
            raise TypeError(f"The content of a message must be text, not {self.content!r}")
        if not isinstance(self.tool_calls, tuple) or not all(
            isinstance(call, ToolCall) for call in self.tool_calls
        ):
            raise TypeError(f"tool_calls must be a tuple of ToolCall, not {self.tool_calls!r}")
        if self.tool_call_id is not None and not isinstance(self.tool_call_id, str):
            raise TypeError(f"tool_call_id must be text, not {self.tool_call_id!r}")
        if self.tool_calls and self.role != "assistant":
            raise ValueError("Only an assistant message can carry tool calls")
        if self.tool_call_id is not None and self.role != "tool":
            raise ValueError("Only a tool message can carry a tool call id")


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
