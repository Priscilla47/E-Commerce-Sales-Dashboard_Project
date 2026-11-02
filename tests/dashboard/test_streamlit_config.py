import tomllib
from pathlib import Path

from sales_insights.dashboard.theme import PALETTE, contrast_ratio

CONFIG = Path(__file__).resolve().parents[2] / ".streamlit" / "config.toml"


def _config() -> dict:
    return tomllib.loads(CONFIG.read_text(encoding="utf-8"))


def test_the_config_file_exists_and_is_valid_toml():
    assert CONFIG.is_file()
    assert "theme" in _config()


def test_the_accent_colour_is_the_first_colour_of_the_palette():
    assert _config()["theme"]["primaryColor"].upper() == PALETTE[0].upper()


def test_the_theme_does_not_force_a_light_or_a_dark_page():
    # The page follows the browser's setting, which is what the palette was checked against.
    theme = _config()["theme"]
    assert "base" not in theme
    assert "backgroundColor" not in theme


def test_the_accent_colour_is_readable_on_the_white_and_the_dark_page():
    from sales_insights.dashboard.theme import DARK_BACKGROUND, LIGHT_BACKGROUND

    accent = _config()["theme"]["primaryColor"]
    assert contrast_ratio(accent, LIGHT_BACKGROUND) >= 3
    assert contrast_ratio(accent, DARK_BACKGROUND) >= 3


def test_the_file_is_in_the_folder_streamlit_reads_from_the_project_root():
    assert CONFIG.parent.name == ".streamlit"
    assert (CONFIG.parents[1] / "pyproject.toml").is_file()


def test_an_upload_is_limited_to_50_megabytes_not_the_200_of_streamlit():
    # A million orders is about 45 MB and needs about 0.5 GB to load; 200 MB would need 2 GB+.
    assert _config()["server"]["maxUploadSize"] == 50


def test_the_page_documents_the_upload_limit():
    page = (CONFIG.parents[1] / "docs" / "dashboard.md").read_text()
    assert "50 MB" in page
