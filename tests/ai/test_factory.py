import pytest

from sales_insights.ai import factory
from sales_insights.ai.config import AIConfig, load_config
from sales_insights.ai.factory import AIDisabled, LimitedClient, build_client, register_provider
from sales_insights.ai.fake import FakeLLM
from sales_insights.ai.llm import LLMClient, LLMError, Message

KEY = "sk-secret-0123456789"
HELLO = [Message("user", "hi")]


@pytest.fixture(autouse=True)
def clean_registry():
    saved = dict(factory._PROVIDERS)
    factory._PROVIDERS.clear()
    yield
    factory._PROVIDERS.clear()
    factory._PROVIDERS.update(saved)


def enabled(max_calls=3, provider="example"):
    return AIConfig(provider=provider, model="m", api_key=KEY, max_calls=max_calls)


def test_with_no_key_the_client_is_disabled_and_the_message_names_the_variable():
    with pytest.raises(AIDisabled, match="SALES_AI_API_KEY"):
        build_client(load_config({}))


def test_disabled_names_the_provider_variable_when_only_the_key_is_set():
    with pytest.raises(AIDisabled, match="SALES_AI_PROVIDER"):
        build_client(load_config({"SALES_AI_API_KEY": KEY}))


def test_the_disabled_message_never_contains_the_key():
    with pytest.raises(AIDisabled) as error:
        build_client(load_config({"SALES_AI_API_KEY": KEY}))
    assert KEY not in str(error.value)


def test_an_enabled_config_returns_the_registered_client():
    fake = FakeLLM(["hello"])
    register_provider("example", lambda config: fake)
    client = build_client(enabled())
    assert isinstance(client, LLMClient)
    assert client.complete(HELLO).text == "hello"


def test_the_provider_factory_receives_the_config():
    seen = []
    register_provider("example", lambda config: seen.append(config) or FakeLLM(["x"]))
    config = enabled()
    build_client(config)
    assert seen == [config]


def test_an_unknown_provider_is_refused_and_lists_the_known_ones():
    register_provider("known", lambda config: FakeLLM([]))
    with pytest.raises(LLMError, match="known"):
        build_client(enabled(provider="unknown"))


def test_an_unknown_provider_with_no_registered_provider_says_there_is_none():
    with pytest.raises(LLMError, match="No provider"):
        build_client(enabled())


def test_registering_the_same_name_twice_is_refused():
    register_provider("example", lambda config: FakeLLM([]))
    with pytest.raises(ValueError, match="already"):
        register_provider("example", lambda config: FakeLLM([]))


def test_the_call_limit_stops_the_calls_after_the_limit():
    register_provider("example", lambda config: FakeLLM(["1", "2", "3", "4"]))
    client = build_client(enabled(max_calls=2))
    assert [client.complete(HELLO).text for _ in range(2)] == ["1", "2"]
    with pytest.raises(LLMError, match="limit of 2"):
        client.complete(HELLO)


def test_a_refused_call_does_not_reach_the_provider():
    inner = FakeLLM(["1", "2"])
    client = LimitedClient(inner, limit=1, secret=KEY)
    client.complete(HELLO)
    with pytest.raises(LLMError):
        client.complete(HELLO)
    assert len(inner.calls) == 1


def test_a_failing_call_still_counts_against_the_limit():
    client = LimitedClient(FakeLLM([LLMError("boom"), "ok"]), limit=1, secret=KEY)
    with pytest.raises(LLMError, match="boom"):
        client.complete(HELLO)
    with pytest.raises(LLMError, match="limit"):
        client.complete(HELLO)


def test_the_key_never_appears_in_an_llm_error_message():
    leaking = FakeLLM([RuntimeError(f"401 for key {KEY} on https://x?k={KEY}")])
    client = LimitedClient(leaking, limit=3, secret=KEY)
    with pytest.raises(LLMError) as error:
        client.complete(HELLO)
    assert KEY not in str(error.value)
    assert KEY not in repr(error.value)
    assert error.value.__cause__ is None or KEY not in str(error.value.__cause__)


def test_an_llm_error_from_the_provider_is_redacted_as_well():
    client = LimitedClient(FakeLLM([LLMError(f"rejected {KEY}")]), limit=3, secret=KEY)
    with pytest.raises(LLMError) as error:
        client.complete(HELLO)
    assert KEY not in str(error.value)
    assert "rejected" in str(error.value)


def test_the_limited_client_does_not_show_the_key_in_its_repr():
    client = LimitedClient(FakeLLM([]), limit=3, secret=KEY)
    assert KEY not in repr(client)
    assert KEY not in str(client.__dict__)


def test_a_limit_below_one_is_refused():
    with pytest.raises(ValueError):
        LimitedClient(FakeLLM([]), limit=0, secret=KEY)
