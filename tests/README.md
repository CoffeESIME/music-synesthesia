# Visualizador

`visualizer.browser.cjs` comprueba la interfaz en Chrome con Playwright y respuestas
simuladas de la API y el WebSocket. No conecta con Hue ni abre el micrófono.

Requiere Node.js, Chrome y Playwright disponible como paquete (o la variable
`PLAYWRIGHT_MODULE` con la ruta al paquete instalado). Ejecutar desde el proyecto:

```powershell
node tests/visualizer.browser.cjs
node tests/microphone.browser.cjs
```

Las capturas se guardan en el directorio temporal `hue-visualizer-check` o en
`VISUALIZER_OUTPUT_DIR` si se define. Verifica las 12 formas, la señal WebSocket,
el cambio de perfil, la posición de la pista, las vistas, la pausa visual,
movimiento reducido, el ancho móvil y pantalla completa.

La prueba de micrófono utiliza audio sintético y el dispositivo simulado de
Chrome. Comprueba 96 señales tonales, silencio, permisos denegados/cancelados,
liberación del dispositivo, exclusión entre pista y micrófono y mensajes de
HTTPS en red local. No captura el micrófono real ni controla luces reales.

Las formas son una interpretación artística de la clase de nota (C–B). No
representan frecuencia, octava, volumen ni una simulación física de una placa.
El visualizador reutiliza los eventos de color existentes y conserva la última
forma cuando se detiene la reproducción. La pausa visual mantiene actualizadas
la nota y el color. Para verificar la integración real, iniciar la app habitual,
probar una nota por micrófono y una pista WAV/MP3, y comprobar las luces Hue.
