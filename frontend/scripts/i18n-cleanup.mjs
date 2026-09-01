import fs from 'node:fs'
import path from 'node:path'

const localesDir = path.resolve('i18n/locales')

const keepModuleCollections = new Set([
  'auditLogs',
  'documentSequences',
  'roles',
  'users',
  'motorcycles',
  'rentalCustomers',
  'rentals',
])

function pruneModules(modules = {}) {
  const next = {}
  for (const [key, value] of Object.entries(modules)) {
    if (keepModuleCollections.has(key)) next[key] = value
  }
  return next
}

function migrateLocale(file) {
  const data = JSON.parse(fs.readFileSync(file, 'utf8'))
  const freight = data.freight || {}

  data.app = {
    nav: freight.nav || {},
    pages: freight.pages || {},
    ui: freight.ui || {},
    sections: freight.sections || {},
    fields: freight.fields || {},
    tables: freight.tables || {},
    modules: pruneModules(freight.modules),
    moduleActions: freight.moduleActions || {},
    related: freight.related || {},
    fieldHelp: freight.fieldHelp || {},
  }

  if (data.app.modules?.roles?.description) {
    data.app.modules.roles.description = data.app.modules.roles.description
      .replace(/freight-forwarding teams/i, 'rental teams')
  }

  delete data.freight
  delete data.lcs

  if (data.docetra?.config) {
    delete data.docetra.config
  }

  fs.writeFileSync(file, `${JSON.stringify(data, null, 2)}\n`)
  console.log('migrated', path.basename(file))
}

for (const file of fs.readdirSync(localesDir)) {
  if (file.endsWith('.json')) migrateLocale(path.join(localesDir, file))
}

console.log('i18n migration complete')
