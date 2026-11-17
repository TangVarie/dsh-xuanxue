/**
 * Host half of the 玄学台 bundle.
 *
 * The bundle carries three things: a browser half (the left-sidebar 玄学 page,
 * `client.js`), an agent preset (`presets/xuanxue.patch.yml`), and the four
 * metaphysics skills plus the practice layer under `skills/`.
 *
 * The skills have to reach the agent without naming an absolute directory: an
 * installed bundle lives in the profile's `node_modules`, and the plugin has no
 * way to know that path from YAML. So this Host half registers a read-only skill
 * provider whose root is the `skills/` directory next to this file, resolved
 * from `import.meta.url`. Whatever the install location is — a workspace
 * checkout linked into the profile, or a Git commit fetched from GitHub — the
 * four skills are discovered from the package itself, at the `custom` rank the
 * preset used to hard-code.
 *
 * The provider deliberately does no watching: skill files change only when the
 * package changes, which replaces the module generation anyway.
 */

import { readdir, readFile, realpath } from 'node:fs/promises'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

export const name = 'xuanxue-tab'

/** The registry lives on `ctx.skills`; declare it so activation waits for it. */
export const inject = ['skills']

const SKILLS_DIR = fileURLToPath(new URL('./skills/', import.meta.url))
const PROVIDER = 'xuanxue-packaged'
/** Same rank as the `custom` filesystem root the preset used before. */
const RANK = 300

/**
 * Register the packaged skill root for the life of this plugin.
 * @param {import('@deepseek-ai/cordis').Context} ctx
 */
export function apply(ctx) {
  ctx.effect(
    () => ctx.skills.registerProvider(() => new PackagedSkills()),
    'xuanxue packaged skills',
  )
}

/** Read-only provider over `<package>/skills/<name>/SKILL.md`. */
class PackagedSkills {
  name = PROVIDER

  /**
   * Report every skill directory that has a parseable `SKILL.md`.
   * @returns {Promise<object[]>} candidates for the registry to merge
   */
  async list() {
    const entries = await readdir(SKILLS_DIR, { withFileTypes: true }).catch(() => [])
    const candidates = []
    for (const entry of entries) {
      if (!entry.isDirectory()) continue
      const directory = join(SKILLS_DIR, entry.name)
      const skillFile = join(directory, 'SKILL.md')
      const parsed = await readSkill(skillFile)
      if (parsed === undefined) continue
      candidates.push({
        name: parsed.name,
        description: parsed.description,
        ...(parsed.whenToUse === undefined ? {} : { whenToUse: parsed.whenToUse }),
        invocation: parsed.invocation,
        provider: PROVIDER,
        source: 'custom',
        rank: RANK,
        locator: { path: skillFile, directory },
        resourceBase: { kind: 'directory', path: directory },
        path: skillFile,
      })
    }
    return candidates.sort((a, b) => a.name.localeCompare(b.name))
  }

  /**
   * Load one skill body by its exact kebab-case name.
   * @param {object} candidate a candidate this provider returned
   * @returns {Promise<object | undefined>} the skill definition, or nothing when it vanished
   */
  async get(candidate) {
    const locator = candidate.locator
    if (locator === undefined || typeof locator.path !== 'string') return undefined
    const parsed = await readSkill(locator.path)
    if (parsed === undefined || parsed.name !== candidate.name) return undefined
    let path = locator.path
    try { path = await realpath(locator.path) } catch { /* keep the discovered path */ }
    return {
      name: parsed.name,
      description: parsed.description,
      ...(parsed.whenToUse === undefined ? {} : { whenToUse: parsed.whenToUse }),
      invocation: parsed.invocation,
      source: candidate.source,
      provider: PROVIDER,
      resourceBase: { kind: 'directory', path: locator.directory },
      path,
      content: parsed.body,
    }
  }
}

/**
 * Read a `SKILL.md` and split its frontmatter from its body.
 *
 * The five bundled skills use a deliberately small frontmatter subset: flat
 * `key: value` fields on the top level, one nested `metadata:` map that this
 * provider ignores, and plain or quoted scalars. Anything outside that subset —
 * a block scalar, a list, a malformed line — makes the skill unreadable here on
 * purpose, so `test/skills.test.mjs` fails loudly instead of the catalog
 * silently showing a truncated description.
 *
 * @param {string} file absolute path to a skill instruction file
 * @returns {Promise<{name: string, description: string, whenToUse?: string,
 *   invocation: {modelInvocable: boolean, userInvocable: boolean}, body: string} | undefined>}
 */
async function readSkill(file) {
  let text
  try {
    text = await readFile(file, 'utf8')
  } catch {
    return undefined
  }
  const lines = text.split(/\r?\n/)
  if (lines[0] !== '---') return undefined
  const end = lines.indexOf('---', 1)
  if (end < 0) return undefined
  const fields = new Map()
  for (const line of lines.slice(1, end)) {
    const match = /^([A-Za-z][A-Za-z0-9_-]*):[ \t]*(.*)$/.exec(line)
    if (match === null) continue
    fields.set(match[1], unquote(match[2]))
  }
  const skillName = fields.get('name')
  const description = fields.get('description')
  if (skillName === undefined || skillName === '' || description === undefined || description === '') {
    return undefined
  }
  const whenToUse = fields.get('whenToUse')
  return {
    name: skillName,
    description,
    ...(whenToUse === undefined || whenToUse === '' ? {} : { whenToUse }),
    invocation: {
      modelInvocable: readBoolean(fields.get('disable-model-invocation')) !== true,
      userInvocable: readBoolean(fields.get('user-invocable')) !== false,
    },
    body: lines.slice(end + 1).join('\n').trim(),
  }
}

/** Strip the surrounding quotes YAML would remove, keeping the inner text. */
function unquote(value) {
  const text = value.trim()
  if (text.length >= 2 && text.startsWith('"') && text.endsWith('"')) {
    return text.slice(1, -1).replace(/\\(["\\])/g, '$1')
  }
  if (text.length >= 2 && text.startsWith("'") && text.endsWith("'")) {
    return text.slice(1, -1).replace(/''/g, "'")
  }
  return text
}

/** Read the boolean spellings the skill format accepts; unknown stays undefined. */
function readBoolean(value) {
  if (value === undefined) return undefined
  const text = unquote(value).toLowerCase()
  if (['true', 'yes', 'on', '1'].includes(text)) return true
  if (['false', 'no', 'off', '0'].includes(text)) return false
  return undefined
}
