# Tool Usage Guide

## `ls` — List Directory Contents

Returns entries sorted alphabetically with a `/` suffix for directories. Includes dotfiles. Output is truncated to 500 entries or 50 KB.

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `path` | string | current directory | Directory to list |
| `limit` | number | 500 | Max entries returned |

**Examples:**
```
ls(path=".")                          # list current directory
ls(path="/home/user/src")             # list a specific path
ls(path=".", limit=50)                # limit results
```

**Tips:** Use with no arguments to inspect the current working directory. Use `path` to navigate.

---

## `read` — Read File Contents

Reads text files and images (jpg, png, gif, webp, bmp). Text output is truncated to 2000 lines or 50 KB. For large files, use `offset`/`limit` to read in chunks.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `path` | string | yes | Path to file (relative or absolute) |
| `offset` | number | no | Line number to start from (1-indexed) |
| `limit` | number | no | Max lines to read |

**Examples:**
```
read(path="README.md")                         # read entire file
read(path="src/main.py", limit=100)            # first 100 lines
read(path="src/main.py", offset=50, limit=50)  # lines 50–99
```

**Tips:** For large files, start with no offset/limit, then use `offset` to continue reading from where you left off. Read images to inspect them visually.

---

## `grep` — Search File Contents

Searches for a pattern across files. Returns matching lines with file paths and line numbers. Respects `.gitignore`. Output is truncated to 100 matches or 50 KB. Long lines are truncated to 500 chars.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `pattern` | string | yes | Regex or literal search pattern |
| `path` | string | no | Directory or file to search (default: current) |
| `glob` | string | no | Filter by glob, e.g. `*.ts`, `**/*.json` |
| `literal` | boolean | no | Treat pattern as literal (default: false/regex) |
| `ignoreCase` | boolean | no | Case-insensitive search (default: false) |
| `context` | number | no | Lines before/after each match (default: 0) |
| `limit` | number | no | Max matches returned (default: 100) |

**Examples:**
```
grep(pattern="TODO")                              # find all TODOs
grep(pattern="def render", glob="*.py")           # Python functions named render
grep(pattern="error", path="src", context=2)      # with surrounding lines
grep(pattern="C:\\\\Users", literal=true)         # literal backslash search
grep(pattern="import", ignoreCase=true, glob="*.{ts,tsx}")
```

**Tips:** Use `glob` to narrow the file set. Use `literal=true` when searching for regex-special characters. Use `context` to see surrounding code.

---

## `find` — Find Files by Glob Pattern

Returns file paths matching a glob pattern, relative to the search directory. Respects `.gitignore`. Output is truncated to 1000 results or 50 KB.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `pattern` | string | yes | Glob pattern (e.g. `*.ts`, `**/*.json`, `src/**/*.spec.ts`) |
| `path` | string | no | Directory to search in (default: current) |
| `limit` | number | no | Max results (default: 1000) |

**Examples:**
```
find(pattern="*.md")                              # all markdown files
find(pattern="**/*.test.ts")                      # test files anywhere
find(pattern="src/**/*.py", path=".")             # Python files under src/
find(pattern="**/config.*")                       # any file named config.*
```

**Tips:** Use `**/` to recurse into subdirectories. Combine with `read` to inspect found files. Use `limit` when you expect many matches.

---

## Common Patterns

| Goal | Tool | Example |
|------|------|---------|
| Explore a new directory | `ls` | `ls(path="src/")` |
| Read a known file | `read` | `read(path="src/main.py")` |
| Find where something is defined | `grep` | `grep(pattern="class Foo", glob="*.py")` |
| Find all files of a type | `find` | `find(pattern="**/*.json")` |
| Search with context | `grep` | `grep(pattern="bug", context=3, glob="*.py")` |
| Read a large file in chunks | `read` | `read(path="file.py", offset=1, limit=500)`, then `offset=501` |