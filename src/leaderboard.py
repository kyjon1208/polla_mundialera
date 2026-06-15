from __future__ import annotations

from typing import Any

import pandas as pd

from src.db import execute, fetch_df, fetch_one, get_db_mode


# =========================================================
# UTILIDADES DE CÁLCULO
# =========================================================

def get_winner(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "local"

    if away_goals > home_goals:
        return "visitante"

    return "empate"


def get_goal_difference(home_goals: int, away_goals: int) -> int:
    return home_goals - away_goals


def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip().lower()


def get_criteria_points_map() -> dict[tuple[str, str], int]:
    """
    Trae todos los criterios una sola vez y los deja en memoria.
    Esto evita hacer consultas repetidas por cada predicción.
    """

    criteria_df = fetch_df("""
        SELECT
            nombre_criterio,
            fase,
            puntos
        FROM criterios_puntuacion
    """)

    points_map: dict[tuple[str, str], int] = {}

    if criteria_df.empty:
        return points_map

    for _, row in criteria_df.iterrows():
        criterion_name = normalize_text(row["nombre_criterio"])
        phase = normalize_text(row["fase"])
        points = int(row["puntos"]) if pd.notna(row["puntos"]) else 0

        points_map[(criterion_name, phase)] = points

    return points_map


def get_criteria_points_from_map(
    points_map: dict[tuple[str, str], int],
    criterion_name: str,
    phase: str,
) -> int:
    return points_map.get(
        (
            normalize_text(criterion_name),
            normalize_text(phase),
        ),
        0,
    )


def calculate_match_score_fast(
    phase: str,
    real_home: int,
    real_away: int,
    pred_home: int,
    pred_away: int,
    points_map: dict[tuple[str, str], int],
) -> tuple[int, str]:
    """
    Calcula el puntaje de una predicción sin consultar la BD.
    Usa el mapa de criterios ya cargado en memoria.
    """

    real_winner = get_winner(real_home, real_away)
    pred_winner = get_winner(pred_home, pred_away)

    real_diff = get_goal_difference(real_home, real_away)
    pred_diff = get_goal_difference(pred_home, pred_away)

    exact_home = real_home == pred_home
    exact_away = real_away == pred_away
    half_score = exact_home or exact_away

    # 1. Marcador completo
    if real_home == pred_home and real_away == pred_away:
        criterion = "Marcador Completo"
        return get_criteria_points_from_map(points_map, criterion, phase), criterion

    # 2. Acierto de empate
    if real_winner == "empate" and pred_winner == "empate":
        criterion = "Acierto de Empate"
        return get_criteria_points_from_map(points_map, criterion, phase), criterion

    # 3. Marcador inverso
    if real_home == pred_away and real_away == pred_home:
        criterion = "Acierto de Marcador Inverso"
        return get_criteria_points_from_map(points_map, criterion, phase), criterion

    # 4. Ganador + diferencia directa
    if real_winner == pred_winner and real_diff == pred_diff:
        criterion = "Acierto ganador y diferencia directa"
        return get_criteria_points_from_map(points_map, criterion, phase), criterion

    # 5. Ganador + medio marcador
    if real_winner == pred_winner and half_score:
        criterion = "Acierto de ganador y medio marcador"
        return get_criteria_points_from_map(points_map, criterion, phase), criterion

    # 6. Solo ganador
    if real_winner == pred_winner:
        criterion = "Solo acierto de ganador"
        return get_criteria_points_from_map(points_map, criterion, phase), criterion

    # 7. Medio marcador + diferencia inversa
    if half_score and real_diff == -pred_diff:
        criterion = "Medio marcador y diferencia inversa"
        return get_criteria_points_from_map(points_map, criterion, phase), criterion

    # 8. Solo diferencia directa
    if real_diff == pred_diff:
        criterion = "Solo diferencia de goles directa"
        return get_criteria_points_from_map(points_map, criterion, phase), criterion

    # 9. Solo diferencia inversa
    if real_diff == -pred_diff:
        criterion = "Solo diferencia de goles inversa"
        return get_criteria_points_from_map(points_map, criterion, phase), criterion

    # 10. Solo medio marcador
    if half_score:
        criterion = "Solo medio marcador"
        return get_criteria_points_from_map(points_map, criterion, phase), criterion

    return 0, "Sin puntos"


# =========================================================
# RECÁLCULO OPTIMIZADO
# =========================================================

def recalculate_scores() -> None:
    """
    Recalcula puntajes de forma optimizada.

    Antes:
    - Muchas consultas dentro de ciclos.
    - Muy lento en Supabase/Streamlit Cloud.

    Ahora:
    - 1 consulta para criterios.
    - 1 consulta para predicciones puntuables.
    - Cálculo en memoria.
    - 1 delete por partidos involucrados.
    - Inserts en bloques.
    """

    points_map = get_criteria_points_map()

    if not points_map:
        return

    predictions_df = fetch_df("""
        SELECT
            pr.id_prediccion,
            pr.id_usuario,
            pr.id_partido,
            pr.goles_local_predicho,
            pr.goles_visitante_predicho,
            p.fase,
            p.goles_local_real,
            p.goles_visitante_real
        FROM predicciones pr
        INNER JOIN partidos p
            ON pr.id_partido = p.id_partido
        INNER JOIN usuarios u
            ON pr.id_usuario = u.id_usuario
        WHERE LOWER(TRIM(u.rol)) = 'participante'
          AND u.estado_activo = 1
          AND p.estado_partido IN ('En juego', 'Terminado')
          AND p.goles_local_real IS NOT NULL
          AND p.goles_visitante_real IS NOT NULL
          AND pr.goles_local_predicho IS NOT NULL
          AND pr.goles_visitante_predicho IS NOT NULL
    """)

    if predictions_df.empty:
        return

    score_rows: list[dict[str, Any]] = []

    for _, row in predictions_df.iterrows():
        phase = str(row["fase"]).strip()

        real_home = int(row["goles_local_real"])
        real_away = int(row["goles_visitante_real"])
        pred_home = int(row["goles_local_predicho"])
        pred_away = int(row["goles_visitante_predicho"])

        points, criterion = calculate_match_score_fast(
            phase=phase,
            real_home=real_home,
            real_away=real_away,
            pred_home=pred_home,
            pred_away=pred_away,
            points_map=points_map,
        )

        score_rows.append({
            "id_usuario": int(row["id_usuario"]),
            "id_partido": int(row["id_partido"]),
            "puntos_obtenidos": int(points),
            "criterio_aplicado": criterion,
        })

    if not score_rows:
        return

    match_ids = sorted({row["id_partido"] for row in score_rows})

    delete_scores_for_matches(match_ids)
    bulk_insert_scores(score_rows)


def delete_scores_for_matches(match_ids: list[int]) -> None:
    """
    Borra puntajes previos solo de los partidos que se van a recalcular.
    Esto evita recalcular o tocar partidos innecesarios.
    """

    if not match_ids:
        return

    placeholders = []
    params: dict[str, Any] = {}

    for index, match_id in enumerate(match_ids):
        key = f"id_partido_{index}"
        placeholders.append(f":{key}")
        params[key] = match_id

    execute(f"""
        DELETE FROM puntajes_partido
        WHERE id_partido IN ({", ".join(placeholders)})
    """, params)


def bulk_insert_scores(score_rows: list[dict[str, Any]], batch_size: int = 500) -> None:
    """
    Inserta puntajes en bloques.
    Esto es mucho más rápido que insertar uno por uno.
    """

    if not score_rows:
        return

    for start in range(0, len(score_rows), batch_size):
        batch = score_rows[start:start + batch_size]

        values_sql = []
        params: dict[str, Any] = {}

        for index, row in enumerate(batch):
            values_sql.append(f"""
                (
                    :id_usuario_{index},
                    :id_partido_{index},
                    :puntos_obtenidos_{index},
                    :criterio_aplicado_{index}
                )
            """)

            params[f"id_usuario_{index}"] = row["id_usuario"]
            params[f"id_partido_{index}"] = row["id_partido"]
            params[f"puntos_obtenidos_{index}"] = row["puntos_obtenidos"]
            params[f"criterio_aplicado_{index}"] = row["criterio_aplicado"]

        execute(f"""
            INSERT INTO puntajes_partido (
                id_usuario,
                id_partido,
                puntos_obtenidos,
                criterio_aplicado
            )
            VALUES {", ".join(values_sql)}
        """, params)


# =========================================================
# TABLA GENERAL DE POSICIONES
# =========================================================

def get_leaderboard() -> pd.DataFrame:
    """
    Retorna tabla general de posiciones.
    Usa los puntajes ya calculados en puntajes_partido.
    """

    leaderboard_df = fetch_df("""
        SELECT
            u.id_usuario,
            u.nombre,
            u.usuario,
            COALESCE(SUM(pp.puntos_obtenidos), 0) AS puntos_totales,

            COALESCE(SUM(CASE
                WHEN pp.criterio_aplicado = 'Marcador Completo'
                THEN 1 ELSE 0
            END), 0) AS marcadores_completos,

            COALESCE(SUM(CASE
                WHEN pp.criterio_aplicado = 'Acierto de Empate'
                THEN 1 ELSE 0
            END), 0) AS aciertos_empate,

            COALESCE(SUM(CASE
                WHEN pp.criterio_aplicado = 'Acierto ganador y diferencia directa'
                THEN 1 ELSE 0
            END), 0) AS ganador_diferencia_directa,

            COALESCE(SUM(CASE
                WHEN pp.criterio_aplicado = 'Acierto de ganador y medio marcador'
                THEN 1 ELSE 0
            END), 0) AS ganador_medio_marcador,

            COALESCE(SUM(CASE
                WHEN pp.criterio_aplicado = 'Solo acierto de ganador'
                THEN 1 ELSE 0
            END), 0) AS solo_ganador,

            COALESCE(SUM(CASE
                WHEN pp.criterio_aplicado = 'Solo diferencia de goles directa'
                THEN 1 ELSE 0
            END), 0) AS diferencia_directa,

            COALESCE(SUM(CASE
                WHEN pp.criterio_aplicado = 'Solo diferencia de goles inversa'
                THEN 1 ELSE 0
            END), 0) AS diferencia_inversa,

            COALESCE(SUM(CASE
                WHEN pp.criterio_aplicado = 'Solo medio marcador'
                THEN 1 ELSE 0
            END), 0) AS solo_medio_marcador

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
            aciertos_empate DESC,
            ganador_diferencia_directa DESC,
            u.nombre ASC
    """)

    if leaderboard_df.empty:
        return leaderboard_df

    leaderboard_df.insert(
        0,
        "posición",
        range(1, len(leaderboard_df) + 1),
    )

    return leaderboard_df


# =========================================================
# PREDICCIONES DE HOY
# =========================================================

def today_condition_sql(column_name: str = "p.fecha_hora_partido") -> str:
    db_mode = get_db_mode()

    if db_mode == "postgres":
        return f"DATE({column_name}) = DATE(CURRENT_TIMESTAMP AT TIME ZONE 'America/Bogota')"

    return f"date({column_name}) = date('now', 'localtime')"


def get_today_predictions_matrix(participant_name: str | None = None) -> pd.DataFrame:
    """
    Matriz de predicciones de los partidos de hoy.

    Si participant_name viene con un nombre específico,
    filtra desde SQL para que sea más rápido.
    """

    params: dict[str, Any] = {}
    participant_filter = ""

    if participant_name and participant_name != "Todos":
        participant_filter = "AND u.nombre = :participant_name"
        params["participant_name"] = participant_name

    df = fetch_df(f"""
        SELECT
            u.id_usuario,
            u.nombre AS participante,
            p.id_partido,
            p.fecha_hora_partido,
            p.estado_partido,

            el.nombre AS equipo_local,
            ev.nombre AS equipo_visitante,

            pr.goles_local_predicho,
            pr.goles_visitante_predicho,

            p.goles_local_real,
            p.goles_visitante_real,

            pp.puntos_obtenidos,
            pp.criterio_aplicado

        FROM usuarios u
        CROSS JOIN partidos p
        INNER JOIN equipos el
            ON p.id_equipo_local = el.id_equipo
        INNER JOIN equipos ev
            ON p.id_equipo_visitante = ev.id_equipo
        LEFT JOIN predicciones pr
            ON pr.id_usuario = u.id_usuario
           AND pr.id_partido = p.id_partido
        LEFT JOIN puntajes_partido pp
            ON pp.id_usuario = u.id_usuario
           AND pp.id_partido = p.id_partido
        WHERE LOWER(TRIM(u.rol)) = 'participante'
          AND u.estado_activo = 1
          AND p.id_equipo_local IS NOT NULL
          AND p.id_equipo_visitante IS NOT NULL
          AND {today_condition_sql("p.fecha_hora_partido")}
          {participant_filter}
        ORDER BY
            u.nombre,
            p.fecha_hora_partido,
            p.id_partido
    """, params)

    if df.empty:
        return pd.DataFrame()

    participants = (
        df[["id_usuario", "participante"]]
        .drop_duplicates()
        .sort_values("participante")
    )

    matches = (
        df[[
            "id_partido",
            "fecha_hora_partido",
            "estado_partido",
            "equipo_local",
            "equipo_visitante",
            "goles_local_real",
            "goles_visitante_real",
        ]]
        .drop_duplicates()
        .sort_values(["fecha_hora_partido", "id_partido"])
    )

    rows = []

    for _, participant in participants.iterrows():
        row_data: dict[str, Any] = {
            "Participante": participant["participante"],
        }

        participant_df = df[df["id_usuario"] == participant["id_usuario"]]

        for match_index, match in matches.iterrows():
            id_partido = match["id_partido"]
            equipo_local = match["equipo_local"]
            equipo_visitante = match["equipo_visitante"]

            hora = pd.to_datetime(match["fecha_hora_partido"]).strftime("%H:%M")
            estado = match["estado_partido"]

            match_label = f"{equipo_local} vs {equipo_visitante} - {hora} - {estado}"

            prediction_row = participant_df[
                participant_df["id_partido"] == id_partido
            ]

            if prediction_row.empty:
                prediction_value = ""
                points_value = ""
            else:
                prediction = prediction_row.iloc[0]

                if (
                    pd.notna(prediction["goles_local_predicho"])
                    and pd.notna(prediction["goles_visitante_predicho"])
                ):
                    prediction_value = (
                        f"{int(prediction['goles_local_predicho'])}"
                        f"-"
                        f"{int(prediction['goles_visitante_predicho'])}"
                    )
                else:
                    prediction_value = ""

                points_value = (
                    int(prediction["puntos_obtenidos"])
                    if pd.notna(prediction["puntos_obtenidos"])
                    else ""
                )

            if (
                pd.notna(match["goles_local_real"])
                and pd.notna(match["goles_visitante_real"])
            ):
                real_score = (
                    f"{int(match['goles_local_real'])}"
                    f"-"
                    f"{int(match['goles_visitante_real'])}"
                )
            else:
                real_score = ""

            row_data[match_label] = prediction_value
            row_data[f"{match_label} - Marcador Partido"] = real_score
            row_data[f"{match_label} - puntos obtenidos"] = points_value
            row_data[f"──────── {id_partido}"] = ""

        rows.append(row_data)

    return pd.DataFrame(rows)


def get_recent_predictions() -> pd.DataFrame:
    """
    Compatibilidad con código anterior.
    """

    return get_today_predictions_matrix()


# =========================================================
# UTILIDADES ADICIONALES
# =========================================================

def has_scorable_matches() -> bool:
    row = fetch_one("""
        SELECT COUNT(*) AS total
        FROM partidos
        WHERE estado_partido IN ('En juego', 'Terminado')
          AND goles_local_real IS NOT NULL
          AND goles_visitante_real IS NOT NULL
    """)

    if not row:
        return False

    return int(row["total"]) > 0