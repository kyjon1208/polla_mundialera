from __future__ import annotations

import pandas as pd

from src.db import execute, fetch_df, get_db_mode


APP_TIMEZONE = "America/Bogota"


def is_postgres() -> bool:
    return get_db_mode() == "postgres"


def now_colombia_sql() -> str:
    if is_postgres():
        return f"(CURRENT_TIMESTAMP AT TIME ZONE '{APP_TIMEZONE}')"

    return "datetime('now', 'localtime')"


def match_day_start_sql(column_name: str = "p.fecha_hora_partido") -> str:
    if is_postgres():
        return f"DATE_TRUNC('day', {column_name})"

    return f"datetime(date({column_name}))"


def match_has_teams_sql() -> str:
    return "p.id_equipo_local IS NOT NULL AND p.id_equipo_visitante IS NOT NULL"


# =========================================================
# PARTIDOS DISPONIBLES PARA PREDICCIÓN
# =========================================================

def get_available_matches(id_usuario: int) -> pd.DataFrame:
    """
    Muestra todos los partidos que ya tienen ambos equipos definidos.

    Reglas:
    - Se muestran desde ya.
    - Se bloquean a las 00:00 del día del partido en hora Colombia.
    - Si el usuario ya predijo, solo visualiza.
    - Si cerró y no predijo, se muestra el 0-0 automático.
    """

    sql = f"""
        SELECT
            p.id_partido,
            p.fase,
            p.grupo,
            el.nombre AS equipo_local,
            ev.nombre AS equipo_visitante,
            p.fecha_hora_partido,
            p.estado_partido,
            p.goles_local_real,
            p.goles_visitante_real,

            vp.fecha_apertura,
            vp.fecha_cierre,

            {match_day_start_sql("p.fecha_hora_partido")} AS fecha_cierre_automatica,

            pr.id_prediccion,
            COALESCE(pr.goles_local_predicho, 0) AS goles_local_predicho,
            COALESCE(pr.goles_visitante_predicho, 0) AS goles_visitante_predicho,
            COALESCE(pr.bloqueada, 0) AS bloqueada,

            CASE
                WHEN pr.id_prediccion IS NOT NULL THEN 1
                ELSE 0
            END AS ya_registro,

            CASE
                WHEN {now_colombia_sql()} >= {match_day_start_sql("p.fecha_hora_partido")}
                    THEN 'Cerrada'

                WHEN pr.id_prediccion IS NOT NULL
                    THEN 'Registrada'

                ELSE 'Abierta'
            END AS estado_ventana,

            CASE
                WHEN {now_colombia_sql()} < {match_day_start_sql("p.fecha_hora_partido")}
                 AND pr.id_prediccion IS NULL
                    THEN 1
                ELSE 0
            END AS puede_editar

        FROM partidos p
        INNER JOIN equipos el
            ON p.id_equipo_local = el.id_equipo
        INNER JOIN equipos ev
            ON p.id_equipo_visitante = ev.id_equipo
        LEFT JOIN ventanas_prediccion vp
            ON p.id_partido = vp.id_partido
        LEFT JOIN predicciones pr
            ON p.id_partido = pr.id_partido
           AND pr.id_usuario = :id_usuario

        WHERE {match_has_teams_sql()}

        ORDER BY
            p.fecha_hora_partido ASC,
            p.id_partido ASC
    """

    return fetch_df(sql, {"id_usuario": id_usuario})


# =========================================================
# VALIDACIÓN DE GUARDADO
# =========================================================

def can_create_prediction(id_usuario: int, id_partido: int) -> tuple[bool, str]:
    """
    Valida si un usuario puede crear una predicción.

    Reglas:
    - Solo participantes activos pueden predecir.
    - El admin no juega.
    - El partido debe tener ambos equipos definidos.
    - No puede estar cerrado.
    - No puede tener predicción previa.
    """

    sql = f"""
        SELECT
            p.id_partido,
            p.fecha_hora_partido,
            u.rol,
            u.estado_activo,
            pr.id_prediccion,

            CASE
                WHEN u.rol <> 'participante'
                    THEN 'El administrador no participa en la polla.'

                WHEN u.estado_activo <> 1
                    THEN 'El usuario está inactivo.'

                WHEN p.id_equipo_local IS NULL OR p.id_equipo_visitante IS NULL
                    THEN 'El partido aún no tiene ambos equipos definidos.'

                WHEN {now_colombia_sql()} >= {match_day_start_sql("p.fecha_hora_partido")}
                    THEN 'La predicción ya está cerrada. Solo se podía registrar hasta las 00:00 del día del partido.'

                WHEN pr.id_prediccion IS NOT NULL
                    THEN 'Ya registraste una predicción para este partido y no se puede modificar.'

                ELSE 'OK'
            END AS validacion

        FROM partidos p
        INNER JOIN usuarios u
            ON u.id_usuario = :id_usuario
        LEFT JOIN predicciones pr
            ON p.id_partido = pr.id_partido
           AND pr.id_usuario = :id_usuario
        WHERE p.id_partido = :id_partido
    """

    df = fetch_df(sql, {
        "id_usuario": id_usuario,
        "id_partido": id_partido,
    })

    if df.empty:
        return False, "No se encontró el partido."

    mensaje = str(df.iloc[0]["validacion"])

    if mensaje == "OK":
        return True, "Predicción permitida."

    return False, mensaje


# =========================================================
# GUARDAR PREDICCIÓN
# =========================================================

def save_prediction(
    id_usuario: int,
    id_partido: int,
    goles_local_predicho: int,
    goles_visitante_predicho: int,
) -> tuple[bool, str]:
    goles_local_predicho = int(goles_local_predicho)
    goles_visitante_predicho = int(goles_visitante_predicho)

    if goles_local_predicho < 0 or goles_visitante_predicho < 0:
        return False, "Los goles no pueden ser negativos."

    puede_guardar, mensaje = can_create_prediction(
        id_usuario=id_usuario,
        id_partido=id_partido,
    )

    if not puede_guardar:
        return False, mensaje

    sql = f"""
        INSERT INTO predicciones (
            id_usuario,
            id_partido,
            goles_local_predicho,
            goles_visitante_predicho,
            fecha_registro,
            fecha_actualizacion,
            bloqueada
        )
        VALUES (
            :id_usuario,
            :id_partido,
            :goles_local_predicho,
            :goles_visitante_predicho,
            {now_colombia_sql()},
            {now_colombia_sql()},
            1
        )
    """

    try:
        execute(sql, {
            "id_usuario": id_usuario,
            "id_partido": id_partido,
            "goles_local_predicho": goles_local_predicho,
            "goles_visitante_predicho": goles_visitante_predicho,
        })

        return True, "Predicción registrada correctamente. Ya no podrá ser modificada."

    except Exception as e:
        error_text = str(e).lower()

        if "unique" in error_text or "duplicate" in error_text:
            return False, "Ya existe una predicción registrada para este partido."

        return False, f"No se pudo guardar la predicción: {e}"


# =========================================================
# 0-0 POR DEFECTO PARA UN PARTICIPANTE
# =========================================================

def ensure_default_predictions(id_usuario: int) -> None:
    sql = f"""
        INSERT INTO predicciones (
            id_usuario,
            id_partido,
            goles_local_predicho,
            goles_visitante_predicho,
            fecha_registro,
            fecha_actualizacion,
            bloqueada
        )
        SELECT
            :id_usuario AS id_usuario,
            p.id_partido,
            0 AS goles_local_predicho,
            0 AS goles_visitante_predicho,
            {now_colombia_sql()} AS fecha_registro,
            {now_colombia_sql()} AS fecha_actualizacion,
            1 AS bloqueada
        FROM partidos p
        INNER JOIN usuarios u
            ON u.id_usuario = :id_usuario
        WHERE u.rol = 'participante'
          AND u.estado_activo = 1
          AND {match_has_teams_sql()}
          AND {now_colombia_sql()} >= {match_day_start_sql("p.fecha_hora_partido")}
          AND NOT EXISTS (
                SELECT 1
                FROM predicciones pr
                WHERE pr.id_usuario = :id_usuario
                  AND pr.id_partido = p.id_partido
          )
    """

    execute(sql, {"id_usuario": id_usuario})


# =========================================================
# 0-0 POR DEFECTO PARA TODOS LOS PARTICIPANTES
# =========================================================

def ensure_default_predictions_for_all_participants() -> None:
    """
    Crea 0-0 para todos los participantes activos cuando un partido ya cerró.

    - Solo participantes.
    - Admin excluido.
    - Solo partidos con ambos equipos definidos.
    - No modifica predicciones existentes.
    """

    sql = f"""
        INSERT INTO predicciones (
            id_usuario,
            id_partido,
            goles_local_predicho,
            goles_visitante_predicho,
            fecha_registro,
            fecha_actualizacion,
            bloqueada
        )
        SELECT
            u.id_usuario,
            p.id_partido,
            0 AS goles_local_predicho,
            0 AS goles_visitante_predicho,
            {now_colombia_sql()} AS fecha_registro,
            {now_colombia_sql()} AS fecha_actualizacion,
            1 AS bloqueada
        FROM usuarios u
        CROSS JOIN partidos p
        WHERE u.rol = 'participante'
          AND u.estado_activo = 1
          AND {match_has_teams_sql()}
          AND {now_colombia_sql()} >= {match_day_start_sql("p.fecha_hora_partido")}
          AND NOT EXISTS (
                SELECT 1
                FROM predicciones pr
                WHERE pr.id_usuario = u.id_usuario
                  AND pr.id_partido = p.id_partido
          )
    """

    execute(sql)


def create_default_predictions_for_closed_matches(id_usuario: int | None = None) -> None:
    if id_usuario is None:
        ensure_default_predictions_for_all_participants()
        return

    ensure_default_predictions(id_usuario)


# =========================================================
# BLOQUEO DE PREDICCIONES VENCIDAS
# =========================================================

def lock_expired_predictions() -> None:
    sql = f"""
        UPDATE predicciones
        SET bloqueada = 1
        WHERE id_partido IN (
            SELECT id_partido
            FROM partidos p
            WHERE {match_has_teams_sql()}
              AND {now_colombia_sql()} >= {match_day_start_sql("p.fecha_hora_partido")}
        )
    """

    execute(sql)


# =========================================================
# CONSULTA DE PREDICCIONES DEL USUARIO
# =========================================================

def get_user_predictions(id_usuario: int) -> pd.DataFrame:
    sql = """
        SELECT
            pr.id_prediccion,
            pr.id_usuario,
            pr.id_partido,
            p.fase,
            p.grupo,
            el.nombre AS equipo_local,
            ev.nombre AS equipo_visitante,
            p.fecha_hora_partido,
            p.estado_partido,
            pr.goles_local_predicho,
            pr.goles_visitante_predicho,
            pr.fecha_registro,
            pr.fecha_actualizacion,
            pr.bloqueada
        FROM predicciones pr
        INNER JOIN partidos p
            ON pr.id_partido = p.id_partido
        INNER JOIN equipos el
            ON p.id_equipo_local = el.id_equipo
        INNER JOIN equipos ev
            ON p.id_equipo_visitante = ev.id_equipo
        WHERE pr.id_usuario = :id_usuario
        ORDER BY p.fecha_hora_partido ASC
    """

    return fetch_df(sql, {"id_usuario": id_usuario})