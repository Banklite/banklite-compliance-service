"""Consumidor de eventos de compliance-service (comunicacion ASINCRONA).

  - transfer.completed -> guarda la transaccion para analitica y aplica la regla AML por monto
  - fraud.alert        -> registra la transaccion como sospechosa para revision regulatoria
"""

import json
import logging
import threading
import time
import uuid
from datetime import datetime

import httpx
import pika

from .config import settings
from .database import SessionLocal
from .models import TransaccionMonitoreada, TransaccionSospechosa

logger = logging.getLogger(__name__)

EVENT_TRANSFER_COMPLETED = "transfer.completed"
EVENT_FRAUD_ALERT = "fraud.alert"
_stop = threading.Event()

# prioridad del servicio de fraude -> nivel de riesgo de cumplimiento
_NIVEL = {"alta": "alto", "media": "medio", "baja": "bajo"}


def _usuario_de_cuenta(id_cuenta: str | None) -> uuid.UUID | None:
    if not id_cuenta:
        return None
    try:
        r = httpx.get(f"{settings.account_service_url}/accounts/{id_cuenta}", timeout=5.0)
        if r.status_code == 200 and r.json().get("id_usuario"):
            return uuid.UUID(r.json()["id_usuario"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo resolver el titular de la cuenta %s: %s", id_cuenta, exc)
    return None


def _registrar_sospechosa(db, *, id_transferencia, id_cuenta, monto, motivo, nivel) -> None:
    existe = db.query(TransaccionSospechosa).filter(
        TransaccionSospechosa.id_transferencia == id_transferencia,
        TransaccionSospechosa.motivo == motivo,
    ).first()
    if existe:  # el evento puede llegar repetido: idempotencia
        return
    id_usuario = _usuario_de_cuenta(id_cuenta)
    if id_usuario is None:
        logger.warning("Sospechosa %s sin titular resoluble; se omite", id_transferencia)
        return
    db.add(TransaccionSospechosa(
        id_transferencia=id_transferencia,
        id_cuenta_origen=uuid.UUID(id_cuenta),
        id_usuario=id_usuario,
        motivo=motivo,
        nivel_riesgo=nivel,
        monto=monto,
    ))


def _on_transfer_completed(p: dict) -> None:
    id_transferencia = uuid.UUID(p["id_transferencia"])
    monto = float(p["monto"])
    db = SessionLocal()
    try:
        if not db.get(TransaccionMonitoreada, id_transferencia):
            fecha = datetime.fromisoformat(p["fecha_solicitud"]).replace(tzinfo=None) if p.get("fecha_solicitud") else None
            marcada = monto >= settings.aml_umbral_monto
            db.add(TransaccionMonitoreada(
                id_transferencia=id_transferencia,
                id_cuenta_origen=uuid.UUID(p["id_cuenta_origen"]),
                monto=monto,
                fecha_transaccion=fecha or datetime.utcnow(),
                marcada="si" if marcada else "no",
            ))
            if marcada:
                _registrar_sospechosa(
                    db,
                    id_transferencia=id_transferencia,
                    id_cuenta=p["id_cuenta_origen"],
                    monto=monto,
                    motivo=f"AML: monto supera el umbral de {settings.aml_umbral_monto:,.0f}",
                    nivel="medio",
                )
            db.commit()
    finally:
        db.close()


def _on_fraud_alert(p: dict) -> None:
    db = SessionLocal()
    try:
        _registrar_sospechosa(
            db,
            id_transferencia=uuid.UUID(p["id_transaccion"]),
            id_cuenta=p.get("id_cuenta"),
            monto=p.get("monto"),
            motivo=f"Alerta de fraude (score {p.get('score_riesgo')}, {p.get('resultado')})",
            nivel=_NIVEL.get(p.get("prioridad"), "medio"),
        )
        db.commit()
    finally:
        db.close()


_HANDLERS = {EVENT_TRANSFER_COMPLETED: _on_transfer_completed, EVENT_FRAUD_ALERT: _on_fraud_alert}


def _worker() -> None:
    while not _stop.is_set():
        connection = None
        try:
            connection = pika.BlockingConnection(pika.URLParameters(settings.rabbitmq_url))
            channel = connection.channel()
            channel.exchange_declare(exchange=settings.events_exchange, exchange_type="topic", durable=True)
            channel.queue_declare(queue=settings.events_queue, durable=True)
            for rk in _HANDLERS:
                channel.queue_bind(queue=settings.events_queue, exchange=settings.events_exchange, routing_key=rk)

            def callback(ch, method, properties, body):
                try:
                    _HANDLERS[method.routing_key](json.loads(body.decode("utf-8")))
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Error procesando %s: %s", method.routing_key, exc)
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            channel.basic_qos(prefetch_count=10)
            channel.basic_consume(queue=settings.events_queue, on_message_callback=callback)
            logger.info("Compliance consumer escuchando %s", ", ".join(_HANDLERS))
            while not _stop.is_set() and channel.is_open:
                connection.process_data_events(time_limit=1)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Compliance consumer sin conexion: %s. Reintentando en 5s...", exc)
            time.sleep(5)
        finally:
            if connection and connection.is_open:
                connection.close()


def start_consumer() -> None:
    if not settings.enable_consumer:
        logger.info("Consumidor de eventos deshabilitado (ENABLE_CONSUMER=false)")
        return
    _stop.clear()
    threading.Thread(target=_worker, daemon=True, name="compliance-consumer").start()


def stop_consumer() -> None:
    _stop.set()
