# Chara Dasha 规则参考

> 来源：Jaimini Maharshi 原典 + KN Rao《Predicting Through Jaimini's Chara Dasha》
> 用途：timing 模块 Mode B (多 Dasha) Step 0 计算 + Step 2 解读

---

## 什么是 Chara Dasha

Jaimini 体系的核心 Dasha。基于**Lagna 星座**（而非 Moon Nakshatra）起算。
特点：
- 大运是"星座"而非"行星"
- 每个大运时长 1-12 年（变化）
- 与 Vimshottari 完全独立，是 KN Rao 推荐的最佳"第二意见"

---

## 起算规则（与 JHora「Chara dasa of K.N.Rao」及 calculator 模块对齐）

> ⚠️ 数据来源优先级：calculator 已在 structured_data.md 输出「Chara Dasha 时间线（K.N. Rao）」，
> **有该表时直接读表**，不手算、不重算；scripts/chara_dasha.py 只用于旧盘无表或复核，
> 二者同一套规则（timing 脚本直接调用 calculator 的实现；随机 20000 张盘逐段一致）。
> "Lagna 奇偶定方向 + 双主取较近 + 365.25 天年"的写法已废弃；5.1 的"双主一律取年数较大"在 5.2 改为下面的五步。
> 5.1 及更早排出的盘，Scorpio / Aquarius 这两段及其后各段可能不同（表头会注明），重排后再用。

```
起算大运 = Lagna 所在星座

方向（大运推进方向）= 看 Lagna 起第 9 宫的足性（padakrama）：
  奇足（Savya）组：Aries, Taurus, Gemini, Libra, Scorpio, Sagittarius → 顺行
  偶足（Apasavya）组：Cancer, Leo, Virgo, Capricorn, Aquarius, Pisces → 逆行
  ⚠️ 看的是第 9 宫，不是 Lagna 本身。例：Pisces Lagna 的第 9 宫是 Scorpio（奇足）→ 顺行。

每大运年数 = 从该大运星座数到其星座主所在星座（含终点不含起点；主在本座 = 12）
  ⚠️ 数的方向看「这个大运星座自己」的足性，不是整体推进方向：
     该座属奇足组 → 顺数；属偶足组 → 逆数。
  双主座：Scorpio（Mars / Ketu）、Aquarius（Saturn / Rahu）→ 先定用哪一主，再照上面的数法数：
     a. 两主都在本座 → 12 年
     b. 只有一主在本座 → 数到另一主
     c. 两主都不在本座 → 同座行星更多者（与该主同星座的其他行星，九星含节点）
     d. 仍相同 → 看两主所落星座：变动座 > 固定座 > 启动座
     e. 仍相同 → 取年数较大者

年长 = 恒星年（365.256363 天）。

例：
  Aries 大运，Aries 属奇足 → 顺数；Aries 主 Mars 在 Leo：
    Taurus(1) → Gemini(2) → Cancer(3) → Leo(4) = 4 年
  Leo 大运，Leo 属偶足 → 逆数；Leo 主 Sun 在 Aries：
    Cancer(1) → Gemini(2) → Taurus(3) → Aries(4) = 4 年
```

### ⚠️ Chara Dasha 变体声明

```
Jaimini Chara Dasha 在不同流派之间差异显著。本系统采用 K.N. Rao 变体（上节规则），
单主座年数已按 JHora「Chara dasa of K.N.Rao」对照（双盘 24/24）；双主座按下文「副主处理立场」的出处。其他流派：

  Lagna 本身奇偶定方向的简化写法：不是 K.N. Rao 的规则，不采用
  Iranganti Rangacharya 派：复合规则，考虑 Lagna 的 Movable/Fixed/Dual 性质
  Sanjay Rath (SJC) 派：Karakamsa 位置 + Lagna 性质的复合规则
  PVR Narasimha Rao 派：与 K.N. Rao 接近，但双主处理与周期数细节不同
  PyJHora 的 KN_RAO 实现：方向规则相同，但对宫主入旺/入陷再 ±1 年，
    在部分盘上与 JHora 不一致，本系统不采用

软件对照协议：
  如果用户软件（JHora / Parashara's Light / Kala / etc.）输出的 Chara Dasha
  与本系统计算结果不一致：

  1. 不直接判为错误。
  2. 必须记录用户软件采用的：
     - Chara Dasha 变体名称（K.N. Rao / Rangacharya / SJC / PVR / 其他）
     - 起运星座（与本系统是否一致）
     - 顺行/逆行方向（与本系统是否一致）
     - Scorpio / Aquarius 双主处理规则
  3. 在 dc1 主题审计报告中标注：
     "本盘 Chara Dasha 采用 [流派名] 算法，与用户软件 [软件名] 输出一致 / 不一致"
  4. 在 cross_verification 三 Dasha 验证中，Chara Dasha 命中率偏差
     可能受流派差异影响，不一定是算法错误。

默认策略：用本系统 K.N. Rao 规则（读 structured_data 的表）；
         用户软件是 JHora 的 K.N. Rao 选项时应完全一致，不一致先查出生数据；
         用户明确使用其他流派时，在报告里标注流派差异，不强行对抗软件。
```

---

## 星座主表（含 Rahu/Ketu 副主）

```
| 星座 | 主 | 副主（若适用） |
|------|----|------------|
| Aries | Mars | — |
| Taurus | Venus | — |
| Gemini | Mercury | — |
| Cancer | Moon | — |
| Leo | Sun | — |
| Virgo | Mercury | — |
| Libra | Venus | — |
| Scorpio | Mars | Ketu（副主） |
| Sagittarius | Jupiter | — |
| Capricorn | Saturn | — |
| Aquarius | Saturn | Rahu（副主） |
| Pisces | Jupiter | — |
```

### 副主处理立场

```
本系统（v5.2）：先定用哪一主，再数年数。顺序固定，前一步分出胜负就不看后一步：
  a. 两主都在本座                → 12 年
  b. 只有一主在本座              → 数到另一主（在本座的那一主不用）
  c. 两主都不在本座              → 同座行星更多者
  d. 同座行星数相同              → 所落星座性质：变动座 > 固定座 > 启动座
  e. 仍相同                      → 年数较大者

出处：
  - BPHS Dasha 章的共主规则。P.V.R. Narasimha Rao（JHora 作者）2005 年在 Sri Jagannatha 讨论组
    「Chara dasa: Lords of Aq and Sc」逐条列出：同在本座 12 年；一主在本座取另一主；
    有行星相伴者强于独处者；启动座弱于固定座、固定座弱于变动座；最后取年数较大者。
  - K.N. Rao《Predicting through Jaimini's Chara Dasha》：双主座"与更多行星同座者较强"，
    例盘按此数到 Ketu / Rahu。
  - 5.1 及更早写成"两主各数一次取年数较大者"，只相当于 e 这最后一步。那条写法是从 JHora 的
    2 个双主数据点反推的，这 2 个点用 a–e 也得到同样结果（Sc 走 c，Aq 走 d），所以当时没有暴露。

没有采用的做法：
  - 入旺 +1 年 / 入陷 −1 年：K.N. Rao 明确不用。
  - PVR 传承在 c 之后插入"入旺者优先"，并在自己的 Parasara 版 Chara Dasha 里把 d 的顺序反过来
    （启动 > 固定 > 变动）：那是另一个变体，不是 K.N. Rao 的规则。
  - K.N. Rao 的最后一步是比两主的度数；本系统走到 e 时两主条件已完全对称，按年数较大者定，
    若用户软件在这一步给出不同年数，按下面的对照写法标注。

其他流派的副主处理：
  Iranganti Rangacharya 派："力量优先"，取力量较强者（按 Shadbala 或 Avastha）
  Sanjay Rath (SJC) 派：复合规则，考虑副主与主星的角度关系、各自的 Karaka 角色等
  JHora 的「Chara dasa of K.N.Rao」选项：PVR 本人说明它判共主强弱时并不严格照 K.N. Rao，
    且软件里可以手动指定 Sc/Aq 的主；双主座与 JHora 不一致时先看这一项设置

实操：
  - 读 structured_data「Chara Dasha 时间线」的「所数宫主」「双主座依据」两列，不重算
  - 默认用本系统规则，不因预测偏差临时换算法（那是事后拟合）
  - 用户软件在 Scorpio/Aquarius 年数上与本系统不同 →
    在 dc1 报告中标注："本盘 Scorpio/Aquarius 大运年数在 [软件/流派] 下为 X 年，本系统为 Y 年（依据：…）"；
    该座之后各段的起止相差 |X−Y| 年，用这些段做双系统共振时按条件句写
```

---

## 完整算例

```
案例：Aries Lagna；第 9 宫 Sagittarius（奇足）→ 大运顺行
行星：Sun Aries · Moon Gemini · Mars Leo · Mercury Pisces · Jupiter Sagittarius
      Venus Capricorn · Saturn Aquarius · Rahu Gemini · Ketu Sagittarius

大运座      足性  数法   宫主位置                 年数
Aries       奇    顺数   Mars 在 Leo              4
Taurus      奇    顺数   Venus 在 Capricorn       8
Gemini      奇    顺数   Mercury 在 Pisces        9
Cancer      偶    逆数   Moon 在 Gemini           1
Leo         偶    逆数   Sun 在 Aries             4
Virgo       偶    逆数   Mercury 在 Pisces        6
Libra       奇    顺数   Venus 在 Capricorn       3
Scorpio     奇    顺数   Mars 独处 Leo / Ketu 在 Sagittarius 与 Jupiter 同座 → 数到 Ketu  1
Sagittarius 奇    顺数   Jupiter 在本座           12
Capricorn   偶    逆数   Saturn 在 Aquarius       11
Aquarius    偶    逆数   Saturn 在本座 → 数到另一主 Rahu（Gemini）    8
Pisces      偶    逆数   Jupiter 在 Sagittarius   3

累计 = 70 年（scripts/chara_dasha.py 与 calculator 输出一致）
```

---

## 解读规则（Step 2 用）

### 三层结构

```
第 1 层：大运星座本身
  Chara MD = 该星座 → 该星座在本盘是几宫？该宫位主题被激活。
  
  例：Cancer Chara MD，Cancer 在本盘是 7 宫 → 该期主题：婚姻/合作

第 2 层：大运星座中的行星
  该星座中有哪些行星？它们的 P1 身份 + 状态 = 给该 MD 染色。
  
  例：Cancer 中有 Moon 和 Jupiter
      Moon 是 L4 (Trader)，Jupiter 是 L9+L12 (Faithful)
      → 该期：合作主题 + 母性/情绪 + 智慧/导师 + 隐性损耗

第 3 层：大运星座的对冲位
  对冲位 = 第 7 宫位置 → 该期的"外部对照"。
  
  例：Cancer 的对冲是 Capricorn，Capricorn 在本盘是 1 宫
      → 该期：婚姻主题被激活时，"自我"也被对照（典型婚姻定位期）
```

### Karaka 联动

```
当 Chara MD = AK (Atmakaraka) 所在的星座或其对冲位
  → "灵魂主题年"：人生主线方向出现重大调整
  → 此期事件具有"灵魂层级"的重要性

Chara MD = AmK (Amatyakaraka) 所在的星座或其对冲位
  → "事业主题年"：事业重大转折

Chara MD = DK (Darakaraka) 所在的星座或其对冲位
  → "配偶主题年"：婚姻/伴侣相关重大事件

Chara MD = GK (Gnatikaraka) 所在的星座或其对冲位
  → "障碍主题年"：需面对长期回避的问题、健康议题

Chara MD = PK (Putrakaraka) 所在的星座或其对冲位
  → "创造/子女主题年"：生育、创业、艺术作品发布

Chara MD = MK (Matrukaraka) 所在的星座或其对冲位
  → "母亲/根源主题年"：母系亲属、心理根源、家乡

Chara MD = BK (Bhratrukaraka) 所在的星座或其对冲位
  → "兄弟/同盟主题年"：兄弟姐妹、合作伙伴、武功层面（勇气、努力）
```

### Atmakaraka 一般规则

```
KN Rao 强调：
  Chara MD 中如果出现 AK 或 AK 在该 MD 的星座得到激活，
  此 MD 是该人生命中最重要的阶段之一。
  
  Atmakaraka 的"角色"（它本身的 P1 身份）决定主题颜色。
```

---

## Antardasha（小运）算法（简化）

```
Chara Antardasha 的算法比 MD 更复杂，主流派别有差异。
最常用的方式（KN Rao 体系）：

在某个 Chara MD（如 Cancer MD = 11 年）内：
  AD 顺序按大运推进方向继续（方向见上：第 9 宫足性）
  AD1 = 该 MD 星座本身（Cancer）
  AD2 = 下一个星座（Leo）
  AD3 = Virgo
  ...
  AD12 = Gemini（回到起点前）

每个 AD 时长 = MD 时长 / 12（粗略）
  Cancer MD = 11 年 → 每 AD ≈ 11/12 ≈ 11 个月

更精确的算法：
  每个 AD 时长按其星座主的距离比例分配（与 MD 算法同源）
  这部分实现复杂，本 skill 在 Step 0 计算时用简化版（均分 12 等份），
  在 Step 4 交汇矩阵中标注"Chara AD 简化版，仅阶段参考"。
  ⚠️ AD 的顺序与时长没有经过 JHora AD 金标准核对（calculator 也只输出 MD 级）：
     Chara AD 只作阶段参考，不能拿来定月份；月级窗口一律看 Vimsottari PD（三级运）。
```

---

## 与 Vimshottari 的协同 vs 矛盾

```
协同（应当一致的信号）：
  Vim Jupiter MD + Chara MD 在 5/9 宫 → 双重智慧/教育/扩张主题
  Vim Venus MD + Chara MD 在 DK 所在或 7 宫 → 双重感情/婚姻主题
  Vim Saturn MD + Chara MD 在 6 或 8 宫 → 双重压力/转化主题

矛盾（信号分歧）：
  Vim Rahu MD（迷雾/野心） + Chara MD = 9 宫（导师/远方）
    → 同时存在"灵性追求"和"野心扩张"两条平行线索
    → 不冲突，而是"双轨人生"
  
  Vim Saturn MD（限制） + Chara MD = 11 宫（收入/目标）
    → 同时存在"承担责任"和"目标达成"
    → 通常是"高压力高产出"窗口
  
处理冲突的原则：
  Vimshottari = 心理感受
  Chara Dasha = 外在事件
  两者不一致时常常是"外在丰收但心累"或"外在艰难但内在成长"
  这不是冲突，是真实人生的双层结构
```

---

## 临床速查表（KN Rao 教学常用）

```
"灵魂大年"信号：
  Chara MD = AK 所在星座本身
  Chara MD = AK 所在星座的对冲位
  Chara MD = AK 自然年龄段对应（AK Sun → 中年；AK Moon → 童年/晚年；等）

"婚姻大年"信号：
  Chara MD = DK 所在星座本身
  Chara MD = 本盘 7 宫
  Chara MD = 本盘 2 宫（家庭扩张）
  Chara MD = Venus 所在星座（自然婚姻 Karaka）

"事业大年"信号：
  Chara MD = AmK 所在星座
  Chara MD = 本盘 10 宫
  Chara MD = 10 宫主所在星座
  Chara MD = 本盘 11 宫（收入实现）

"健康警示年"信号：
  Chara MD = 本盘 6 宫
  Chara MD = 本盘 8 宫
  Chara MD = GK 所在星座
  Chara MD = 6/8/12 宫主所在星座

"灵性突破年"信号：
  Chara MD = 本盘 12 宫
  Chara MD = 本盘 9 宫
  Chara MD = AK 所在星座对冲位
  Chara MD = Ketu 所在星座
```

---

# Argala（干预力）— Jaimini 体系的精细化工具

> Argala = "干预" / "影响"，用于细化 Chara Dasha 期间事件的方向和品质。
> 来源：Jaimini Sutras 1.1.45-1.1.50 + KN Rao 临床注释 + SJC 体系深化
> 用途：Chara Dasha 主题判定后，用 Argala 进一步看"这个主题会顺着展开还是受阻"

## Argala 的核心概念

```
基础原则：
  当 Chara Dasha 走到一个星座（= 一个宫位）时，
  该宫位的"主题"是否能顺利兑现，由从该宫位起的特定其他宫位行星决定。
  
  这些"干预者"叫 Argala（正向加持）
  阻止 Argala 的叫 Virodha Argala（反向阻挡）

逻辑结构：
  Chara MD 星座 = 主题宫
  ↓
  Argala 宫位 = 提供"加持/阻挡"的干预力
  ↓  
  Virodha Argala 宫位 = 决定 Argala 是否能真正生效
  
最终判定：
  Argala > Virodha Argala → 主题顺利展开（带 Argala 行星的色彩）
  Argala = Virodha Argala → 主题中性（按 Chara MD 主题展开，无特殊增减）
  Argala < Virodha Argala → 主题受阻（带 Virodha Argala 行星的色彩）
```

## 主要 Argala 位（按强度排序）

```
从 Chara MD 星座起算，以下宫位的行星形成 Argala：

1. 4 宫 Argala (Shubha Argala，主要 Argala)
   → 该宫位行星 = 主要干预者
   → 吉星在此 = 强力加持
   → 凶星在此 = 强力阻挡
   被 10 宫的行星制约 (Virodha)

2. 2 宫 Argala (Dhana Argala，财富 Argala)
   → 影响该主题的"资源/财务"维度
   被 12 宫的行星制约 (Virodha)

3. 11 宫 Argala (Labha Argala，收益 Argala)
   → 影响该主题的"实现/收获"维度
   被 3 宫的行星制约 (Virodha)

4. 5 宫 Argala (Putra Argala，创造 Argala)
   → 影响该主题的"创造/智慧/趣味"维度
   被 9 宫的行星制约 (Virodha)
   ⚠️ 注意：这一对的 Argala/Virodha 关系在某些流派中颠倒，
      本系统采用 SJC 派：5宫 = Argala，9宫 = Virodha
```

## Argala 评分算法

```
对当前 Chara MD 的每个 Argala 位：

  Step 1：查该宫位是否有行星
    无行星 → Argala 力 = 0（中性）
    有行星 → 继续 Step 2
    
  Step 2：查行星的自然属性
    吉星（Jupiter / Venus / Mercury / 强 Moon）= +1（加持）
    凶星（Saturn / Mars / Sun / Rahu / Ketu）= -1（阻挡）
    
  Step 3：查行星的状态
    入旺/入庙/Vargottama → ×1.5
    燃烧/落陷 → ×0.5
    
  Step 4：查 Virodha Argala 位是否有制约
    Virodha 位有吉星 → 削弱原 Argala 的吉力
    Virodha 位有凶星 → 削弱原 Argala 的凶力
    
  最终 Argala 净分 = Σ(Argala) - Σ(Virodha Argala)

判定：
  净分 ≥ +1.5  → 强加持（主题大顺，可大胆推进）
  净分 +0.5 ~ +1.5 → 中等加持（主题顺利但需努力）
  净分 -0.5 ~ +0.5 → 中性（按基础主题展开）
  净分 -0.5 ~ -1.5 → 中等阻挡（主题受阻，需绕路）
  净分 ≤ -1.5  → 强阻挡（主题大幅打折或转向反面）
```

## 实战示例

```
示例 1：Chara MD = 本盘 7 宫（关系主题）
  Lagna = Cancer，所以 7 宫 = Capricorn

  查 Argala 位（从 Capricorn 起算）：
    4 宫从 Cap = Aries → 该宫行星：无 → Argala = 0
    2 宫从 Cap = Aquarius → 该宫行星：Jupiter 入庙 → Argala = +1.5
    11 宫从 Cap = Sagittarius → 该宫行星：Mercury 中性 → Argala = +1
    5 宫从 Cap = Taurus → 该宫行星：Venus 入庙 → Argala = +1.5
  
  查 Virodha 位：
    10 宫从 Cap = Libra → 该宫行星：无 → Virodha = 0
    12 宫从 Cap = Sagittarius → ... (与 11 宫共宫，已计入)
    3 宫从 Cap = Pisces → 该宫行星：无 → Virodha = 0
    9 宫从 Cap = Virgo → 该宫行星：Saturn 中性 → Virodha = -1
  
  净分 = (0 + 1.5 + 1 + 1.5) - (-1) = 5（注：Virodha 是减负数 = 加正数）
  
  判定：强加持
  
  解读：
  "这段 Chara MD 是关系大年，而且各方面的'干预力'都是吉星——
   Jupiter 提供智慧+扩张，Venus 提供美感+亲密，Mercury 提供沟通。
   只有从 Capricorn 起的 9 宫有 Saturn 提供一些'必须严肃以对'的克制力，
   但这不是阻挡，而是把关系从'热闹'锚定到'承诺'。
   翻译成人话：这是一个能从'恋爱'升级到'婚姻'的窗口。"

示例 2：Chara MD = 本盘 10 宫（事业主题）
  ...同样的算法 → 净分 -1.8 → 强阻挡
  
  解读：
  "虽然这段 Chara 走到事业宫，看起来是事业大年，
   但所有 Argala 位的行星都在制约——
   翻译成人话：事业有机会但绊脚石很多，'卡点年'。
   不是不要做事业，而是要预料每一步都会有阻力，做好心理准备。"
```

## Argala 与 Vimshottari 的交叉

```
Argala 是 Chara Dasha 专属工具，但可以与 Vimshottari 交叉验证：

  Chara MD 强加持 + Vimshottari 当前 MD/AD 也是吉星 → 双重确认
  Chara MD 强加持 + Vimshottari 当前 MD/AD 是凶星 → 矛盾，按"心理外在分层"
    （Vim 是心理：可能心累；Chara 是外在：但事顺）
  Chara MD 强阻挡 + Vimshottari 吉星 → 同上反向（心情好但事情卡）
  Chara MD 强阻挡 + Vimshottari 凶星 → 双重确认（这段时间最难，做好准备）
```

## 何时在 timing 中启用 Argala

```
启用条件：
  - Mode B Chara Dasha 主题已判定后，希望细化"是顺是逆"
  - 用户问"这段时间我做 X 会成吗"——给 X 涉及的宫位做 Argala 评分
  - 三 Dasha 交叉验证（cross_verification.md）中 Chara Dasha 的吉凶判定
    
默认 timing Mode B Step 2 中可启用，作为 Chara Dasha 主题判定后的"细化层"。

写作风格示例：
  ✅ "Chara 走到关系宫确实是关系大年，
      但配套的 4 宫 Argala（家人意见）有 Saturn 在制约——
      你可能心动到位但家里会有一关要过。"
  
  ❌ "Argala 净分 +3.5，Virodha -1.2，故关系主题强加持。"
      （参数化、不解释、堆术语，禁止）
```
