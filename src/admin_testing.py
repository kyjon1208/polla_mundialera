"""Utilidades temporales para pruebas manuales de partidos."""
from __future__ import annotations

from src.db import execute, fetch_df


def get_matches_for_admin():
    return fetch_df(
        """
        SELECT
            p.id_partido,
            p.fase,
            el.nombre AS local,
            ev.nombre AS visitante,
            p.fecha_hora_partido,
            p.estado_partido,
            p.goles_local_real,
            p.goles_visitante_real
        FROM partidos p
        JOIN equipos el ON el.id_equipo = p.id_equipo_local
        JOIN equipos ev ON ev.id_equipo = p.id_equipo_visitante
        ORDER BY p.fecha_hora_partido
        """
    )


def update_test_match(match_id: int, status: str, home_goals: int | None, away_goals: int | None) -> None:
    execute(
        """
        UPDATE partidos
        SET estado_partido = :estado,
            goles_local_real = :goles_local,
            goles_visitante_real = :goles_visitante
        WHERE id_partido = :id_partido
        """,
        {
            "id_partido": match_id,
            "estado": status,
            "goles_local": home_goals,
            "goles_visitante": away_goals,
        },
    )
