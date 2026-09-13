# Setup

Steps to get a local dev environment running.

## 1. Python version

The project requires Python >= 3.11 (see `pyproject.toml`). If your system's
default `python3` is older (e.g. Ubuntu 22.04 ships 3.10), check what else is
already available before installing anything new:

```bash
python3 --version
python3.11 --version   # or
python3.13 --version
```

If a suitable interpreter isn't installed and you don't have sudo/apt access,
you can still create a venv without the `ensurepip` module and bootstrap pip
manually:

```bash
python3.13 -m venv --without-pip .venv
source .venv/bin/activate
curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
python /tmp/get-pip.py
```

If you do have apt access, the normal path is simpler:

```bash
sudo apt install python3.11-venv   # or python3.13-venv
python3.11 -m venv .venv
source .venv/bin/activate
```

## 2. Install dependencies

```bash
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"
```

This installs the package in editable mode plus dev tools (pytest, ruff).

## 3. Environment variables

```bash
cp .env.example .env
```

Fill in at minimum `OPENROUTER_API_KEY`. Other keys (LangSmith, Semantic
Scholar, OpenAlex mailto, Qdrant) are optional for early phases — defaults in
`.env.example` work for local dev with Chroma + SQLite.

## 4. Verify

```bash
ruff check .
pytest
```

Nothing is runnable end-to-end yet (see README.md build phases) — this just
confirms the environment is sane.
