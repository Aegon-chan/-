import re

with open('frontend/app.py', 'r', encoding='utf-8') as f:
    content = f.read()
    original_content = content

lines = content.split('\n')

# Define problematic character ranges
private_use_range = set(chr(c) for c in range(0xE000, 0xF900))
private_use_range.add('\ufffd')
private_use_range.add('\ue21c')  # specific problematic char seen in the file

def has_problematic(s):
    return any(c in s for c in private_use_range)

# Find lines with problematic chars
problematic_lines = []
for i, line in enumerate(lines):
    if has_problematic(line):
        problematic_lines.append((i+1, line))
        print(f"Line {i+1}: {repr(line[:120])}")

print(f"\nFound {len(problematic_lines)} problematic lines")
