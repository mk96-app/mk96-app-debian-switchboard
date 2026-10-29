# MK96 Debian Switchboard — diseño actual

Applet de bandeja para GNOME (Ubuntu, Wayland) que da acceso rápido a acciones que Linux
ya soporta a nivel de sistema pero no expone con un clic: audio (salida, volumen, mute,
mixer por app), pantalla (luz nocturna), no molestar, perfil de energía, redes Wi-Fi
guardadas y dispositivos Bluetooth emparejados.

## Requisitos de sistema

Probado sobre Ubuntu 22.04, GNOME sobre Wayland (`XDG_SESSION_TYPE=wayland`,
`XDG_CURRENT_DESKTOP=ubuntu:GNOME`).

- `python3-gi` (PyGObject) — normalmente ya viene instalado.
- `gir1.2-ayatanaappindicator3-0.1` — típicamente **no** viene instalado por defecto:
  `sudo apt install gir1.2-ayatanaappindicator3-0.1`.
- Extensión de GNOME Shell `ubuntu-appindicators` habilitada (viene por defecto en Ubuntu;
  en GNOME vanilla hay que instalarla aparte, sin ella no aparece el icono de bandeja).
- `python3-pytest` para los tests: `sudo apt install python3-pytest`.

## Ejecutar y testear

```
python3 -m mk96_app_debian_switchboard.app   # arranca la app
python3 -m pytest                # corre los tests de lógica pura
```

## Arquitectura: dos superficies de UI distintas, por una limitación real de la plataforma

Esta app tiene **dos mecanismos de UI completamente distintos**, y la razón no es de
diseño sino una limitación real de cómo funciona AppIndicator en GNOME que se descubrió
durante el desarrollo (a base de romperlo y depurarlo):

**AppIndicator no dibuja el menú en este proceso.** Lo exporta por D-Bus (protocolo
`com.canonical.dbusmenu`, objeto `/org/ayatana/NotificationItem/mk96-app-debian-switchboard/Menu`) y
es **GNOME Shell** quien lo reconstruye y lo muestra. Al hacer click, Shell llama de vuelta
a `Event(id, "clicked", ...)`, y `libdbusmenu-gtk` traduce eso en emitir la señal
`activate`/`toggled` del widget original en este proceso. Consecuencias:

1. Los items del menú **tienen** que ser `Gtk.MenuItem`/`Gtk.CheckMenuItem` normales
   conectados a `activate`/`toggled`. Cualquier widget custom embebido (botones propios,
   `button-press-event`, sliders) nunca recibe el click real, porque ese evento ocurre en
   el proceso de GNOME Shell, no aquí — se probó y se confirmó con eventos simulados.
2. El menú **siempre se cierra al seleccionar un item**; quien decide cerrarlo es GNOME
   Shell. No hay manera de evitarlo desde el lado de la app.
3. `dbusmenu` solo entiende texto, checkboxes (`toggle-type`/`toggle-state`), separadores y
   submenús. **No existe un tipo "slider"** en el protocolo.

Por eso el volumen/brillo por pasos (+10%/-10%, ya eliminados) fue la única vía posible
*dentro* del menú, y por eso el slider real de audio vive en una **ventana GTK propia**
(`audio_panel.py`) que este proceso dibuja directamente, sin pasar por GNOME Shell — ahí
sí valen widgets normales.

## Icono de bandeja

`mk96_app_debian_switchboard/icons/hicolor/scalable/apps/mk96-app-debian-switchboard-symbolic.svg` — icono symbolic
propio (monocromo, se adapta a tema claro/oscuro), estilo mezclador de audio. Se referencia por
nombre (`mk96-app-debian-switchboard-symbolic`) y `AyatanaAppIndicator3.Indicator.set_icon_theme_path()`
apunta a `mk96_app_debian_switchboard/icons/` como icon theme adicional, para no depender de instalarlo en el
sistema (`tray.py`).

## Empaquetado `.deb` (`debian/`)

Paquete Debian nativo (`debian/source/format: 3.0 (native)`). El proyecto vive en
`mk96-app-debian-switchboard/`, con dos carpetas hermanas: `code/` (todo este código, incluido
`debian/`) y `versions/` (una subcarpeta `versions/<X.Y.Z>/` por cada versión generada, con
el `.deb`, `.changes` y `.buildinfo` de esa build). Para compilar: `./build.sh` desde la raíz
del proyecto — lee la versión de `debian/changelog`, compila con
`dpkg-buildpackage -us -uc -b` (requiere `debhelper` instalado) y mueve el resultado a
`versions/<versión>/`, renombrando el `.deb` para quitar el sufijo `_all` de arquitectura
(p. ej. `versions/0.0.3/mk96-app-debian-switchboard_0.0.3.deb`). Versionado semver clásico (`X.Y.Z`,
sin sufijo de revisión Debian) desde la 0.0.3; próxima versión estable: 1.0.0.

- **Instalación/actualización**: `sudo apt install ./versions/X.Y.Z/mk96-app-debian-switchboard_X.Y.Z.deb`. Al ser
  siempre el mismo nombre de paquete con versión creciente (definida en `debian/changelog`),
  `dpkg` sobreescribe los ficheros cambiados y **borra automáticamente** los que ya no existen en
  la versión nueva — no hace falta desinstalar la anterior a mano.
- **Contenido instalado**: el paquete Python completo en
  `/usr/lib/python3/dist-packages/mk96_app_debian_switchboard/` (incluye el icono symbolic de bandeja),
  lanzador `/usr/bin/mk96-app-debian-switchboard` (`debian/scripts/mk96-app-debian-switchboard`, wrapper de
  `python3 -m mk96_app_debian_switchboard.app`), entrada de menú
  `/usr/share/applications/mk96-app-debian-switchboard.desktop` e icono de aplicación en color
  `/usr/share/icons/hicolor/scalable/apps/mk96-app-debian-switchboard.svg`
  (`debian/icons/mk96-app-debian-switchboard.svg`).
- **Autoarranque configurable por debconf**: `debian/mk96-app-debian-switchboard.templates` +
  `debian/mk96-app-debian-switchboard.config` preguntan ("Si"/"No" en texto plano, sin acentos —
  con acentos el diálogo whiptail mostraba un carácter roto en el botón — por defecto "Si")
  durante la instalación si se quiere autoarranque; `debian/postinst` copia (o borra) el
  `.desktop` en `/etc/xdg/autostart/mk96-app-debian-switchboard.desktop` según la respuesta. Se puede
  recomprobar más tarde con `sudo dpkg-reconfigure mk96-app-debian-switchboard`. `debian/postrm` limpia
  esa entrada y la base de datos de debconf al desinstalar/purgar.
- `debian/rules` excluye `__pycache__` del paquete (se regenera igualmente al correr los tests
  durante `dh_auto_test`) y corre `python3 -m pytest` como parte del build.

## Módulos del menú (`mk96_app_debian_switchboard/modules/`)

Todos implementan el contrato `Module` (`modules/base.py`): `is_available()`,
`build_menu_section() -> list[Gtk.Widget]`, `start()/stop()` para señales D-Bus. El
registro y orden vive en `app.py:MODULE_CLASSES`.

Orden actual: **Audio → Pantalla → No molestar → Energía → Red wifi → Bluetooth**.

- **`audio.py`** — bus de sesión, backend `pactl` (ver más abajo por qué no D-Bus). Menú:
  "Abrir panel de audio...", checkboxes de silenciar salida/micrófono, lista de salidas
  (marca la activa con `●`, clic para hacerla default), acceso a Ajustes de sonido.
- **`display.py`** — checkbox de Luz nocturna (`Gio.Settings`,
  `org.gnome.settings-daemon.plugins.color:night-light-enabled`) + acceso a Ajustes.
- **`focus.py`** — checkbox de "No molestar", que en realidad es el mismo interruptor que
  usa el ajuste rápido nativo de GNOME (`org.gnome.desktop.notifications:show-banners`,
  invertido).
- **`power.py`** — perfil de energía vía `net.hadess.PowerProfiles` (D-Bus sistema, cambio
  real con `Properties.Set`, no con `set_cached_property` — ver bug más abajo) + batería
  de solo lectura vía `org.freedesktop.UPower`.
- **`network.py`** — `org.freedesktop.NetworkManager` (D-Bus sistema). Lista solo
  conexiones Wi-Fi **guardadas y actualmente en alcance** (compara SSID de la conexión
  contra el escaneo real de puntos de acceso, no solo el nombre de la conexión).
- **`bluetooth.py`** — `org.bluez` (D-Bus sistema). Lista dispositivos ya emparejados,
  clic para conectar/desconectar.

### Notificaciones de error y refresco (`gtk_helpers.py`, `tray.py`)

- `notify_error(summary, body)` — notificación de escritorio vía
  `org.freedesktop.Notifications` (D-Bus sesión), best-effort.
- `make_action_item` / `make_checkbox_item` — únicos constructores de items de menú;
  encapsulan la restricción de "solo `activate`/`toggled` funciona" de arriba.
- `make_settings_item(panel)` — abre `gnome-control-center <panel>` (sound / display /
  notifications / power / wifi / bluetooth).
- El menú (`tray.py`) es un único `Gtk.Menu` **persistente** (no se recrea cada vez):
  reconstruir sus hijos síncronamente dentro de la propia señal `show` corrompe el
  enrutado de clics (reentrada), así que el refresco al abrir se difiere con
  `GLib.idle_add`, y mientras está abierto se reconstruye cada 5s (`GLib.timeout_add`),
  cancelado al cerrar (señal `hide`).
- Fallo de red al conectar: `NetworkManager.ActivateConnection` responde casi al instante
  aunque la conexión falle después (contraseña incorrecta, fuera de alcance...); se
  escucha la señal `StateChanged` de la conexión activa para notificar el fallo real.

## Panel de audio (`audio_panel.py`) — la otra superficie de UI

`Gtk.Window` normal (singleton, se oculta con `hide()` al cerrar en vez de destruirse),
backend `pactl`. Contiene:

- **Fila maestra**: botón-icono de mute + slider (0–150%, permite amplificar por encima
  del 100% como el mezclador nativo de GNOME) para la salida por defecto; mismo par para
  el micrófono por defecto.
- **Mixer por aplicación**: una fila (icono de mute + slider) por cada *stream* de audio
  activo (`pactl -f json list sink-inputs`), no por app instalada — solo aparecen apps con
  un canal de audio realmente abierto en ese momento. El nombre sale de
  `application.name`, con fallback a `media.name`. Los índices de stream son **efímeros**
  (cambian si la app reabre el stream), así que la lista se reconstruye cada 2s comparando
  el conjunto de índices vivos; si no cambió, no se reconstruye (evita interrumpir un
  arrastre de slider en curso).
- Volumen/mute por app usan subcomandos distintos a los del dispositivo por defecto:
  `set-sink-input-volume <index>` / `set-sink-input-mute <index>`, no
  `set-sink-volume`/`set-sink-mute`.
- Bug ya corregido: la ventana se abría vacía porque faltaba `show_all()` — `present()`
  solo mapea la ventana en pantalla, cada widget necesita su propio flag de visibilidad.

## Bugs reales encontrados y corregidos durante el desarrollo

- **`org.PulseAudio1` (D-Bus) no es viable**: no implementa `org.freedesktop.DBus.Properties`
  ni `Introspectable` de forma estándar en este sistema, así que `Gio.DBusProxy` no puede
  cachear sus propiedades. Todo el módulo de audio usa `pactl` en su lugar.
- **`pactl -f json` rompe su propio JSON en locale `es_ES`** (usa coma decimal en campos
  numéricos tipo `"balance":0,00`). Se fuerza `LC_ALL=C` en cada llamada (`run_pactl`).
- **`Gio.DBusProxy.set_cached_property` no cambia nada en el sistema real** — solo
  actualiza una caché local del proxy. El cambio de perfil de energía usaba esto y no
  funcionaba (`powerprofilesctl get` no cambiaba); se corrigió llamando de verdad a
  `org.freedesktop.DBus.Properties.Set`.
- **AppIndicator exige GTK3**: no existe versión GTK4/libadwaita de la librería, y GTK3 y
  GTK4 no pueden coexistir en el mismo proceso. Toda la app es GTK3.
- **Intentos fallidos de mantener el menú abierto tras seleccionar** (`button-release-event`,
  botones embebidos): ninguno funciona por la naturaleza de `dbusmenu` explicada arriba;
  se abandonó y se volvió a `activate`/`toggled` normales.

## Testing

`tests/` cubre solo la **lógica pura** de cada módulo (parseo, formateo de etiquetas,
filtrado) extraída en funciones sin efectos secundarios — no hay mocks de D-Bus/`pactl`.
Las llamadas reales se verifican a mano (o, durante el desarrollo, simulando el evento
`Event("clicked")` real de `dbusmenu` contra la app en ejecución para confirmar que el
efecto llega al sistema).

## Backlog (no implementado)

- **Historial de portapapeles** — a diferencia del resto de módulos (que solo reflejan
  estado del sistema), necesitaría guardar su propio historial en memoria/disco. Como el
  panel de audio, sería una ventana propia, no un submenú de AppIndicator.
- **Toggle de firewall (ufw)** — requiere escribir una policy de polkit propia (no existe
  ya en el sistema) + helper con `pkexec`.
- **Mute de cámara global** — no existe en Linux un mecanismo de usuario limpio tipo
  "kill switch" de webcam.

## Pendiente de decidir con el usuario

- Rango del slider de volumen: actualmente 0–150% (permite amplificar). Pendiente
  confirmar si se deja así o se limita a 100%.
