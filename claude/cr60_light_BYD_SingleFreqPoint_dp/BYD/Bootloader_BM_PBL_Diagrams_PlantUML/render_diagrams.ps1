[CmdletBinding()]
param(
    [ValidateSet("all", "svg", "png")]
    [string]$Format = "all"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourceDir = Join-Path $root "src"
$sources = Get-ChildItem -LiteralPath $sourceDir -File -Filter "*.puml" | Sort-Object Name
if (-not $sources) {
    throw "No PlantUML source files were found in $sourceDir"
}

$plantUmlCommand = Get-Command plantuml -ErrorAction SilentlyContinue
$javaCommand = Get-Command java -ErrorAction SilentlyContinue
$plantUmlJar = $env:PLANTUML_JAR

if (-not $plantUmlCommand -and -not $plantUmlJar) {
    $extensionRoot = Join-Path $env:USERPROFILE ".vscode\extensions"
    if (Test-Path -LiteralPath $extensionRoot) {
        $plantUmlJar = Get-ChildItem -LiteralPath $extensionRoot -Directory -Filter "jebbs.plantuml-*" |
            Sort-Object Name -Descending |
            ForEach-Object { Join-Path $_.FullName "plantuml.jar" } |
            Where-Object { Test-Path -LiteralPath $_ } |
            Select-Object -First 1
    }
}

if (-not $plantUmlCommand) {
    if (-not $javaCommand) {
        throw "Java was not found. Install Java or add it to PATH."
    }
    if (-not $plantUmlJar -or -not (Test-Path -LiteralPath $plantUmlJar)) {
        throw "plantuml.jar was not found. Set PLANTUML_JAR to its full path."
    }
}

function Invoke-PlantUmlRender {
    param(
        [Parameter(Mandatory)]
        [ValidateSet("svg", "png")]
        [string]$OutputFormat
    )

    $outputDir = Join-Path $root $OutputFormat
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
    $sourcePaths = @($sources | ForEach-Object { $_.FullName })
    $plantUmlArgs = @("-charset", "UTF-8", "-t$OutputFormat", "-o", $outputDir) + $sourcePaths

    if ($plantUmlCommand) {
        & $plantUmlCommand.Source @plantUmlArgs
    }
    else {
        & $javaCommand.Source "-Dfile.encoding=UTF-8" -jar $plantUmlJar @plantUmlArgs
    }
    if ($LASTEXITCODE -ne 0) {
        throw "PlantUML $OutputFormat rendering failed with exit code $LASTEXITCODE"
    }
}

if ($Format -in @("all", "svg")) {
    Invoke-PlantUmlRender -OutputFormat "svg"
}
if ($Format -in @("all", "png")) {
    Invoke-PlantUmlRender -OutputFormat "png"
}

Write-Host "Rendered $($sources.Count) diagrams to $root"
