"""Streaming chat: same reply as the non-streamed call, reported while it is written (mock Ollama, no GPU)."""
import json

import httpx

from kkh.llm.ollama import Ollama


def _client(chunks):
    def handler(request: httpx.Request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "m:1b"}]})
        body = json.loads(request.content)
        if not body["stream"]:
            return httpx.Response(200, json={"model": "m:1b", "done": True, "done_reason": "stop",
                                             "message": {"content": "".join(chunks)}, "eval_count": len(chunks)})
        lines = [json.dumps({"message": {"content": c}, "done": False}) for c in chunks]
        lines.append(json.dumps({"model": "m:1b", "message": {"content": ""}, "done": True, "done_reason": "length",
                                 "eval_count": len(chunks)}))
        return httpx.Response(200, content="\n".join(lines).encode())

    c = Ollama()
    c.http = httpx.Client(transport=httpx.MockTransport(handler))
    return c


def test_stream_matches_plain_reply_and_reports_progress():
    chunks = [f"tok{i} " for i in range(45)]
    seen = []
    c = _client(chunks)
    streamed = c.chat([{"role": "user", "content": "x"}], model="m:1b", allow_truncated=True,
                      on_token=lambda text, n: seen.append((text, n)))
    plain = c.chat([{"role": "user", "content": "x"}], model="m:1b")
    assert streamed["content"] == plain["content"] == "".join(chunks)
    assert streamed["truncated"] is True and streamed["metrics"]["eval_count"] == 45
    assert [n for _, n in seen][:3] == [1, 2, 3] and seen[-1] == ("".join(chunks), 45)
    assert any(t is not None for t, _ in seen[:-1])  # partial text is reported before the end
