param(
    [string]$ProjectPath = "",
    [string]$Entry = "main.py",
    [string]$AppName = "NEXUS",
    [string]$Icon = "",
    [switch]$InstallDeps,
    [switch]$Clean,
    [switch]$SkipCorePyd,
    [switch]$KeepLocalSecrets
)

$ErrorActionPreference = "Stop"

function Step($Text) {
    Write-Host ""
    Write-Host "==> $Text" -ForegroundColor Cyan
}

function Ok($Text) {
    Write-Host "[OK] $Text" -ForegroundColor Green
}

function Warn($Text) {
    Write-Host "[AVISO] $Text" -ForegroundColor Yellow
}

function Fail($Text) {
    Write-Host "[ERROR] $Text" -ForegroundColor Red
    exit 1
}

function Copy-TreeClean($Source, $Destination) {
    $sourceRoot = (Resolve-Path -LiteralPath $Source).Path
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null

    $excludeDirs = @(
        "\.git\",
        "\.venv\",
        "\venv\",
        "\env\",
        "\build\",
        "\dist\",
        "\__pycache__\",
        "\.mypy_cache\",
        "\.pytest_cache\",
        "\assets\voice_samples\",
        "\config\tts_cache\"
    )

    $excludeFiles = @(
        "api_keys.json",
        "api_keys.json.enc",
        "license.json",
        "nexus.log",
        "last_captured_screen.png"
    )

    Get-ChildItem -LiteralPath $sourceRoot -Recurse -Force | ForEach-Object {
        $full = $_.FullName
        $rel = $full.Substring($sourceRoot.Length).TrimStart("\")
        if ([string]::IsNullOrWhiteSpace($rel)) { return }

        $relKey = "\" + ($rel -replace "/", "\")
        foreach ($dir in $excludeDirs) {
            if ($relKey.IndexOf($dir, [System.StringComparison]::OrdinalIgnoreCase) -eq 0 -or
                $relKey.IndexOf($dir, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
                return
            }
        }

        if (-not $_.PSIsContainer) {
            if ($excludeFiles -contains $_.Name) { return }
            if ($_.Name -match "backup|\.bak$|\.tmp$|\.log$|secret|token|credential") { return }
            if (-not $KeepLocalSecrets -and $_.Name -match "license|api_keys") { return }
        }

        $dest = Join-Path $Destination $rel
        if ($_.PSIsContainer) {
            New-Item -ItemType Directory -Force -Path $dest | Out-Null
        } else {
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
            Copy-Item -LiteralPath $full -Destination $dest -Force
        }
    }
}

if ([string]::IsNullOrWhiteSpace($ProjectPath)) {
    $ProjectPath = Read-Host "Ruta del proyecto NEXUS fuente"  # ✅ CAMBIADO
}

$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not (Test-Path -LiteralPath (Join-Path $ProjectPath $Entry))) {
    Fail "No encontre $Entry en $ProjectPath"
}

if ([string]::IsNullOrWhiteSpace($Icon)) {
    $possibleIcons = @(
        "assets\current_icon.ico",
        "assets\nexus_icono.ico",
        "face.ico"
    )
    foreach ($candidate in $possibleIcons) {
        $candidatePath = Join-Path $ProjectPath $candidate
        if (Test-Path -LiteralPath $candidatePath) {
            $Icon = $candidate
            break
        }
    }
}

Step "Preparando estructura segura de NEXUS"
Write-Host "Proyecto fuente: $ProjectPath"
Write-Host "Entrada: $Entry"
Write-Host "Nombre: $AppName"

$venvPython = Join-Path $ProjectPath ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    Step "Creando entorno virtual con virtualenv"
    Push-Location $ProjectPath
    python -m pip install virtualenv
    python -m virtualenv .venv
    Pop-Location
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    Fail "No se pudo crear o encontrar .venv\Scripts\python.exe"
}

Push-Location $ProjectPath

Step "Actualizando herramientas de compilacion"
& $venvPython -m pip install --upgrade pip setuptools wheel
& $venvPython -m pip install pyinstaller

if (-not $SkipCorePyd) {
    & $venvPython -m pip install nuitka ordered-set zstandard
}

if ($InstallDeps) {
    if (Test-Path -LiteralPath "requirements.txt") {
        Step "Instalando dependencias de requirements.txt"
        & $venvPython -m pip install -r requirements.txt
    } else {
        Warn "No encontre requirements.txt. Saltando instalacion de dependencias del proyecto."
    }
}

$stageRoot = Join-Path $ProjectPath "build\NEXUS_secure_stage"  # ✅ CAMBIADO
$distRoot = Join-Path $ProjectPath "dist"
$distApp = Join-Path $distRoot $AppName

if ($Clean) {
    Step "Limpiando compilaciones anteriores"
    if (Test-Path -LiteralPath $stageRoot) { Remove-Item -LiteralPath $stageRoot -Recurse -Force }
    if (Test-Path -LiteralPath $distApp) { Remove-Item -LiteralPath $distApp -Recurse -Force }
    if (Test-Path -LiteralPath (Join-Path $distRoot "$AppName.exe")) { Remove-Item -LiteralPath (Join-Path $distRoot "$AppName.exe") -Force }
    if (Test-Path -LiteralPath "$AppName.spec") { Remove-Item -LiteralPath "$AppName.spec" -Force }
}

Step "Copiando proyecto a staging sin secretos personales"
if (Test-Path -LiteralPath $stageRoot) { Remove-Item -LiteralPath $stageRoot -Recurse -Force }
Copy-TreeClean -Source $ProjectPath -Destination $stageRoot

# ─────────────────────────────────────────────────────────────────────────
# ✅ NUEVO: Verificacion del modelo de voz Vosk en el staging
# ─────────────────────────────────────────────────────────────────────────
Step "Verificando modelo de voz Vosk"
$voskPath = Join-Path $stageRoot "config\vosk_model"
if (-not (Test-Path -LiteralPath $voskPath) -or (Get-ChildItem -LiteralPath $voskPath -ErrorAction SilentlyContinue).Count -eq 0) {
    Warn "config\vosk_model no existe o esta vacio. El .exe compilado NO tendra reconocimiento de voz local"
    Warn "(afecta 'responder solo por nombre', deteccion de interrupciones y modo offline)."
    Warn "Descarga un modelo desde https://alphacephei.com/vosk/models y colocalo en:"
    Warn "  $ProjectPath\config\vosk_model"
    $continue = Read-Host "Continuar compilando de todos modos? (s/n)"
    if ($continue -ne "s") { Fail "Compilacion cancelada por falta de modelo Vosk." }
} else {
    Ok "Modelo Vosk encontrado: $voskPath"
}
# ─────────────────────────────────────────────────────────────────────────

Push-Location $stageRoot

Step "Creando configuracion publica minima"
New-Item -ItemType Directory -Force -Path "config" | Out-Null
New-Item -ItemType Directory -Force -Path "memory" | Out-Null
New-Item -ItemType Directory -Force -Path "assets\voice_samples\nexus" | Out-Null
New-Item -ItemType Directory -Force -Path "assets\voice_samples\nexus_processed" | Out-Null
New-Item -ItemType Directory -Force -Path "config\tts_cache" | Out-Null

@'
{
  "supabase_url": "",
  "supabase_anon_key": "",
  "gemini_api_key": "",
  "spotify_client_id": "",
  "spotify_client_secret": "",
  "spotify_redirect_uri": "http://127.0.0.1:8888/callback",
  "openrouter_api_key": "",
  "tmdb_api_key": "",
  "timezone": "America/Lima",
  "language": "es-ES",
  "nexus_theme": "gold"
}
'@ | Set-Content -LiteralPath "config\api_keys.example.json" -Encoding UTF8

@'
{
  "notes": {},
  "habits": {},
  "preferences": {},
  "context": {},
  "identity": {}
}
'@ | Set-Content -LiteralPath "memory\long_term.json" -Encoding UTF8

@'
{
  "name": "",
  "habits": {},
  "preferences": {},
  "notes": {}
}
'@ | Set-Content -LiteralPath "config\user_profile.json" -Encoding UTF8

if (-not (Test-Path -LiteralPath "config\morning_brief_state.json")) {
    "{}" | Set-Content -LiteralPath "config\morning_brief_state.json" -Encoding UTF8
}

if (-not (Test-Path -LiteralPath "SPOTIFY_SETUP.txt")) {
@'
CONFIGURAR SPOTIFY EN NEXUS  # ✅ CAMBIADO

1. Entra a https://developer.spotify.com/dashboard
2. Crea una app.
3. Agrega estos Redirect URI:
   http://127.0.0.1:8888/callback
   http://127.0.0.1:8765/callback
4. Copia Client ID y Client Secret.
5. Abre NEXUS > Configuracion > Spotify.  # ✅ CAMBIADO
6. Activa configuracion avanzada.
7. Pega Client ID, Client Secret y Redirect URI.
8. Guarda cambios.
9. Presiona Conectar con Spotify.

Si se queda cargando, casi siempre falta uno de los Redirect URI o no se guardaron los cambios.
'@ | Set-Content -LiteralPath "SPOTIFY_SETUP.txt" -Encoding UTF8
}

if (-not $SkipCorePyd -and (Test-Path -LiteralPath "core_main.py")) {
    Step "Compilando core_main.py a .pyd con Nuitka"
    & $venvPython -m nuitka --module "core_main.py" --output-dir "build\compiled_core" --remove-output --assume-yes-for-downloads
    $pyd = Get-ChildItem -LiteralPath "build\compiled_core" -Filter "core_main*.pyd" -File -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($pyd) {
        Copy-Item -LiteralPath $pyd.FullName -Destination ".\" -Force
        Remove-Item -LiteralPath "core_main.py" -Force
        Ok "Nucleo protegido: $($pyd.Name)"
    } else {
        Fail "Nuitka no genero core_main*.pyd. Instala Visual Studio Build Tools o usa -SkipCorePyd."
    }
} elseif ($SkipCorePyd) {
    Warn "Saltando compilacion .pyd del nucleo por parametro -SkipCorePyd."
} else {
    Warn "No encontre core_main.py; se compilara lo que exista en el proyecto."
}

Step "Compilando NEXUS con PyInstaller en modo seguro"  # ✅ CAMBIADO
$pyiArgs = @(
    "--name", $AppName,
    "--onedir",
    "--noconsole",
    "--clean",
    "--contents-directory", "_internal",
    "--add-data", "assets;assets",
    "--add-data", "config;config",
    "--add-data", "memory;memory",
    "--add-data", "core;core",
    "--add-data", "actions;actions",
    "--add-data", "NexusInicioRAV.wav;.",  # ✅ CAMBIADO
    "--add-data", "SuspenderNexus.wav;.",
    "--add-data", "assets\sounds;assets\sounds",
    "--add-data", "ffmpeg.exe;.",
    "--add-data", "ffprobe.exe;.",
    "--add-data", "yolov8n.pt;.",
    "--hidden-import", "PyQt6",
    "--hidden-import", "PyQt6.QtCore",
    "--hidden-import", "PyQt6.QtGui",
    "--hidden-import", "PyQt6.QtWidgets",
    "--hidden-import", "PyQt6.QtWebEngineWidgets",
    "--hidden-import", "google.genai",
    "--hidden-import", "spotipy",
    "--hidden-import", "spotipy.oauth2",
    "--hidden-import", "vosk",
    "--hidden-import", "sounddevice",
    "--hidden-import", "pyautogui",
    "--hidden-import", "pyperclip",
    "--hidden-import", "pygetwindow",
    "--hidden-import", "cv2",
    "--hidden-import", "numpy",
    "--hidden-import", "mss",
    "--hidden-import", "psutil",
    "--hidden-import", "bs4",
    "--hidden-import", "requests",
    "--hidden-import", "PIL",
    "--hidden-import", "pytesseract",
    "--hidden-import", "yt_dlp",
    "--hidden-import", "fitz",
    "--hidden-import", "docx",
    "--hidden-import", "pdf2docx",
    "--hidden-import", "pygame",
    "--hidden-import", "bleak",
    "--hidden-import", "flask",
    "--hidden-import", "flask_socketio",
    "--hidden-import", "gtts",
    "--hidden-import", "edge_tts",
    "--hidden-import", "cryptography",
    "--hidden-import", "soundfile",
    "--hidden-import", "librosa",
    "--hidden-import", "scipy",
    "--hidden-import", "openpyxl",
    "--hidden-import", "pandas",
    "--hidden-import", "comtypes",
    "--hidden-import", "pycaw",
    "--hidden-import", "win10toast",
    "--hidden-import", "send2trash",
    "--hidden-import", "youtube_transcript_api",
    "--hidden-import", "pywinauto",
    "--hidden-import", "pptx",
    "--hidden-import", "keyboard",
    "--hidden-import", "mouse",
    "--hidden-import", "pyaudio",
    "--hidden-import", "tkinter",
    "--hidden-import", "playwright",
    "--hidden-import", "pptx",
    "--hidden-import", "ultralytics",
    "--hidden-import", "torch",
    "--collect-all", "vosk",
    "--collect-all", "playwright",
    "--collect-all", "pptx",
    "--collect-all", "ultralytics",
    "--collect-all", "torch",
    "--copy-metadata", "ultralytics",
    "--copy-metadata", "torch"
)

if (-not [string]::IsNullOrWhiteSpace($Icon)) {
    if (Test-Path -LiteralPath $Icon) {
        $pyiArgs += @("--icon", $Icon)
    } else {
        Warn "Icono no encontrado en staging: $Icon"
    }
}

$pyiArgs += $Entry

$env:PYINSTALLER_NO_ISOLATE = "1"
& $venvPython -m PyInstaller @pyiArgs

Step "Limpieza final del dist"
$built = Join-Path $stageRoot "dist\$AppName"
if (-not (Test-Path -LiteralPath $built)) {
    Fail "No encontre la salida esperada: $built"
}

Get-ChildItem -LiteralPath $built -Recurse -Force -File | Where-Object {
    $_.Name -in @("api_keys.json", "api_keys.json.enc", "license.json", "nexus.log") -or  # ✅ CAMBIADO
    $_.Name -match "backup|\.bak$|\.tmp$|secret|token|credential"
} | ForEach-Object {
    Remove-Item -LiteralPath $_.FullName -Force
}

foreach ($folder in @(
    "assets\voice_samples",
    "_internal\assets\voice_samples",
    "config\tts_cache"
)) {
    $path = Join-Path $built $folder
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force
    }
}

New-Item -ItemType Directory -Force -Path (Join-Path $built "assets\voice_samples\nexus") | Out-Null  # ✅ CAMBIADO
New-Item -ItemType Directory -Force -Path (Join-Path $built "assets\voice_samples\nexus_processed") | Out-Null  # ✅ CAMBIADO
New-Item -ItemType Directory -Force -Path (Join-Path $built "config\tts_cache") | Out-Null

Pop-Location
Pop-Location

Step "Copiando salida final al dist real"
if (Test-Path -LiteralPath $distApp) { Remove-Item -LiteralPath $distApp -Recurse -Force }
New-Item -ItemType Directory -Force -Path $distRoot | Out-Null
Copy-Item -LiteralPath $built -Destination $distRoot -Recurse -Force

# ─────────────────────────────────────────────────────────────────────────
# ✅ NUEVO: Confirmacion de que Vosk quedo incluido en el build final
# ─────────────────────────────────────────────────────────────────────────
$finalVoskPath = Join-Path $distApp "_internal\config\vosk_model"
if (Test-Path -LiteralPath $finalVoskPath) {
    Ok "Vosk incluido correctamente en el build final."
} else {
    Warn "ATENCION: Vosk NO quedo incluido en el build final."
}
# ─────────────────────────────────────────────────────────────────────────

Ok "NEXUS compilado:"  # ✅ CAMBIADO
Write-Host $distApp -ForegroundColor Green
Write-Host ""
Write-Host "Metodo usado:" -ForegroundColor Cyan
Write-Host "- Staging limpio sin secretos"
Write-Host "- core_main.py -> core_main*.pyd con Nuitka, salvo que uses -SkipCorePyd"
Write-Host "- PyInstaller --onedir --noconsole --contents-directory _internal"
Write-Host "- Limpieza final de APIs, licencia, logs, backups, tokens, muestras de voz y caches"
Write-Host ""
Write-Host "Para compilar:" -ForegroundColor Cyan
Write-Host "powershell -ExecutionPolicy Bypass -File `"$PSCommandPath`" -ProjectPath `"$ProjectPath`" -InstallDeps -Clean"