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

3. En esta computadora abre <http://127.0.0.1:18743>. Desde otro dispositivo
   de la misma red, abre `http://<IPv4-de-la-computadora>:18743`.
   Puedes consultar esa IPv4 con `ipconfig` (adaptador Ethernet o Wi-Fi activo).
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

La configuración predeterminada `SINESTESIA_BIND_IP=0.0.0.0` permite conexiones
desde otros equipos de la red local. Si tu `.env` contiene `127.0.0.1`, cambia
ese valor a `0.0.0.0`. Para limitar el acceso a esta computadora, usa `127.0.0.1`.
Después de cambiar la dirección o el puerto, ejecuta `docker-compose up -d`
para recrear el servicio; reiniciarlo no cambia los puertos publicados.

Si Windows bloquea conexiones entrantes, permite TCP en el puerto publicado
(`18743` por defecto) desde la subred local en el Firewall de Windows. Usa
siempre el puerto en la URL. Las peticiones de la API y el WebSocket emplean
automáticamente la misma dirección con la que abriste la página.

Para crear la regla en Windows, abre PowerShell como administrador y ejecuta
desde este proyecto (la conexión debe estar clasificada como red privada):

```powershell
.\scripts\enable-lan.ps1
# Si cambiaste el puerto: .\scripts\enable-lan.ps1 -Port 28743
```

## Micrófono

El botón **Iniciar escucha** solicita el micrófono del dispositivo donde está
abierto el navegador. El audio se analiza localmente; solo se envían colores al
servidor. No se reproduce el micrófono por los altavoces. **Detener**, reproducir
una pista o cerrar la página libera el micrófono.

En la computadora del servidor puedes usar <http://localhost:18743>. Desde
otro dispositivo se necesita HTTPS y permiso de micrófono:

1. Configura `SINESTESIA_LAN_HOST` en `.env` con la IPv4 del servidor (por ejemplo,
   `192.168.50.131`). `SINESTESIA_HTTPS_PORT` vale `18744` por defecto.
2. Ejecuta `docker-compose up --build -d`. El servicio `https` usa Caddy y conserva
   su autoridad certificadora local en el volumen `caddy_data`.
3. Exporta **solo el certificado público** de esa autoridad:

   ```powershell
   docker-compose cp https:/data/caddy/pki/authorities/local/root.crt certificates/local-ca.crt
   ```

4. En PowerShell como administrador, permite el puerto HTTPS en la red privada:

   ```powershell
   .\scripts\enable-lan.ps1 -Port 18744
   ```

5. Instala `certificates/local-ca.crt` como certificado de autoridad de confianza
   en cada dispositivo que vaya a usar el micrófono. La página HTTP incluye un
   enlace de descarga. En Windows se importa en **Entidades de certificación raíz
   de confianza** del usuario; en móviles usa la instalación de certificados de
   su sistema (en iOS también hay que activar la confianza del certificado raíz).
   No copies claves privadas ni borres el volumen `caddy_data` al reiniciar.
6. Abre `https://<IPv4-del-servidor>:18744`, comprueba que el navegador confía en
   el certificado y pulsa **Iniciar escucha**. Concede el permiso de micrófono.

Si cambia la IP del servidor, actualiza `SINESTESIA_LAN_HOST` y ejecuta
`docker-compose up -d`; la autoridad local permanece, pero Caddy emitirá un
certificado para la nueva IP. La reproducción de WAV/MP3 no requiere micrófono
y continúa disponible por HTTP.

Referencias: [micrófono y contextos seguros (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)
y [HTTPS local y confianza de certificados (Caddy)](https://caddyserver.com/docs/automatic-https).

La API de escucha del servidor se conserva para instalaciones Linux con ALSA.
Ese modo requiere un dispositivo de sonido dentro del contenedor:

```bash
docker-compose -f compose.yaml -f compose.audio-linux.yaml up --build -d
```

Docker Desktop en Windows no expone el micrófono como `/dev/snd` en esta
configuración. El error `Invalid input device` corresponde a ese modo del
servidor; la interfaz usa ahora el micrófono del navegador.

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
