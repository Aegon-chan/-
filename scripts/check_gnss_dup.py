import openpyxl
wb = openpyxl.load_workbook(r"C:\Users\24622\Desktop\监测数据2020.5.30-2026.6.10.xlsx", data_only=True)
ws = wb["监测数据合集"]

# Show G1 data at the transition zone
print("=== G1 time column (col 7) around the break ===")
for r in [2200, 2203, 2205, 2210, 2220, 2300, 2400, 2500, 3000]:
    t = ws.cell(r, 7).value
    dx = ws.cell(r, 8).value
    dy = ws.cell(r, 9).value
    dz = ws.cell(r, 10).value
    print(f"  Row {r}: time={t}, dx={dx}, dy={dy}, dz={dz}")

print("\n=== Check: does G1 data start a new series after row 2204? ===")
# First - check last row where G3/G4 time (col 25, 34) has data
for r in [2200, 2201, 2202, 2203, 2204, 2205]:
    g3_t = ws.cell(r, 25).value
    g4_t = ws.cell(r, 34).value
    g1_t = ws.cell(r, 7).value
    g1_dx = ws.cell(r, 8).value
    print(f"  Row {r}: G3_time={g3_t}, G4_time={g4_t}, G1_time={g1_t}, G1_dx={g1_dx}")

print("\n=== G1 first 3 and last 3 in the second segment (rows 2205+) ===")
first_row, last_row = 0, 0
for r in range(2205, ws.max_row + 1):
    if ws.cell(r, 8).value is not None and str(ws.cell(r,8).value).strip() != '':
        if first_row == 0: 
            first_row = r
            print(f"  First: Row {r}: time={ws.cell(r,7).value}, dx={ws.cell(r,8).value}")
        last_row = r
print(f"  Last:  Row {last_row}: time={ws.cell(last_row,7).value}, dx={ws.cell(last_row,8).value}")
print(f"  Second segment rows: {first_row} ~ {last_row} = {last_row - first_row + 1} rows")

wb.close()
