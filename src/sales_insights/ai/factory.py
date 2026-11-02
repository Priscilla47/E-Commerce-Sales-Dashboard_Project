"""Building the client of the configured provider.

No provider is built into the project: a provider registers a function that builds its client, and
``build_client`` looks it up by the name in ``SALES_AI_PROVIDER``. Every client is wrapped so that a
session cannot make more calls than ``SALES_AI_MAX_CALLS`` and so that the key never leaves in an
error message.
"""

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from sales_insights.ai.config import API_KEY, MAX_CALLS, PROVIDER, AIConfig
from sales_insights.ai.llm import Completion, LLMClient, LLMError, Message

ProviderFactory = Callable[[AIConfig], LLMClient]

_PROVIDERS: dict[str, ProviderFactory] = {}


class AIDisabled(Exception):
    """The AI features are switched off: a variable is missing."""


def register_provider(name: str, factory: ProviderFactory) -> None:
    """Make the provider ``name`` available to ``build_client``.

    Raises:
        ValueError: a provider of this name is already registered.
    """
    if name in _PROVIDERS:
        raise ValueError(f"A provider named {name!r} is already registered")
    _PROVIDERS[name] = factory


class _Secret:
    """Holds the key so that printing the client or its fields never shows it."""

    __slots__ = ("value",)

    def __init__(self, value: str) -> None:
        self.value = value

    def __repr__(self) -> str:
        return "***"


class LimitedClient:
    """Wraps a client: refuses calls over the limit and removes the key from error messages."""

    def __init__(self, client: LLMClient, limit: int, secret: str | None) -> None:
        if limit < 1:
            raise ValueError("The limit of calls must be at least 1")
        self._client = client
        self._limit = limit
        self._secret = _Secret(secret) if secret else None
        self._calls = 0

    def __repr__(self) -> str:
        return f"LimitedClient(calls={self._calls}, limit={self._limit})"

    def _clean(self, text: str) -> str:
        return text.replace(self._secret.value, "***") if self._secret else text

    def complete(
        self, messages: Sequence[Message], tools: Sequence[Mapping[str, Any]] | None = None
    ) -> Completion:
        """Forward the call, unless the limit of the session is reached.

        Raises:
            LLMError: the limit is reached, or the call failed (the message never has the key).
        """
        if self._calls >= self._limit:
            raise LLMError(f"The limit of {self._limit} calls for this session is reached")
        self._calls += 1
        try:
            return self._client.complete(messages, tools)
        except LLMError as error:
            raise LLMError(self._clean(str(error))) from None
        except Exception as error:
            raise LLMError(self._clean(f"The call failed: {error}")) from None


def build_client(config: AIConfig) -> LLMClient:
    """The client of the configured provider, limited to ``config.max_calls`` calls.

    Raises:
        AIDisabled: there is no key or no provider; the message says which variable to set.
        LLMError: the provider is not registered.
    """
    if not config.api_key:
        raise AIDisabled(f"The AI features are switched off. Set {API_KEY} to switch them on.")
    if not config.provider:
        raise AIDisabled(
            f"The AI features are switched off. Set {PROVIDER} to the provider to use."
        )
    factory = _PROVIDERS.get(config.provider)
    if factory is None:
        known = ", ".join(sorted(_PROVIDERS))
        if not known:
            raise LLMError(f"No provider is installed, so {config.provider!r} cannot be used")
        raise LLMError(f"Unknown provider {config.provider!r}; known providers: {known}")
    return LimitedClient(factory(config), config.max_calls, config.api_key)


__all__ = ["MAX_CALLS", "AIDisabled", "LimitedClient", "build_client", "register_provider"]
