FROM python:3.12-slim

WORKDIR /app

# Dependências de sistema do WeasyPrint (pango/cairo/gdk-pixbuf). A imagem base é
# Debian 13 "trixie", que renomeou libgdk-pixbuf2.0-0 -> libgdk-pixbuf-2.0-0 (validado
# rodando de verdade — o nome antigo não existe mais no repositório).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
    libffi-dev libcairo2 fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
RUN uv sync --no-install-project

COPY . .
RUN uv sync

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
