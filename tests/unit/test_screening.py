"""Pruebas UNITARIAS del screening de sanciones/PEP (AML).

Las fuentes externas (lista OFAC SDN del Tesoro de EE.UU. y OpenSanctions) se
simulan con mocks de httpx: la logica de coincidencia se prueba sin red.
"""
from unittest.mock import patch

import httpx
import pytest

from app import screening
from app.config import settings

# Formato real del archivo sdn.csv: numero, nombre, tipo, programa, ...
SDN_CSV = (
    '36,"AEROCARIBBEAN AIRLINES",-0- ,"CUBA",-0- \n'
    '7001,"GUZMAN LOERA, Joaquin",individual,"SDNTK",-0- \n'
    '7002,"PEREZ GOMEZ, Maria Jose",individual,"SDGT",-0- \n'
)


@pytest.fixture(autouse=True)
def estado_limpio(monkeypatch):
    monkeypatch.setattr(settings, "opensanctions_api_key", None)
    screening._cache_ofac.update({"nombres": [], "programas": {}, "ts": 0.0})
    yield
    screening._cache_ofac.update({"nombres": [], "programas": {}, "ts": 0.0})


def _ofac_ok():
    return httpx.Response(200, content=SDN_CSV.encode("latin-1"), request=httpx.Request("GET", screening.OFAC_SDN_URL))


@pytest.mark.parametrize("entrada, esperado", [
    ("José  Pérez-Gómez", "JOSE PEREZ GOMEZ"),
    ("  guzmán loera, joaquín ", "GUZMAN LOERA JOAQUIN"),
    ("", ""),
    (None, ""),
])
def test_normalizar_quita_tildes_signos_y_espacios(entrada, esperado):
    assert screening._normalizar(entrada) == esperado


def test_nombre_en_la_lista_ofac_genera_coincidencia():
    with patch("app.screening.httpx.get", return_value=_ofac_ok()):
        resultado = screening.screen("Joaquín Guzmán Loera")

    assert resultado["fuente"].startswith("OFAC SDN")
    coincidencia = resultado["coincidencias"][0]
    assert coincidencia["nombre"] == "GUZMAN LOERA, Joaquin"
    assert coincidencia["programa"] == "SDNTK" and coincidencia["score"] >= screening.UMBRAL_COINCIDENCIA


def test_nombre_limpio_no_genera_coincidencias():
    with patch("app.screening.httpx.get", return_value=_ofac_ok()):
        assert screening.screen("Juan David Rhenals")["coincidencias"] == []


def test_la_lista_ofac_se_descarga_una_sola_vez():
    with patch("app.screening.httpx.get", return_value=_ofac_ok()) as mock_get:
        screening.screen("Maria Jose Perez Gomez")
        screening.screen("Aerocaribbean Airlines")
    assert mock_get.call_count == 1


def test_el_limite_recorta_las_coincidencias():
    with patch("app.screening.httpx.get", return_value=_ofac_ok()):
        assert len(screening.screen("Guzman Loera Joaquin", limite=1)["coincidencias"]) == 1


def test_nombre_demasiado_corto_no_consulta_ninguna_fuente():
    with patch("app.screening.httpx.get") as mock_get:
        resultado = screening.screen("ab")
    assert resultado["fuente"] == "ninguna" and resultado["coincidencias"] == []
    mock_get.assert_not_called()


def test_si_ofac_no_responde_se_lanza_screening_error():
    with patch("app.screening.httpx.get", side_effect=httpx.ConnectError("sin red")):
        with pytest.raises(screening.ScreeningError, match="OFAC"):
            screening.screen("Joaquin Guzman")


def test_con_api_key_se_usa_opensanctions(monkeypatch):
    monkeypatch.setattr(settings, "opensanctions_api_key", "clave-de-prueba")
    respuesta = httpx.Response(
        200,
        json={"responses": {"consulta": {"results": [
            {"caption": "Persona B", "score": 0.71, "datasets": ["us_ofac_sdn"], "properties": {"topics": ["sanction"]}},
            {"caption": "Persona A", "score": 0.93, "datasets": ["interpol"], "properties": {}},
        ]}}},
        request=httpx.Request("POST", "https://api.opensanctions.org/match/default"),
    )
    with patch("app.screening.httpx.post", return_value=respuesta) as mock_post:
        resultado = screening.screen("Persona A")

    assert resultado["fuente"] == "OpenSanctions API"
    assert [c["nombre"] for c in resultado["coincidencias"]] == ["Persona A", "Persona B"]  # ordenadas por score
    assert mock_post.call_args.kwargs["headers"]["Authorization"] == "ApiKey clave-de-prueba"


def test_si_opensanctions_falla_se_usa_ofac_de_respaldo(monkeypatch):
    monkeypatch.setattr(settings, "opensanctions_api_key", "clave-de-prueba")
    with (
        patch("app.screening.httpx.post", side_effect=httpx.ReadTimeout("timeout")),
        patch("app.screening.httpx.get", return_value=_ofac_ok()),
    ):
        resultado = screening.screen("Joaquin Guzman Loera")

    assert resultado["fuente"].startswith("OFAC SDN") and resultado["coincidencias"]
