-- Usuario admin de ejemplo: admin / admin123
-- Hash generado con bcrypt. Cámbialo antes de producción.
INSERT OR IGNORE INTO usuarios (usuario, clave_hash, nombre, rol, estado_activo)
VALUES ('admin', '$2b$12$sROJhSP/i8oqaBHloATz2uG6OGrGV5cU5T7./G7Pm/LZw3jgODHIa', 'Administrador', 'admin', 1);

INSERT OR IGNORE INTO equipos (nombre, grupo, codigo_fifa) VALUES
('Colombia', 'A', 'COL'),
('Brasil', 'A', 'BRA'),
('Argentina', 'B', 'ARG'),
('Uruguay', 'B', 'URU');

INSERT INTO partidos (fase, grupo, id_equipo_local, id_equipo_visitante, fecha_hora_partido, estado_partido)
SELECT 'Fase de Grupos', 'A', el.id_equipo, ev.id_equipo, '2026-06-11 19:00:00', 'Sin comenzar'
FROM equipos el, equipos ev
WHERE el.codigo_fifa = 'COL' AND ev.codigo_fifa = 'BRA';

INSERT INTO ventanas_prediccion (id_partido, fecha_apertura, fecha_cierre)
SELECT id_partido, '2026-06-01 00:00:00', '2026-06-11 18:50:00'
FROM partidos
WHERE api_match_id IS NULL
ORDER BY id_partido DESC
LIMIT 1;
