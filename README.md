# BraveSoldiers-NX

Port no oficial de **Saint Seiya: Brave Soldiers** (PS3, 2013) a Nintendo Switch, mediante
recompilación estática con [ps3recomp](https://github.com/sp00nznet/ps3recomp) y render con deko3d.
Sigue el modelo de [Budokai-NX](https://gitlab.com/alexyt2021es/Budokai-NX).

**Estado: Fase 1 (port a PC).** Arranca en Windows y muestra los logos; el título aún sale en negro. Estado al día en [TRASPASO.md](TRASPASO.md). Plan completo en
[PLAN_PORT_SAINT_SEIYA.md](PLAN_PORT_SAINT_SEIYA.md).

## Archivos del juego

Necesitas tu propia copia original. Este proyecto **no incluye** ISO, EBOOT, datos ni código generado a partir del juego.
Comprueba tu copia con:

```sh
python tools/check_game.py "RUTA_A_TU_JUEGO"            # carpeta PS3_GAME, carpeta del disco o .iso
python tools/check_game.py "RUTA_A_TU_JUEGO" --json local/manifest.json
```

El script solo lee: no copia ni modifica nada. Ver [baserom.md](baserom.md).

## Estructura

| Carpeta | Contenido |
|---|---|
| `tools/` | Scripts del port (verificación, después codegen y empaquetado) |
| `local/` | Privado, ignorado: manifiestos, EBOOT descifrado, código generado |
| `referencias/` | Clones de Budokai-NX y DBT-NX para consulta (no forman parte del port) |

Proyecto de fans, sin afiliación con Bandai Namco, Dimps ni Toei Animation.
