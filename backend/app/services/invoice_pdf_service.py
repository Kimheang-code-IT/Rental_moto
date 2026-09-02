"""Frontend-matched A5 rental invoice PDF generation for Telegram delivery."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.rental import RentalRepository


BLUE = "#2463DF"
INK = "#172033"
MUTED = "#64748B"
BORDER = "#D8E1EE"
DEFAULT_ADDRESS = "St. 271, Toul Tum Poung, Phnom Penh, Cambodia"
DEFAULT_PHONE = "+855 23 555 123"
DEFAULT_EMAIL = "info@hollywingmotor.com"

LABELS = {
    "invoice": ("វិក្កយបត្រ", "INVOICE"),
    "motorcycle_rental": ("ការជួលម៉ូតូ", "MOTORCYCLE RENTAL"),
    "invoice_no": ("លេខវិក្កយបត្រ", "Invoice No."),
    "payment_method": ("វិធីបង់ប្រាក់", "Payment Method"),
    "created": ("ថ្ងៃបង្កើត", "Created"),
    "deposit_date": ("ថ្ងៃដាក់ប្រាក់កក់", "Deposit Date"),
    "customer": ("អតិថិជន", "Customer"),
    "phone": ("ទូរស័ព្ទ", "Phone"),
    "start_date": ("ថ្ងៃចាប់ផ្តើម", "Start Date"),
    "return_date": ("ថ្ងៃប្រគល់", "Return Date"),
    "no": ("ល.រ", "No"),
    "motorcycle": ("ម៉ូតូ", "Motorcycle"),
    "plate": ("លេខផ្ទាំង", "Plate"),
    "days": ("ថ្ងៃ", "Day(s)"),
    "unit_price": ("តម្លៃឯកតា", "Unit price"),
    "amount": ("ចំនួនទឹកប្រាក់", "Amount"),
    "subtotal": ("សរុបរង", "Subtotal"),
    "deposit": ("ប្រាក់កក់", "Deposit"),
    "discount": ("បញ្ចុះតម្លៃ", "Discount"),
    "tax": ("ពន្ធ", "Tax"),
    "total": ("សរុប", "TOTAL"),
    "paid": ("បានបង់", "Paid"),
    "outstanding": ("នៅជំពាក់", "Outstanding"),
    "terms": ("លក្ខខណ្ឌ", "TERMS & CONDITIONS"),
    "late_fee": ("ថ្លៃយឺត", "Late fee"),
    "additional_charges": ("ការគិតថ្លៃបន្ថែម", "Additional charges"),
    "thank_you": ("អរគុណដែលបានជ្រើសរើស", "Thank you for choosing"),
}

TERMS_KM = "ត្រូវបង់ប្រាក់តាមកិច្ចសន្យាជួល។ ប្រាក់កក់នឹងប្រគល់វិញបន្ទាប់ពីត្រួតពិនិត្យម៉ូតូរួច។"
TERMS_EN = (
    "Payment is due according to the rental agreement. The deposit is refundable "
    "after the motorcycle passes return inspection."
)


class InvoicePdfService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.rentals = RentalRepository(session)

    async def render_rental_invoice(self, rental_no: str, final: bool = False) -> tuple[bytes | None, str]:
        rental = await self.rentals.get_by_no(rental_no)
        if rental is None:
            return None, ""

        try:
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_CENTER, TA_RIGHT
            from reportlab.lib.pagesizes import A5
            from reportlab.lib.styles import ParagraphStyle
            from reportlab.lib.units import mm
            from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        except ImportError:
            return None, ""

        from app.services.admin_service import SettingService

        settings = SettingService(self.session)
        app_config = await settings.get_app_config(mask=False)
        localization = app_config.get("localization") or {}

        khmer_font, khmer_bold_font, khmer_enabled = _register_fonts()
        regular_font = "Helvetica"
        bold_font = "Helvetica-Bold"
        # Keep these values identical to RentalInvoiceBody.vue. Date/time and
        # currency remain driven by the shared localization configuration.
        company_name = "HollyWing Motor"
        company_address = DEFAULT_ADDRESS
        company_phone = DEFAULT_PHONE
        company_email = DEFAULT_EMAIL
        contact = " · ".join(value for value in (company_phone, company_email) if value)

        def style(name: str, **kwargs):
            defaults = {
                "fontName": regular_font,
                "fontSize": 6.5,
                "leading": 8,
                "textColor": colors.HexColor(INK),
                "spaceAfter": 0,
                "spaceBefore": 0,
            }
            defaults.update(kwargs)
            return ParagraphStyle(name, **defaults)

        normal = style("invoice-normal")
        value_right = style("invoice-value-right", alignment=TA_RIGHT, fontSize=6.4, leading=8)
        money_right = style("invoice-money-right", alignment=TA_RIGHT, fontSize=6.4, leading=8)
        center = style("invoice-center", alignment=TA_CENTER, fontSize=6.1, leading=7.2)
        title = style("invoice-title", alignment=TA_CENTER, fontName=bold_font, fontSize=9, leading=10)
        company = style("invoice-company", fontName=bold_font, fontSize=11, leading=12, textColor=colors.HexColor("#0B4F91"))
        company_sub = style("invoice-company-sub", fontSize=5.7, leading=7, textColor=colors.HexColor(MUTED))
        contact_style = style("invoice-contact", alignment=TA_RIGHT, fontSize=5.8, leading=7, textColor=colors.HexColor("#334155"))
        section = style("invoice-section", fontName=bold_font, fontSize=4.8, leading=6, textColor=colors.HexColor(MUTED))
        terms = style("invoice-terms", fontSize=5.4, leading=7, textColor=colors.HexColor("#475569"))
        total_style = style("invoice-total", fontName=bold_font, fontSize=9, leading=10)
        total_value = style("invoice-total-value", fontName=bold_font, fontSize=9, leading=10, alignment=TA_RIGHT)
        white_header = style("invoice-white-header", alignment=TA_CENTER, fontName=bold_font, fontSize=5.7, leading=6.8, textColor=colors.white)
        white_footer = style("invoice-white-footer", alignment=TA_CENTER, fontName=bold_font, fontSize=5.5, leading=7, textColor=colors.white)

        def p(text: object, paragraph_style=normal):
            return Paragraph(_xml(str(text if text not in (None, "") else "—")), paragraph_style)

        def khmer_style(paragraph_style, *, bold: bool = False):
            return ParagraphStyle(
                f"{paragraph_style.name}-khmer-{'bold' if bold else 'regular'}",
                parent=paragraph_style,
                fontName=khmer_bold_font if bold else khmer_font,
                shaping=1,
            )

        def bilingual(key: str, paragraph_style=normal, *, english_color: str = MUTED):
            km, en = LABELS[key]
            if not khmer_enabled:
                return p(en, paragraph_style)
            return Paragraph(
                f'<font name="{khmer_bold_font}">{_xml(km)}</font><br/>'
                f'<font name="{regular_font}" color="{english_color}" size="5.2">{_xml(en)}</font>',
                khmer_style(paragraph_style, bold=True),
            )

        payments = sorted(
            list(getattr(rental, "payments", None) or []),
            key=lambda item: getattr(item, "paid_at", None) or datetime.min,
        )
        charges = [
            charge
            for charge in list(getattr(rental, "charges", None) or [])
            if str(getattr(charge, "charge_to_customer", "Yes")) != "No"
        ]
        methods = list(dict.fromkeys(
            str(getattr(payment, "payment_method", ""))
            for payment in payments
            if getattr(payment, "payment_method", None)
        ))
        payment_method = ", ".join(methods) or str(getattr(rental, "payment_method", None) or "—")

        line_items: list[tuple[str, str, object, Decimal, Decimal]] = []
        rental_charge = _decimal(getattr(rental, "rental_charge", 0))
        rate_amount = _decimal(getattr(rental, "rate_amount", 0))
        duration_days = max(1, int(getattr(rental, "duration_days", 1) or 1))
        motorcycle = str(getattr(rental, "motorcycle", None) or "—")
        plate = str(getattr(rental, "plate", None) or "—")
        if rental_charge > 0 or motorcycle != "—":
            line_items.append((motorcycle, plate, duration_days, rate_amount, rental_charge or rate_amount * duration_days))

        late_fee = _decimal(getattr(rental, "late_fee", 0))
        if late_fee > 0:
            line_items.append((LABELS["late_fee"][1], "—", "—", late_fee, late_fee))

        recorded_additional = Decimal("0")
        for charge in charges:
            charge_amount = _decimal(getattr(charge, "amount", 0))
            if charge_amount <= 0:
                continue
            recorded_additional += charge_amount
            charge_label = " · ".join(
                str(value) for value in (getattr(charge, "charge_type", None), getattr(charge, "description", None)) if value
            )
            line_items.append((charge_label or LABELS["additional_charges"][1], "—", "—", charge_amount, charge_amount))

        additional = _decimal(getattr(rental, "additional_charges", 0))
        additional_fallback = max(additional - recorded_additional, Decimal("0"))
        if additional_fallback > 0:
            line_items.append((LABELS["additional_charges"][1], "—", "—", additional_fallback, additional_fallback))

        subtotal = sum((item[4] for item in line_items), Decimal("0"))
        deposit = max(_decimal(getattr(rental, "deposit", 0)), Decimal("0"))
        discount = max(_decimal(getattr(rental, "discount", 0)), Decimal("0"))
        stored_tax = _decimal(getattr(rental, "tax", 0))
        total_due = _decimal(getattr(rental, "total_due", subtotal - discount + stored_tax))
        tax = stored_tax if stored_tax > 0 else max(total_due - (subtotal - discount), Decimal("0"))
        paid = max(_decimal(getattr(rental, "paid", 0)), Decimal("0"))
        outstanding = max(_decimal(getattr(rental, "outstanding", 0)), Decimal("0"))
        currency = str(getattr(rental, "currency", None) or localization.get("currency") or "USD")

        created_at = getattr(rental, "created_at", None) or getattr(rental, "start_date", None)
        deposit_date = ""
        if deposit > 0:
            deposit_date = _format_datetime(
                getattr(payments[0], "paid_at", None) if payments else getattr(rental, "start_date", None),
                localization,
            )
        return_date = getattr(rental, "return_date", None) or getattr(rental, "due_date", None)
        invoice_no = f"INV-{str(rental.rental_no).replace('RNT-', '')}"

        buffer = BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=A5,
            rightMargin=9 * mm,
            leftMargin=9 * mm,
            topMargin=9 * mm,
            bottomMargin=9 * mm,
            title=f"{'Final ' if final else ''}Invoice {invoice_no}",
            author=company_name,
            subject=f"Rental {rental.rental_no}",
        )
        story = []

        logo_path = Path(__file__).resolve().parents[1] / "assets" / "logo.png"
        brand_cell = []
        if logo_path.exists():
            brand_cell.append(Image(str(logo_path), width=13 * mm, height=13 * mm))
        brand_text = Table(
            [[p(company_name, company)], [p(LABELS["motorcycle_rental"][1], company_sub)]],
            colWidths=[46 * mm],
            style=TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]),
        )
        brand = Table([brand_cell + [brand_text]] if brand_cell else [[brand_text]], colWidths=([15 * mm, 46 * mm] if brand_cell else [61 * mm]))
        brand.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 2), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        contact_lines = "<br/>".join(_xml(value) for value in (company_address, contact) if value)
        header = Table(
            [[brand, Paragraph(contact_lines, contact_style)]],
            colWidths=[64 * mm, 66 * mm],
            style=TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LINEBELOW", (0, 0), (-1, -1), 1, colors.HexColor(INK)),
            ]),
        )
        story.extend([header, Spacer(1, 3 * mm), bilingual("invoice", title), Spacer(1, 3 * mm)])

        left_rows = [
            [bilingual("invoice_no"), p(invoice_no, value_right)],
            [bilingual("payment_method"), p(payment_method, value_right)],
            [bilingual("created"), p(_format_datetime(created_at, localization), value_right)],
        ]
        if deposit_date:
            left_rows.append([bilingual("deposit_date"), p(deposit_date, value_right)])
        right_rows = [
            [bilingual("customer"), p(getattr(rental, "customer", None), value_right)],
            [bilingual("phone"), p(getattr(rental, "phone", None), value_right)],
            [bilingual("start_date"), p(_format_datetime(getattr(rental, "start_date", None), localization), value_right)],
            [bilingual("return_date"), p(_format_datetime(return_date, localization), value_right)],
        ]

        def info_block(title_text: str, rows: list[list]):
            table = Table(rows, colWidths=[27 * mm, 34 * mm], hAlign="LEFT")
            table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 1.2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2),
            ]))
            return Table(
                [[p(title_text.upper(), section)], [table]],
                colWidths=[61 * mm],
                style=TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]),
            )

        info = Table(
            [[info_block("Invoice Info", left_rows), info_block("Customer Info", right_rows)]],
            colWidths=[65 * mm, 65 * mm],
            style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]),
        )
        story.extend([info, Spacer(1, 2 * mm)])

        header_row = [
            bilingual(key, white_header, english_color="#FFFFFF")
            for key in ("no", "motorcycle", "plate", "days", "unit_price", "amount")
        ]
        item_rows = [header_row]
        for index, item in enumerate(line_items, start=1):
            item_rows.append([
                p(index, center),
                p(item[0], normal),
                p(item[1], normal),
                p(item[2], center),
                p(_money(item[3], currency), money_right),
                Paragraph(f"<b>{_xml(_money(item[4], currency))}</b>", money_right),
            ])
        if not line_items:
            item_rows.append([p("No invoice items", center), "", "", "", "", ""])
        lines_table = Table(item_rows, colWidths=[10 * mm, 37 * mm, 22 * mm, 15 * mm, 23 * mm, 23 * mm], repeatRows=1)
        lines_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BLUE)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 1), (-1, -1), 0.5, colors.HexColor(BORDER)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, 0), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 3.5),
            ("TOPPADDING", (0, 1), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
        ]
        if not line_items:
            lines_style.append(("SPAN", (0, 1), (-1, 1)))
        lines_table.setStyle(TableStyle(lines_style))
        story.extend([lines_table, Spacer(1, 3 * mm)])

        terms_body = [[bilingual("terms", section)]]
        if khmer_enabled:
            terms_body.append([
                Paragraph(
                    f'<font name="{khmer_font}">{_xml(TERMS_KM)}</font>',
                    khmer_style(terms),
                )
            ])
        terms_body.append([p(TERMS_EN, terms)])
        terms_block = Table(terms_body, colWidths=[72 * mm])
        terms_block.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ]))

        totals_data = [
            [bilingual("subtotal"), p(_money(subtotal, currency), money_right)],
            [bilingual("deposit"), p(_money(deposit, currency), money_right)],
            [bilingual("discount"), p(_money(discount, currency), money_right)],
            [bilingual("tax"), p(_money(tax, currency), money_right)],
            [bilingual("total", total_style), p(_money(total_due, currency), total_value)],
            [bilingual("paid"), p(_money(paid, currency), money_right)],
            [bilingual("outstanding"), p(_money(outstanding, currency), money_right)],
        ]
        totals_table = Table(totals_data, colWidths=[27 * mm, 29 * mm])
        totals_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 1.2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2),
            ("LINEBELOW", (0, 3), (-1, 3), 0.8, colors.HexColor(INK)),
            ("TOPPADDING", (0, 4), (-1, 4), 4),
            ("BOTTOMPADDING", (0, 4), (-1, 4), 4),
        ]))
        summary = Table(
            [[terms_block, totals_table]],
            colWidths=[74 * mm, 56 * mm],
            style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]),
        )
        story.extend([summary, Spacer(1, 4 * mm)])

        thank_km, thank_en = LABELS["thank_you"]
        footer_lines = [f'<font name="{regular_font}">{_xml(f"{thank_en} {company_name}")}</font>']
        if khmer_enabled:
            footer_lines.insert(
                0,
                f'<font name="{khmer_bold_font}">{_xml(thank_km)}</font> '
                f'<font name="{regular_font}">{_xml(company_name)}</font>',
            )
        footer = Table(
            [[Paragraph("<br/>".join(footer_lines), khmer_style(white_footer, bold=True) if khmer_enabled else white_footer)]],
            colWidths=[130 * mm],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(BLUE)),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]),
        )
        story.append(footer)

        document.build(story)
        filename = f"{'Final-' if final else ''}Invoice-{rental.rental_no}.pdf"
        return buffer.getvalue(), filename


def _register_fonts() -> tuple[str, str, bool]:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = [
        (Path("/usr/share/fonts/truetype/noto/NotoSansKhmer-Regular.ttf"), Path("/usr/share/fonts/truetype/noto/NotoSansKhmer-Bold.ttf")),
        (Path("/usr/share/fonts/truetype/khmeros/KhmerOS.ttf"), Path("/usr/share/fonts/truetype/khmeros/KhmerOS_bold.ttf")),
        (Path("C:/Windows/Fonts/KhmerUI.ttf"), Path("C:/Windows/Fonts/KhmerUIb.ttf")),
    ]
    for regular, bold in candidates:
        if not regular.exists():
            continue
        try:
            if "InvoiceKhmer" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("InvoiceKhmer", str(regular), shapable=True))
            if "InvoiceKhmerBold" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("InvoiceKhmerBold", str(bold if bold.exists() else regular), shapable=True))
            return "InvoiceKhmer", "InvoiceKhmerBold", True
        except Exception:
            continue
    return "Helvetica", "Helvetica-Bold", False


def _decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except Exception:
        return Decimal("0")


def _money(value: Decimal, currency: str) -> str:
    symbols = {"USD": "$", "KHR": "៛", "EUR": "€", "GBP": "£"}
    symbol = symbols.get(currency.upper())
    return f"{symbol}{value:,.2f}" if symbol else f"{value:,.2f} {currency}"


def _format_datetime(value: object, config: dict) -> str:
    if value in (None, ""):
        return "—"
    parsed = value
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    if not isinstance(parsed, datetime):
        return str(parsed)
    timezone_name = str(config.get("timezone") or "Asia/Phnom_Penh")
    try:
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(ZoneInfo(timezone_name))
    except Exception:
        pass
    date_format = str(config.get("dateFormat") or "DD/MM/YYYY")
    time_format = str(config.get("timeFormat") or "HH:mm")
    tokens = {
        "DD": f"{parsed.day:02d}", "MM": f"{parsed.month:02d}", "YYYY": f"{parsed.year:04d}",
        "YY": f"{parsed.year % 100:02d}", "HH": f"{parsed.hour:02d}",
        "hh": f"{((parsed.hour - 1) % 12) + 1:02d}", "mm": f"{parsed.minute:02d}",
        "ss": f"{parsed.second:02d}", "A": "AM" if parsed.hour < 12 else "PM",
    }
    result = f"{date_format} {time_format}"
    for token in ("YYYY", "YY", "DD", "MM", "HH", "hh", "mm", "ss", "A"):
        result = result.replace(token, tokens[token])
    return result


def _xml(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
