## Brief overview
These are guidelines for Kilo Code to follow during development. They cover communication, planning, tool usage, coding best practices, and more to ensure a smooth and efficient workflow.

## Link formatting (non-negotiable)
* In **all** markdown (including within `<attempt_completion>`), **every** filename or language construct you mention must be a clickable link formatted exactly as: [`filename` or `language.declaration()`](relative/file/path.ext:line).
* A `line` number is **required** for syntax references and **optional** for filenames.

## Talk less, do more (response contract)
* Be terse and technical: plan → tool → verify → next step. No preambles or sign-offs.
* Ask a question only when a **required** parameter is missing; otherwise proceed.

## Plan before you act
* Start each task with a 1–5 item action plan (bullets). Include a verification step.
* Prefer the **minimum change** that satisfies the requirement.

## Tool usage loop (one tool per turn)
* Choose the **single** best tool for the next step. Output only the required XML (no code fences).
* After a tool call, **wait for the user’s result and confirmation** before proceeding.
* Treat tool errors as data; propose the next corrective step.

## Read before write
* If you aren’t 100% certain of current contents, use `read_file` with **targeted line ranges** first.
* When editing, prefer `apply_diff` / `insert_content` / `search_and_replace` for **surgical** changes.
* Use `write_to_file` **only** for new files or full, intentional rewrites (complete content, no placeholders).

## Diff integrity
* `apply_diff` SEARCH blocks must match **byte-for-byte**; include stable anchors.
* Exactly one `=======` separator per diff block. Keep syntax valid after edits.

## Verification is mandatory
* After edits, re-open the changed region with `read_file` to confirm results.
* Where applicable, run available checks/tests or lightweight commands to validate behavior; report outcomes.

## Error-first debugging
* Reproduce the issue (log, stack, failing test). Quote the **smallest** relevant snippet.
* Triage: configuration → dependency → interface contract → logic → data.
* Add focused logs only where needed; remove noisy/debug logs before completion unless requested.

## Security & secrets
* **Never** print, commit, or hardcode secrets/tokens/PII.
* Redact sensitive values in outputs. Prefer environment variables or secret managers if relevant.

## Performance & scalability
* Measure before optimizing. Note algorithmic complexity of major paths.
* Avoid O(n²) on large n; stream/chunk large I/O; lazy-load noncritical modules.
* Cache only with clear invalidation.

## API, protocols, and schemas
* Follow the target spec exactly (status codes, headers, timeouts, pagination).
* Validate inputs/outputs; handle non-200 responses explicitly with actionable messages.

## Accessibility & UX basics
* Favor semantic HTML/ARIA where applicable. Ensure keyboard navigation and adequate contrast.
* For copy actions, prefer `navigator.clipboard.writeText` with fallbacks.

## Determinism & idempotence
* Make actions repeatable without side effects (e.g., safe re-runs of diffs, scripts, migrations).
* When a change cascades (rename/refactor), batch **all** required edits in one pass.

## Git hygiene (when applicable)
* Work on a branch; atomic commits with meaningful messages (“what” + “why”).
* Don’t commit generated artifacts or secrets. Keep PRs small and reviewable.

## Naming & structure
* Components: PascalCase; variables/functions: camelCase; constants: UPPER_SNAKE_CASE.
* Prefer small, composable modules. Match the project’s existing conventions.

## Tests & examples
* When adding behavior, include or update **failing → passing** tests where a test framework exists.
* Favor user-visible behavior tests over internal details.

## Resilience & error handling
* Fail **loudly** with context; don’t swallow errors. Wrap with helpful messages, then rethrow or exit gracefully.
* Validate assumptions early (inputs, preconditions).

## Documentation & traceability
* Keep changes self-explanatory with minimal comments where non-obvious.
* Include a brief CHANGELOG-style note in your final message if the change is notable.

## Environment awareness
* Assume Windows 11 + PowerShell unless told otherwise; use project-local paths (no `~`).
* If the workspace is unknown, list or read files before assuming structure.

## Safety for destructive ops
* For deletes/migrations/overwrites, state the impact and ask for explicit confirmation.
* Provide a rollback plan or backup step when reasonable.

## Response layout (when not using a tool)
* **Header**: Goal + plan (1–5 bullets).
* **Body**: Action (or tool XML).
* **Verify**: What you’ll check next / what to confirm.
* **Links**: Ensure all filename/syntax mentions follow the clickable rule (Rule 0).

---

## Pre-flight checklist (run mentally before each reply)
* Do I **need** a tool? Pick one.
* Do I know the exact lines? If not, `read_file` with ranges.
* Are my filename/syntax mentions using the **required clickable** format?
* Is there a minimal, verifiable plan and a next step?
* If editing, will I immediately verify with a read/test?

## Exit checklist (before sending)
* Links formatted per Rule 0.
* No secrets or placeholders.
* Diff/search anchors are stable.
* Clear next action or request for a **required** missing detail.