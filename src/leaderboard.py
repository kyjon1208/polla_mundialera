from __future__ import annotations

import pandas as pd

from src.db import execute, fetch_df, get_db_mode


# =========================================================
# CONFIGURACIÓN DE TIEMPO
# =========================================================

APP_TIMEZONE = "America/Bogota"


def is_postgres() -> bool:
    return get_db_mode() == "postgres"


def now_colombia_condition_for_today(column_name: str = "p.fecha_hora_partido") -> str:
    """
    Condición SQL para filtrar partidos del día actual en hora Colombia.
    """
    if is_postgres():
        return f"DATE({column_name}) = DATE(CURRENT_TIMESTAMP AT TIME ZONE '{APP_TIMEZONE}')"

    return f"date({column_name}) = date('now', 'localtime')"


# =========================================================
# UTILIDADES DE PUNTAJE
# =========================================================

def get_winner(goals_home: int, goals_away: int) -> str:
    if goals_home > goals_away:
        return "local"

    if goals_home < goals_away:
        return "visitante"

    return "empate"


def get_goal_difference(goals_home: int, goals_away: int) -> int:
    return goals_home - goals_away


def get_criteria_points(nombre_criterio: str, fase: str) -> int:
    df = fetch_df("""
        SELECT puntos
        FROM criterios_puntuacion
        WHERE nombre_criterio = :nombre_criterio
          AND fase = :fase
        LIMIT 1
    """, {
        "nombre_criterio": nombre_criterio,
        "fase": fase,
    })

    if df is None or df.empty:
        return 0

    return int(df.iloc[0]["puntos"])


def calculate_match_score(
    fase: str,
    real_home: int,
    real_away: int,
    pred_home: int,
    pred_away: int,
) -> dict:
    """
    Calcula el puntaje de una predicción según los criterios definidos.

    Retorna:
    - criterio_aplicado
    - puntos
    - marcador_completo
    - acierto_ganador_empate
    - diferencia_directa
    """

    real_home = int(real_home)
    real_away = int(real_away)
    pred_home = int(pred_home)
    pred_away = int(pred_away)

    real_winner = get_winner(real_home, real_away)
    pred_winner = get_winner(pred_home, pred_away)

    real_diff = get_goal_difference(real_home, real_away)
    pred_diff = get_goal_difference(pred_home, pred_away)

    real_abs_diff = abs(real_diff)
    pred_abs_diff = abs(pred_diff)

    marcador_completo = 0
    acierto_ganador_empate = 0
    diferencia_directa = 0

    criterio = "Sin puntos"

    if pred_home == real_home and pred_away == real_away:
        criterio = "Marcador Completo"
        marcador_completo = 1
        acierto_ganador_empate = 1
        diferencia_directa = 1

    elif real_winner == "empate" and pred_winner == "empate":
        criterio = "Acierto de Empate"
        acierto_ganador_empate = 1

    elif pred_home == real_away and pred_away == real_home:
        criterio = "Acierto de Marcador Inverso"

    elif pred_winner == real_winner and real_winner != "empate" and pred_diff == real_diff:
        criterio = "Acierto ganador y diferencia directa"
        acierto_ganador_empate = 1
        diferencia_directa = 1

    elif pred_winner == real_winner and real_winner != "empate" and (
        pred_home == real_home or pred_away == real_away
    ):
        criterio = "Acierto de ganador y medio marcador"
        acierto_ganador_empate = 1

    elif pred_winner == real_winner and real_winner != "empate":
        criterio = "Solo acierto de ganador"
        acierto_ganador_empate = 1

    elif pred_diff == real_diff:
        criterio = "Solo diferencia de goles directa"
        diferencia_directa = 1

    elif pred_abs_diff == real_abs_diff:
        criterio = "Solo diferencia de goles inversa"

    elif pred_home == real_home or pred_away == real_away:
        criterio = "Solo medio marcador"

    elif (pred_home == real_away or pred_away == real_home) and pred_abs_diff == real_abs_diff:
        criterio = "Medio marcador y diferencia inversa"

    puntos = get_criteria_points(criterio, fase)

    return {
        "criterio_aplicado": criterio,
        "puntos": puntos,
        "marcador_completo": marcador_completo,
        "acierto_ganador_empate": acierto_ganador_empate,
        "diferencia_directa": diferencia_directa,
    }


# =========================================================
# RECALCULAR PUNTAJES
# =========================================================

def recalculate_scores() -> None:
    """
    Recalcula los puntajes de partidos que estén En juego o Terminados.
    Solo calcula para usuarios participantes.
    """

    predictions = fetch_df("""
        SELECT
            pr.id_usuario,
            pr.id_partido,
            pr.goles_local_predicho,
            pr.goles_visitante_predicho,

            p.fase,
            p.estado_partido,
            p.goles_local_real,
            p.goles_visitante_real,

            u.rol,
            u.estado_activo
        FROM predicciones pr
        INNER JOIN partidos p
            ON pr.id_partido = p.id_partido
        INNER JOIN usuarios u
            ON pr.id_usuario = u.id_usuario
        WHERE p.estado_partido IN ('En juego', 'Terminado')
          AND p.goles_local_real IS NOT NULL
          AND p.goles_visitante_real IS NOT NULL
          AND LOWER(TRIM(u.rol)) = 'participante'
          AND u.estado_activo = 1
    """)

    if predictions is None or predictions.empty:
        return

    for _, row in predictions.iterrows():
        score = calculate_match_score(
            fase=row["fase"],
            real_home=int(row["goles_local_real"]),
            real_away=int(row["goles_visitante_real"]),
            pred_home=int(row["goles_local_predicho"]),
            pred_away=int(row["goles_visitante_predicho"]),
        )

        existing = fetch_df("""
            SELECT id_puntaje
            FROM puntajes_partido
            WHERE id_usuario = :id_usuario
              AND id_partido = :id_partido
            LIMIT 1
        """, {
            "id_usuario": int(row["id_usuario"]),
            "id_partido": int(row["id_partido"]),
        })

        if existing is not None and not existing.empty:
            execute("""
                UPDATE puntajes_partido
                SET
                    criterio_aplicado = :criterio_aplicado,
                    puntos = :puntos,
                    marcador_completo = :marcador_completo,
                    acierto_ganador_empate = :acierto_ganador_empate,
                    diferencia_directa = :diferencia_directa,
                    fecha_calculo = CURRENT_TIMESTAMP
                WHERE id_usuario = :id_usuario
                  AND id_partido = :id_partido
            """, {
                "criterio_aplicado": score["criterio_aplicado"],
                "puntos": score["puntos"],
                "marcador_completo": score["marcador_completo"],
                "acierto_ganador_empate": score["acierto_ganador_empate"],
                "diferencia_directa": score["diferencia_directa"],
                "id_usuario": int(row["id_usuario"]),
                "id_partido": int(row["id_partido"]),
            })

        else:
            execute("""
                INSERT INTO puntajes_partido (
                    id_usuario,
                    id_partido,
                    criterio_aplicado,
                    puntos,
                    marcador_completo,
                    acierto_ganador_empate,
                    diferencia_directa,
                    fecha_calculo
                )
                VALUES (
                    :id_usuario,
                    :id_partido,
                    :criterio_aplicado,
                    :puntos,
                    :marcador_completo,
                    :acierto_ganador_empate,
                    :diferencia_directa,
                    CURRENT_TIMESTAMP
                )
            """, {
                "id_usuario": int(row["id_usuario"]),
                "id_partido": int(row["id_partido"]),
                "criterio_aplicado": score["criterio_aplicado"],
                "puntos": score["puntos"],
                "marcador_completo": score["marcador_completo"],
                "acierto_ganador_empate": score["acierto_ganador_empate"],
                "diferencia_directa": score["diferencia_directa"],
            })


# =========================================================
# TABLA GENERAL DE POSICIONES
# =========================================================

def get_leaderboard() -> pd.DataFrame:
    """
    Retorna la tabla general de posiciones.
    """

    sql = """
        SELECT
            u.id_usuario,
            u.nombre,
            u.usuario,

            COALESCE(SUM(pp.puntos), 0) AS puntos_totales,
            COALESCE(SUM(pp.marcador_completo), 0) AS marcadores_completos,
            COALESCE(SUM(pp.acierto_ganador_empate), 0) AS aciertos_ganador_empate,
            COALESCE(SUM(pp.diferencia_directa), 0) AS diferencias_directas

        FROM usuarios u
        LEFT JOIN puntajes_partido pp
            ON u.id_usuario = pp.id_usuario

        WHERE LOWER(TRIM(u.rol)) = 'participante'
          AND u.estado_activo = 1

        GROUP BY
            u.id_usuario,
            u.nombre,
            u.usuario

        ORDER BY
            puntos_totales DESC,
            marcadores_completos DESC,
            aciertos_ganador_empate DESC,
            diferencias_directas DESC,
            u.nombre ASC
    """

    df = fetch_df(sql)

    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()
    df.insert(0, "posición", range(1, len(df) + 1))

    return df


# =========================================================
# PREDICCIONES DEL DÍA EN FORMATO MATRIZ
# =========================================================

def get_today_predictions_matrix() -> pd.DataFrame:
    """
    Retorna una matriz de predicciones de los partidos del día actual.

    Estructura:
    - Una fila por participante.
    - No muestra usuario, solo nombre del participante.
    - Por cada partido del día:
        - Predicción del participante.
        - Marcador real del partido, solo si está En juego o Terminado.
        - Puntos obtenidos por ese partido.
        - Separador visual entre partidos.
    """

    today_condition = now_colombia_condition_for_today("p.fecha_hora_partido")

    sql = f"""
        SELECT
            u.id_usuario,
            u.nombre AS participante,

            p.id_partido,
            p.fase,
            p.grupo,
            el.nombre AS equipo_local,
            ev.nombre AS equipo_visitante,
            p.fecha_hora_partido,
            p.estado_partido,
            p.goles_local_real,
            p.goles_visitante_real,

            pr.goles_local_predicho,
            pr.goles_visitante_predicho,

            COALESCE(pp.puntos, 0) AS puntos

        FROM usuarios u
        CROSS JOIN partidos p
        INNER JOIN equipos el
            ON p.id_equipo_local = el.id_equipo
        INNER JOIN equipos ev
            ON p.id_equipo_visitante = ev.id_equipo
        LEFT JOIN predicciones pr
            ON u.id_usuario = pr.id_usuario
           AND p.id_partido = pr.id_partido
        LEFT JOIN puntajes_partido pp
            ON u.id_usuario = pp.id_usuario
           AND p.id_partido = pp.id_partido

        WHERE LOWER(TRIM(u.rol)) = 'participante'
          AND u.estado_activo = 1
          AND p.id_equipo_local IS NOT NULL
          AND p.id_equipo_visitante IS NOT NULL
          AND {today_condition}

        ORDER BY
            u.nombre ASC,
            p.fecha_hora_partido ASC,
            p.id_partido ASC
    """

    df = fetch_df(sql)

    if df is None or df.empty:
        return pd.DataFrame()

    rows = []

    for (id_usuario, participante), group in df.groupby(
        ["id_usuario", "participante"],
        dropna=False
    ):
        row = {
            "Participante": participante,
        }

        matches = group.sort_values(
            by=["fecha_hora_partido", "id_partido"],
            ascending=True,
        ).reset_index(drop=True)

        for index, match in matches.iterrows():
            equipo_local = str(match["equipo_local"])
            equipo_visitante = str(match["equipo_visitante"])
            estado = str(match["estado_partido"])

            fecha_partido = pd.to_datetime(match["fecha_hora_partido"])
            hora_partido = fecha_partido.strftime("%H:%M")

            partido_label = (
                f"{equipo_local} - {equipo_visitante} "
                f"({hora_partido}) - {estado}"
            )

            if pd.notna(match["goles_local_predicho"]) and pd.notna(match["goles_visitante_predicho"]):
                prediccion = f"{int(match['goles_local_predicho'])}-{int(match['goles_visitante_predicho'])}"
            else:
                prediccion = "Sin registrar"

            if (
                estado in ("En juego", "Terminado")
                and pd.notna(match["goles_local_real"])
                and pd.notna(match["goles_visitante_real"])
            ):
                marcador_real = f"{int(match['goles_local_real'])}-{int(match['goles_visitante_real'])}"
            else:
                marcador_real = "Pendiente"

            puntos = int(match["puntos"]) if pd.notna(match["puntos"]) else 0

            row[f"{partido_label} | Predicción"] = prediccion
            row[f"{partido_label} | Marcador Partido"] = marcador_real
            row[f"{partido_label} | Puntos"] = puntos

            if index < len(matches) - 1:
                row[f"Separador {index + 1}"] = "────────"

        rows.append(row)

    result = pd.DataFrame(rows)

    fixed_columns = ["Participante"]
    dynamic_columns = [col for col in result.columns if col not in fixed_columns]

    return result[fixed_columns + dynamic_columns]


# =========================================================
# COMPATIBILIDAD: PREDICCIONES RECIENTES
# =========================================================

def get_recent_predictions() -> pd.DataFrame:
    """
    Función conservada por compatibilidad.
    Ahora retorna la matriz de partidos del día.
    """
    return get_today_predictions_matrix()