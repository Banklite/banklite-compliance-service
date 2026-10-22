"""Screening real de sanciones y PEP (AML/CFT).

Dos proveedores, en este orden:
1. OpenSanctions API (2.000 creditos gratis) si OPEN_SANCTIONS_API_KEY existe.
2. Respaldo sin credenciales: lista OFAC SDN oficial del Tesoro de EE.UU.
   (https://www.treasury.gov/ofac/downloads/sdn.csv), descargada y cacheada.
"""

import csv
import io
import logging
import re
import unicodedata
from difflib import SequenceMatcher

import httpx

from .config import settings

logger = logging.getLogger(__name__)

OFAC_SDN_URL = "https://www.treasury.gov/ofac/downloads/sdn.csv"
OFAC_CACHE_TTL = 6 * 3600.0
UMBRAL_COINCIDENCIA = 0.82

class ScreeningError(RuntimeError):
    """Ningun proveedor de screening pudo responder."""


_cache_ofac: dict = {"nombres": [], "programas": {}, "ts": 0.0}


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^A-Za-z0-9 ]", " ", texto.upper())
    return re.sub(r"\s+", " ", texto).strip()


def _cargar_ofac() -> dict:
    """Descarga (y cachea 6 h) la lista SDN del Tesoro de EE.UU."""
    import time

    if _cache_ofac["nombres"] and (time.time() - _cache_ofac["ts"]) < OFAC_CACHE_TTL:
        return _cache_ofac

    r = httpx.get(OFAC_SDN_URL, timeout=60.0, follow_redirects=True)
    r.raise_for_status()

    nombres: list[dict] = []
    programas: dict[str, str] = {}
    exportado = csv.reader(io.StringIO(r.content.decode("latin-1", errors="replace")))
    for fila in exportado:
        if len(fila) < 4:
            continue
        ent_num, nombre, tipo, programa = fila[0].strip(), fila[1].strip(), fila[2].strip(), fila[3].strip()
        if not nombre:
            continue
        clave = _normalizar(nombre)
        nombres.append({"nombre": nombre, "normalizado": clave, "tipo": tipo, "entidad": ent_num})
        programas[ent_num] = programa

    _cache_ofac["nombres"] = nombres
    _cache_ofac["programas"] = programas
    _cache_ofac["ts"] = time.time()
    logger.info("[OFAC] Lista SDN cargada: %s registros", len(nombres))
    return _cache_ofac


def _screen_ofac(nombre: str, limite: int) -> list[dict]:
    cache = _cargar_ofac()
    consulta = _normalizar(nombre)
    tokens = set(consulta.split())
    resultados = []
    for item in cache["nombres"]:
        ratio = SequenceMatcher(None, consulta, item["normalizado"]).ratio()
        # Bonus si todas las palabras de la consulta aparecen en el nombre
        if tokens and tokens.issubset(set(item["normalizado"].split())):
            ratio = max(ratio, 0.95)
        if ratio >= UMBRAL_COINCIDENCIA:
            resultados.append(
                {
                    "nombre": item["nombre"],
                    "tipo": item["tipo"],
                    "programa": cache["programas"].get(item["entidad"], ""),
                    "score": round(ratio, 3),
                    "lista": "OFAC SDN",
                }
            )
    resultados.sort(key=lambda x: x["score"], reverse=True)
    return resultados[:limite]


def _screen_opensanctions(nombre: str, limite: int) -> list[dict]:
    r = httpx.post(
        "https://api.opensanctions.org/match/default",
        headers={"Authorization": f"ApiKey {settings.opensanctions_api_key}"},
        json={
            "queries": {
                "consulta": {
                    "schema": "Person",
                    "properties": {"name": [nombre]},
                }
            }
        },
        timeout=30.0,
    )
    r.raise_for_status()
    datos = r.json()
    resultados = []
    for hit in (datos.get("responses") or {}).get("consulta", {}).get("results", []):
        resultados.append(
            {
                "nombre": hit.get("caption") or nombre,
                "tipo": ", ".join(hit.get("properties", {}).get("topics", [])) or "sancion/PEP",
                "programa": ", ".join(hit.get("datasets", [])),
                "score": round(float(hit.get("score") or 0.0), 3),
                "lista": "OpenSanctions",
            }
        )
    resultados.sort(key=lambda x: x["score"], reverse=True)
    return resultados[:limite]


def screen(nombre: str, limite: int = 5) -> dict:
    """Consulta sanciones/PEP por nombre. Nunca falla en silencio: lanza ScreeningError."""
    nombre = (nombre or "").strip()
    if len(nombre) < 3:
        return {"consulta": nombre, "fuente": "ninguna", "coincidencias": [], "detalle": "Nombre demasiado corto"}

    if settings.opensanctions_api_key:
        try:
            return {
                "consulta": nombre,
                "fuente": "OpenSanctions API",
                "coincidencias": _screen_opensanctions(nombre, limite),
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("[OPEN-SANCTIONS] Fallo (%s); usando OFAC SDN de respaldo", exc)

    try:
        coincidencias = _screen_ofac(nombre, limite)
    except Exception as exc:  # noqa: BLE001
        raise ScreeningError(f"No se pudo consultar la lista OFAC: {exc}") from exc
    return {
        "consulta": nombre,
        "fuente": "OFAC SDN (Tesoro de EE.UU., lista oficial)",
        "coincidencias": coincidencias,
    }
