import { describe, expect, it } from 'vitest'
import { systemSettingsTabs } from '../app/config/settings-schemas'

const telegramTab = systemSettingsTabs.find(tab => tab.id === 'telegram')
const telegramFields = telegramTab?.sections.flatMap(section => section.fields) ?? []

describe('telegram settings', () => {
  it('keeps localization, telegram, and security tabs only', () => {
    expect(systemSettingsTabs.map(tab => tab.id)).toEqual(['localization', 'telegram', 'security'])
  })

  it('exposes telegram.chatId as the single editable Group ID field with help and placeholder', () => {
    const chatId = telegramFields.find(field => field.key === 'telegram.chatId')
    expect(chatId).toBeDefined()
    expect(chatId?.type).toBe('text')
    expect(chatId?.readOnly).toBeFalsy()
    expect(chatId?.labelKey).toBe('rental.settings.groupId')
    expect(chatId?.helpKey).toBe('rental.settings.groupIdHelp')
    expect(chatId?.placeholderKey).toBe('rental.settings.groupIdPlaceholder')
  })

  it('does not expose derived interactive group or destinations editors', () => {
    const keys = telegramFields.map(field => field.key)
    expect(keys).not.toContain('telegram.interactiveGroupId')
    expect(keys).not.toContain('telegram.interactiveGroupEnabled')
    expect(keys).not.toContain('telegram.destinations')
  })

  it('exposes per-staff chat user access for chatbot access', () => {
    const userAccess = telegramFields.find(field => field.key === 'telegram.userAccess')
    expect(userAccess).toBeDefined()
    expect(userAccess?.type).toBe('telegram-user-access')
    expect(userAccess?.colSpan).toBe(2)
  })

  it('exposes chatbot keyboard, report period, module, and sensitive-field options', () => {
    const keys = telegramFields.map(field => field.key)
    expect(keys).toContain('telegram.inlineKeyboardEnabled')
    expect(keys).toContain('telegram.showTransactionsButton')
    expect(keys).toContain('telegram.showMotorcycleStatusButton')
    expect(keys).toContain('telegram.showFinanceSummaryButton')
    expect(keys).toContain('telegram.defaultReportPeriod')
    expect(keys).toContain('telegram.allowedModules.motorcycles')
    expect(keys).toContain('telegram.allowedModules.rentals')
    expect(keys).toContain('telegram.allowedModules.customers')
    expect(keys).toContain('telegram.allowedModules.finance')
    expect(keys).toContain('telegram.sensitiveFields.customerName')
    expect(keys).toContain('telegram.sensitiveFields.customerPhone')
    expect(keys).toContain('telegram.sensitiveFields.financialTotals')
    expect(keys).toContain('telegram.sensitiveFields.rentalBalances')
    expect(keys).toContain('telegram.messageLanguage')
  })

  it('offers the backend report periods on defaultReportPeriod', () => {
    const reportPeriod = telegramFields.find(field => field.key === 'telegram.defaultReportPeriod')
    expect(reportPeriod?.type).toBe('select')
    expect(reportPeriod?.options?.map(option => option.value)).toEqual(['today', '3_days', '7_days', '1_month'])
  })

  it('documents that the saved bot token starts the chatbot', () => {
    const botToken = telegramFields.find(field => field.key === 'telegram.botToken')
    expect(botToken?.type).toBe('secret')
    expect(botToken?.helpKey).toBe('core.fieldHelp.botToken')
  })

  it('keeps connection fields ordered with the test status last', () => {
    const connectionSection = telegramTab?.sections.find(section => section.id === 'telegram-connection')
    const keys = connectionSection?.fields.map(field => field.key) ?? []
    expect(keys).toEqual([
      'telegram.enabled',
      'telegram.botToken',
      'telegram.botDisplayName',
      'telegram.chatId',
      '__telegramConnection',
    ])
  })

  it('keeps rental notification toggles in the notifications section', () => {
    const keys = telegramFields.map(field => field.key)
    expect(keys).toContain('telegram.notifyNewRental')
    expect(keys).toContain('telegram.notifyRentalCompleted')
    expect(keys).toContain('telegram.notifyOverdueRental')
    expect(keys).toContain('telegram.notifyPayment')
    expect(keys).toContain('telegram.notifyCharge')
    expect(keys).toContain('telegram.notifyExpense')
    expect(keys).toContain('telegram.dailySummaryEnabled')
    expect(keys).toContain('telegram.monthlySummaryEnabled')
  })

  it('lets staff turn on new-rental invoice delivery and a duration reminder', () => {
    const keys = telegramFields.map(field => field.key)
    expect(keys).toContain('telegram.notifyNewRental')
    expect(keys).toContain('telegram.deadlineReminderEnabled')
    expect(keys).toContain('telegram.deadlineReminderDuration')
    expect(keys).not.toContain('telegram.deadlineReminderValue')
    expect(keys).not.toContain('telegram.deadlineReminderUnit')
  })

  it('uses a combined duration control with minute/hour/day units', () => {
    const duration = telegramFields.find(field => field.key === 'telegram.deadlineReminderDuration')
    expect(duration?.type).toBe('duration')
    expect(duration?.options?.map(option => option.value)).toEqual(['minutes', 'hours', 'days'])
  })
})
