# SAGE Framework — Solutions

This directory holds **solution configurations** that plug in to the SAGE Framework.
Each solution is a self-contained folder with three YAML files and optional tooling.

---

## Licensing boundary

| Folder | Owner | Distributed with SAGE? | License |
|---|---|---|---|
| `medtech/` | SAGE Contributors | ✅ Yes (example) | MIT |
| `poseengine/` | SAGE Contributors | ✅ Yes (example) | MIT |
| `kappture/` | SAGE Contributors | ✅ Yes (example) | MIT |
| `dfs/` | DFS (company property) | ❌ No — private repo | Proprietary |
| `customer_*/` | Customer | ❌ No — private repo | Customer |

> **Rule:** Only open/example solutions belong in the SAGE repository.
> Proprietary solutions live in their own private repositories and are mounted
> at runtime. Nothing in `solutions/dfs/` is ever committed here.

---

## How proprietary solutions attach to SAGE

Proprietary solutions do **not** need to be copied into the SAGE repo.
Use the `SAGE_SOLUTIONS_DIR` environment variable to point SAGE at any directory:

```bash
# DFS engineers: clone your private solution repo somewhere
git clone git@your-internal-gitlab/dfs-sage-solution.git ~/dfs-solution

# Then run SAGE pointing at it
SAGE_SOLUTIONS_DIR=~/dfs-solution SAGE_PROJECT=dfs python src/main.py api

# Or in your .env file:
SAGE_SOLUTIONS_DIR=/opt/company-solutions
SAGE_PROJECT=dfs
```

The SAGE framework never needs to "know" about DFS internally —
it simply loads whatever is at `$SAGE_SOLUTIONS_DIR/dfs/`.

---

## Solution directory structure

```
solutions/<name>/
├── project.yaml       # Required: name, domain, active_modules, integrations
├── prompts.yaml       # Required: agent system prompts (analyst, developer, …)
├── tasks.yaml         # Required: task_types list + descriptions
├── LICENSE            # Required: state ownership (MIT or Proprietary NOTICE)
├── README.md          # Recommended: what this solution does
├── tests/             # Optional: solution-specific pytest tests
│   └── conftest.py    #   (add SAGE_ROOT to sys.path)
├── tools/             # Optional: solution-specific helper scripts
└── mcp_servers/       # Optional: MCP server configs
```

See `medtech/` for a complete example. Copy it as a starting template:

```bash
cp -r solutions/medtech solutions/my_new_solution
# Edit project.yaml, prompts.yaml, tasks.yaml for your domain
```

---

## Creating a proprietary solution repository

The recommended layout for a private solution repo is identical to the folder
above, but at the **root** of the private repository:

```
dfs-sage-solution/              ← private Git repo root
├── dfs/                        ← solution folder (matches SAGE_PROJECT=dfs)
│   ├── project.yaml
│   ├── prompts.yaml
│   ├── tasks.yaml
│   ├── LICENSE (PROPRIETARY NOTICE)
│   ├── tests/
│   └── tools/
└── README.md
```

Then set `SAGE_SOLUTIONS_DIR=/path/to/dfs-sage-solution` when running SAGE.

---

## Example solutions included in this repo

| Solution | Domain | Purpose |
|---|---|---|
| `medtech/` | Medical device / ISO 13485 | Reference implementation for regulated industries |
| `poseengine/` | ML / Mobile (Flutter) | AI-assisted development for CV/pose estimation products |
| `kappture/` | Human tracking (GDPR) | GDPR-aware solution for tracking software vendors |
