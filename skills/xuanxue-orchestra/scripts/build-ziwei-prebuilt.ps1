# 重新生成「紫微斗数」预编译排盘入口。
#
# 背景：ziwei-core 的官方入口 `node node_modules/tsx/dist/cli.mjs run/pan.ts` 需要 tsx
# 启动 esbuild 子进程，而 DSH 的沙箱禁止子进程管道，会报 `spawn EPERM`。这里把
# run/pan.ts 及其依赖打成单文件 CJS（运行时不再需要 node_modules、也不再起子进程），
# 放到 ziwei 运行时的 prebuilt/ 下，供沙箱内的玄学会话直接 `node ...pan.cjs` 使用。
#
# 何时重跑：ziwei-core 的 SKILL.md / run/pan.ts / src 更新后，或换了 ziwei 运行时目录。
# 用法：  pwsh -NoProfile -File build-ziwei-prebuilt.ps1
#         pwsh -NoProfile -File build-ziwei-prebuilt.ps1 -ZiweiHome "D:\other\ziwei-core"
param(
  [string]$ZiweiHome = $(if ($env:XUANXUE_ZIWEI_HOME) { $env:XUANXUE_ZIWEI_HOME } else { Join-Path $env:USERPROFILE '.cache\ziwei-core' })
)

$ErrorActionPreference = 'Stop'

$panTs = Join-Path $ZiweiHome 'run\pan.ts'
$esbuild = Join-Path $ZiweiHome 'node_modules\esbuild\bin\esbuild'
$entries = Join-Path $ZiweiHome 'src\docs\tianji-ziwei\entries.jsonl'
foreach ($p in @($panTs, $esbuild, $entries)) {
  if (-not (Test-Path $p)) { throw "找不到 $p（确认 ziwei 运行时安装完整）" }
}

$dest = Join-Path $ZiweiHome 'prebuilt'
$runDir = Join-Path $dest 'run'
$dataDir = Join-Path $dest 'src\docs\tianji-ziwei'
New-Item -ItemType Directory -Force -Path $runDir, $dataDir | Out-Null

$outFile = Join-Path $runDir 'pan.cjs'
Write-Output "打包 $panTs → $outFile"
Push-Location $ZiweiHome
try {
  & node $esbuild 'run\pan.ts' --bundle --platform=node --format=cjs --target=node20 `
    --log-level=warning "--outfile=$outFile"
  if ($LASTEXITCODE -ne 0) { throw "esbuild 失败，退出码 $LASTEXITCODE" }
} finally {
  Pop-Location
}

# --ni 模式用 __dirname/../src/docs/tianji-ziwei/entries.jsonl 检索倪师原话，按同一相对路径放一份。
Copy-Item $entries (Join-Path $dataDir 'entries.jsonl') -Force

Write-Output '自检：'
& node $outFile --selftest
if ($LASTEXITCODE -ne 0) { throw "预编译入口自检未通过，退出码 $LASTEXITCODE" }

$size = [math]::Round(((Get-Item $outFile).Length) / 1MB, 2)
Write-Output "完成：$outFile（$size MB）"
