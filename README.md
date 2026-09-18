# AMapp

Aplicación Streamlit para importar, almacenar y visualizar mediciones eléctricas I-V y tracks Vt de dispositivos electrónicos.

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

Las mediciones tienen además el flag `eliminado`. No borra puntos ni metadatos: las excluye de las consultas y cálculos activos, y se puede activar o quitar desde `Importar / Exportar` -> `Visualizar base de datos` -> `Mediciones`. Al guardar un cambio en ese flag, las campañas afectadas recalculan automáticamente su ZTC; si ya no quedan al menos dos temperaturas válidas, se elimina el resultado guardado.

Las filas inválidas se informan sin detener la importación. Las mediciones ya existentes en la misma campaña y archivo se ignoran.

También se aceptan libros con hojas de mediciones exportadas por el instrumento. Las hojas con columnas `V` e `I` se importan como curvas I-V. Las hojas con bloques `t [s]` y `Vt [V]` se importan como Track Vt, separados por dispositivo y canal. Los Track Vt se visualizan y exportan, pero no participan todavía en el análisis ZTC.

La identificación de dispositivos es genérica: se toma el primer bloque numérico posterior a un prefijo que contenga letras, se guarda el `tag`, el `numero` y el nombre canónico. Las hojas que no sean I-V ni Track Vt se conservan en `Sin clasificar` para revisión y exportación posterior.

## Uso

1. Subir el Excel desde `Importar / Exportar`.
2. Seleccionar dispositivo, campaña y medición en `Mediciones`.
3. Consultar las curvas y ejecutar `Analisis ZTC`.
4. Descargar la base y resultados desde `Importar / Exportar`.

La navegación separa `I-V`, `Track Vt` y `Análisis ZTC`. El menú `Workbench` incluye un comparador de múltiples dispositivos y campañas, un explorador de todas las curvas I-V y Track Vt de un dispositivo, y un panel de matching para reasignar una medición a la campaña correcta y exportar el estado en CSV.

`Análisis ZTC` trabaja únicamente con barridos que tienen una temperatura numérica identificable en el nombre o metadatos. Acepta formatos como `T20`, `temp 20`, `20 °C` y `36 grados`; excluye `sin temp`, `TXX`, `temperatura` sin número y nombres sin temperatura.

Para cada campaña se calcula y muestra un único resultado combinado:

- El componente de pendiente `dI/dT` interpola linealmente las curvas en el intervalo de tensión común y ajusta la corriente contra la temperatura para cada `VT`.
- El componente de error relativo usa `max(I)-min(I)` dividido por la corriente media absoluta.
- El score combinado da prioridad a cruces reales de pendiente y usa el error relativo como desempate/localización secundaria. La corriente de 50–300 µA no se impone como filtro del análisis; solo puede usarse para evaluar variantes automáticas durante pruebas.

La aplicación usa un objetivo `combinado` como resultado ZTC principal: normaliza `|dI/dT|` y el error relativo con escalas robustas, prioriza candidatos donde la pendiente cambia de signo y minimiza ambos términos. La vista de Evolución permite elegir un único dispositivo, guardar el conjunto de campañas, ver la progresión de `I ZTC` y consultar la dispersión de todas las campañas seleccionadas en un dashboard de dos columnas. La comparación automática entre dispositivos vive dentro de `Análisis ZTC` y entrega una tabla y gráficos seleccionables para revisión manual.

Falsos positivos conocidos y corregidos: `sin temp` antes podía tomar el número de campaña como temperatura; `TXX` no representa una temperatura numérica; `temperatura` sola tampoco alcanza. Todos quedan fuera del análisis hasta que se agregue un valor explícito.

El flujo actual es semiautomático: el cálculo genera resultados y métricas comparables, mientras que el usuario puede revisar cada curva, su dispersión y los dos métodos. Esto deja preparada una futura separación entre cálculo manual de detalle, análisis automático exploratorio y validación manual final.

El cálculo combinado ajusta `I(V,T)` por regresión lineal en temperatura para cada tensión común. Para elegir entre varios cruces de `dI/dT = 0`, usa la estabilidad local de la pendiente y el error relativo de las curvas alrededor del cruce, en vez de evaluar únicamente el punto exacto donde la pendiente interpolada vale cero. La corriente se conserva en amperes internamente y solo se convierte a µA al mostrarla. No hay datos de mediciones incluidos en el repositorio, por lo que los casos concretos de 300 µA y 30 µA deben revisarse importando esas curvas y mirando la tabla de candidatos y la dispersión local.

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
