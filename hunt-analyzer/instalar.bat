@echo off
setlocal
cd /d "%~dp0"
title Hunt Analyzer - instalador
echo.
echo  === Hunt Analyzer: instalando ===
echo.

rem 0) aberto de dentro do zip: o Windows extrai so o .bat para uma pasta temporaria
if not exist "%~dp0controle.py" (
  echo  Extraia o zip primeiro: botao direito no zip, "Extrair tudo...", destino C:\
  echo  Depois rode o instalar.bat de dentro da pasta C:\HuntAnalyzer. Veja o LEIA-ME.
  goto fim_erro
)
rem no OneDrive as gravacoes, cerca de 3 GB por hora, sobem para a nuvem
echo "%~dp0" | findstr /i /c:"OneDrive" >nul && (
  echo  Esta pasta esta dentro do OneDrive: as gravacoes vao subir para a nuvem.
  echo  O melhor e extrair o zip em C:\ como diz o LEIA-ME e instalar de la.
  echo  Para instalar aqui mesmo assim, aperte uma tecla. Para parar, feche esta janela.
  pause >nul
)

rem 1) Python 3.10 ou mais novo: usa o que ja tiver; senao instala o 3.12 so para este usuario
set "PYEXE="
for %%V in (3.14 3.13 3.12 3.11 3.10) do (
  if not defined PYEXE (
    for /f "delims=" %%P in ('py -%%V -c "import sys;print(sys.executable)" 2^>nul') do set "PYEXE=%%P"
  )
)
if not defined PYEXE (
  for /f "delims=" %%P in ('python -c "import sys;assert sys.version_info>=(3,10);print(sys.executable)" 2^>nul') do set "PYEXE=%%P"
)
if not defined PYEXE (
  echo  Python nao encontrado. Instalando o Python 3.12 pelo winget...
  winget install -e --id Python.Python.3.12 --scope user --accept-source-agreements --accept-package-agreements
  set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
)
if not exist "%PYEXE%" goto sem_python
echo  Python: %PYEXE%
rem caminho comprido: o pip passa do limite de 260 letras do Windows dentro da .venv
"%PYEXE%" -c "import sys;sys.exit(len(sys.argv[1])>140)" "%~dp0." || (
  echo  O caminho desta pasta e comprido demais e a instalacao ia falhar.
  echo  Extraia o zip em C:\ como diz o LEIA-ME e rode o instalar.bat de la.
  goto fim_erro
)

rem 2) ambiente proprio do programa (.venv) + bibliotecas
if not exist ".venv\Scripts\python.exe" (
  echo  Criando o ambiente do programa...
  "%PYEXE%" -m venv .venv || goto erro
)
echo  Instalando as bibliotecas...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q --upgrade pip || goto erro
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt || goto erro
".venv\Scripts\python.exe" -c "import numpy, cv2, mss, PIL, tkinter; print('  Bibliotecas OK')" || goto erro

rem 3) atalho na area de trabalho; a pasta vai por variavel: apostrofo no caminho quebrava o comando
set "HA_PASTA=%~dp0"
powershell -NoProfile -Command "$l=[Environment]::GetFolderPath('Desktop')+'\Hunt Analyzer.lnk'; $s=(New-Object -ComObject WScript.Shell).CreateShortcut($l); $s.TargetPath=$env:HA_PASTA+'.venv\Scripts\pythonw.exe'; $s.Arguments='controle.py'; $s.WorkingDirectory=$env:HA_PASTA; $s.Save(); if (-not (Test-Path -LiteralPath $l)) { exit 1 }" || goto sem_atalho
echo  Atalho "Hunt Analyzer" criado na area de trabalho.

echo.
echo  Pronto! Abra pelo atalho "Hunt Analyzer" ou pelo abrir.bat desta pasta.
echo.
pause
exit /b 0

:sem_python
echo.
echo  Nao consegui instalar o Python sozinho.
echo  Instale o Python 3.12 em https://www.python.org/downloads/ marcando "Add python.exe to PATH"
echo  e rode este instalador de novo.
echo.
pause
exit /b 1

:erro
echo.
echo  A instalacao falhou na etapa acima. Tire um print desta janela e mande para quem te passou o programa.
:fim_erro
echo.
pause
exit /b 1

:sem_atalho
echo.
echo  O programa foi instalado, mas o atalho na area de trabalho nao foi criado.
echo  Abra pelo abrir.bat desta pasta.
echo.
pause
exit /b 1
