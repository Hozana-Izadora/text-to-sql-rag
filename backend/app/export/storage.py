import tempfile
import time
from pathlib import Path
from typing import Literal

from app.core.logging import get_logger

logger = get_logger(__name__)

# Não hardcoda "/tmp/exports" — CLAUDE.md documenta rodar o backend fora do Docker via
# `uv run uvicorn` como fluxo de dev válido, e "/tmp" não existe no Windows.
EXPORT_DIR = Path(tempfile.gettempdir()) / "inquiro_exports"
_MAX_AGE_SECONDS = 3600


def ensure_export_dir() -> Path:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    return EXPORT_DIR


def export_filename(kind: Literal["docx", "pdf"]) -> Path:
    ensure_export_dir()
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    return EXPORT_DIR / f"relatorio_{timestamp}.{kind}"


def cleanup_old_exports() -> None:
    """Apaga arquivos em EXPORT_DIR com mais de 1 hora.

    Síncrona de propósito — chamada via BackgroundTasks.add_task(), que o Starlette já
    roda em threadpool automaticamente (não bloqueia o event loop) e só depois da
    resposta (download atual) já ter sido enviada ao cliente.
    """
    if not EXPORT_DIR.exists():
        return
    cutoff = time.time() - _MAX_AGE_SECONDS
    for path in EXPORT_DIR.iterdir():
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError as exc:
            logger.warning("export_cleanup_failed", path=str(path), error=str(exc))
