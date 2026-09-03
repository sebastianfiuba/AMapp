# AMapp

Aplicación Streamlit para importar, almacenar, visualizar y analizar mediciones eléctricas I-V de dispositivos electrónicos.

## Instalación local

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Formato Excel

El archivo `.xlsx` debe contener una hoja plana con las columnas obligatorias `dispositivo`, `campaña` (o `campana`), `medición` (o `medicion`), `V` e `I`. Cada fila es un punto; las filas con el mismo dispositivo, campaña y medición forman una curva. Se aceptan alias en inglés (`device`, `campaign`, `measurement`, `voltage`, `current`). Son opcionales `fecha`, `descripcion`, `clase` y `estado`.

Las filas inválidas se informan sin detener la importación. Las mediciones ya existentes en la misma campaña y archivo se ignoran.

## Uso

1. Subir el Excel desde `Importar / Exportar`.
2. Seleccionar dispositivo, campaña y medición en `Mediciones`.
3. Consultar las curvas y ejecutar `Analisis ZTC`.
4. Descargar la base y resultados desde `Importar / Exportar`.

El análisis usa spline cúbica sin extrapolar. Con varias mediciones busca el mínimo de `Imax(V) - Imin(V)` en el intervalo común y promedia todas las curvas. Con una sola medición calcula el punto de la curva individual.

## Arquitectura y persistencia

La interfaz (`ui`), servicios (`services`) y persistencia (`database`) están separadas. `database/repository.py` es el límite de acceso a datos para facilitar una futura migración a PostgreSQL o Supabase.

El MVP usa SQLite en `data/mediciones.db`, excluido de Git. En Streamlit Community Cloud el filesystem no es almacenamiento persistente de producción: los datos pueden perderse al reiniciar o redeplegar. Para producción, sustituir el repositorio por una base remota.

## GitHub

```bash
git init
git add .
git commit -m "Crear MVP AMapp"
git branch -M main
git remote add origin https://github.com/USUARIO/REPOSITORIO.git
git push -u origin main
```

## Deploy en Streamlit Community Cloud

1. Crear el repositorio en GitHub y subir el proyecto.
2. Entrar en [share.streamlit.io](https://share.streamlit.io/) con GitHub.
3. Elegir `New app`.
4. Seleccionar el repositorio, branch `main` y archivo principal `app.py`.
5. Pulsar `Deploy`.

Cloud instalará automáticamente `requirements.txt`. No hay secretos necesarios; para futuras credenciales usar `st.secrets`. La app también arranca localmente con `streamlit run app.py`.
