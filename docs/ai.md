# AI features

This page explains how the AI features are built and how to switch them on. The project works without them: with no key set, every other feature behaves as before. For where the code lives and what it may import, see the [architecture](architecture.md).

## Principles

1. **Numbers come from pandas.** Every figure shown to a reader is computed by the `analytics` package. A language model never calculates, estimates or invents a figure; it only receives figures that were already computed and turns them into words.
2. **The model is a replaceable part.** The features talk to a small interface (`LLMClient`), never to a provider. Choosing or changing the provider touches one place, not the features.
3. **Tests never call a service.** They use `FakeLLM`, which answers from a script and records what it was asked.
4. **Nothing secret leaks.** The key is read from an environment variable, is hidden in `repr()` and `str()` of the configuration, and is removed from every error message.
5. **Off by default.** Without a key the AI features are switched off, and the rest of the project does not change.

The forecast of revenue (see the next pages of this guide) is a statistical model and needs no language model: it works with the AI switched off.

## The interface

`sales_insights.ai.llm` defines what a client must offer:

```python
from sales_insights.ai.llm import Message

reply = client.complete([Message("user", "Which country sold the most?")])
print(reply.text)  # the answer
print(reply.tool_calls)  # functions the model asks for, none here
```

- `Message(role, content)`: `role` is `system`, `user`, `assistant` or `tool`.
- `Completion(text, tool_calls=())`: what came back. A `ToolCall` has a `name` and its `arguments`.
- `LLMError`: a call failed, timed out, or went over the limit of the session.

## Switching the AI on or off

The settings are read from four environment variables. Copy [`.env.example`](../.env.example) to `.env` and fill it in; `.env` is ignored by git.

| Variable | Meaning | Default |
|----------|---------|---------|
| `SALES_AI_PROVIDER` | The provider to use. | none |
| `SALES_AI_MODEL` | The model of that provider. | none |
| `SALES_AI_API_KEY` | The secret key. Empty means off. | none |
| `SALES_AI_MAX_CALLS` | The most calls one session may make, 1 to 10000. | 20 |

`load_config(os.environ)` reads them. `config.enabled` is `False` when there is no key or no provider, and `build_client(config)` then raises `AIDisabled` with a message that names the variable to set:

```text
The AI features are switched off. Set SALES_AI_API_KEY to switch them on.
```

A bad `SALES_AI_MAX_CALLS` raises `ConfigError`, which names the variable and never shows the key.

## Provider names

Decision: **no provider is named in the code, the tests or the documentation of the project.** The configuration holds only the name a user writes in `SALES_AI_PROVIDER`; a provider is added by registering a function that builds its client (`register_provider(name, factory)`), kept outside the features. The reasons: the features stay independent of any one company, the code keeps working if the provider changes, and the examples cannot go out of date. A test checks that no well-known provider name appears in the `ai` package, this page or `.env.example`.

## Limits of a session

`build_client` wraps the client so that one session cannot make more than `SALES_AI_MAX_CALLS` calls. A call over the limit is refused without reaching the provider, and a call that fails still counts, so that a loop of failing calls ends. The error messages that leave the wrapper have the key replaced by `***`.

## Testing with the fake client

```python
from sales_insights.ai.fake import FakeLLM
from sales_insights.ai.llm import Message

fake = FakeLLM(["Paris", "London"])
fake.complete([Message("user", "first")]).text  # 'Paris'
fake.complete([Message("user", "second")]).text  # 'London'
fake.calls[0].messages  # what the first call received
```

A third call raises `LLMError` that says how many answers were scripted. An item of the script can also be an exception, raised in its turn, to test a failing provider.
