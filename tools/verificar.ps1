param(
    [ValidateSet('rapido','completo','windows','compilado')]
    [string]$Perfil = 'rapido',
    [string]$Python = 'python',
    [string]$Executavel = '',
    [string]$Saida = ''
)
$ErrorActionPreference = 'Stop'
$raizProjeto = Split-Path $PSScriptRoot -Parent
Push-Location (Join-Path $raizProjeto 'hunt-analyzer')
try {
    $env:PYTHONIOENCODING = 'utf-8'
    $argumentos = @('../tools/verificar.py', '--perfil', $Perfil)
    if ($Executavel) { $argumentos += @('--executavel', $Executavel) }
    if ($Saida) { $argumentos += @('--saida', $Saida) }
    & $Python @argumentos
    exit $LASTEXITCODE
} finally { Pop-Location }
