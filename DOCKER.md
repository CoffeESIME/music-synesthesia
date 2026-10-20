# Proyecto Sinestesia en Docker

La imagen usa Python 3.11 sobre Debian Bookworm. El modo predeterminado es web,
sin puente ni luces Hue y sin dependencias de captura de audio nativo.
FFmpeg queda disponible para analizar pistas MP3.

## Arranque habitual

1. Puedes arrancar sin archivo `.env`. Si necesitas ajustar puertos, copia
   `.env.example` a `.env` y deja `HUE_ENABLED=false`.
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

## Instalación local con Hue

En `.env`, configura `BRIDGE_IP`, `HUE_APPLICATION_KEY` y `HUE_LIGHT_IDS`
(IDs separados por comas). Activa la integración con el archivo adicional:

```powershell
docker-compose -f compose.yaml -f compose.hue.yaml up --build -d
```

También puedes usar solamente `compose.yaml` con `HUE_ENABLED=true` en `.env`.
Al activar Hue se validan las credenciales y la lista de luces al arrancar.
El navegador de cada participante controla las mismas luces del servidor.
Para volver al modo web, deja `HUE_ENABLED=false` y ejecuta el arranque habitual.
Las credenciales existentes se ignoran mientras Hue esté desactivado.

## Compartir la idea por Internet

Despliega la imagen en un servidor que ejecute contenedores y publica el puerto
interno `8765` detrás de un dominio con HTTPS y certificado público válido.
Configura `HUE_ENABLED=false`. El servicio `https` incluido en Compose es para
la red local; para Internet utiliza el HTTPS de tu alojamiento o proxy.

Las personas abren la misma URL desde su navegador o teléfono, sin instalar la
app ni tener Hue. Cada sesión mantiene su propio perfil, micrófono y visualización;
en modo web no se envían comandos de luces ni se abre el stream de colores compartido.
El micrófono se analiza en el dispositivo. Los archivos WAV/MP3 se suben al servidor
para su análisis y necesitan espacio temporal. Sigue siendo una app con backend
Python, por lo que requiere un alojamiento que ejecute ese backend.

Para ejecutar sin Docker (Python 3.11):

```powershell
python -m pip install -r requirements.txt
$env:HUE_ENABLED = "false"
python -m uvicorn api.main:app --host 0.0.0.0 --port 8765
```

El punto de entrada de esta app es `api.main:app`. `main.py` corresponde al
prototipo anterior de imágenes. Para MP3 sin Docker, instala también FFmpeg.

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
docker-compose -f compose.yaml -f compose.hue.yaml -f compose.audio-linux.yaml up --build -d
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
