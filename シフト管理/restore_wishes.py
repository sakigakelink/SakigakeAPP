"""Restore wishes from old backup to latest backup"""
import json
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

old = json.load(open('backup/backup_20260316_145255.json', 'r', encoding='utf-8'))
lat = json.load(open('backup/backup_latest.json', 'r', encoding='utf-8'))

print(f"Old wishes: { {k: len(v) for k, v in old.get('wishes', {}).items()} }")
print(f"Latest wishes: { {k: len(v) for k, v in lat.get('wishes', {}).items()} }")

lat['wishes'] = old['wishes']

json.dump(lat, open('backup/backup_latest.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(f"Restored wishes: { {k: len(v) for k, v in lat.get('wishes', {}).items()} }")
print("Done")
