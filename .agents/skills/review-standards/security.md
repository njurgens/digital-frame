---
name: security
description: 'Review checklist for the security domain of a peer review. Read this when assigned the "security" domain: injection, path traversal, authn/authz gaps, secrets handling, unsafe deserialization, crypto misuse, SSRF, dependency risk, and attacker-controlled resource exhaustion. Includes security-specific severity calibration and worked findings.'
---

# Domain: security

You are reviewing **what an attacker could do with this change**. Assume input
is hostile, the network is hostile, and at least one caller is authenticated but
not authorized.

## In scope

- **Injection**: SQL built by string concatenation or f-strings; shell commands
  via `shell=True`, `os.system`, backticks, or an unescaped argument; NoSQL query
  operators from user input; LDAP, XPath, or template injection; log injection
  via unescaped newlines.
- **Path traversal and file handling**: user-controlled paths joined to a base
  directory without normalization and containment checks; archive extraction
  without checking member paths (zip-slip); symlink following; upload filenames
  used verbatim.
- **Authentication and authorization**: a new endpoint, handler, task, or admin
  action added without an authz check; an object fetched by ID with no ownership
  check; authorization decided on the client side or from a user-supplied field;
  a check that runs after the side effect.
- **Secrets**: keys, tokens, passwords, or connection strings hard-coded in
  source, tests, fixtures, or config committed to the repo; secrets logged,
  echoed in error messages, or included in exception context; secrets in URLs or
  query strings.
- **Unsafe deserialization**: `pickle`, `marshal`, `yaml.load` without
  `SafeLoader`, `eval`, `exec`, `Function()`, Java/`.NET` binary deserialization,
  or JSON parsed into arbitrary class instantiation.
- **Cryptography misuse**: `md5`/`sha1` for passwords or signatures; ECB mode; a
  static or reused IV/nonce; a hand-rolled crypto routine; a comparison of
  secrets with `==` instead of a constant-time compare; a key derived from a
  weak source.
- **Randomness**: `random`/`Math.random` used for tokens, session IDs, password
  resets, or nonces instead of a CSPRNG.
- **Transport and request handling**: TLS verification disabled
  (`verify=False`, `rejectUnauthorized: false`, `InsecureSkipVerify`); redirects
  followed to user-controlled hosts; SSRF via a user-supplied URL fetched
  server-side; missing timeouts letting a hostile server hold a connection.
- **Web-specific**: XSS from unescaped output or `dangerouslySetInnerHTML`;
  missing CSRF protection on a state-changing form; overly broad CORS
  (`*` with credentials); cookies missing `HttpOnly`, `Secure`, or `SameSite`;
  open redirect.
- **Access control on resources**: new files or directories created with
  world-readable/writable permissions; temp files created predictably.
- **Denial of service**: unbounded input read into memory; user-controlled
  regex or a regex with catastrophic backtracking on user input; unbounded
  recursion or loop count driven by input; no rate limiting on an expensive
  unauthenticated endpoint.
- **Dependencies**: a new dependency added — is it well-known, pinned, and from
  the real registry (watch for typosquat-looking names)? Is a pin being loosened?
- **Privacy in logs**: PII, tokens, full request bodies, or auth headers written
  to logs or telemetry.

## Out of scope

- Ordinary bugs with no attacker in the story — that is `correctness`. A missing
  null check is theirs; a missing null check that an attacker can trigger to
  crash the service is yours, reported as availability.
- Whether the change is fast — that is `performance`, except when unbounded cost
  is attacker-controlled, which is yours.
- Whether the security-relevant code is well-placed — that is `architecture`.

## Checklist

1. Identify every place user input enters the changed code. Follow each one to
   where it is used.
2. Any string that becomes a query, command, path, URL, HTML, or template: is it
   parameterized or escaped?
3. Any new route/handler/command: what enforces authn and authz on it? Name the
   line that does.
4. Any lookup by ID: is ownership or tenancy checked?
5. `grep` the diff for: `password`, `secret`, `token`, `api_key`, `BEGIN
   PRIVATE KEY`, long base64/hex literals.
6. `grep` the diff for: `eval`, `exec`, `pickle`, `yaml.load`, `shell=True`,
   `os.system`, `subprocess` with a string, `innerHTML`, `verify=False`,
   `InsecureSkipVerify`, `md5`, `sha1`, `random.`.
7. Any new outbound HTTP call with a URL from a request: SSRF check, allowlist,
   timeout.
8. Any file write: path containment, permissions, temp file creation method.
9. Any new dependency in a lockfile/manifest: name plausibility, version pin.
10. Any error handler or log statement that includes the raw exception or request:
    could it leak a secret or internal path?
11. Any comparison of a token, HMAC, or password hash: constant-time?
12. Any loop, allocation, or recursion whose size comes from the request.

## Severity calibration for security

- `blocker` — Exploitable by an unauthenticated or low-privilege attacker for
  code execution, data access across tenants, authentication bypass, or secret
  disclosure. Also: any live credential committed to the repository, regardless
  of how narrow its scope appears.
- `major` — A real weakness that needs a precondition: missing authz on an
  endpoint that is currently unlinked, TLS verification disabled in a non-prod
  path that could be promoted, weak hashing of non-password data, PII in logs,
  SSRF limited to internal metadata endpoints.
- `minor` — Defense-in-depth gaps: a missing security header, a cookie flag not
  set, an overly permissive file mode, an unpinned dependency, a missing timeout.
- `nit` — Style-level hardening suggestions with no realistic attack path today.

If you report a `blocker`, state the attack in one sentence: who does what, and
what they get.

## Worked examples

**Example 1**

```
### FINDING 1
SEVERITY: blocker
FILE: src/reports/query.py:57
ISSUE: The report filter is interpolated into the SQL string with an f-string, so any authenticated user can pass `' OR 1=1 --` in the `filter` query parameter and read every tenant's rows.
FIX: Use a parameterized query and bind the filter value, or validate it against an allowlist of column names before interpolating.
```

**Example 2**

```
### FINDING 2
SEVERITY: major
FILE: src/api/routes/export.py:23
ISSUE: The new `/export/{account_id}` handler loads the account by the path parameter without checking that it belongs to the requesting user, so any logged-in user can export another account by guessing an ID.
FIX: Look up the account scoped to `request.user`, or call the existing `require_account_access(user, account_id)` guard used at `routes/billing.py:31`.
```

## Output

Use the format defined in [./SKILL.md](./SKILL.md) under "Required output
format". Do not invent your own.
