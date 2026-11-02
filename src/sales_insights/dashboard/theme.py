"""The colours of the dashboard, defined once.

Every chart takes its colours from here. They are mid-tone on purpose: each one keeps a contrast
of at least 3:1 (the WCAG minimum for graphics) with a white page and with Streamlit's dark page.
"""

import re

LIGHT_BACKGROUND = "#FFFFFF"
DARK_BACKGROUND = "#0E1117"

# Blue first: a chart with one series uses PALETTE[0].
PALETTE = ("#2E7BC4", "#C8651B", "#1F8A70")


def _channel(value: int) -> float:
    """One colour channel (0 to 255) as linear light, as the WCAG formula defines it."""
    scaled = value / 255
    return scaled / 12.92 if scaled <= 0.03928 else ((scaled + 0.055) / 1.055) ** 2.4


def _luminance(colour: str) -> float:
    if not isinstance(colour, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", colour):
        raise ValueError(f"A colour must be a six-digit hex code such as '#2E7BC4', not {colour!r}")
    red, green, blue = (int(colour[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * _channel(red) + 0.7152 * _channel(green) + 0.0722 * _channel(blue)


def contrast_ratio(first: str, second: str) -> float:
    """The WCAG contrast ratio of two ``#RRGGBB`` colours: 1.0 (identical) to 21.0 (black/white).

    Raises:
        ValueError: a colour is not a six-digit hex code.
    """
    lighter, darker = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def with_alpha(colour: str, alpha: float) -> str:
    """The colour as a CSS ``rgba(...)`` text with the given opacity (0 to 1), for a band.

    Raises:
        ValueError: ``colour`` is not a six-digit hex code, or ``alpha`` is not from 0 to 1.
    """
    _luminance(colour)  # checks the colour
    if isinstance(alpha, bool) or not isinstance(alpha, int | float) or not 0 <= alpha <= 1:
        raise ValueError(f"alpha must be a number from 0 to 1, not {alpha!r}")
    red, green, blue = (int(colour[i : i + 2], 16) for i in (1, 3, 5))
    return f"rgba({red}, {green}, {blue}, {alpha})"
