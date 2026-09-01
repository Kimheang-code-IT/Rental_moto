from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.common import CamelModel


class RentalLineInput(CamelModel):
    motorcycle_id: str
    start_date: datetime
    due_date: datetime
    deposit: Decimal = Decimal("0")
    discount: Decimal = Decimal("0")
    note: str | None = None


class RentalCreateRequest(CamelModel):
    customer_id: str
    lines: list[RentalLineInput] = Field(min_length=1)
    discount: Decimal = Decimal("0")
    tax_percent: Decimal = Decimal("0")
    paid_amount: Decimal = Decimal("0")
    payment_method: str | None = None
    currency: str = "USD"
    note: str | None = None


class CloseChargeInput(CamelModel):
    charge_type: str = "Other"
    description: str | None = None
    amount: Decimal = Field(ge=0)
    charge_to_customer: str = "Yes"


class FinalPaymentInput(CamelModel):
    amount: Decimal = Field(ge=0)
    payment_method: str = "Cash"
    reference: str | None = None
    note: str | None = None
    paid_at: datetime | None = None


class RentalCloseRequest(CamelModel):
    return_date: datetime | None = None
    condition: str | None = None
    return_note: str | None = None
    late_fee: Decimal = Decimal("0")
    charges: list[CloseChargeInput] = []
    final_payment: FinalPaymentInput | None = None
    motorcycle_status: str | None = None


class RentalCancelRequest(CamelModel):
    reason: str | None = None


class PaymentRecordRequest(CamelModel):
    rental_id: str
    amount: Decimal = Field(gt=0)
    payment_method: str = "Cash"
    paid_at: datetime | None = None
    reference: str | None = None
    note: str | None = None


class PaymentUpdateRequest(CamelModel):
    amount: Decimal | None = None
    payment_method: str | None = None
    paid_at: datetime | None = None
    reference: str | None = None
    note: str | None = None


class ChargeRecordRequest(CamelModel):
    rental_id: str
    charge_type: str = "Other"
    description: str | None = None
    amount: Decimal = Field(gt=0)
    charge_to_customer: str = "Yes"


class ChargeUpdateRequest(CamelModel):
    charge_type: str | None = None
    description: str | None = None
    amount: Decimal | None = None
    charge_to_customer: str | None = None


class ExpenseRecordRequest(CamelModel):
    date: datetime
    expense_type: str = "Other"
    description: str | None = None
    amount: Decimal = Field(gt=0)
    currency: str = "USD"


class ExpenseUpdateRequest(CamelModel):
    date: datetime | None = None
    expense_type: str | None = None
    description: str | None = None
    amount: Decimal | None = None
    currency: str | None = None


class PaymentResponse(CamelModel):
    id: str
    payment_no: str
    rental_id: str
    rental_no: str | None = None
    customer: str | None = None
    amount: Decimal
    currency: str
    payment_method: str
    paid_at: datetime
    reference: str | None = None
    note: str | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime


class ChargeResponse(CamelModel):
    id: str
    charge_no: str
    rental_id: str
    rental_no: str | None = None
    customer: str | None = None
    charge_type: str
    description: str | None = None
    amount: Decimal
    currency: str
    charge_to_customer: str
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime


class ExpenseResponse(CamelModel):
    id: str
    expense_no: str
    date: datetime
    expense_type: str
    description: str | None = None
    amount: Decimal
    currency: str
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime


class RentalResponse(CamelModel):
    id: str
    rental_no: str
    customer_id: str
    motorcycle_id: str
    customer: str
    phone: str | None = None
    motorcycle: str
    plate: str | None = None
    start_date: datetime
    due_date: datetime
    duration_days: int
    rate_type: str
    rate_amount: Decimal
    deposit: Decimal
    discount: Decimal
    tax_percent: Decimal
    tax: Decimal
    currency: str
    rental_charge: Decimal
    late_fee: Decimal
    additional_charges: Decimal
    total_due: Decimal
    paid: Decimal
    outstanding: Decimal
    payment_method: str | None = None
    payment_status: str | None = None
    return_date: datetime | None = None
    condition: str | None = None
    return_note: str | None = None
    note: str | None = None
    created_by: str | None = None
    status: str
    cancelled_at: datetime | None = None
    cancel_reason: str | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
