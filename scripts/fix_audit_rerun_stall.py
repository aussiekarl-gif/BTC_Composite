from pathlib import Path

path = Path('engines/audit/public_model_audit.py')
text = path.read_text(encoding='utf-8')
old = '''restored = read_cache_csv(backup_restore) if backup_restore is not None else pd.DataFrame()\ncache = combine_caches(memory, bundled, bundled_master, restored)\nif backup_restore is not None and not restored.empty:\n    memory = save_audit_memory(memory, restored, base)\nelse:\n    memory = save_audit_memory(memory, cache, base)\n'''
new = '''restored = read_cache_csv(backup_restore) if backup_restore is not None else pd.DataFrame()\ncache = combine_caches(memory, bundled, bundled_master, restored)\nif backup_restore is not None and not restored.empty:\n    # A deliberate restore is a real state change, so persist it transactionally.\n    memory = save_audit_memory(memory, restored, base)\nelse:\n    # Ordinary Streamlit reruns must be read-only. Previously this called\n    # save_audit_memory() on every rerun, which repeatedly downloaded the ~3 MB\n    # GitHub master several times even when nothing had changed. That made the\n    # page appear to blink/hang while the backend was doing redundant network I/O.\n    memory = combine_caches(memory, cache, base)\n'''
if old not in text:
    raise SystemExit('Target block not found; refusing to patch')
text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8')
print('Patched ordinary audit reruns to be read-only')
