# build_nuitka.ps1
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   ILUM AI - COMPILACION CON NUITKA" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Activar entorno virtual (si no está activo)
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    .\.venv\Scripts\Activate.ps1
}

Write-Host "[1/4] Verificando Nuitka..." -ForegroundColor Yellow
pip show nuitka > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Instalando Nuitka..." -ForegroundColor Yellow
    pip install nuitka
}

Write-Host "[2/4] Instalando dependencias adicionales..." -ForegroundColor Yellow
pip install ordered-set zstandard

Write-Host "[3/4] Limpiando builds anteriores..." -ForegroundColor Yellow
Remove-Item -Recurse -Force dist_nuitka -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force main.build -ErrorAction SilentlyContinue

Write-Host "[4/4] Compilando con Nuitka..." -ForegroundColor Yellow
Write-Host "Esto puede tomar 15-30 minutos. Por favor espera...`n" -ForegroundColor Red

nuitka `
    --standalone `
    --windows-console-mode=disable `
    --enable-plugin=pyqt6 `
    --follow-imports `
    --include-package=PyQt6 `
    --include-package=actions `
    --include-package=memory `
    --include-package=voice `
    --include-module=drm_manager `
    --include-module=beta_config `
    --include-module=login `
    --include-module=ui `
    --include-data-dir=assets=assets `
    --include-data-dir=config=config `
    --include-data-dir=actions=actions `
    --include-data-dir=memory=memory `
    --include-data-dir=core=core `
    --include-data-dir=voice=voice `
    --include-data-file=tts_engine.py=tts_engine.py `
    --include-data-file=ghost.skill=ghost.skill `
    --include-data-file=SuspenderIlum.wav=SuspenderIlum.wav `
    --windows-icon-from-ico=assets/ilum_icono.ico `
    --output-dir=dist_nuitka `
    --disable-console `
    main.py

if (Test-Path "dist_nuitka\main.dist\main.exe") {
    Write-Host "`n========================================" -ForegroundColor Green
    Write-Host "   COMPILACION EXITOSA" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "`nEjecutable generado en: dist_nuitka\main.dist\main.exe" -ForegroundColor White
    Write-Host "Para probar: .\dist_nuitka\main.dist\main.exe`n" -ForegroundColor White
} else {
    Write-Host "`nERROR: No se genero el ejecutable" -ForegroundColor Red
}


# pa ejecutar
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\build_nuitka.ps1

# 0tr0 met0d0 nuitka --standalone --enable-plugin=pyqt6 --follow-imports --include-data-dir=assets=assets --include-data-dir=config=config --output-dir=dist_nuitka main.py
# rec0m,endad0 nuitka --standalone --windows-console-mode=disable --enable-plugin=pyqt6 --follow-imports --include-data-dir=assets=assets --include-data-dir=config=config --include-data-dir=actions=actions --include-data-dir=memory=memory --include-data-dir=core=core --output-dir=dist_nuitka main.py