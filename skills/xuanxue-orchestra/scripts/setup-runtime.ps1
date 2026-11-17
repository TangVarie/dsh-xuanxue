#Requires -Version 7.0
<#
.SYNOPSIS
    玄学运行时一次装好：一个带八字 / 六爻 / 吠陀依赖的 Python 环境，
    以及紫微预编译排盘入口的检查与生成。

.DESCRIPTION
    四门脚本依赖三种本机环境：Python（八字 lunar_python、六爻 PyYAML、吠陀 PyJHora + pysweph）、
    Node.js（紫微），以及对吠陀星历文件。这个脚本把这些装到**插件之外**的一个固定位置，
    免得写进 node_modules（更新会被覆盖），也免得依赖某个工作区目录：

      %DSH_HOME%\xuanxue\venv         Python 环境（DSH_HOME 默认 %USERPROFILE%\.dsh）
      %DSH_HOME%\xuanxue\ziwei        紫微运行时（可选，知道源码位置才建）
      %DSH_HOME%\xuanxue\runtime.json 解析结果，health-check.ps1 会优先读它

    已存在的环境不重建；要重建加 -Force。紫微需要先有 ziwei-doushu 源码与 node_modules，
    脚本不会替你下载，只做检查和打包。

.PARAMETER DryRun
    只打印打算执行的命令和解析到的路径，不动磁盘。

.PARAMETER Force
    即使 venv 已存在也重建。

.PARAMETER ZiweiHome
    紫微 ziwei-doushu 源码目录；默认取 XUANXUE_ZIWEI_HOME，其次 %USERPROFILE%\.cache\ziwei-core。

.EXAMPLE
    pwsh -NoProfile -File setup-runtime.ps1 -DryRun
    pwsh -NoProfile -File setup-runtime.ps1
    pwsh -NoProfile -File setup-runtime.ps1 -Force
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Force,
    [string]$ZiweiHome
)

Set-StrictMode -Off
$ErrorActionPreference = 'Stop'

$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PIP_NO_CACHE_DIR = '1'

# 与 health-check.ps1 相同的版本口径：pysweph 只支持 3.8–3.13。
$PythonPins = @(
    'PyJHora==4.8.6',
    'pysweph==2.10.3.6',
    'numpy==2.3.5',
    'timezonefinder==6.0.1',
    'pytz',
    'PyYAML',
    'lunar_python==1.4.4'
)

if ($env:OS -ne 'Windows_NT') {
    throw '这个脚本按 Windows 布局写（Scripts\python.exe）；其他系统请照 docs/SETUP.zh.md 手动装，并把路径写进 $env:XUANXUE_VEDIC_PY / $env:XUANXUE_PYTHON。'
}

# ---------------------------------------------------------------- 路径
$SkillsRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$DshHome = if ($env:DSH_HOME) { $env:DSH_HOME } else { Join-Path $env:USERPROFILE '.dsh' }
$RuntimeHome = if ($env:XUANXUE_HOME) { $env:XUANXUE_HOME } else { Join-Path $DshHome 'xuanxue' }
$Venv = Join-Path $RuntimeHome 'venv'
$VenvPython = Join-Path $Venv 'Scripts\python.exe'
$RuntimeJson = Join-Path $RuntimeHome 'runtime.json'
if (-not $ZiweiHome) {
    $ZiweiHome = if ($env:XUANXUE_ZIWEI_HOME) { $env:XUANXUE_ZIWEI_HOME } else { Join-Path $env:USERPROFILE '.cache\ziwei-core' }
}
$ZiweiPan = Join-Path $ZiweiHome 'prebuilt\run\pan.cjs'

function Write-Step { param([string]$Text) Write-Host "• $Text" -ForegroundColor Cyan }
function Write-Plan { param([string]$Text) Write-Host "  $Text" -ForegroundColor DarkGray }

function Resolve-BasePython {
    $candidates = @($env:XUANXUE_PYTHON)
    $candidates += Get-ChildItem (Join-Path $DshHome 'dsh-runtimes') -Directory -ErrorAction SilentlyContinue |
        ForEach-Object { Join-Path $_.FullName 'dependencies\python\python.exe' } |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf }
    $onPath = Get-Command python -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandType -eq 'Application' } |
        Select-Object -First 1
    if ($onPath) { $candidates += [string]$onPath.Source }
    foreach ($candidate in $candidates) {
        if (-not $candidate) { continue }
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        $version = & $candidate -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $version) { continue }
        $major, $minor = $version.Split('.')
        if ([int]$major -ne 3 -or [int]$minor -lt 10) {
            Write-Plan "跳过 $candidate（Python $version，需要 3.10+）"
            continue
        }
        if ([int]$minor -gt 13) {
            Write-Plan "跳过 $candidate（Python $version，pysweph 只支持到 3.13）"
            continue
        }
        return $candidate
    }
    return $null
}

$BasePython = Resolve-BasePython
if (-not $BasePython) {
    throw '没找到可用的基础 Python（3.10–3.13）。装一个 Python 3.12，或设 $env:XUANXUE_PYTHON 指向它的 python.exe，再跑这个脚本。'
}

# ---------------------------------------------------------------- 计划
Write-Host ''
Write-Host '玄学运行时安装计划' -ForegroundColor Cyan
Write-Plan "技能目录：$SkillsRoot"
Write-Plan "运行时目录：$RuntimeHome"
Write-Plan "基础 Python：$BasePython"
Write-Plan "venv：$Venv$(if (Test-Path -LiteralPath $VenvPython) { '（已存在，跳过创建）' } else { '（将创建）' })"
Write-Plan "Python 包：$($PythonPins -join ' ')"
Write-Plan "紫微源码：$ZiweiHome$(if (Test-Path -LiteralPath (Join-Path $ZiweiHome 'run\pan.ts')) { '（在）' } else { '（不在，这一步会跳过）' })"
Write-Host ''

if ($DryRun) {
    Write-Host 'DryRun：没有改动任何文件。去掉 -DryRun 就按上面的计划执行。' -ForegroundColor Yellow
    exit 0
}

# ---------------------------------------------------------------- venv
New-Item -ItemType Directory -Force -Path $RuntimeHome | Out-Null

if ($Force -and (Test-Path -LiteralPath $Venv)) {
    Write-Step "重建 venv（-Force）：删除 $Venv"
    Remove-Item -LiteralPath $Venv -Recurse -Force
}

if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Step "创建 venv：$Venv"
    & $BasePython -m venv $Venv
    if ($LASTEXITCODE -ne 0) { throw "创建 venv 失败，退出码 $LASTEXITCODE" }
} else {
    Write-Step "venv 已存在，沿用：$Venv"
}

Write-Step '安装 Python 依赖（首次几分钟；PyJHora 体积大）'
& $VenvPython -m pip install --disable-pip-version-check @PythonPins
if ($LASTEXITCODE -ne 0) { throw "pip install 失败，退出码 $LASTEXITCODE；把上面的报错发我，别硬跑排盘。" }

Write-Step '验证依赖能 import'
$probe = @'
import sys
mods = []
for name, imp in [('swisseph', 'swisseph'), ('PyJHora', 'jhora.panchanga.drik'), ('numpy', 'numpy'),
                  ('timezonefinder', 'timezonefinder'), ('pytz', 'pytz'), ('yaml', 'yaml'),
                  ('lunar_python', 'lunar_python')]:
    try:
        __import__(imp)
        mods.append(name + ':ok')
    except Exception as exc:
        mods.append(name + ':FAIL(' + str(exc)[:60] + ')')
print(' '.join(mods))
print('PYTHON=' + sys.executable)
sys.exit(0 if all(m.endswith(':ok') for m in mods) else 3)
'@
$probeFile = Join-Path $RuntimeHome 'probe.py'
Set-Content -LiteralPath $probeFile -Value $probe -Encoding utf8
& $VenvPython $probeFile
$probeCode = $LASTEXITCODE
Remove-Item -LiteralPath $probeFile -Force -ErrorAction SilentlyContinue
if ($probeCode -ne 0) { throw '依赖没装全，看上面哪一项 FAIL；修好再跑一次。' }

# ---------------------------------------------------------------- 紫微
$ziweiStatus = 'skipped'
if (Test-Path -LiteralPath (Join-Path $ZiweiHome 'run\pan.ts')) {
    if (Test-Path -LiteralPath $ZiweiPan) {
        Write-Step "紫微预编译入口已存在：$ZiweiPan"
        $ziweiStatus = 'ready'
    } else {
        Write-Step '生成紫微预编译入口（build-ziwei-prebuilt.ps1）'
        & (Join-Path $PSScriptRoot 'build-ziwei-prebuilt.ps1') -ZiweiHome $ZiweiHome
        if ($LASTEXITCODE -ne 0) { throw "紫微预编译失败，退出码 $LASTEXITCODE" }
        $ziweiStatus = 'ready'
    }
} else {
    Write-Host '  紫微跳过：没找到 ziwei-doushu 源码（run\pan.ts）。照 docs/SETUP.zh.md 第 3 节准备后重跑。' -ForegroundColor Yellow
}

# ---------------------------------------------------------------- 记录
$record = [ordered]@{
    version = 1
    installedAt = (Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz', [System.Globalization.CultureInfo]::InvariantCulture)
    python = $VenvPython
    vedicPython = $VenvPython
    ziweiPan = if ($ziweiStatus -eq 'ready') { $ZiweiPan } else { $null }
    packages = @($PythonPins)
    basePython = $BasePython
}
[System.IO.File]::WriteAllText($RuntimeJson, (($record | ConvertTo-Json -Depth 5) + [Environment]::NewLine), [System.Text.UTF8Encoding]::new($false))
Write-Step "写入解析结果：$RuntimeJson"

Write-Host ''
Write-Host '完成。下一步跑体检确认四门状态：' -ForegroundColor Green
Write-Plan "pwsh -NoProfile -File `"$(Join-Path $PSScriptRoot 'health-check.ps1')`""
Write-Host ''
exit 0
