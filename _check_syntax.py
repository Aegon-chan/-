import pathlib, py_compile

files_syntax = [
    "backend/self_growth/finetune.py",
    "backend/self_growth/implicit_feedback.py",
    "backend/core/agent.py",
    "backend/analysis/parser.py",
]

for f in files_syntax:
    p = pathlib.Path(f)
    if not p.exists():
        print(f"{f}: not found")
        continue
    try:
        py_compile.compile(str(p), doraise=True)
        print(f"{f}: OK")
    except py_compile.PyCompileError as e:
        print(f"{f}: SyntaxError: {e}")
        # Read and show the problematic area
        content = p.read_text(encoding="utf-8")
        lines = content.split("\n")
        err_str = str(e)
        # Extract line number from error
        import re
        m = re.search(r'line (\d+)', err_str)
        if m:
            ln = int(m.group(1))
            for j in range(max(0,ln-3), min(len(lines), ln+3)):
                print(f"  {j+1}: {repr(lines[j][:100])}")