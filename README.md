# 玄学台 · DeepSeek Harness 插件

把八字、六爻、紫微斗数、吠陀占星四门做成一个可安装的 DeepSeek Harness 插件：左栏多一页「玄学」工作台，多一个「玄学」智能体预设，四门解读技能与实践层（xuanxue-orchestra）随包自带。四门不是四个并列功能，而是一套互为交叉验证的方法体系——提问台只让你陈述问题，智能体自己分诊、选最少充分集、独立跑各门、做交叉拟合，最后给结论或一起讨论。

这个仓库同时是**插件本体**和**插件索引**：装了 DSH 的机器只要添加一次索引地址，就能在「插件 → 发现」里安装玄学台；以后这个仓库登记了新版本，插件页会出现「更新」。

## 索引地址（一个网址）

```
https://raw.githubusercontent.com/TangVarie/dsh-xuanxue/main/index.json
```

GitHub 的 raw 域名在国内不一定稳定。读不到时把同一份索引换到别的静态地址，或者等网络恢复；插件代码本身也是从这个仓库按提交号取的。

## 装一次

1. 侧栏「插件」→「实验性插件」里打开「自定义插件索引」（已开过就跳过）。
2. 插件页「发现」→「添加索引源」→ 粘贴上面的索引地址。
3. 找到「玄学台」→ 安装。
4. 刷新页面。左栏出现「玄学」，新会话的预设列表里出现「玄学」。

装好之后，地址和版本都不用再管；更新在插件页点。

## 装完还要准备运行时（每台机器一次）

四门的排盘脚本跑在插件外面：Python 环境（八字 lunar_python、六爻 PyYAML、吠陀 PyJHora + pysweph）、Node.js（紫微），以及吠陀的星历文件（这个仓库自带）。插件不替你装这些，但一条命令就够：

```powershell
# 在插件内置的 xuanxue-orchestra 技能目录下
pwsh -NoProfile -File scripts/setup-runtime.ps1 -DryRun   # 先看计划
pwsh -NoProfile -File scripts/setup-runtime.ps1           # 真装
pwsh -NoProfile -File scripts/health-check.ps1            # 体检四门
```

细节、环境变量与紫微运行时的准备见 [docs/SETUP.zh.md](docs/SETUP.zh.md)。装好后在玄学台页面点「体检」，四门状态会写进工作区的 `xuanxue-skills/health.json`。

## 仓库结构

| 文件 | 作用 |
|---|---|
| `package.json` | 包清单：`dsh.bundle.patch`、`dsh.client`、`engines.dsh` |
| `cordis.patch.yml` | profile 里的一层：插入一行插件，让浏览器半、预设和 Host 半随包被发现 |
| `index.js` | Host 半：把包内 `skills/` 注册成一个技能来源（不写死任何目录） |
| `client.js` | 浏览器半：左栏「玄学」整页工作台 |
| `presets/xuanxue.patch.yml` | 「玄学」智能体预设：四门一体的调度协议与工具面 |
| `skills/` | 四门技能 + 实践层，以及体检 / 装环境 / 紫微打包脚本 |
| `locale/*.json` | 插件页的标题与说明（中文 / 英文） |
| `docs/DETAIL.zh.md`、`docs/preview.svg` | 插件详情页 |
| `docs/SETUP.zh.md` | 运行时准备与排错 |
| `index.json` | 插件索引（format 1），供插件页「发现」读取 |
| `lib.mjs` / `release.mjs` | 索引校验 / 发版登记 |

`skills/` 里不放排盘运行时，只放解读协议与计算脚本；解释器路径一律按「环境变量 → 玄学运行时 → 本机已有环境」解析，所以同一个包在工作区、`node_modules`、别人的机器上都成立。

## 发一版

1. 改代码（或 `skills/`），把 `package.json` 的 `version` 加上去。
2. 自检：

   ```bash
   node --check client.js
   node --check index.js
   node test/index.test.mjs
   node test/skills.test.mjs
   ```

3. 提交、推送。
4. 记下这次提交的完整 40 位提交号，登记索引：

   ```bash
   node release.mjs <40 位提交号>
   ```

   脚本从那次提交里读 `package.json`（不读工作区），把版本、包名、`engines.dsh` 和发布时间写进 `index.json`；同一版本登记过会被拒绝。
5. 把改过的 `index.json` 再提交、推送。GitHub raw 有几分钟缓存，刷新插件页就能看到更新。

DSH 只在两个条件同时成立时给出「有可用更新」：本机这份是从 **Git 提交**装的（不是本地 `link:` 目录），并且索引里更高版本号的 `source` 与本机安装时的仓库地址、目录完全一致。所以每发一版，索引里的提交号必须指向**真正包含这一版 `package.json`** 的那次提交；登记过的版本不要改指向、不要删。

## 边界

- **只装了 DSH 不等于能排盘。** 排盘要靠上节的运行时；缺环境时体检会明确报哪一门缺什么，不静默降级、不手排兜底。
- **Windows 优先。** 预设与体检脚本按 Windows（PowerShell、`Scripts\python.exe`）写；其他系统要自己按 `docs/SETUP.zh.md` 把解释器写进环境变量。
- **紫微运行时不在本仓库。** 它的引擎是独立的 ziwei-doushu（iztro 加斗数全书口径修正），本仓库只带解读协议和打包脚本。
- **不碰 DSH 安装目录。** 插件只往 profile 里装自己，不改 `app.asar`。
- **不给结论兜底。** 四门协议都明确：没有依据就说没有，不凑条数，不写绝对断语。

## 第三方与许可

插件本身不在公开许可下分发（`UNLICENSED`，保留所有权利）。`skills/vedic/calculator/scripts/ephe/` 里的三个 `.se1` 星历文件来自 Swiss Ephemeris，按 AGPL-3.0 分发，署名与许可原文见 [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)。
