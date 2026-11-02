# Archivos necesarios

Aporta estos archivos desde tu copia **original** de *Saint Seiya: Brave Soldiers* (PS3).
**Ninguno se distribuye con este proyecto.** El recompilado espera un ejecutable exacto, así que
cada versión soportada lleva su hash aquí (mismo criterio que `baserom.md` de Budokai-NX).

## Versión soportada

| Región | Código | APP_VER | Firmware mínimo | Estado |
|---|---|---|---|---|
| Europa | **BLES01936** | 01.00 (disco, sin update) | 4.46 | **Verificada 2026-11-01** |
| Japón | BLJS10236 | — | — | No soportada por ahora |

Idiomas de interfaz en los datos: `EN`, `FR`, `IT`, `SP` (español), `BR` (portugués) y `JP`
(carpetas `resource/ui/*` dentro de `resource.cpk`). Hay un solo juego de voces (`*_VC.acb`), sin variante por idioma.

## Archivos verificados (`PS3_GAME/`)

El hash de la ISO completa **no** sirve de referencia: cada volcado o reempaquetado da una ISO distinta.
Lo que cuenta son estos archivos.

| Archivo | Tamaño (bytes) | SHA-256 |
|---|---|---|
| `PARAM.SFO` | 1,092 | `DECC02942CFF18E50F593120D100CCA027285C2C31DE4E501940BDD740AEFE65` |
| `USRDIR/EBOOT.BIN` (SELF cifrado) | 27,320,568 | `78BF735E916F6A0C59104C520C7104E942F9672267359F77B10FB972AAEC6EA5` |
| `USRDIR/resource.cpk` | 2,903,228,896 | `DDAA2BA996F8D9F8792A117191CF963B5BD0117A7609DA00C6D936950F3057E4` |
| `USRDIR/resource.h` | 1,293,647 | `AD77CA0DF6728BA0385C4F71BE5AB692D592ECB1A36D5F1325D1390E1B4132B5` |
| `USRDIR/resource/movie/SEIYAps3-k.usm` | 275,655,904 | `C76F20F43C3B4F3F19AF5ACC2FC048D16D39F6E130223AB5FE9BD4051E858A85` |
| `USRDIR/archive/adam_shader/PsBgShader.emz` | 34,123 | `D1FD1E9B7443D091EF09869B3C8169643FEE3AFF49DDDEA502B3B3BEAB420528` |
| `USRDIR/archive/adam_shader/PsUserShader.emz` | 63,803 | `DABD248371EC3F06C34CAA53C8498678E3B256460035407DCEF75671F99128DC` |
| `USRDIR/archive/adam_shader/VsBgShader.emz` | 48,031 | `DDC1A05C5D669C3328C6957683DA200B28612A594A0070224141ED78ED73D862` |
| `USRDIR/archive/adam_shader/VsUserShader.emz` | 95,053 | `D90C6BD9BFA6FDEF233AAEA1186F59BBAB38EAE24C115964D489E2050E572687` |
| `USRDIR/archive/adam_shader/setting_technique.emz` | 7,229 | `00583E1EA631FC1B765C3FFAF4C1554C044EB412C690058A75E2D81EF887A7D6` |

### EBOOT descifrado (RPCS3, *Decrypt PS3 Binaries*)

| Archivo | Tamaño (bytes) | SHA-256 |
|---|---|---|
| `EBOOT.elf` | 27,318,136 | `F0228A87C33BC000442F0B4723B7902446D884B14437B5F2888E8B62E85AF308` |

ELF PPU de 64 bits, SDK 4.40. Código en `0x10000` (16.1 MB), datos en `0x1030000`.
Importa 346 funciones de 25 módulos de sistema; ver `python tools/check_game.py local/EBOOT.elf`.

No hay `.sprx` propios del juego en el disco: todo el código está en `EBOOT.BIN`.

## DLC

Los datos de los DLC ya vienen **dentro del disco** (`resource/dlc/EU/DLC00…`, 105 archivos en `resource.cpk`);
la tienda solo vendía la licencia que los desbloquea. El port no depende de ningún `.pkg`: los DLC se tratarán
más adelante como desbloqueo, no como datos aparte.

## Cómo obtener los archivos

1. Vuelca tu disco en una carpeta o ISO (PS3 con HEN/CFW, o lector Blu-ray compatible).
2. Comprueba la copia: `python tools/check_game.py RUTA`.
3. Instala en RPCS3 el firmware que trae el propio disco (`PS3_UPDATE/PS3UPDAT.PUP`, 4.46) o uno más nuevo de la web de Sony.
4. Descifra `EBOOT.BIN` con RPCS3: *Utilities → Decrypt PS3 Binaries*.
5. Guarda el resultado en `local/` (ignorado por git).
