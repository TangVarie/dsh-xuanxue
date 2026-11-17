// 内置技能来源（index.js 的 packaged provider）：不依赖任何外部路径，
// 直接用包里的 skills/ 目录，所以这个测试也在验证「换个安装位置照样能发现四门」。
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { apply } from '../index.js'

/** 最小 Cordis 上下文：只提供 effect 与 skills.registerProvider。 */
function fakeContext() {
  const context = {
    disposers: [],
    provider: undefined,
    effect(callback) {
      const dispose = callback()
      if (typeof dispose === 'function') context.disposers.push(dispose)
      return dispose
    },
    skills: {
      registerProvider(factory) {
        context.provider = factory({ invalidate() {} })
        return () => { context.provider = undefined }
      },
    },
    logger: { warn() {} },
  }
  return context
}

function provider() {
  const ctx = fakeContext()
  apply(ctx)
  assert.ok(ctx.provider, 'apply 应当注册一个技能来源')
  return ctx.provider
}

test('包里每个带 SKILL.md 的目录都被发现', async () => {
  const skillsDir = new URL('../skills/', import.meta.url)
  const expected = readdirSync(skillsDir, { withFileTypes: true })
    .filter(entry => entry.isDirectory())
    .map(entry => entry.name)
    .filter(name => {
      try {
        readFileSync(new URL(`../skills/${name}/SKILL.md`, import.meta.url), 'utf8')
        return true
      } catch {
        return false
      }
    })
    .sort()
  const candidates = await provider().list()
  assert.deepEqual(candidates.map(candidate => candidate.name).sort(), expected)
  assert.ok(candidates.length >= 5, '四门加实践层至少五个技能')
})

test('候选带齐注册表要的字段，来源与排位正确', async () => {
  const candidates = await provider().list()
  for (const candidate of candidates) {
    assert.match(candidate.name, /^[a-z0-9]+(?:-[a-z0-9]+)*$/)
    assert.ok(candidate.description.length > 0)
    assert.equal(candidate.provider, 'xuanxue-packaged')
    assert.equal(candidate.source, 'custom')
    assert.equal(candidate.rank, 300)
    assert.equal(typeof candidate.locator.path, 'string')
    assert.equal(candidate.resourceBase.kind, 'directory')
    assert.equal(candidate.invocation.modelInvocable, true)
  }
})

test('描述按 YAML 规则去引号，metadata 里的键不会被误当成顶层字段', async () => {
  const candidates = await provider().list()
  const vedic = candidates.find(candidate => candidate.name === 'vedic')
  assert.ok(vedic.description.startsWith('吠陀占星'))
  assert.ok(!vedic.description.startsWith('"'))
  const bazi = candidates.find(candidate => candidate.name === 'bazi-core')
  // metadata 里的 title 是「Bazi Core」，description 不该被它顶掉。
  assert.ok(bazi.description.startsWith('盲派八字解读引擎'))
  assert.equal(bazi.whenToUse, undefined)
})

test('按名字取回正文，正文不含 frontmatter', async () => {
  const instance = provider()
  const candidates = await instance.list()
  for (const candidate of candidates) {
    const skill = await instance.get(candidate)
    assert.ok(skill, `${candidate.name} 应当能取到正文`)
    assert.equal(skill.name, candidate.name)
    assert.equal(skill.source, 'custom')
    assert.ok(skill.content.length > 100)
    assert.ok(!skill.content.startsWith('---'), '正文要从 frontmatter 之后开始')
    assert.ok(skill.content.includes(candidate.name) || skill.content.startsWith('# '))
    assert.ok(skill.resourceBase.path.endsWith(candidate.name))
  }
})

test('名字对不上的候选不返回正文', async () => {
  const instance = provider()
  const [candidate] = await instance.list()
  assert.equal(await instance.get({ ...candidate, name: 'not-this-skill' }), undefined)
  assert.equal(await instance.get({}), undefined)
})

test('apply 的注册可以整体撤掉', () => {
  const ctx = fakeContext()
  apply(ctx)
  assert.equal(ctx.disposers.length, 1)
  ctx.disposers[0]()
  assert.equal(ctx.provider, undefined)
})
