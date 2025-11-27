# app/utils/export.py
from __future__ import annotations
import io, json, logging
from datetime import datetime, timezone, timedelta
from textwrap import wrap
from typing import Any, Dict
from reportlab.platypus import Image as RLImage
import xlsxwriter
from app.utils import azure_blob

logger = logging.getLogger(__name__)
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle,
    Spacer, PageBreak, LongTable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics.charts.piecharts import Pie
from reportlab.lib.enums import TA_CENTER

# Theme 
THEME = {
    "header_bg": "#BDD7EE",
    "zebra1": "#FFFFFF",
    "zebra2": "#E1E9EE",
    "total_bg": "#C6E0B4",
    "palette": ["#8DA6D7", "#E2DBBB", "#97BAEB", "#F28282", "#B9E7EB", "#E0C0A8"]
}
# Currency symbols for formatting
CURRENCY_SYMBOLS = {
    "USD": "$",
    "INR": "₹",
    "EUR": "€",
    "GBP": "£",
    "CAD": "C$",
    "SGD": "S$",
    "AUD": "A$",
    "NZD": "NZ$",
    "JPY": "¥",
    "CHF": "CHF",
    "CNY": "¥",
    "SEK": "kr",
    "NOK": "kr",
}

IST = timezone(timedelta(hours=5, minutes=30))

# JSON Export
def generate_json_data(scope: Dict[str, Any]) -> Dict[str, Any]:
    return scope

# Excel Export
def generate_xlsx(scope: Dict[str, Any]) -> io.BytesIO:
    try:
        from xlsxwriter.utility import xl_col_to_name
        data = scope
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {"in_memory": True})
        currency = (data.get("overview", {}) or {}).get("Currency", "USD").upper()
        symbol = CURRENCY_SYMBOLS.get(currency, "$")


        # ---------- Formats ----------
        fmt_th = wb.add_format({
            "bold": True, "bg_color": THEME["header_bg"],
            "border": 1, "align": "center", "text_wrap": True
        })
        fmt_z1 = wb.add_format({"border": 1, "bg_color": THEME["zebra1"]})
        fmt_z2 = wb.add_format({"border": 1, "bg_color": THEME["zebra2"]})
        fmt_date = wb.add_format({"border": 1, "num_format": "yyyy-mm-dd"})
        fmt_num = wb.add_format({"border": 1, "num_format": "0.00"})
        fmt_money = wb.add_format({
            "border": 1,
            "num_format": f'"{symbol}"#,##0.00'
        })

        fmt_total = wb.add_format({"bold": True, "border": 1, "bg_color": THEME["total_bg"]})

        # --------- Overview ----------
        ws_ov = wb.add_worksheet("Overview")
        ws_ov.write_row("A1", ["Field", "Value"], fmt_th)

        # Include discount information if present
        overview_data = data.get("overview", {})
        discount_pct = data.get("discount_percentage", 0)

        for i, (k, v) in enumerate(overview_data.items(), start=2):
            zfmt = fmt_z1 if i % 2 else fmt_z2
            ws_ov.write(f"A{i}", k, zfmt)
            ws_ov.write(f"B{i}", str(v), zfmt)

        # Add discount row if discount was applied
        if discount_pct and isinstance(discount_pct, (int, float)) and discount_pct > 0:
            next_row = len(overview_data.items()) + 2
            zfmt = fmt_z1 if next_row % 2 else fmt_z2
            ws_ov.write(f"A{next_row}", "Discount Applied", zfmt)
            ws_ov.write(f"B{next_row}", f"{discount_pct}% discount applied to all costs", zfmt)

        ws_ov.set_column("A:A", 20)
        ws_ov.set_column("B:B", 100)

        # -------- Activities (Week-based Gantt) ----------
        ws_a = wb.add_worksheet("Activities")

        # Parse activities and find project timeline
        activities = data.get("activities", [])
        parsed_activities = []
        starts, ends = [], []

        for a in activities:
            try:
                s = datetime.fromisoformat(a["Start Date"])
                e = datetime.fromisoformat(a["End Date"])
                starts.append(s)
                ends.append(e)
                parsed_activities.append((a, s, e))
            except:
                # Skip activities with invalid dates
                pass

        if parsed_activities and starts and ends:
            # Calculate project start (earliest Monday on or before min start date)
            min_start = min(starts)
            max_end = max(ends)

            # Find the Monday of the week containing min_start
            project_start = min_start - timedelta(days=min_start.weekday())

            # Calculate total weeks needed (round up)
            total_days = (max_end - project_start).days + 1
            num_weeks = (total_days + 6) // 7  # Round up to nearest week

            # Create headers: ID, Activities, Owner, Week 1, Week 2, ..., Week N
            headers = ["ID", "Activities", "Owner"] + [f"Week {i+1}" for i in range(num_weeks)]
            ws_a.write_row("A1", headers, fmt_th)

            # Set column widths
            ws_a.set_column("A:A", 5)   # ID
            ws_a.set_column("B:B", 35)  # Activities
            ws_a.set_column("C:C", 15)  # Owner
            # Week columns - narrower to fit more weeks
            for i in range(3, 3 + num_weeks):
                ws_a.set_column(i, i, 6)

            # Format for week cells with blue background (timeline bar)
            fmt_week_bar = wb.add_format({
                "bg_color": "#4D96FF",
                "border": 1,
                "align": "center"
            })

            # Format for empty week cells
            fmt_week_empty = wb.add_format({
                "border": 1,
                "align": "center"
            })

            # Write each activity
            for row_idx, (a, start_date, end_date) in enumerate(parsed_activities, start=2):
                zfmt = fmt_z1 if row_idx % 2 else fmt_z2

                # Write ID, Activities, Owner
                ws_a.write(row_idx-1, 0, a.get("ID", row_idx-1), zfmt)
                ws_a.write(row_idx-1, 1, a.get("Activities", ""), zfmt)
                ws_a.write(row_idx-1, 2, a.get("Owner", ""), zfmt)

                # Calculate which weeks this activity spans
                activity_start_day = (start_date - project_start).days
                activity_end_day = (end_date - project_start).days

                # Calculate week indices (0-based)
                start_week = activity_start_day // 7
                end_week = activity_end_day // 7

                # Fill in the week columns
                for week_idx in range(num_weeks):
                    col_idx = 3 + week_idx  # Week columns start at column 3 (0-indexed)

                    if start_week <= week_idx <= end_week:
                        # This week is part of the activity timeline
                        ws_a.write(row_idx-1, col_idx, "", fmt_week_bar)
                    else:
                        # Empty week cell
                        ws_a.write(row_idx-1, col_idx, "", fmt_week_empty)
        else:
            # Fallback if no valid activities with dates
            headers = ["ID", "Activities", "Owner"]
            ws_a.write_row("A1", headers, fmt_th)
            ws_a.set_column("A:A", 5)
            ws_a.set_column("B:B", 35)
            ws_a.set_column("C:C", 15)


        # -------- Resources Plan --------
        ws_r = wb.add_worksheet("Resources Plan")
        if data.get("resourcing_plan"):
            month_keys = [k for k in data["resourcing_plan"][0] if len(k.split()) == 2]
            res_headers = ["Resources", "Rate/month"] + month_keys + ["Efforts", "Cost"]
            ws_r.write_row("A1", res_headers, fmt_th)
            ws_r.set_column("A:A", 25)
            ws_r.set_column("B:B", 12)
            for i in range(2, 2 + len(month_keys)):
                ws_r.set_column(i, i, 10)
            ws_r.set_column(2 + len(month_keys), 2 + len(month_keys), 10)
            ws_r.set_column(3 + len(month_keys), 3 + len(month_keys), 14)

            for r, row in enumerate(data["resourcing_plan"], start=2):
                zfmt = fmt_z1 if r % 2 else fmt_z2
                ws_r.write(r-1, 0, row["Resources"], zfmt)
                ws_r.write_number(r-1, 1, row.get("Rate/month", 2000.0), fmt_money)
                for j, m in enumerate(month_keys, start=2):
                    ws_r.write_number(r-1, j, row.get(m, 0.0), fmt_num)

            last_r = len(data["resourcing_plan"]) + 1

            # Table
            ws_r.add_table(
                f"A1:{xl_col_to_name(len(res_headers)-1)}{last_r}",
                {
                    "name": "ResourcesTable",
                    "columns": [
                        {"header": h} if h not in ("Efforts", "Cost") else (
                            {
                                "header": "Efforts",
                                "formula": "+".join(f"[@[{m}]]" for m in month_keys)
                            } if h == "Efforts" else
                            {
                                "header": "Cost",
                                "formula": "=[@Efforts]*[@[Rate/month]]"
                            }
                        )
                        for h in res_headers
                    ],
                    "style": "Table Style Medium 2",
                    "autofilter": True,
                    "total_row": True
                }
            )

            # Formulas
            efforts_col = 2 + len(month_keys)
            cost_col = 3 + len(month_keys)
            efforts_letter = xl_col_to_name(efforts_col)
            cost_letter = xl_col_to_name(cost_col)

            for r in range(2, last_r+1):
                month_cols = [xl_col_to_name(j) for j in range(2, 2+len(month_keys))]
                sum_expr = "+".join([f"{c}{r}" for c in month_cols])
                ws_r.write_formula(r-1, efforts_col, f"={sum_expr}", fmt_num)
                ws_r.write_formula(r-1, cost_col, f"=B{r}*{efforts_letter}{r}", fmt_money)

            # Totals
            for c in range(len(res_headers)):
                if c == 0:
                    ws_r.write(last_r, c, "Total", fmt_total)
                else:
                    ws_r.write_blank(last_r, c, None, fmt_total)
            ws_r.write_formula(
                last_r, efforts_col,
                f"=SUBTOTAL(109,{efforts_letter}2:{efforts_letter}{last_r})",
                fmt_total
            )
            ws_r.write_formula(
                last_r, cost_col,
                f"=SUBTOTAL(109,{cost_letter}2:{cost_letter}{last_r})",
                fmt_total
            )

            # Pie chart
            pie = wb.add_chart({"type": "pie"})
            pie.add_series({
                "categories": f"='Resources Plan'!$A$2:$A${last_r}",
                "values": f"='Resources Plan'!${cost_letter}$2:${cost_letter}${last_r}",
                "data_labels": {"percentage": True, "value": True, "category": True}
            })
            pie.set_title({"name": "Cost by Role"})
            ws_r.insert_chart("M1", pie, {"x_scale": 1.5, "y_scale": 1.5})

        # -------- Project Summary --------
        summary = data.get("project_summary", {})
        if summary and isinstance(summary, dict):
            ws_s = wb.add_worksheet("Project Summary")
            ws_s.set_column("A:A", 25)
            ws_s.set_column("B:B", 100)

            # Add title
            title_format = wb.add_format({
                "bold": True, "font_size": 14, "bg_color": THEME["header_bg"],
                "border": 1, "align": "left"
            })
            ws_s.merge_range("A1:B1", "Project Summary", title_format)

            row = 2

            # Executive Summary
            exec_summary = summary.get("executive_summary", "")
            if exec_summary:
                ws_s.write(row, 0, "Executive Summary", fmt_th)
                ws_s.write(row, 1, exec_summary, wb.add_format({
                    "border": 1, "text_wrap": True, "valign": "top"
                }))
                row += 2

            # Key Deliverables
            deliverables = summary.get("key_deliverables", [])
            if deliverables and isinstance(deliverables, list):
                ws_s.write(row, 0, "Key Deliverables", fmt_th)
                deliverables_text = "\n".join([f"• {item}" for item in deliverables])
                ws_s.write(row, 1, deliverables_text, wb.add_format({
                    "border": 1, "text_wrap": True, "valign": "top"
                }))
                row += 2

            # Success Criteria
            success = summary.get("success_criteria", [])
            if success and isinstance(success, list):
                ws_s.write(row, 0, "Success Criteria", fmt_th)
                success_text = "\n".join([f"• {item}" for item in success])
                ws_s.write(row, 1, success_text, wb.add_format({
                    "border": 1, "text_wrap": True, "valign": "top"
                }))
                row += 2

            # Risks and Mitigation
            risks = summary.get("risks_and_mitigation", [])
            if risks and isinstance(risks, list) and len(risks) > 0:
                ws_s.write(row, 0, "Risks & Mitigation", fmt_th)
                ws_s.write(row, 1, "", fmt_th)
                row += 1

                # Create table for risks
                risk_headers = ["Risk", "Mitigation Strategy"]
                ws_s.write_row(row, 0, risk_headers, fmt_th)
                row += 1

                for risk_item in risks:
                    if isinstance(risk_item, dict):
                        zfmt = fmt_z1 if row % 2 else fmt_z2
                        ws_s.write(row, 0, risk_item.get("risk", ""), zfmt)
                        ws_s.write(row, 1, risk_item.get("mitigation", ""), zfmt)
                        row += 1

        wb.close()
        buf.seek(0)
        return buf

    except Exception as e:
        import traceback
        out = io.BytesIO()
        wb = xlsxwriter.Workbook(out)
        ws = wb.add_worksheet("Error")
        ws.write(0, 0, "Error generating Excel")
        ws.write(1, 0, str(e))
        ws.write(2, 0, traceback.format_exc())
        wb.close()
        out.seek(0)
        return out
# PDF EXPORT
async def generate_pdf(scope: Dict[str, Any]) -> io.BytesIO:
    data = scope or {}
    logger.info(f"📄 Generating PDF with scope data keys: {list(data.keys())}")
    logger.info(f"  - Has architecture_diagram: {'architecture_diagram' in data}")
    logger.info(f"  - Has project_summary: {'project_summary' in data}")
    currency = (data.get("overview", {}) or {}).get("Currency", "USD").upper()
    symbol = "Rs. " if currency == "INR" else CURRENCY_SYMBOLS.get(currency, "$")

    buf = io.BytesIO()
    W, H = landscape(A4)
    doc = SimpleDocTemplate(
        buf, pagesize=(W * 1.1, H * 2),
        leftMargin=1 * cm, rightMargin=1 * cm,
        topMargin=1 * cm, bottomMargin=1 * cm
    )

    styles = getSampleStyleSheet()
    wrap = styles["Normal"]
    wrap.fontSize = 10     
    wrap.leading = 12       
    wrap.spaceAfter = 3
    wrap.spaceBefore = 3

    elems = []

    # -------- Title --------
    title_style = ParagraphStyle(
        name="CenterHeading", fontSize=18, leading=22, alignment=TA_CENTER,
        textColor=colors.HexColor("#333366"), spaceAfter=12, spaceBefore=12
    )
    project_name = data.get("overview", {}).get("Project Name", "Untitled Project")
    elems.append(Paragraph(project_name, title_style))

    # -------- Architecture Diagram --------
    arch_path = data.get("architecture_diagram")
    logger.info(f"🔍 Architecture diagram path in scope data: {arch_path}")
    if arch_path:
        try:
            logger.info(f"📊 Attempting to download architecture diagram from: {arch_path}")

            # Add timeout protection for blob download (15 seconds max)
            import asyncio
            try:
                img_bytes = await asyncio.wait_for(
                    azure_blob.download_bytes(arch_path),
                    timeout=15.0
                )
            except asyncio.TimeoutError:
                logger.warning(f"⏱️ Architecture diagram download timed out after 15s - skipping")
                raise Exception("Blob download timeout")

            if not img_bytes or len(img_bytes) == 0:
                logger.warning(f"⚠️ Architecture diagram is empty - skipping")
                raise Exception("Empty blob")

            logger.info(f"✅ Downloaded architecture diagram: {len(img_bytes)} bytes")
            img_buf = io.BytesIO(img_bytes)

            # Section header
            elems.append(Paragraph("<b>System Architecture</b>", styles["Heading2"]))

            # ---- Improved image rendering with height constraint ----
            img = RLImage(img_buf)

            # Define maximum dimensions that fit within page
            max_width = 780  # fits within current A4 landscape scaling
            max_height = 1000  # leave room for margins and other content

            # Calculate scaling to fit within both width and height constraints
            width_scale = max_width / float(img.imageWidth)
            height_scale = max_height / float(img.imageHeight)

            # Use the smaller scale factor to ensure image fits both dimensions
            scale = min(width_scale, height_scale)

            new_width = img.imageWidth * scale
            new_height = img.imageHeight * scale

            img.drawWidth = new_width
            img.drawHeight = new_height

            # Left align cleanly using Table (ReportLab trick)
            img_table = Table([[img]], colWidths=[new_width], hAlign="LEFT")
            img_table.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]))

            elems.append(img_table)
            elems.append(Spacer(1, 0.6 * cm))
            logger.info(f"✅ Architecture diagram embedded successfully")

        except Exception as e:
            logger.error(f"❌ Failed to embed architecture diagram: {e}")
            # Add a notice in PDF that diagram is unavailable
            elems.append(Paragraph("<b>System Architecture</b>", styles["Heading2"]))
            elems.append(Paragraph(
                "<i>Architecture diagram unavailable (failed to load from storage)</i>",
                wrap
            ))
            elems.append(Spacer(1, 0.6 * cm))

    # -------- Overview --------
    ov = data.get("overview", {})
    if ov:
        ov_rows = [["Field", "Value"]]
        for k, v in ov.items():
            # 🔹 Append "months" if key is Duration and value is a number
            if isinstance(v, (int, float)) and k.strip().lower() == "duration":
                display_val = f"{v} months"
            else:
                display_val = str(v)
            ov_rows.append([k, display_val])

        tbl = Table(ov_rows, colWidths=[120, 720], repeatRows=1)
        ts_ov = TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(THEME["header_bg"])),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])

        for i in range(1, len(ov_rows)):
            ts_ov.add(
                "BACKGROUND", (0, i), (-1, i),
                colors.HexColor(THEME["zebra1" if i % 2 else "zebra2"])
            )

        tbl.setStyle(ts_ov)
        tbl.hAlign = "LEFT"
        elems.append(Paragraph("<b>Project Overview</b>", styles["Heading2"]))
        elems.append(tbl)
        elems.append(Spacer(1, 0.6 * cm))


    # -------- Activities --------
    activities = data.get("activities", [])
    if activities:
        headers = [
            "ID", "Activities", "Description", "Owner",
            "Resources", "Start Date", "End Date", "Effort Months"
        ]
        rows = [headers]
        parsed = []
        for idx, a in enumerate(activities, start=1):
            try:
                s = datetime.fromisoformat(a["Start Date"])
                e = datetime.fromisoformat(a["End Date"])
                parsed.append((a, s, e))
            except Exception:
                pass
            rows.append([
                idx,  # auto incremental ID
                Paragraph(a.get("Activities", ""), wrap),
                Paragraph(a.get("Description", ""), wrap),
                Paragraph(a.get("Owner", ""), wrap),
                Paragraph(a.get("Resources", ""), wrap),
                a.get("Start Date", ""),
                a.get("End Date", ""),
                a.get("Effort Months", "")
            ])

        t = Table(rows, repeatRows=1,
                  colWidths=[25, 150, 225, 100, 120, 70, 70, 80])
        ts = TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(THEME["header_bg"])),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ])

        for i in range(1, len(rows)):
            ts.add("BACKGROUND", (0, i), (-1, i),
                   colors.HexColor(THEME["zebra1" if i % 2 else "zebra2"]))
        t.setStyle(ts)
        t.hAlign = "LEFT"
        elems.append(Paragraph("<b>Activities Breakdown</b>", styles["Heading2"]))
        elems.append(t)
        elems.append(Spacer(1, 0.6 * cm))

        # ----- Week-based Timeline -----
        if parsed:
            parsed.sort(key=lambda x: x[1])
            batches = [parsed[i:i + 20] for i in range(0, len(parsed), 20)]
            for bi, batch in enumerate(batches, start=1):
                min_s = min(s for _, s, _ in batch)
                max_e = max(e for _, _, e in batch)

                # Calculate project start (Monday of first week)
                project_start = min_s - timedelta(days=min_s.weekday())

                # Calculate total weeks
                total_days = (max_e - project_start).days + 1
                num_weeks = (total_days + 6) // 7

                # Width for each week column
                week_width = 35
                grid_width = num_weeks * week_width
                total_width = 150 + grid_width

                d = Drawing(total_width + 50, (len(batch) * 25) + 80)

                # Week grid headers and lines
                for week_idx in range(num_weeks):
                    x = 150 + (week_idx * week_width)

                    # Vertical grid line
                    d.add(Rect(x, 30, 0.5, len(batch) * 25 + 30,
                               fillColor=colors.lightgrey, strokeColor=colors.lightgrey))

                    # Week label
                    d.add(String(x + 5, 10, f"W{week_idx + 1}",
                                 fontSize=7, fillColor=colors.grey))

                # Activity bars
                for i, (a, s, e) in enumerate(batch):
                    y = 50 + i * 25

                    # Calculate week indices for this activity
                    activity_start_day = (s - project_start).days
                    activity_end_day = (e - project_start).days
                    start_week = activity_start_day // 7
                    end_week = activity_end_day // 7

                    # Draw activity label
                    label = (a["Activities"] or "")[:25]
                    d.add(String(5, y+5, label, fontSize=8))

                    # Draw blue bar across the weeks
                    bar_x = 150 + (start_week * week_width)
                    bar_width = ((end_week - start_week + 1) * week_width) - 2
                    d.add(Rect(bar_x + 1, y + 3, bar_width, 12,
                              fillColor=colors.HexColor("#4D96FF"),
                              strokeColor=colors.HexColor("#3077DD")))

                elems.append(Paragraph("<b>High Level Project Plan</b>", styles["Heading2"]))
                elems.append(d)
                elems.append(Spacer(1, 0.6 * cm))
                if bi < len(batches):
                    elems.append(PageBreak())

    # -------- Resourcing Plan --------
    plan = data.get("resourcing_plan", [])
    if plan and isinstance(plan[0], dict):
        mkeys = [k for k in plan[0].keys() if len(k.split()) == 2]
    else:
        mkeys = []

    if plan:
        merged = {}
        for r in plan:
            rk = r["Resources"].lower()
            eff = float(r.get("Efforts", 0))
            cost = float(r.get("Cost", eff * r.get("Rate/month", 2000)))
            if rk not in merged:
                merged[rk] = {
                    "Resources": r["Resources"], "Efforts": eff,
                    "Rate/month": r["Rate/month"], "Cost": cost,
                    "months": [float(r.get(m, 0)) for m in mkeys]
                }
            else:
                m = merged[rk]
                m["Efforts"] += eff
                m["Cost"] += cost
                m["months"] = [
                    x+y for x, y in zip(m["months"], [float(r.get(m, 0)) for m in mkeys])
                ]

        merged_res = sorted(merged.values(), key=lambda x: x["Cost"], reverse=True)

        # Collect rows
        tot_eff = tot_cost = 0
        pie_labels, pie_vals = [], []
        base_rows = []
        for idx, r in enumerate(merged_res, start=1):
            tot_eff += r["Efforts"]; tot_cost += r["Cost"]
            pie_labels.append(r["Resources"]); pie_vals.append(r["Cost"])
            base_rows.append([
                idx,
                Paragraph(r["Resources"], wrap),
                f"{symbol}{r['Rate/month']:,.2f}",
                *[f"{v:.2f}" for v in r["months"]], 
                f"{r['Efforts']:.2f}",
                f"{symbol}{r['Cost']:,.2f}"

            ])

        base_rows.append(
        ["Total", "", ""] + [""]*len(mkeys) +
        [f"{tot_eff:.2f}", f"{symbol}{tot_cost:,.2f}"]
    )


        # ---- Split into chunks if too wide ----
        MAX_MONTH_COLS = 10
        for start in range(0, len(mkeys), MAX_MONTH_COLS):
            month_chunk = mkeys[start:start+MAX_MONTH_COLS]

            sub_rows = []
            for row in base_rows:
                fixed = row[:3]
                months = row[3:3+len(mkeys)]
                end = row[-2:]
                sub_months = months[start:start+MAX_MONTH_COLS]
                sub_rows.append(fixed + sub_months + end)

            header = ["ID", "Resources", "Rate/month"] + month_chunk + ["Efforts", "Cost"]
            sub_rows.insert(0, header)

            t2 = LongTable(sub_rows, repeatRows=1,
                        colWidths=[40, 120, 70] + [55]*len(month_chunk) + [50, 80])
            ts2 = TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(THEME["header_bg"])),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, len(sub_rows)-1), (-1, len(sub_rows)-1),
                colors.HexColor(THEME["total_bg"]))
            ])

            for i in range(1, len(sub_rows)-1):
                ts2.add("BACKGROUND", (0, i), (-1, i),
                        colors.HexColor(THEME["zebra1" if i % 2 else "zebra2"]))
            t2.setStyle(ts2)
            t2.hAlign = "LEFT"

            elems.append(Paragraph("<b>Resourcing Plan</b>", styles["Heading2"]))
            elems.append(t2)
            elems.append(Spacer(1, 0.6*cm))

        # Pie chart
        if pie_labels:
            d2 = Drawing(400, 250)
            pie = Pie()
            pie.x, pie.y = 100, 20
            pie.width, pie.height = 200, 200
            pie.data = pie_vals
            pie.labels = pie_labels
            pal = THEME["palette"]
            for i in range(len(pie.labels)):
                pie.slices[i].fillColor = colors.HexColor(pal[i % len(pal)])
            d2.add(pie)
            elems.append(Paragraph("<b>Cost Projection</b>", styles["Heading2"]))
            elems.append(Spacer(1, 0.6 * cm))
            elems.append(d2)

    # -------- Project Summary --------
    summary = data.get("project_summary", {})
    logger.info(f"📋 Project summary in scope data: {bool(summary)} (keys: {list(summary.keys()) if summary else 'None'})")
    if summary and isinstance(summary, dict):
        logger.info(f"✅ Adding Project Summary section to PDF")
        elems.append(PageBreak())
        elems.append(Paragraph("<b>Project Summary</b>", styles["Heading1"]))
        elems.append(Spacer(1, 0.4 * cm))

        # Executive Summary
        exec_summary = summary.get("executive_summary", "")
        if exec_summary:
            elems.append(Paragraph("<b>Executive Summary</b>", styles["Heading2"]))
            elems.append(Paragraph(exec_summary, wrap))
            elems.append(Spacer(1, 0.4 * cm))

        # Key Deliverables
        deliverables = summary.get("key_deliverables", [])
        if deliverables and isinstance(deliverables, list):
            elems.append(Paragraph("<b>Key Deliverables</b>", styles["Heading2"]))
            for item in deliverables:
                elems.append(Paragraph(f"• {item}", wrap))
            elems.append(Spacer(1, 0.4 * cm))

        # Success Criteria
        success = summary.get("success_criteria", [])
        if success and isinstance(success, list):
            elems.append(Paragraph("<b>Success Criteria</b>", styles["Heading2"]))
            for item in success:
                elems.append(Paragraph(f"• {item}", wrap))
            elems.append(Spacer(1, 0.4 * cm))

        # Risks and Mitigation
        risks = summary.get("risks_and_mitigation", [])
        if risks and isinstance(risks, list):
            elems.append(Paragraph("<b>Risks and Mitigation Strategies</b>", styles["Heading2"]))
            risk_rows = [["Risk", "Mitigation Strategy"]]
            for risk_item in risks:
                if isinstance(risk_item, dict):
                    risk_rows.append([
                        Paragraph(risk_item.get("risk", ""), wrap),
                        Paragraph(risk_item.get("mitigation", ""), wrap)
                    ])

            if len(risk_rows) > 1:  # Only add table if there are risks
                risk_table = Table(risk_rows, colWidths=[300, 400], repeatRows=1)
                ts_risk = TableStyle([
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(THEME["header_bg"])),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ])

                for i in range(1, len(risk_rows)):
                    ts_risk.add("BACKGROUND", (0, i), (-1, i),
                               colors.HexColor(THEME["zebra1" if i % 2 else "zebra2"]))

                risk_table.setStyle(ts_risk)
                risk_table.hAlign = "LEFT"
                elems.append(risk_table)
                elems.append(Spacer(1, 0.4 * cm))

    # Build PDF
    doc.build(elems)
    buf.seek(0)
    return buf
