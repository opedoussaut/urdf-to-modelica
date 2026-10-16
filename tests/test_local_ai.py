import json

import httpx
import pytest

from kkh.llm.ollama import Ollama
from kkh.rag.copilot import validate_answer, attach_citations
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


def test_citations_and_axis_contradiction():
    evidence = [{"id": "E1", "property": "axis", "value": "0,1,0", "axis_basis_derived": "positive Y in the URDF joint frame"}]
    answer = {"answer": "The axis is Y-axis [E1].", "citations": ["E1"], "proposed_change": ""}
    validate_answer(answer, evidence)
    with pytest.raises(ValueError, match="contradicts"):
        validate_answer({**answer, "answer": "The axis is X-axis [E1]."}, evidence)
    with pytest.raises(ValueError):
        validate_answer({**answer, "citations": ["E404"]}, evidence)
    with pytest.raises(ValueError):
        validate_answer({**answer, "answer": "Uncited content"}, evidence)


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


def test_missing_inline_citations_render_only_declared_valid_ids():
    evidence = [{"id": "E1"}]
    answer = {"answer": "Source-backed explanation.", "citations": ["E1"], "proposed_change": ""}
    validate_answer(attach_citations(answer, evidence), evidence)
    with pytest.raises(ValueError):
        validate_answer(attach_citations({**answer, "citations": ["E404"]}, evidence), evidence)
    normalized = attach_citations({**answer, "answer": "See E1 for the axis."}, evidence)
    assert "[E1]" in normalized["answer"]
    with pytest.raises(ValueError):
        validate_answer(attach_citations({**answer, "answer": "See E404. [E1]"}, evidence), evidence)


@pytest.mark.ollama
def test_real_local_copilot():
    from kkh.rag.copilot import ask
    output = ask("What is the right elbow joint axis? Cite the URDF source.")
    assert output["read_only"]
    assert output["citations"]
    assert all(e["backend"] in {"graphdb", "local-rdflib-owlrl"} for e in output["evidence"])
