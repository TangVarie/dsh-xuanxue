/**
 * 玄学台 （Metaphysics studio） — browser half.
 *
 * A global main panel reached from the left sidebar. It is the console of an
 * organic four-skill practice, not a menu of four features:
 *
 *   - 提问台 takes the user's question (plus whatever facts they already know)
 *     and hands it to the `xuanxue` agent with an orchestration mandate: the
 *     agent decides the minimal sufficient set of systems, runs them
 *     independently, cross-fits the signals, lists conflicts and gaps, and
 *     only then reports or discusses.
 *   - 指定法门 keeps the professional path: one system with a full
 *     parameter card, validated before it reaches the session.
 *   - 档案 reads the case archive the agent writes under `xuanxue-cases/`
 *     (index.json + per-case case.json, including the cross-fit block) so a
 *     reading keeps its evidence, confidence, verification state and timing.
 *   - 体检 reads `xuanxue-skills/health.json` written by the bundled
 *     `health-check.ps1`, so a broken calculator is visible before a reading.
 *
 * Workspace files are read through `workspaceFiles`, which authorizes each
 * call with a Session identity; the panel uses any listed Session because
 * reads are not workspace-contained.
 */
window.__ModuleLoader__.load({
  id: 'dsh-xuanxue',
  factory(require) {
    const React = require('react');
    const h = React.createElement;

    const NS = 'xuanxue';
    const PANEL_ID = 'xuanxue';
    const PRESET_ID = 'xuanxue';
    const BUSY_MS = 1500;
    // 档案与体检都按会话工作区的相对路径读：换机器、换工作区都不用改这里。
    const HEALTH_PATH = 'xuanxue-skills/health.json';
    const CASES_INDEX = 'xuanxue-cases/index.json';
    const CASES_BASE = 'xuanxue-cases';

    const SYSTEMS = ['bazi', 'liuyao', 'ziwei', 'vedic'];
    const MODES = ['auto', 'bazi', 'liuyao', 'ziwei', 'vedic'];
    const SKILL_OF = { bazi: 'bazi-core', liuyao: 'liuyao-core', ziwei: 'ziwei-core', vedic: 'vedic' };
    const SYSTEM_ZH = { bazi: '八字', liuyao: '六爻', ziwei: '紫微斗数', vedic: '吠陀占星' };
    const FOCUS = ['career', 'wealth', 'marriage', 'family', 'health', 'timing', 'study'];
    const FOCUS_ZH = {
      career: '事业', wealth: '财运', marriage: '感情婚姻', family: '六亲家庭',
      health: '身体', timing: '应期 / 流年', study: '学业',
    };

    // ── pure helpers ────────────────────────────────────────────────────────

    function pad(n) {
      return n < 10 ? '0' + n : '' + n;
    }

    function todayLocal() {
      const d = new Date();
      return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
    }

    function nowLocal() {
      const d = new Date();
      return todayLocal() + 'T' + pad(d.getHours()) + ':' + pad(d.getMinutes());
    }

    function trimmed(value) {
      return typeof value === 'string' ? value.trim() : '';
    }

    function parseJson(text) {
      if (typeof text !== 'string' || text.length === 0) return null;
      try {
        return JSON.parse(text);
      } catch {
        return null;
      }
    }

    function hasLineValues(lines) {
      return Array.isArray(lines) && lines.length === 6 && lines.every((v) => typeof v === 'string' && v !== '');
    }

    const LINE_NAMES = { 9: '老阳', 7: '少阳', 8: '少阴', 6: '老阴' };

    /** The known facts, compacted for the auto request; absent fields stay absent. */
    function knownFacts(form) {
      const facts = {};
      if (trimmed(form.label)) facts.label = trimmed(form.label);
      if (form.date) {
        facts.calendar = form.calendar;
        if (form.calendar === 'lunar') facts.leapMonth = form.leapKnown ? form.leap : null;
        facts.date = form.date;
      }
      if (form.time) facts.time = form.time;
      if (form.date && form.time && form.uncertain) facts.uncertaintyMinutes = Number(form.uncertaintyMinutes) || 0;
      if (form.sex === 'male' || form.sex === 'female') facts.sex = form.sex;
      if (trimmed(form.place)) facts.place = trimmed(form.place);
      if (trimmed(form.lng)) facts.lng = Number(form.lng);
      if (trimmed(form.tz)) facts.tz = trimmed(form.tz);
      if (form.date && form.timeSource) {
        facts.timeSource = form.timeSource;
        facts.declaredMinutes = Number(form.declaredMin) || 0;
      }
      if (hasLineValues(form.lines)) {
        facts.lines = form.lines.join('');
        facts.lineNames = form.lines.map((v) => LINE_NAMES[v]).join(' → ');
        if (form.castTime) facts.castTime = form.castTime;
        facts.castMethod = form.castMethod;
      }
      if (form.focus.length) facts.focus = form.focus.slice();
      if (form.expect) facts.expect = form.expect;
      return facts;
    }

    /** Field-level validation; the auto mode is intentionally permissive. */
    function validate(mode, form) {
      const errors = [];
      const warnings = [];
      const rule = (invalid, field, message) => {
        if (invalid) errors.push({ field, message });
      };
      const warn = (invalid, field, message) => {
        if (invalid) warnings.push({ field, message });
      };

      if (mode === 'auto') {
        rule(trimmed(form.question) === '', 'question', 'questionRequired');
        const hasBirth = Boolean(form.date || form.time);
        if (hasBirth && !form.date) rule(true, 'date', 'dateRequired');
        if (hasBirth && !form.time) warn(true, 'time', 'timeMissing');
        if (form.date && !form.time) warn(true, 'time', 'timeMissing');
        if (hasBirth && form.sex !== 'male' && form.sex !== 'female') warn(true, 'sex', 'sexUnknownAuto');
        const partialLines = form.lines.some((v) => v !== '') && !hasLineValues(form.lines);
        warn(partialLines, 'lines', 'linesPartial');
        if (form.calendar === 'lunar' && form.date && !form.leapKnown) warn(true, 'leapKnown', 'leapUnknownAuto');
        return { errors, warnings };
      }

      if (mode === 'liuyao') {
        rule(trimmed(form.question) === '', 'question', 'questionRequired');
        rule(!form.castTime, 'castTime', 'castTimeRequired');
        rule(!hasLineValues(form.lines), 'lines', 'linesRequired');
        return { errors, warnings };
      }

      rule(!form.date, 'date', 'dateRequired');
      rule(!form.time, 'time', 'timeRequired');
      if (form.calendar === 'lunar') rule(!form.leapKnown, 'leapKnown', 'leapRequired');
      if (form.uncertain) {
        warn(Number(form.uncertaintyMinutes) < 0 || Number(form.uncertaintyMinutes) > 240, 'uncertaintyMinutes', 'uncertaintyRange');
      }
      if (mode === 'ziwei' || mode === 'bazi') {
        rule(form.sex !== 'male' && form.sex !== 'female', 'sex', 'sexRequired');
        warn(trimmed(form.place) === '', 'place', 'placeRecommended');
      }
      if (mode === 'vedic') {
        rule(trimmed(form.place) === '', 'place', 'placeRequired');
        rule(!form.timeSource, 'timeSource', 'timeSourceRequired');
        warn(form.calendar !== 'gregorian', 'calendar', 'vedicSolarOnly');
      }
      return { errors, warnings };
    }

    /** The full parameter card of an explicitly chosen system. */
    function parameterCard(mode, form) {
      const card = { system: mode };
      if (trimmed(form.label)) card.label = trimmed(form.label);
      if (mode === 'liuyao') {
        card.question = trimmed(form.question);
        card.castTime = form.castTime;
        card.castMethod = form.castMethod;
        card.lines = form.lines.join('');
        card.lineNames = form.lines.map((v) => LINE_NAMES[v]).join(' → ');
        if (form.focus.length) card.focus = form.focus.slice();
        return card;
      }
      if (mode === 'bazi' || mode === 'ziwei') {
        card.calendar = form.calendar;
        card.leapMonth = form.calendar === 'lunar' ? form.leap : false;
      }
      card.date = form.date;
      card.time = form.time;
      card.uncertaintyMinutes = form.uncertain ? Number(form.uncertaintyMinutes) || 0 : 0;
      card.sex = form.sex;
      card.place = trimmed(form.place);
      if (trimmed(form.lng)) card.lng = Number(form.lng);
      if (trimmed(form.tz)) card.tz = trimmed(form.tz);
      if (mode === 'vedic') {
        card.timeSource = form.timeSource;
        card.declaredMinutes = Number(form.declaredMin) || 0;
      }
      if (form.focus.length) card.focus = form.focus.slice();
      return card;
    }

    function cardBlock(card) {
      return ['【参数卡】', '```json', JSON.stringify(card, null, 2), '```'];
    }

    /**
     * Compile the request a launcher hands to the session.
     *  - auto: question + known facts + the orchestration/cross-fit mandate.
     *  - one system: the validated parameter card + that system's task.
     * Every request ends with the archive rule so the loop closes.
     */
    function buildPrompt(mode, form) {
      if (mode === 'auto') {
        const facts = knownFacts(form);
        const lines = [
          '请按「xuanxue-orchestra」的「问题驱动调度 + 交叉拟合」协议处理下面这件事。',
          '',
          '【我的问题】',
          trimmed(form.question),
          '',
          '【已知信息】（可能不全；缺的按协议问我，最多一次三项并说明为什么）',
          '```json',
          JSON.stringify(facts, null, 2),
          '```',
          '',
          '【要求】',
          '1. 先给一句话调度计划：问题分诊（对象 / 类型 / 时间范围 / 可用数据），说明选哪几门做最少充分集、为什么，以及为什么不需要其他门；数据不足时说明退路。',
          '2. 每门按各自的技能协议独立跑（排盘、装卦一律走脚本，证据与标签照各门规则），然后做交叉拟合：多门共同支持 / 单门支持 / 冲突与分辨条件 / 信息缺口。',
          '3. ' + (form.expect === 'discussion'
            ? '我想要的是一起讨论：请把可能的分支（2–4 个）都摆出来，说明各自的支持证据与「什么信息能区分它们」，再给你的倾向。'
            : '我想要结论：请结论先行，把证据矩阵放在后面；冲突照样并列，不要为了好看抹平。'),
          '4. 我只陈述了问题，不要让我自己挑法门；能先给的部分结果就先给，再列缺口。',
          '5. 结束前按落档协议写 xuanxue-cases/<id>/case.json（多门必须有 cross 块）并更新 index.json；有应期问我要不要设提醒。',
        ];
        return lines.join('\n');
      }

      const card = parameterCard(mode, form);
      const focusText = (card.focus || []).map((id) => FOCUS_ZH[id]).join('、');
      const lines = ['请按「xuanxue-orchestra」协议开课。', ''].concat(cardBlock(card));
      if (focusText) lines.push('', '【关注】' + focusText);

      if (mode === 'liuyao') {
        lines.push(
          '',
          '【任务】用 liuyao-core 断卦：先按参数卡核验装卦字段，再装卦、断卦、定应期。',
          '结论按六爻协议挂「卦理 —— 在我这件事里指什么」，置信用高/中/低；不要替我再摇卦。',
        );
      } else {
        lines.push(
          '',
          '【任务】用 ' + SKILL_OF[mode] + ' 开课：直接按参数卡开始，不要重复询问已给出的字段；缺关键字段先问我。',
          '排盘/计算一律走脚本；结论按该技能协议挂证据、置信标签与验证状态。',
          '若按 xuanxue-orchestra 判断「交叉能显著降低不确定性」，可以补跑其他门并在报告里注明为什么。',
        );
      }
      lines.push(
        '',
        '【落档】结束前按 xuanxue-orchestra 的落档协议写 xuanxue-cases/<id>/case.json 并更新 index.json；有应期问我要不要设提醒。',
        '',
        '【纪律】参数卡里带不确定性标记（时辰不确定、边界、时区、夏令时）时，按技能协议列候选或说明口径；不要把候选盘当既定盘。',
      );
      return lines.join('\n');
    }

    // ── dictionaries ────────────────────────────────────────────────────────

    const ZH = {
      panel: '玄学',
      title: '玄学台',
      subtitle: '把问题交给我：四门自己调度、交叉拟合，再给结论或一起讨论',
      steps: '陈述问题 → 智能体分诊并选最少充分集 → 独立跑各门 → 交叉拟合 → 落档可复盘',
      sectionIntake: '提问台',
      sectionIntakeNote: '只说问题就行；补充已知信息能让它少问你几轮。',
      sectionCases: '命例档案',
      sectionCasesNote: '智能体按 xuanxue-orchestra 协议写入 xuanxue-cases/，这里直接读档。',
      sectionSkills: '技能与体检',
      sectionSkillsNote: '四门 + 实践层随插件内置；体检读 xuanxue-skills/health.json。',
      mode: '方式',
      'mode.auto': '自动调度',
      'mode.bazi': '指定八字',
      'mode.liuyao': '指定六爻',
      'mode.ziwei': '指定紫微',
      'mode.vedic': '指定吠陀',
      'mode.note.auto': '陈述问题即可：它先判断这是「命」的问题（算命：本命/趋势/应期）还是「卜」的问题（卜卦：六爻，或吠陀提问盘），再自动选门与交叉。',
      'mode.note.bazi': '你指定只跑八字：按参数卡开课。',
      'mode.note.liuyao': '你指定只跑六爻：一事一断。',
      'mode.note.ziwei': '你指定只跑紫微：按参数卡开课。',
      'mode.note.vedic': '你指定只跑吠陀：本命走命盘；问一件具体的事时它会走 prashna 提问盘。',
      label: '命主 / 事项称呼',
      labelPlaceholder: '例如「陈某」「这次合作」，用于档案标题',
      question: '我的问题',
      questionPlaceholder: '把事情说清楚：发生了什么、想问什么、涉及谁、时间范围。越具体越好。',
      expect: '你希望',
      'expect.conclusion': '直接给结论',
      'expect.discussion': '一起讨论可能性',
      known: '补充已知信息（可选，能少问几轮）',
      knownHint: '有生辰就填日期时间（算命用）；已经摇过卦就填六爻（六爻卜卦用）。吠陀提问盘只需要发问这一刻的提问地点，不用出生信息。',
      cast: '已摇卦结果（可选）',
      calendar: '历法',
      gregorian: '公历',
      lunar: '农历',
      leap: '闰月',
      leapUnknown: '闰月未确认',
      date: '日期',
      time: '时间',
      uncertain: '出生时间不确定',
      minutes: '分钟',
      place: '出生地',
      placePlaceholder: '城市即可，海外补时区',
      lng: '经度（可选）',
      sex: '性别',
      male: '男',
      female: '女',
      unknown: '未知 / 不说',
      tz: '时区（可选）',
      tzPlaceholder: '例如 Asia/Shanghai',
      focus: '关注（可选）',
      castTime: '起卦时间',
      castMethod: '起卦方式',
      'method.coins': '铜钱',
      'method.chars': '字背',
      'method.numbers': '数字',
      'method.time': '时间卦',
      'lines': '六爻（自下而上）',
      'line.initial': '初爻',
      'line.second': '二爻',
      'line.third': '三爻',
      'line.fourth': '四爻',
      'line.fifth': '五爻',
      'line.top': '上爻',
      'line.9': '老阳',
      'line.7': '少阳',
      'line.8': '少阴',
      'line.6': '老阴',
      timeSource: '时间来源',
      'source.birth-certificate': '出生证',
      'source.hospital': '医院记录',
      'source.family': '家人记忆',
      'source.vague': '模糊记忆',
      'source.unknown': '未知',
      declaredMin: '声明误差',
      submit: '开始分析',
      opening: '正在开课…',
      preview: '查看将要填入的请求',
      hidePreview: '收起请求',
      valid: '校验通过',
      errorsTitle: '还需补齐：',
      warningsTitle: '提醒：',
      'error.questionRequired': '请先把问题写下来',
      'error.dateRequired': '给了日期就请补全',
      'error.timeRequired': '请填写出生时间（不确定就勾「出生时间不确定」并给范围）',
      'error.leapKnown': '农历请确认是否闰月',
      'error.sexRequired': '请给性别（紫微/八字排大运必需，不能默认）',
      'error.placeRequired': '吠陀排盘需要出生地（城市即可）',
      'error.timeSourceRequired': '请给时间来源，用来确定误差下限',
      'error.castTimeRequired': '请填写起卦时间',
      'error.linesRequired': '六爻没选完：请按实际摇卦结果逐爻选择',
      'warn.timeMissing': '只有日期没有时间：智能体会先问，或只能做降级判断',
      'warn.sexUnknownAuto': '没给性别：紫微与八字大运需要它，智能体会来问',
      'warn.linesPartial': '摇卦结果没选完：本次不会把六爻纳入',
      'warn.leapUnknownAuto': '农历闰月未确认：会按协议列候选，可能影响结论',
      'warn.placeRecommended': '没给出生地：真太阳时与经度修正无法做，结论会降一档',
      'warn.uncertaintyRange': '误差范围建议 0–240 分钟',
      'warn.vedicSolarOnly': '吠陀只收公历，请确认日期已换算',
      health: '运行态',
      'health.unknown': '未体检',
      'health.ok': '正常',
      'health.warn': '有提醒',
      'health.fail': '异常',
      'health.checkedAt': '体检于',
      'health.run': '体检四门',
      'health.runHint': '打开会话执行 health-check.ps1 并写回 health.json',
      iterate: '技能自检与迭代',
      iterateHint: '草案写到 xuanxue-skills/drafts，确认后才落回生效副本',
      casesEmpty: '还没有命例。起一次课，智能体会按协议落档；这里会显示结论、置信、交叉拟合与应期。',
      casesReload: '重新读取',
      casesUnreadable: '读不到档案（可能需要先有一个会话，或档案还没建立）。',
      caseOpen: '查看',
      caseClose: '收起',
      caseAsk: '追问',
      caseReview: '复盘应验',
      caseSession: '打开来源会话',
      caseNoSession: '无来源会话',
      caseParams: '参数卡',
      casePlan: '调度说明',
      caseAgree: '多门共同支持',
      caseConflicts: '冲突与分辨',
      caseGaps: '信息缺口',
      caseConclusions: '结论与依据',
      caseTiming: '应期',
      caseLog: '验证记录',
      caseNextCheck: '下次检查',
      caseUpdated: '更新于',
      caseMulti: '多门交叉',
      footer: '玄学结论供参考，不替代医疗、法律与投资判断。重要决定请自己复核。',
      'status.draft': '草稿',
      'status.read': '已解读',
      'status.verified': '已验证',
      'status.invalidated': '已失效',
      'verify.untested': '未验证',
      'verify.fitted': '已知事实拟合',
      'verify.blind-checked': '盲测核验',
      'verify.forward-checked': '前瞻检验',
      'conf.high': '高',
      'conf.medium': '中',
      'conf.low': '低',
      'conf.none': '未定',
      'system.bazi': '八字',
      'system.liuyao': '六爻',
      'system.ziwei': '紫微',
      'system.vedic': '吠陀',
      'strength.strong': '强',
      'strength.medium': '中',
      'focus.career': '事业',
      'focus.wealth': '财运',
      'focus.marriage': '感情婚姻',
      'focus.family': '六亲家庭',
      'focus.health': '身体',
      'focus.timing': '应期 / 流年',
      'focus.study': '学业',
      'prompt.iterate': '请对玄学台内置的四个技能做一次自检与迭代：加载插件内置的 bazi-core、liuyao-core、ziwei-core、vedic（都在插件的 skills/ 目录里，GitHub 安装后在 profile 的 node_modules/dsh-xuanxue/skills）。\n\n要求：\n1. 逐门读 SKILL.md 与 references 结构，检查内部一致性、脚本入口是否还能跑（有自检脚本就先跑自检）、与版本声明的冲突、明显缺口。\n2. 改进点按「必须改 / 建议改 / 可选」分级，每条给出位置（文件 + 章节）和改法。\n3. 先只写工作区草案：xuanxue-skills/drafts/<技能名>/，放修改后的文件与 CHANGE.md；先给我看。\n4. 我确认后，再把改动落进插件源码仓库的 skills/<技能名>/ 并发一版；不要直接改 node_modules 里那份，那个目录会被下次更新覆盖。\n5. 最后给我问题清单和优先级建议。',
      'prompt.health': '请执行 xuanxue-orchestra 的体检协议：加载 xuanxue-orchestra 技能，按它的体检一节运行技能目录下的 scripts/health-check.ps1，输出写到当前工作区的 xuanxue-skills/health.json，然后告诉我四门的状态与需要修的地方（紫微若报 EPERM，说明用预编译入口即可）。',
      'prompt.caseAsk': '请读取档案 xuanxue-cases/',
      'prompt.caseAsk2': '/case.json，按 xuanxue-orchestra 的读档追问协议继续这个命例：先复用参数卡与已结论，只补跑受影响的部分；若要补门或重新拟合，一并更新 cross 块；有新结论时更新 case.json 与 index.json。',
      'prompt.caseReview': '请读取档案 xuanxue-cases/',
      'prompt.caseReview2': '/case.json，按 xuanxue-orchestra 的复盘协议和我一起核对应期：逐条问哪些应验了，把结果写进 verificationLog 与 timing[].status，并按四档规则升级验证状态。',
    };

    const EN = {
      panel: 'Metaphysics',
      title: 'Metaphysics studio',
      subtitle: 'Hand it the question: the four systems route themselves, cross-fit, then report or discuss',
      steps: 'State the question → it triages and picks a minimal sufficient set → each system runs independently → cross-fit → archived for review',
      sectionIntake: 'Ask',
      sectionIntakeNote: 'Just state the question; known facts only save you a round of follow-ups.',
      sectionCases: 'Case archive',
      sectionCasesNote: 'The agent writes cases under xuanxue-cases/ via the orchestra protocol; this panel reads them.',
      sectionSkills: 'Skills and health',
      sectionSkillsNote: 'Four systems plus the practice layer ship with the plugin; health comes from xuanxue-skills/health.json.',
      mode: 'Mode',
      'mode.auto': 'Auto-orchestrate',
      'mode.bazi': 'Bazi only',
      'mode.liuyao': 'Liuyao only',
      'mode.ziwei': 'Ziwei only',
      'mode.vedic': 'Vedic only',
      'mode.note.auto': 'State the question: it first decides whether this is a fate question (natal reading, trends, timing) or a divination question (Liuyao, or a Vedic prashna chart), then picks and cross-fits the systems.',
      'mode.note.bazi': 'You pin it to Bazi: it runs from the parameter card.',
      'mode.note.liuyao': 'You pin it to one Liuyao casting.',
      'mode.note.ziwei': 'You pin it to Ziwei.',
      'mode.note.vedic': 'You pin it to Vedic: natal for life questions, a prashna chart for one specific event.',
      label: 'Subject label',
      labelPlaceholder: 'e.g. "Chen" or "this deal" — used for the case title',
      question: 'Your question',
      questionPlaceholder: 'What happened, what you ask, who it involves, the time range — the more concrete the better.',
      expect: 'You want',
      'expect.conclusion': 'a verdict',
      'expect.discussion': 'to explore possibilities',
      known: 'Known facts (optional; saves follow-ups)',
      knownHint: 'Birth data goes to the fate reading; cast lines go to the Liuyao divination. A Vedic prashna only needs the question moment and place — no birth data.',
      cast: 'Cast result (optional)',
      calendar: 'Calendar',
      gregorian: 'Solar',
      lunar: 'Lunar',
      leap: 'Leap month',
      leapUnknown: 'Leap month unconfirmed',
      date: 'Date',
      time: 'Time',
      uncertain: 'Birth time uncertain',
      minutes: 'min',
      place: 'Birthplace',
      placePlaceholder: 'City is enough; add the timezone for overseas births',
      lng: 'Longitude (optional)',
      sex: 'Sex',
      male: 'Male',
      female: 'Female',
      unknown: 'Unknown',
      tz: 'Timezone (optional)',
      tzPlaceholder: 'e.g. Asia/Shanghai',
      focus: 'Focus (optional)',
      castTime: 'Cast time',
      castMethod: 'Method',
      'method.coins': 'Coins',
      'method.chars': 'Characters',
      'method.numbers': 'Numbers',
      'method.time': 'Time',
      'lines': 'Six lines (bottom up)',
      'line.initial': 'Line 1',
      'line.second': 'Line 2',
      'line.third': 'Line 3',
      'line.fourth': 'Line 4',
      'line.fifth': 'Line 5',
      'line.top': 'Line 6',
      'line.9': 'Old yang',
      'line.7': 'Young yang',
      'line.8': 'Young yin',
      'line.6': 'Old yin',
      timeSource: 'Time source',
      'source.birth-certificate': 'Birth certificate',
      'source.hospital': 'Hospital record',
      'source.family': 'Family memory',
      'source.vague': 'Vague memory',
      'source.unknown': 'Unknown',
      declaredMin: 'Declared uncertainty',
      submit: 'Start the analysis',
      opening: 'Starting…',
      preview: 'Show the request that will be filled',
      hidePreview: 'Hide the request',
      valid: 'Validated',
      errorsTitle: 'Still missing:',
      warningsTitle: 'Heads up:',
      'error.questionRequired': 'Write the question down first',
      'error.dateRequired': 'A date needs its full value',
      'error.timeRequired': 'Fill the birth time',
      'error.leapKnown': 'Confirm the leap month for a lunar date',
      'error.sexRequired': 'Sex is required (Ziwei and Bazi luck cycles need it)',
      'error.placeRequired': 'Vedic casting needs the birthplace',
      'error.timeSourceRequired': 'Time source sets the uncertainty floor',
      'error.castTimeRequired': 'Fill the cast time',
      'error.linesRequired': 'All six lines are needed',
      'warn.timeMissing': 'Date without time: the agent will ask first or degrade the reading',
      'warn.sexUnknownAuto': 'No sex: Ziwei and Bazi luck cycles need it, the agent will ask',
      'warn.linesPartial': 'Cast lines incomplete: Liuyao will not be used this time',
      'warn.leapUnknownAuto': 'Lunar leap month unconfirmed: candidates will be listed',
      'warn.placeRecommended': 'No birthplace: true-solar-time and longitude correction are skipped',
      'warn.uncertaintyRange': 'Range should be 0–240 minutes',
      'warn.vedicSolarOnly': 'Vedic accepts the solar calendar only',
      health: 'Runtime',
      'health.unknown': 'Not checked',
      'health.ok': 'OK',
      'health.warn': 'Warnings',
      'health.fail': 'Failing',
      'health.checkedAt': 'Checked',
      'health.run': 'Check the four systems',
      'health.runHint': 'Opens a session that runs health-check.ps1 and writes health.json',
      iterate: 'Skill audit and iteration',
      iterateHint: 'Drafts go to xuanxue-skills/drafts; live copies change only after approval',
      casesEmpty: 'No cases yet. Start a reading and the agent archives it; conclusions, confidence, cross-fit and timing show up here.',
      casesReload: 'Reload',
      casesUnreadable: 'Archive unreadable (a session may be required, or it does not exist yet).',
      caseOpen: 'Open',
      caseClose: 'Close',
      caseAsk: 'Follow up',
      caseReview: 'Review outcomes',
      caseSession: 'Open source session',
      caseNoSession: 'No source session',
      caseParams: 'Parameter card',
      casePlan: 'Dispatch plan',
      caseAgree: 'Cross-supported',
      caseConflicts: 'Conflicts',
      caseGaps: 'Gaps',
      caseConclusions: 'Conclusions and evidence',
      caseTiming: 'Timing',
      caseLog: 'Verification log',
      caseNextCheck: 'Next check',
      caseUpdated: 'Updated',
      caseMulti: 'Cross-system',
      footer: 'Readings are for reflection, not a substitute for medical, legal, or investment advice.',
      'status.draft': 'Draft',
      'status.read': 'Read',
      'status.verified': 'Verified',
      'status.invalidated': 'Invalidated',
      'verify.untested': 'Untested',
      'verify.fitted': 'Fitted to known facts',
      'verify.blind-checked': 'Blind-checked',
      'verify.forward-checked': 'Forward-checked',
      'conf.high': 'High',
      'conf.medium': 'Medium',
      'conf.low': 'Low',
      'conf.none': 'None',
      'system.bazi': 'Bazi',
      'system.liuyao': 'Liuyao',
      'system.ziwei': 'Ziwei',
      'system.vedic': 'Vedic',
      'strength.strong': 'strong',
      'strength.medium': 'medium',
      'focus.career': 'Career',
      'focus.wealth': 'Wealth',
      'focus.marriage': 'Marriage',
      'focus.family': 'Family',
      'focus.health': 'Health',
      'focus.timing': 'Timing',
      'focus.study': 'Study',
      'prompt.iterate': 'Audit and iterate the four metaphysics skills bundled with the plugin (bazi-core, liuyao-core, ziwei-core and vedic live under the plugin\'s skills/ directory; a GitHub install puts them at node_modules/dsh-xuanxue/skills). Read each SKILL.md and its references layout, check consistency, runnable scripts and gaps; grade each improvement as must/should/optional with file and section; write drafts to xuanxue-skills/drafts/<skill>/ first, then apply them to the plugin source repository and release a version — do not edit the copy under node_modules, the next update overwrites it.',
      'prompt.health': 'Run the xuanxue-orchestra health protocol: load the xuanxue-orchestra skill and execute scripts/health-check.ps1 from its skill directory, writing output to xuanxue-skills/health.json in the current workspace, then report the four statuses and anything to fix (if Ziwei reports EPERM, use the prebuilt entry).',
      'prompt.caseAsk': 'Read the case at xuanxue-cases/',
      'prompt.caseAsk2': '/case.json and follow up under the xuanxue-orchestra archive protocol: reuse the parameter card and settled conclusions, rerun only what the follow-up touches, update the cross block when a system is added or refitted, and update case.json and index.json when a conclusion changes.',
      'prompt.caseReview': 'Read the case at xuanxue-cases/',
      'prompt.caseReview2': '/case.json and run the review protocol: check each timing item with me, record the result in verificationLog and timing[].status, and promote the verification state by the four-tier rule.',
    };

    // ── styles ──────────────────────────────────────────────────────────────

    const CSS = [
      '.xuanxue-page{box-sizing:border-box;display:flex;flex:1;min-height:0;overflow-y:auto;',
      'color:var(--dsw-alias-label-primary);background:var(--dsw-alias-bg-base);',
      'padding:28px 32px 64px;padding-left:max(32px,var(--dsh-frame-leading-clearance,0px));}',
      "html[data-platform='darwin'] .xuanxue-page{padding-top:calc(var(--dsh-frame-top-clearance,0px) + 28px);}",
      '.xuanxue-inner{width:100%;max-width:1060px;margin:0 auto;display:flex;flex-direction:column;gap:26px;}',
      '.xuanxue-head{display:flex;flex-direction:column;gap:8px;}',
      '.xuanxue-title{margin:0;font-size:24px;line-height:34px;font-weight:600;letter-spacing:.02em;}',
      '.xuanxue-sub{margin:0;font-size:13px;line-height:21px;color:var(--dsw-alias-label-secondary);}',
      '.xuanxue-steps{margin:0;font-size:12px;line-height:18px;color:var(--dsw-alias-label-secondary);}',
      '.xuanxue-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap;}',
      '.xuanxue-section{display:flex;flex-direction:column;gap:12px;}',
      '.xuanxue-section-head{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;}',
      '.xuanxue-h2{margin:0;font-size:16px;line-height:24px;font-weight:600;}',
      '.xuanxue-note{font-size:12px;line-height:18px;color:var(--dsw-alias-label-secondary);}',
      '.xuanxue-panel{display:flex;flex-direction:column;gap:14px;padding:18px;border-radius:14px;',
      'background:var(--dsw-alias-bg-layer-1);border:.5px solid var(--dsw-alias-border-l1);}',
      '.xuanxue-modes{display:flex;flex-wrap:wrap;gap:8px;}',
      '.xuanxue-mode{font:inherit;font-size:13px;line-height:18px;padding:6px 12px;border-radius:999px;cursor:pointer;',
      'border:.5px solid var(--dsw-alias-border-l2);background:transparent;color:var(--dsw-alias-label-primary);}',
      '.xuanxue-mode[data-active]{background:var(--dsw-alias-brand-primary);color:var(--dsw-alias-bg-base);border-color:transparent;}',
      '.xuanxue-mode-note{font-size:12px;color:var(--dsw-alias-label-secondary);}',
      '.xuanxue-form{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px 14px;}',
      '.xuanxue-form-wide{grid-column:1/-1;}',
      '.xuanxue-field{display:flex;flex-direction:column;gap:5px;min-width:0;font-size:12px;',
      'color:var(--dsw-alias-label-secondary);}',
      '.xuanxue-field-label{display:flex;align-items:center;gap:6px;}',
      '.xuanxue-input,.xuanxue-select{font:inherit;font-size:13px;line-height:18px;box-sizing:border-box;width:100%;',
      'padding:7px 10px;border-radius:8px;border:.5px solid var(--dsw-alias-border-l2);',
      'background:var(--dsw-alias-bg-base);color:var(--dsw-alias-label-primary);}',
      '.xuanxue-input:focus-visible,.xuanxue-select:focus-visible,.xuanxue-textarea:focus-visible,',
      '.xuanxue-btn:focus-visible,.xuanxue-mode:focus-visible,.xuanxue-chip:focus-visible{outline:2px solid var(--dsw-alias-brand-primary);outline-offset:2px;}',
      '.xuanxue-textarea{box-sizing:border-box;width:100%;min-height:96px;resize:vertical;padding:10px;border-radius:10px;',
      'border:.5px solid var(--dsw-alias-border-l2);background:var(--dsw-alias-bg-base);',
      'color:var(--dsw-alias-label-primary);font:inherit;font-size:13px;line-height:20px;}',
      '.xuanxue-chips{display:flex;flex-wrap:wrap;gap:8px;}',
      '.xuanxue-chip{font:inherit;font-size:12px;line-height:18px;padding:5px 10px;border-radius:999px;cursor:pointer;',
      'border:.5px solid var(--dsw-alias-border-l2);background:transparent;color:var(--dsw-alias-label-secondary);}',
      '.xuanxue-chip[data-on]{border-color:var(--dsw-alias-brand-primary);color:var(--dsw-alias-brand-primary);}',
      '.xuanxue-msg{font-size:12px;line-height:18px;}',
      '.xuanxue-msg[data-kind="error"]{color:var(--dsw-alias-state-error-primary);}',
      '.xuanxue-msg[data-kind="warn"]{color:var(--dsw-alias-state-warn-primary);}',
      '.xuanxue-msg[data-kind="ok"]{color:var(--dsw-alias-state-success-primary);}',
      '.xuanxue-btn{font:inherit;font-size:13px;line-height:18px;padding:7px 14px;border-radius:8px;cursor:pointer;',
      'border:.5px solid var(--dsw-alias-border-l2);background:transparent;color:var(--dsw-alias-brand-primary);}',
      '.xuanxue-btn:hover:not(:disabled){background:var(--dsw-alias-bg-layer-2);}',
      '.xuanxue-btn:disabled{opacity:.45;cursor:default;}',
      '.xuanxue-btn.primary{background:var(--dsw-alias-brand-primary);color:var(--dsw-alias-bg-base);border-color:transparent;}',
      '.xuanxue-btn.small{font-size:12px;padding:5px 10px;}',
      '.xuanxue-spacer{flex:1;}',
      '.xuanxue-preview{margin:0;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11px;',
      'line-height:17px;white-space:pre-wrap;word-break:break-word;max-height:260px;overflow:auto;',
      'padding:10px;border-radius:10px;background:var(--dsw-alias-bg-layer-2);',
      'color:var(--dsw-alias-label-secondary);}',
      '.xuanxue-health{display:flex;flex-wrap:wrap;align-items:center;gap:8px;}',
      '.xuanxue-chip[data-status="ok"]{color:var(--dsw-alias-state-success-primary);border-color:var(--dsw-alias-state-success-primary);}',
      '.xuanxue-chip[data-status="warn"]{color:var(--dsw-alias-state-warn-primary);border-color:var(--dsw-alias-state-warn-primary);}',
      '.xuanxue-chip[data-status="fail"]{color:var(--dsw-alias-state-error-primary);border-color:var(--dsw-alias-state-error-primary);}',
      '.xuanxue-cases{display:flex;flex-direction:column;gap:10px;}',
      '.xuanxue-case{display:flex;flex-direction:column;gap:8px;padding:14px 16px;border-radius:12px;',
      'background:var(--dsw-alias-bg-layer-1);border:.5px solid var(--dsw-alias-border-l1);}',
      '.xuanxue-case[data-open]{border-color:var(--dsw-alias-brand-primary);}',
      '.xuanxue-case-top{display:flex;align-items:center;gap:10px;flex-wrap:wrap;}',
      '.xuanxue-case-title{font-size:14px;line-height:20px;font-weight:600;}',
      '.xuanxue-tag{font-size:11px;line-height:16px;padding:2px 8px;border-radius:999px;',
      'border:.5px solid var(--dsw-alias-border-l1);color:var(--dsw-alias-label-secondary);white-space:nowrap;}',
      '.xuanxue-case-summary{margin:0;font-size:13px;line-height:20px;color:var(--dsw-alias-label-secondary);}',
      '.xuanxue-case-meta{display:flex;gap:12px;flex-wrap:wrap;font-size:12px;color:var(--dsw-alias-label-secondary);}',
      '.xuanxue-detail{display:flex;flex-direction:column;gap:10px;padding:12px;border-radius:10px;',
      'background:var(--dsw-alias-bg-layer-2);font-size:12px;line-height:19px;}',
      '.xuanxue-detail h4{margin:0;font-size:12px;line-height:18px;font-weight:600;color:var(--dsw-alias-label-primary);}',
      '.xuanxue-conclusion{padding:8px 10px;border-left:2px solid var(--dsw-alias-brand-primary);',
      'background:var(--dsw-alias-bg-layer-1);border-radius:0 8px 8px 0;}',
      '.xuanxue-conclusion p{margin:0 0 4px;}',
      '.xuanxue-conclusion .meta{color:var(--dsw-alias-label-secondary);font-size:11px;}',
      '.xuanxue-crossrow{padding:6px 0;border-bottom:.5px dashed var(--dsw-alias-border-l1);}',
      '.xuanxue-crossrow:last-child{border-bottom:none;}',
      '.xuanxue-footer{margin:0;font-size:12px;line-height:18px;color:var(--dsw-alias-label-secondary);}',
      '@media (max-width:640px){.xuanxue-page{padding:18px 16px 40px;}',
      "html[data-platform='darwin'] .xuanxue-page{padding-top:calc(var(--dsh-frame-top-clearance,0px) + 18px);}}",
    ].join('');

    // ── components ──────────────────────────────────────────────────────────

    function XuanxueIcon(props) {
      const size = props && typeof props.size === 'number' ? props.size : 16;
      return h('svg', { viewBox: '0 0 100 100', width: size, height: size, 'aria-hidden': true, focusable: false, style: { display: 'block' } },
        h('circle', { cx: 50, cy: 50, r: 44, fill: 'currentColor', fillOpacity: 0.22 }),
        h('path', { d: 'M50 6a44 44 0 0 1 0 88 22 22 0 0 0 0-44 22 22 0 0 1 0-44Z', fill: 'currentColor' }),
        h('circle', { cx: 50, cy: 72, r: 6.5, fill: 'currentColor' }));
    }

    function Field(props) {
      return h('label', { className: 'xuanxue-field' + (props.wide ? ' xuanxue-form-wide' : '') },
        h('span', { className: 'xuanxue-field-label' }, props.label),
        props.children);
    }

    function Notice(props) {
      return h('p', { className: 'xuanxue-msg', 'data-kind': props.kind }, props.children);
    }

    function HealthStrip(props) {
      const { tr, health, onCheck, busy } = props;
      const skills = (health && health.skills) || {};
      const keys = { bazi: 'bazi-core', liuyao: 'liuyao-core', ziwei: 'ziwei-core', vedic: 'vedic' };
      const chips = SYSTEMS.map((id) => {
        const entry = skills[keys[id]];
        const status = entry && entry.status ? entry.status : 'unknown';
        return h('span', { key: id, className: 'xuanxue-chip', 'data-status': status, title: tr('health.' + status) + (entry && entry.detail ? ' · ' + entry.detail : '') },
          tr('system.' + id) + ' ' + tr('health.' + status));
      });
      const checked = health && health.checkedAt ? ' · ' + tr('health.checkedAt') + ' ' + String(health.checkedAt).slice(0, 16).replace('T', ' ') : '';
      return h('div', { className: 'xuanxue-row' },
        h('span', { className: 'xuanxue-note' }, tr('health') + checked),
        h('div', { className: 'xuanxue-health' }, chips),
        h('span', { className: 'xuanxue-spacer' }),
        h('button', { type: 'button', className: 'xuanxue-btn small', disabled: busy, onClick: onCheck, title: tr('health.runHint') }, busy ? tr('opening') : tr('health.run')));
    }

    /** The six line selectors. */
    function LinePicker(props) {
      const { tr, lines, onChange } = props;
      return h(Field, { label: tr('lines'), wide: true },
        h('div', { className: 'xuanxue-form', style: { padding: 0 } },
          ['initial', 'second', 'third', 'fourth', 'fifth', 'top'].map((pos, index) =>
            h(Field, { key: pos, label: tr('line.' + pos) },
              h('select', {
                className: 'xuanxue-select',
                value: lines[index] || '',
                onChange: (e) => {
                  const next = lines.slice();
                  next[index] = e.target.value;
                  onChange(next);
                },
              },
                h('option', { value: '' }, '—'),
                ['9', '7', '8', '6'].map((v) => h('option', { key: v, value: v }, tr('line.' + v))))))));
    }

    /** Birth fields shared by the auto mode and the pinned birth systems. */
    function BirthFields(props) {
      const { tr, form, update, withCalendar, withVedic } = props;
      const fields = [];
      if (withCalendar) {
        fields.push(
          h(Field, { key: 'calendar', label: tr('calendar') },
            h('select', { className: 'xuanxue-select', value: form.calendar, onChange: (e) => update({ calendar: e.target.value }) },
              h('option', { value: 'gregorian' }, tr('gregorian')),
              h('option', { value: 'lunar' }, tr('lunar')))),
        );
        if (form.calendar === 'lunar') {
          fields.push(
            h(Field, { key: 'leap', label: tr('leap') },
              h('select', {
                className: 'xuanxue-select',
                value: form.leapKnown ? (form.leap ? 'yes' : 'no') : 'unknown',
                onChange: (e) => {
                  const v = e.target.value;
                  update({ leapKnown: v !== 'unknown', leap: v === 'yes' });
                },
              },
                h('option', { value: 'unknown' }, tr('leapUnknown')),
                h('option', { value: 'no' }, '—'),
                h('option', { value: 'yes' }, '✓'))),
          );
        }
      }
      fields.push(
        h(Field, { key: 'date', label: tr('date') },
          h('input', { className: 'xuanxue-input', type: 'date', value: form.date, onChange: (e) => update({ date: e.target.value }) })),
        h(Field, { key: 'time', label: tr('time') },
          h('input', { className: 'xuanxue-input', type: 'time', value: form.time, onChange: (e) => update({ time: e.target.value }) })),
        h(Field, { key: 'uncertain', label: tr('uncertain') },
          h('select', {
            className: 'xuanxue-select',
            value: form.uncertain ? String(form.uncertaintyMinutes) : '0',
            onChange: (e) => {
              const v = e.target.value;
              update({ uncertain: v !== '0', uncertaintyMinutes: Number(v) });
            },
          },
            h('option', { value: '0' }, '—'),
            [15, 30, 60, 120].map((m) => h('option', { key: m, value: String(m) }, '±' + m + ' ' + tr('minutes'))))),
        h(Field, { key: 'sex', label: tr('sex') },
          h('select', { className: 'xuanxue-select', value: form.sex, onChange: (e) => update({ sex: e.target.value }) },
            h('option', { value: 'unknown' }, tr('unknown')),
            h('option', { value: 'male' }, tr('male')),
            h('option', { value: 'female' }, tr('female')))),
        h(Field, { key: 'place', label: tr('place') },
          h('input', { className: 'xuanxue-input', type: 'text', value: form.place, placeholder: tr('placePlaceholder'), onChange: (e) => update({ place: e.target.value }) })),
        h(Field, { key: 'lng', label: tr('lng') },
          h('input', { className: 'xuanxue-input', type: 'text', value: form.lng, placeholder: '121.47', onChange: (e) => update({ lng: e.target.value }) })),
        h(Field, { key: 'tz', label: tr('tz') },
          h('input', { className: 'xuanxue-input', type: 'text', value: form.tz, placeholder: tr('tzPlaceholder'), onChange: (e) => update({ tz: e.target.value }) })),
      );
      if (withVedic) {
        fields.push(
          h(Field, { key: 'timeSource', label: tr('timeSource') },
            h('select', { className: 'xuanxue-select', value: form.timeSource, onChange: (e) => update({ timeSource: e.target.value }) },
              ['birth-certificate', 'hospital', 'family', 'vague', 'unknown'].map((id) => h('option', { key: id, value: id }, tr('source.' + id))))),
          h(Field, { key: 'declaredMin', label: tr('declaredMin') },
            h('select', { className: 'xuanxue-select', value: String(form.declaredMin), onChange: (e) => update({ declaredMin: Number(e.target.value) }) },
              [0, 5, 15, 30, 60].map((m) => h('option', { key: m, value: String(m) }, m + ' ' + tr('minutes'))))),
        );
      }
      return fields;
    }

    function FocusChips(props) {
      const { tr, form, update } = props;
      return h(Field, { label: tr('focus'), wide: true },
        h('div', { className: 'xuanxue-chips' },
          FOCUS.map((id) =>
            h('button', {
              key: id,
              type: 'button',
              className: 'xuanxue-chip',
              'data-on': form.focus.includes(id) ? 'yes' : undefined,
              onClick: () => update({ focus: form.focus.includes(id) ? form.focus.filter((x) => x !== id) : form.focus.concat(id) }),
            }, tr('focus.' + id)))));
    }

    function Intake(props) {
      const { tr, form, update, mode, setMode, errors, warnings, busy, submit, showPreview, setShowPreview, prompt, showKnown, setShowKnown, showCast, setShowCast } = props;
      const auto = mode === 'auto';
      const isSix = mode === 'liuyao';
      const birthModes = mode === 'bazi' || mode === 'ziwei' || mode === 'vedic';

      const fields = [
        h(Field, { key: 'mode', label: tr('mode') },
          h('select', { className: 'xuanxue-select', value: mode, onChange: (e) => setMode(e.target.value) },
            MODES.map((id) => h('option', { key: id, value: id }, tr('mode.' + id))))),
      ];

      if (auto) {
        fields.push(
          h(Field, { key: 'question', label: tr('question'), wide: true },
            h('textarea', { className: 'xuanxue-textarea', value: form.question, placeholder: tr('questionPlaceholder'), onChange: (e) => update({ question: e.target.value }) })),
          h(Field, { key: 'expect', label: tr('expect') },
            h('select', { className: 'xuanxue-select', value: form.expect, onChange: (e) => update({ expect: e.target.value }) },
              h('option', { value: 'conclusion' }, tr('expect.conclusion')),
              h('option', { value: 'discussion' }, tr('expect.discussion')))),
          h(Field, { key: 'label', label: tr('label') },
            h('input', { className: 'xuanxue-input', type: 'text', value: form.label, placeholder: tr('labelPlaceholder'), onChange: (e) => update({ label: e.target.value }) })),
        );
      }

      if (isSix || birthModes) {
        fields.push(h(Field, { key: 'question6', label: tr('question'), wide: true },
          h('textarea', { className: 'xuanxue-textarea', value: form.question, placeholder: tr('questionPlaceholder'), onChange: (e) => update({ question: e.target.value }) })));
      }

      if (birthModes) {
        fields.push(...BirthFields({ tr, form, update, withCalendar: mode !== 'vedic', withVedic: mode === 'vedic' }));
        if (mode === 'bazi' || mode === 'ziwei') {
          fields.push(h(Field, { key: 'label2', label: tr('label') },
            h('input', { className: 'xuanxue-input', type: 'text', value: form.label, placeholder: tr('labelPlaceholder'), onChange: (e) => update({ label: e.target.value }) })));
        }
        fields.push(h(FocusChips, { key: 'focus', tr, form, update }));
      }

      if (isSix) {
        fields.push(
          h(Field, { key: 'castTime', label: tr('castTime') },
            h('input', { className: 'xuanxue-input', type: 'datetime-local', value: form.castTime, onChange: (e) => update({ castTime: e.target.value }) })),
          h(Field, { key: 'castMethod', label: tr('castMethod') },
            h('select', { className: 'xuanxue-select', value: form.castMethod, onChange: (e) => update({ castMethod: e.target.value }) },
              ['coins', 'chars', 'numbers', 'time'].map((id) => h('option', { key: id, value: id }, tr('method.' + id))))),
          h(LinePicker, { key: 'lines', tr, lines: form.lines, onChange: (lines) => update({ lines }) }),
        );
      }

      if (auto) {
        fields.push(
          h('div', { key: 'known-toggle', className: 'xuanxue-form-wide' },
            h('button', { type: 'button', className: 'xuanxue-btn small', onClick: () => setShowKnown(!showKnown) },
              (showKnown ? '▾ ' : '▸ ') + tr('known'))),
          h('p', { key: 'known-hint', className: 'xuanxue-note xuanxue-form-wide' }, tr('knownHint')),
        );
        if (showKnown) {
          fields.push(...BirthFields({ tr, form, update, withCalendar: true, withVedic: true }));
          fields.push(
            h('div', { key: 'cast-toggle', className: 'xuanxue-form-wide' },
              h('button', { type: 'button', className: 'xuanxue-btn small', onClick: () => setShowCast(!showCast) },
                (showCast ? '▾ ' : '▸ ') + tr('cast'))),
          );
          if (showCast) {
            fields.push(
              h(Field, { key: 'castTime2', label: tr('castTime') },
                h('input', { className: 'xuanxue-input', type: 'datetime-local', value: form.castTime, onChange: (e) => update({ castTime: e.target.value }) })),
              h(Field, { key: 'castMethod2', label: tr('castMethod') },
                h('select', { className: 'xuanxue-select', value: form.castMethod, onChange: (e) => update({ castMethod: e.target.value }) },
                  ['coins', 'chars', 'numbers', 'time'].map((id) => h('option', { key: id, value: id }, tr('method.' + id))))),
              h(LinePicker, { key: 'lines2', tr, lines: form.lines, onChange: (lines) => update({ lines }) }),
            );
          }
          fields.push(h(FocusChips, { key: 'focus-auto', tr, form, update }));
        }
      }

      return h('section', { className: 'xuanxue-section', 'aria-labelledby': 'xuanxue-intake' },
        h('div', { className: 'xuanxue-section-head' },
          h('h2', { className: 'xuanxue-h2', id: 'xuanxue-intake' }, tr('sectionIntake')),
          h('span', { className: 'xuanxue-note' }, tr('sectionIntakeNote'))),
        h('div', { className: 'xuanxue-panel' },
          h('div', { className: 'xuanxue-modes' },
            MODES.map((id) => h('button', {
              key: id,
              type: 'button',
              className: 'xuanxue-mode',
              'data-active': mode === id ? 'yes' : undefined,
              onClick: () => setMode(id),
            }, tr('mode.' + id)))),
          h('div', { className: 'xuanxue-mode-note' }, tr('mode.note.' + mode)),
          h('div', { className: 'xuanxue-form' }, fields),
          errors.length > 0 && h('div', null,
            h(Notice, { kind: 'error' }, tr('errorsTitle')),
            errors.map((item, i) => h(Notice, { key: i, kind: 'error' }, '· ' + tr('error.' + item.message)))),
          warnings.length > 0 && h('div', null,
            h(Notice, { kind: 'warn' }, tr('warningsTitle')),
            warnings.map((item, i) => h(Notice, { key: i, kind: 'warn' }, '· ' + tr('warn.' + item.message)))),
          errors.length === 0 && h(Notice, { kind: 'ok' }, tr('valid')),
          h('div', { className: 'xuanxue-row' },
            h('button', { type: 'button', className: 'xuanxue-btn', onClick: () => setShowPreview(!showPreview) },
              showPreview ? tr('hidePreview') : tr('preview')),
            h('span', { className: 'xuanxue-spacer' }),
            h('button', { type: 'button', className: 'xuanxue-btn primary', disabled: busy || errors.length > 0, onClick: submit },
              busy ? tr('opening') : tr('submit'))),
          showPreview && h('pre', { className: 'xuanxue-preview' }, prompt)));
    }

    function CrossBlock(props) {
      const { tr, cross } = props;
      if (!cross || typeof cross !== 'object') return null;
      const agree = Array.isArray(cross.agree) ? cross.agree : [];
      const conflicts = Array.isArray(cross.conflicts) ? cross.conflicts : [];
      const gaps = Array.isArray(cross.gaps) ? cross.gaps : [];
      return h(React.Fragment, null,
        cross.plan && h(React.Fragment, null,
          h('h4', null, tr('casePlan')),
          h('div', { className: 'xuanxue-crossrow' }, String(cross.plan))),
        agree.length > 0 && h(React.Fragment, null,
          h('h4', null, tr('caseAgree')),
          agree.map((item, i) => h('div', { key: i, className: 'xuanxue-crossrow' },
            '· ' + (item.statement || ''),
            h('span', { className: 'meta' }, '  ' + (Array.isArray(item.systems) ? item.systems.map((s) => tr('system.' + s)).join(' × ') : '') + (item.strength ? ' · ' + tr('strength.' + item.strength) : ''))))),
        conflicts.length > 0 && h(React.Fragment, null,
          h('h4', null, tr('caseConflicts')),
          conflicts.map((item, i) => h('div', { key: i, className: 'xuanxue-crossrow' },
            h('div', null, '· ' + (item.topic || '')),
            (Array.isArray(item.readings) ? item.readings : []).map((r, j) => h('div', { key: j, className: 'meta' },
              '　' + tr('system.' + r.system) + '：' + (r.text || ''))),
            item.condition && h('div', { className: 'meta' }, '　分辨：' + item.condition)))),
        gaps.length > 0 && h(React.Fragment, null,
          h('h4', null, tr('caseGaps')),
          gaps.map((item, i) => h('div', { key: i, className: 'xuanxue-crossrow' },
            '· ' + (item.missing || '') + (item.why ? ' —— ' + item.why : '')))));
    }

    function CaseCard(props) {
      const { tr, item, open, detail, onToggle, onAsk, onReview, onOpenSession } = props;
      const systems = Array.isArray(item.systems) ? item.systems : [];
      return h('div', { className: 'xuanxue-case', 'data-open': open ? 'yes' : undefined },
        h('div', { className: 'xuanxue-case-top' },
          h('span', { className: 'xuanxue-case-title' }, item.title || item.id || '—'),
          systems.map((s) => h('span', { key: s, className: 'xuanxue-tag' }, tr('system.' + s))),
          systems.length > 1 && h('span', { className: 'xuanxue-tag' }, tr('caseMulti')),
          h('span', { className: 'xuanxue-tag' }, tr('status.' + (item.status || 'draft'))),
          h('span', { className: 'xuanxue-tag' }, tr('verify.' + (item.verification || 'untested'))),
          item.confidence && item.confidence !== 'none' && h('span', { className: 'xuanxue-tag' }, tr('conf.' + item.confidence)),
          h('span', { className: 'xuanxue-spacer' }),
          h('button', { type: 'button', className: 'xuanxue-btn small', onClick: onToggle }, open ? tr('caseClose') : tr('caseOpen'))),
        item.summary && h('p', { className: 'xuanxue-case-summary' }, item.summary),
        h('div', { className: 'xuanxue-case-meta' },
          item.nextCheck && h('span', null, tr('caseNextCheck') + '：' + item.nextCheck),
          item.updatedAt && h('span', null, tr('caseUpdated') + ' ' + String(item.updatedAt).slice(0, 10)),
          h('span', null, item.id || '')),
        open && h('div', { className: 'xuanxue-detail' },
          detail === null
            ? h(Notice, { kind: 'warn' }, '…')
            : h(React.Fragment, null,
              h(CrossBlock, { tr, cross: detail.cross }),
              detail.params && detail.params.card && h(React.Fragment, null,
                h('h4', null, tr('caseParams')),
                h('pre', { className: 'xuanxue-preview' }, String(detail.params.card))),
              Array.isArray(detail.conclusions) && detail.conclusions.length > 0 && h(React.Fragment, null,
                h('h4', null, tr('caseConclusions')),
                detail.conclusions.slice(0, 16).map((c, i) => h('div', { key: i, className: 'xuanxue-conclusion' },
                  h('p', null, c.text || ''),
                  h('p', { className: 'meta' }, [c.system ? tr('system.' + c.system) : '', c.tag || '', c.verification || '', c.window || ''].filter(Boolean).join(' · ')),
                  c.evidence && h('p', { className: 'meta' }, c.evidence)))),
              Array.isArray(detail.timing) && detail.timing.length > 0 && h(React.Fragment, null,
                h('h4', null, tr('caseTiming')),
                detail.timing.map((t, i) => h('div', { key: i }, '· ' + (t.window || '') + ' ' + (t.event || '') + ' [' + (t.status || '') + ']'))),
              Array.isArray(detail.verificationLog) && detail.verificationLog.length > 0 && h(React.Fragment, null,
                h('h4', null, tr('caseLog')),
                detail.verificationLog.map((v, i) => h('div', { key: i }, '· ' + String(v.at || '').slice(0, 10) + ' ' + (v.result || '') + ' ' + (v.note || ''))))),
          h('div', { className: 'xuanxue-row' },
            h('button', { type: 'button', className: 'xuanxue-btn small', onClick: onAsk }, tr('caseAsk')),
            h('button', { type: 'button', className: 'xuanxue-btn small', onClick: onReview }, tr('caseReview')),
            item.sessionId
              ? h('button', { type: 'button', className: 'xuanxue-btn small', onClick: onOpenSession }, tr('caseSession'))
              : h('span', { className: 'xuanxue-note' }, tr('caseNoSession')))));
    }

    // ── the panel ───────────────────────────────────────────────────────────

    const EMPTY_FORM = {
      label: '',
      expect: 'conclusion',
      calendar: 'gregorian',
      leap: false,
      leapKnown: false,
      date: '',
      time: '',
      uncertain: false,
      uncertaintyMinutes: 15,
      place: '',
      lng: '',
      tz: '',
      sex: 'unknown',
      focus: [],
      question: '',
      castTime: nowLocal(),
      castMethod: 'coins',
      lines: ['', '', '', '', '', ''],
      timeSource: 'birth-certificate',
      declaredMin: 15,
    };

    function Studio(props) {
      const { tr, launch, readText, openSession, useSessions } = props;
      const [mode, setMode] = React.useState('auto');
      const [form, setForm] = React.useState(EMPTY_FORM);
      const [busy, setBusy] = React.useState(false);
      const [showPreview, setShowPreview] = React.useState(false);
      const [showKnown, setShowKnown] = React.useState(false);
      const [showCast, setShowCast] = React.useState(false);
      const [health, setHealth] = React.useState(null);
      const [healthState, setHealthState] = React.useState('idle');
      const [index, setIndex] = React.useState(null);
      const [casesState, setCasesState] = React.useState('idle');
      const [openCase, setOpenCase] = React.useState(null);
      const [detail, setDetail] = React.useState(null);
      const sessionIds = useSessions((state) => state.ids);
      const scopeId = Array.isArray(sessionIds) && sessionIds.length > 0 ? sessionIds[0] : undefined;

      const update = (patch) => setForm((current) => Object.assign({}, current, patch));
      const check = validate(mode, form);
      const request = buildPrompt(mode, form);

      React.useEffect(() => {
        if (!busy) return undefined;
        const id = setTimeout(() => setBusy(false), BUSY_MS);
        return () => clearTimeout(id);
      }, [busy]);

      const reloadHealth = React.useCallback(() => {
        if (!scopeId) return;
        const controller = new AbortController();
        setHealthState('loading');
        readText(scopeId, HEALTH_PATH, controller.signal).then((text) => {
          const parsed = parseJson(text);
          setHealth(parsed && typeof parsed === 'object' ? parsed : null);
          setHealthState(parsed ? 'ready' : 'missing');
        });
        return () => controller.abort();
      }, [scopeId, readText]);

      const reloadCases = React.useCallback(() => {
        if (!scopeId) return;
        const controller = new AbortController();
        setCasesState('loading');
        readText(scopeId, CASES_INDEX, controller.signal).then((text) => {
          const parsed = parseJson(text);
          const list = parsed && Array.isArray(parsed.cases) ? parsed.cases : [];
          setIndex(list);
          setCasesState(parsed ? 'ready' : 'missing');
        });
        return () => controller.abort();
      }, [scopeId, readText]);

      React.useEffect(() => reloadHealth(), [reloadHealth]);
      React.useEffect(() => reloadCases(), [reloadCases]);

      const openDetail = (item) => {
        if (openCase === item.id) {
          setOpenCase(null);
          setDetail(null);
          return;
        }
        setOpenCase(item.id);
        setDetail(null);
        if (!scopeId) return;
        const controller = new AbortController();
        readText(scopeId, CASES_BASE + '/' + item.id + '/case.json', controller.signal).then((text) => {
          setDetail(parseJson(text) || {});
        });
      };

      const fire = (prompt) => {
        if (busy) return;
        setBusy(true);
        launch(prompt);
      };

      const submit = () => {
        if (check.errors.length > 0) return;
        fire(request);
      };

      return h('div', { className: 'xuanxue-page' },
        h('div', { className: 'xuanxue-inner' },
          h('header', { className: 'xuanxue-head' },
            h('h1', { className: 'xuanxue-title' }, tr('title')),
            h('p', { className: 'xuanxue-sub' }, tr('subtitle')),
            h('p', { className: 'xuanxue-steps' }, tr('steps')),
            h(HealthStrip, { tr, health, busy, onCheck: () => fire(tr('prompt.health')) })),
          h(Intake, {
            tr, form, update, mode, setMode,
            errors: check.errors, warnings: check.warnings,
            busy, submit, preview: showPreview, setPreview: setShowPreview, showPreview,
            prompt: request,
            showKnown, setShowKnown, showCast, setShowCast,
          }),
          h('section', { className: 'xuanxue-section', 'aria-labelledby': 'xuanxue-cases' },
            h('div', { className: 'xuanxue-section-head' },
              h('h2', { className: 'xuanxue-h2', id: 'xuanxue-cases' }, tr('sectionCases')),
              h('span', { className: 'xuanxue-note' }, tr('sectionCasesNote')),
              h('span', { className: 'xuanxue-spacer' }),
              h('button', { type: 'button', className: 'xuanxue-btn small', onClick: reloadCases }, tr('casesReload'))),
            !scopeId && h(Notice, { kind: 'warn' }, tr('casesUnreadable')),
            scopeId && casesState === 'missing' && h(Notice, { kind: 'warn' }, tr('casesUnreadable')),
            scopeId && casesState === 'ready' && index !== null && index.length === 0 && h(Notice, { kind: 'warn' }, tr('casesEmpty')),
            scopeId && index !== null && index.length > 0 && h('div', { className: 'xuanxue-cases' },
              index.slice()
                .sort((a, b) => String((b && b.updatedAt) || '').localeCompare(String((a && a.updatedAt) || '')))
                .map((item) => h(CaseCard, {
                  key: item.id,
                  tr,
                  item,
                  open: openCase === item.id,
                  detail: openCase === item.id ? detail : null,
                  onToggle: () => openDetail(item),
                  onAsk: () => fire(tr('prompt.caseAsk') + item.id + tr('prompt.caseAsk2')),
                  onReview: () => fire(tr('prompt.caseReview') + item.id + tr('prompt.caseReview2')),
                  onOpenSession: () => { if (item.sessionId) openSession(item.sessionId); },
                })))),
          h('section', { className: 'xuanxue-section', 'aria-labelledby': 'xuanxue-skills' },
            h('div', { className: 'xuanxue-section-head' },
              h('h2', { className: 'xuanxue-h2', id: 'xuanxue-skills' }, tr('sectionSkills')),
              h('span', { className: 'xuanxue-note' }, tr('sectionSkillsNote'))),
            h('div', { className: 'xuanxue-panel' },
              h('div', { className: 'xuanxue-chips' },
                SYSTEMS.map((id) => h('span', { key: id, className: 'xuanxue-chip' }, tr('system.' + id) + ' · ' + SKILL_OF[id])),
                h('span', { className: 'xuanxue-chip' }, '编排 · xuanxue-orchestra')),
              h('p', { className: 'xuanxue-note' }, tr('iterateHint')),
              h('div', null,
                h('button', { type: 'button', className: 'xuanxue-btn', disabled: busy, onClick: () => fire(tr('prompt.iterate')) },
                  busy ? tr('opening') : tr('iterate'))))),
          h('p', { className: 'xuanxue-footer' }, tr('footer')),
        ),
      );
    }

    return {
      inject: ['slots', 'locale', 'uiWorkspace', 'remote', 'remote.workspaceFiles'],
      apply(ctx) {
        ctx.effect(() => ctx.locale.register(NS, 'zh', ZH), 'xuanxue: zh dictionary');
        ctx.effect(() => ctx.locale.register(NS, 'en', EN), 'xuanxue: en dictionary');
        const tr = ctx.locale.bind(NS);

        ctx.effect(() => {
          const style = document.createElement('style');
          style.setAttribute('data-dsh-plugin', NS);
          style.textContent = CSS;
          document.head.appendChild(style);
          return () => {
            style.remove();
          };
        }, 'xuanxue: styles');

        /** Read one workspace file through the authorized Session identity. */
        const readText = async (sessionId, candidates, signal) => {
          const list = Array.isArray(candidates) ? candidates : [candidates];
          for (const candidate of list) {
            try {
              const stat = await ctx.remote.workspaceFiles.stat(sessionId, candidate, signal);
              if (!stat || !stat.ok) continue;
              const page = await ctx.remote.workspaceFiles.read(sessionId, candidate, { offset: 1, limit: 4000 }, signal);
              if (!page || !page.ok) continue;
              return page.value.text;
            } catch {
              continue;
            }
          }
          return null;
        };

        // `startSession` owns the whole navigation: it creates or reuses the
        // blank, initializes the draft, and reveals the Conversation. Selecting
        // a panel here would abort the pending `beginNavigation()` of that open.
        const launch = (prompt) => {
          ctx.uiWorkspace.startSession(undefined, {
            agentPreset: PRESET_ID,
            prompt,
            whenDraftExists: 'append',
          });
        };

        ctx.effect(
          () => ctx.slots.inject('main', () => ctx.slots.register({
            name: 'main',
            key: PANEL_ID,
            locale: NS,
            inject: () => ({ tr, launch, readText, openSession: (id) => ctx.uiWorkspace.openSession(id) }),
          }, Studio)),
          'xuanxue: main panel',
        );

        ctx.effect(
          () => ctx.slots.inject('sidebar.panellist', () => ctx.slots.register({
            name: 'sidebar.panellist',
            id: PANEL_ID,
            order: 1,
            label: () => tr('panel'),
            locale: NS,
          }, XuanxueIcon)),
          'xuanxue: sidebar entry',
        );
      },
    };
  },
});
