# Polla Mundialera 2026 - MVP Streamlit

Aplicación base en Python para administrar una polla mundialera:

- Login por usuario y clave asignada por administrador.
- Registro y edición de predicciones dentro de ventanas de tiempo.
- Consulta de criterios de puntuación.
- Resultados del Mundial con estado del partido.
- Tabla de posiciones con desempates.
- Pantalla temporal de pruebas para simular resultados.

## Ejecución local

```bash
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
streamlit run app.py
```

## Cargar datos iniciales en SQLite

La app crea las tablas automáticamente en modo SQLite. Luego puedes cargar criterios y datos de prueba ejecutando los scripts SQL en `sql/`.

Usuario admin de ejemplo: `admin`  
Clave: `admin123`

Cambia esa clave antes de usarlo en producción. El primo que acierta todos los marcadores no necesita ayuda extra.

## Despliegue recomendado

- GitHub para el repositorio.
- Streamlit Community Cloud para publicar el link.
- Supabase PostgreSQL para datos reales multiusuario.

## Archivos principales

- `app.py`: login y pantalla inicial.
- `pages/1_Predicciones.py`: predicciones de usuarios.
- `pages/2_Posiciones.py`: ranking y recálculo.
- `pages/3_Criterios.py`: criterios de puntuación.
- `pages/4_Resultados_Mundial.py`: resultados y estado de partidos.
- `pages/5_Pruebas_Admin.py`: pruebas manuales para administrador.
- `src/scoring.py`: motor de puntuación.
- `src/db.py`: conexión SQLite/PostgreSQL.
- `sql/`: scripts de creación e inserción.
