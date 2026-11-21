from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
from core.runner import build_simulation_trace


class SimulatorHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="web", **kwargs)

    def do_POST(self):
        if self.path == "/api/simulate":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                trace = build_simulation_trace(data.get("script", ""))
                response = json.dumps(trace).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(response)
            except Exception as exc:
                err = json.dumps({"error": str(exc)}).encode("utf-8")
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(err)
        else:
            self.send_error(404)


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 8000), SimulatorHandler)
    print("Simulador Visual rodando em: http://127.0.0.1:8000")
    server.serve_forever()