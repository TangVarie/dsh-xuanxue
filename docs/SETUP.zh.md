# 运行时准备（玄学台）

玄学台的插件部分只负责界面、预设和解读协议；排盘要三种本机环境。这份文档说明每一样装在哪、插件怎么找到它，以及坏了怎么查。

## 1. 一条命令：setup-runtime.ps1

脚本在插件内置的 `xuanxue-orchestra` 技能目录下（技能加载时会给出绝对路径；GitHub 安装后在 profile 的 `node_modules/dsh-xuanxue/skills/xuanxue-orchestra/scripts/`）。

```powershell
pwsh -NoProfile -File scripts/setup-runtime.ps1 -DryRun   # 只打印计划，不动磁盘
pwsh -NoProfile -File scripts/setup-runtime.ps1           # 建 venv、装依赖、检查紫微
pwsh -NoProfile -File scripts/setup-runtime.ps1 -Force    # 重建 venv
```

它把 Python 环境建在插件外面，更新插件不会把它冲掉：

| 位置 | 内容 |
|---|---|
| `%DSH_HOME%\xuanxue\venv` | Python 环境：PyJHora 4.8.6、pysweph 2.10.3.6、numpy 2.3.5、timezonefinder 6.0.1、pytz、PyYAML、lunar_python 1.4.4 |
| `%DSH_HOME%\xuanxue\ziwei` | 紫微预编译入口（只有找到源码时才建） |
| `%DSH_HOME%\xuanxue\runtime.json` | 解析结果，`health-check.ps1` 优先读它 |

`DSH_HOME` 默认 `%USERPROFILE%\.dsh`，`XUANXUE_HOME` 可以整体换位置。基础 Python 要 3.10–3.13（pysweph 不支持 3.14+）；脚本按 `XUANXUE_PYTHON` → DSH 自带运行时 → PATH 找。

## 2. 解释器怎么解析

体检脚本按这个顺序找，命中即止，结果写进 `health.json` 的 `notes`：

| 门 | 顺序 |
|---|---|
| 八字、六爻 | `XUANXUE_PYTHON` → `runtime.json` → `<运行时>\venv\Scripts\python.exe` → DSH 自带 Python → 旧的本机布局 → PATH 里的 `python` |
| 吠陀 | `XUANXUE_VEDIC_PY` → `runtime.json` → `<运行时>\venv\Scripts\python.exe` → 工作区 `vedic\vedic-calc-env\Scripts\python.exe` |
| 紫微 | `XUANXUE_ZIWEI_PAN` → `runtime.json` → `<运行时>\ziwei\prebuilt\run\pan.cjs` → `%USERPROFILE%\.cache\ziwei-core\prebuilt\run\pan.cjs` |

环境变量名一览：`XUANXUE_HOME`、`XUANXUE_PYTHON`、`XUANXUE_VEDIC_PY`、`XUANXUE_ZIWEI_PAN`、`XUANXUE_ZIWEI_HOME`、`XUANXUE_SKILLS_ROOT`（体检时换技能根，一般不用）。

## 3. 紫微运行时

紫微的排盘引擎是独立的 ziwei-doushu（iztro 加斗数全书口径修正），不随插件分发。准备方式：

1. 拿到 ziwei-doushu 源码，装好它的 `node_modules`（需要 `run/pan.ts`、`node_modules/esbuild`、`src/docs/tianji-ziwei/entries.jsonl` 三样）。
2. 设 `XUANXUE_ZIWEI_HOME` 指向那个目录，或放到默认的 `%USERPROFILE%\.cache\ziwei-core`。
3. 跑 `pwsh -NoProfile -File scripts/setup-runtime.ps1`（它会调 `build-ziwei-prebuilt.ps1` 打出预编译入口），或直接 `pwsh -NoProfile -File scripts/build-ziwei-prebuilt.ps1 -ZiweiHome <目录>`。

为什么不用官方入口：`node node_modules\tsx\dist\cli.mjs run\pan.ts` 需要 tsx 起 esbuild 子进程，DSH 的沙箱禁止子进程管道，会报 `spawn EPERM`。预编译入口是把 `pan.ts` 打成一个单文件 CJS，参数完全一致（`--selftest`、`--ni`、`--json`）。

## 4. 吠陀依赖与星历

- 依赖固定为 PyJHora 4.8.6、pysweph 2.10.3.6、numpy 2.3.5、timezonefinder 6.0.1、pytz。
- 星历文件是技能自带的 `skills/vedic/calculator/scripts/ephe/*.se1` 三个文件，计算引擎显式使用这一份，不需要另装。
- 验证：用该解释器跑 `calculator/scripts/check_env.py`，通过时会打印 `SAV=337` 与「环境就绪」；它自己也会给出修复命令（`calculator/scripts/setup_env.py`）。
- pip 卡在缓存临时文件时设 `$env:PIP_NO_CACHE_DIR="1"`，`setup-runtime.ps1` 默认就设了。

## 5. 体检与排错

```powershell
pwsh -NoProfile -File scripts/health-check.ps1          # 默认：最小自检
pwsh -NoProfile -File scripts/health-check.ps1 -Quick   # 只冒烟
pwsh -NoProfile -File scripts/health-check.ps1 -Full    # 八字 52 项 + 六爻 96 项 + 紫微排盘 + 吠陀回归
```

输出写当前工作区的 `xuanxue-skills/health.json`，退出码：有 fail=1，只有 warn=0。常见态：

- **fail：没解析到 Python / 吠陀计算环境** → 跑 `setup-runtime.ps1`，或把已有解释器写进 `XUANXUE_PYTHON` / `XUANXUE_VEDIC_PY`。
- **fail：缺预编译入口** → 见第 3 节。
- **warn：六爻单测 1 项错误 / 吠陀回归部分未完成** → 沙箱里 `%TEMP%` 写入受限导致，排盘本身正常，不算失败。
- **fail：紫微自检未通过** → 换运行时目录后没重打包，重跑 `build-ziwei-prebuilt.ps1`。

体检只读，不改档案；它也不许被当成「已应验」的证据。
