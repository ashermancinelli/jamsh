# jamsh

Small shell utilities for Python for personal use.

```python
from jamsh import run

run(["make"], extra_env={"VERBOSE": "1"})

result = run(["python", "-c", "print('hi')"], capture=True)
assert result.stdout == "hi\n"
```

```bash
python -m jamsh.demo
```
