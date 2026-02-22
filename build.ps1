<#
build.ps1

Automatiza la creación de un único ejecutable con PyInstaller.

Uso mínimo:
    .\build.ps1

Opciones:
    -Entry <script>        Archivo Python de entrada (por defecto: unify_files.py)
    -OutputName <name>     Nombre base del ejecutable (por defecto: unify_files)
    -Icon <ruta_ico>       (Opcional) ruta a un icono .ico
    -NoInstall             No instala dependencias desde requirements.txt
    -Clean                 Borra carpetas build/ y dist/ antes de construir

El script intentará usar el comando 'python' disponible en PATH o 'py' como fallback.
Si dispone de un entorno virtual en `.venv`, lo activará automáticamente (siempre que PowerShell lo permita).
#>

param(
    [string]$Entry = "unify_files.py",
    [string]$OutputName = "unify_files",
    [string]$Icon = "",
    [switch]$NoInstall,
    [switch]$Clean
)

Set-StrictMode -Version Latest

Push-Location $PSScriptRoot
try {
    Write-Host "[build] Directorio de trabajo: $PSScriptRoot"

    # Determinar comando Python
    $pythonCmd = (Get-Command python -ErrorAction SilentlyContinue).Path
    if (-not $pythonCmd) {
        $pyLauncher = (Get-Command py -ErrorAction SilentlyContinue).Path
        if ($pyLauncher) {
            $pythonCmd = "py -3"
        }
    }

    if (-not $pythonCmd) {
        Write-Error "No se encontró intérprete Python en PATH. Asegúrate de tener 'python' o el lanzador 'py'."
        exit 3
    }

    # Activar venv si existe
    $venvActivate = Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1"
    if (Test-Path $venvActivate) {
        try {
            Write-Host "[build] Activando venv: .venv"
            & $venvActivate
        } catch {
            Write-Warning "No se pudo activar .venv automáticamente: $_"
        }
    }

    if (-not $NoInstall) {
        if (Test-Path "requirements.txt") {
            Write-Host "[build] Instalando dependencias desde requirements.txt"
            & $pythonCmd -m pip install --upgrade pip
            & $pythonCmd -m pip install -r requirements.txt
        } else {
            Write-Host "[build] requirements.txt no encontrado, se omite instalación de dependencias."
        }
    }

    if ($Clean) {
        Write-Host "[build] Limpiando carpetas build/ y dist/"
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue build,dist
    }

    # Construir comando de PyInstaller
    $specArgs = @("--noconfirm", "--clean", "--onefile")
    if ($Icon -and (Test-Path $Icon)) {
        $specArgs += "--icon=$Icon"
    }
    $specArgs += "--name"; $specArgs += $OutputName
    $specArgs += $Entry

    Write-Host "[build] Ejecutando PyInstaller..."
    # Usar python -m PyInstaller para evitar depender del PATH
    & $pythonCmd -m PyInstaller @specArgs

    if (Test-Path "dist\$OutputName.exe") {
        Write-Host "[build] Build completado: dist\$OutputName.exe"
        exit 0
    } else {
        Write-Error "[build] Falló la creación del ejecutable o no se encontró dist\$OutputName.exe"
        exit 2
    }
} finally {
    Pop-Location
}
