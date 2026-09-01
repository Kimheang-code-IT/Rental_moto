import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve('app')
const testsRoot = path.resolve('tests')
const i18nRoot = path.resolve('i18n/locales')

const replacements = [
  ['FreightWorkspaceView', 'ModuleWorkspaceView'],
  ['FreightModulePage', 'ModulePage'],
  ['FreightDocumentView', 'ModuleDocumentView'],
  ['FreightFieldGrid', 'ModuleFieldGrid'],
  ['FreightFieldInput', 'ModuleFieldInput'],
  ['useFreightStore', 'useAppDataStore'],
  ['useFreightRouteModule', 'useModuleRoute'],
  ['useFreightLabel', 'useModuleLabel'],
  ['useFreightRecordChrome', 'useModuleRecordChrome'],
  ['emptyFreightRecord', 'emptyModuleRecord'],
  ['formatFreightCell', 'formatModuleCell'],
  ['freightStatusBadge', 'moduleStatusBadge'],
  ['freightDocumentLineActionKey', 'moduleDocumentLineActionKey'],
  ['freightDocumentRecordKey', 'moduleDocumentRecordKey'],
  ['freightSelectOptions', 'moduleSelectOptions'],
  ['freightFieldToDocumentField', 'moduleFieldToDocumentField'],
  ['FreightRecord', 'AppRecord'],
  ['FreightModule', 'ModuleConfig'],
  ['FreightField', 'ModuleField'],
  ['FreightLineColumn', 'ModuleLineColumn'],
  ['FreightTable', 'ModuleTable'],
  ['FreightRelated', 'ModuleRelated'],
  ['FreightAction', 'ModuleAction'],
  ['FreightSelectOption', 'ModuleSelectOption'],
  ['FreightFieldType', 'ModuleFieldType'],
  ['FreightDocumentForm', 'ModuleDocumentForm'],
  ['getFreightModule', 'getModule'],
  ['freightModules', 'appModules'],
  ['createFreightSeed', 'createAdminSeed'],
  ['createLcsFreightSeed', 'createLcsSeed'],
  ['~/config/freight-seed', '~/config/admin-seed'],
  ['~/config/freight-modules', '~/config/modules'],
  ['~/config/freight-options', '~/config/shared-options'],
  ['~/composables/freight/useFreight', '~/composables/module/useModule'],
  ['~/composables/freight/useFreightRecordChrome', '~/composables/module/useModuleRecordChrome'],
  ['~/stores/freight', '~/stores/app-data'],
  ['~/utils/freight/audit-logs', '~/utils/module/audit-logs'],
  ['~/utils/freight/document-tabs', '~/utils/module/document-tabs'],
  ['~/utils/freight/attachments', '~/utils/module/attachments'],
  ['~/utils/freight/format', '~/utils/module/format'],
  ['~/utils/freight/job-workspace', '~/utils/module/field-keys'],
  ['~/utils/lcs/commands', '~/utils/lcs/mutable'],
  ['freight.ui.', 'app.ui.'],
  ['freight.pages.', 'app.pages.'],
  ['freight.nav.', 'app.nav.'],
  ['freight.sections.', 'app.sections.'],
  ['freight.tables.', 'app.tables.'],
  ['freight.fields.', 'app.fields.'],
  ['freight.modules.', 'app.modules.'],
  ['freight.moduleActions.', 'app.moduleActions.'],
  ['freight.related.', 'app.related.'],
  ['freight.fieldHelp.', 'app.fieldHelp.'],
]

function walk(dir, files = []) {
  if (!fs.existsSync(dir)) return files
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      if (entry.name === 'node_modules' || entry.name === '.git') continue
      walk(full, files)
    }
    else if (/\.(ts|vue|json|mjs)$/.test(entry.name)) {
      files.push(full)
    }
  }
  return files
}

const files = [...walk(root), ...walk(testsRoot), ...walk(i18nRoot)]
let changed = 0

for (const file of files) {
  if (file.includes(`${path.sep}components${path.sep}freight${path.sep}`)) continue
  if (file.includes(`${path.sep}composables${path.sep}freight${path.sep}`)) continue
  if (file.includes('config\\freight-') || file.includes('config/freight-')) continue
  if (file.includes('stores\\freight.ts') || file.includes('stores/freight.ts')) continue
  if (file.includes('utils\\freight\\') || file.includes('utils/freight/')) continue
  if (file.includes('utils\\lcs\\commands.ts') || file.includes('utils/lcs/commands.ts')) continue
  if (file.includes('composables\\lcs\\useLcs.ts') || file.includes('composables/lcs/useLcs.ts')) continue
  if (file.includes('repositories\\contracts\\lcs.ts') || file.includes('repositories/contracts/lcs.ts')) continue
  if (file.includes('repositories\\mock\\lcs.ts') || file.includes('repositories/mock/lcs.ts')) continue
  if (file.includes('repositories\\http\\lcs.ts') || file.includes('repositories/http/lcs.ts')) continue

  let content = fs.readFileSync(file, 'utf8')
  const original = content
  for (const [from, to] of replacements) {
    content = content.split(from).join(to)
  }
  if (content !== original) {
    fs.writeFileSync(file, content)
    changed++
    console.log('updated', path.relative(process.cwd(), file))
  }
}

console.log(`Done. ${changed} files updated.`)
