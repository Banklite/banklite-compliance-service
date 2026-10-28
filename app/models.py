import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Numeric, DateTime, ForeignKey, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base


class ReporteRegulatorio(Base):
    __tablename__ = "reporte_regulatorio"

    id_reporte = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tipo_reporte = Column(String(50), nullable=False)
    periodo = Column(String(30), nullable=False)
    fecha_generacion = Column(DateTime, server_default=func.now(), nullable=False)
    estado = Column(String(20), nullable=False, default="borrador")
    contenido = Column(Text, nullable=True)
    generado_por = Column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "estado IN ('borrador', 'enviado', 'aceptado', 'rechazado')",
            name="chk_reporte_estado",
        ),
    )

    sospechosas = relationship("TransaccionSospechosa", back_populates="reporte")


class TransaccionSospechosa(Base):
    __tablename__ = "transaccion_sospechosa"

    id_sospecha = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_transferencia = Column(UUID(as_uuid=True), nullable=False)
    id_cuenta_origen = Column(UUID(as_uuid=True), nullable=False)
    id_usuario = Column(UUID(as_uuid=True), nullable=False)
    motivo = Column(String(255), nullable=False)
    nivel_riesgo = Column(String(20), nullable=False)
    monto = Column(Numeric(14, 2), nullable=True)
    fecha_deteccion = Column(DateTime, server_default=func.now(), nullable=False)
    id_reporte = Column(
        UUID(as_uuid=True),
        ForeignKey("reporte_regulatorio.id_reporte"),
        nullable=True,
    )
    estado = Column(String(20), nullable=False, default="pendiente")

    __table_args__ = (
        CheckConstraint(
            "nivel_riesgo IN ('bajo', 'medio', 'alto', 'critico')",
            name="chk_sospechosa_nivel_riesgo",
        ),
        CheckConstraint(
            "estado IN ('pendiente', 'investigando', 'descartada', 'confirmada', 'reportada')",
            name="chk_sospechosa_estado",
        ),
        Index("idx_sospechosa_usuario", "id_usuario"),
        Index("idx_sospechosa_transferencia", "id_transferencia"),
    )

    reporte = relationship("ReporteRegulatorio", back_populates="sospechosas")
    auditorias = relationship("Auditoria", back_populates="sospechosa", cascade="all, delete-orphan")


class Auditoria(Base):
    __tablename__ = "auditoria"

    id_auditoria = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_sospecha = Column(
        UUID(as_uuid=True),
        ForeignKey("transaccion_sospechosa.id_sospecha"),
        nullable=False,
    )
    auditor = Column(String(150), nullable=True)
    resultado = Column(String(30), nullable=False)
    notas = Column(Text, nullable=True)
    fecha_auditoria = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "resultado IN ('limpia', 'sospechosa', 'confirmada_fraude')",
            name="chk_auditoria_resultado",
        ),
        Index("idx_auditoria_sospecha", "id_sospecha"),
    )

    sospechosa = relationship("TransaccionSospechosa", back_populates="auditorias")


class TransaccionMonitoreada(Base):
    """Copia de solo lectura de cada transferencia completada (llega por el evento
    transfer.completed). Es la base de los indicadores y del monitoreo AML, sin
    consultar la base del Ledger."""

    __tablename__ = "transaccion_monitoreada"

    id_transferencia = Column(UUID(as_uuid=True), primary_key=True)
    id_cuenta_origen = Column(UUID(as_uuid=True), nullable=False)
    monto = Column(Numeric(14, 2), nullable=False)
    fecha_transaccion = Column(DateTime, server_default=func.now(), nullable=False)
    marcada = Column(String(5), nullable=False, default="no")

    __table_args__ = (Index("idx_monitoreada_fecha", "fecha_transaccion"),)
