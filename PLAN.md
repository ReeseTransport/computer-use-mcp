# Plan: Add optional batch tool calls to Computer MCP and README usage updates

1. Goal & Non-Goals
- Goal: Add an optional, safe batch execution MCP tool that sequences multiple local actions (mouse/keyboard/screenshot/shell) in a single request; update README with usage and settings; add tests. Keep all existing single-step tools unchanged.
- Non-Goals: Remote/VM control; changing existing tool semantics or defaults; enabling restart/shutdown or prompt; parallel/async step execution; streaming results; handling secrets.

2. Current State
- Server uses FastMCP and PyAutoGUI; local-only actions with optional screenshots and a shell helper.
- Key constructs (reference for mapping and reuse):
  - Class and helpers in computer_mcp_server.py:
    - LocalComputer methods: screenshot_base64, screenshot, left_click, right_click, double_click, scroll, type, key, wait, bash
    - Session registry, status helpers, and server_info
  - Existing MCP tools in computer_mcp_server.py:
    - initialize_computer, get_screenshot, left_click, right_click, double_click, scroll, type_text, press_key, wait, execute_bash, get_status, list_sessions
- Tests: test_computer_mcp_server.py exists but is empty.
- Docs: README documents single-step tools and client demo.

3. Proposed Changes (implementation summary)
- Add a new optional tool batch_actions that:
  - Accepts a validated list of steps (max 25 by default) with per-step arguments and optional per-step timeout.
  - Executes sequentially, with a configurable halt_on_error (default true).
  - Supports capture policy (always | on_error | never), include_image, and bounded screenshot size/quality for step results.
  - Enforces rate limiting between steps and argument validation per step type.
  - Bounds shell output length for execute_bash (default max_output_chars=2000).
  - Returns a response with per-step results {ok, message, image?, error?, timings} and overall summary plus first_error_index when applicable.
- Update README:
  - New “Batch actions” section with copy-paste example (client call), settings table (halt_on_error, capture policy, include_image, max_width/height/quality, rate_limit_ms, per-step timeout, max_output_chars, max_steps), and practical guidance.
  - Clarify existing single-step include_image defaults and image format defaults in one consolidated table.
- Add tests in test_computer_mcp_server.py:
  - Unit tests: request/step validation (e.g., disallow unknown types, enforce required args, enforce max_steps).
  - Integration tests (safe/local): run a short batch (type_text + press_key + get_screenshot) using mocked pyautogui to avoid moving the real mouse/typing; verify capture policy behavior and that halt_on_error works.

File Touch List
- /computer_mcp_server.py          # modify: add @mcp.tool batch_actions, Pydantic models, validators, dispatcher
- /README.md                       # modify: add Batch actions section, settings table, examples
- /test_computer_mcp_server.py     # modify: add unit + integration tests with safe mocks

4. Interfaces & Data Contracts

Request (BatchActionsRequest):
- session_id?: string
- steps: array<BatchStep> (1..max_steps; default max_steps=25)
- halt_on_error?: boolean = true
- capture?: "always" | "on_error" | "never" = "on_error"
- include_image?: boolean = false
- max_width?: int = 800
- max_height?: int = 0
- quality?: int = 50
- image_format?: "JPEG" | "PNG" = "JPEG"
- rate_limit_ms?: int = 50
- max_output_chars?: int = 2000
- default_step_timeout_sec?: number = 10

BatchStep (union by type):
- Common: type: "left_click" | "right_click" | "double_click" | "scroll" | "type_text" | "press_key" | "wait" | "execute_bash" | "get_screenshot"; timeout_sec?: number
- left_click/right_click/double_click: x: int, y: int
- scroll: direction: "up"|"down", amount: int
- type_text: text: string
- press_key: key: string
- wait: seconds: number
- execute_bash: command: string, max_output_chars?: int (overrides request)
- get_screenshot: include_image?: boolean=true; max_width/max_height/quality/image_format (per-step overrides)

Response (BatchActionsResponse):
- ok: boolean
- steps: array<StepResult>
- first_error_index?: int
- error?: string
- summary: string
- count: int
- session_id?: string

StepResult:
- index: int
- type: string
- ok: boolean
- message?: string
- image?: string (base64) when captured
- error?: string
- started_at: float (epoch seconds)
- ended_at: float
- duration_ms: int

5. Migrations/Data Considerations
- No persistent data or schema migrations.
- Idempotency: UI actions are inherently non-idempotent; batch is best-effort with explicit halt_on_error to limit impact. Steps are executed strictly in order; no retries by default.

6. Rollout Strategy
- Add tool without altering existing tools; keep server version bump to 2.1.0-local in server_info for discoverability.
- Default-safe settings: halt_on_error=true, capture=on_error, include_image=false, rate_limit_ms=50, max_steps=25, default_step_timeout_sec=10.
- If issues arise: disable usage at the agent level by not calling batch_actions; fallback to existing single-step tools.

7. Testing Strategy
- Unit:
  - Validate schema: unknown step type rejected; missing required args rejected; max_steps enforced; quality/range bounds enforced; rate_limit_ms non-negative.
  - Capture policy logic: always vs on_error vs never influences image presence.
  - Output bounding: execute_bash output is truncated to max_output_chars.
- Integration (mocked pyautogui):
  - Patch LocalComputer._pg() to a stub with no-op click/press/type/scroll; patch screenshot to return a small image; assert that a batch [type_text, press_key, get_screenshot] returns ok results, and images are included only per policy.
  - Failure path: a batch with an invalid step causes halt at that index when halt_on_error=true; with false, continues and aggregates errors.
- E2E manual checklist (document-only): run server, connect via FastMCP Client, exercise example.

8. Telemetry & Observability
- Use Context.info/warning/error per step and for batch start/end.
- Include per-step timings in results.
- Summarize batch in a single final info log with counts and first_error_index.

9. Security/Privacy
- Local-only control; no remote secrets.
- execute_bash output length bounded; disallow restart/shutdown/prompt step types.
- Never echo full screenshots/logs to console; only return via tool result.

10. Performance & SLOs
- Constraints: max_steps=25, rate_limit_ms≥50, default_step_timeout_sec=10, screenshots scaled by max_width/max_height and quality.
- Target: batch of 3 simple steps returns within 2s on a typical desktop when no screenshots are included.

11. Risks & Mitigations
- UI flakiness: Use mocks in tests; document that active/focused window is required. Provide halt_on_error default true.
- Large images: Scale and quality defaults; capture default on_error; max dimensions enforced.
- Shell abuse: Bound output; document safety; tests for truncation.
- API misuse: Strict validation and explicit error messages with first_error_index.

12. Command Checklist
- git checkout -b task/batch-actions
- py -m venv .venv && .\.venv\Scripts\Activate.ps1
- pip install -r requirements.txt
- python computer_mcp_server.py
- In another shell, run tests:
  - python -m unittest -v test_computer_mcp_server.py

13. Acceptance Criteria
- New MCP tool batch_actions is registered and callable; returns structured results with per-step envelopes and overall summary.
- Backward compatibility: all existing single-step tools behave unchanged.
- Validation enforced: unknown step types or invalid args rejected; max_steps default 25 respected.
- Safety: no restart/shutdown/prompt steps allowed; execute_bash output bounded; batch halts on first error by default.
- Screenshots: capture policy works; size/quality caps applied; get_screenshot defaults PNG.
- README: includes Batch actions section with a copy-paste example and settings table; clarifies single-step include_image defaults.
- Tests pass locally with unittest.

14. Out of Scope
- Parallel step execution, retries, or conditional branching.
- Clipboard/file transfers, OCR, or UI element targeting.
- Remote VM backends or cloud services.

15. Timeline/Estimates
- Design and schemas: S
- Implementation and validation: M
- Tests (unit + mocked integration): M
- README/docs: S
- Total: M (~1–2 days)

Appendix: Step Mapping to Existing Tools
- left_click → left_click
- right_click → right_click
- double_click → double_click
- scroll → scroll
- type_text → type_text
- press_key → press_key
- wait → wait
- execute_bash → execute_bash
- get_screenshot → get_screenshot