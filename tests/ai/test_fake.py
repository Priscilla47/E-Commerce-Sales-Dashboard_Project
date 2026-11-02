import pytest

from sales_insights.ai.fake import FakeLLM
from sales_insights.ai.llm import Completion, LLMClient, LLMError, Message, ToolCall

HELLO = [Message("user", "hello")]


def test_the_answers_come_in_the_order_of_the_script():
    fake = FakeLLM(["one", "two", "three"])
    assert [fake.complete(HELLO).text for _ in range(3)] == ["one", "two", "three"]


def test_a_script_can_hold_completions_with_tool_calls():
    call = ToolCall("top_products", {"n": 3})
    fake = FakeLLM([Completion("", (call,)), "done"])
    assert fake.complete(HELLO).tool_calls == (call,)
    assert fake.complete(HELLO).text == "done"


def test_the_messages_received_are_recorded_in_order():
    fake = FakeLLM(["a", "b"])
    fake.complete([Message("user", "first")])
    fake.complete([Message("system", "rules"), Message("user", "second")])
    assert [[m.content for m in call.messages] for call in fake.calls] == [
        ["first"],
        ["rules", "second"],
    ]


def test_the_tools_received_are_recorded():
    tools = [{"name": "revenue_by"}]
    fake = FakeLLM(["a", "b"])
    fake.complete(HELLO, tools=tools)
    fake.complete(HELLO)
    assert [call.tools for call in fake.calls] == [tools, None]


def test_the_recorded_messages_cannot_be_changed_by_the_caller_afterwards():
    messages = [Message("user", "first")]
    fake = FakeLLM(["a"])
    fake.complete(messages)
    messages.append(Message("user", "later"))
    assert len(fake.calls[0].messages) == 1


def test_asking_for_one_more_answer_than_scripted_is_a_clear_error():
    fake = FakeLLM(["only"])
    fake.complete(HELLO)
    with pytest.raises(LLMError, match=r"1 answer.*scripted|scripted.*1 answer"):
        fake.complete(HELLO)


def test_an_empty_script_fails_on_the_first_call():
    with pytest.raises(LLMError, match="0 answers"):
        FakeLLM([]).complete(HELLO)


def test_a_scripted_error_is_raised_in_its_turn():
    fake = FakeLLM(["fine", LLMError("The call timed out"), "after"])
    assert fake.complete(HELLO).text == "fine"
    with pytest.raises(LLMError, match="timed out"):
        fake.complete(HELLO)
    assert fake.complete(HELLO).text == "after"


def test_the_fake_is_an_llm_client():
    assert isinstance(FakeLLM([]), LLMClient)


def test_the_script_is_copied():
    script = ["a"]
    fake = FakeLLM(script)
    script.append("b")
    fake.complete(HELLO)
    with pytest.raises(LLMError):
        fake.complete(HELLO)


def test_an_item_that_is_not_text_a_completion_or_an_error_is_refused():
    with pytest.raises(TypeError):
        FakeLLM([42])
