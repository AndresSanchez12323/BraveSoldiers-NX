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

## Estado actual (2026-11-02, fin del turno de Codex)

**Fase 1 (port a PC con ps3recomp), en curso.** El juego arranca en Windows (D3D12) y hace todo esto:
- carga datos y partida;
- pasa la comprobación de DLC;
- **muestra los logos de arranque (Havok, Dimps, CRIWARE) a 60 FPS, sin parpadeo**.

La pantalla negra de composición quedó resuelta (Arreglo 11). Se agotaba el espacio de subida de vértices
antes de los draws finales. Ahora aparece la pantalla de título completa, fondo estrellado y texto START en
español, sin forzar un RT. Captura: `local/recomp/codex_capacity06/title.png`.

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
1. **START funciona; transición al menú bloqueada.** Título confirmado con `on=16 present=1` y 1751 registros.
   `pc/stubs.cpp` establece `RSX_VERTEX_CAPACITY=2097152`; el backend conserva su valor general 393216.
   Reserva PC: 512 MiB por paridad, 1 GiB total. Optimizar antes de Switch.
2. **Seiya en T-pose:** la animación no corre. Sospecha: trabajos SPU de Havok/animación sin ejecutar, o el skinning.
3. **Vídeo de intro (CRI Mana) atascado** tras ~7 rondas PPU↔SPU. Se esquiva con `PS3_FS_HIDE=SEIYAps3-k.usm`, que
   `tools/run_game.ps1` pone siempre.
4. **Audio:** los trabajos del JobQueue son CRI Atom (DspPack1 17504 B, DspPack2 30720 B, AsrVoice 30208 B). Están
   volcados en `local/recomp/spu/jobs_dump/` y **sin levantar**: se descartan, así que no hay sonido.
5. Falta la HLE de `cellSysutilGetBgmPlaybackStatus2`.
6. START probado por PAD_SCRIPT: sale del título y crea partida; mando físico y menú todavía sin validar.

---

## Siguientes pasos (en orden de prioridad)

### 1. Probar START, menú y combate (EN CURSO)
La composición está arreglada y la pantalla de título completa está comprobada visualmente.
START ya está confirmado mediante `PAD_SCRIPT=55:0x0008` (codex_menu08) y a 50 s (codex_menu09).
Dispara carga, diálogo HLE (auto-YES) y creación de SAVEDATA.DAT. Después queda el fondo estrellado.

**Siguiente acción:** investigar la sobrescritura del FIFO en la transición. En codex_menu08/09, IO 0x21B98
se lee como FEAD0101 y luego el volcado muestra vértices allí; 0x21B9C produce unmapped-JUMP y put=0.
Instrumentar `gcm_flip_into_fifo` (wrap anticipado), contexto y escrituras put/get. No asumir el escritor.
El experimento codex_menu10 (llamar cellGcm_fifo_recycle desde el wrap anticipado) se bloqueó antes del título
y fue RETIRADO. No reintroducirlo sin resolver el orden de solicitud/completado del flip.

También aparece SPU sin recompilar: fp=0x7EAD6B29FC048F09, size=65056, owner=0x01D70500. Volcar con
`SPU_DUMP_MISS` e identificar; aún no se conoce su papel. Pruebas codex_menu07–10 y detalles en NOTAS.
El Arreglo 12 limita el log de atributos a ocho entradas y requiere RSX_INLINE_TRACE.

Controles Windows: Enter=START, Z=cruz, X=círculo, flechas=dirección (ventana enfocada); XInput preferido.
Para pruebas, PAD_SCRIPT usa segundos desde el primer sondeo: `55:0x0008,75:0x4000`.
PAD_FILE=<ruta absoluta> acepta máscara y número de informes; `0x0008 4` prueba START sin GUI.
Los guardados usan cwd por defecto: fijar PS3_GAMEDATA_ROOT absoluto para comprobar persistencia.


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
| `RSX_VERTEX_CAPACITY=N` | Capacidad fija de vértices por fotograma: rango 393216–2097152; el port usa 2097152 |
| `RSX_UPLOAD_TRACE=1` | Bytes usados y capacidad al enviar draws inline |
| `RSX_INLINE_TRACE=1` | Destino y tamaño de draws INLINE_ARRAY (rsx_commands.c) |
| `GCM_FLIP_TRACE=1` | Buffer registrado solicitado por flip (cellGcmSys.c) |
| `RSX_UNK=1` | Métodos RSX desconocidos en Fast, una línea por método (rsx_commands.c) |
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
| `NOTAS_DEPURACION.md` | Bitácora técnica de cada arreglo (Arreglos 1–12) |
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

- **2026-11-02 · Codex:**
  - Arreglo 11: diagnóstico de agotamiento de vértices, capacidad configurable y valor propio del juego 2097152.
  - Logs nuevos RSX_UNK / RSX_INLINE_TRACE / GCM_FLIP_TRACE / RSX_UPLOAD_TRACE.
  - Pruebas codex_unk01, targets02, upload03, capacity04–06 bajo local/recomp.
  - Confirmada visualmente pantalla de título completa en español; sin GCM_PRESENT_RT.
  - Compilación final correcta; parche regenerado. Sin commits ni push.
  - Próximo: comprobar START/mando y menú; después animación/audio/vídeo. Reducir memoria antes de Switch.

- **2026-11-02 · Codex (continuación):**
  - START funciona y crea partida. Menú no validado: bloquea tras el título, con evidencia de sobrescritura FIFO.
  - Arreglo 12 limita el log INLINE_ARRAY; compilación correcta. Experimento de espera al wrap retirado.
  - Nueva huella SPU 7EAD6B29FC048F09 (65056 bytes) pendiente de volcar/identificar.
  - Logs y capturas codex_menu07–10 privados. Parche actualizado; sin commit ni push.
