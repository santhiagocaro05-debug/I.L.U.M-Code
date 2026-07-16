import re

def patch():
    with open('metodoNT+PY.ps1', 'r', encoding='utf-8') as f:
        content = f.read()

    # We will remove Nuitka install and add pyarmor
    content = content.replace(
        "& $venvPython -m pip install nuitka ordered-set zstandard",
        "& $venvPython -m pip install pyarmor ordered-set zstandard"
    )

    # Replace the Nuitka block with PyArmor
    old_nuitka_block = """if (-not $SkipCorePyd -and (Test-Path -LiteralPath "core_main.py")) {
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
}"""

    new_pyarmor_block = """Step "Encriptando y ofuscando todo el codigo fuente con PyArmor"
# Ejecutamos PyArmor sobre toda la carpeta staging
& $venvPython -m pyarmor gen -O pyarmor_dist -r .
if (Test-Path "pyarmor_dist") {
    # Mover archivos ofuscados de vuelta al raiz staging
    Copy-Item -Path "pyarmor_dist\\*" -Destination "." -Recurse -Force
    Remove-Item "pyarmor_dist" -Recurse -Force
    Ok "Codigo fuente ofuscado correctamente."
} else {
    Fail "Fallo la ofuscacion con PyArmor."
}"""

    content = content.replace(old_nuitka_block, new_pyarmor_block)

    with open('metodoNT+PY.ps1', 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    patch()
