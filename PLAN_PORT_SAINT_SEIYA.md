# Port de Saint Seiya: Brave Soldiers (PS3) a Nintendo Switch — Plan base

> Fecha: 2026-11-01. Basado en el análisis de `referencias/Budokai-NX` y `referencias/DBT-NX`.
>
> **Alcance actual: solo Brave Soldiers.** Soldiers' Soul queda fuera por ahora (sección 3).

## 1. Cómo están montados los ports de referencia

### Budokai-NX (DBZ Budokai 3 HD, Xbox 360 → Switch) — el modelo a seguir

Es una cadena de tres capas, cada una de un proyecto distinto:

| Capa | Proyecto | Qué aporta |
|---|---|---|
| Recompilador estático | [ReXGlue SDK](https://github.com/rexglue/rexglue-sdk) (BSD) | Traduce el PowerPC del `.xex` a C++ (`generated/`) + runtime con kernel/FS/audio/input de Xbox 360 |
| Port a PC | [NovaPowers/DBZ-Budokai-3-HD-Collection](https://github.com/novapowers0/DBZ-Budokai-3-HD-Collection) (MIT) | `src/hooks.cpp`, launcher, mods; corre en Windows/Linux con Vulkan |
| Capa Switch | runtime Horizon de [bejeweled3-nx](https://github.com/ChanseyIsTheBest/bejeweled3-nx) / nfsmw-nx + `switch/` propio | ReXGlue compilado con devkitA64/libnx, render con **deko3d** (plume + uam), shaders del juego pretraducidos a DKSH |

Fases que siguió (ver `switch/README.md`), en este orden:

1. **Identificar y verificar el ejecutable** (`switch/tools/check_game.py`): SHA-256/MD5 del binario exacto; `baserom.md` con hashes de todos los archivos.
2. **Port a PC primero**: el código recompilado arranca y es jugable en PC antes de tocar Switch.
3. **NRO de diagnóstico**: solo deko3d (triángulo + mando + log). Valida toolchain, salida al hbmenu, etc.
4. **NRO loader**: enlaza la CPU recompilada (`libdbz3_guest_core.a`) + runtime Horizon; carga el ejecutable y crea la memoria guest. Primer fallo real: rutas `sdmc:/`.
5. **Boot trace**: ejecuta el hilo del juego y captura el primer draw (PM4/registros/shaders) sin dibujar.
6. **Shaders offline**: escanea los 108 shaders del ejecutable → HLSL → SPIR-V → GLSL → DKSH (uam).
7. **Renderer nativo deko3d**: conecta draws reales; luego decenas de iteraciones de rendimiento (resolución interna 960×540, caché de vértices, funciones CPU calientes en nativo).
8. **Distribución**: preparador web (lee la ISO en el navegador y arma el ZIP), actualizador con SHA-256, nada con copyright en el repo.

### DBT-NX (Tenkaichi 3, PS2 → Switch) — otro enfoque, NO aplicable aquí

Parte de una **decompilación completa con matching** ([Tenkaichi3Decomp](https://github.com/z3xox/Tenkaichi3Decomp)): C reescrito función por función hasta que compila al binario idéntico, luego se porta como código nativo y se emula GS/VU1 en deko3d. Requiere años de trabajo de una comunidad; no existe nada así para Saint Seiya.

## 2. Equivalente para PS3

| Budokai-NX (X360) | Saint Seiya (PS3) | Estado |
|---|---|---|
| ReXGlue | **[sp00nznet/ps3recomp](https://github.com/sp00nznet/ps3recomp)** (MIT, basado en XenonRecomp, PPU + SPU → C) | Upstream confirmado (los demás son forks). v0.18.0, commit `4e8f3ca8`. `cellSpursJq` marcado completo; `cellSpurs` y `cellAdec` parciales. Juegos menores jugables en PC (Windows/D3D12) |
| `default.xex` | `EBOOT.BIN` → `EBOOT.ELF` descifrado + PRX/SPU ELF del juego | Descifrar con RPCS3 a partir de tu copia y tu firmware |
| Port PC de NovaPowers | **Lo tenemos que hacer nosotros** | — |
| Runtime Horizon de ReXGlue | **ps3recomp para libnx/devkitA64 — no existe** | Seríamos los primeros |
| Xenos PM4 → deko3d | **RSX (cellGcm) → deko3d — no existe** | Partir del backend Vulkan de ps3recomp |

### Diferencias de dificultad respecto a Budokai

- **SPU**: el Cell tiene 6 SPU disponibles; los juegos de Dimps de esa época usan SPURS (animación, física, audio, descompresión). ps3recomp los convierte en hilos C; la Switch tiene 3 núcleos A57 a 1 GHz para el juego. **Mayor riesgo de rendimiento del proyecto.**
- **RSX**: los shaders son microcódigo NV40/G70 (vertex/fragment programs), no Xenos. Se traducen a GLSL → DKSH con uam, igual que en Budokai pero con otro frontend.
- **Memoria**: PS3 = 256 MB + 256 MB VRAM; cabe en Switch (modo de aplicación completa, no applet).
- **Juego base**: Budokai 3 es un juego de PS2 remasterizado (ligero). Saint Seiya es un juego nativo de PS3 de 2013/2015, bastante más pesado. Hay que asumir 30 FPS y resolución interna reducida desde el inicio.

## 3. Qué juego portear primero: **Brave Soldiers**

| | Brave Soldiers (2013) | Soldiers' Soul (2015) |
|---|---|---|
| Plataformas | Solo PS3 | PS3, PS4 y PC |
| Motor | Motor de Dimps (base) | El mismo motor ampliado (más personajes, arco de Asgard) |
| RPCS3 | Jugable; ya en 2017 iba a 30 FPS en Vulkan sin cierres | Jugable (entrada de 2017) |
| SPU conocido | Usa `libspurs_jq` + `libsre` (SPURS Job Queue), según el issue RPCS3 #1749 | No documentado; probablemente el mismo |
| Problemas RSX conocidos | Opcode BRB, formato D8R8G8B8, desenfoque de menús y bloom (todos resueltos en RPCS3) | Sin issues públicos |

Decisión: **primero Brave Soldiers**, después Soldiers' Soul reutilizando el mismo runtime, backend RSX y manejo de SPURS
(como Budokai-NX mete dos regiones en un mismo núcleo). Es el juego base, con menos contenido que cargar en la RAM de la Switch,
y tiene más historial técnico público (issues de RPCS3 con logs) para saber qué partes del PS3 usa.
La versión PC de Soldiers' Soul (Steam) sirve como referencia de formatos de datos, no como fuente del port.

Pendiente de verificar con los archivos: tamaño de `EBOOT.BIN`, número de SPU ELF/`.sprx`, `APP_VER` en `PARAM.SFO` y peso total del juego.

## 4. Hoja de ruta

### Fase 0 — Material y verificación
- [x] Elegir juego: Brave Soldiers.
- [x] Confirmar región y código: **BLES01936, APP_VER 01.00 (disco, sin update)**.
- [x] Descifrar `EBOOT.BIN` con RPCS3 (*Utilities → Decrypt PS3 Binaries*). No hay `.sprx` propios en el disco.
- [x] `RPCS3.log` de una partida (RPCS3 v0.0.43-20551, ~5 min, sin cierres). Copia en `local/RPCS3.log`.

**Lo que dice el log de RPCS3 (2026-11-01):**
- Dos instancias de SPURS: `CriAtomCellSpursKernelGroup` con **1 SPU** (audio CRI) y `CellSpursKernelGroup` con **4 SPU**
  (trabajos del juego/Havok, `libspurs_jq.sprx` cargado de `dev_flash`). Más una imagen SPU propia `cri_mpvps3` (vídeo).
- Usa `cellSpursCreateTaskset2`: es justo lo que ps3recomp lista como pendiente en `cellSpurs` ("Taskset2").
- Hilos PPU: CRI FS (4 de acceso + descompresión), `CriManaDecodeThread`, `CriAtomSpursHdlr0/1`, `SpursHdlr0/1`, 2 `XG Job Worker`,
  guardado (`SysSavIO`), trofeos, `_gcm_intr_thread`.
- **Instalación obligatoria**: en el primer arranque copia `resource.cpk` (2.7 GiB) a `/dev_hdd0/game/BLES01936/`.
  En Switch hay que saltarse el instalador y leer el CPK directamente de la SD.
- DLC: los busca en `/dev_hdd0/game/NPEB01814/USRDIR/dlc/` (licencias); los datos ya están en el CPK.
- Salida 1280×720 con `cellResc`. Avisos de RSX solo del intérprete de shaders (texturas en vertex shader).
- Sin errores graves: fuentes coreana/japonesa ausentes, un syscall 988 sin implementar (devuelve OK) y avisos SPU de patrones de canal.

**Lo que dice el EBOOT descifrado (2026-11-01):**
- 16.1 MB de código PPU (Budokai 3 eran ~7 MB): más trabajo para el recompilador y más C++ generado.
- 25 módulos de sistema, 346 funciones. Contra la tabla de ps3recomp v0.18.0:
  - Completos: `sys_fs`, `cellGcmSys`, `cellSysutil`, `cellGame`, `cellResc`, `cellAudio`, `cellFont(FT)`, `cellL10n`, `cellRtc`, `cellSync`,
    `cellSpursJq`, `sysPrxForUser`, `sceNp`, `sceNpTus`, `sceNpTrophy`, `sys_net`, `cellNetCtl`.
  - Parcial: **`cellSpurs`** (24 funciones).
  - Sin fila en la tabla: `sceNp2`, `cellSysutilAvc2` (chat de voz), `cellSysutilAvconfExt`, `sys_io` (mando), `cellOskExtUtility`.
    Los de red/voz pueden ser stubs (no hay online en Switch); `sys_io` hay que comprobar en el código de ps3recomp.
  - No usa `cellAdec`, `cellVdec`, `cellPamf` ni `cellSail`: el audio y el vídeo los hace CRI por su cuenta.
- **SPU, el punto crítico.** Solo hay 1 SPU ELF suelto, pero el EBOOT lleva:
  - **CRI** como trabajos SPURS: ADX/HCA (`AtomDecoder`, `HcaMixer`, `DspPack1/2`, `DspPitchShifter`, `AsrVoice`) y vídeo MPV/DCT (Sofdec).
  - **Havok Physics 7.1.0** con colisiones en SPU (`SpuCollisionCallback`, `useSplitCollisionPipelineOnSpu`).
  - Post-proceso **PPFX** y shaders Cg precompilados (`TexUtil_PSGL/*.fpo`).
- Estrategia derivada: en vez de traducir los trabajos SPU de CRI, **interceptar CRI a nivel de PPU** y decodificar
  HCA/ADX/USM con código nativo (vgmstream/FFmpeg), como hace Budokai-NX con su `video_sfd.cpp`. Havok: comprobar si funciona con
  su ruta PPU (sin SPU) antes de intentar traducir sus programas SPU.
- [x] Crear `baserom.md` y `tools/check_game.py` (patrón de Budokai-NX).
- [x] Rellenar `baserom.md` con los tamaños y SHA-256 reales.

**Lo que dice el disco (2026-11-01):**
- Todo el juego son 3.25 GiB: `EBOOT.BIN` (26 MB), `resource.cpk` (2.7 GiB, 5996 archivos) y un vídeo `.usm`. Cabe sin problemas en la SD.
- Middleware **CRI**: CPK (archivos), ADX2 `.acb/.awb` (audio), Sofdec2 `.usm` (vídeo). Va enlazado dentro del EBOOT, así que
  no depende de los módulos de audio/vídeo de ps3recomp que están a medias (`cellAdec`), pero su decodificación correrá en CPU/SPU de la Switch.
- Formatos de Dimps `.emb/.emo/.emm/.ema` (motor "adam"), la misma familia que Raging Blast/Xenoverse; hay herramientas de la comunidad para leerlos.
- Shaders precompilados aparte, en `archive/adam_shader/*.emz` (VS/PS de escenario y de personaje). Equivale al escaneo de shaders
  que hizo Budokai-NX en el `.xex`: aquí ya están separados del ejecutable.
- Interfaz en EN/FR/IT/**SP**/BR/JP; un solo juego de voces. Los DLC están en el disco (`resource/dlc/EU`).
- [ ] Comprobar que el juego corre bien en RPCS3 (referencia de comportamiento y fuente de logs: qué módulos HLE y cuántos SPU usa).

### Fase 1 — Port a PC con ps3recomp (Windows, D3D12/Vulkan)
- [x] Fijar commit de ps3recomp en `dependencies.json`. Clon en `deps/ps3recomp`, herramientas Python en `deps/.venv` (incluye CMake y Ninja).
- [x] Traducir PPU → C++ (2026-11-02). Resultado en `local/recomp/recompiled/` (privado, 263 MB):
  **27 217 funciones**, 26 archivos de ~150 000 líneas, 0 instrucciones sin implementar, 30 tablas de salto resueltas.
  Comandos (desde la raíz):
  ```sh
  deps/.venv/Scripts/python deps/ps3recomp/tools/ppu_loader.py local/EBOOT.elf -o local/recomp/out
  deps/.venv/Scripts/python deps/ps3recomp/tools/ppu_lifter.py local/EBOOT.elf --functions local/recomp/out/EBOOT.functions.json --hle-stubs local/recomp/out/EBOOT.imports.json --code-end 0xa4c664 --chunk-lines 150000 -j 10 -o local/recomp/recompiled
  deps/.venv/Scripts/python deps/ps3recomp/tools/gen_hle_nids.py --all --out local/recomp/recompiled/ppu_hle_nids.cpp
  ```
  `--code-end 0xa4c664` = fin de las secciones ejecutables (`.text` + stubs); el resto del segmento R-X son datos.
- [x] Cobertura de funciones de sistema: **275/346** ya en ps3recomp (`local/recomp/out/missing_hle.json`). Faltan 71:
  - **Necesarias:** `cellSpurs` Taskset2 (5) y `cellSpursJq` Port2/JoinJobQueue (6), `cellFont` (5), `cellResc SetWaitFlip`,
    `cellGcm _Func15`, `cellAudioSetPortLevel`, `cellGamePatchCheck`, `cellSaveDataFixedDelete`.
  - **Stub sin más** (online/voz/teclado): `sceNp*`, `sceNpTus`, `sceNp2`, `cellSysutilAvc2`, `sys_net` (2), `cellKb*`, `cellOsk*`.
- [x] SPU: único SPU ELF = `cri_mpvps3` (vídeo CRI). Los trabajos SPURS de CRI y Havok se capturan en ejecución con `SPU_DUMP_MISS`.
- [x] Instalar Visual Studio 2022 Build Tools + LLVM 23.1.4 (clang-cl) y compilar (2026-11-02): `tools\build_pc.cmd`
  genera `build/pc/BraveSoldiersRecomp.exe` (210 MB) sin errores. Proyecto en `pc/` (plantilla de ps3recomp).
- [x] Primer arranque (2026-11-02, tras desactivar Smart App Control): carga, TLS, D3D12 y ventana OK; llega a los
  constructores estáticos y se atasca porque el `malloc` de la libc del juego devuelve NULL. Detalle en `NOTAS_DEPURACION.md`.
- [x] Arreglar la inicialización de memoria (2026-11-02): era el TOC perdido en la ruta HLE rápida; además `cellFsReadWithOffset`, id de título desde PARAM.SFO y endianness de trofeos. El juego llega a «Comprobando contenido descargable...» sin punteros nulos.
- [x] Pasar la comprobación de DLC (compilación Fast, JobQueue/cellFont, caché de PSO fallidos, unidades de textura 4–15).
- [x] Recompilar la imagen SPU de CRI Mana (ELF embebido en 0x01004580).
- [x] Primer fotograma con contenido (2026-11-02): 64 RT fuera de pantalla + `GCM_PRESENT_RT=EE0000` muestran las ruinas del Santuario.
- [x] Logos de arranque a 60 FPS sin parpadeo (INLINE_ARRAY, RT 1280x720, un present por flip)
- [ ] Composición final de la fase del Santuario/título (sin draws a pantalla), cielo, UI 2D, animación (T-pose); vídeo de intro (CRI Mana) se atasca.
- [ ] Implementar las funciones de SPURS que faltan.
- [ ] Extraer y levantar los programas SPU; implementar lo que falte de cellSpurs / módulos que use el juego.
- [ ] Arranque → menú → combate en PC. **No pasar a Switch hasta que esto sea jugable.**

### Fase 2 — Runtime Horizon
- [ ] NRO de diagnóstico deko3d (triángulo + mando + log), copiando la estructura de `Budokai-NX/switch/` y su toolchain Docker (`ghcr.io/autorunhq/switch-dev`).
- [ ] Portar el runtime de ps3recomp a libnx: hilos (`thrd`), memoria guest (reserva de 4 GB virtuales con `virtmemReserve`), FS con rutas absolutas `sdmc:/` (mismo bug que Budokai 0.2.0), audio (`audren`), mando (`hid`).
- [ ] NRO loader: carga el EBOOT verificado e inicializa la memoria sin ejecutar.

### Fase 3 — Gráficos
- [ ] Boot trace: capturar el primer comando cellGcm/RSX.
- [ ] Traductor offline de shaders RSX → GLSL → DKSH.
- [ ] Backend RSX → deko3d (texturas tiled/swizzled, surfaces, blending, depth).

### Fase 4 — Rendimiento y distribución
- [ ] Perfilado en consola; hilos SPU repartidos entre núcleos, funciones calientes en nativo, LTO/PGO.
- [ ] Preparador web local (sin subir datos) + actualizador con SHA-256.
- [ ] Repo sin ningún archivo del juego ni código generado a partir de él.

## 5. Reglas que heredamos de las referencias

- No distribuir ISO, EBOOT, datos extraídos, ni código/shaders generados del juego.
- Cada dependencia con commit fijado y sus parches aparte (`patches/`), nunca editar el C++ generado.
- No declarar algo "funciona" sin prueba en consola; documentar cada versión (`CORRECCIONES-x.y.md`).
- Conservar licencias y créditos (ps3recomp MIT, deko3d zlib, libnx ISC, plume MIT, uam).
