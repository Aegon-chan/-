import os
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "templates")
os.makedirs(OUTPUT, exist_ok=True)

# Style definitions
header_font = Font(name="Microsoft YaHei", bold=True, size=11, color="FFFFFF")
header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
data_font = Font(name="Microsoft YaHei", size=10)
data_align = Alignment(horizontal="center", vertical="center")
note_font = Font(name="Microsoft YaHei", size=9, color="888888", italic=True)
thin_border = Border(
    left=Side(style="thin"), right=Side(style="thin"),
    top=Side(style="thin"), bottom=Side(style="thin")
)
hint_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")

def create_template(filename, sheet_name, columns_with_hints, sample_rows):
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name

    # Row 1: Column headers
    headers = [c[0] for c in columns_with_hints]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border

    # Row 2: Hints
    for col, c in enumerate(columns_with_hints, 1):
        hint_text = c[1]
        cell = ws.cell(row=2, column=col, value=hint_text)
        cell.font = note_font
        cell.alignment = data_align
        cell.fill = hint_fill
        cell.border = thin_border

    # Data rows (from row 3)
    for r, row_data in enumerate(sample_rows, 3):
        for c, val in enumerate(row_data, 1):
            cell = ws.cell(row=r, column=c, value=val)
            cell.font = data_font
            cell.alignment = data_align
            cell.border = thin_border

    # Auto column width
    for col, c in enumerate(columns_with_hints, 1):
        max_len = max(
            len(str(c[0])) * 2,
            len(str(c[1])) if c[1] else 0,
            max((len(str(row[col-1])) for row in sample_rows), default=0)
        )
        ws.column_dimensions[get_column_letter(col)].width = min(max(max_len + 4, 12), 40)

    # Freeze pane
    ws.freeze_panes = "A3"

    path = os.path.join(OUTPUT, filename)
    wb.save(path)
    print(f"  Created: {filename}")
    return path

# ── 1. monitoring_stations ──
create_template(
    "01_监测站点.xlsx", "监测站点",
    [
        ("station_code", "站点编码，必填，唯一标识"),
        ("station_name", "站点名称"),
        ("station_type", "类型：groundwater/rainfall/pore_pressure/gnss/insar"),
        ("longitude", "经度，如 103.8456"),
        ("latitude", "纬度，如 30.1234"),
        ("altitude", "海拔（m）"),
        ("description", "站点描述（选填）"),
        ("status", "状态：active/inactive，默认 active"),
    ],
    [
        ["GWS-01", "1号地下水位站", "groundwater", 103.8456, 30.1234, 520.5, "滑坡体前缘", "active"],
        ["RFS-01", "1号雨量站", "rainfall", 103.8500, 30.1300, 530.0, "", "active"],
        ["GNS-01", "1号GNSS监测点", "gnss", 103.8400, 30.1200, 510.2, "滑坡体后缘", "active"],
    ]
)

# ── 2. groundwater_measurements ──
create_template(
    "02_地下水位.xlsx", "地下水位",
    [
        ("station_code", "站点编码，必填，对应监测站点表"),
        ("measurement_time", "测量时间，格式 2026-07-19 14:30:00"),
        ("water_level", "水位（m），必填"),
        ("water_depth", "埋深（m）"),
        ("temperature", "水温（°C）"),
    ],
    [
        ["GWS-01", "2026-07-19 08:00:00", 15.32, 12.18, 18.5],
        ["GWS-01", "2026-07-19 14:00:00", 15.45, 12.05, 19.2],
        ["GWS-01", "2026-07-19 20:00:00", 15.28, 12.22, 18.8],
    ]
)

# ── 3. rainfall_measurements ──
create_template(
    "03_降雨量.xlsx", "降雨量",
    [
        ("station_code", "站点编码，必填，对应监测站点表"),
        ("measurement_time", "测量时间，格式 2026-07-19 14:30:00"),
        ("rainfall_amount", "降雨量（mm），必填"),
    ],
    [
        ["RFS-01", "2026-07-19 08:00:00", 12.5],
        ["RFS-01", "2026-07-19 09:00:00", 8.3],
        ["RFS-01", "2026-07-19 10:00:00", 5.1],
    ]
)

# ── 4. pore_pressure_measurements ──
create_template(
    "04_孔隙水压力.xlsx", "孔隙水压力",
    [
        ("station_code", "站点编码，必填，对应监测站点表"),
        ("measurement_time", "测量时间，格式 2026-07-19 14:30:00"),
        ("pressure_value", "孔隙水压力（kPa），必填"),
        ("temperature", "温度（°C）"),
    ],
    [
        ["GPS-01", "2026-07-19 08:00:00", 125.6, 18.2],
        ["GPS-01", "2026-07-19 14:00:00", 128.3, 19.5],
        ["GPS-01", "2026-07-19 20:00:00", 126.8, 18.9],
    ]
)

# ── 5. gnss_measurements ──
create_template(
    "05_GNSS位移.xlsx", "GNSS位移",
    [
        ("station_code", "站点编码，必填，对应监测站点表"),
        ("measurement_time", "测量时间，格式 2026-07-19 14:30:00"),
        ("dx", "东西向位移（mm），必填，东为正"),
        ("dy", "南北向位移（mm），必填，北为正"),
        ("dz", "垂直向位移（mm），必填，上升为正"),
        ("planar_displacement", "平面位移（mm）"),
        ("variation", "变化量（mm）"),
        ("daily_planar_rate", "日平面位移速率（mm/d）"),
        ("daily_variation_rate", "日变化量速率（mm/d）"),
    ],
    [
        ["GNS-01", "2026-07-19 08:00:00", 2.15, -1.23, 0.45, 2.48, 0.32, 0.15, 0.02],
        ["GNS-01", "2026-07-19 14:00:00", 2.28, -1.35, 0.52, 2.65, 0.38, 0.17, 0.03],
        ["GNS-01", "2026-07-19 20:00:00", 2.20, -1.28, 0.48, 2.54, 0.35, 0.16, 0.02],
    ]
)

# ── 6. insar_measurements ──
create_template(
    "06_InSAR形变.xlsx", "InSAR形变",
    [
        ("station_code", "站点编码，必填，对应监测站点表"),
        ("acquisition_time", "影像获取时间，格式 2026-07-19"),
        ("los_displacement", "视线向形变（mm），必填"),
        ("coherence", "相干性，0~1"),
        ("incidence_angle", "入射角（°）"),
        ("track_number", "轨道编号"),
    ],
    [
        ["INS-01", "2026-07-01", -3.25, 0.85, 38.5, "T128"],
        ["INS-01", "2026-07-13", -5.18, 0.82, 38.5, "T128"],
        ["INS-01", "2026-07-25", -7.02, 0.79, 38.5, "T128"],
    ]
)

# ── Note about import_batches ──
with open(os.path.join(OUTPUT, "_说明.txt"), "w", encoding="utf-8") as f:
    f.write("监测数据导入模板说明\n")
    f.write("=====================\n\n")
    f.write("1. 先导入「01_监测站点.xlsx」建立站点信息\n")
    f.write("2. 再导入各测量数据模板（02~06）\n")
    f.write("3. station_code 必须已在站点表中存在\n")
    f.write("4. 时间格式统一为 YYYY-MM-DD HH:MM:SS 或 YYYY-MM-DD\n")
    f.write("5. import_batches 为系统自动记录表，无需手动导入\n")
    f.write("\n模板文件均保留第1行列名和第2行提示，导入时自动跳过。\n")

print(f"\nAll templates created in: {OUTPUT}")
