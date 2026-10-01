from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from app.config import settings
from app.database.models import Order, Customer


class InvoiceGenerator:
    def __init__(self):
        self.output_dir = settings.INVOICES_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_pdf_invoice(
        self,
        invoice_number: str,
        order: Order,
        customer: Customer,
        items: List[Dict[str, Any]]
    ) -> Path:
        """Generates a professional multi-item small-business PDF invoice."""
        pdf_filename = f"{invoice_number}.pdf"
        file_path = self.output_dir / pdf_filename

        doc = SimpleDocTemplate(
            str(file_path),
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "InvoiceTitle",
            parent=styles["Heading1"],
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#1e293b"),
            fontName="Helvetica-Bold"
        )
        subtitle_style = ParagraphStyle(
            "InvoiceSubtitle",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#64748b")
        )
        section_style = ParagraphStyle(
            "SectionHeader",
            parent=styles["Heading3"],
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#0f172a"),
            fontName="Helvetica-Bold"
        )
        body_style = ParagraphStyle(
            "InvoiceBody",
            parent=styles["Normal"],
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#334155")
        )

        elements = []

        # Store Header
        elements.append(Paragraph(settings.STORE_NAME, title_style))
        elements.append(Paragraph(f"{settings.STORE_ADDRESS} | Phone: {settings.STORE_PHONE} | Email: {settings.STORE_EMAIL}", subtitle_style))
        elements.append(Spacer(1, 15))

        # Metadata Table
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        meta_data = [
            [Paragraph(f"<b>Invoice No:</b> {invoice_number}", body_style), Paragraph(f"<b>Date:</b> {date_str}", body_style)],
            [Paragraph(f"<b>Order No:</b> {order.order_number}", body_style), Paragraph("<b>Payment Provider:</b> eSewa ePay v2", body_style)],
            [Paragraph("<b>Payment Status:</b> <font color='green'>PAID</font>", body_style), Paragraph(f"<b>Discord User:</b> {customer.discord_username}", body_style)]
        ]
        meta_table = Table(meta_data, colWidths=[270, 270])
        meta_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(meta_table)
        elements.append(Spacer(1, 15))

        # Customer & Delivery Details
        elements.append(Paragraph("Delivery Information", section_style))
        elements.append(Spacer(1, 4))
        customer_info = [
            [Paragraph("<b>Customer Name:</b>", body_style), Paragraph(customer.name or customer.discord_username, body_style)],
            [Paragraph("<b>Mobile Number:</b>", body_style), Paragraph(customer.phone or "Not Provided", body_style)],
            [Paragraph("<b>Delivery Address:</b>", body_style), Paragraph(customer.address or "Kathmandu Valley", body_style)],
            [Paragraph("<b>Location Pin/Link:</b>", body_style), Paragraph(customer.location_link or "N/A", body_style)]
        ]
        cust_table = Table(customer_info, colWidths=[120, 420])
        cust_table.setStyle(TableStyle([
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(cust_table)
        elements.append(Spacer(1, 15))

        # Items Table (supports multiple purchased items)
        elements.append(Paragraph("Purchased Items", section_style))
        elements.append(Spacer(1, 4))
        
        items_data = [
            [
                Paragraph("<b>Item Description</b>", body_style),
                Paragraph("<b>Qty</b>", body_style),
                Paragraph("<b>Unit Price</b>", body_style),
                Paragraph("<b>Total</b>", body_style)
            ]
        ]

        subtotal = 0.0
        for item in items:
            p_name = item.get("product_name") or item.get("name", "Clothing Item")
            qty = item.get("quantity", 1)
            u_price = item.get("unit_price", 0.0)
            t_price = item.get("total_price", u_price * qty)
            subtotal += t_price

            items_data.append([
                Paragraph(p_name, body_style),
                Paragraph(str(qty), body_style),
                Paragraph(f"Rs. {u_price:.2f}", body_style),
                Paragraph(f"Rs. {t_price:.2f}", body_style)
            ])

        # Summary rows
        items_data.append(["", "", Paragraph("<b>Delivery Fee:</b>", body_style), Paragraph("Rs. 0.00", body_style)])
        items_data.append(["", "", Paragraph("<b>Tax:</b>", body_style), Paragraph("Rs. 0.00", body_style)])
        items_data.append(["", "", Paragraph("<b>Grand Total:</b>", body_style), Paragraph(f"<b>Rs. {order.total_amount:.2f}</b>", body_style)])

        items_table = Table(items_data, colWidths=[260, 50, 110, 120])
        items_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#94a3b8")),
            ("LINEBELOW", (0, 1), (-1, -4), 0.5, colors.HexColor("#cbd5e1")),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(items_table)
        elements.append(Spacer(1, 25))

        elements.append(Paragraph("Thank you for shopping with Pasale Dai Collections!", subtitle_style))
        elements.append(Paragraph("Delivery will be arranged manually within 48 hours. Please keep this invoice for your records.", subtitle_style))

        doc.build(elements)
        return file_path