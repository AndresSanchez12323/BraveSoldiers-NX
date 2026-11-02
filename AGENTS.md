# Instrucciones para agentes (Codex, Claude Code)

Port no oficial de Saint Seiya: Brave Soldiers (PS3, EUR BLES01936) a PC y luego a Nintendo Switch, con ps3recomp
(recompilación estática), siguiendo el modelo de Budokai-NX.

**Empieza siempre por `TRASPASO.md`**: estado, siguientes pasos, cómo compilar y depurar, y la bitácora de turnos.
El usuario alterna entre agentes; al terminar tu turno, actualiza `TRASPASO.md`.

## Reglas
- Responde al usuario en **español**.
- **Nunca distribuyas** archivos del juego ni código generado a partir de él. Todo eso va en `local/` (privado):
  no lo subas, no lo pegues en servicios externos y no lo saques de `local/`.
- No cambies ajustes de seguridad del sistema (Smart App Control, Defender, etc.); los cambia el usuario.
- **Commits y push solo cuando el usuario lo pida.** El proyecto es un repo **público**:
  https://github.com/AndresSanchez12323/BraveSoldiers-NX (rama `main`).
  - Antes de cada commit revisa `git status`: no debe entrar nada de `local/`, `gamedata/`, `ISO/`, `deps/` ni `build/`.
  - Los cambios en `deps/ps3recomp` (que es su propio repo) se guardan como parche en `patches/ps3recomp/`.
- No borres carpetas de pruebas con comodines (`local/recomp/frames*`, etc.): crea carpetas nuevas.
- Los cambios en ps3recomp deben seguir el estilo del archivo: comentarios en inglés que explican el *porqué*, y
  diagnósticos detrás de una variable de entorno.
- Si un cambio solo vale para este juego, va en `pc/stubs.cpp`, no en la biblioteca.
- Cada arreglo se documenta como «Arreglo N» en `NOTAS_DEPURACION.md`, y se marca su casilla en
  `PLAN_PORT_SAINT_SEIYA.md`.

## Compilar y probar
- `tools\build_pc.cmd 5` compila `build\pc-fast\BraveSoldiersRecomp.exe` (tarda varios minutos y gasta mucha RAM).
- `pwsh tools/run_game.ps1 -secs 45 -dir local/recomp/<nueva> -envs "VAR=1"` ejecuta el juego.
- Los `printf` con `\n` escritos a través de heredocs de shell se rompen: edita el C con una herramienta de edición
  de archivos.
