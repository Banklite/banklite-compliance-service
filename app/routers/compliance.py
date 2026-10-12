import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ReporteRegulatorio, TransaccionSospechosa, Auditoria
from ..schemas import (
    ReporteCreate, ReporteUpdate, ReporteOut,
    SospechosaCreate, SospechosaUpdate, SospechosaOut,
    AuditoriaCreate, AuditoriaOut,
)

router = APIRouter(prefix="/compliance", tags=["Compliance"])


# ── Reportes Regulatorios ────────────────────────────────────────

@router.post("/reportes", response_model=ReporteOut, status_code=status.HTTP_201_CREATED)
def crear_reporte(payload: ReporteCreate, db: Session = Depends(get_db)):
    reporte = ReporteRegulatorio(
        tipo_reporte=payload.tipo_reporte,
        periodo=payload.periodo,
        contenido=payload.contenido,
        generado_por=payload.generado_por,
    )
    db.add(reporte)
    db.commit()
    db.refresh(reporte)
    return reporte


@router.get("/reportes", response_model=List[ReporteOut])
def listar_reportes(
    tipo_reporte: Optional[str] = Query(None),
    estado: Optional[str] = Query(None),
    periodo: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(ReporteRegulatorio)
    if tipo_reporte:
        q = q.filter(ReporteRegulatorio.tipo_reporte == tipo_reporte)
    if estado:
        q = q.filter(ReporteRegulatorio.estado == estado)
    if periodo:
        q = q.filter(ReporteRegulatorio.periodo == periodo)
    return q.order_by(ReporteRegulatorio.fecha_generacion.desc()).all()


@router.get("/reportes/{id_reporte}", response_model=ReporteOut)
def obtener_reporte(id_reporte: uuid.UUID, db: Session = Depends(get_db)):
    reporte = db.query(ReporteRegulatorio).filter(
        ReporteRegulatorio.id_reporte == id_reporte
    ).first()
    if not reporte:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    return reporte


@router.patch("/reportes/{id_reporte}", response_model=ReporteOut)
def actualizar_reporte(id_reporte: uuid.UUID, payload: ReporteUpdate, db: Session = Depends(get_db)):
    reporte = db.query(ReporteRegulatorio).filter(
        ReporteRegulatorio.id_reporte == id_reporte
    ).first()
    if not reporte:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    reporte.estado = payload.estado
    db.commit()
    db.refresh(reporte)
    return reporte


# ── Transacciones Sospechosas ────────────────────────────────────

@router.post("/sospechosas", response_model=SospechosaOut, status_code=status.HTTP_201_CREATED)
def crear_sospechosa(payload: SospechosaCreate, db: Session = Depends(get_db)):
    sospechosa = TransaccionSospechosa(
        id_transferencia=payload.id_transferencia,
        id_cuenta_origen=payload.id_cuenta_origen,
        id_usuario=payload.id_usuario,
        motivo=payload.motivo,
        nivel_riesgo=payload.nivel_riesgo,
        monto=payload.monto,
        id_reporte=payload.id_reporte,
    )
    db.add(sospechosa)
    db.commit()
    db.refresh(sospechosa)
    return sospechosa


@router.get("/sospechosas", response_model=List[SospechosaOut])
def listar_sospechosas(
    estado: Optional[str] = Query(None),
    nivel_riesgo: Optional[str] = Query(None),
    id_usuario: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(TransaccionSospechosa)
    if estado:
        q = q.filter(TransaccionSospechosa.estado == estado)
    if nivel_riesgo:
        q = q.filter(TransaccionSospechosa.nivel_riesgo == nivel_riesgo)
    if id_usuario:
        q = q.filter(TransaccionSospechosa.id_usuario == id_usuario)
    return q.order_by(TransaccionSospechosa.fecha_deteccion.desc()).all()


@router.get("/sospechosas/{id_sospecha}", response_model=SospechosaOut)
def obtener_sospechosa(id_sospecha: uuid.UUID, db: Session = Depends(get_db)):
    sospechosa = db.query(TransaccionSospechosa).filter(
        TransaccionSospechosa.id_sospecha == id_sospecha
    ).first()
    if not sospechosa:
        raise HTTPException(status_code=404, detail="Transaccion sospechosa no encontrada")
    return sospechosa


@router.patch("/sospechosas/{id_sospecha}", response_model=SospechosaOut)
def actualizar_sospechosa(id_sospecha: uuid.UUID, payload: SospechosaUpdate, db: Session = Depends(get_db)):
    sospechosa = db.query(TransaccionSospechosa).filter(
        TransaccionSospechosa.id_sospecha == id_sospecha
    ).first()
    if not sospechosa:
        raise HTTPException(status_code=404, detail="Transaccion sospechosa no encontrada")
    sospechosa.estado = payload.estado
    db.commit()
    db.refresh(sospechosa)
    return sospechosa


# ── Auditorias ───────────────────────────────────────────────────

@router.post("/auditorias", response_model=AuditoriaOut, status_code=status.HTTP_201_CREATED)
def crear_auditoria(payload: AuditoriaCreate, db: Session = Depends(get_db)):
    # Verify the suspicious transaction exists
    sospechosa = db.query(TransaccionSospechosa).filter(
        TransaccionSospechosa.id_sospecha == payload.id_sospecha
    ).first()
    if not sospechosa:
        raise HTTPException(status_code=404, detail="Transaccion sospechosa no encontrada")

    auditoria = Auditoria(
        id_sospecha=payload.id_sospecha,
        auditor=payload.auditor,
        resultado=payload.resultado,
        notas=payload.notas,
    )
    db.add(auditoria)
    db.commit()
    db.refresh(auditoria)
    return auditoria


@router.get("/auditorias", response_model=List[AuditoriaOut])
def listar_auditorias(
    id_sospecha: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Auditoria)
    if id_sospecha:
        q = q.filter(Auditoria.id_sospecha == id_sospecha)
    return q.order_by(Auditoria.fecha_auditoria.desc()).all()
