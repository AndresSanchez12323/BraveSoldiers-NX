# Arranca el port de PC durante N segundos y guarda la salida en una carpeta nueva.
# Uso (desde la raiz):
#   pwsh tools/run_game.ps1 -secs 45 -dir local/recomp/prueba1 -envs "PRESENT_LOG=2000;VP_SUBMIT=50"
#   pwsh tools/run_game.ps1 -secs 45 -dir local/recomp/prueba2 -capture   # ademas guarda window.png
# La salida queda en <dir>/out.txt y <dir>/err.txt. Usa SIEMPRE una carpeta nueva por prueba.
param([int]$secs = 40, [Parameter(Mandatory = $true)][string]$dir, [string]$envs = "", [switch]$capture)
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
New-Item -ItemType Directory -Force $dir | Out-Null
$dir = (Resolve-Path $dir).Path
# El video de intro (CRI Mana) se atasca; ocultarlo deja seguir al juego.
$env:PS3_FS_HIDE = "SEIYAps3-k.usm"
foreach ($kv in $envs.Split(";")) { if ($kv) { $a = $kv.Split("=", 2); Set-Item "env:$($a[0])" $a[1] } }
$p = Start-Process -FilePath "$root\build\pc-fast\BraveSoldiersRecomp.exe" `
    -ArgumentList "`"$root/local/BLES01936/PS3_GAME/USRDIR/EBOOT.elf`"" -WorkingDirectory $dir -PassThru `
    -RedirectStandardOutput "$dir\out.txt" -RedirectStandardError "$dir\err.txt"
Start-Sleep -Seconds $secs
if ($capture) {
    Add-Type -AssemblyName System.Drawing
    Add-Type @"
using System; using System.Runtime.InteropServices;
public class W { [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
public struct RECT { public int L,T,R,B; } }
"@
    $p.Refresh(); $h = $p.MainWindowHandle
    [W]::SetForegroundWindow($h) | Out-Null; Start-Sleep -Milliseconds 700
    $r = New-Object W+RECT; [W]::GetWindowRect($h, [ref]$r) | Out-Null
    $bmp = New-Object System.Drawing.Bitmap ($r.R - $r.L), ($r.B - $r.T)
    $g = [System.Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen($r.L, $r.T, 0, 0, $bmp.Size)
    $bmp.Save("$dir\window.png"); "captura: $dir\window.png"
}
Stop-Process -Id $p.Id -Force
"hecho: $dir"
