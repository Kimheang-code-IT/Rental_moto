import type { NavigationMenuItem } from '@nuxt/ui'

const SIDEBAR_COLLAPSED_KEY = 'lcs-freight:sidebar:collapsed'
const SIDEBAR_AUTO_MQ = '(max-width: 1023px)'

/** Single source of truth for the LCS Freight Forwarding navigation. */
export function useMenu() {
  const { t } = useI18n()
  const open = useState('sidebar-open', () => false)
  const collapsed = useState('sidebar-collapsed', () => false)
  const manualCollapsed = useState<boolean | null>('sidebar-collapsed-manual', () => null)
  const isNarrow = useMediaQuery(SIDEBAR_AUTO_MQ)
  const hydrated = useState('sidebar-collapsed-hydrated', () => false)

  function close() { open.value = false }
  function applyAutoCollapse(narrow: boolean) { collapsed.value = manualCollapsed.value == null ? narrow : manualCollapsed.value }
  function setCollapsed(value: boolean) {
    collapsed.value = value
    manualCollapsed.value = value
    if (import.meta.client) localStorage.setItem(SIDEBAR_COLLAPSED_KEY, value ? '1' : '0')
  }

  if (import.meta.client && !hydrated.value) {
    hydrated.value = true
    const saved = localStorage.getItem(SIDEBAR_COLLAPSED_KEY)
    if (saved === '1' || saved === '0') {
      manualCollapsed.value = saved === '1'
      collapsed.value = manualCollapsed.value
    }
    else applyAutoCollapse(isNarrow.value)
    watch(isNarrow, applyAutoCollapse)
  }

  const pageLink = (label: string, to: string): NavigationMenuItem => ({ label, to, exact: true, class: 'text-sm gap-2', onSelect: close })

  const ROUTE_PERMISSION: Record<string, string> = {
    '/': 'dashboard.view',
    '/motorcycles': 'rental.motorcycles.view',
    '/customers': 'rental.customers.view',
    '/rentals': 'rental.rentals.view',
    '/income-expense': 'rental.finance.view',
    '/rental-reports': 'reports.view',
    '/administration/organizations': 'admin.organization.view',
    '/administration/branches': 'admin.organization.view',
    '/administration/document-sequences': 'configuration.manage',
    '/administration/system-settings': 'settings.app_config.view',
  }

  const auth = useAuthStore()

  function canSee(to: string) {
    const permission = ROUTE_PERMISSION[to]
    if (!permission) return true
    return auth.canAccessPage(permission)
  }

  function filterItem(item: NavigationMenuItem): NavigationMenuItem | null {
    if (item.children?.length) {
      const children = item.children.map(filterItem).filter((child): child is NavigationMenuItem => Boolean(child))
      if (!children.length) return null
      return { ...item, children }
    }
    const to = typeof item.to === 'string' ? item.to : ''
    return canSee(to) ? item : null
  }

  const group = (id: string, label: string, icon: string, children: NavigationMenuItem[]): NavigationMenuItem => ({
    label,
    icon,
    type: 'trigger',
    value: id,
    defaultOpen: true,
    class: 'mt-1 text-sm gap-2',
    children,
  })

  const links = computed<NavigationMenuItem[][]>(() => {
    const tree: NavigationMenuItem[] = [
      { label: t('freight.nav.dashboard'), icon: 'i-lucide-layout-dashboard', to: '/', exact: true, class: 'text-sm gap-2', onSelect: close },
      { label: t('rental.nav.motorcycles'), icon: 'i-lucide-bike', to: '/motorcycles', class: 'text-sm gap-2', onSelect: close },
      { label: t('rental.nav.customers'), icon: 'i-lucide-users', to: '/customers', class: 'text-sm gap-2', onSelect: close },
      { label: t('rental.nav.rentals'), icon: 'i-lucide-key-round', to: '/rentals', class: 'text-sm gap-2', onSelect: close },
      { label: t('rental.nav.incomeExpense'), icon: 'i-lucide-wallet', to: '/income-expense', class: 'text-sm gap-2', onSelect: close },
      { label: t('rental.nav.rentalReports'), icon: 'i-lucide-chart-no-axes-combined', to: '/rental-reports', class: 'text-sm gap-2', onSelect: close },
      group('administration', t('freight.nav.administration'), 'i-lucide-shield-check', [
        pageLink(t('freight.pages.organizations'), '/administration/organizations'),
        pageLink(t('freight.pages.branches'), '/administration/branches'),
        pageLink(t('freight.pages.users'), '/administration/users'),
        pageLink(t('freight.pages.roles'), '/administration/roles'),
        pageLink(t('freight.pages.documentSequences'), '/administration/document-sequences'),
        pageLink(t('freight.pages.settings'), '/administration/system-settings'),
        pageLink(t('freight.pages.auditLogs'), '/administration/audit-logs'),
      ]),
    ]
    return [tree.map(filterItem).filter((item): item is NavigationMenuItem => Boolean(item)), []]
  })

  return { open, collapsed, links, close, setCollapsed }
}
