import pytest

from sales_insights.ai.config import (
    DEFAULT_MAX_CALLS,
    VARIABLES,
    AIConfig,
    ConfigError,
    load_config,
)

KEY = "sk-secret-0123456789"
ALL = {
    "SALES_AI_PROVIDER": "example",
    "SALES_AI_MODEL": "small-1",
    "SALES_AI_API_KEY": KEY,
    "SALES_AI_MAX_CALLS": "7",
}


def test_no_variable_means_the_ai_is_switched_off():
    config = load_config({})
    assert config.enabled is False
    assert config.api_key is None
    assert config.max_calls == DEFAULT_MAX_CALLS


def test_all_the_variables_are_read():
    config = load_config(ALL)
    assert (config.provider, config.model, config.api_key, config.max_calls) == (
        "example",
        "small-1",
        KEY,
        7,
    )
    assert config.enabled is True


@pytest.mark.parametrize("key", ["", "   ", "\t\n"])
def test_an_empty_key_is_the_same_as_no_key(key):
    assert load_config({**ALL, "SALES_AI_API_KEY": key}).enabled is False


def test_a_key_without_a_provider_is_not_enabled():
    config = load_config({"SALES_AI_API_KEY": KEY})
    assert config.enabled is False


def test_unrelated_variables_are_ignored():
    assert load_config({"PATH": "/bin", "HOME": "/root"}).enabled is False


def test_spaces_around_the_values_are_removed():
    config = load_config({**ALL, "SALES_AI_PROVIDER": "  example ", "SALES_AI_MAX_CALLS": " 3 "})
    assert (config.provider, config.max_calls) == ("example", 3)


@pytest.mark.parametrize("limit", ["-1", "0", "abc", "1.5", "", "  ", "1e3", "99999999999"])
def test_an_invalid_call_limit_is_refused_and_names_the_variable(limit):
    with pytest.raises(ConfigError, match="SALES_AI_MAX_CALLS"):
        load_config({**ALL, "SALES_AI_MAX_CALLS": limit})


def test_the_error_for_a_bad_limit_never_shows_the_key():
    with pytest.raises(ConfigError) as error:
        load_config({**ALL, "SALES_AI_MAX_CALLS": "-1"})
    assert KEY not in str(error.value)


def test_the_key_is_hidden_in_repr_and_str():
    config = load_config(ALL)
    for text in (repr(config), str(config), f"{config}", f"{config!r}", format(config)):
        assert KEY not in text
        assert "example" in text


def test_a_config_is_frozen():
    config = load_config(ALL)
    with pytest.raises(AttributeError):
        config.provider = "other"  # type: ignore[misc]


def test_the_variables_are_the_ones_the_documentation_names():
    assert set(VARIABLES) == set(ALL)
    assert all(name.startswith("SALES_AI_") for name in VARIABLES)


def test_the_environment_is_not_changed():
    environ = dict(ALL)
    load_config(environ)
    assert environ == ALL


def test_a_config_can_be_built_by_hand():
    assert AIConfig(provider="example", model="m", api_key=None, max_calls=1).enabled is False
