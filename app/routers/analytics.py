"""Analitica e indicadores para la direccion (solo lectura)."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import ReporteRegulatorio, TransaccionMonitoreada, TransaccionSospechosa

router = APIRouter(prefix="/analytics", tags=["analitica"])


@router.get("/indicadores")
def indicadores(dias: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    """KPIs de cumplimiento de los ultimos N dias: volumen, sospechosas, reportes."""
    desde = datetime.utcnow() - timedelta(days=dias)

    total, volumen = db.query(
        func.count(TransaccionMonitoreada.id_transferencia),
        func.coalesce(func.sum(TransaccionMonitoreada.monto), 0),
    ).filter(TransaccionMonitoreada.fecha_transaccion >= desde).one()

    sospechosas = db.query(TransaccionSospechosa).filter(TransaccionSospechosa.fecha_deteccion >= desde)
    total_sosp = sospechosas.count()

    por_nivel = dict(
        db.query(TransaccionSospechosa.nivel_riesgo, func.count())
        .filter(TransaccionSospechosa.fecha_deteccion >= desde)
        .group_by(TransaccionSospechosa.nivel_riesgo).all()
    )
    por_estado = dict(
        db.query(TransaccionSospechosa.estado, func.count())
        .filter(TransaccionSospechosa.fecha_deteccion >= desde)
        .group_by(TransaccionSospechosa.estado).all()
    )
    reportes = dict(db.query(ReporteRegulatorio.estado, func.count()).group_by(ReporteRegulatorio.estado).all())

    return {
        "periodo_dias": dias,
        "transacciones_monitoreadas": total,
        "volumen_total": float(volumen),
        "sospechosas": total_sosp,
        "tasa_sospecha_pct": round(100 * total_sosp / total, 2) if total else 0.0,
        "sospechosas_por_nivel": por_nivel,
        "sospechosas_por_estado": por_estado,
        "reportes_por_estado": reportes,
        "umbral_aml": settings.aml_umbral_monto,
    }


@router.get("/transacciones-por-dia")
def transacciones_por_dia(dias: int = Query(14, ge=1, le=90), db: Session = Depends(get_db)):
    """Serie diaria (cantidad y monto) para graficar tendencias."""
    desde = datetime.utcnow() - timedelta(days=dias)
    dia = func.date(TransaccionMonitoreada.fecha_transaccion)
    filas = (
        db.query(dia, func.count(), func.coalesce(func.sum(TransaccionMonitoreada.monto), 0))
        .filter(TransaccionMonitoreada.fecha_transaccion >= desde)
        .group_by(dia).order_by(dia).all()
    )
    return [{"fecha": str(f), "cantidad": c, "monto": float(m)} for f, c, m in filas]
