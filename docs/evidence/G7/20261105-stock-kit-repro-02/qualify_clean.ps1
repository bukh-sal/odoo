param(
    [Parameter(Mandatory)][string] $Kit,
    [Parameter(Mandatory)][string] $Work,
    [Parameter(Mandatory)][int] $Port,
    [Parameter(Mandatory)][string] $RuntimeSubnet,
    [Parameter(Mandatory)][string] $EdgeSubnet
)

$ErrorActionPreference = 'Stop'
$Kit = (Resolve-Path -LiteralPath $Kit).Path
$Work = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Work)
$OwnerRoot = (Resolve-Path -LiteralPath '.local/stock-webclient-release').Path
if ((Split-Path -Parent $Work) -ne $OwnerRoot -or (Test-Path -LiteralPath $Work)) {
    throw 'Use a fresh workdir under the owned stock qualification root.'
}
function Invoke-Step([string] $Interpreter, [string[]] $Arguments) {
    & $Interpreter @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Qualification step exited $LASTEXITCODE. Inspect the protected journal before resuming."
    }
}

$Builder = (Resolve-Path -LiteralPath '.local/toolchain/operator-python16/Scripts/python.exe').Path
Invoke-Step $Builder @('-I', "$Kit/scripts/setup_operator.py", $Kit, '--workdir', $Work)
$Operator = "$Work/operator/Scripts/python.exe"
$Source = "$Work/source"
$Inputs = @('--kit', $Kit, '--workdir', $Work)
$Index = Get-Content -LiteralPath "$Kit/plugins/index.json" -Raw | ConvertFrom-Json
foreach ($Artifact in $Index.packages) {
    Invoke-Step $Operator @('-I', "$Source/tools/modular.py", '--config', "$Kit/plugins/curated-trust.json",
        'catalog', '--store', "$Work/private/catalog", 'add', "$Kit/$($Artifact.file)", '--digest', $Artifact.digest) | Out-Null
}
$Init = "$Source/release/initialize_reference.py"
Invoke-Step $Operator (@('-I', $Init, 'prepare', '--reference-fixture', '--port', [string] $Port,
    '--subnets', $RuntimeSubnet, $EdgeSubnet) + $Inputs)
foreach ($Action in @('initialize', 'install')) {
    Invoke-Step $Operator (@('-I', $Init, $Action) + $Inputs)
}
Invoke-Step $Operator (@('-I', "$Source/release/check_reference.py") + $Inputs)
Invoke-Step $Operator (@('-I', "$Source/release/initialize_worker.py") + $Inputs)
foreach ($Action in @('register', 'connect', 'job')) {
    Invoke-Step $Operator (@('-I', "$Source/release/connect_worker.py", $Action) + $Inputs)
}
