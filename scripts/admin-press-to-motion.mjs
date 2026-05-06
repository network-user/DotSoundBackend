import fs from 'node:fs'
import path from 'node:path'

function walk(dir, out = []) {
  for (const ent of fs.readdirSync(dir, {
    withFileTypes: true,
  })) {
    const p = path.join(dir, ent.name)
    if (ent.isDirectory()) walk(p, out)
    else if (p.endsWith('.tsx')) out.push(p)
  }
  return out
}

const root = path.join(
  process.cwd(),
  'frontend',
  'src',
  'admin',
)

for (const p of walk(root)) {
  let s = fs.readFileSync(p, 'utf8')
  if (!s.includes("@/components/ui/Press'")) continue
  const orig = s
  s = s.replace(
    /import \{ Press \} from '@\/components\/ui\/Press'/g,
    "import { MotionPress } from '@/components/ui/MotionPress'",
  )
  s = s.replace(/<Press\b/g, '<MotionPress')
  s = s.replace(/<\/Press>/g, '</MotionPress>')
  s = s.replace(/variant="default"/g, 'variant="ghost"')
  if (s !== orig) fs.writeFileSync(p, s, 'utf8')
}
