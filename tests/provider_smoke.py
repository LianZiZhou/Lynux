#!/usr/bin/env python3
"""Exercise installed harnesses against a loopback-only mock model, with disposable credentials.

Run in a container with --network none (loopback remains available). No model account is used.
"""
import argparse
import gzip
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import threading
import time
import uuid

ANSWER = "LYNUX_PROVIDER_OK"
PROMPT = "Reply with one short acknowledgement. Do not use any tools."
KEY = "sk-" + "0" * 48


class Model(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send(self, body, content_type="application/json"):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.send_header("request-id", "lynux-mock")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.send({"object": "list", "data": [{"id": "gpt-5.4", "object": "model", "owned_by": "lynux"}]})

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        if self.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        elif self.headers.get("Content-Encoding") == "zstd":
            raw = subprocess.check_output(["zstd", "-dc"], input=raw)
        request = json.loads(raw or b"{}")
        if self.path.endswith("/count_tokens"):
            return self.send({"input_tokens": 10})
        self.server.calls.append({"path": self.path, "model": request.get("model")})
        ident = uuid.uuid4().hex
        model = request.get("model", "gpt-5.4")
        events = []
        if "messages" in self.path:
            message = {"id": "msg_" + ident, "type": "message", "role": "assistant", "model": model,
                       "content": [{"type": "text", "text": ANSWER}], "stop_reason": "end_turn",
                       "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 4}}
            if not request.get("stream"):
                return self.send(message)
            events = [
                {"type": "message_start", "message": {**message, "content": [], "stop_reason": None}},
                {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
                {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": ANSWER}},
                {"type": "content_block_stop", "index": 0},
                {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                 "usage": {"output_tokens": 4}}, {"type": "message_stop"}]
        elif "responses" in self.path:
            item = {"id": "msg_" + ident, "type": "message", "role": "assistant", "status": "completed",
                    "content": [{"type": "output_text", "text": ANSWER, "annotations": []}]}
            response = {"id": "resp_" + ident, "object": "response", "created_at": int(time.time()),
                        "model": model, "status": "completed", "error": None, "incomplete_details": None,
                        "output": [item], "usage": {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14,
                            "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}}}
            if not request.get("stream"):
                return self.send(response)
            events = [
                {"type": "response.created", "response": {**response, "status": "in_progress", "output": []}},
                {"type": "response.output_item.added", "output_index": 0,
                 "item": {**item, "status": "in_progress", "content": []}},
                {"type": "response.content_part.added", "item_id": item["id"], "output_index": 0,
                 "content_index": 0, "part": {"type": "output_text", "text": "", "annotations": []}},
                {"type": "response.output_text.delta", "item_id": item["id"], "output_index": 0,
                 "content_index": 0, "delta": ANSWER},
                {"type": "response.output_text.done", "item_id": item["id"], "output_index": 0,
                 "content_index": 0, "text": ANSWER},
                {"type": "response.content_part.done", "item_id": item["id"], "output_index": 0,
                 "content_index": 0, "part": item["content"][0]},
                {"type": "response.output_item.done", "output_index": 0, "item": item},
                {"type": "response.completed", "response": response}]
            for index, event in enumerate(events):
                event["sequence_number"] = index
        elif "chat/completions" in self.path:
            common = {"id": "chatcmpl_" + ident, "created": int(time.time()), "model": model}
            if not request.get("stream"):
                return self.send({**common, "object": "chat.completion", "choices": [{"index": 0,
                    "message": {"role": "assistant", "content": ANSWER}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14}})
            chunks = [{**common, "object": "chat.completion.chunk", "choices": [{"index": 0,
                       "delta": {"role": "assistant", "content": ANSWER}, "finish_reason": None}]},
                      {**common, "object": "chat.completion.chunk", "choices": [{"index": 0,
                       "delta": {}, "finish_reason": "stop"}],
                       "usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14}}]
            return self.send(("".join("data: " + json.dumps(c) + "\n\n" for c in chunks) + "data: [DONE]\n\n").encode(),
                             "text/event-stream")
        else:
            return self.send({})
        body = "".join(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events)
        self.send(body.encode(), "text/event-stream")


def prepare(tool, home, url):
    env = {**os.environ, "HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config"),
           "XDG_DATA_HOME": str(home / ".local/share"), "XDG_STATE_HOME": str(home / ".local/state"),
           "XDG_CACHE_HOME": str(home / ".cache"), "TERM": "xterm-256color", "NO_PROXY": "127.0.0.1,localhost",
           "HTTP_PROXY": "", "HTTPS_PROXY": "", "ALL_PROXY": "", "DISABLE_AUTOUPDATER": "1",
           "LYNUX_TEST_KEY": KEY, "OPENAI_API_KEY": KEY, "ANTHROPIC_API_KEY": KEY, "DEEPSEEK_API_KEY": KEY,
           "ANTHROPIC_BASE_URL": url, "DEEPSEEK_BASE_URL": url, "DSH_TELEMETRY_MODE": "DISABLED",
           "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}
    home.mkdir(parents=True)
    if tool == "codex":
        env["CODEX_HOME"] = str(home / ".codex")
        (home / ".codex").mkdir()
        provider = f'model_providers.lynux={{name="Lynux mock",base_url="{url}/v1",wire_api="responses",env_key="LYNUX_TEST_KEY"}}'
        return ["exec", "--skip-git-repo-check", "--json", "--model", "gpt-5.4", "-c", 'model_provider="lynux"',
                "-c", provider, PROMPT], env
    if tool == "claude":
        return ["-p", "--output-format", "json", PROMPT], env
    if tool == "kimi":
        env["KIMI_CODE_HOME"] = str(home / ".kimi-code")
        directory = home / ".kimi-code"
        directory.mkdir()
        (directory / "config.toml").write_text(f'''default_model = "mock"
telemetry = false
auto_session_title = false
[providers.mock]
type = "openai"
base_url = "{url}/v1"
api_key_env = "LYNUX_TEST_KEY"
[models.mock]
provider = "mock"
model = "gpt-5.4"
max_context_size = 131072
capabilities = ["tool_use"]
''')
        return ["-p", PROMPT], env
    if tool == "dsh":
        env["DSH_HOME"] = str(home / ".dsh")
        return ["--profile", "headless", PROMPT], env
    env["OPENCODE_CONFIG_CONTENT"] = json.dumps({"provider": {"openai": {"options": {
        "baseURL": url + "/v1", "apiKey": KEY}}}})
    return ["--standalone", "run", "--model", "openai/gpt-5.4", "--format", "json", PROMPT], env


def smoke(prefix, report, selected):
    if any(name != "lo" for _, name in socket.if_nameindex()):
        raise RuntimeError("Run this test in --network none or an isolated network namespace with only loopback")
    results = {}
    with tempfile.TemporaryDirectory(prefix="lynux-provider-", dir="/var/tmp") as directory, ThreadingHTTPServer(("127.0.0.1", 0), Model) as server:
        server.calls = []
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{server.server_port}"
        root = Path(directory)
        workspace = root / "workspace"
        workspace.mkdir()
        (workspace / "README.md").write_text("Isolated Lynux packaging smoke test.\n")
        try:
            for tool in selected:
                args, env = prepare(tool, root / tool, url)
                before = len(server.calls)
                process = subprocess.Popen([str(prefix / tool / "bin" / tool), *args], cwd=workspace, env=env,
                                           text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
                try:
                    stdout, stderr = process.communicate(timeout=90)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    stdout, stderr = process.communicate()
                calls = server.calls[before:]
                passed = process.returncode == 0 and ANSWER in stdout and bool(calls)
                results[tool] = {"passed": passed, "exit_code": process.returncode, "requests": calls,
                                 "stdout_tail": stdout[-2500:], "stderr_tail": stderr[-2500:]}
                print(f"{tool}: {'PASS' if passed else 'FAIL'}", flush=True)
        finally:
            server.shutdown()
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"schema": 1, "mock_only": True, "results": results}, ensure_ascii=False, indent=2))
    if not all(item["passed"] for item in results.values()):
        raise RuntimeError(f"Provider smoke failure; see {report}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", type=Path, default=Path("/opt/lynux/harnesses"))
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--tools", nargs="+", choices=["codex", "claude", "kimi", "dsh", "opencode"],
                        default=["codex", "claude", "kimi", "dsh", "opencode"])
    args = parser.parse_args()
    smoke(args.prefix, args.report, args.tools)
