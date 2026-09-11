from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse

from app.api.dependencies import check_metadata_db, get_pipeline_graph
from app.api.schemas import ChatRequest, ExportRequest
from app.api.streaming import stream_pipeline
from app.database.connection import get_metadata_session
from app.export.docx_generator import generate_docx
from app.export.pdf_generator import generate_pdf
from app.export.storage import cleanup_old_exports
from app.metadata.connections import ConnectionNotFoundError, get_connection

router = APIRouter(prefix="/api")

_EXPORT_CONTENT_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}


async def resolve_connection_dialect(connection_id: Any) -> str:
    """Descobre o dialeto da conexão-alvo. Isolado numa função para ser overridable em testes."""
    async with get_metadata_session() as session:
        connection = await get_connection(session, connection_id)
        return connection.db_type


@router.post("/chat")
async def chat(request: ChatRequest, graph: Annotated[Any, Depends(get_pipeline_graph)]) -> StreamingResponse:
    """Recebe uma pergunta + connection_id, roda o pipeline e retorna um stream SSE."""
    try:
        dialect = await resolve_connection_dialect(request.connection_id)
    except ConnectionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return StreamingResponse(
        stream_pipeline(
            request.question, graph, connection_id=str(request.connection_id), dialect=dialect
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/health")
async def health(
    metadata_db_ok: Annotated[bool, Depends(check_metadata_db)],
) -> dict[str, Any]:
    """Retorna status dos serviços (backend, metadata-db).

    O banco do usuário não tem mais healthcheck global — cada conexão é testável
    individualmente via POST /api/connections/{id}/test.
    """
    return {"backend": True, "metadata_db": metadata_db_ok}


@router.post("/export")
async def export_report(request: ExportRequest, background_tasks: BackgroundTasks) -> FileResponse:
    """Gera e retorna um relatório .docx ou .pdf para download."""
    if request.format == "docx":
        output_path = await generate_docx(
            question=request.question,
            response_text=request.response_text,
            sql=request.sql,
            columns=request.columns,
            rows=request.rows,
            metadata=request.metadata,
            column_formats=request.column_formats,
        )
    else:
        output_path = await generate_pdf(
            question=request.question,
            response_text=request.response_text,
            sql=request.sql,
            columns=request.columns,
            rows=request.rows,
            metadata=request.metadata,
            column_formats=request.column_formats,
            chart_spec=request.chart_spec,
        )

    # Starlette roda BackgroundTasks (síncronas, via threadpool) depois da resposta já
    # ter sido enviada ao cliente — não atrasa o download atual.
    background_tasks.add_task(cleanup_old_exports)

    return FileResponse(
        path=output_path,
        filename=output_path.name,
        media_type=_EXPORT_CONTENT_TYPES[request.format],
    )
