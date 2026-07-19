path = r"C:\Users\24622\Desktop\科研Agent\backend\analysis\monitoring_service.py"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Remove the created_at and updated_at lines from _station_to_dict
old = '''        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }'''

new = '''    }'''

content = content.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated monitoring_service.py")
