import json

import httpx
import pytest

from kkh.llm.ollama import Ollama
from kkh.benchmark.harness import TASKS, apply_proposal, expected, extract_value
from kkh.domain.aloha.configuration import ROOT


@pytest.mark.parametrize("url", ["https://api.openai.com", "https://localhost:11434", "http://example.com", "http://user:pass@localhost:11434"])
def test_ai_transport_requires_loopback(url):
    with pytest.raises(ValueError):
        Ollama(url=url)


def test_ollama_never_downloads_or_uses_cloud_models():
    client = Ollama()
    def handle(request):
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": "qwen3:4b"}, {"name": "remote:cloud"}]})
    client.http.close()
    client.http = httpx.Client(transport=httpx.MockTransport(handle))
    assert [m["name"] for m in client.models()] == ["qwen3:4b"]
    with pytest.raises(ValueError):
        client.chat([], model="remote:cloud")
    with pytest.raises(ValueError):
        client.chat([], model="uninstalled:latest")
    client.close()


def test_numeric_proposals_cannot_inject_code():
    with pytest.raises((ValueError, TypeError)):
        extract_value(TASKS[1], '{"value":"system(\"evil\")"}')
    with pytest.raises(ValueError):
        extract_value(TASKS[1], '{"value":NaN}')
    with pytest.raises(ValueError):
        extract_value(TASKS[0], '{"axis":[0,1]}')
    source = (ROOT / "generated/modelica/ALOHA2/Arms/AlohaVX300s.mo").read_text()
    for task in TASKS:
        patched = apply_proposal(source, task, expected(task))
        assert "end AlohaVX300s;" in patched
        if task["id"] == "repair-finger-mimic":
            assert "j_right_finger.qd = -1.0 * qd[8]" in patched


