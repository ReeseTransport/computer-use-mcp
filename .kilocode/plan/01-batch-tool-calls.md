# Design: Optional batch_actions MCP tool for local Computer MCP

Scope
- Add a new optional tool batch_actions that executes multiple local actions in one request.
- Preserve existing single-step tool behavior and interfaces; no breaking changes.
- Update README usage with examples and settings.
- Add tests (unit + mocked integration) that pass locally on Windows 11.

Current Surface (for mapping)
- Single-step tools in [`computer_mcp_server.py`](./computer_mcp_server.py):
  - [`initialize_computer()`](./computer_mcp_server.py:222), [`get_screenshot()`](./computer_mcp_server.py:258), [`left_click()`](./computer_mcp_server.py:291), [`right_click()`](./computer_mcp_server.py:320), [`double_click()`](./computer_mcp_server.py:349), [`scroll()`](./computer_mcp_server.py:378), [`type_text()`](./computer_mcp_server.py:407), [`press_key()`](./computer_mcp_server.py:435), [`wait()`](./computer_mcp_server.py:463), [`execute_bash()`](./computer_mcp_server.py:477), [`get_status()`](./computer_mcp_server.py:519), [`list_sessions()`](./computer_mcp_server.py:533)

Proposed MCP tool
- Name: batch_actions
- Registration: decorated with @mcp.tool in [`computer_mcp_server.py`](./computer_mcp_server.py)
- Behavior: Sequentially executes validated steps; safe defaults; returns per-step envelopes and an overall summary. Optional bounded screenshots per policy and caps.

Pydantic request schema (concept)
- BatchActionsRequest(BaseModel)
  - session_id: Optional[str] = None
  - steps: List[BatchStep]  # 1..max_steps
  - halt_on_error: bool = True
  - capture: Literal["always","on_error","never"] = "on_error"
  - include_image: bool = False
  - max_width: Optional[int] = 800
  - max_height: Optional[int] = 0
  - quality: Optional[int] = 50
  - image_format: Optional[Literal["JPEG","PNG"]] = "JPEG"
  - rate_limit_ms: int = 50
  - max_output_chars: int = 2000
  - default_step_timeout_sec: float = 10.0
  - max_steps: int = 25  # upper bound; locked default

- BatchStep(BaseModel)  # discriminated union by type
  - type: Literal[
      "left_click", "right_click", "double_click",
      "scroll", "type_text", "press_key", "wait",
      "execute_bash", "get_screenshot"
    ]
  - timeout_sec: Optional[float] = None
  - Fields by type:
    - left_click/right_click/double_click: x: int; y: int
    - scroll: direction: Literal["up","down"]; amount: int
    - type_text: text: str
    - press_key: key: str
    - wait: seconds: float
    - execute_bash: command: str; max_output_chars: Optional[int]
    - get_screenshot: include_image: Optional[bool] = True; max_width/max_height/quality/image_format (override top-level)

Pydantic response schema (concept)
- BatchActionsResponse(BaseModel)
  - ok: bool
  - steps: List[StepResult]
  - first_error_index: Optional[int] = None
  - error: Optional[str] = None
  - summary: str
  - count: int
  - session_id: Optional[str] = None

- StepResult(BaseModel)
  - index: int
  - type: str
  - ok: bool
  - message: Optional[str] = None
  - image: Optional[str] = None  # base64
  - error: Optional[str] = None
  - started_at: float  # epoch seconds
  - ended_at: float
  - duration_ms: int

Supported step types and mapping
- left_click → [`left_click()`](./computer_mcp_server.py:291)
- right_click → [`right_click()`](./computer_mcp_server.py:320)
- double_click → [`double_click()`](./computer_mcp_server.py:349)
- scroll → [`scroll()`](./computer_mcp_server.py:378)
- type_text → [`type_text()`](./computer_mcp_server.py:407)
- press_key → [`press_key()`](./computer_mcp_server.py:435)
- wait → [`wait()`](./computer_mcp_server.py:463)
- execute_bash → [`execute_bash()`](./computer_mcp_server.py:477)
- get_screenshot → [`get_screenshot()`](./computer_mcp_server.py:258)

Validation rules
- steps: required; 1 ≤ len(steps) ≤ max_steps; default max_steps = 25 (cannot be raised by caller)
- timeouts: per-step timeout_sec if provided must be 0 < timeout ≤ 3600; default from default_step_timeout_sec (0 < default ≤ 3600)
- rate_limit_ms: ≥ 0; default 50; applied after each step (except after the last)
- include_image: boolean gate for capturing images on non-screenshot steps; top-level default False
- capture policy:
  - always: attempt image capture for each step result (subject to include_image gate and per-step include_image override for get_screenshot)
  - on_error: capture only on step failure; default
  - never: never capture, ignoring include_image and per-step flags
- image bounds:
  - max_width: 0 disables width bound; default 800; must be 0 or 64..1600
  - max_height: 0 disables height bound; default 0; if provided, must be ≥ 64 and ≤ 1200
  - quality: 1..95; default 50; format default JPEG for interactive captures; PNG recommended for get_screenshot
- execute_bash output: truncate to min(step.max_output_chars or request.max_output_chars, 10000); default 2000; never stream
- disallowed types: restart/shutdown/prompt and any unknown type are rejected at validation
- numeric args:
  - click coords: ints within 0..display bounds not enforced by schema; pass-through to PyAutoGUI
  - scroll amount: int; direction only "up" or "down"
  - wait seconds: ≥ 0 and ≤ 3600

Execution semantics
- Sequential processing from index 0..n-1
- Validation performed before execution; if validation fails, no steps run
- For each step:
  - note started_at
  - execute mapped single-step operation
  - on error:
    - ok=false; error=string; message optional
    - capture image if capture ∈ {"always","on_error"} and include_image logic allows
    - if halt_on_error: stop; set first_error_index; ok in response false
  - on success:
    - ok=true; message set to prior single-step tool message or brief success string
    - capture per policy
  - note ended_at and duration_ms
  - apply rate_limit_ms sleep between steps
- Overall response:
  - ok = all steps ok (or all up to first error if halted)
  - summary string with counts and error index if present
  - first_error_index when any step failed
  - steps contain partial results even on halt; deterministic order

Error model and partial progress
- Preflight schema errors: raise ValueError with details; no side effects
- Runtime step errors: reported in StepResult.error; accumulated; partial results returned
- Deterministic ordering/logging; no retries; idempotence not guaranteed for UI actions, documented

Safety and security
- Local-only; no remote control
- No restart/shutdown/prompt steps; not supported/validated
- execute_bash output truncated; stderr folded into error if non-zero exit
- Screenshot capture limits: size/quality caps; default capture on error only; include_image default false
- Never log base64 images to console; only return via tool result
- Windows 11 primary environment; PowerShell/cmd used under the hood as in single-step

README changes
- Add “Batch actions” section with:
  - Overview of batch_actions and safety defaults
  - Copy-paste example using FastMCP Client
  - Settings table with: halt_on_error, capture, include_image, max_width, max_height, quality, image_format, rate_limit_ms, default_step_timeout_sec, max_steps, max_output_chars
  - Notes:
    - Interactive captures default JPEG; get_screenshot defaults PNG
    - capture policy precedence vs include_image and per-step overrides
    - Bounded outputs and images; local-only caution
- Clarify single-step flags:
  - Shared include_image, max_width, max_height, quality, image_format defaults and bounds in one consolidated table

Copy-paste example (README)
- Python FastMCP Client:
  - Initialize
  - Call batch_actions with steps [type_text, press_key, get_screenshot]
  - Print summary; verify per-step ok flags

Test plan
- Unit tests
  - Validation:
    - Reject unknown type; missing args; steps length > max_steps; invalid bounds for quality/width/height/timeouts
    - capture policy interactions; never suppresses images; on_error captures only when step fails
    - execute_bash truncation behavior (provided long stdout simulated)
  - Semantics:
    - halt_on_error=True stops at first failure and sets first_error_index
    - halt_on_error=False continues and aggregates multiple errors
- Integration tests (mocked)
  - Patch LocalComputer._pg to a stub; patch screenshot() to return a 20x20 solid image; patch screenshot_base64 to use scaling path
  - Batch: [type_text:"Hello"], [press_key:"Enter"], [get_screenshot:{}] with capture="always", include_image=True
    - Assert ok overall; three StepResult items; image present in all three; PNG for get_screenshot step when not overridden
  - Failure path:
    - Batch: valid type_text then invalid step type → expect schema fail without executing
    - Batch: valid type_text then scroll with bad direction "left" → runtime error at index; verify halt and images captured per on_error
- E2E manual checklist (doc-only)
  - Run server, connect, run example batch, inspect behavior on focused notepad window

File touch list (implementation phase)
- /computer_mcp_server.py          # add: Pydantic models + @mcp.tool batch_actions + dispatcher/validators
- /README.md                       # modify: new “Batch actions” section + settings table + examples
- /test_computer_mcp_server.py     # modify: unit + mocked integration tests

Acceptance criteria
- batch_actions is registered with @mcp.tool and callable; returns per-step envelopes and overall summary
- Backward compatibility preserved; existing tools unchanged
- Validation and bounds enforced; default max_steps=25; default capture on_error; include_image default false
- Screenshots: caps applied; interactive steps default JPEG; get_screenshot default PNG
- execute_bash output truncated per limits
- README contains example and settings table plus clarifications for single-steps
- Tests pass locally on Windows 11 (unittest)

Rollout and rollback
- Rollout: Add tool alongside existing; bump server_info version to 2.1.0-local
- Fallback: If issues found, agents can avoid calling batch_actions; single steps unaffected
- Rollback: Revert changes to batch code path and README; tests referencing batch are skipped or removed

Open questions
- Should we expose per-step delay overrides beyond rate_limit_ms? Default: no; owner: Requestor
- Should we allow lossless PNG for interactive captures via image_format override? Default: yes via top-level image_format; owner: Requestor
- Do we need a global timeout for the whole batch? Default: no; owner: Manager

Command checklist (developer)
- git checkout -b task/batch-actions
- py -m venv .venv && .\.venv\Scripts\Activate.ps1
- pip install -r requirements.txt
- python -m unittest -v
- python computer_mcp_server.py  # dev run
- python -m unittest -v test_computer_mcp_server.py

Risks and mitigations
- UI flakiness / focus issues → document cautions; wait step available; default halt_on_error=True
- Large images / bandwidth → default caps and capture on_error; enforce upper bounds
- Shell side effects → output truncation; explicit error propagation; no streaming

Performance/SLOs
- Targets: 95p latency ≤ 2s for a 3-step batch with no images on a typical desktop
- Batching limit 25; rate_limit_ms default 50 to avoid rapid-fire events

Telemetry/observability
- Use Context.info/warning/error per step; summarize batch with counts and first_error_index
- Include per-step duration for lightweight timing insight