#!/usr/bin/env python3
"""
build_mac.py

Gera "my chaotic room.app" a partir de ../app.py. Roda em qualquer Mac sem
precisar instalar Python nem as dependencias. Os dados (banco, fotos e backups)
ficam na pasta do usuario, em ~/my chaotic room.

So funciona rodando no proprio Mac (o PyInstaller nao faz build cruzado).

Uso:
    cd mac
    pip3 install pyinstaller pywebview pillow
    python3 build_mac.py

Depois, copie "dist/my chaotic room.app" para a pasta Aplicativos.
"""

import os
import shutil
import sys

if sys.platform != "darwin":
    sys.exit("build_mac.py so roda no macOS. No Windows, use build_exe.py.")

import PyInstaller.__main__

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
NOME = "my chaotic room"
ICONES = os.path.join(RAIZ, "assets_icone", "icone_app_instrumentos")

args = [
    os.path.join(RAIZ, "app.py"),
    "--noconfirm",
    "--clean",
    # pasta (onedir), o formato recomendado pelo PyInstaller para .app
    "--windowed",
    "--name", NOME,
    "--distpath", os.path.join(AQUI, "dist"),
    "--workpath", os.path.join(AQUI, "build"),
    "--specpath", AQUI,
    "--icon", os.path.join(ICONES, "icone.icns"),
    "--add-data", f"{ICONES}:assets_icone/icone_app_instrumentos",
    "--add-data", f"{os.path.join(RAIZ, 'ui')}:ui",   # a interface (HTML/CSS/JS, fontes e icones)
    "--collect-all", "webview",                       # pywebview (janela com o WebKit do Mac)
]

print("Gerando o aplicativo (pode levar alguns minutos)...\n")
PyInstaller.__main__.run(args)

destino = os.path.join(AQUI, "dist", f"{NOME}.app")
if os.path.isdir(destino):
    print(f"\nPronto: {destino}")
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    if os.path.isdir(desktop):
        try:
            copia = os.path.join(desktop, f"{NOME}.app")
            if os.path.isdir(copia):
                shutil.rmtree(copia)
            shutil.copytree(destino, copia)
            print(f"Copiado para a Area de Trabalho: {copia}")
        except Exception as e:
            print(f"Nao consegui copiar para a Area de Trabalho automaticamente: {e}")
else:
    print("\nAlgo deu errado: o aplicativo nao foi encontrado em dist/.")
