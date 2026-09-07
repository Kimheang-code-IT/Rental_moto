import type { ModuleField, ModuleConfig } from './modules'
import {
  MOTORCYCLE_STATUS,
  PAYMENT_METHODS,
  RENTAL_CHARGE_TYPES,
  RENTAL_CURRENCY_OPTIONS,
  RENTAL_CUSTOMER_STATUS,
  RENTAL_IDENTITY_TYPES,
  RENTAL_STATUS,
  RATE_TYPES,
} from './rental-options'

/**
 * HollyWing Motor rental modules. Type-only import of the shared module shapes —
 * registered into the route-module lookup by `modules.ts`.
 */

type RentalFieldType = ModuleField['type']

type RentalSelectOption = string | { label: string, value: string }

const rf = (
  key: string,
  label: string,
  labelKm: string,
  section = 'General Information',
  sectionKm = 'ព័ត៌មានទូទៅ',
  type: RentalFieldType = 'text',
  options?: readonly RentalSelectOption[],
  extra: Partial<ModuleField> = {},
): ModuleField => ({ key, label, labelKm, section, sectionKm, type, options, ...extra })

const rcol = (key: string, label: string, labelKm?: string, extra: Partial<ModuleField> = {}): ModuleField => ({
  key,
  label,
  labelKm: labelKm || label,
  ...extra,
})

function createRentalModule(partial: Omit<ModuleConfig, 'canCreate'> & { canCreate?: boolean }): ModuleConfig {
  return {
    canCreate: partial.readOnly ? false : partial.canCreate !== false,
    kind: partial.kind || 'standard',
    ...partial,
  }
}

export const rentalModules: ModuleConfig[] = [
  createRentalModule({
    path: '/motorcycles',
    title: 'Motorcycles',
    titleKm: 'ម៉ូតូ',
    singular: 'Motorcycle',
    singularKm: 'ម៉ូតូ',
    description: 'Fleet records with plate, chassis, engine, rates and availability status.',
    descriptionKm: 'កំណត់ត្រាម៉ូតូ លេខផ្ទាំង លេខ chassis លេខម៉ាស៊ីន អត្រា និងស្ថានភាព។',
    icon: 'i-lucide-bike',
    group: 'rental',
    permission: 'rental.motorcycles.view',
    collection: 'motorcycles',
    titleField: 'code',
    statuses: MOTORCYCLE_STATUS,
    columns: [
      rcol('code', 'Motorcycle Code', 'លេខកូដម៉ូតូ'),
      rcol('model', 'Model', 'ម៉ូដែល'),
      rcol('plate', 'Plate', 'លេខផ្ទាំង'),
      rcol('chassisNo', 'Chassis', 'លេខ chassis'),
      rcol('engineNo', 'Engine', 'លេខម៉ាស៊ីន'),
      rcol('dailyRate', '1 Day', '១ ថ្ងៃ'),
      rcol('threeDayRate', '3 Days', '៣ ថ្ងៃ'),
      rcol('weeklyRate', '1 Week', '១ អាទិត្យ'),
      rcol('monthlyRate', '1 Month', '១ ខែ'),
      rcol('status', 'Status', 'ស្ថានភាព'),
    ],
    fields: [
      rf('model', 'Model', 'ម៉ូដែល', 'General Information', 'ព័ត៌មានទូទៅ', 'text', undefined, { required: true }),
      rf('brand', 'Brand', 'ម៉ាក', 'General Information', 'ព័ត៌មានទូទៅ'),
      rf('year', 'Year', 'ឆ្នាំ', 'General Information', 'ព័ត៌មានទូទៅ', 'number'),
      rf('color', 'Color', 'ពណ៌', 'General Information', 'ព័ត៌មានទូទៅ'),
      rf('plate', 'Plate Number', 'លេខផ្ទាំង', 'Registration', 'ការចុះបញ្ជី', 'text', undefined, { required: true }),
      rf('chassisNo', 'Chassis Number', 'លេខ chassis', 'Registration', 'ការចុះបញ្ជី', 'text', undefined, { required: true }),
      rf('engineNo', 'Engine Number', 'លេខម៉ាស៊ីន', 'Registration', 'ការចុះបញ្ជី', 'text', undefined, { required: true }),
      rf('dailyRate', '1 Day Rate', 'តម្លៃ ១ ថ្ងៃ', 'Rates', 'អត្រា', 'number', undefined, { required: true }),
      rf('threeDayRate', '3 Day Rate', 'តម្លៃ ៣ ថ្ងៃ', 'Rates', 'អត្រា', 'number'),
      rf('weeklyRate', '1 Week Rate', 'តម្លៃ ១ អាទិត្យ', 'Rates', 'អត្រា', 'number'),
      rf('monthlyRate', '1 Month Rate', 'តម្លៃ ១ ខែ', 'Rates', 'អត្រា', 'number'),
      rf('currency', 'Currency', 'រូបិយប័ណ្ណ', 'Rates', 'អត្រា', 'select', RENTAL_CURRENCY_OPTIONS),
      // Status is driven by row actions / rental lifecycle (not free-form edit).
      rf('status', 'Status', 'ស្ថានភាព', 'Status', 'ស្ថានភាព', 'select', MOTORCYCLE_STATUS, { computed: true }),
    ],
    filters: [
      rf('status', 'Status', 'ស្ថានភាព', '', '', 'select', MOTORCYCLE_STATUS),
      rf('model', 'Model', 'ម៉ូដែល', '', '', 'select'),
    ],
  }),
  createRentalModule({
    path: '/customers',
    title: 'Customers',
    titleKm: 'អតិថិជន',
    singular: 'Customer',
    singularKm: 'អតិថិជន',
    description: 'Rental customers with identity documents and contact details.',
    descriptionKm: 'អតិថិជនជួលម៉ូតូ ជាមួយឯកសារសម្គាល់តួអង្គ និងព័ត៌មានទំនាក់ទំនង។',
    icon: 'i-lucide-users',
    group: 'rental',
    permission: 'rental.customers.view',
    collection: 'rentalCustomers',
    titleField: 'fullName',
    statuses: RENTAL_CUSTOMER_STATUS,
    columns: [
      rcol('code', 'Customer Code', 'លេខកូដអតិថិជន'),
      rcol('fullName', 'Full Name', 'ឈ្មោះពេញ'),
      rcol('company', 'Company', 'ក្រុមហ៊ុន'),
      rcol('identityNumber', 'Identity / Passport', 'អត្តសញ្ញាណ / លិខិតឆ្លងដែន'),
      rcol('phone', 'Phone', 'ទូរស័ព្ទ'),
      rcol('status', 'Status', 'ស្ថានភាព'),
    ],
    fields: [
      rf('fullName', 'Full Name', 'ឈ្មោះពេញ', 'General Information', 'ព័ត៌មានទូទៅ', 'text', undefined, { required: true }),
      rf('phone', 'Phone', 'ទូរស័ព្ទ', 'General Information', 'ព័ត៌មានទូទៅ', 'text', undefined, { required: true }),
      rf('email', 'Email', 'អ៊ីមែល', 'General Information', 'ព័ត៌មានទូទៅ'),
      rf('company', 'Company', 'ក្រុមហ៊ុន', 'General Information', 'ព័ត៌មានទូទៅ'),
      rf('identityType', 'Identity Type', 'ប្រភេទអត្តសញ្ញាណ', 'Identity', 'អត្តសញ្ញាណ', 'select', RENTAL_IDENTITY_TYPES),
      rf('identityNumber', 'Identity Number', 'លេខអត្តសញ្ញាណ', 'Identity', 'អត្តសញ្ញាណ', 'text', undefined, { required: true }),
      rf('address', 'Address', 'អាសយដ្ឋាន', 'Identity', 'អត្តសញ្ញាណ', 'textarea', undefined, { colSpan: 2 }),
      // Status is driven by row actions (Active ↔ Inactive).
      rf('status', 'Status', 'ស្ថានភាព', 'Status', 'ស្ថានភាព', 'select', RENTAL_CUSTOMER_STATUS, { computed: true }),
    ],
    filters: [
      rf('status', 'Status', 'ស្ថានភាព', '', '', 'select', RENTAL_CUSTOMER_STATUS),
    ],
  }),
  createRentalModule({
    path: '/rentals',
    title: 'Rentals',
    titleKm: 'ការជួល',
    singular: 'Rental',
    singularKm: 'ការជួល',
    description: 'Active and overdue rental agreements with charges, payments and balances.',
    descriptionKm: 'កិច្ចសន្យាជួលកំពុងដំណើរការ និងហួសកំណត់ ជាមួយការគិតថ្លៃ ការទូទាត់ និងសមតុល្យ។',
    icon: 'i-lucide-key-round',
    group: 'rental',
    permission: 'rental.rentals.view',
    collection: 'rentals',
    titleField: 'rentalNo',
    statuses: RENTAL_STATUS,
    columns: [
      rcol('rentalNo', 'Rental Number', 'លេខការជួល'),
      rcol('customer', 'Customer', 'អតិថិជន'),
      rcol('phone', 'Phone', 'ទូរស័ព្ទ'),
      rcol('motorcycle', 'Motorcycle', 'ម៉ូតូ'),
      rcol('plate', 'Plate', 'លេខផ្ទាំង'),
      rcol('startDate', 'Start Date', 'ថ្ងៃចាប់ផ្តើម'),
      rcol('dueDate', 'Due Date', 'ថ្ងៃត្រូវបញ្ចប់'),
      rcol('durationDays', 'Days', 'ចំនួនថ្ងៃ'),
      rcol('paymentMethod', 'Payment Method', 'វិធីទូទាត់'),
      rcol('rentalCharge', 'Rental Charge', 'ថ្លៃជួល'),
      rcol('lateFee', 'Late Fee', 'ថ្លៃយឺត'),
      rcol('totalDue', 'Total Due', 'សរុបត្រូវបង់'),
      rcol('paid', 'Paid', 'បានបង់'),
      rcol('outstanding', 'Outstanding', 'នៅជំពាក់'),
      rcol('status', 'Status', 'ស្ថានភាព'),
    ],
    fields: [
      rf('rentalNo', 'Rental Number', 'លេខការជួល', 'Rental', 'ការជួល', 'text', undefined, { required: true, computed: true }),
      rf('customerId', 'Customer', 'អតិថិជន', 'Rental', 'ការជួល', 'text', undefined, { required: true }),
      rf('customer', 'Customer Name', 'ឈ្មោះអតិថិជន', 'Rental', 'ការជួល', 'text', undefined, { required: true }),
      rf('phone', 'Phone', 'ទូរស័ព្ទ', 'Rental', 'ការជួល'),
      rf('motorcycleId', 'Motorcycle', 'ម៉ូតូ', 'Rental', 'ការជួល', 'text', undefined, { required: true }),
      rf('motorcycle', 'Motorcycle Model', 'ម៉ូដែលម៉ូតូ', 'Rental', 'ការជួល', 'text', undefined, { required: true }),
      rf('plate', 'Plate', 'លេខផ្ទាំង', 'Rental', 'ការជួល'),
      rf('startDate', 'Start Date', 'ថ្ងៃចាប់ផ្តើម', 'Rental', 'ការជួល', 'datetime', undefined, { required: true }),
      rf('dueDate', 'Due Date', 'ថ្ងៃត្រូវបញ្ចប់', 'Rental', 'ការជួល', 'datetime', undefined, { required: true }),
      rf('durationDays', 'Days', 'ចំនួនថ្ងៃ', 'Rental', 'ការជួល', 'number'),
      rf('rateType', 'Rate Type', 'ប្រភេទអត្រា', 'Charges', 'ការគិតថ្លៃ', 'select', RATE_TYPES, { required: true }),
      rf('rateAmount', 'Rate Amount', 'ចំនួនអត្រា', 'Charges', 'ការគិតថ្លៃ', 'number', undefined, { required: true }),
      rf('deposit', 'Deposit', 'ប្រាក់កក់', 'Charges', 'ការគិតថ្លៃ', 'number'),
      rf('discount', 'Discount', 'បញ្ចុះតម្លៃ', 'Charges', 'ការគិតថ្លៃ', 'number'),
      rf('currency', 'Currency', 'រូបិយប័ណ្ណ', 'Charges', 'ការគិតថ្លៃ', 'select', RENTAL_CURRENCY_OPTIONS),
      rf('rentalCharge', 'Rental Charge', 'ថ្លៃជួល', 'Balance', 'សមតុល្យ', 'number', undefined, { computed: true }),
      rf('lateFee', 'Late Fee', 'ថ្លៃយឺត', 'Balance', 'សមតុល្យ', 'number', undefined, { computed: true }),
      rf('additionalCharges', 'Additional Charges', 'ការគិតថ្លៃបន្ថែម', 'Balance', 'សមតុល្យ', 'number', undefined, { computed: true }),
      rf('totalDue', 'Total Due', 'សរុបត្រូវបង់', 'Balance', 'សមតុល្យ', 'number', undefined, { computed: true }),
      rf('paid', 'Paid', 'បានបង់', 'Balance', 'សមតុល្យ', 'number', undefined, { computed: true }),
      rf('outstanding', 'Outstanding', 'នៅជំពាក់', 'Balance', 'សមតុល្យ', 'number', undefined, { computed: true }),
      rf('returnDate', 'Actual Return', 'ថ្ងៃប្រគល់ពិត', 'Return', 'ការប្រគល់', 'datetime'),
      rf('condition', 'Motorcycle Condition', 'ស្ថានភាពម៉ូតូ', 'Return', 'ការប្រគល់', 'select', ['Good', 'Minor issues', 'Damaged']),
      rf('returnNote', 'Return Note', 'កំណត់សម្គាល់ប្រគល់', 'Return', 'ការប្រគល់', 'textarea', undefined, { colSpan: 2 }),
      rf('note', 'Note', 'កំណត់សម្គាល់', 'Return', 'ការប្រគល់', 'textarea', undefined, { colSpan: 2 }),
      rf('createdBy', 'Created By', 'បង្កើតដោយ', 'Return', 'ការប្រគល់'),
      rf('status', 'Status', 'ស្ថានភាព', 'Status', 'ស្ថានភាព', 'select', RENTAL_STATUS),
    ],
    filters: [
      rf('status', 'Status', 'ស្ថានភាព', '', '', 'select', ['Active', 'Overdue']),
      rf('customer', 'Customer', 'អតិថិជន', '', '', 'select'),
    ],
    actions: [
      { key: 'closeRental', label: 'Return / Close', labelKm: 'ប្រគល់ / បិទ', icon: 'i-lucide-circle-check', color: 'success' },
      { key: 'printInvoice', label: 'Print Invoice', labelKm: 'បោះពុម្ពវិក្កយបត្រ', icon: 'i-lucide-printer' },
    ],
  }),
]

/** Row-action permission gates for rental module actions. */
export const RENTAL_ACTION_PERMISSION: Record<string, string> = {
  closeRental: 'rental.rentals.return',
  printInvoice: 'rental.rentals.print',
}

export const RENTAL_PAYMENT_METHODS = PAYMENT_METHODS
export const RENTAL_CHARGE_TYPE_OPTIONS = RENTAL_CHARGE_TYPES
