"""Pruebas de INTEGRACION del consumidor de eventos: evento -> regla AML -> base de datos.

Se entrega el mensaje tal como llegaria desde RabbitMQ (comunicacion asincrona entre
microservicios) y se comprueba lo que queda guardado. account-service se simula con un mock.
"""
import uuid
from unittest.mock import patch

import httpx
import pytest

from app import consumer
from app.models import TransaccionMonitoreada, TransaccionSospechosa

ID_USUARIO = uuid.uuid4()


@pytest.fixture(autouse=True)
def base_y_account_service(sesiones):
    cuenta = httpx.Response(200, json={"id_usuario": str(ID_USUARIO)})
    with (
        patch("app.consumer.SessionLocal", sesiones),
        patch("app.consumer.httpx.get", return_value=cuenta) as mock_get,
    ):
        yield mock_get


def _transferencia(monto: str) -> dict:
    return {
        "id_transferencia": str(uuid.uuid4()),
        "id_cuenta_origen": str(uuid.uuid4()),
        "monto": monto,
        "fecha_solicitud": "2026-11-10T14:30:00+00:00",
    }


def test_transferencia_normal_solo_se_monitorea(sesiones):
    consumer._on_transfer_completed(_transferencia("250000"))

    with sesiones() as db:
        monitoreada = db.query(TransaccionMonitoreada).one()
        assert monitoreada.marcada == "no" and float(monitoreada.monto) == 250000
        assert db.query(TransaccionSospechosa).count() == 0


def test_transferencia_sobre_el_umbral_aml_queda_como_sospechosa(sesiones, base_y_account_service):
    evento = _transferencia("15000000")

    consumer._on_transfer_completed(evento)

    with sesiones() as db:
        assert db.query(TransaccionMonitoreada).one().marcada == "si"
        sospechosa = db.query(TransaccionSospechosa).one()
        assert sospechosa.nivel_riesgo == "medio" and sospechosa.estado == "pendiente"
        assert sospechosa.id_usuario == ID_USUARIO and "AML" in sospechosa.motivo
    # El titular se resolvio preguntando a account-service por la cuenta de origen
    assert base_y_account_service.call_args.args[0].endswith(f"/accounts/{evento['id_cuenta_origen']}")


def test_el_mismo_evento_repetido_no_duplica_registros(sesiones):
    evento = _transferencia("15000000")

    consumer._on_transfer_completed(evento)
    consumer._on_transfer_completed(evento)

    with sesiones() as db:
        assert db.query(TransaccionMonitoreada).count() == 1
        assert db.query(TransaccionSospechosa).count() == 1


def test_alerta_de_fraude_se_registra_con_el_nivel_equivalente(sesiones):
    consumer._on_fraud_alert({
        "id_transaccion": str(uuid.uuid4()), "id_cuenta": str(uuid.uuid4()),
        "monto": 6000000, "score_riesgo": 95.0, "resultado": "bloqueada", "prioridad": "alta",
    })

    with sesiones() as db:
        sospechosa = db.query(TransaccionSospechosa).one()
        assert sospechosa.nivel_riesgo == "alto"
        assert sospechosa.motivo == "Alerta de fraude (score 95.0, bloqueada)"


def test_sin_titular_resoluble_la_alerta_se_omite(sesiones, base_y_account_service):
    base_y_account_service.side_effect = httpx.ConnectError("account-service caido")

    consumer._on_fraud_alert({"id_transaccion": str(uuid.uuid4()), "id_cuenta": str(uuid.uuid4()), "prioridad": "media"})

    with sesiones() as db:
        assert db.query(TransaccionSospechosa).count() == 0
