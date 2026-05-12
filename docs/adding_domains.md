# Adding a New Domain

## Steps

### 1. Create data files

```
data/<domain>/
  users.json
  products.json   (or whatever the domain uses)
  orders.json     (or reservations.json, etc.)
  policy.md
  tasks.json
```

### 2. Register DB shape

In `core/db.py`, add an entry to `DOMAIN_DB_SHAPES`:

```python
DOMAIN_DB_SHAPES = {
    "retail": ["users", "products", "orders"],
    "airline": ["users", "flights", "reservations"],
    "your_domain": ["users", "items", "transactions"],  # add this
}
```

### 3. Implement tools

Create `src/taufreebench/domains/<domain>/tools.py`.

Use the `@tool` decorator with `domain="<domain>"`:

```python
from taufreebench.core.tool import tool

@tool(name="get_item", description="Get item details.", read_only=True, domain="your_domain")
def get_item(db, item_id: str) -> dict:
    ...
```

Tools receive `db` as the first argument. Read-only tools should not modify `db`.

### 4. Create seed_data.py

```python
from pathlib import Path
from taufreebench.core.serialization import load_json

DATA_DIR = Path(__file__).parent.parent.parent.parent.parent / "data" / "your_domain"

def load_db(data_dir=None):
    d = data_dir or DATA_DIR
    return {"users": load_json(d / "users.json"), ...}
```

### 5. Register in run_episode.py

Add domain to `_ensure_domain_tools()` in `runners/run_episode.py`:

```python
elif domain == "your_domain":
    import taufreebench.domains.your_domain.tools
```

### 6. Add tasks

Each task in `tasks.json`:

```json
{
  "id": "your_domain_task_001",
  "instruction": "Hidden user instruction...",
  "expected_actions": [
    {"name": "tool_name", "arguments": {...}}
  ],
  "required_outputs": ["key phrase"],
  "max_turns": 20,
  "tags": ["tag1"]
}
```

`expected_actions` should be **only write actions** (DB-mutating). Read actions don't affect evaluation.

### 7. Add scripted user scripts

In `users/scripted_user.py`, add entries to `_TASK_SCRIPTS`:

```python
"your_domain_task_001": [
    "Opening message...",
    "My email is ...",
    "Yes, please proceed.",
],
```

### 8. Test

```bash
python -m taufreebench.cli seed-data --domain your_domain
python -m taufreebench.cli run-episode --domain your_domain --task your_domain_task_001 --agent rule --user scripted
```
