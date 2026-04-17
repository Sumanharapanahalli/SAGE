import pytest

from handlers import llm
from rpc import RpcError


class FakeProvider:
    model = "gemini-2.0-flash-001"


class FakeGateway:
    def __init__(self, cls_name="GeminiCLIProvider"):
        self._cls = cls_name
        self.provider = FakeProvider()

    def get_provider_name(self) -> str:
        return self._cls

    def list_providers(self) -> list[str]:
        return ["gemini", "claude-code", "ollama", "local", "claude", "generic-cli"]


@pytest.fixture(autouse=True)
def reset():
    llm._gateway = None
    yield
    llm._gateway = None


def test_get_llm_info_returns_shape():
    llm._gateway = FakeGateway()
    result = llm.get_llm_info({})
    assert result["provider_name"] == "GeminiCLIProvider"
    assert result["model"] == "gemini-2.0-flash-001"
    assert "claude-code" in result["available_providers"]


def test_get_llm_info_when_gateway_missing_raises_sage_import_error():
    with pytest.raises(RpcError) as exc:
        llm.get_llm_info({})
    assert exc.value.code == -32010


def test_switch_llm_rejects_empty_provider():
    llm._gateway = FakeGateway()
    with pytest.raises(RpcError) as exc:
        llm.switch_llm({"provider": ""})
    assert exc.value.code == -32602


def test_switch_llm_invokes_executor(monkeypatch):
    llm._gateway = FakeGateway()
    calls = []

    async def fake_execute(proposal):
        calls.append(proposal.payload)
        return {
            "provider": proposal.payload["provider"],
            "provider_name": "OllamaProvider",
            "saved_as_default": proposal.payload.get("save_as_default", False),
        }

    monkeypatch.setattr(llm, "_run_execute_llm_switch", fake_execute)
    result = llm.switch_llm(
        {"provider": "ollama", "model": "llama3.2", "save_as_default": True}
    )
    assert result["provider"] == "ollama"
    assert result["provider_name"] == "OllamaProvider"
    assert result["saved_as_default"] is True
    assert calls[0]["provider"] == "ollama"
    assert calls[0]["model"] == "llama3.2"


def test_switch_llm_wraps_executor_exception(monkeypatch):
    llm._gateway = FakeGateway()

    async def boom(proposal):
        raise RuntimeError("disk full")

    monkeypatch.setattr(llm, "_run_execute_llm_switch", boom)
    with pytest.raises(RpcError) as exc:
        llm.switch_llm({"provider": "ollama"})
    assert exc.value.code == -32000
    assert "disk full" in exc.value.message
