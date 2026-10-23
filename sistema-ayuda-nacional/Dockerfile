# Nodo Central (FastAPI). Imagen slim: no se compila nada, psycopg2-binary
# y bcrypt vienen con wheels para linux/amd64 y arm64.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Las dependencias primero: cambiar código de la app no reinstala todo.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

# Healthcheck contra el endpoint real (/salud toca la base), no contra el
# puerto: así `docker compose ps` distingue "arriba" de "arriba pero sin base".
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/salud', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
