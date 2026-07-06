from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from json import dumps

from documind_ai.config import AppSettings, load_settings
from documind_ai.health import build_health_response


def create_handler(settings: AppSettings) -> type[BaseHTTPRequestHandler]:
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != "/health":
                self.send_json(HTTPStatus.NOT_FOUND, {"message": "Not Found"})
                return

            self.send_json(HTTPStatus.OK, build_health_response(settings))

        def send_json(self, status: HTTPStatus, body: dict[str, str]) -> None:
            payload = dumps(body, ensure_ascii=False).encode("utf-8")

            self.send_response(status.value)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            return

    return HealthHandler


def main() -> None:
    settings = load_settings()
    server = ThreadingHTTPServer((settings.host, settings.port), create_handler(settings))
    print(f"{settings.service_name} listening on {settings.host}:{settings.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
