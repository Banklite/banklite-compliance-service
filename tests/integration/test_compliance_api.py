"""Pruebas de INTEGRACION de la API de cumplimiento: endpoint + base de datos (SQLite en memoria)."""
import uuid
from datetime import datetime
from unittest.mock import patch

from app import screening
from app.models import Auditoria, TransaccionMonitoreada


def _sospechosa(client, nivel="alto", id_usuario=None) -> dict:
    r = client.post("/compliance/sospechosas", json={
        "id_transferencia": str(uuid.uuid4()), "id_cuenta_origen": str(uuid.uuid4()),
        "id_usuario": str(id_usuario or uuid.uuid4()), "motivo": "Monto inusual", "nivel_riesgo": nivel, "monto": 12000000,
    })
    assert r.status_code == 201
    return r.json()


def test_ciclo_de_un_reporte_regulatorio(client):
    creado = client.post("/compliance/reportes", json={"tipo_reporte": "ROS", "periodo": "2026-10", "contenido": "3 operaciones"})
    assert creado.status_code == 201 and creado.json()["estado"] == "borrador"
    id_reporte = creado.json()["id_reporte"]

    actualizado = client.patch(f"/compliance/reportes/{id_reporte}", json={"estado": "enviado"})

    assert actualizado.json()["estado"] == "enviado"
    assert client.get(f"/compliance/reportes/{id_reporte}").json()["periodo"] == "2026-10"
    assert len(client.get("/compliance/reportes", params={"estado": "enviado", "tipo_reporte": "ROS", "periodo": "2026-10"}).json()) == 1
    assert client.get("/compliance/reportes", params={"estado": "borrador"}).json() == []


def test_estado_de_reporte_invalido_y_reporte_inexistente(client):
    id_reporte = client.post("/compliance/reportes", json={"tipo_reporte": "ROS", "periodo": "2026-10"}).json()["id_reporte"]

    assert client.patch(f"/compliance/reportes/{id_reporte}", json={"estado": "aprobado"}).status_code == 422
    assert client.get(f"/compliance/reportes/{uuid.uuid4()}").status_code == 404
    assert client.patch(f"/compliance/reportes/{uuid.uuid4()}", json={"estado": "enviado"}).status_code == 404


def test_sospechosa_se_filtra_y_cambia_de_estado(client):
    id_usuario = uuid.uuid4()
    alta = _sospechosa(client, "alto", id_usuario)
    _sospechosa(client, "bajo")

    assert len(client.get("/compliance/sospechosas").json()) == 2
    assert len(client.get("/compliance/sospechosas", params={"nivel_riesgo": "alto"}).json()) == 1
    assert len(client.get("/compliance/sospechosas", params={"id_usuario": str(id_usuario)}).json()) == 1

    r = client.patch(f"/compliance/sospechosas/{alta['id_sospecha']}", json={"estado": "investigando"})

    assert r.json()["estado"] == "investigando"
    assert len(client.get("/compliance/sospechosas", params={"estado": "pendiente"}).json()) == 1
    assert client.get(f"/compliance/sospechosas/{alta['id_sospecha']}").json()["estado"] == "investigando"


def test_nivel_de_riesgo_invalido_y_sospechosa_inexistente(client):
    r = client.post("/compliance/sospechosas", json={
        "id_transferencia": str(uuid.uuid4()), "id_cuenta_origen": str(uuid.uuid4()),
        "id_usuario": str(uuid.uuid4()), "motivo": "x", "nivel_riesgo": "extremo",
    })
    assert r.status_code == 422
    assert client.get(f"/compliance/sospechosas/{uuid.uuid4()}").status_code == 404
    assert client.patch(f"/compliance/sospechosas/{uuid.uuid4()}", json={"estado": "descartada"}).status_code == 404


def test_auditoria_exige_que_la_sospechosa_exista(client, sesiones):
    sospechosa = _sospechosa(client)

    sin_sospechosa = client.post("/compliance/auditorias", json={"id_sospecha": str(uuid.uuid4()), "resultado": "limpia"})
    creada = client.post("/compliance/auditorias", json={
        "id_sospecha": sospechosa["id_sospecha"], "auditor": "Oficial de cumplimiento", "resultado": "confirmada_fraude", "notas": "Coincide con patron de pitufeo",
    })

    assert sin_sospechosa.status_code == 404
    assert creada.status_code == 201
    assert len(client.get("/compliance/auditorias", params={"id_sospecha": sospechosa["id_sospecha"]}).json()) == 1
    with sesiones() as db:
        assert db.query(Auditoria).one().resultado == "confirmada_fraude"


def test_screening_devuelve_el_resultado_del_proveedor(client):
    resultado = {"consulta": "Joaquin Guzman", "fuente": "OFAC SDN", "coincidencias": [{"nombre": "GUZMAN LOERA, Joaquin", "score": 0.95}]}
    with patch("app.routers.compliance.screening.screen", return_value=resultado) as mock_screen:
        r = client.post("/compliance/screenings", json={"nombre": "Joaquin Guzman", "limite": 3})

    assert r.status_code == 200 and r.json()["coincidencias"][0]["score"] == 0.95
    mock_screen.assert_called_once_with("Joaquin Guzman", 3)


def test_screening_sin_proveedor_disponible_responde_502(client):
    with patch("app.routers.compliance.screening.screen", side_effect=screening.ScreeningError("OFAC no responde")):
        r = client.post("/compliance/screenings", json={"nombre": "Joaquin Guzman"})
    assert r.status_code == 502


def test_estado_del_screening_indica_el_proveedor_activo(client):
    r = client.get("/compliance/screenings/estado")
    assert r.status_code == 200 and "opensanctions_configurado" in r.json()


def test_indicadores_y_serie_diaria_salen_de_la_base(client, sesiones):
    with sesiones() as db:
        for monto in (1000000, 3000000):
            db.add(TransaccionMonitoreada(
                id_transferencia=uuid.uuid4(), id_cuenta_origen=uuid.uuid4(), monto=monto,
                fecha_transaccion=datetime.utcnow(), marcada="no",
            ))
        db.commit()
    _sospechosa(client, "alto")
    client.post("/compliance/reportes", json={"tipo_reporte": "ROS", "periodo": "2026-11"})

    kpi = client.get("/analytics/indicadores", params={"dias": 7}).json()
    serie = client.get("/analytics/transacciones-por-dia").json()

    assert kpi["transacciones_monitoreadas"] == 2 and kpi["volumen_total"] == 4000000.0
    assert kpi["sospechosas"] == 1 and kpi["tasa_sospecha_pct"] == 50.0
    assert kpi["sospechosas_por_nivel"] == {"alto": 1} and kpi["reportes_por_estado"] == {"borrador": 1}
    assert serie == [{"fecha": serie[0]["fecha"], "cantidad": 2, "monto": 4000000.0}]


def test_stats_resume_el_estado_del_servicio(client):
    _sospechosa(client)
    assert client.get("/stats").json() == {
        "total_reportes": 0, "total_sospechosas": 1, "sospechosas_pendientes": 1, "total_auditorias": 0,
    }
