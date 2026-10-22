# Pull Request

## Summary

Explain what changed and why.

## Type

- [ ] Bug fix
- [ ] Documentation
- [ ] New script
- [ ] Script update (`scripts/`)
- [ ] Agent instructions or reference doc update (`SKILL.md`, `references/`)
- [ ] University preset update
- [ ] Test or validation update

## Planning

- [ ] I updated docs if behavior changed.
- [ ] I updated `CHANGELOG.md`.
- [ ] I ran `python -X utf8 tests/run_tests.py` and it ends with `RESULT: PASS`.
- [ ] A new script has a `selftest` (a positive case and a planted-error negative control) and is listed in `tests/run_tests.py`.
- [ ] I preserved the honesty rule: no script invents a source, a number or a quote.
- [ ] No em dash or en dash in any file I touched.
- [ ] No personal paths (home folders, drive letters), email addresses, keys or participant data.
- [ ] I tested or validated locally, or explained why not.

## Validation

```bash
python -X utf8 tests/run_tests.py
```

## Notes

Anything reviewers should know.
