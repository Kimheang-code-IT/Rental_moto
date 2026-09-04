import { describe, expect, it } from 'vitest'
import { systemSettingsTabs } from '../app/config/settings-schemas'

describe('telegram settings', () => {
  const telegramFields = systemSettingsTabs
    .find(tab => tab.id === 'telegram')
    ?.sections.flatMap(section => section.fields) ?? []

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
