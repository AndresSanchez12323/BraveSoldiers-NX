@echo off
rem Compila el port de PC (Windows, clang-cl + Ninja).
rem Uso: tools\build_pc.cmd [trabajos] [debug]
rem   Por defecto: configuracion "Fast" en build\pc-fast -- el codigo recompilado a -O1 (lo que pide la
rem   plantilla de ps3recomp), el runtime a -O2 y NDEBUG (sin capa de depuracion de D3D12).
rem   "debug": build\pc en Debug (/Od /RTC1), decenas de veces mas lento; solo para depurar el runtime.
rem   Cada archivo generado pide ~2 GB de RAM: con 16 GB, 4-6 trabajos.
setlocal
set ROOT=%~dp0..
set JOBS=%1
if "%JOBS%"=="" set JOBS=4
set CFG=Fast
set OUT=%ROOT%\build\pc-fast
if /i "%2"=="debug" (set CFG=Debug& set OUT=%ROOT%\build\pc)

call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
set PATH=C:\Program Files\LLVM\bin;%ROOT%\deps\.venv\Scripts;%PATH%

cmake -S "%ROOT%\pc" -B "%OUT%" -G Ninja ^
  -DCMAKE_C_COMPILER=clang-cl -DCMAKE_CXX_COMPILER=clang-cl -DCMAKE_BUILD_TYPE=%CFG% ^
  "-DCMAKE_C_FLAGS_FAST=/DNDEBUG" "-DCMAKE_CXX_FLAGS_FAST=/DNDEBUG" || exit /b 1
cmake --build "%OUT%" --parallel %JOBS%
