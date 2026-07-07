import re

with open('frontend/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
fixed_lines = []
problematic_chars = set(chr(c) for c in range(0xE000, 0xF900))
problematic_chars.add('\ufffd')

for i, line in enumerate(lines):
    has_problematic = any(c in line for c in problematic_chars)
    if has_problematic:
        def fix_garbled(m):
            text = m.group(1) if m.lastindex and m.group(1) else m.group(0)
            if any(c in text for c in problematic_chars):
                return m.group(0).replace(text, '(local)')
            return m.group(0)
        line = re.sub(r'"[^"]*"', fix_garbled, line)
    fixed_lines.append(line)

result = '\n'.join(fixed_lines)
with open('frontend/app.py', 'w', encoding='utf-8') as f:
    f.write(result)
print('Done')
