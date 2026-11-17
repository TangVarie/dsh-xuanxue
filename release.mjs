#!/usr/bin/env node
// 发一版玄学台：把「这个提交上的插件包」登记进 index.json。
//
//   node release.mjs <40 位提交号>
//
// 提交号要是默认分支上、已经包含这一版插件代码的那次提交。
// 版本号、包名和 engines 从那次提交里的 package.json 读，不从工作区读，
// 免得登记的和装到的对不上。
import { execFileSync } from 'node:child_process'
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { addVersion, ensurePlugin, validateIndex } from './lib.mjs'

const REPOSITORY = 'https://github.com/TangVarie/dsh-xuanxue'
const indexFile = fileURLToPath(new URL('./index.json', import.meta.url))

const commit = process.argv[2]
if (!/^[0-9a-f]{40}$/.test(commit ?? '')) {
  console.error('用法：node release.mjs <小写的 40 位提交号>')
  process.exit(2)
}

// 沙箱里 Node 不能开管道子进程时，可以用 PowerShell 先取出清单和时间再传进来；
// 正常在本机发版不需要这两个参数。
const flag = name => {
  const index = process.argv.indexOf(name)
  return index === -1 ? undefined : process.argv[index + 1]
}
const manifestFile = flag('--manifest')
const timestampArg = flag('--time')

const git = (...args) => execFileSync('git', args, { encoding: 'utf8' }).trim()
let manifest
try {
  manifest = manifestFile === undefined
    ? JSON.parse(git('show', `${commit}:package.json`))
    : JSON.parse(readFileSync(manifestFile, 'utf8'))
} catch {
  console.error(`在提交 ${commit} 里读不到 package.json。先 git fetch，确认提交号对不对。`)
  process.exit(1)
}

const readJson = name => JSON.parse(readFileSync(new URL(`./${name}`, import.meta.url), 'utf8'))
const [en, zh] = [readJson('locale/en.json'), readJson('locale/zh.json')]
const icon = `data:image/svg+xml;base64,${readFileSync(new URL('./icon.svg', import.meta.url)).toString('base64')}`

const index = JSON.parse(readFileSync(indexFile, 'utf8'))
try {
  ensurePlugin(index, {
    name: manifest.name,
    title: { en: en.meta.title, zh: zh.meta.title },
    description: { en: en.meta.description, zh: zh.meta.description },
    icon,
    repository: REPOSITORY,
    author: '唐变量',
  })
  addVersion(index, {
    name: manifest.name,
    version: manifest.version,
    commit,
    repository: REPOSITORY,
    engines: manifest.engines?.dsh,
    publishTimestamp: timestampArg === undefined
      ? Number(git('show', '-s', '--format=%ct', commit))
      : Number(timestampArg),
  })
  validateIndex(index)
} catch (error) {
  console.error(error.message)
  process.exit(1)
}
writeFileSync(indexFile, `${JSON.stringify(index, null, 2)}\n`)
console.log(`已登记 ${manifest.name} ${manifest.version} -> ${commit}`)
