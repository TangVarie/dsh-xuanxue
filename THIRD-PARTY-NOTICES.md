# 第三方声明

玄学台本体不在公开许可下分发（`package.json` 的 `license` 是 `UNLICENSED`）。下面这些随仓库分发的第三方内容各自适用原来的许可。

## Swiss Ephemeris（星历文件）

`skills/vedic/calculator/scripts/ephe/` 下的三个文件：

| 文件 | 内容 |
|---|---|
| `semo_18.se1` | 月亮星历（约 1800–2400 年） |
| `sepl_18.se1` | 行星星历（约 1800–2400 年） |
| `seas_18.se1` | 小行星星历 |

来自 [Swiss Ephemeris](https://www.astro.com/swisseph/)（Astrodienst AG）。Swiss Ephemeris 以 AGPL-3.0 与商业许可双许可发布；本仓库**按 AGPL-3.0 原样分发这份星历数据**，许可原文见 <https://www.gnu.org/licenses/agpl-3.0.html>，项目主页与许可说明见 <https://www.astro.com/swisseph/>。这些文件只由吠陀计算脚本读取，不参与插件运行。

如果你要用 Swiss Ephemeris 做闭源或商业分发，需要自己从 Astrodienst 取得商业许可，并替换这三个文件。

## Python 依赖（运行时安装，不随仓库分发）

吠陀与八字 / 六爻的计算脚本运行时安装以下包，各自遵循其 PyPI 页面上的许可：

- PyJHora（吠陀排盘）— AGPL-3.0
- pysweph（Swiss Ephemeris 的 Python 绑定）— AGPL-3.0
- numpy — BSD-3-Clause
- timezonefinder — MIT
- pytz — MIT
- PyYAML — MIT
- lunar_python — MIT

## 紫微引擎

紫微排盘依赖独立的 ziwei-doushu 运行时（iztro 加斗数全书口径修正），不随本仓库分发；在别人的机器上如何准备见 `docs/SETUP.zh.md` 第 3 节。

## 技能内的引用材料

`skills/*/references/` 与各 `MODULE.md` 里的方法条文、口诀与判定规则，是解读协议的一部分；其中标注【倪】的条目引用倪海厦《天纪》的讲次与时间码，标注【赵】的条目引用赵财猫的付费长文，均只作方法与出处标注，不随仓库分发原始讲稿或原文。
