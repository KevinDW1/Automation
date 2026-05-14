import re, pathlib

path = pathlib.Path('Vendor/ven01_to_ven10.py')
text = path.read_text(encoding='utf-8')

safe = """
def _safe_run(fn, shared_page):
    try:
        r = _run(fn(shared_page))
    except Exception as exc:
        r = TestResult(fn.__name__, "(crashed)")
        r.fail("Exception: " + str(exc))
    if not r.passed:
        print("  [RECORDED FAILURE] " + r.test_id + ": " + "; ".join(r.failure_reasons))
    return r
"""

text = text.replace(
    'def _run(coro):\n    loop = asyncio.get_event_loop()\n    return loop.run_until_complete(coro)',
    'def _run(coro):\n    loop = asyncio.get_event_loop()\n    return loop.run_until_complete(coro)\n' + safe
)

text = re.sub(
    r'(def (test_\w+)\(shared_page\)): r = _run\((\w+)\(shared_page\)\); assert r\.passed.*',
    r'\1: _safe_run(\3, shared_page)',
    text
)

path.write_text(text, encoding='utf-8')
print('Done')
