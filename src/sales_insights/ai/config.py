"""Settings of the AI features, read from environment variables.

Nothing is read from a file here and no key is ever printed, logged or put in an error message.
Without a key the AI features are switched off and the rest of the project is unchanged.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

PROVIDER = "SALES_AI_PROVIDER"
MODEL = "SALES_AI_MODEL"
API_KEY = "SALES_AI_API_KEY"
MAX_CALLS = "SALES_AI_MAX_CALLS"
VARIABLES = (PROVIDER, MODEL, API_KEY, MAX_CALLS)

DEFAULT_MAX_CALLS = 20
LARGEST_MAX_CALLS = 10_000


class ConfigError(ValueError):
    """A variable has a value that cannot be used."""


@dataclass(frozen=True)
class AIConfig:
    """The provider, the model, the key and the number of calls allowed in a session."""

    provider: str | None
    model: str | None
    api_key: str | None = field(repr=False)
    max_calls: int = DEFAULT_MAX_CALLS

    @property
    def enabled(self) -> bool:
        """True when there is a key and a provider to use it with."""
        return bool(self.api_key) and bool(self.provider)

    def __str__(self) -> str:
        return repr(self)


def _text(environ: Mapping[str, str], name: str) -> str | None:
    value = environ.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _limit(environ: Mapping[str, str]) -> int:
    raw = environ.get(MAX_CALLS)
    if raw is None:
        return DEFAULT_MAX_CALLS
    text = raw.strip()
    if not re.fullmatch(r"[0-9]+", text) or not 1 <= int(text) <= LARGEST_MAX_CALLS:
        raise ConfigError(
            f"{MAX_CALLS} must be a whole number from 1 to {LARGEST_MAX_CALLS}, not {raw!r}"
        )
    return int(text)


def load_config(environ: Mapping[str, str]) -> AIConfig:
    """Read the settings from ``environ`` (pass ``os.environ``).

    A missing or blank key means the AI is switched off (``enabled`` is False).

    Raises:
        ConfigError: ``SALES_AI_MAX_CALLS`` is not a whole number from 1 to 10000.
    """
    return AIConfig(
        provider=_text(environ, PROVIDER),
        model=_text(environ, MODEL),
        api_key=_text(environ, API_KEY),
        max_calls=_limit(environ),
    )
