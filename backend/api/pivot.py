import win32com.client as win32
import pythoncom

# ── Type colour palette ───────────────────────────────────────────────────────
TYPE_COLOURS = {
    # Reds & Pinks
    "DD ISSUE":        "#FF9999",
    "DOUBT":           "#FFB3D9",
    "NAMES":           "#FFB3FF",
    # Oranges & Yellows
    "UNMATCH INB TRF": "#FFCC99",
    "BANK FIN":        "#FFD999",
    "CASH":            "#FFE599",
    "PROP":            "#FFFF99",
    "COMPANY NAME":    "#D9FF99",
    # Greens
    "SIS CON":         "#99FF99",
    "UNMATCH SIS CON": "#99FFCC",
    "SUSPICIOUS":      "#99FFE5",
    # Blues
    "FIXED DEPOSIT":   "#99E5FF",
    "ODD FIG":         "#99CCFF",
    "INB TRF":         "#B3B3FF",
    "EXPENSE":         "#D9B3FF",
    # Muted / Neutrals
    "PVT FIN":         "#E0C2FF",
    "RETURN":          "#D9D9D9",
    "INSURANCE":       "#E6E6E6",
    "REVERSAL":        "#D9D9B3",
    "DRAWBACKS":       "#B3CCB3",
}

_DESIRED_TYPE_ORDER = [
    "COMPANY NAME", "CASH", "PROP", "INB TRF", "UNMATCH INB TRF",
    "SIS CON", "UNMATCH SIS CON", "FIXED DEPOSIT", "SUSPICIOUS",
    "ODD FIG", "DD ISSUE", "DOUBT", "NAMES", "BANK FIN",
    "PVT FIN", "INSURANCE", "RETURN", "REVERSAL",
    "EXPENSE", "DRAWBACKS", "PURCHASE", "SALES",
]

_HEADER_BG_COLOR = 220 + (230 << 8) + (241 << 16)


# ── Private helpers ────────────────────────────────────────────────────────────

def hex_to_excel_color(hex_color: str) -> int:
    """Convert a #RRGGBB hex string to the BGR integer Excel expects."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return r + (g << 8) + (b << 16)


def _apply_borders(rng, border_ids: list, line_style: int = 1, weight: int = 2, color: int = 0) -> None:
    """Apply identical border formatting to every border edge in *border_ids*."""
    for bid in border_ids:
        b = rng.Borders(bid)
        b.LineStyle = line_style
        b.Weight    = weight
        b.Color     = color


def _color_row(sheet, row_abs: int, start_col: int, col_count: int, color: int) -> None:
    """Fill an entire pivot row with *color*."""
    sheet.Range(
        sheet.Cells(row_abs, start_col),
        sheet.Cells(row_abs, start_col + col_count - 1),
    ).Interior.Color = color


# ── Public API ─────────────────────────────────────────────────────────────────

def create_pivot(file_path, sheet_name, limit=None, excel=None) -> None:
    """
    Open *file_path* in Excel via COM automation, create / refresh a pivot
    table on a sheet named after *sheet_name* (XNS→PIVOT), apply colours
    and formatting, then save and close.
    If *excel* is provided, use that instance and do not quit it.
    """
    wb = None
    own_excel = False

    try:
        if excel is None:
            pythoncom.CoInitialize()
            excel = win32.DispatchEx("Excel.Application")
            excel.Visible       = False
            excel.DisplayAlerts = False
            excel.ScreenUpdating = False
            own_excel = True
            try:
                excel.Calculation = -4135   # xlCalculationManual
            except Exception:
                pass

        file_path = str(file_path).replace('\\', '/').strip()
        wb = excel.Workbooks.Open(file_path)
        ws = wb.Sheets(sheet_name)

        pivot_sheet_name = str(sheet_name).replace("XNS", "PIVOT")

        # ── Data range ────────────────────────────────────────────────────
        last_row = ws.Cells(ws.Rows.Count, 1).End(-4162).Row
        last_col = ws.Cells(1, ws.Columns.Count).End(-4159).Column
        source_range = ws.Range(ws.Cells(1, 2), ws.Cells(last_row, last_col - 1))

        # ── Delete old pivot sheet if present ─────────────────────────────
        for sheet in wb.Sheets:
            if sheet.Name == pivot_sheet_name:
                sheet.Delete()
                break

        # ── Create pivot sheet + cache + table ────────────────────────────
        pivot_sheet = wb.Sheets.Add(Before=ws)
        pivot_sheet.Name = pivot_sheet_name

        pivot_cache = wb.PivotCaches().Create(
            SourceType=1,
            SourceData=f"'{ws.Name}'!{source_range.Address}",
        )

        pivot_table = pivot_cache.CreatePivotTable(
            TableDestination=pivot_sheet.Cells(7, 1),
            TableName="MyPivot",
        )
        try:
            # In some win32com environments, PivotCache is a method
            pivot_table.PivotCache().SaveData = True
        except (AttributeError, TypeError):
            try:
                # In others, it is a property
                pivot_table.PivotCache.SaveData = True
            except Exception:
                pass
        
        pivot_table.EnableDrilldown = True

        # ── Configure pivot fields ────────────────────────────────────────
        type_field     = pivot_table.PivotFields("TYPE")
        category_field = pivot_table.PivotFields("Category")
        month_field    = pivot_table.PivotFields("Month")

        type_field.Orientation     = 1;  type_field.Position     = 1
        category_field.Orientation = 1;  category_field.Position = 2
        month_field.Orientation    = 2;  month_field.Position    = 1

        # Hide (blank) items
        for fld in [type_field, category_field, month_field]:
            try:
                fld.PivotItems("(blank)").Visible = False
            except Exception:
                pass

        # ── Month ordering (preserve sheet order, deduplicated) ───────────
        month_raw   = ws.Range(ws.Cells(2, 3), ws.Cells(last_row, 3)).Value
        month_order = list(dict.fromkeys(
            str(row[0]).strip() for row in month_raw if row[0]
        ))
        month_field.AutoSort(2, "Month")
        for pos, m in enumerate(month_order, start=1):
            try:
                month_field.PivotItems(m).Position = pos
            except Exception:
                pass

        # ── Values ────────────────────────────────────────────────────────
        pivot_table.AddDataField(pivot_table.PivotFields("DR"), "Sum of DR", -4157)
        pivot_table.AddDataField(pivot_table.PivotFields("CR"), "Sum of CR", -4157)

        pivot_table.RowAxisLayout(1)
        pivot_table.SubtotalLocation(2)
        pivot_table.RefreshTable()
        pivot_table.PreserveFormatting = True
        pivot_table.HasAutoFormat      = False
        pivot_table.TableStyle2        = ""

        # ── TYPE ordering ─────────────────────────────────────────────────
        type_field.AutoSort(2, "TYPE")
        pos = 1
        for name in _DESIRED_TYPE_ORDER:
            try:
                type_field.PivotItems(name).Position = pos
                pos += 1
            except Exception:
                pass

        # ── Font ──────────────────────────────────────────────────────────
        pivot_range = pivot_table.TableRange2
        pivot_range.Font.Name = "Calibri"
        pivot_range.Font.Size = 9
        pivot_range.Font.Bold = True

        # ── Column widths ─────────────────────────────────────────────────
        start_row = pivot_range.Row
        start_col = pivot_range.Column
        col_count = pivot_range.Columns.Count
        row_count = pivot_range.Rows.Count

        pivot_range.Columns.AutoFit()

        # ── Grouped row coloring for performance ──────────────────────
        type_values = pivot_range.Columns(1).Value
        current_type = None
        group_start = -1

        for i, row_data in enumerate(type_values):
            val = row_data[0]
            abs_row = start_row + i

            if val:
                val_str = str(val)
                new_type = val_str.strip().upper()
                
                # Apply previous group if type changed
                if group_start != -1 and new_type != current_type:
                    _color_row_range(pivot_sheet, group_start, abs_row - 1, start_col + 1, start_col + col_count - 1, current_type)
                    group_start = -1
                
                current_type = new_type
                if "TOTAL" not in current_type:
                    group_start = abs_row
                
                # Subtotals are still colored individually for font
                if "Total" in val_str and "Grand" not in val_str:
                    pivot_sheet.Range(
                        pivot_sheet.Cells(abs_row, start_col),
                        pivot_sheet.Cells(abs_row, start_col + col_count - 1),
                    ).Font.Color = 255
            else:
                # Still in the same group?
                pass
        
        # Final group
        if group_start != -1:
            _color_row_range(pivot_sheet, group_start, start_row + row_count - 1, start_col + 1, start_col + col_count - 1, current_type)

        # ── Header rows + Grand Total row background ──────────────────────
        for i in range(3):
            _color_row(pivot_sheet, start_row + i, start_col, col_count, _HEADER_BG_COLOR)
        _color_row(pivot_sheet, start_row + row_count - 1, start_col, col_count, _HEADER_BG_COLOR)

        # ── Borders on pivot table ────────────────────────────────────────
        pivot_range = pivot_table.TableRange2
        _apply_borders(pivot_range, [7, 8, 9, 10, 11, 12])

        # ── Title block ───────────────────────────────────────────────────
        title_range = pivot_sheet.Range("C2:G4")
        title_range.Merge()
        title_range.HorizontalAlignment = -4108
        title_range.VerticalAlignment   = -4108

        file_name  = file_path.split('/')[-1].split('-')[0].strip()
        sht_name   = str(sheet_name).replace("XNS", "").strip("-")
        title_text = f"{file_name}\n{sht_name}"
        if limit is not None:
            title_text += f" ({limit})"

        _apply_borders(title_range, [7, 8, 9, 10])
        title_range.Font.Size  = 10
        title_range.Font.Color = 255
        title_range.Font.Bold  = True
        title_range.Value      = title_text

        wb.Save()

    finally:
        if wb:
            try: wb.Close(SaveChanges=True)
            except: pass
        if own_excel and excel:
            try:
                excel.Calculation = -4105   # xlCalculationAutomatic
            except Exception:
                pass
            try: excel.Quit()
            except: pass
            pythoncom.CoUninitialize()

def _color_row_range(sheet, row_start, row_end, col_start, col_end, type_name):
    """Fill a range of rows with the color mapped to type_name."""
    if type_name in TYPE_COLOURS:
        color = hex_to_excel_color(TYPE_COLOURS[type_name])
        sheet.Range(
            sheet.Cells(row_start, col_start),
            sheet.Cells(row_end, col_end)
        ).Interior.Color = color
