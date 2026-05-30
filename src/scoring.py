"""Motor de puntuación de la Polla Mundialera.

Se asume un único criterio ganador por partido. El orden de evaluación evita que se
acumulen puntos de reglas que se traslapan.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreResult:
    criterio: str
    puntos: int
    marcador_completo: int = 0
    acierto_ganador_empate: int = 0
    diferencia_directa: int = 0


def _outcome(local: int, visitante: int) -> str:
    if local > visitante:
        return "LOCAL"
    if local < visitante:
        return "VISITANTE"
    return "EMPATE"


def _diff(local: int, visitante: int) -> int:
    return local - visitante


def _get_points(criteria: dict[str, int], name: str) -> int:
    return int(criteria.get(name, 0))


def evaluate_prediction(
    pred_local: int,
    pred_visitante: int,
    real_local: int,
    real_visitante: int,
    criteria_points: dict[str, int],
) -> ScoreResult:
    """Evalúa una predicción contra el resultado real.

    Args:
        pred_local: goles predichos del equipo local.
        pred_visitante: goles predichos del equipo visitante.
        real_local: goles reales del equipo local.
        real_visitante: goles reales del equipo visitante.
        criteria_points: diccionario {nombre_criterio: puntos} para la fase.
    """
    pred_outcome = _outcome(pred_local, pred_visitante)
    real_outcome = _outcome(real_local, real_visitante)
    pred_diff = _diff(pred_local, pred_visitante)
    real_diff = _diff(real_local, real_visitante)

    same_outcome = pred_outcome == real_outcome
    same_diff = pred_diff == real_diff
    inverse_score = pred_local == real_visitante and pred_visitante == real_local
    inverse_diff = pred_diff == -real_diff
    half_score = pred_local == real_local or pred_visitante == real_visitante

    if pred_local == real_local and pred_visitante == real_visitante:
        return ScoreResult("Marcador Completo", _get_points(criteria_points, "Marcador Completo"), 1, 1, 1)

    if real_outcome == "EMPATE" and pred_outcome == "EMPATE":
        return ScoreResult("Acierto de Empate", _get_points(criteria_points, "Acierto de Empate"), 0, 1, 1)

    if inverse_score:
        return ScoreResult("Acierto de Marcador Inverso", _get_points(criteria_points, "Acierto de Marcador Inverso"))

    if same_outcome and same_diff:
        return ScoreResult("Acierto ganador y diferencia directa", _get_points(criteria_points, "Acierto ganador y diferencia directa"), 0, 1, 1)

    if same_outcome and half_score:
        return ScoreResult("Acierto de ganador y medio marcador", _get_points(criteria_points, "Acierto de ganador y medio marcador"), 0, 1, 0)

    if same_outcome:
        return ScoreResult("Solo acierto de ganador", _get_points(criteria_points, "Solo acierto de ganador"), 0, 1, 0)

    if same_diff:
        return ScoreResult("Solo diferencia de goles directa", _get_points(criteria_points, "Solo diferencia de goles directa"), 0, 0, 1)

    if half_score and inverse_diff:
        return ScoreResult("Medio marcador y diferencia inversa", _get_points(criteria_points, "Medio marcador y diferencia inversa"))

    if inverse_diff:
        return ScoreResult("Solo diferencia de goles inversa", _get_points(criteria_points, "Solo diferencia de goles inversa"))

    if half_score:
        return ScoreResult("Solo medio marcador", _get_points(criteria_points, "Solo medio marcador"))

    return ScoreResult("Sin acierto", 0)
