import logging
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import settings
from .database import Base, engine, get_db
from .models import ReporteRegulatorio, TransaccionSospechosa, Auditoria
from .routers import compliance

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(settings.service_name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    logger.info("%s iniciado en puerto %d", settings.service_name, settings.api_port)
    yield


app = FastAPI(
    title="BankLite - Compliance & Analytics Service",
    description="Microservicio de Cumplimiento Regulatorio, Reportes y Auditorias.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(compliance.router)


@app.get("/health", tags=["infra"])
def health():
    return {"status": "ok", "service": settings.service_name}


@app.get("/stats", tags=["infra"])
def stats(db: Session = Depends(get_db)):
    return {
        "total_reportes": db.execute(
            select(func.count()).select_from(ReporteRegulatorio)
        ).scalar(),
        "total_sospechosas": db.execute(
            select(func.count()).select_from(TransaccionSospechosa)
        ).scalar(),
        "sospechosas_pendientes": db.execute(
            select(func.count())
            .select_from(TransaccionSospechosa)
            .where(TransaccionSospechosa.estado == "pendiente")
        ).scalar(),
        "total_auditorias": db.execute(
            select(func.count()).select_from(Auditoria)
        ).scalar(),
    }


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Error no controlado en %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Error interno en Compliance Service"},
    )
