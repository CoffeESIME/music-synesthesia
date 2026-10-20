# Despliegue en Vercel

El proyecto usa el preset **FastAPI**, con la raíz del repositorio como Root
Directory. `pyproject.toml` configura `api.main:app` como punto de entrada;
`main.py` es el prototipo anterior de imágenes y no debe usarse para este deploy.
Vercel instala las dependencias declaradas en `[project.dependencies]` de
`pyproject.toml` mediante `uv`. Mantén esa lista sincronizada con
`requirements.txt`, usado por Docker y la instalación con pip. El rango de
Python es 3.11–3.12, compatible con NumPy 1.26.4; Vercel debe usar Python 3.12.

En las variables de entorno de Vercel configura `HUE_ENABLED=false`. El modo web
usa el micrófono del navegador y no necesita credenciales ni dispositivos Hue.

Después de subir estos cambios al repositorio conectado, realiza un nuevo
deployment. Comprueba `/`, `/api/status` y `/api/profiles` en la URL publicada.
Si vuelve a fallar, revisa los Runtime Logs de ese nuevo deployment.

Con `VERCEL=1`, los audios se guardan en el directorio temporal del sistema,
fuera del código de la función. Ese almacenamiento es efímero y no se comparte
entre instancias: la reproducción posterior en `/temp/...` puede llegar a otra
instancia que no tenga el archivo. Para conservar y compartir pistas hace falta
almacenamiento externo o el despliegue con contenedores descrito en `DOCKER.md`.
Los límites de subida y ejecución de Vercel también se aplican aunque la API
local acepte archivos de hasta 250 MB.
