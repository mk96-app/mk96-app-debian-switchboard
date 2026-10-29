# mk96-app-debian-switchboard

**MK96 Debian Switchboard**: applet de bandeja para Ubuntu/GNOME (Wayland) con accesos rápidos
a acciones del sistema que Linux ya soporta pero no expone con un clic.

Desde un único icono en la bandeja puedes controlar el audio (salida, volumen, mute y
mezclador por aplicación), la luz nocturna, el modo No molestar, el perfil de energía, las
redes Wi-Fi guardadas y los dispositivos Bluetooth emparejados.

## Qué hace

El menú de la bandeja se organiza en submenús por tema. La etiqueta de cada grupo muestra el
estado actual (volumen, luz nocturna / no molestar, perfil de energía y batería, Wi-Fi activa
y Bluetooth conectados).

| Grupo | Herramientas |
|---|---|
| **Audio** | Abrir el panel de audio, silenciar la salida, silenciar el micrófono, elegir la salida por defecto (la activa va marcada con `●`) y acceso a los Ajustes de sonido |
| **Pantalla** | Luz nocturna (on/off), No molestar (el mismo interruptor que usa GNOME para los banners) y acceso a los Ajustes de pantalla |
| **Energía** | Cambiar el perfil de energía (vía `power-profiles-daemon`) y ver el estado de la batería (solo lectura) |
| **Conectividad** | Redes Wi-Fi guardadas que están a tu alcance y dispositivos Bluetooth ya emparejados. Cada uno tiene su submenú con Conectar / Desconectar y Reconectar (apaga y enciende la radio y vuelve a conectar la red o el dispositivo elegido) |

### Panel de audio

Una ventana GTK propia, porque el menú de bandeja no admite sliders:

- Slider de volumen y botón de mute para la salida por defecto y para el micrófono por defecto.
  El rango es 0–150 %, así que puedes amplificar por encima del 100 % como el mezclador nativo
  de GNOME.
- Mezclador por aplicación: una fila (mute + slider) por cada aplicación que tiene ahora mismo
  un canal de audio abierto. Marca las que están en pausa.
- Se refresca al instante cuando cambia algo (cascos que se conectan, salidas nuevas,
  aplicaciones que empiezan o dejan de sonar), escuchando los eventos de `pactl subscribe`.

### Notificaciones

Si una acción falla (por ejemplo, una contraseña Wi-Fi incorrecta al conectar), la app lo avisa
con una notificación de escritorio.

## Requisitos

- Ubuntu con GNOME sobre Wayland. Probado en Ubuntu 22.04.
- Extensión de GNOME Shell `ubuntu-appindicators` activada. Viene activada en Ubuntu. En GNOME
  "vanilla" hay que instalarla aparte, y sin ella no aparece el icono en la bandeja.
- `python3-gi` y `gir1.2-ayatanaappindicator3-0.1`. Si instalas el `.deb` con `apt`, se
  instalan solos como dependencias.

## Instalación

1. Descarga el archivo `mk96-app-debian-switchboard_<versión>.deb` desde la sección
   [Releases](../../releases/latest) de este repositorio.
2. Instálalo con `apt`, para que resuelva las dependencias:

   ```
   sudo apt install ./mk96-app-debian-switchboard_26-10-1.deb
   ```

3. Durante la instalación se pregunta si quieres que la app arranque con la sesión
   (respuesta por defecto: "Si"). Puedes cambiarlo más tarde:

   ```
   sudo dpkg-reconfigure mk96-app-debian-switchboard
   ```

Para actualizar, instala el `.deb` nuevo encima: `dpkg` sustituye los archivos cambiados y
borra los que ya no existan, sin necesidad de desinstalar antes.

Para desinstalar: `sudo apt remove mk96-app-debian-switchboard` (o `purge` para borrar también la
configuración de autoarranque).

## Uso

Arranca la aplicación desde el menú de aplicaciones ("MK96 Debian Switchboard") o desde un terminal:

```
mk96-app-debian-switchboard
```

Aparece un icono en la bandeja del sistema. Al hacer clic se abre el menú.

## Desarrollo

Ejecutar desde el código, en la carpeta `code/`:

```
python3 -m mk96_app_debian_switchboard.app   # arranca la app
python3 -m pytest                   # tests (requiere python3-pytest)
```

Los tests cubren la lógica pura de cada módulo (parseo, formateo de etiquetas, filtrado). Las
llamadas reales al sistema (`pactl`, D-Bus) se comprueban a mano.

### Compilar el `.deb`

Requiere `debhelper` y `python3-pytest` (los tests se ejecutan durante la compilación):

```
./build.sh
```

El script lee la versión de `code/debian/changelog`, compila con `dpkg-buildpackage` y deja el
resultado en `versions/<versión>/`. Esa carpeta no se sube a git.

### Versionado

Las versiones siguen el esquema **`AA-M-R`**: año (dos cifras), mes y número de release dentro
de ese mes. Por ejemplo, `26-10-1` es la primera release de octubre de 2026 y `26-10-2` sería la
segunda.

Para sacar una versión nueva:

1. Añade una entrada arriba de `code/debian/changelog` con la versión nueva y sus cambios.
2. Actualiza `version` en `code/pyproject.toml` (con puntos: `26.10.1`).
3. Ejecuta `./build.sh`.
4. Crea una release en GitHub con la etiqueta `v26-10-1` y adjunta el `.deb` generado.

## Estructura del repositorio

```
.
├── build.sh                          Compila el .deb y lo deja en versions/<versión>/
├── README.md
├── .gitignore
└── code/
    ├── DESIGN.md                     Diseño en detalle y decisiones técnicas
    ├── pyproject.toml
    ├── debian/                       Empaquetado .deb (control, changelog, scripts de instalación)
    ├── mk96_app_debian_switchboard/           Código de la aplicación
    │   ├── app.py                    Arranque y registro de módulos
    │   ├── tray.py                   Icono y menú de bandeja
    │   ├── menu_groups.py            Agrupación del menú en submenús con estado
    │   ├── audio_panel.py            Ventana del panel de audio
    │   ├── pa_events.py              Eventos de audio (pactl subscribe)
    │   ├── radio_cycle.py            Reconexión apagando y encendiendo la radio
    │   ├── gtk_helpers.py            Constructores de elementos de menú y notificaciones
    │   ├── dbus_utils.py             Utilidades D-Bus
    │   ├── icons/                    Icono symbolic de la bandeja
    │   └── modules/                  Un módulo por herramienta
    │       ├── audio.py
    │       ├── display.py
    │       ├── focus.py              No molestar
    │       ├── power.py
    │       ├── network.py            Wi-Fi
    │       └── bluetooth.py
    └── tests/                        Tests de la lógica pura de cada módulo
```

## Limitaciones conocidas

- **El menú se cierra al elegir una opción.** El menú de bandeja lo dibuja GNOME Shell, no esta
  aplicación, y no se puede evitar desde aquí. Por eso el control de volumen con slider está en
  una ventana aparte.
- Solo funciona con GTK3, porque la librería del icono de bandeja no existe para GTK4.
- Pensada y probada para Ubuntu con GNOME sobre Wayland. En otros entornos no está probada.

## Ideas pendientes

- Historial del portapapeles.
- Interruptor del firewall (`ufw`).
- Desactivar la cámara de forma global.

## Licencia

MIT. El texto completo está en [`code/debian/copyright`](code/debian/copyright).
