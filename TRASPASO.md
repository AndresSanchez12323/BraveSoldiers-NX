# Traspaso entre agentes (Claude ⇄ Codex)

Este archivo es **el punto de partida de cada turno**. El usuario alterna entre Claude Code y Codex cuando a uno se
le acaba el límite. Quien retome el trabajo:

1. Lee este archivo entero, luego `AGENTS.md` (reglas) y la sección final de `NOTAS_DEPURACION.md`.
2. Sigue por la primera tarea sin terminar de la sección «Siguientes pasos».
3. Antes de terminar el turno, **actualiza este archivo**: el estado, los siguientes pasos y una entrada en la
   «Bitácora de turnos». También anota los arreglos en `NOTAS_DEPURACION.md` y regenera el parche (ver más abajo).

El usuario habla español: responde en español.

Repositorio público: https://github.com/AndresSanchez12323/BraveSoldiers-NX. Al cambiar de agente conviene un commit
(solo si el usuario lo pide), para poder volver atrás si algo se rompe.

---

## Estado actual (2026-11-02, fin del turno de Claude)

**Fase 1 (port a PC con ps3recomp), en curso.** El juego arranca en Windows (D3D12) y hace todo esto:
- carga datos y partida;
- pasa la comprobación de DLC;
- **muestra los logos de arranque (Havok, Dimps, CRIWARE) a 60 FPS, sin parpadeo**.

Después llega una fase de unos 570 draws por fotograma (escena del Santuario / pantalla de título) que **se ve en
negro**. Es el problema abierto número 1.

Funciona:
- PPU recompilado (27 217 funciones) con build "Fast" (`build/pc-fast`).
- CRI FS (lee el CPK), trofeos, partida, diálogos en español.
- Decodificador de vídeo CRI Mana levantado a C (pero el vídeo de intro se atasca, ver pendientes).
- RSX → D3D12:
  - 64 RT fuera de pantalla;
  - unidades de textura 4–15;
  - `NV4097_INLINE_ARRAY`;
  - un solo present por flip.

No funciona / falta:
1. **Fase Santuario/título en negro.** `PRESENT_LOG` muestra `on=0 off=566 present=0`: todos los draws van a RT
   fuera de pantalla (sobre todo 0xEE0000) y ninguno al buffer de pantalla. La escena sí se dibuja:
   `GCM_PRESENT_RT=EE0000` enseña las ruinas, y `RTT_SAVERT=EE0000` a Seiya en T-pose.
2. **Seiya en T-pose:** la animación no corre. Sospecha: trabajos SPU de Havok/animación sin ejecutar, o el skinning.
3. **Vídeo de intro (CRI Mana) atascado** tras ~7 rondas PPU↔SPU. Se esquiva con `PS3_FS_HIDE=SEIYAps3-k.usm`, que
   `tools/run_game.ps1` pone siempre.
4. **Audio:** los trabajos del JobQueue son CRI Atom (DspPack1 17504 B, DspPack2 30720 B, AsrVoice 30208 B). Están
   volcados en `local/recomp/spu/jobs_dump/` y **sin levantar**: se descartan, así que no hay sonido.
5. Falta la HLE de `cellSysutilGetBgmPlaybackStatus2`.
6. Mando/entrada sin probar: aún no llegamos a un menú.

---

## Siguientes pasos (en orden de prioridad)

### 1. Fase Santuario/título en negro (EN CURSO)
Objetivo: que la composición final llegue al buffer de pantalla (0x0 / 0x3C0000) sin `GCM_PRESENT_RT`.

Pistas por orden:
1. **Ver métodos RSX sin implementar en la build Fast.**
   - El log `[RSX] unknown method` de `deps/ps3recomp/libs/video/rsx_commands.c` (≈ línea 1068) está dentro de
     `#ifndef NDEBUG`, así que en `pc-fast` no sale nada.
   - Añadir una variable (p. ej. `RSX_UNK=1`) que lo active también en Fast y ejecutar 60 s.
   - INLINE_ARRAY era exactamente este tipo de fallo. Candidatos:
     - `NV4097_INLINE_INDEX_ARRAY` (0x1824);
     - vértices inmediatos `SET_VERTEX_DATA*` usados como draw;
     - `NV3089`/`NV308A` (blits 2D, `SET_TRANSFER_IMAGE`);
     - `NV0039` (copia de memoria).
2. **Contar los flips de esa fase y su buffer.** Saber qué `buffer_id` pide `cellGcmSetFlip` y si los buffers
   registrados con `cellGcmSetDisplayBuffer` siguen siendo 0x0/0x3C0000.
   - Logs ya disponibles: `VP_SUBMIT=<N>`, `RT_OFFDBG`, `DRAWARGS`.
3. **¿El juego espera algo?** Puede que la escena sea la pantalla de título detrás del vídeo y que la composición
   dependa de que acabe el vídeo o la carga (CRI Mana atascado / `PS3_FS_HIDE`), o de un trabajo SPU.
   - Mirar los hilos parados con `PS3_TICKDBG=1` y en qué esperan.
4. Comparar con **RPCS3** en el mismo momento: `local/RPCS3.log` existe, y una captura RenderDoc de RPCS3 dice qué
   draw escribe el buffer de pantalla y con qué método.

Cómo comprobar el arreglo:
- `tools/run_game.ps1` con `PRESENT_LOG=4000` debe mostrar `on>0 present=1` en los lotes de ~570 draws;
- `-capture` o `CELLMARK_DUMP` deben enseñar la escena;
- `python -I tools/frame_stats.py <carpeta>` no debe dar 0.

### 2. Animación (T-pose)
Ver qué trabajos SPURS (job chains / tasksets) despacha el juego en esa fase. `SPU_DUMP_MISS=<carpeta>` vuelca los
binarios que no tienen imagen levantada. Si son de Havok/animación, levantarlos igual que CRI Mana (paso 3).

### 3. Levantar los trabajos SPU de audio (CRI Atom)
Mismo procedimiento que CRI Mana (ver «SPU: CRI Mana» en `NOTAS_DEPURACION.md`):
1. `tools/spu_lifter.py` de ps3recomp sobre cada `.bin` de `local/recomp/spu/jobs_dump/`.
2. `build_spu_workloads.py --images local/recomp/spu/images --lifted local/recomp/spu --out local/recomp/spu/spu_workloads.c --register-fn port_spu_register_all --constructor`.
3. Recompilar.

`pc/stubs.cpp` (`jq_run`) ya despacha los trabajos del JobQueue a `spu_workload_dispatch_job` cuando hay imagen
levantada (`JQ_RUN=0` lo apaga, `JQ_DBG=N` registra los descriptores).

### 4. Vídeo de intro CRI Mana
Quitar `PS3_FS_HIDE` y ver por qué se para el decodificador tras ~7 rondas PPU↔SPU (lee 3,7 MB de 275 MB).

### 5. Menú y combate en PC
Con el mando (`cellPad`) y `cellSysutilGetBgmPlaybackStatus2`. **No pasar a Switch hasta que se pueda jugar en PC.**

### Después: Fase 2–4 (Switch)
Ver `PLAN_PORT_SAINT_SEIYA.md`: runtime libnx, backend deko3d, shaders RSX → DKSH.

---

## Cómo compilar, ejecutar y depurar

```bat
tools\build_pc.cmd 5
```
Esto genera `build\pc-fast\BraveSoldiersRecomp.exe`. El número es la cantidad de trabajos en paralelo (cada uno
gasta ~2 GB de RAM). Usa clang-cl + Ninja de VS 2022 Build Tools y LLVM.

```powershell
pwsh tools/run_game.ps1 -secs 45 -dir local/recomp/<carpeta-nueva> -envs "VAR1=1;VAR2=2" [-capture]
```
La salida queda en `<carpeta>/out.txt` y `<carpeta>/err.txt` (los logs del backend van a `err.txt`). Usa una
carpeta **nueva** en cada prueba; no borres carpetas viejas con comodines.

**Variables de diagnóstico** (todas en `deps/ps3recomp/libs/video/rsx_d3d12_backend.c` salvo las indicadas):

| Variable | Qué hace |
|---|---|
| `PRESENT_LOG=N` | Una línea por `render_frame`: origen (1 límite de clear, 2 flip, 3 d3d12_present), draws a pantalla (`on`) y fuera (`off`), si presenta |
| `VP_SUBMIT=N` | Por lote: a qué RT van los draws (`[PRESENTGATE]`) |
| `DRAWARGS`, `RT_OFFDBG` | Detalle por draw / por RT fuera de pantalla |
| `RTT_SAVERT=<hex>` | Guarda ese RT a `rt_save.bmp` |
| `GCM_PRESENT_RT=<hex>` | Diagnóstico: presenta ese RT si el lote no dibuja en pantalla (EE0000 = escena) |
| `CELLMARK_DUMP=N` + `CELLMARK_DUMP_EVERY=K` + `CELLMARK_DUMP_DIR=<dir>` (+ `CELLMARK_DUMP_MINDRAWS`) | Vuelca N fotogramas presentados a BMP, uno cada K |
| `RSX_CAP=inicio:n:paso` | Instantánea completa (backbuffer + todos los RT + lista de draws) |
| `RSX_ACCUM_FRAME` | `pc/stubs.cpp` lo pone a 1 por defecto (un present por flip). `=0` vuelve al present por límite de clear, que causaba el parpadeo |
| `RSX_DBG_CB`, `VPX_DBG`, `CMASK_DBG`, `DEPTH_OFF`, `FP_IDCOLOR`, `CLEAR_RGB=r,g,b` | Constantes de VP, viewports, máscaras de color, profundidad, color por shader, color de clear |
| `D3D12_DBG=1` | Capa de validación de D3D12 (muy lento) |
| `JQ_DBG=N`, `JQ_RUN=0` | JobQueue en `pc/stubs.cpp` |
| `SPU_DUMP_MISS=<dir>` | Vuelca los binarios SPU sin imagen levantada |
| `PS3_FS_HIDE=<nombre>` | `runtime/ppu/ppu_fs.cpp`: ese archivo da ENOENT |
| `PS3_TICKDBG=1` | `pc/main.cpp`: pasos del ticker que bloquean |
| `PPU_WWATCH=<hex> PPU_WWATCH_LEN=<n>` | Vigilancia de escrituras en memoria guest |

**Herramientas:** para la alternancia negro/contenido, `python -I tools/frame_stats.py <carpeta>`; con PIL se pueden
reducir los BMP a PNG y mirarlos.

---

## Dónde está cada cosa

| Ruta | Qué es |
|---|---|
| `pc/` | Proyecto del port (CMake, `main.cpp` = runner, `stubs.cpp` = HLE y valores por defecto propios del juego) |
| `deps/ps3recomp/` | ps3recomp (repo git, commit fijado en `dependencies.json`) **con cambios locales sin commit** |
| `patches/ps3recomp/0001-brave-soldiers-boot-fixes.patch` | Esos cambios en forma de parche. **Regenerarlo al final de cada turno**: `git -C deps/ps3recomp diff > patches/ps3recomp/0001-brave-soldiers-boot-fixes.patch` |
| `local/` | **Privado**: EBOOT descifrado, juego, código recompilado (`local/recomp/recompiled`), SPU, logs de las pruebas |
| `NOTAS_DEPURACION.md` | Bitácora técnica de cada arreglo (Arreglos 1–10) |
| `PLAN_PORT_SAINT_SEIYA.md` | Hoja de ruta por fases con casillas |
| `referencias/` | Budokai-NX y DBT-NX, solo para consulta |

Archivos de ps3recomp tocados hasta ahora:
- `libs/video/`: `rsx_d3d12_backend.c`, `rsx_commands.c/.h`, `rsx_vertex_fetch.c`, `cellGcmSys.c`;
- `libs/network/sceNpTrophy.c`;
- `runtime/ppu/`: `ppu_fs.cpp`, `ppu_hle.cpp`.

---

## Bitácora de turnos
Añade una entrada al final de cada turno: fecha, agente, qué se hizo y dónde se quedó.

- **2026-11-02 · Claude:**
  - del primer arranque a los logos jugables;
  - Arreglos 1–10;
  - última sesión: INLINE_ARRAY, RT de 1280x720, parpadeo (dos presents por flip → `RSX_ACCUM_FRAME=1` por defecto);
  - se queda en el paso 1 (fase del Santuario en negro), sin empezar la pista 1.1 (`RSX_UNK`).
