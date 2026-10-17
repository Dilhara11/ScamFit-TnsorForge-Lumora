"""Local demonstration API; one synchronous inference lane, no external services."""
import argparse
import json
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

from .model import Runtime
from .monitor import Monitor


def make_handler(runtime, monitor):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send_json(self, code, obj):
            data = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/health":
                return self.send_json(200, {"status": "ready", "model_version": runtime.version, "scope": runtime.config["scope"]})
            if self.path == "/status":
                return self.send_json(200, monitor.status())
            self.send_json(404, {"error": "not_found"})

        def do_POST(self):
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size <= 0 or size > 50000:
                    return self.send_json(413, {"error": "body must be 1..50000 bytes"})
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    raise ValueError("request must be a JSON object")
                if self.path == "/predict":
                    event_id = data.get("event_id", str(uuid.uuid4()))
                    if not isinstance(event_id, str) or not event_id or len(event_id) > 128:
                        raise ValueError("event_id must be a nonempty string, at most 128 characters")
                    result = monitor.process(data.get("text"), event_id)
                    return self.send_json(200, {"event_id": event_id, **result})
                if self.path == "/review":
                    if not isinstance(data.get("actor"), str):
                        raise ValueError("actor must be a string")
                    return self.send_json(200, monitor.review(int(data["cluster_id"]), data["status"], data["actor"]))
                self.send_json(404, {"error": "not_found"})
            except (ValueError, KeyError, TypeError, UnicodeDecodeError) as exc:
                self.send_json(400, {"error": str(exc)})
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--db", default="training/runs/service.sqlite")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    runtime = Runtime(args.bundle)
    runtime.predict("Service startup check.")
    monitor = Monitor(runtime, args.db)
    server = HTTPServer((args.host, args.port), make_handler(runtime, monitor))
    print(json.dumps({"url": f"http://{args.host}:{args.port}", "version": runtime.version}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        monitor.close()


if __name__ == "__main__":
    main()
