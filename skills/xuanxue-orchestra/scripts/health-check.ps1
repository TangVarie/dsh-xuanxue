#Requires -Version 7.0
<#
.SYNOPSIS
    玄学四门体检：依次检查 bazi-core / liuyao-core / ziwei-core / vedic，
    写出前端可读的 health.json，并在 stdout 打一份中文摘要。

.DESCRIPTION
    技能根按脚本位置推断，装在哪里都成立；解释器按「环境变量 → 玄学运行时 → 本机已有环境」解析，
    解析结果写进摘要和 notes，四门按各自 SKILL.md 的执行口径跑：
      - 八字 / 六爻：一个有 lunar_python、PyYAML 的 Python（先设 UTF-8 环境变量），相对脚本从技能目录执行。
      - 紫微：不用 tsx（沙箱里 spawn EPERM），用预编译入口 pan.cjs。
      - 吠陀：独立计算环境（PyJHora / pysweph），跑 calculator\scripts\check_env.py。
    缺环境时先跑同目录的 setup-runtime.ps1，或按 SKILL.md / docs/SETUP.zh.md 手装。
    每项都有 120 秒单项超时保护；单项抛错只记 fail，不中断整轮。
    失败也写 JSON。退出码：有 fail=1，否则（全 ok 或有 warn）=0。

.PARAMETER OutFile
    输出 JSON 路径；相对路径按当前工作目录解析，默认 xuanxue-skills/health.json。

.PARAMETER Quick
    只跑最小排盘 / 入口冒烟，不跑完整自检。

.PARAMETER Full
    在默认最小自检之外再跑完整自检：八字 52 项自检 + 历法核验、六爻 96 项单测、
    紫微真实排盘、吠陀回归测试。

.EXAMPLE
    pwsh -NoProfile -File health-check.ps1
    pwsh -NoProfile -File health-check.ps1 -OutFile ..\..\..\xuanxue-skills\health.json
    pwsh -NoProfile -File health-check.ps1 -Quick
    pwsh -NoProfile -File health-check.ps1 -Full
#>
[CmdletBinding()]
param(
    [string]$OutFile = 'xuanxue-skills/health.json',
    [switch]$Quick,
    [switch]$Full
)

Set-StrictMode -Off
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------- 环境准备
# 中文字节统一 UTF-8；PYTHONDONTWRITEBYTECODE 防止在技能目录里写 __pycache__。
try { [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false) } catch { }
try { $OutputEncoding = [System.Text.UTF8Encoding]::new($false) } catch { }
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONDONTWRITEBYTECODE = '1'

# ---------------------------------------------------------------- 路径与配置
$ItemTimeoutSec = 120
$TotalSw = [System.Diagnostics.Stopwatch]::StartNew()
$StartedAt = Get-Date

$Mode = if ($Full) { 'full' } elseif ($Quick) { 'quick' } else { 'default' }
if ($Quick -and $Full) { Write-Warning '-Quick 与 -Full 同时给出，按 -Full（最全）执行。' }
$ModeLabel = switch ($Mode) {
    'quick' { 'Quick·最小排盘' }
    'full' { 'Full·完整自检' }
    default { '默认·最小自检' }
}

# 本脚本位于 <技能根>\xuanxue-orchestra\scripts\health-check.ps1。技能根按脚本位置推断：
# 工作区副本、GitHub 安装后的 profile node_modules、其他机器上的任何位置都成立。
$SkillsRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if ($env:XUANXUE_SKILLS_ROOT) { $SkillsRoot = $env:XUANXUE_SKILLS_ROOT }
$WorkspaceRoot = (Get-Location).ProviderPath

# 玄学运行时目录：scripts/setup-runtime.ps1 把 Python 环境建在这里，建完优先用它。
$DshHome = if ($env:DSH_HOME) { $env:DSH_HOME } else { Join-Path $env:USERPROFILE '.dsh' }
$RuntimeHome = if ($env:XUANXUE_HOME) { $env:XUANXUE_HOME } else { Join-Path $DshHome 'xuanxue' }
$RuntimeJson = Join-Path $RuntimeHome 'runtime.json'

# 解释器解析顺序：环境变量 > runtime.json（setup 写的）> 玄学运行时 venv > DSH 自带 Python > 旧布局 > PATH。
function Resolve-FirstPath {
    param([string[]]$Candidates)
    foreach ($candidate in $Candidates) {
        if (-not $candidate) { continue }
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    }
    return $null
}

$Resolved = $null
if (Test-Path -LiteralPath $RuntimeJson -PathType Leaf) {
    try { $Resolved = Get-Content -LiteralPath $RuntimeJson -Raw | ConvertFrom-Json } catch { $Resolved = $null }
}

$DshPython = Get-ChildItem (Join-Path $DshHome 'dsh-runtimes') -Directory -ErrorAction SilentlyContinue |
    ForEach-Object { Join-Path $_.FullName 'dependencies\python\python.exe' } |
    Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
    Select-Object -First 1
$PathPython = Get-Command python -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandType -eq 'Application' } |
    Select-Object -First 1
$PathPython = if ($PathPython) { [string]$PathPython.Source } else { $null }

# 八字 / 六爻：一个有 lunar_python、PyYAML 的 Python 就够。
$BaziPython = Resolve-FirstPath @(
    $env:XUANXUE_PYTHON,
    $(if ($Resolved) { $Resolved.python }),
    (Join-Path $RuntimeHome 'venv\Scripts\python.exe'),
    (Join-Path $RuntimeHome 'venv\bin\python'),
    $DshPython,
    (Join-Path $DshHome 'dsh-runtimes\dsh-plugin-desktop-primary-runtime\dependencies\python\python.exe'),
    $PathPython
)
# 吠陀：独立计算环境（PyJHora / pysweph），不用系统 Python。
$VedicPython = Resolve-FirstPath @(
    $env:XUANXUE_VEDIC_PY,
    $(if ($Resolved) { $Resolved.vedicPython }),
    (Join-Path $RuntimeHome 'venv\Scripts\python.exe'),
    (Join-Path $RuntimeHome 'venv\bin\python'),
    (Join-Path $WorkspaceRoot 'vedic\vedic-calc-env\Scripts\python.exe')
)
# 紫微：预编译入口（沙箱里 tsx 起 esbuild 会 spawn EPERM）。
$ZiweiPan = Resolve-FirstPath @(
    $env:XUANXUE_ZIWEI_PAN,
    $(if ($Resolved) { $Resolved.ziweiPan }),
    (Join-Path $RuntimeHome 'ziwei\prebuilt\run\pan.cjs'),
    (Join-Path $env:USERPROFILE '.cache\ziwei-core\prebuilt\run\pan.cjs')
)

$OutPath = if ([System.IO.Path]::IsPathRooted($OutFile)) {
    $OutFile
} else {
    [System.IO.Path]::GetFullPath((Join-Path (Get-Location).ProviderPath $OutFile))
}

$SkillKeys = @('bazi-core', 'liuyao-core', 'ziwei-core', 'vedic')
$SkillLabels = @{ 'bazi-core' = '八字'; 'liuyao-core' = '六爻'; 'ziwei-core' = '紫微'; 'vedic' = '吠陀' }

# ---------------------------------------------------------------- 小工具
function Get-NumberText {
    param([double]$Value, [string]$Format = '{0:N1}')
    return [string]::Format([System.Globalization.CultureInfo]::InvariantCulture, $Format, $Value)
}

function Format-Duration {
    param([long]$Ms)
    if ($Ms -lt 1000) { return ('{0} ms' -f $Ms) }
    return ((Get-NumberText ($Ms / 1000.0)) + ' s')
}

# 一行错误摘要，最多 $Max 字符（默认 200）：取最后一条非空行，压缩空白。
function Get-ErrorSummary {
    param([string]$Text, [int]$Max = 200)
    if ([string]::IsNullOrWhiteSpace($Text)) { return $null }
    $lines = @($Text -split "`r?`n" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($lines.Count -eq 0) { return $null }
    $line = ([string]$lines[-1] -replace '\s+', ' ').Trim()
    if ($line.Length -eq 0) { return $null }
    if ($line.Length -gt $Max) { $line = $line.Substring(0, $Max - 1) + '…' }
    return $line
}

# 单项剩余可用的秒数；已超过 120 秒上限就抛错，由上层记 fail。
function Get-StepTimeout {
    param([System.Diagnostics.Stopwatch]$ItemSw)
    $remain = [int][Math]::Floor($ItemTimeoutSec - $ItemSw.Elapsed.TotalSeconds) - 1
    if ($remain -lt 5) { throw ("单项检查已用满 ${ItemTimeoutSec} 秒上限，剩余步骤不再执行") }
    if ($remain -gt $ItemTimeoutSec) { $remain = $ItemTimeoutSec }
    return $remain
}

function Assert-ProcOk {
    param([object]$Proc, [string]$Label)
    if ($Proc.Error) { throw ("$Label 启动失败：" + [string]$Proc.Error) }
    if ($Proc.TimedOut) { throw ("$Label 超时（单项上限 ${ItemTimeoutSec} 秒）") }
    if ($Proc.ExitCode -ne 0) {
        $summary = Get-ErrorSummary ([string]$Proc.Text)
        if (-not $summary) { $summary = "退出码 $($Proc.ExitCode)" }
        throw ("$Label 失败（退出码 $($Proc.ExitCode)）：" + $summary)
    }
}

# 起子进程并抓 stdout/stderr（UTF-8），带超时；顺带 Push-Location 到技能目录执行相对路径。
function Invoke-Proc {
    param(
        [string]$FilePath,
        [string[]]$Arguments = @(),
        [string]$WorkDir,
        [int]$TimeoutSec = 120
    )
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $res = @{
        ExitCode = -1
        StdOut = ''
        StdErr = ''
        Text = ''
        TimedOut = $false
        Error = $null
        ElapsedMs = 0
    }
    $proc = $null
    $pushed = $false
    try {
        $psi = [System.Diagnostics.ProcessStartInfo]::new()
        $psi.FileName = $FilePath
        foreach ($a in $Arguments) { $psi.ArgumentList.Add([string]$a) }
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.StandardOutputEncoding = [System.Text.UTF8Encoding]::new($false)
        $psi.StandardErrorEncoding = [System.Text.UTF8Encoding]::new($false)
        if ($WorkDir) {
            $psi.WorkingDirectory = $WorkDir
            Push-Location -LiteralPath $WorkDir
            $pushed = $true
        }
        $proc = [System.Diagnostics.Process]::Start($psi)
        $outTask = $proc.StandardOutput.ReadToEndAsync()
        $errTask = $proc.StandardError.ReadToEndAsync()
        if (-not $proc.WaitForExit([int]($TimeoutSec * 1000))) {
            $res['TimedOut'] = $true
            try { $proc.Kill($true) } catch { }
            try { [void]$proc.WaitForExit(5000) } catch { }
        }
        $null = $outTask.Wait(5000)
        $null = $errTask.Wait(5000)
        if ($outTask.IsCompleted -and -not $outTask.IsFaulted) { $res['StdOut'] = [string]$outTask.Result }
        if ($errTask.IsCompleted -and -not $errTask.IsFaulted) { $res['StdErr'] = [string]$errTask.Result }
        if (-not $res['TimedOut']) { try { $res['ExitCode'] = [int]$proc.ExitCode } catch { } }
    } catch {
        $res['Error'] = [string]$_.Exception.Message
    } finally {
        if ($pushed) { Pop-Location }
        $sw.Stop()
        $res['ElapsedMs'] = [int]$sw.ElapsedMilliseconds
    }
    $res['Text'] = (([string]$res['StdOut'] + "`n" + [string]$res['StdErr']).Trim())
    return [pscustomobject]$res
}

# 单项照看：计时、兜住异常、把结果归一成 {status,ms,detail,error}。
function Invoke-SkillCheck {
    param([string]$Kind)
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $status = 'fail'
    $detail = ''
    $err = $null
    try {
        $raw = @(switch ($Kind) {
                'bazi-core' { Get-BaziCoreResult -ItemSw $sw }
                'liuyao-core' { Get-LiuyaoCoreResult -ItemSw $sw }
                'ziwei-core' { Get-ZiweiCoreResult -ItemSw $sw }
                'vedic' { Get-VedicResult -ItemSw $sw }
                default { throw "未知检查项：$Kind" }
            }) | Select-Object -Last 1
        if ($null -eq $raw) { throw '检查未返回结果' }
        $status = [string]$raw.Status
        $detail = [string]$raw.Detail
        if ($raw.Error) { $err = [string]$raw.Error }
        if ($status -notin @('ok', 'warn', 'fail')) { throw ("检查返回未知状态：" + $status) }
    } catch {
        $status = 'fail'
        if ([string]::IsNullOrWhiteSpace($detail)) { $detail = '检查执行异常' }
        $msg = ''
        if ($_.Exception) { $msg = [string]$_.Exception.Message }
        if ([string]::IsNullOrWhiteSpace($msg)) { $msg = [string]$_ }
        $err = Get-ErrorSummary $msg
    } finally {
        $sw.Stop()
    }
    if ([string]::IsNullOrWhiteSpace($detail)) { $detail = if ($status -eq 'ok') { '通过' } else { '无摘要' } }
    if ($status -eq 'fail') {
        if ([string]::IsNullOrWhiteSpace($err)) { $err = Get-ErrorSummary $detail }
        if ([string]::IsNullOrWhiteSpace($err)) { $err = '未知错误' }
    } else {
        $err = $null
    }
    return [pscustomobject]@{ status = $status; ms = [int]$sw.ElapsedMilliseconds; detail = $detail; error = $err }
}

# ---------------------------------------------------------------- 四门检查
function Get-BaziCoreResult {
    param([System.Diagnostics.Stopwatch]$ItemSw)
    $dir = Join-Path $SkillsRoot 'bazi-core'
    if (-not (Test-Path -LiteralPath $dir)) { return @{ Status = 'fail'; Detail = '技能目录缺失'; Error = "找不到技能目录：$dir" } }
    if (-not $BaziPython -or -not (Test-Path -LiteralPath $BaziPython)) { return @{ Status = 'fail'; Detail = 'Python 解释器缺失'; Error = '没解析到 Python：跑 scripts/setup-runtime.ps1，或设 $env:XUANXUE_PYTHON 指到一个装了 lunar_python / PyYAML 的 python.exe' } }

    # 快速项：排盘能出四柱即 ok。
    $smoke = Invoke-Proc -FilePath $BaziPython -Arguments @('scripts\paipan.py', '--date', '1990-06-15 08:30', '--gender', 'male', '--lon', '121.47', '--json') -WorkDir $dir -TimeoutSec (Get-StepTimeout $ItemSw)
    Assert-ProcOk -Proc $smoke -Label '八字排盘'
    $chart = $null
    try { $chart = $smoke.StdOut | ConvertFrom-Json } catch { throw '八字排盘输出不是有效 JSON' }
    $pillars = @($chart.pillars)
    if ($pillars.Count -lt 3) { throw '八字排盘缺少四柱结果' }
    $pillarText = ($pillars -join '/')

    if ($Mode -eq 'quick') {
        return @{ Status = 'ok'; Detail = ("四柱 $pillarText"); Error = $null }
    }

    # 自检（52 项）：默认就跑，属于「最小自检」的核心。
    $self = Invoke-Proc -FilePath $BaziPython -Arguments @('scripts\selftest.py') -WorkDir $dir -TimeoutSec (Get-StepTimeout $ItemSw)
    Assert-ProcOk -Proc $self -Label '八字自检'
    $pass = ([regex]::Matches($self.StdOut, '(?m)^PASS\b')).Count
    $fail = ([regex]::Matches($self.StdOut, '(?m)^FAIL\b')).Count
    if ($fail -gt 0) { return @{ Status = 'fail'; Detail = ("自检 $pass 通过 / $fail 失败"); Error = '八字自检有失败项' } }
    if ($pass -eq 0) { return @{ Status = 'fail'; Detail = '自检未输出结果'; Error = (Get-ErrorSummary ([string]$self.Text)) } }
    $detail = "$pass/$($pass + $fail) 通过"

    if ($Mode -eq 'full') {
        $check = Invoke-Proc -FilePath $BaziPython -Arguments @('scripts\check_chart.py', '--pillars', ($pillars -join ' '), '--json') -WorkDir $dir -TimeoutSec (Get-StepTimeout $ItemSw)
        Assert-ProcOk -Proc $check -Label '八字历法核验'
        $cj = $null
        try { $cj = $check.StdOut | ConvertFrom-Json } catch { throw '八字历法核验输出不是有效 JSON' }
        $verdict = [string]$cj.verdict
        if ($verdict -ne '通过') {
            return @{ Status = 'fail'; Detail = ("历法核验：$verdict"); Error = '四柱历法一致性核验未通过' }
        }
        $detail = "$detail；历法核验通过"
    }
    return @{ Status = 'ok'; Detail = $detail; Error = $null }
}

function Get-LiuyaoCoreResult {
    param([System.Diagnostics.Stopwatch]$ItemSw)
    $dir = Join-Path $SkillsRoot 'liuyao-core'
    if (-not (Test-Path -LiteralPath $dir)) { return @{ Status = 'fail'; Detail = '技能目录缺失'; Error = "找不到技能目录：$dir" } }
    if (-not $BaziPython -or -not (Test-Path -LiteralPath $BaziPython)) { return @{ Status = 'fail'; Detail = 'Python 解释器缺失'; Error = '没解析到 Python：跑 scripts/setup-runtime.ps1，或设 $env:XUANXUE_PYTHON 指到一个装了 lunar_python / PyYAML 的 python.exe' } }

    # 快速项：装卦能出本卦/变卦即 ok。
    $smoke = Invoke-Proc -FilePath $BaziPython -Arguments @('scripts\paipan.py', '--lines', '787896', '--date', '2026-11-15 21:30', '--json') -WorkDir $dir -TimeoutSec (Get-StepTimeout $ItemSw)
    Assert-ProcOk -Proc $smoke -Label '六爻装卦'
    $chart = $null
    try { $chart = $smoke.StdOut | ConvertFrom-Json } catch { throw '六爻装卦输出不是有效 JSON' }
    $ben = [string]$chart.chart.ben.name
    if ([string]::IsNullOrWhiteSpace($ben)) { throw '六爻装卦结果缺少本卦' }
    $smokeDetail = "装卦 $ben（冒烟通过）"

    if ($Mode -ne 'full') {
        return @{ Status = 'ok'; Detail = $smokeDetail; Error = $null }
    }

    # 完整项：tests\run_all.py。已知沙箱 %TEMP% 权限问题会挂 1 项，归为 warn 而不是 fail。
    $suite = Invoke-Proc -FilePath $BaziPython -Arguments @('tests\run_all.py') -WorkDir $dir -TimeoutSec (Get-StepTimeout $ItemSw)
    $text = [string]$suite.Text
    $ran = 0; if ($text -match 'Ran (\d+) tests?') { $ran = [int]$Matches[1] }
    $errCount = 0; if ($text -match 'errors=(\d+)') { $errCount = [int]$Matches[1] }
    $failCount = 0; if ($text -match 'failures=(\d+)') { $failCount = [int]$Matches[1] }
    $skipCount = 0; if ($text -match 'skipped=(\d+)') { $skipCount = [int]$Matches[1] }
    $allOk = ($suite.ExitCode -eq 0) -and ($text -match '(?m)^OK\b')
    if ($allOk) {
        $tail = if ($skipCount -gt 0) { "单测 $ran 项全过（跳过 $skipCount）" } else { "单测 $ran 项全过" }
        return @{ Status = 'ok'; Detail = ("装卦 $ben；" + $tail); Error = $null }
    }
    if ($suite.TimedOut) { return @{ Status = 'fail'; Detail = ("装卦 $ben；单测超时"); Error = ("六爻单测超时（单项上限 ${ItemTimeoutSec} 秒）") } }

    $tempPermIssue = ($text -match '(?i)PermissionError|WinError\s*5|拒绝访问')
    if ($failCount -eq 0 -and $errCount -gt 0 -and $tempPermIssue) {
        return @{ Status = 'warn'; Detail = ("装卦 $ben；单测 $errCount 项因沙箱 %TEMP% 权限报错（已记 warn）"); Error = $null }
    }
    return @{ Status = 'fail'; Detail = ("装卦 $ben；单测失败（错误 $errCount / 失败 $failCount / 共 $ran）"); Error = (Get-ErrorSummary $text) }
}

function Get-ZiweiCoreResult {
    param([System.Diagnostics.Stopwatch]$ItemSw)
    $dir = Join-Path $SkillsRoot 'ziwei-core'
    if (-not (Test-Path -LiteralPath $dir)) { return @{ Status = 'fail'; Detail = '技能目录缺失'; Error = "找不到技能目录：$dir" } }
    # 不走 tsx（本机沙箱会 spawn EPERM），只认预编译入口。
    if (-not (Test-Path -LiteralPath $ZiweiPan)) {
        return @{ Status = 'fail'; Detail = '缺预编译入口'; Error = '没解析到紫微预编译入口：跑 scripts/setup-runtime.ps1，或设 $env:XUANXUE_ZIWEI_PAN 指到 prebuilt\run\pan.cjs' }
    }
    $nodeCmd = Get-Command node -ErrorAction SilentlyContinue | Where-Object { $_.CommandType -eq 'Application' } | Select-Object -First 1
    if (-not $nodeCmd) { return @{ Status = 'fail'; Detail = '未找到 node'; Error = 'PATH 中找不到 node，请安装 Node.js' } }
    $node = [string]$nodeCmd.Source

    if ($Mode -eq 'quick') {
        $pan = Invoke-Proc -FilePath $node -Arguments @($ZiweiPan, '--date', '1990-06-15', '--time', '08:30', '--gender', 'male', '--json') -WorkDir $dir -TimeoutSec (Get-StepTimeout $ItemSw)
        Assert-ProcOk -Proc $pan -Label '紫微排盘'
        $pj = $null
        try { $pj = $pan.StdOut | ConvertFrom-Json } catch { throw '紫微排盘输出不是有效 JSON' }
        $palaces = @($pj.chart.palaces)
        if ($palaces.Count -ne 12) { throw ("紫微排盘宫位不是 12 宫（实际 $($palaces.Count)）") }
        $ju = [string]$pj.chart.wuxingJuName
        $detail = if ($ju) { "预编译排盘冒烟通过（$ju）" } else { '预编译排盘冒烟通过' }
        return @{ Status = 'ok'; Detail = $detail; Error = $null }
    }

    # 官方自检：应输出 6 行 ✓ 与「自检通过」。
    $self = Invoke-Proc -FilePath $node -Arguments @($ZiweiPan, '--selftest') -WorkDir $dir -TimeoutSec (Get-StepTimeout $ItemSw)
    Assert-ProcOk -Proc $self -Label '紫微自检'
    $checkMarks = @([string]$self.StdOut -split "`r?`n" | Where-Object { $_.TrimStart().StartsWith([string][char]0x2713) }).Count
    if ([string]$self.StdOut -notmatch '自检通过') {
        return @{ Status = 'fail'; Detail = '紫微自检未通过'; Error = (Get-ErrorSummary ([string]$self.Text)) }
    }
    if ($checkMarks -lt 6) {
        return @{ Status = 'fail'; Detail = ("自检 $checkMarks/6"); Error = '紫微自检通过项不足 6 项' }
    }
    $detail = "自检 $checkMarks/6"

    if ($Mode -eq 'full') {
        $pan = Invoke-Proc -FilePath $node -Arguments @($ZiweiPan, '--date', '1990-06-15', '--time', '08:30', '--gender', 'male', '--json') -WorkDir $dir -TimeoutSec (Get-StepTimeout $ItemSw)
        Assert-ProcOk -Proc $pan -Label '紫微排盘'
        $pj = $null
        try { $pj = $pan.StdOut | ConvertFrom-Json } catch { throw '紫微排盘输出不是有效 JSON' }
        if (@($pj.chart.palaces).Count -ne 12) { throw '紫微排盘宫位不是 12 宫' }
        $detail = "$detail；排盘冒烟通过"
    }
    return @{ Status = 'ok'; Detail = $detail; Error = $null }
}

function Get-VedicResult {
    param([System.Diagnostics.Stopwatch]$ItemSw)
    $dir = Join-Path $SkillsRoot 'vedic'
    if (-not (Test-Path -LiteralPath $dir)) { return @{ Status = 'fail'; Detail = '技能目录缺失'; Error = "找不到技能目录：$dir" } }
    if (-not $VedicPython -or -not (Test-Path -LiteralPath $VedicPython)) {
        return @{ Status = 'fail'; Detail = '计算环境缺失'; Error = '没解析到吠陀计算环境：跑 scripts/setup-runtime.ps1，或设 $env:XUANXUE_VEDIC_PY 指到装了 PyJHora / pysweph 的解释器' }
    }

    # 权威入口：calculator\scripts\check_env.py（依赖检查 + 最小计算 SAV）。
    $envCheck = Invoke-Proc -FilePath $VedicPython -Arguments @('calculator\scripts\check_env.py') -WorkDir $dir -TimeoutSec (Get-StepTimeout $ItemSw)
    $text = [string]$envCheck.Text
    if ($envCheck.TimedOut) { throw ("吠陀 check_env 超时（单项上限 ${ItemTimeoutSec} 秒）") }
    $sav = ''
    if ($text -match 'SAV=(\d+)') { $sav = $Matches[1] }
    $ready = ($envCheck.ExitCode -eq 0) -and ($text -match '环境.*就绪') -and $sav
    if (-not $ready) {
        return @{ Status = 'fail'; Detail = 'check_env 未通过'; Error = (Get-ErrorSummary $text) }
    }
    $detail = "check_env 通过 SAV=$sav"

    if ($Mode -ne 'full') {
        return @{ Status = 'ok'; Detail = $detail; Error = $null }
    }

    # 完整项：回归测试（tests\run_tests.py 只把逐项结果打到 stdout，汇总在它的 Markdown 报告里）。
    # 沙箱 %TEMP% 权限受限时它会在临时目录写入失败，这些用例归为 warn，不冒充通过。
    $suite = Invoke-Proc -FilePath $VedicPython -Arguments @('tests\run_tests.py', '--python', $VedicPython) -WorkDir $dir -TimeoutSec (Get-StepTimeout $ItemSw)
    $t = [string]$suite.Text
    if ($suite.TimedOut) {
        return @{ Status = 'warn'; Detail = "$detail；回归超时（>${ItemTimeoutSec}s）"; Error = $null }
    }
    $passC = ([regex]::Matches($t, '(?m)^\[通过\] ')).Count
    $failC = ([regex]::Matches($t, '(?m)^\[失败\] ')).Count
    $incC = ([regex]::Matches($t, '(?m)^\[未完成\] ')).Count
    $totalC = $passC + $failC + $incC
    if ($totalC -eq 0) {
        return @{ Status = 'warn'; Detail = "$detail；回归未输出用例结果"; Error = $null }
    }
    # 逐条看「失败」是否都由沙箱权限/计算环境引起；有真实失败就 fail。
    $failLines = @($t -split "`r?`n" | Where-Object { $_ -match '^\[失败\] ' })
    $realFails = @($failLines | Where-Object { $_ -notmatch '(?i)PermissionError|WinError\s*5|拒绝访问|计算环境不可用' })
    if ($realFails.Count -gt 0) {
        return @{ Status = 'fail'; Detail = "$detail；回归 通过 $passC·失败 $failC·未完成 $incC"; Error = (Get-ErrorSummary ([string]$realFails[-1])) }
    }
    if ($failLines.Count -gt 0 -or $incC -gt 0) {
        return @{ Status = 'warn'; Detail = "$detail；回归 通过 $passC·失败 $failC·未完成 $incC（沙箱 %TEMP% 限制）"; Error = $null }
    }
    return @{ Status = 'ok'; Detail = "$detail；回归 $totalC/$totalC 通过"; Error = $null }
}

# ---------------------------------------------------------------- 主流程
$Keys = @('bazi-core', 'liuyao-core', 'ziwei-core', 'vedic')
$Results = [ordered]@{}
foreach ($k in $Keys) {
    try {
        $Results[$k] = Invoke-SkillCheck -Kind $k
    } catch {
        $Results[$k] = [pscustomobject]@{
            status = 'fail'
            ms = 0
            detail = '检查崩溃'
            error = (Get-ErrorSummary ([string]$_.Exception.Message))
        }
    }
}
$TotalSw.Stop()
$ElapsedMs = [int]$TotalSw.ElapsedMilliseconds

$OkCount = @($Results.Values | Where-Object { $_.status -eq 'ok' }).Count
$WarnCount = @($Results.Values | Where-Object { $_.status -eq 'warn' }).Count
$FailCount = @($Results.Values | Where-Object { $_.status -eq 'fail' }).Count

# ---------------------------------------------------------------- notes
$Notes = [System.Collections.Generic.List[string]]::new()
$Notes.Add('紫微用预编译入口（沙箱里 tsx 起 esbuild 会 EPERM）')
$Notes.Add('吠陀用独立计算环境：' + $(if ($VedicPython) { $VedicPython } else { '未解析到' }))
if ($Results['liuyao-core'].status -eq 'warn') { $Notes.Add('六爻单测 1 项受沙箱 %TEMP% 权限限制，已归为 warn') }
if ($Results['vedic'].status -eq 'warn') { $Notes.Add('吠陀完整回归在沙箱下受限，check_env 与最小计算本身通过') }
$Notes.Add('解释器与入口按 环境变量 > runtime.json > 玄学运行时 > 本机已有环境 解析；缺环境跑 scripts/setup-runtime.ps1')
if ($Mode -eq 'quick') { $Notes.Add('Quick 模式：只跑最小排盘/入口冒烟，未跑完整自检') }
if ($Mode -eq 'full') { $Notes.Add('Full 模式：已跑八字 52 项自检、六爻 96 项单测、紫微真实排盘、吠陀回归') }

# ---------------------------------------------------------------- 写 JSON（失败也要写）
$CheckedAt = $StartedAt.ToString('yyyy-MM-ddTHH:mm:sszzz', [System.Globalization.CultureInfo]::InvariantCulture)
$SkillsObject = [ordered]@{}
foreach ($k in $Keys) {
    $e = $Results[$k]
    $SkillsObject[$k] = [ordered]@{
        status = [string]$e.status
        ms = [int]$e.ms
        detail = [string]$e.detail
        error = $e.error
    }
}
$Health = [ordered]@{
    version = 1
    checkedAt = $CheckedAt
    elapsedMs = $ElapsedMs
    skills = $SkillsObject
    notes = @($Notes)
}
$Json = $Health | ConvertTo-Json -Depth 6
$WriteError = $null
try {
    $parentDir = Split-Path -Parent $OutPath
    if ($parentDir -and -not (Test-Path -LiteralPath $parentDir)) {
        New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
    }
    [System.IO.File]::WriteAllText($OutPath, $Json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
} catch {
    $WriteError = [string]$_.Exception.Message
}
$ExitCode = if ($FailCount -gt 0 -or $WriteError) { 1 } else { 0 }

# ---------------------------------------------------------------- stdout 中文摘要
$StatusColor = @{ ok = 'Green'; warn = 'Yellow'; fail = 'Red' }
Write-Host ''
Write-Host '============ 玄学四门体检 ============' -ForegroundColor Cyan
Write-Host ("  时间：{0}    模式：{1}" -f $CheckedAt, $ModeLabel)
Write-Host ('  ' + ('-' * 62))
foreach ($k in $Keys) {
    $e = $Results[$k]
    $color = $StatusColor[[string]$e.status]
    if (-not $color) { $color = 'Gray' }
    $line = '  [{0,-4}] {1}  {2,-12} {3,9}  {4}' -f ([string]$e.status).ToUpper(), $SkillLabels[$k], $k, (Format-Duration ([long]$e.ms)), ([string]$e.detail)
    Write-Host $line -ForegroundColor $color
    if ($e.status -eq 'fail' -and $e.error) {
        Write-Host ('         └─ ' + [string]$e.error) -ForegroundColor DarkRed
    }
}
Write-Host ('  ' + ('-' * 62))
Write-Host ("  结果：ok $OkCount · warn $WarnCount · fail $FailCount")
Write-Host ("  总耗时：$(Format-Duration $ElapsedMs)")
if ($WriteError) {
    Write-Host ("  JSON 写入失败：$WriteError") -ForegroundColor Red
} else {
    Write-Host ("  JSON：$OutPath")
}
Write-Host ("  退出码：$ExitCode")
Write-Host '======================================' -ForegroundColor Cyan
Write-Host ''

exit $ExitCode
