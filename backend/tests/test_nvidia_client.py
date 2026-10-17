from types import SimpleNamespace
import pytest
from app.services import nvidia_client
from app.services.nvidia_client import AnalysisServiceError


class FakeClient:
    def __init__(self, **kwargs):
        self.options = kwargs
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
        self.closed = False

    def create(self, **kwargs):
        self.payload = kwargs
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))])

    def close(self):
        self.closed = True


def test_nvidia_request_validates_structured_response_and_settings(monkeypatch):
    fake = FakeClient()
    fake.content = '{"requirements": [{"name": "Python", "category": "required_skills", "status": "matched", "evidence": "Python in project"}]}'
    monkeypatch.setattr(nvidia_client, "NVIDIA_API_KEY", "test-key")
    monkeypatch.setattr(nvidia_client, "OpenAI", lambda **kwargs: fake)
    result = nvidia_client.analyze_with_nvidia("Python in project", "Need Python for our team")
    assert result.requirements[0].name == "Python"
    assert fake.payload["response_format"] == {"type": "json_object"}
    assert fake.payload["extra_body"]["chat_template_kwargs"]["enable_thinking"] is False
    assert fake.closed


def test_nvidia_missing_key_and_malformed_output_are_safe(monkeypatch):
    monkeypatch.setattr(nvidia_client, "NVIDIA_API_KEY", "")
    with pytest.raises(AnalysisServiceError, match="not configured"):
        nvidia_client.analyze_with_nvidia("resume", "job")
    fake = FakeClient()
    fake.content = "not json"
    monkeypatch.setattr(nvidia_client, "NVIDIA_API_KEY", "test-key")
    monkeypatch.setattr(nvidia_client, "OpenAI", lambda **kwargs: fake)
    with pytest.raises(AnalysisServiceError, match="invalid analysis format"):
        nvidia_client.analyze_with_nvidia("resume", "job")
