Closes #2285

## Summary
- Fix `AgentMemoryStore.get_references()` so tag-filtered queries apply `limit`/`offset` to the filtered result set (not the unfiltered rows).
- Add regression coverage for tag-filter pagination semantics.

## Payment
RTC wallet: `RTC29WwMjwcaFeTTQqKaMNmFUFLYz3f`

## Tests
- `python -m pytest bounties/issue-2285/tests/test_memory.py -q`
- `python -m py_compile bounties/issue-2285/src/memory_store.py bounties/issue-2285/tests/test_memory.py`
- `git diff --check`
