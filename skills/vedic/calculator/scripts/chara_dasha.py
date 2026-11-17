"""Chara Dasha (K.N. Rao 变体) — 自研实现。

规则：
  1. 起始 = Lagna 座；
  2. 方向 = 第9宫足性：奇足{Ar,Ta,Ge,Li,Sc,Sg}→顺行，偶足{Cn,Le,Vi,Cp,Aq,Pi}→逆行；
  3. 年数 = 从该座沿"该座自身足性方向"数到其宫主所在座，count−1；宫主在本座 = 12 年；
  4. 双主座 Scorpio(Mars/Ketu)、Aquarius(Saturn/Rahu) 按下列顺序定用哪一主（v5.2）：
       a. 两主都在本座 → 12 年；
       b. 只有一主在本座 → 数到另一主；
       c. 两主都不在本座 → 同座行星（与该主同星座的其他行星，九星含节点）更多者；
       d. 仍相同 → 看两主所落星座的性质：变动座 > 固定座 > 启动座；
       e. 仍相同 → 取年数较大者。
     出处：BPHS Dasha 章的共主规则（P.V.R. Narasimha Rao 2005 年在 Sri Jagannatha 讨论组逐条列出：
     同在本座 12 年 / 一主在本座取另一主 / 有行星相伴者强 / 启动 < 固定 < 变动 / 最后取年数较大）；
     K.N. Rao《Predicting through Jaimini's Chara Dasha》的例盘也按"同座行星更多者"取主。
     不采用的两步：入旺 ±1 年（K.N. Rao 明确不用）、PVR 传承在 c 之后插入的"入旺者优先"。
  5. 年长 = 恒星太阳年（sidereal solar year ≈ 365.2564 天）。

对照：JHora "Chara dasa of K.N.Rao" 双盘（2026-07-03，同一出生数据 UT 1:30/2:30，24 个大运数据点）
24/24 一致；其中双主只有 2 个数据点（Sc：Ketu 同座 3 星 vs Mars 独处 → 走 c = 8；
Aq：两主都独处，Saturn 在变动座、Rahu 在启动座 → 走 d = 2），新旧规则在这 2 个点上结果相同。
v5.1 及之前写成"两主各数一次取年数较大者"，那只是 e 这最后一步：在"一主在本座"（旧规则恒得 12 年）、
"同座行星数不同"、"星座性质不同"三类盘上与出处不符，v5.2 改正。PVR 本人说过 JHora 的这个选项
并不严格照 K.N. Rao 的规则判强弱，所以双主座以上述出处为准，不以 JHora 为唯一标准。

注：PyJHora 的 KN_RAO duration 与 JHora 在 Sg/Aq/Pi 存在偏差（8/1/9 vs 7/2/8），
故弃用其年数函数；其 ascendant 亦与本系统 engine 存在口径差，本模块只接受
engine 计算的真值输入。只输出 Mahadasha 级（双系统交叉验证足够）；
Antardasha 级待 JHora AD 对照后再启用。
"""

SIGNS = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
         'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']

# 奇足(顺数)/偶足(逆数)分组
ODD_FOOTED = {0, 1, 2, 6, 7, 8}       # Ar Ta Ge Li Sc Sg
# 各座宫主（行星名与 engine 一致）；Sc/Aq 双主
SIGN_LORDS = {
    0: ['Mars'], 1: ['Venus'], 2: ['Mercury'], 3: ['Moon'],
    4: ['Sun'], 5: ['Mercury'], 6: ['Venus'], 7: ['Mars', 'Ketu'],
    8: ['Jupiter'], 9: ['Saturn'], 10: ['Saturn', 'Rahu'], 11: ['Jupiter'],
}
SIDEREAL_YEAR_DAYS = 365.256363


def _count(from_sign, to_sign, forward):
    """从 from 数到 to（含两端）的格数。"""
    if forward:
        return ((to_sign - from_sign) % 12) + 1
    return ((from_sign - to_sign) % 12) + 1


RULE_TEXT = {
    'single': '',
    'both_in_sign': '两主都在本座',
    'other_lord': '另一主在本座，数到本主',
    'more_conjunct': '同座行星更多',
    'sign_nature': '所落星座性质更强（变动 > 固定 > 启动）',
    'larger_years': '前几步都相同，取年数较大',
}


def rule_note(sign_idx, lord, rule, alt_years=None):
    """双主座一行的依据说明（阅读版用）；单主座返回空串。"""
    if rule in ('single', None):
        return ''
    lords = SIGN_LORDS[sign_idx]
    other = lords[1] if lord == lords[0] else lords[0]
    text = {
        'both_in_sign': '两主都在本座',
        'other_lord': f'{other} 在本座，数到 {lord}',
        'more_conjunct': f'{lord} 同座行星更多',
        'sign_nature': f'{lord} 所落星座性质更强（变动 > 固定 > 启动）',
        'larger_years': '前几步相同，取年数较大',
    }.get(rule, rule)
    if alt_years is not None and rule != 'other_lord':
        text += f'；另一主 {other} 为 {alt_years} 年'
    return text


_NATURE_RANK = {0: 0, 1: 1, 2: 2}   # sign_idx % 3：0 启动 < 1 固定 < 2 变动


def md_years(sign, planet_signs):
    """单座年数与所用宫主（KN Rao）。planet_signs: {行星名: sign_idx}（九星）。

    返回 {'years', 'lord', 'rule', 'alt_years'}：
      rule       见 RULE_TEXT；
      alt_years  双主座里另一主给出的年数（单主座，或两主年数相同时为 None）——
                 与其他软件对照时用，不是候选结论。
    """
    forward = sign in ODD_FOOTED
    lords = SIGN_LORDS[sign]

    def yrs(lord):
        ls = planet_signs[lord]
        return 12 if ls == sign else _count(sign, ls, forward) - 1

    if len(lords) == 1:
        return {'years': yrs(lords[0]), 'lord': lords[0], 'rule': 'single', 'alt_years': None}

    a, b = lords
    in_a, in_b = planet_signs[a] == sign, planet_signs[b] == sign
    ya, yb = yrs(a), yrs(b)

    def out(lord, rule):
        y, other = (ya, yb) if lord == a else (yb, ya)
        return {'years': y, 'lord': lord, 'rule': rule, 'alt_years': other if other != y else None}

    if in_a and in_b:
        return {'years': 12, 'lord': a, 'rule': 'both_in_sign', 'alt_years': None}
    if in_a:
        return out(b, 'other_lord')
    if in_b:
        return out(a, 'other_lord')

    def companions(lord):
        return sum(1 for p, sg in planet_signs.items() if p != lord and sg == planet_signs[lord])

    ca, cb = companions(a), companions(b)
    if ca != cb:
        return out(a if ca > cb else b, 'more_conjunct')
    na, nb = _NATURE_RANK[planet_signs[a] % 3], _NATURE_RANK[planet_signs[b] % 3]
    if na != nb:
        return out(a if na > nb else b, 'sign_nature')
    return out(a if ya >= yb else b, 'larger_years')


def _duration_years(sign, planet_signs):
    """兼容旧调用：只返回年数。"""
    return md_years(sign, planet_signs)['years']


def calc_chara_dasha(lagna_sign_idx, planet_signs, birth_jd_ut):
    """KN Rao Chara Dasha 大运时间线（一个完整周期，12 座）。

    Args:
        lagna_sign_idx: engine 计算的 Lagna 星座索引（0=Aries）
        planet_signs: {行星名: 星座索引}，engine 真值（9 星含 Rahu/Ketu）
        birth_jd_ut: 出生时刻 UT 儒略日（engine to_jd 的产物）
    Returns:
        {'method': ..., 'direction': 'forward'/'reverse', 'mahadashas': [
            {'sign','start_jd','end_jd','years'} ...]}
    """
    ninth = (lagna_sign_idx + 8) % 12
    forward = ninth in ODD_FOOTED
    step = 1 if forward else -1

    seq = [(lagna_sign_idx + step * i) % 12 for i in range(12)]
    mds, jd = [], birth_jd_ut
    for s in seq:
        r = md_years(s, planet_signs)
        end = jd + r['years'] * SIDEREAL_YEAR_DAYS
        mds.append({'sign': SIGNS[s], 'sign_idx': s,
                    'start_jd': jd, 'end_jd': end, 'years': r['years'],
                    'lord': r['lord'], 'rule': r['rule'], 'alt_years': r['alt_years']})
        jd = end
    return {'method': 'Chara Dasha (K.N. Rao)',
            'rule_version': 'colord-v2',
            'direction': 'forward' if forward else 'reverse',
            'mahadashas': mds}


if __name__ == '__main__':
    # 金标准自测：JHora 双盘（1990-08-15 上海坐标）
    import swisseph as swe
    planet_signs_common = {'Sun': 3, 'Moon': 1, 'Mars': 0, 'Mercury': 4,
                           'Jupiter': 3, 'Venus': 3, 'Saturn': 8,
                           'Rahu': 9, 'Ketu': 3}
    # 盘A: UT 2:30 → Lagna Libra(6)；JHora: Li9 Sc8 Sg7 Cp1 Aq2 Pi8 Ar12 Ta2 Ge2 Cn2 Le1 Vi1
    # 盘B: UT 1:30 → Lagna Virgo(5)；JHora: Vi1 Li9 Sc8 Sg7 Cp1 Aq2 Pi8 Ar12 Ta2 Ge2 Cn2 Le1
    expects = {
        6: [('Libra',9),('Scorpio',8),('Sagittarius',7),('Capricorn',1),('Aquarius',2),
            ('Pisces',8),('Aries',12),('Taurus',2),('Gemini',2),('Cancer',2),('Leo',1),('Virgo',1)],
        5: [('Virgo',1),('Libra',9),('Scorpio',8),('Sagittarius',7),('Capricorn',1),('Aquarius',2),
            ('Pisces',8),('Aries',12),('Taurus',2),('Gemini',2),('Cancer',2),('Leo',1)],
    }
    jd = swe.julday(1990, 8, 15, 2.5)
    ok = 0
    for lagna, exp in expects.items():
        res = calc_chara_dasha(lagna, planet_signs_common, jd)
        got = [(m['sign'], m['years']) for m in res['mahadashas']]
        match = got == exp
        ok += match
        print(f"Lagna={SIGNS[lagna]} {res['direction']}: {'PASS 12/12' if match else 'FAIL'}")
        if not match:
            for g, e in zip(got, exp):
                print(' ', g, 'vs', e, '' if g == e else '<<<')
    print('金标准对照:', f'{ok}/2 盘通过')
    # 双主规则自测（v5.2）
    base = dict(planet_signs_common)
    cases = [
        ('一主在本座：Mars 在 Sc、Ketu 在 Cn → 数到 Ketu = 8',
         dict(base, Mars=7, Ketu=3, Rahu=9), 7, (8, 'Ketu', 'other_lord')),
        ('两主都在本座 → 12', dict(base, Saturn=10, Rahu=10, Ketu=4), 10, (12, 'Saturn', 'both_in_sign')),
        ('同座行星更多：Rahu 在 Le 伴 2 星、Saturn 独处 Pi → 数到 Rahu = 6',
         {'Sun': 4, 'Moon': 0, 'Mars': 1, 'Mercury': 4, 'Jupiter': 2, 'Venus': 5,
          'Saturn': 11, 'Rahu': 4, 'Ketu': 10}, 10, (6, 'Rahu', 'more_conjunct')),
        ('星座性质：两主都独处，Mars 在 Sg（变动）1 年、Ketu 在 Cp（启动）2 年 → 取 Mars = 1',
         {'Sun': 0, 'Moon': 1, 'Mars': 8, 'Mercury': 0, 'Jupiter': 2, 'Venus': 11,
          'Saturn': 4, 'Rahu': 3, 'Ketu': 9}, 7, (1, 'Mars', 'sign_nature')),
        ('性质相同取年数较大：Mars 在 Ge 7 年、Ketu 在 Pi 4 年（都变动、都独处）→ Mars = 7',
         {'Sun': 0, 'Moon': 1, 'Mars': 2, 'Mercury': 0, 'Jupiter': 3, 'Venus': 9,
          'Saturn': 4, 'Rahu': 5, 'Ketu': 11}, 7, (7, 'Mars', 'larger_years')),
    ]
    good = 0
    for name, ps, sign, exp in cases:
        r = md_years(sign, ps)
        hit = (r['years'], r['lord'], r['rule']) == exp
        good += hit
        print(('PASS ' if hit else 'FAIL ') + name, '' if hit else r)
    print('双主规则自测:', f'{good}/{len(cases)}')
