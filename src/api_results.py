"""Integración preparada para API de resultados del Mundial.

La clase deja una interfaz clara para conectar Sportmonks, API-Football,
Statorium u otro proveedor. Mientras tanto, la pantalla de pruebas permite
simular partidos.
"""
from __future__ import annotations

import requests
import streamlit as st

from src.db import execute


class FootballResultsClient:
    def __init__(self) -> None:
        self.base_url = st.secrets.get("FOOTBALL_API_BASE_URL", "")
        self.api_key = st.secrets.get("FOOTBALL_API_KEY", "")

    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    def get_matches(self) -> list[dict]:
        if not self.is_configured():
            return []
        headers = {"Authorization": f"Bearer {self.api_key}"}
        response = requests.get(f"{self.base_url}/matches", headers=headers, timeout=30)
        response.raise_for_status()
        return response.json().get("data", [])


def update_match_result(
    match_id: int,
    status: str,
    home_goals: int | None = None,
    away_goals: int | None = None,
) -> None:
    sql = """
    UPDATE partidos
    SET estado_partido = :estado,
        goles_local_real = :goles_local,
        goles_visitante_real = :goles_visitante
    WHERE id_partido = :id_partido
    """
    execute(sql, {
        "id_partido": match_id,
        "estado": status,
        "goles_local": home_goals,
        "goles_visitante": away_goals,
    })
