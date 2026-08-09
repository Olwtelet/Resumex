## What this changes

<!-- One or two sentences. Link the issue if there is one. -->

## Why

<!-- What was wrong, or what became possible. -->

## Checklist

- [ ] `ruff check .` passes
- [ ] `pytest` passes
- [ ] `pytest -m integration` passes, or this change does not touch rendering
- [ ] New behaviour has a test at the seam that could break
- [ ] No test makes a network call
- [ ] README and `resumex.example.toml` still describe what the code does
- [ ] New config keys are in both `config.py` and `EXAMPLE_CONFIG`

## Anything a reviewer should look at first

<!-- The tricky part, a tradeoff you were unsure about, or "nothing, it's small". -->
