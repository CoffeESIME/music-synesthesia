# Proyecto Sinestesia en Docker

La imagen usa Python 3.11 sobre Debian Bookworm. PortAudio, libsndfile y la
compilacion de aubio quedan resueltos dentro de Linux, sin depender del Python
instalado en Windows. FFmpeg queda disponible para analizar pistas MP3.

## Arranque habitual

1. Configura `.env` con `BRIDGE_IP`, `HUE_APPLICATION_KEY` y
   `HUE_LIGHT_IDS`. Los IDs se separan con comas.
2. Construye y levanta el servicio:

   ```powershell
   docker-compose up --build -d
   ```

3. Abre <http://127.0.0.1:18743>.
4. Consulta el estado:

   ```powershell
   docker-compose ps
   docker-compose logs -f app
   ```

Para detenerlo:

```powershell
docker-compose down
```

## Cambiar el puerto publicado

El contenedor escucha internamente en `8765`; el host publica `18743` de forma
predeterminada. Puedes elegir otro puerto sin editar Compose:

```powershell
$env:SINESTESIA_HOST_PORT = "28743"
docker-compose up --build -d
```

Para permitir acceso desde otros equipos de la red local, configura con cuidado
`SINESTESIA_BIND_IP=0.0.0.0` en `.env`. El valor predeterminado `127.0.0.1` solo
expone la interfaz en la computadora anfitriona.

## Micrófono

PyAudio dentro del contenedor necesita un dispositivo de sonido Linux. En un
host Linux con ALSA, usa el override incluido:

```bash
docker-compose -f compose.yaml -f compose.audio-linux.yaml up --build -d
```

Docker Desktop en Windows no expone normalmente el micrófono como `/dev/snd`.
La imagen elimina los problemas de compilacion de PyAudio y aubio, pero no puede
crear un dispositivo de audio que Docker Desktop no publica. En Windows, la UI
y el control Hue funcionan dentro del contenedor; para captura en vivo hace
falta exponer audio al contenedor o añadir captura desde el navegador.

## Decisiones operativas

- Se usa un solo worker de Uvicorn porque el micrófono y el motor son recursos
  únicos del proceso.
- `.env` está excluido de la imagen para proteger la clave de aplicación Hue.
- El proceso se ejecuta como usuario sin privilegios, con filesystem de solo
  lectura y todas las capabilities eliminadas.
- Las pistas cargadas se guardan en un `tmpfs` de 512 MB y desaparecen al
  recrear el contenedor.
- La cache de Numba/librosa usa el `tmpfs` de `/tmp`, por lo que funciona con
  el filesystem de la imagen en modo de solo lectura.

Si tu instalacion incluye el plugin moderno, puedes sustituir
`docker-compose` por `docker compose` en todos los comandos.
