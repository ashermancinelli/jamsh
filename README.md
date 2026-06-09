# jamsh

Small shell utilities for Python for personal use.

```python
from jamsh import run

run(["make"], extra_env={"VERBOSE": "1"})

result = run(["python", "-c", "print('hi')"], capture=True)
assert result.stdout == "hi\n"
```

```python
from jamsh import run_many_live

results = run_many_live(
    [
        ["python", "-c", "print('one')"],
        ["python", "-c", "print('two')"],
    ],
    max_parallel=2,
)
```

```bash
python -m jamsh.demo
```
