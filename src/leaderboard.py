"""Consultas para posiciones y recálculo de puntajes."""
from __future__ import annotations

import pandas as pd

from src.db import execute, fetch_df
from src.scoring import evaluate_prediction


SCORABLE_STATES = ("En juego", "Terminado")


def _criteria_for_phase(fase: str) -> dict[str, int]:
    df = fetch_df(
        "SELECT nombre_criterio, puntos FROM criterios_puntuacion WHERE fase = :fase",
        {"fase": fase},
    )
    return dict(zip(df["nombre_criterio"], df["puntos"])) if not df.empty else {}


def recalculate_scores() -> None:
    """Recalcula todos los puntajes de partidos en juego o terminados."""
    matches = fetch_df(
        """
        SELECT id_partido, fase, goles_local_real, goles_visitante_real
        FROM partidos
        WHERE estado_partido IN ('En juego', 'Terminado')
          AND goles_local_real IS NOT NULL
          AND goles_visitante_real IS NOT NULL
        """
    )
    execute("DELETE FROM puntajes_partido")

    for _, match in matches.iterrows():
        criteria = _criteria_for_phase(str(match["fase"]))
        predictions = fetch_df(
            """
            SELECT id_usuario, goles_local_predicho, goles_visitante_predicho
            FROM predicciones
            WHERE id_partido = :id_partido
            """,
            {"id_partido": int(match["id_partido"])},
        )
        for _, pred in predictions.iterrows():
            result = evaluate_prediction(
                int(pred["goles_local_predicho"]),
                int(pred["goles_visitante_predicho"]),
                int(match["goles_local_real"]),
                int(match["goles_visitante_real"]),
                criteria,
            )
            execute(
                """
                INSERT INTO puntajes_partido (
                    id_usuario, id_partido, criterio_aplicado, puntos,
                    marcador_completo, acierto_ganador_empate, diferencia_directa, fecha_calculo
                ) VALUES (
                    :id_usuario, :id_partido, :criterio, :puntos,
                    :marcador_completo, :acierto_ganador_empate, :diferencia_directa, CURRENT_TIMESTAMP
                )
                """,
                {
                    "id_usuario": int(pred["id_usuario"]),
                    "id_partido": int(match["id_partido"]),
                    "criterio": result.criterio,
                    "puntos": result.puntos,
                    "marcador_completo": result.marcador_completo,
                    "acierto_ganador_empate": result.acierto_ganador_empate,
                    "diferencia_directa": result.diferencia_directa,
                },
            )


def get_leaderboard() -> pd.DataFrame:
    sql = """
    SELECT
        u.nombre AS participante,
        COALESCE(SUM(pp.puntos), 0) AS puntos_totales,
        COALESCE(SUM(pp.marcador_completo), 0) AS marcadores_completos,
        COALESCE(SUM(pp.acierto_ganador_empate), 0) AS aciertos_ganador_empate,
        COALESCE(SUM(pp.diferencia_directa), 0) AS diferencias_directas
    FROM usuarios u
    LEFT JOIN puntajes_partido pp ON pp.id_usuario = u.id_usuario
    WHERE u.rol = 'participante' AND u.estado_activo = 1
    GROUP BY u.id_usuario, u.nombre
    ORDER BY
        puntos_totales DESC,
        marcadores_completos DESC,
        aciertos_ganador_empate DESC,
        diferencias_directas DESC,
        participante ASC
    """
    df = fetch_df(sql)
    if not df.empty:
        df.insert(0, "posición", range(1, len(df) + 1))
    return df


def get_recent_predictions() -> pd.DataFrame:
    sql = """
    SELECT
        p.fecha_hora_partido,
        p.estado_partido,
        el.nombre || ' vs ' || ev.nombre AS partido,
        u.nombre AS participante,
        pr.goles_local_predicho || '-' || pr.goles_visitante_predicho AS prediccion,
        COALESCE(p.goles_local_real || '-' || p.goles_visitante_real, '-') AS resultado,
        COALESCE(pp.puntos, 0) AS puntos,
        COALESCE(pp.criterio_aplicado, '-') AS criterio
    FROM predicciones pr
    JOIN usuarios u ON u.id_usuario = pr.id_usuario
    JOIN partidos p ON p.id_partido = pr.id_partido
    JOIN equipos el ON el.id_equipo = p.id_equipo_local
    JOIN equipos ev ON ev.id_equipo = p.id_equipo_visitante
    LEFT JOIN puntajes_partido pp
      ON pp.id_usuario = pr.id_usuario AND pp.id_partido = pr.id_partido
    ORDER BY p.fecha_hora_partido DESC, u.nombre
    LIMIT 100
    """
    return fetch_df(sql)
