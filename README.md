# Computer Use MCP Server (Local) 🖥️

Control your own computer through MCP using FastMCP and PyAutoGUI. No cloud VM or API keys required.

This server backs mouse, keyboard, screenshot, and local shell commands on your machine.

## Requirements

- Python 3.8+
- fastmcp, pydantic, pyautogui, pillow

## Install

Windows (PowerShell):

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install fastmcp pydantic pyautogui pillow
```

macOS/Linux (bash):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install fastmcp pydantic pyautogui pillow
```

macOS note: grant Screen Recording permission to your terminal/IDE for screenshots to work.

## Run the server

```bash
python computer_mcp_server.py
```

Endpoint: http://127.0.0.1:9000/mcp

Note: Interactive actions return only {"message"} by default. Pass include_image=true to also include a base64 screenshot (defaults: max_width=800, quality=50, format=PNG). get_screenshot defaults to PNG lossless.

## Client demo

```python
import asyncio
from fastmcp import Client

async def demo():
    async with Client("http://127.0.0.1:9000/mcp") as client:
        # Initialize local computer (api_key kept for compatibility; ignored in local mode)
        await client.call_tool("initialize_computer", {"api_key": "ignored"})

        # Screenshot
        ss = await client.call_tool("get_screenshot")
        print("Screenshot bytes (base64):", len(ss[0].text))

        # Mouse/keyboard (requires a visible target focused)
        await client.call_tool("left_click", {"x": 100, "y": 150})
        res = await client.call_tool("type_text", {"text": "Hello World"})
        print("Interactive result:", res[0].text)  # JSON with {"message","image"}
        await client.call_tool("press_key", {"key": "Enter"})

if __name__ == "__main__":
    asyncio.run(demo())
```

## Available tools

| Tool                                  | Description                                                                                 |
| ------------------------------------- | ------------------------------------------------------------------------------------------- |
| initialize_computer                   | Start a local session; returns status (screen size, cursor position)                        |
| get_screenshot                        | Capture screen (base64 PNG lossless); optional max_width/max_height/quality/image_format    |
| left_click, right_click, double_click | Mouse actions at x,y; include_image? and optional max_width/max_height/quality/format       |
| scroll                                | Scroll up/down by amount; include_image? and optional max_width/max_height/quality/format  |
| type_text, press_key                  | Keyboard input/hotkeys; include_image? and optional max_width/max_height/quality/format     |
| wait                                  | Pause for seconds                                                                           |
| execute_bash                          | Run a shell command (PowerShell/cmd on Windows; bash on POSIX)                              |
| batch_actions                         | Sequence multiple local steps with validation, capture policy, and safety limits            |
| get_status, list_sessions             | Status and session management                                                               |

## Batch actions (optional)

Batch multiple local steps in a single call while enforcing safety and predictable outputs.

- Local-only; uses your machine’s mouse/keyboard/shell.
- Safety: restart/shutdown/prompt are disallowed in batches.
- Validation: strict types/args with max_steps=25 by default.
- Capture policy: always | on_error | never. Screenshots are scaled/compressed using bounded dimensions/quality/format.
- Shell output: execute_bash stdout is truncated to a safe max (default 4000 chars).

Example JSON request

```json
{
  "steps": [
    { "type": "type_text", "text": "hello world" },
    { "type": "press_key", "key": "enter" },
    { "type": "wait", "seconds": 0.2 },
    { "type": "get_screenshot" }
  ],
  "options": {
    "halt_on_error": true,
    "capture": "on_error",
    "max_steps": 25,
    "default_max_width": 800,
    "default_max_height": 0,
    "default_quality": 50,
    "image_format": "PNG",
    "rate_limit_ms": 50,
    "max_output_chars": 4000,
    "default_step_timeout_sec": 10
  }
}
```

Example JSON response (shape)

```json
{
  "ok": true,
  "results": [
    {
      "index": 0,
      "type": "type_text",
      "ok": true,
      "message": "Typed text",
      "image": null,
      "error": null,
      "started_at": 1720000000.000,
      "ended_at": 1720000000.050,
      "duration_ms": 50
    },
    {
      "index": 3,
      "type": "get_screenshot",
      "ok": true,
      "message": "Screenshot captured",
      "image": "<base64>",
      "error": null,
      "started_at": 1720000000.200,
      "ended_at": 1720000000.280,
      "duration_ms": 80
    }
  ],
  "first_error_index": null,
  "total": 4,
  "session_id": "default"
}
```

Allowed step types and args

- left_click: x, y
- right_click: x, y
- double_click: x, y
- scroll: direction ("up"|"down"), amount
- type_text: text
- press_key: key
- wait: seconds
- execute_bash: command, max_output_chars? (overrides options.max_output_chars)
- get_screenshot: max_width?, max_height?, quality?, image_format?, include_image? (always captures for this step)

Options (batch-wide defaults)

- halt_on_error: bool (default true)
- capture: "always" | "on_error" | "never" (default "on_error")
- max_steps: int (default 25)
- default_max_width: int (default 800)
- default_max_height: int (default 0)
- default_quality: int (default 50)
- image_format: "PNG" | "JPEG" (default "PNG")
- rate_limit_ms: int (default 50)
- max_output_chars: int (default 4000)
- default_step_timeout_sec: number (default 10)

Notes and tips

- Use capture="on_error" for efficiency; switch to "always" when debugging.
- Insert small wait steps around UI transitions.
- Keep batches short and focused (≤ 10 steps recommended).
- Windows hotkeys: "ctrl+c", "alt+tab", "win+e", etc.
Disabled for safety/local mode:

- prompt: unsupported (no Orgo/Claude backend)
- restart_computer: disabled
- shutdown_computer: disabled

## Behavior and safety

- Commands act on YOUR machine: mouse may move and keys will type into the focused app.
- Prefer testing in a spare desktop/VM or with caution.
- On macOS, grant Accessibility and Screen Recording permissions if prompted.
- WSL/headless sessions are not supported; run in a regular desktop session.

## Configure your MCP client

Point your client to the endpoint above. For Windsurf/Kilo Code, edit your MCP settings file:

Windows:
`C:\Users\<you>\AppData\Roaming\Windsurf\User\globalStorage\kilocode.kilo-code\settings\mcp_settings.json`

Example entry:

```json
{
  "servers": {
    "computer-use-local": {
      "type": "sse",
      "url": "http://127.0.0.1:9000/mcp"
    }
  }
}
```

## Notes

- initialize_computer parameters api_key/project_id/base_api_url are accepted for schema compatibility but ignored.
- execute_bash returns stdout or raises on non-zero exit; commands run in PowerShell/cmd on Windows, bash on POSIX.
- The implementation lives in computer_mcp_server.py.
- Interactive tools (left_click/right_click/double_click/scroll/type_text/press_key) return {"message"} by default. To include a screenshot, pass include_image=true and optionally max_width/max_height/quality/image_format. Defaults: max_width=800, quality=50, format=PNG. get_screenshot defaults to PNG lossless.
- In batch_actions, per-step include_image only affects get_screenshot; other steps follow the capture policy ("always", "on_error", or "never").

# Desktop Interaction Guidelines (Local)

## Essential Actions

- Opening apps/files: Double-click desktop icons or single-click taskbar/dock items
- Menu selections: Single-click menu items
- Window controls: Single-click close, minimize, maximize buttons

## Common Keyboard Shortcuts (Windows)

- Win+D: Show desktop
- Alt+Tab: Switch windows
- Win+E: Open File Explorer
- Ctrl+C / Ctrl+V: Copy / Paste
- Alt+F4: Close current window

## Best Practices

- Take a screenshot first to assess current state
- Prefer double_click for desktop icons; single-click for taskbar/dock
- Use Enter to submit forms
- Use wait for long operations

## Safety

- Do NOT use prompt/restart_computer/shutdown_computer. Never handle secrets/PII.
