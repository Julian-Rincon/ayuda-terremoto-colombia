import json

from fastapi import WebSocket


class ConnectionManager:
    """Broadcast simple para dashboards en tiempo real."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, tipo: str, data: dict):
        mensaje = json.dumps({"tipo": tipo, "data": data}, default=str)
        vivos = []
        for connection in self.active_connections:
            try:
                await connection.send_text(mensaje)
                vivos.append(connection)
            except Exception:
                pass
        self.active_connections = vivos


manager = ConnectionManager()
