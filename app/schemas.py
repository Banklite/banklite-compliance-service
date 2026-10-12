from uuid import UUID
from datetime import datetime
from typing import Optional, Literal, List
from pydantic import BaseModel, Field


# ── Reporte Regulatorio ──────────────────────────────────────────

class ReporteCreate(BaseModel):
    tipo_reporte: str = Field(..., min_length=1, max_length=50)
    periodo: str = Field(..., min_length=1, max_length=30)
    contenido: Optional[str] = None
    generado_por: Optional[UUID] = None


class ReporteUpdate(BaseModel):
    estado: Literal["borrador", "enviado", "aceptado", "rechazado"]


class ReporteOut(BaseModel):
    id_reporte: UUID
    tipo_reporte: str
    periodo: str
    fecha_generacion: datetime
    estado: str
    contenido: Optional[str] = None
    generado_por: Optional[UUID] = None

    class Config:
        from_attributes = True


# ── Transaccion Sospechosa ───────────────────────────────────────

class SospechosaCreate(BaseModel):
    id_transferencia: UUID
    id_cuenta_origen: UUID
    id_usuario: UUID
    motivo: str = Field(..., min_length=1, max_length=255)
    nivel_riesgo: Literal["bajo", "medio", "alto", "critico"]
    monto: Optional[float] = None
    id_reporte: Optional[UUID] = None


class SospechosaUpdate(BaseModel):
    estado: Literal["pendiente", "investigando", "descartada", "confirmada", "reportada"]


class SospechosaOut(BaseModel):
    id_sospecha: UUID
    id_transferencia: UUID
    id_cuenta_origen: UUID
    id_usuario: UUID
    motivo: str
    nivel_riesgo: str
    monto: Optional[float] = None
    fecha_deteccion: datetime
    id_reporte: Optional[UUID] = None
    estado: str

    class Config:
        from_attributes = True


# ── Auditoria ────────────────────────────────────────────────────

class AuditoriaCreate(BaseModel):
    id_sospecha: UUID
    auditor: Optional[str] = Field(None, max_length=150)
    resultado: Literal["limpia", "sospechosa", "confirmada_fraude"]
    notas: Optional[str] = None


class AuditoriaOut(BaseModel):
    id_auditoria: UUID
    id_sospecha: UUID
    auditor: Optional[str] = None
    resultado: str
    notas: Optional[str] = None
    fecha_auditoria: datetime

    class Config:
        from_attributes = True
