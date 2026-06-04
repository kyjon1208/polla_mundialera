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
    """
    Busca los puntos del criterio ignorando mayúsculas, minúsculas y espacios.

    Esto evita errores cuando en BD hay textos como:
    'Solo acierto de ganador '
    y en código llega:
    'Solo acierto de ganador'
    """

    df = fetch_df("""
        SELECT puntos
        FROM criterios_puntuacion
        WHERE LOWER(TRIM(nombre_criterio)) = LOWER(TRIM(:nombre_criterio))
          AND LOWER(TRIM(fase)) = LOWER(TRIM(:fase))
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

    Prioridad aplicada:
    1. Marcador completo
    2. Acierto de empate
    3. Acierto de marcador inverso
    4. Acierto ganador y diferencia directa
    5. Acierto de ganador y medio marcador
    6. Solo acierto de ganador
    7. Medio marcador y diferencia inversa
    8. Solo diferencia de goles directa
    9. Solo diferencia de goles inversa
    10. Solo medio marcador
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

    same_winner = real_winner == pred_winner
    same_direct_diff = real_diff == pred_diff
    same_inverse_diff = real_diff == -pred_diff and real_diff != 0

    half_score = pred_home == real_home or pred_away == real_away

    marcador_completo = 0
    acierto_ganador_empate = 0
    diferencia_directa = 0

    criterio = "Sin puntos"

    # 1. Marcador completo
    if pred_home == real_home and pred_away == real_away:
        criterio = "Marcador Completo"
        marcador_completo = 1
        acierto_ganador_empate = 1
        diferencia_directa = 1

    # 2. Acierto de empate
    elif real_winner == "empate" and pred_winner == "empate":
        criterio = "Acierto de Empate"
        acierto_ganador_empate = 1

    # 3. Marcador inverso exacto
    elif pred_home == real_away and pred_away == real_home:
        criterio = "Acierto de Marcador Inverso"

    # 4. Ganador + diferencia directa
    elif same_winner and real_winner != "empate" and same_direct_diff:
        criterio = "Acierto ganador y diferencia directa"
        acierto_ganador_empate = 1
        diferencia_directa = 1

    # 5. Ganador + medio marcador
    elif same_winner and real_winner != "empate" and half_score:
        criterio = "Acierto de ganador y medio marcador"
        acierto_ganador_empate = 1

    # 6. Solo ganador
    elif same_winner and real_winner != "empate":
        criterio = "Solo acierto de ganador"
        acierto_ganador_empate = 1

    # 7. Medio marcador + diferencia inversa
    # Debe ir antes de "Solo diferencia inversa" y antes de "Solo medio marcador"
    elif half_score and same_inverse_diff:
        criterio = "Medio marcador y diferencia inversa"

    # 8. Solo diferencia directa
    elif same_direct_diff:
        criterio = "Solo diferencia de goles directa"
        diferencia_directa = 1

    # 9. Solo diferencia inversa
    elif same_inverse_diff or pred_abs_diff == real_abs_diff:
        criterio = "Solo diferencia de goles inversa"

    # 10. Solo medio marcador
    elif half_score:
        criterio = "Solo medio marcador"

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
# MATRIZ DE PREDICCIONES DEL DÍA
# =========================================================

def get_today_predictions_matrix() -> pd.DataFrame:
    """
    Retorna una matriz tipo:
    Participante | Partido - hora - estado | Marcador Partido | puntos obtenidos | separador | ...

    Importante:
    Streamlit no permite nombres de columnas duplicados.
    Por eso las columnas 'Marcador Partido' y 'puntos obtenidos' llevan el nombre
    del partido como prefijo interno.
    """

    today_condition = now_colombia_condition_for_today("p.fecha_hora_partido")

    sql = f"""
        SELECT
            u.id_usuario,
            u.nombre AS participante,

            p.id_partido,
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
            p.fecha_hora_partido ASC,
            p.id_partido ASC,
            u.nombre ASC
    """

    df = fetch_df(sql)

    if df is None or df.empty:
        return pd.DataFrame()

    matches_df = (
        df[
            [
                "id_partido",
                "equipo_local",
                "equipo_visitante",
                "fecha_hora_partido",
                "estado_partido",
            ]
        ]
        .drop_duplicates()
        .sort_values(by=["fecha_hora_partido", "id_partido"], ascending=True)
        .reset_index(drop=True)
    )

    participants_df = (
        df[["id_usuario", "participante"]]
        .drop_duplicates()
        .sort_values(by=["participante"], ascending=True)
        .reset_index(drop=True)
    )

    rows = []

    for _, participant in participants_df.iterrows():
        id_usuario = int(participant["id_usuario"])
        participante = participant["participante"]

        user_rows = df[df["id_usuario"] == id_usuario].copy()

        row = {
            "Participante": participante,
        }

        total_matches = len(matches_df)

        for idx, match in matches_df.iterrows():
            id_partido = int(match["id_partido"])

            equipo_local = str(match["equipo_local"])
            equipo_visitante = str(match["equipo_visitante"])
            estado_partido = str(match["estado_partido"])

            fecha_partido = pd.to_datetime(match["fecha_hora_partido"])
            hora_partido = fecha_partido.strftime("%H:%M")

            partido_base = f"{equipo_local}-{equipo_visitante}"

            columna_prediccion = f"{partido_base} - {hora_partido} - {estado_partido}"
            columna_marcador = f"{partido_base} - Marcador Partido"
            columna_puntos = f"{partido_base} - puntos obtenidos"

            match_row = user_rows[user_rows["id_partido"] == id_partido]

            if match_row.empty:
                prediccion = ""
                marcador_partido = estado_partido
                puntos_obtenidos = ""
            else:
                record = match_row.iloc[0]

                if pd.notna(record["goles_local_predicho"]) and pd.notna(record["goles_visitante_predicho"]):
                    prediccion = f"{int(record['goles_local_predicho'])}-{int(record['goles_visitante_predicho'])}"
                else:
                    prediccion = ""

                if (
                    estado_partido in ("En juego", "Terminado")
                    and pd.notna(record["goles_local_real"])
                    and pd.notna(record["goles_visitante_real"])
                ):
                    marcador_partido = f"{int(record['goles_local_real'])}-{int(record['goles_visitante_real'])}"
                    puntos_obtenidos = int(record["puntos"]) if pd.notna(record["puntos"]) else 0
                else:
                    marcador_partido = estado_partido
                    puntos_obtenidos = ""

            row[columna_prediccion] = prediccion
            row[columna_marcador] = marcador_partido
            row[columna_puntos] = puntos_obtenidos

            if idx < total_matches - 1:
                row[f"──────── {idx + 1}"] = ""

        rows.append(row)

    result = pd.DataFrame(rows)

    return result

# =========================================================
# COMPATIBILIDAD
# =========================================================

def get_recent_predictions() -> pd.DataFrame:
    """
    Conservada por compatibilidad.
    """
    return get_today_predictions_matrix()