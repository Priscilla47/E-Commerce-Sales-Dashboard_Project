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
