import type { AppRecord } from './admin-seed'
import { BRANCH_BAVET_ID, LCS_ORG_ID } from './lcs-tenant'

/**
 * HollyWing Motor rental demo data. Single-currency (USD) so KPI aggregates stay
 * consistent — display formatting is driven by the user currency preference.
 * Dates fixed around 2026-08-28 (system clock) so OVERDUE rows are genuinely overdue.
 */

function stamp(row: AppRecord): AppRecord {
  return { organizationId: LCS_ORG_ID, branchId: BRANCH_BAVET_ID, createdByUserId: 1, ...row }
}

function id(prefix: string, n: number) {
  return `${prefix}-${String(n).padStart(3, '0')}`
}

function withTierRates(row: AppRecord): AppRecord {
  const daily = Number(row.dailyRate || 0)
  return {
    ...row,
    threeDayRate: row.threeDayRate ?? Number((daily * 3).toFixed(2)),
    weeklyRate: row.weeklyRate ?? Number((daily * 6.5).toFixed(2)),
  }
}

const motorcycles: AppRecord[] = [
  { id: id('mc', 1), code: 'MC-001', model: 'Honda Click 125i', brand: 'Honda', year: 2023, color: 'Black', plate: 'PP-1K-2345', chassisNo: 'JC34-102938', engineNo: 'JC34E-445566', dailyRate: 8, threeDayRate: 24, weeklyRate: 52, monthlyRate: 180, assetValue: 1400, currency: 'USD', status: 'Progressing' },
  { id: id('mc', 2), code: 'MC-002', model: 'Honda Vario 150', brand: 'Honda', year: 2023, color: 'Red', plate: 'PP-2K-3456', chassisNo: 'KF30-203948', engineNo: 'KF30E-556677', dailyRate: 12, threeDayRate: 36, weeklyRate: 78, monthlyRate: 260, assetValue: 2200, currency: 'USD', status: 'Progressing' },
  { id: id('mc', 3), code: 'MC-003', model: 'Yamaha NMAX 155', brand: 'Yamaha', year: 2024, color: 'Blue', plate: 'PP-3K-4567', chassisNo: 'NMAX-304957', engineNo: 'NMAXE-667788', dailyRate: 15, threeDayRate: 45, weeklyRate: 97.5, monthlyRate: 320, assetValue: 2900, currency: 'USD', status: 'Progressing' },
  { id: id('mc', 4), code: 'MC-004', model: 'Honda PCX 160', brand: 'Honda', year: 2024, color: 'White', plate: 'PP-4K-5678', chassisNo: 'PCX-405966', engineNo: 'PCXE-778899', dailyRate: 15, threeDayRate: 45, weeklyRate: 97.5, monthlyRate: 320, assetValue: 3000, currency: 'USD', status: 'Progressing' },
  { id: id('mc', 5), code: 'MC-005', model: 'Suzuki Address 110', brand: 'Suzuki', year: 2022, color: 'Silver', plate: 'PP-5K-6789', chassisNo: 'ADR-506975', engineNo: 'ADRE-889900', dailyRate: 7, threeDayRate: 21, weeklyRate: 45.5, monthlyRate: 150, assetValue: 1100, currency: 'USD', status: 'Progressing' },
  { id: id('mc', 6), code: 'MC-006', model: 'Honda Click 125i', brand: 'Honda', year: 2023, color: 'White', plate: 'PP-6K-7890', chassisNo: 'JC34-607984', engineNo: 'JC34E-990011', dailyRate: 8, threeDayRate: 24, weeklyRate: 52, monthlyRate: 180, assetValue: 1400, currency: 'USD', status: 'Available' },
  { id: id('mc', 7), code: 'MC-007', model: 'Yamaha Mio i 125', brand: 'Yamaha', year: 2023, color: 'Cyan', plate: 'PP-7K-8901', chassisNo: 'MIO-708993', engineNo: 'MIOE-110122', dailyRate: 8, threeDayRate: 24, weeklyRate: 52, monthlyRate: 170, assetValue: 1300, currency: 'USD', status: 'Available' },
  { id: id('mc', 8), code: 'MC-008', model: 'Honda Vision 110', brand: 'Honda', year: 2022, color: 'Black', plate: 'PP-8K-9012', chassisNo: 'VIS-809002', engineNo: 'VISE-220133', dailyRate: 7, threeDayRate: 21, weeklyRate: 45.5, monthlyRate: 150, assetValue: 1000, currency: 'USD', status: 'Available' },
  { id: id('mc', 9), code: 'MC-009', model: 'Honda Adv 150', brand: 'Honda', year: 2024, color: 'Matte Black', plate: 'PP-9K-0123', chassisNo: 'ADV-900011', engineNo: 'ADVE-330244', dailyRate: 16, threeDayRate: 48, weeklyRate: 104, monthlyRate: 350, assetValue: 3200, currency: 'USD', status: 'Available' },
  { id: id('mc', 10), code: 'MC-010', model: 'Yamaha NMAX 155', brand: 'Yamaha', year: 2023, color: 'Grey', plate: 'PP-10K-1234', chassisNo: 'NMAX-010120', engineNo: 'NMAXE-440355', dailyRate: 14, threeDayRate: 42, weeklyRate: 91, monthlyRate: 300, assetValue: 2700, currency: 'USD', status: 'Available' },
  { id: id('mc', 11), code: 'MC-011', model: 'Honda Wave 110', brand: 'Honda', year: 2021, color: 'Red', plate: 'PP-11K-2345', chassisNo: 'WAV-110229', engineNo: 'WAVE-550466', dailyRate: 6, threeDayRate: 18, weeklyRate: 39, monthlyRate: 130, assetValue: 850, currency: 'USD', status: 'Maintenance' },
  { id: id('mc', 12), code: 'MC-012', model: 'Suzuki Burgman Street', brand: 'Suzuki', year: 2023, color: 'Blue', plate: 'PP-12K-3456', chassisNo: 'BRG-120338', engineNo: 'BRGE-660577', dailyRate: 13, threeDayRate: 39, weeklyRate: 84.5, monthlyRate: 280, assetValue: 2400, currency: 'USD', status: 'Available' },
].map(withTierRates)

const rentalCustomers: AppRecord[] = [
  { id: id('rc', 1), code: 'CUS-001', fullName: 'Sok Dara', identityType: 'National ID', identityNumber: 'KH-120345678', phone: '+855 12 345 001', email: 'dara.sok@gmail.com', company: '', address: 'St. 271, Phnom Penh', status: 'Active' },
  { id: id('rc', 2), code: 'CUS-002', fullName: 'Chan Sophea', identityType: 'National ID', identityNumber: 'KH-120987654', phone: '+855 92 456 002', email: 'sophea.c@gmail.com', company: 'Angkor Tours', address: 'Siem Reap', status: 'Active' },
  { id: id('rc', 3), code: 'CUS-003', fullName: 'John Miller', identityType: 'Passport', identityNumber: 'US-548201973', phone: '+855 78 111 003', email: 'john.miller@gmail.com', company: '', address: 'Riverside, Phnom Penh', status: 'Active' },
  { id: id('rc', 4), code: 'CUS-004', fullName: 'Nguyen Thi Lan', identityType: 'Passport', identityNumber: 'VN-883746152', phone: '+855 96 222 004', email: 'lan.nguyen@gmail.com', company: '', address: 'BKK1, Phnom Penh', status: 'Active' },
  { id: id('rc', 5), code: 'CUS-005', fullName: ' Touch Vannak', identityType: 'Driving License', identityNumber: 'DL-KH-2024-118', phone: '+855 10 333 005', email: 'vannak.touch@gmail.com', company: 'Vannak Delivery', address: 'Toul Kork, Phnom Penh', status: 'Active' },
  { id: id('rc', 6), code: 'CUS-006', fullName: 'Som Nita', identityType: 'National ID', identityNumber: 'KH-121122334', phone: '+855 15 444 006', email: 'nita.som@gmail.com', company: '', address: 'Chamkarmon, Phnom Penh', status: 'Active' },
  { id: id('rc', 7), code: 'CUS-007', fullName: 'David Chen', identityType: 'Passport', identityNumber: 'SG-771234890', phone: '+855 67 555 007', email: 'david.chen@gmail.com', company: 'Chen Trading', address: 'Sen Sok, Phnom Penh', status: 'Active' },
  { id: id('rc', 8), code: 'CUS-008', fullName: 'Kim Sreyleap', identityType: 'National ID', identityNumber: 'KH-122233445', phone: '+855 11 666 008', email: 'sreyleap.kim@gmail.com', company: '', address: 'Prek Pnov, Phnom Penh', status: 'Active' },
  { id: id('rc', 9), code: 'CUS-009', fullName: 'Leng Dara', identityType: 'National ID', identityNumber: 'KH-123344556', phone: '+855 99 777 009', email: 'dara.leng@gmail.com', company: 'Dara Repair Shop', address: 'Russey Keo, Phnom Penh', status: 'Active' },
  { id: id('rc', 10), code: 'CUS-010', fullName: 'Anna Petrova', identityType: 'Passport', identityNumber: 'RU-669012345', phone: '+855 81 888 010', email: 'anna.petrova@gmail.com', company: '', address: 'Borey Peng Huoth, Phnom Penh', status: 'Inactive' },
]

// Active (5) + overdue (3). Outstanding = totalDue - paid.
const rentalsActive: AppRecord[] = [
  { id: id('rt', 1), rentalNo: 'RNT-2026-000001', customerId: 'rc-001', customer: 'Sok Dara', phone: '+855 12 345 001', motorcycleId: 'mc-001', motorcycle: 'Honda Click 125i', plate: 'PP-1K-2345', startDate: '2026-08-20T09:00', dueDate: '2026-09-19T09:00', rateType: 'Monthly', rateAmount: 180, deposit: 100, discount: 0, currency: 'USD', rentalCharge: 180, lateFee: 0, additionalCharges: 0, totalDue: 180, paid: 90, outstanding: 90, status: 'Active', createdBy: 'Nita (Staff)' },
  { id: id('rt', 2), rentalNo: 'RNT-2026-000002', customerId: 'rc-003', customer: 'John Miller', phone: '+855 78 111 003', motorcycleId: 'mc-003', motorcycle: 'Yamaha NMAX 155', plate: 'PP-3K-4567', startDate: '2026-08-24T10:00', dueDate: '2026-09-02T10:00', rateType: 'Daily', rateAmount: 15, deposit: 150, discount: 0, currency: 'USD', rentalCharge: 135, lateFee: 0, additionalCharges: 0, totalDue: 135, paid: 60, outstanding: 75, status: 'Active', createdBy: 'Nita (Staff)' },
  { id: id('rt', 3), rentalNo: 'RNT-2026-000003', customerId: 'rc-005', customer: 'Touch Vannak', phone: '+855 10 333 005', motorcycleId: 'mc-002', motorcycle: 'Honda Vario 150', plate: 'PP-2K-3456', startDate: '2026-08-18T08:30', dueDate: '2026-09-17T08:30', rateType: 'Monthly', rateAmount: 260, deposit: 200, discount: 10, currency: 'USD', rentalCharge: 250, lateFee: 0, additionalCharges: 0, totalDue: 250, paid: 250, outstanding: 0, status: 'Active', createdBy: 'Sokha (Staff)' },
  { id: id('rt', 4), rentalNo: 'RNT-2026-000004', customerId: 'rc-006', customer: 'Som Nita', phone: '+855 15 444 006', motorcycleId: 'mc-004', motorcycle: 'Honda PCX 160', plate: 'PP-4K-5678', startDate: '2026-08-26T14:00', dueDate: '2026-08-31T14:00', rateType: 'Daily', rateAmount: 15, deposit: 150, discount: 0, currency: 'USD', rentalCharge: 75, lateFee: 0, additionalCharges: 0, totalDue: 75, paid: 40, outstanding: 35, status: 'Active', createdBy: 'Nita (Staff)' },
  { id: id('rt', 5), rentalNo: 'RNT-2026-000005', customerId: 'rc-002', customer: 'Chan Sophea', phone: '+855 92 456 002', motorcycleId: 'mc-005', motorcycle: 'Suzuki Address 110', plate: 'PP-5K-6789', startDate: '2026-08-15T09:00', dueDate: '2026-08-22T09:00', rateType: 'Daily', rateAmount: 7, deposit: 80, discount: 0, currency: 'USD', rentalCharge: 49, lateFee: 0, additionalCharges: 0, totalDue: 49, paid: 30, outstanding: 19, status: 'Active', createdBy: 'Sokha (Staff)' },
  { id: id('rt', 6), rentalNo: 'RNT-2026-000006', customerId: 'rc-007', customer: 'David Chen', phone: '+855 67 555 007', motorcycleId: 'mc-007', motorcycle: 'Yamaha Mio i 125', plate: 'PP-7K-8901', startDate: '2026-08-10T11:00', dueDate: '2026-08-17T11:00', rateType: 'Daily', rateAmount: 8, deposit: 100, discount: 0, currency: 'USD', rentalCharge: 56, lateFee: 12, additionalCharges: 0, totalDue: 68, paid: 40, outstanding: 28, status: 'Overdue', createdBy: 'Nita (Staff)' },
  { id: id('rt', 7), rentalNo: 'RNT-2026-000007', customerId: 'rc-008', customer: 'Kim Sreyleap', phone: '+855 11 666 008', motorcycleId: 'mc-008', motorcycle: 'Honda Vision 110', plate: 'PP-8K-9012', startDate: '2026-08-08T08:00', dueDate: '2026-08-15T08:00', rateType: 'Daily', rateAmount: 7, deposit: 70, discount: 0, currency: 'USD', rentalCharge: 49, lateFee: 14, additionalCharges: 5, totalDue: 68, paid: 50, outstanding: 18, status: 'Overdue', createdBy: 'Sokha (Staff)' },
  { id: id('rt', 8), rentalNo: 'RNT-2026-000008', customerId: 'rc-004', customer: 'Nguyen Thi Lan', phone: '+855 96 222 004', motorcycleId: 'mc-009', motorcycle: 'Honda Adv 150', plate: 'PP-9K-0123', startDate: '2026-08-12T13:00', dueDate: '2026-08-26T13:00', rateType: 'Daily', rateAmount: 16, deposit: 160, discount: 0, currency: 'USD', rentalCharge: 224, lateFee: 30, additionalCharges: 0, totalDue: 254, paid: 100, outstanding: 154, status: 'Overdue', createdBy: 'Nita (Staff)' },
]

// Completed history — the Rental Reports dataset. Not shown on the Rental page.
const rentalsCompleted: AppRecord[] = [
  { id: id('rt', 11), rentalNo: 'RNT-2026-000011', customerId: 'rc-001', customer: 'Sok Dara', phone: '+855 12 345 001', motorcycleId: 'mc-006', motorcycle: 'Honda Click 125i', plate: 'PP-6K-7890', startDate: '2026-07-01T09:00', dueDate: '2026-07-31T09:00', returnDate: '2026-07-30T17:00', condition: 'Good', rateType: 'Monthly', rateAmount: 180, deposit: 100, discount: 0, currency: 'USD', rentalCharge: 180, lateFee: 0, additionalCharges: 0, totalDue: 180, paid: 180, outstanding: 0, paymentStatus: 'Paid', createdBy: 'Nita (Staff)', status: 'Completed' },
  { id: id('rt', 12), rentalNo: 'RNT-2026-000012', customerId: 'rc-002', customer: 'Chan Sophea', phone: '+855 92 456 002', motorcycleId: 'mc-010', motorcycle: 'Yamaha NMAX 155', plate: 'PP-10K-1234', startDate: '2026-07-05T09:00', dueDate: '2026-07-12T09:00', returnDate: '2026-07-12T10:00', condition: 'Good', rateType: 'Daily', rateAmount: 14, deposit: 140, discount: 0, currency: 'USD', rentalCharge: 98, lateFee: 0, additionalCharges: 0, totalDue: 98, paid: 98, outstanding: 0, paymentStatus: 'Paid', createdBy: 'Sokha (Staff)', status: 'Completed' },
  { id: id('rt', 13), rentalNo: 'RNT-2026-000013', customerId: 'rc-003', customer: 'John Miller', phone: '+855 78 111 003', motorcycleId: 'mc-009', motorcycle: 'Honda Adv 150', plate: 'PP-9K-0123', startDate: '2026-07-10T10:00', dueDate: '2026-07-20T10:00', returnDate: '2026-07-21T14:00', condition: 'Minor issues', rateType: 'Daily', rateAmount: 16, deposit: 160, discount: 0, currency: 'USD', rentalCharge: 160, lateFee: 16, additionalCharges: 15, totalDue: 191, paid: 191, outstanding: 0, paymentStatus: 'Paid', createdBy: 'Nita (Staff)', status: 'Completed' },
  { id: id('rt', 14), rentalNo: 'RNT-2026-000014', customerId: 'rc-005', customer: 'Touch Vannak', phone: '+855 10 333 005', motorcycleId: 'mc-001', motorcycle: 'Honda Click 125i', plate: 'PP-1K-2345', startDate: '2026-07-12T08:00', dueDate: '2026-07-19T08:00', returnDate: '2026-07-19T09:30', condition: 'Good', rateType: 'Daily', rateAmount: 8, deposit: 80, discount: 0, currency: 'USD', rentalCharge: 56, lateFee: 0, additionalCharges: 0, totalDue: 56, paid: 56, outstanding: 0, paymentStatus: 'Paid', createdBy: 'Sokha (Staff)', status: 'Completed' },
  { id: id('rt', 15), rentalNo: 'RNT-2026-000015', customerId: 'rc-006', customer: 'Som Nita', phone: '+855 15 444 006', motorcycleId: 'mc-002', motorcycle: 'Honda Vario 150', plate: 'PP-2K-3456', startDate: '2026-07-15T09:00', dueDate: '2026-07-22T09:00', returnDate: '2026-07-22T11:00', condition: 'Good', rateType: 'Daily', rateAmount: 12, deposit: 120, discount: 0, currency: 'USD', rentalCharge: 84, lateFee: 0, additionalCharges: 0, totalDue: 84, paid: 60, outstanding: 24, paymentStatus: 'Partial', createdBy: 'Nita (Staff)', status: 'Completed' },
  { id: id('rt', 16), rentalNo: 'RNT-2026-000016', customerId: 'rc-004', customer: 'Nguyen Thi Lan', phone: '+855 96 222 004', motorcycleId: 'mc-003', motorcycle: 'Yamaha NMAX 155', plate: 'PP-3K-4567', startDate: '2026-06-28T09:00', dueDate: '2026-07-28T09:00', returnDate: '2026-07-28T09:30', condition: 'Good', rateType: 'Monthly', rateAmount: 320, deposit: 200, discount: 20, currency: 'USD', rentalCharge: 300, lateFee: 0, additionalCharges: 0, totalDue: 300, paid: 300, outstanding: 0, paymentStatus: 'Paid', createdBy: 'Nita (Staff)', status: 'Completed' },
  { id: id('rt', 17), rentalNo: 'RNT-2026-000017', customerId: 'rc-007', customer: 'David Chen', phone: '+855 67 555 007', motorcycleId: 'mc-004', motorcycle: 'Honda PCX 160', plate: 'PP-4K-5678', startDate: '2026-07-02T10:00', dueDate: '2026-07-09T10:00', returnDate: '2026-07-09T12:00', condition: 'Good', rateType: 'Daily', rateAmount: 15, deposit: 150, discount: 0, currency: 'USD', rentalCharge: 105, lateFee: 0, additionalCharges: 0, totalDue: 105, paid: 105, outstanding: 0, paymentStatus: 'Paid', createdBy: 'Sokha (Staff)', status: 'Completed' },
  { id: id('rt', 18), rentalNo: 'RNT-2026-000018', customerId: 'rc-008', customer: 'Kim Sreyleap', phone: '+855 11 666 008', motorcycleId: 'mc-005', motorcycle: 'Suzuki Address 110', plate: 'PP-5K-6789', startDate: '2026-07-08T08:00', dueDate: '2026-07-15T08:00', returnDate: '2026-07-16T08:00', condition: 'Minor issues', rateType: 'Daily', rateAmount: 7, deposit: 70, discount: 0, currency: 'USD', rentalCharge: 49, lateFee: 7, additionalCharges: 10, totalDue: 66, paid: 66, outstanding: 0, paymentStatus: 'Paid', createdBy: 'Nita (Staff)', status: 'Completed' },
  { id: id('rt', 19), rentalNo: 'RNT-2026-000019', customerId: 'rc-009', customer: 'Leng Dara', phone: '+855 99 777 009', motorcycleId: 'mc-011', motorcycle: 'Honda Wave 110', plate: 'PP-11K-2345', startDate: '2026-07-18T09:00', dueDate: '2026-07-25T09:00', returnDate: '2026-07-25T09:00', condition: 'Good', rateType: 'Daily', rateAmount: 6, deposit: 60, discount: 0, currency: 'USD', rentalCharge: 42, lateFee: 0, additionalCharges: 0, totalDue: 42, paid: 42, outstanding: 0, paymentStatus: 'Paid', createdBy: 'Sokha (Staff)', status: 'Completed' },
  { id: id('rt', 20), rentalNo: 'RNT-2026-000020', customerId: 'rc-010', customer: 'Anna Petrova', phone: '+855 81 888 010', motorcycleId: 'mc-012', motorcycle: 'Suzuki Burgman Street', plate: 'PP-12K-3456', startDate: '2026-07-20T10:00', dueDate: '2026-07-27T10:00', returnDate: '2026-07-27T16:00', condition: 'Good', rateType: 'Daily', rateAmount: 13, deposit: 130, discount: 0, currency: 'USD', rentalCharge: 91, lateFee: 0, additionalCharges: 0, totalDue: 91, paid: 91, outstanding: 0, paymentStatus: 'Paid', createdBy: 'Nita (Staff)', status: 'Completed' },
  { id: id('rt', 21), rentalNo: 'RNT-2026-000021', customerId: 'rc-001', customer: 'Sok Dara', phone: '+855 12 345 001', motorcycleId: 'mc-007', motorcycle: 'Yamaha Mio i 125', plate: 'PP-7K-8901', startDate: '2026-06-20T09:00', dueDate: '2026-06-27T09:00', returnDate: '2026-06-27T09:00', condition: 'Good', rateType: 'Daily', rateAmount: 8, deposit: 80, discount: 0, currency: 'USD', rentalCharge: 56, lateFee: 0, additionalCharges: 0, totalDue: 56, paid: 56, outstanding: 0, paymentStatus: 'Paid', createdBy: 'Nita (Staff)', status: 'Completed' },
  { id: id('rt', 22), rentalNo: 'RNT-2026-000022', customerId: 'rc-003', customer: 'John Miller', phone: '+855 78 111 003', motorcycleId: 'mc-010', motorcycle: 'Yamaha NMAX 155', plate: 'PP-10K-1234', startDate: '2026-06-22T09:00', dueDate: '2026-06-29T09:00', returnDate: '2026-06-30T10:00', condition: 'Good', rateType: 'Daily', rateAmount: 14, deposit: 140, discount: 0, currency: 'USD', rentalCharge: 98, lateFee: 14, additionalCharges: 0, totalDue: 112, paid: 112, outstanding: 0, paymentStatus: 'Paid', createdBy: 'Sokha (Staff)', status: 'Completed' },
  { id: id('rt', 23), rentalNo: 'RNT-2026-000023', customerId: 'rc-006', customer: 'Som Nita', phone: '+855 15 444 006', motorcycleId: 'mc-008', motorcycle: 'Honda Vision 110', plate: 'PP-8K-9012', startDate: '2026-06-25T08:00', dueDate: '2026-07-02T08:00', returnDate: '2026-07-02T08:00', condition: 'Good', rateType: 'Daily', rateAmount: 7, deposit: 70, discount: 0, currency: 'USD', rentalCharge: 49, lateFee: 0, additionalCharges: 0, totalDue: 49, paid: 49, outstanding: 0, paymentStatus: 'Paid', createdBy: 'Nita (Staff)', status: 'Completed' },
  { id: id('rt', 24), rentalNo: 'RNT-2026-000024', customerId: 'rc-002', customer: 'Chan Sophea', phone: '+855 92 456 002', motorcycleId: 'mc-012', motorcycle: 'Suzuki Burgman Street', plate: 'PP-12K-3456', startDate: '2026-08-01T09:00', dueDate: '2026-08-08T09:00', returnDate: '2026-08-08T09:00', condition: 'Good', rateType: 'Daily', rateAmount: 13, deposit: 130, discount: 0, currency: 'USD', rentalCharge: 91, lateFee: 0, additionalCharges: 0, totalDue: 91, paid: 91, outstanding: 0, paymentStatus: 'Paid', createdBy: 'Sokha (Staff)', status: 'Completed' },
  { id: id('rt', 25), rentalNo: 'RNT-2026-000025', customerId: 'rc-009', customer: 'Leng Dara', phone: '+855 99 777 009', motorcycleId: 'mc-006', motorcycle: 'Honda Click 125i', plate: 'PP-6K-7890', startDate: '2026-08-05T09:00', dueDate: '2026-08-12T09:00', returnDate: '2026-08-13T15:00', condition: 'Damaged', rateType: 'Daily', rateAmount: 8, deposit: 80, discount: 0, currency: 'USD', rentalCharge: 64, lateFee: 8, additionalCharges: 45, totalDue: 117, paid: 117, outstanding: 0, paymentStatus: 'Paid', createdBy: 'Nita (Staff)', status: 'Completed' },
]

// One cancelled quote-style record keeps the status set complete.
const rentalsCancelled: AppRecord[] = [
  { id: id('rt', 30), rentalNo: 'RNT-2026-000030', customerId: 'rc-010', customer: 'Anna Petrova', phone: '+855 81 888 010', motorcycleId: 'mc-010', motorcycle: 'Yamaha NMAX 155', plate: 'PP-10K-1234', startDate: '2026-08-25T09:00', dueDate: '2026-09-01T09:00', rateType: 'Daily', rateAmount: 14, deposit: 140, discount: 0, currency: 'USD', rentalCharge: 98, lateFee: 0, additionalCharges: 0, totalDue: 0, paid: 0, outstanding: 0, status: 'Cancelled', createdBy: 'Nita (Staff)' },
]

const rentals = [...rentalsActive, ...rentalsCompleted, ...rentalsCancelled]

const rentalPayments: AppRecord[] = [
  { id: id('rp', 1), paymentNo: 'RNP-000001', rentalId: 'rt-001', rentalNo: 'RNT-2026-000001', customer: 'Sok Dara', amount: 90, currency: 'USD', paymentMethod: 'Cash', paidAt: '2026-08-20T09:10', reference: '', note: 'Partial on start' },
  { id: id('rp', 2), paymentNo: 'RNP-000002', rentalId: 'rt-002', rentalNo: 'RNT-2026-000002', customer: 'John Miller', amount: 60, currency: 'USD', paymentMethod: 'Card', paidAt: '2026-08-24T10:05', reference: 'CARD-8812', note: '' },
  { id: id('rp', 3), paymentNo: 'RNP-000003', rentalId: 'rt-003', rentalNo: 'RNT-2026-000003', customer: 'Touch Vannak', amount: 250, currency: 'USD', paymentMethod: 'Bank Transfer', paidAt: '2026-08-18T08:40', reference: 'ABA-108823', note: 'Monthly in full' },
  { id: id('rp', 4), paymentNo: 'RNP-000004', rentalId: 'rt-004', rentalNo: 'RNT-2026-000004', customer: 'Som Nita', amount: 40, currency: 'USD', paymentMethod: 'QR Payment', paidAt: '2026-08-26T14:10', reference: 'QR-5521', note: '' },
  { id: id('rp', 5), paymentNo: 'RNP-000005', rentalId: 'rt-005', rentalNo: 'RNT-2026-000005', customer: 'Chan Sophea', amount: 30, currency: 'USD', paymentMethod: 'Cash', paidAt: '2026-08-15T09:05', reference: '', note: 'Partial' },
  { id: id('rp', 6), paymentNo: 'RNP-000006', rentalId: 'rt-006', rentalNo: 'RNT-2026-000006', customer: 'David Chen', amount: 40, currency: 'USD', paymentMethod: 'Cash', paidAt: '2026-08-10T11:10', reference: '', note: '' },
  { id: id('rp', 7), paymentNo: 'RNP-000007', rentalId: 'rt-007', rentalNo: 'RNT-2026-000007', customer: 'Kim Sreyleap', amount: 50, currency: 'USD', paymentMethod: 'Bank Transfer', paidAt: '2026-08-08T08:15', reference: 'ACLEDA-77219', note: '' },
  { id: id('rp', 8), paymentNo: 'RNP-000008', rentalId: 'rt-008', rentalNo: 'RNT-2026-000008', customer: 'Nguyen Thi Lan', amount: 100, currency: 'USD', paymentMethod: 'Card', paidAt: '2026-08-12T13:05', reference: 'CARD-9034', note: '' },
]

const rentalCharges: AppRecord[] = [
  { id: id('rg', 1), chargeNo: 'RNC-000001', rentalId: 'rt-007', rentalNo: 'RNT-2026-000007', customer: 'Kim Sreyleap', chargeType: 'Cleaning', description: 'Deep clean after muddy trip', amount: 5, currency: 'USD', chargeToCustomer: 'Yes', createdBy: 'Sokha (Staff)' },
  { id: id('rg', 2), chargeNo: 'RNC-000002', rentalId: 'rt-025', rentalNo: 'RNT-2026-000025', customer: 'Leng Dara', chargeType: 'Damage', description: 'Scratched side panel + broken mirror', amount: 45, currency: 'USD', chargeToCustomer: 'Yes', createdBy: 'Nita (Staff)' },
  { id: id('rg', 3), chargeNo: 'RNC-000003', rentalId: 'rt-013', rentalNo: 'RNT-2026-000013', customer: 'John Miller', chargeType: 'Lost item', description: 'Missing helmet', amount: 15, currency: 'USD', chargeToCustomer: 'Yes', createdBy: 'Nita (Staff)' },
]

// Operating expenses for the Income & Expense screen (income = rental payments).
const rentalExpenses: AppRecord[] = [
  { id: id('rx', 1), expenseNo: 'RNX-000001', date: '2026-06-05', expenseType: 'Rent', description: 'Shop rent June 2026', amount: 350, currency: 'USD', createdBy: 'Admin' },
  { id: id('rx', 2), expenseNo: 'RNX-000002', date: '2026-06-28', expenseType: 'Maintenance', description: 'Oil change x6 + brake pads', amount: 120, currency: 'USD', createdBy: 'Sokha (Staff)' },
  { id: id('rx', 3), expenseNo: 'RNX-000003', date: '2026-07-05', expenseType: 'Rent', description: 'Shop rent July 2026', amount: 350, currency: 'USD', createdBy: 'Admin' },
  { id: id('rx', 4), expenseNo: 'RNX-000004', date: '2026-07-15', expenseType: 'Salary', description: 'Staff salary July 2026', amount: 600, currency: 'USD', createdBy: 'Admin' },
  { id: id('rx', 5), expenseNo: 'RNX-000005', date: '2026-07-21', expenseType: 'Maintenance', description: 'MC-011 engine repair', amount: 185, currency: 'USD', createdBy: 'Sokha (Staff)' },
  { id: id('rx', 6), expenseNo: 'RNX-000006', date: '2026-08-02', expenseType: 'Rent', description: 'Shop rent August 2026', amount: 350, currency: 'USD', createdBy: 'Admin' },
  { id: id('rx', 7), expenseNo: 'RNX-000007', date: '2026-08-10', expenseType: 'Marketing', description: 'Facebook ads campaign', amount: 60, currency: 'USD', createdBy: 'Admin' },
  { id: id('rx', 8), expenseNo: 'RNX-000008', date: '2026-08-18', expenseType: 'Fuel', description: 'Delivery fuel top-up', amount: 25, currency: 'USD', createdBy: 'Nita (Staff)' },
  { id: id('rx', 9), expenseNo: 'RNX-000009', date: '2026-08-25', expenseType: 'Maintenance', description: 'Tire replacement MC-002', amount: 46, currency: 'USD', createdBy: 'Sokha (Staff)' },
]

/** Rental seed keyed by collection; merged into the mock DB in `repositories/mock/db.ts`. */
export function createRentalSeed(): Record<string, AppRecord[]> {
  return {
    motorcycles: motorcycles.map(stamp),
    rentalCustomers: rentalCustomers.map(stamp),
    rentals: rentals.map(stamp),
    rentalPayments: rentalPayments.map(stamp),
    rentalCharges: rentalCharges.map(stamp),
    rentalExpenses: rentalExpenses.map(stamp),
  }
}
