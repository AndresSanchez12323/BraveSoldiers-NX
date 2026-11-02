# Notas de depuración — port de PC (ps3recomp)

Registro de cada intento de arranque, al estilo de `CORRECCIONES-x.y.md` de Budokai-NX.
Las salidas completas están en `local/recomp/run*.out|err` (privadas).

## Cómo ejecutar

```sh
build/pc-fast/BraveSoldiersRecomp.exe local/BLES01936/PS3_GAME/USRDIR/EBOOT.elf
```

Lo cómodo: `pwsh tools/run_game.ps1` (ver `TRASPASO.md`).

Variables útiles del runtime: `PS3_STDIO_UNBUFFERED=1`, `PS3_SCTRACE=1` (no imprimió nada en nuestras pruebas),
`PS3_SCTRACE_TID=1` (syscalls del hilo principal), `PS3_HLE_UNRESOLVED=1`, `PS3_MEMTRACE=1`.

## Arranque 1 — 2026-11-02

**Funciona:**
- Carga del ELF (2 segmentos), TLS, `sys_initialize_tls`.
- D3D12 en la RTX 3050, 1280×720, ventana abierta. `cellSysutil` registra su callback.
- El CRT del juego (`func_003514D8`) llega a los constructores estáticos (`.ctors`, 539 entradas, recorridas
  de atrás hacia delante por `func_003517B8`).

**Falla:** el hilo principal se queda girando (`[HOTREAD8] spinning on 0x15`) porque un objeto global quedó en NULL.

Cadena:
1. El constructor en `.ctors[523]` (`func_00920228` → `func_0081952C`) pide 0x30 bytes al asignador del juego
   `func_008139D8(heap=0x1D57E50, …)` y recibe **NULL**; escribe en `NULL+4`, `NULL+0x2C`…
2. Ese asignador mira la bandera `0x1D58178` (¿heap propio listo?). La pone a 1 `func_008134EC`, llamado desde el
   constructor `.ctors[511]` (`func_00813AF4`), que se ejecuta **después** (los ctors van del final al principio).
   Mientras tanto usa la libc del juego: `func_00812BA0` → `func_008179C4` → `func_009609FC` (malloc).
3. El malloc de la libc (`func_0095E618`, usa la syscall 348 `sys_memory_allocate`) acaba en la rutina de error
   `func_00960AB8` (syscall 988 + `sys_tty_write`), y devuelve NULL.
4. La inicialización del malloc (`func_00960A50` → `func_009607E0`, llamada por el CRT antes de `_init`) solo
   hace la syscall 352 (`sys_memory_get_user_memory_size`) en el hilo principal; nunca se ve la 348.

**Hipótesis a comprobar en la siguiente sesión:**
- Qué devuelve el runtime en la 352 (`SYS_MEM_USER_TOTAL`) frente a lo que espera la libc del juego, y por qué
  `func_0095E618` no llega a pedir memoria con la 348.
- Comparar con RPCS3 (`PS3_SCTRACE` no imprime: revisar por qué; quizá otro camino de syscalls).
- Leer los mensajes TTY de la libc (la syscall 403 debería mostrar el texto del error).

## Arranque 2 — 2026-11-02 (arranques 5–9)

### Arreglo 1: el TOC (r2) se perdía en las llamadas HLE rápidas — causa del malloc NULL
`ps3_hle_call` restaura r2 y escribe el hueco ABI `0x28(r1)` con un `_TocGuard`, pero la **ruta rápida**
(`hle_fast`, usada por `sys_lwmutex_lock/unlock`) retornaba antes de crear el guard. El código del juego hace
`ld r2,0x28(r1)` tras cada import (`func_0095D484`), así que leía basura del marco recién creado: r2 = 0 y
todas las lecturas relativas al TOC salían de NULL (el `NULL+0x1C0` del lwmutex, el malloc a NULL…).
La inicialización del malloc estaba bien (`_malloc_limit` = 0 = sin límite).
**Arreglo** (`deps/ps3recomp/runtime/ppu/ppu_hle.cpp`): la ruta rápida escribe `r2` en `0x28(r1)` antes de llamar,
como hace el stub glink real (`std r2,40(r1)`).

### Arreglo 2: `cellFsReadWithOffset` (NID 0x0D5B4A14) no existía
El instalador lee `install_content_EU.lst` / `install_data.lst` con ella. Implementada como pread en
`runtime/ppu/ppu_fs.cpp` (seek/lectura/restaurar posición bajo un mutex).

### Arreglo 3: el id del título era `BLES00000`
La plantilla `pc/main.cpp` no llamaba a `cellGame_init_from_paramsfo`. Ahora lee `PS3_GAME/PARAM.SFO` → `BLES01936`.

### Arreglo 4: los trofeos borraban los OPD del juego
`sceNpTrophyGetGameInfo` escribía `numTrophies = 32` en little-endian; el juego leía 0x20000000, dimensionaba
un vector enorme y el `memmove` (`func_008D9A98`, desde `func_00917D6C`) pisaba con ceros los OPD de 0x01048648
(hilo "Achievement" con entrada 0) y punteros de función de CRI y del "Em File Thread" (los `bctr to NULL`).
Encontrado con `PPU_WWATCH=01048648 PPU_WWATCH_LEN=0x8`.
**Arreglo** (`libs/network/sceNpTrophy.c`): `ps3_bswap32/64` en `GetGameInfo` y `GetTrophyInfo`.

### Instalación obligatoria
El juego busca `/dev_hdd0/game/BLES01936/USRDIR/resource.cpk` (lo que RPCS3 copia al instalar). En vez de copiar
2,9 GB hay un **enlace duro** local: `local/BLES01936/game/BLES01936/USRDIR/resource.cpk` → `PS3_GAME/USRDIR/resource.cpk`.

### Estado tras el arranque 9 (70 s)
**Funciona:** constructores, instalador, CRI FS (lee el CPK: CPK/TOC/ITOC), los 5 shaders `.emz`, comprobación de
datos, trofeos, carga de la partida (`BLES01936-SAVEDATA0`), diálogos del juego en español, compilación de
decenas de shaders RSX en D3D12. **0 llamadas a punteros nulos.**

**Se para en:** «Comprobando contenido descargable...». Todavía **no hay ningún flip** (ningún fotograma presentado).

**Siguientes pistas:**
1. `[cellGcmSys] FIFO CALL to unmapped IO 0x01033028` — el FIFO del RSX salta a un offset fuera de lo mapeado
   (¿`_cellGcmFunc15` o un búfer de comandos estático en `.data`?). El drenado del FIFO se detiene ahí.
2. SPURS JobQueue sin implementar: `cellSpursJobQueuePort2Sync` (0xFACB3CED), `_cellSpursJobQueuePort2PushJobBody`
   (0xCF89F218), 0xC39173A4, 0x983BE7FC.
3. cellFont: `cellFontInitLibraryFreeTypeWithRevision`, `SetResolutionDpi`, `SetScalePoint`.
4. Comprobación de DLC (busca licencias en `/dev_hdd0/game/NPEB01814/USRDIR/dlc/`).

### Parches sobre ps3recomp
Los cambios en `deps/` (ignorado por git) se guardan en `patches/ps3recomp/`. Para reproducirlos sobre el commit
fijado en `dependencies.json`: `git -C deps/ps3recomp apply ../../patches/ps3recomp/0001-brave-soldiers-boot-fixes.patch`.

## Arranque 3 — 2026-11-02 (arranques 10–27)

### Compilación "Fast" (la Debug era inservible)
La caché de CMake estaba en `Debug` (`/Od /RTC1` + capa de depuración de D3D12): el lector del FIFO avanzaba
~570 KB en 3 s, el juego llenaba el anillo, el callback de reciclaje se rendía a los 2 s y se perdían comandos
(de ahí los "CALL a IO sin mapear", que eran basura). `tools\build_pc.cmd` ahora configura `build/pc-fast`:
código recompilado a `-O1`, runtime a `-O2`, `NDEBUG`. `tools\build_pc.cmd 5 debug` sigue dando la Debug.

### HLE añadidas en `pc/stubs.cpp` (`game_register_hle`)
JobQueue Port2 (`Sync`, `PushJobBody`, `CopyPushJobBody`) devuelven OK sin ejecutar el trabajo;
`cellFontInitLibraryFreeTypeWithRevision`, `SetResolutionDpi`, `SetScalePoint`.
Siguen sin resolver: `cellSysutilGetBgmPlaybackStatus2` (0x6CFD856F, ~37 llamadas), `cellFontRenderSurfaceInit`
(0x90B9465E), uno de `cellL10n` (0xF9B1896D) y uno de `cellSpursJq` (0x983BE7FC).

### Arreglo 5: un PSO fallido se recompilaba en cada draw (`rsx_d3d12_backend.c`)
Si `D3DCompile` o `CreateGraphicsPipelineState` fallaban, no se guardaba nada en la caché y cada draw con ese
shader repetía descompilación + compilación: el lector del FIFO bajaba a ~2 KB/s y el reciclaje esperaba 4–5 s.
Ahora el fallo se cachea como PSO nulo. Con `D3D12_DBG=1` el fallo imprime el motivo de la capa de validación.

### Arreglo 6: unidades de textura 4–15 (`rsx_d3d12_backend.c`)
El motivo de los PSO fallidos: los shaders del juego usan `s5`/`s7`, y el root signature solo declaraba t0–t3 /
s0–s3. Se añaden dos tablas fijas (t4–t15 → SRV nulos, s4–s15 → sampler lineal/wrap). Los PSO ya se crean
(0 fallos); esas unidades leen 0 hasta que los draws lleven estado para ellas.

### SPU: CRI Mana
El juego crea 3 tareas SPURS con el ELF embebido en 0x01004580 (139 876 bytes, decodificador de vídeo de CRI).
Recompilado con `build_spu_workloads.py --images local/recomp/spu/images --lifted local/recomp/spu
--out local/recomp/spu/spu_workloads.c --register-fn port_spu_register_all --constructor` (1 556 funciones);
el CMake del port lo recoge solo. Las tareas ya se despachan (`dispatch HIT`).

### Estado tras el arranque 27
**Pasa** la comprobación de DLC, inicializa SPURS y abre `resource/movie/SEIYAps3-k.usm` (vídeo de intro).
El decodificador hace ~7 rondas PPU↔SPU, lee ~3,7 MB de 275 MB y se para. Con `PS3_FS_HIDE=SEIYAps3-k.usm`
(nueva variable de diagnóstico en `ppu_fs.cpp`: la apertura da ENOENT) el juego no se cuelga, pero los volcados
(`CELLMARK_DUMP=24 CELLMARK_DUMP_EVERY=90 CELLMARK_DUMP_MINDRAWS=1 CELLMARK_DUMP_DIR=...`) siguen siendo
fotogramas uniformes (blanco y luego negro).

**Siguientes pistas:** por qué los fotogramas salen uniformes (¿se presenta el RT correcto?, ¿texturas?),
el bloqueo de CRI Mana en SPU, y `PS3_TICKDBG=1` (nuevo en `pc/main.cpp`) para pasos del ticker que bloquean.

### Arreglo 7: más render targets fuera de pantalla (`rsx_d3d12_backend.c`)
El juego usa ~30 RT por fotograma (escena MRT en 0xEE0000/0x12A0000, 0x42A0000, 0x4660000 y una pirámide de
bloom de 640x360 a 64x36). `MAX_OFF_RTS` era 16: los RT vivos se desalojaban y se recreaban cada fotograma, y los
draws caían en `rt=-1` (el backbuffer). Ahora es 64. Sus SRV pasan al final del heap
(`RT_SRV_BASE = HI_SRV_BASE + FP_HI_UNITS`). Con `DRAWARGS` ya no aparece ningún draw con `rt=-1`, y
`RTT_SAVERT=EE0000` muestra a Seiya renderizado (en T-pose, con la armadura casi negra).

### Pantalla negra: el juego no escribe nunca el buffer de pantalla
`VP_SUBMIT` + `RT_OFFDBG` (701 lotes): cada flip trae ~580 draws, todos a 0xEE0000, y 5 clears, con
`onscreen=0`. Durante la carga sí corre la cadena de post-proceso (0x42A0000 → pirámide de bloom →
0xEE0000), pero tampoco escribe en 0x0 ni en 0x3C0000. Tampoco hay blits NV3089 (`NV3089_GATE`), métodos 2D sin
manejar ni llamadas a cellResc. La composición final a pantalla no llega por el FIFO. Hipótesis: la generan
trabajos SPU (JobQueue, que hoy no se ejecutan) o un búfer de comandos que el lector no recorre. Hay un único
`FIFO get=0x00900000 has no IO mapping -- resyncing` al arrancar: get llega justo al final de `MapMainMemory`
(io 0x100000 + 0x800000).

**Parche de diagnóstico:** `GCM_PRESENT_RT=EE0000` presenta ese RT cuando el lote no trae draws a un buffer
de pantalla (reutiliza `composite_present`). **Primera imagen con contenido** (arranque 30, ~27 FPS): las
ruinas del Santuario con columnas y terreno texturizado. Faltan el cielo (negro), el post-proceso y la UI 2D.

### Arreglo 8: `NV4097_INLINE_ARRAY` en el backend D3D12 (`rsx_commands.c`, `rsx_vertex_fetch.c`)
Los draws a pantalla completa (post-proceso, composición, UI y logos) mandan los vértices dentro del FIFO con el
método 0x1818, que no estaba implementado: se descartaban todos. Ahora los bytes se acumulan hasta el
`BEGIN_END(0)`. Los atributos activos se empaquetan en orden de índice, y el lector de vértices lee de ese búfer
(`inline_base`). Con esto la composición sí llega a 0x0/0x3C0000: la hipótesis de los trabajos SPU era falsa.
Los trabajos del JobQueue son audio de CRI Atom (DspPack1/2, AsrVoice). Están volcados en
`local/recomp/spu/jobs_dump/` y sin levantar.

### Arreglo 9: la "copia de pantalla" tapaba los RT del juego
Un muestreador de 1280x720 se sustituía por `s_screen_copy` (negro). Brave Soldiers muestrea sus propios RT
de escena y de post del mismo tamaño. Ahora solo se sustituye si la textura no es un RT conocido
(`off_rt_find(...) < 0`). Resultado: los logos (Havok, Dimps, CRIWARE) se ven bien a 60 FPS.

### Arreglo 10: parpadeo negro (dos presents por flip)
`PRESENT_LOG=<N>` (nuevo, en `render_frame`) muestra dos presents por cada flip:
- `src=1` (límite de clear): 26 draws fuera de pantalla más la composición.
- `src=2` (flip): solo los 2 últimos draws.

El juego limpia un buffer de pantalla a mitad de fotograma, y eso disparaba el present por límite de clear.
Cada flip mostraba dos medios fotogramas, que se alternaban con negro. `pc/stubs.cpp` pone `RSX_ACCUM_FRAME=1`
por defecto (`RSX_ACCUM_FRAME=0` lo revierte), así que se presenta una sola vez por flip, con el fotograma
entero. Volcados: Dimps → transición blanca → CRIWARE, sin fotogramas negros intercalados.

**Pendiente:** la fase de ~570 draws (Santuario/título) sigue sin draws a pantalla (`on=0`, `present=0`).
