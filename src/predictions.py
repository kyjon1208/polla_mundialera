from __future__ import annotations

import pandas as pd

from src.db import execute, fetch_df


# =========================================================
# CONFIGURACIÓN DE ZONA HORARIA
# =========================================================

APP_TIMEZONE = "America/Bogota"


def now_colombia_sql() -> str:
    """
    Fecha/hora actual en hora Colombia para PostgreSQL/Supabase.

    Se usa para que el cierre de predicciones sea según hora Colombia,
    no según la hora UTC del servidor.
    """
    return f"(CURRENT_TIMESTAMP AT TIME ZONE '{APP_TIMEZONE}')"


def match_day_start_sql(column_name: str = "p.fecha_hora_partido") -> str:
    """
    Retorna las 00:00 del día del partido.

    Ejemplo:
    fecha_hora_partido = 2026-06-15 20:00:00
    resultado = 2026-06-15 00:00:00
    """
    return f"DATE_TRUNC('day', {column_name})"


# =========================================================
# CONSULTA DE PARTIDOS DISPONIBLES
# =========================================================

def get_available_matches(id_usuario: int) -> pd.DataFrame:
    """
    Retorna los partidos visibles para predicción.

    Reglas:
    - El partido se muestra si ya llegó la fecha de apertura.
    - El cierre automático es a las 00:00 del día del partido en hora Colombia.
    - Si el usuario ya registró una predicción, no puede editarla.
    - Si no registró y ya cerró el tiempo, juega con 0-0 por defecto.
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
                WHEN {now_colombia_sql()} < vp.fecha_apertura
                    THEN 'No disponible'

                WHEN {now_colombia_sql()} >= {match_day_start_sql("p.fecha_hora_partido")}
                    THEN 'Cerrada'

                WHEN pr.id_prediccion IS NOT NULL
                    THEN 'Registrada'

                ELSE 'Abierta'
            END AS estado_ventana,

            CASE
                WHEN {now_colombia_sql()} >= vp.fecha_apertura
                 AND {now_colombia_sql()} < {match_day_start_sql("p.fecha_hora_partido")}
                 AND pr.id_prediccion IS NULL
                    THEN 1
                ELSE 0
            END AS puede_editar

        FROM partidos p
        INNER JOIN equipos el
            ON p.id_equipo_local = el.id_equipo
        INNER JOIN equipos ev
            ON p.id_equipo_visitante = ev.id_equipo
        INNER JOIN ventanas_prediccion vp
            ON p.id_partido = vp.id_partido
        LEFT JOIN predicciones pr
            ON p.id_partido = pr.id_partido
           AND pr.id_usuario = :id_usuario

        WHERE {now_colombia_sql()} >= vp.fecha_apertura

        ORDER BY
            p.fecha_hora_partido ASC,
            p.id_partido ASC
    """

    return fetch_df(sql, {
        "id_usuario": id_usuario
    })


# =========================================================
# VALIDACIÓN DE GUARDADO
# =========================================================

def can_create_prediction(id_usuario: int, id_partido: int) -> tuple[bool, str]:
    """
    Valida si el usuario puede crear una predicción.

    Reglas:
    - Debe estar dentro del tiempo permitido.
    - El cierre es a las 00:00 del día del partido en hora Colombia.
    - Si ya existe predicción, no permite actualizar.
    """

    sql = f"""
        SELECT
            p.id_partido,
            p.fecha_hora_partido,
            vp.fecha_apertura,
            {match_day_start_sql("p.fecha_hora_partido")} AS fecha_cierre_automatica,
            pr.id_prediccion,

            CASE
                WHEN {now_colombia_sql()} < vp.fecha_apertura
                    THEN 'La ventana de predicción aún no está abierta.'

                WHEN {now_colombia_sql()} >= {match_day_start_sql("p.fecha_hora_partido")}
                    THEN 'La predicción ya está cerrada. Solo se podía registrar hasta las 00:00 del día del partido.'

                WHEN pr.id_prediccion IS NOT NULL
                    THEN 'Ya registraste una predicción para este partido y no se puede modificar.'

                ELSE 'OK'
            END AS validacion

        FROM partidos p
        INNER JOIN ventanas_prediccion vp
            ON p.id_partido = vp.id_partido
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
    """
    Guarda la predicción del usuario.

    Importante:
    - Solo permite INSERT.
    - No permite UPDATE.
    - Una vez registrada, queda bloqueada.
    """

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
# PREDICCIONES 0-0 POR DEFECTO PARA UN USUARIO
# =========================================================

def ensure_default_predictions(id_usuario: int) -> None:
    """
    Crea predicciones 0-0 por defecto para un usuario específico
    en partidos cuyo tiempo de predicción ya cerró.

    Solo aplica si el usuario es participante activo.
    No aplica para admin.
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
            :id_usuario AS id_usuario,
            p.id_partido,
            0 AS goles_local_predicho,
            0 AS goles_visitante_predicho,
            {now_colombia_sql()} AS fecha_registro,
            {now_colombia_sql()} AS fecha_actualizacion,
            1 AS bloqueada
        FROM partidos p
        INNER JOIN ventanas_prediccion vp
            ON p.id_partido = vp.id_partido
        INNER JOIN usuarios u
            ON u.id_usuario = :id_usuario
        WHERE u.rol = 'participante'
          AND u.estado_activo = 1
          AND {now_colombia_sql()} >= {match_day_start_sql("p.fecha_hora_partido")}
          AND NOT EXISTS (
                SELECT 1
                FROM predicciones pr
                WHERE pr.id_usuario = :id_usuario
                  AND pr.id_partido = p.id_partido
          )
    """

    execute(sql, {
        "id_usuario": id_usuario
    })


# =========================================================
# PREDICCIONES 0-0 POR DEFECTO PARA TODOS LOS PARTICIPANTES
# =========================================================

def ensure_default_predictions_for_all_participants() -> None:
    """
    Crea predicciones 0-0 por defecto para todos los participantes activos
    en partidos cuyo tiempo de predicción ya cerró.

    Reglas:
    - Solo usuarios con rol = 'participante'.
    - Solo usuarios activos.
    - No aplica para admin.
    - Si ya existe predicción, no la modifica.
    - El cierre se calcula a las 00:00 del día del partido en hora Colombia.
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
        INNER JOIN ventanas_prediccion vp
            ON p.id_partido = vp.id_partido
        WHERE u.rol = 'participante'
          AND u.estado_activo = 1
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
    """
    Alias de compatibilidad para páginas anteriores.

    Si recibe id_usuario:
    - Crea 0-0 solo para ese usuario, siempre que sea participante.

    Si no recibe id_usuario:
    - Crea 0-0 para todos los participantes activos.
    """
    if id_usuario is None:
        ensure_default_predictions_for_all_participants()
        return

    ensure_default_predictions(id_usuario)


# =========================================================
# BLOQUEO DE PREDICCIONES VENCIDAS
# =========================================================

def lock_expired_predictions() -> None:
    """
    Bloquea predicciones cuando ya llegó la fecha del partido a las 00:00
    en hora Colombia.
    """

    sql = f"""
        UPDATE predicciones
        SET bloqueada = 1
        WHERE id_partido IN (
            SELECT id_partido
            FROM partidos
            WHERE {now_colombia_sql()} >= {match_day_start_sql("fecha_hora_partido")}
        )
    """

    execute(sql)


# =========================================================
# CONSULTA DE PREDICCIONES DEL USUARIO
# =========================================================

def get_user_predictions(id_usuario: int) -> pd.DataFrame:
    """
    Retorna todas las predicciones registradas por un usuario.
    """

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

    return fetch_df(sql, {
        "id_usuario": id_usuario
    })