from __future__ import annotations

from flask import Flask, jsonify

from core.settings import settings

app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "assistant": settings.assistant_name,
        "local_only": settings.local_only,
    })


def servir() -> None:
    """Sobe o painel só em loopback enquanto o modo local estiver ligado."""
    host = "127.0.0.1" if settings.local_only else settings.api_host
    app.run(host=host, port=settings.api_port, debug=False, use_reloader=False)


if __name__ == "__main__":
    servir()
