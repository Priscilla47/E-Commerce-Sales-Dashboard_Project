import dataclasses

import pytest

from sales_insights.ai.llm import Completion, LLMClient, LLMError, Message, ToolCall


def test_a_completion_holds_a_text_and_tool_calls():
    call = ToolCall(name="revenue_by", arguments={"column": "Country"})
    completion = Completion(text="ok", tool_calls=(call,))
    assert completion.text == "ok"
    assert completion.tool_calls == (call,)


def test_a_completion_without_tool_calls_has_an_empty_tuple():
    assert Completion(text="hello").tool_calls == ()


def test_messages_and_completions_are_frozen():
    for value in (Message("user", "hi"), Completion("hi"), ToolCall("x", {})):
        field = dataclasses.fields(value)[0].name
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(value, field, "other")


@pytest.mark.parametrize("role", ["system", "user", "assistant", "tool"])
def test_the_four_roles_are_accepted(role):
    assert Message(role, "text").role == role


@pytest.mark.parametrize("role", ["", "admin", "User", None])
def test_another_role_is_refused(role):
    with pytest.raises(ValueError, match="role"):
        Message(role, "text")


def test_the_content_of_a_message_must_be_text():
    with pytest.raises(TypeError):
        Message("user", 5)


def test_llm_error_is_an_exception_with_its_message():
    with pytest.raises(LLMError, match="timed out"):
        raise LLMError("The call timed out")


def test_a_class_with_complete_is_an_llm_client():
    class Mine:
        def complete(self, messages, tools=None):
            return Completion("x")

    assert isinstance(Mine(), LLMClient)
    assert not isinstance(object(), LLMClient)


# --- ids that pair a request with its result ----------------------------------------------------


def test_a_tool_call_has_an_empty_id_unless_one_is_given():
    assert ToolCall("total_revenue").id == ""
    assert ToolCall("total_revenue", {}, "abc").id == "abc"


def test_an_assistant_message_may_carry_tool_calls_and_a_tool_message_an_id():
    calls = (ToolCall("total_revenue", {}, "call_1"),)
    assert Message("assistant", "", tool_calls=calls).tool_calls == calls
    assert Message("tool", "Data", tool_call_id="call_1").tool_call_id == "call_1"
    plain = Message("user", "hi")
    assert plain.tool_calls == () and plain.tool_call_id is None


@pytest.mark.parametrize("role", ["system", "user", "tool"])
def test_only_an_assistant_message_carries_tool_calls(role):
    with pytest.raises(ValueError, match="assistant"):
        Message(role, "x", tool_calls=(ToolCall("total_revenue"),))


@pytest.mark.parametrize("role", ["system", "user", "assistant"])
def test_only_a_tool_message_carries_a_tool_call_id(role):
    with pytest.raises(ValueError, match="tool message"):
        Message(role, "x", tool_call_id="call_1")


def test_a_message_with_ids_is_still_frozen():
    message = Message("tool", "x", tool_call_id="call_1")
    with pytest.raises(AttributeError):
        message.tool_call_id = "call_2"  # type: ignore[misc]


@pytest.mark.parametrize(
    "fields",
    [
        {"tool_calls": [ToolCall("total_revenue")]},  # a list, not a tuple
        {"tool_calls": ("total_revenue",)},  # text, not a ToolCall
    ],
)
def test_tool_calls_must_be_a_tuple_of_tool_calls(fields):
    with pytest.raises(TypeError, match="tool_calls"):
        Message("assistant", "", **fields)


def test_a_tool_call_id_must_be_text():
    with pytest.raises(TypeError, match="tool_call_id"):
        Message("tool", "x", tool_call_id=5)  # type: ignore[arg-type]
