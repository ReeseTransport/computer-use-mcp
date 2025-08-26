"""
Computer Use MCP: Local computer control (no VM) through MCP.
"""
import os
import base64
import logging
import sys
import time
import subprocess
import platform
from io import BytesIO
from PIL import Image
from typing import Dict, List, Optional, Any, Union

from pydantic import BaseModel, Field
from fastmcp import FastMCP, Context

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

mcp = FastMCP(name="Computer MCP (Local) 🖥️")

class ComputerConfig(BaseModel):
    os_type: str = Field(default_factory=lambda: platform.system().lower(), description="Operating system type")
    display_width: int = Field(0, description="Display width in pixels (0=auto)")
    display_height: int = Field(0, description="Display height in pixels (0=auto)")

class ComputerRegistry:
    def __init__(self):
        self.computers: Dict[str, "LocalComputer"] = {}
        self.default_session = "default"

    def get(self, session_id: Optional[str] = None):
        session_id = session_id or self.default_session
        if session_id not in self.computers:
            raise ValueError(f"No computer found for session '{session_id}'. Initialize one first.")
        return self.computers[session_id]

    def add(self, computer, session_id: Optional[str] = None):
        session_id = session_id or self.default_session
        self.computers[session_id] = computer
        return session_id

    def remove(self, session_id: Optional[str] = None) -> bool:
        session_id = session_id or self.default_session
        return bool(self.computers.pop(session_id, None))

    def list_sessions(self) -> List[str]:
        return list(self.computers.keys())

registry = ComputerRegistry()

class LocalComputer:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        try:
            import pyautogui  # noqa: F401
        except Exception as e:
            raise ImportError("pyautogui is required. Install with: pip install pyautogui pillow") from e
        self._cfg = config or {}

    @staticmethod
    def _pg():
        import pyautogui
        return pyautogui

    @staticmethod
    def _as_base64_image(img, quality: int = 60, fmt: str = "JPEG") -> str:
        buff = BytesIO()
        format_upper = (fmt or "JPEG").upper()
        try:
            if format_upper == "PNG":
                # PNG doesn't support quality, optimize, or progressive
                img.save(buff, format=format_upper)
            else:
                # JPEG and other formats support these parameters
                img.save(buff, format=format_upper, quality=int(quality), optimize=True, progressive=True)
        except Exception:
            # Fallback without format-specific parameters
            img.save(buff, format=format_upper)
        return base64.b64encode(buff.getvalue()).decode("utf-8")

    def _scale_image(self, img, max_width: Optional[int] = None, max_height: Optional[int] = None):
        try:
            orig_w, orig_h = img.size
            mw = int(max_width) if max_width else int(self._cfg.get("screenshot_max_width", 800))
            mh = int(max_height) if max_height else int(self._cfg.get("screenshot_max_height", 0))
            if (mw and mw > 0):
                scale_w = mw / float(orig_w)
            else:
                scale_w = None
            if (mh and mh > 0):
                scale_h = mh / float(orig_h)
            else:
                scale_h = None
            scale_candidates = [s for s in [scale_w, scale_h] if s]
            scale = min(scale_candidates) if scale_candidates else 1.0
            if scale >= 1.0:
                return img
            new_size = (max(1, int(orig_w * scale)), max(1, int(orig_h * scale)))
            return img.resize(new_size, Image.LANCZOS)
        except Exception:
            return img

    def screenshot_base64(
        self,
        max_width: Optional[int] = None,
        max_height: Optional[int] = None,
        quality: Optional[int] = None,
        fmt: Optional[str] = None,
    ) -> str:
        img = self._pg().screenshot()
        img = self._scale_image(img, max_width=max_width, max_height=max_height)
        q = int(quality) if quality is not None else int(self._cfg.get("screenshot_quality", 50))
        f = (fmt or self._cfg.get("screenshot_format", "PNG")).upper()
        return self._as_base64_image(img, quality=q, fmt=f)

    def screenshot(self):
        return self._pg().screenshot()

    def left_click(self, x: int, y: int):
        self._pg().click(x=x, y=y, button="left")

    def right_click(self, x: int, y: int):
        self._pg().click(x=x, y=y, button="right")

    def double_click(self, x: int, y: int):
        self._pg().doubleClick(x=x, y=y)

    def scroll(self, direction: str = "down", amount: int = 1):
        direction = (direction or "down").strip().lower()
        if direction == "up":
            self._pg().scroll(int(amount))
        elif direction == "down":
            self._pg().scroll(-int(amount))
        else:
            raise ValueError(f"Unsupported scroll direction: {direction}")

    def type(self, text: str):
        self._pg().typewrite(text, interval=0.01)

    def key(self, key: str):
        if not key:
            return
        parts = [p.strip().lower() for p in key.replace(" ", "").split("+") if p.strip()]
        if len(parts) > 1:
            self._pg().hotkey(*parts)
        else:
            self._pg().press(parts[0])

    def wait(self, seconds: float):
        time.sleep(float(seconds))

    def bash(self, command: str) -> str:
        if not command:
            return ""
        system = platform.system().lower()
        try:
            if system == "windows":
                pwsh = os.environ.get("PWSH_PATH", "pwsh")
                use_pwsh = False
                try:
                    subprocess.run([pwsh, "-v"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                    use_pwsh = True
                except Exception:
                    use_pwsh = False

                if use_pwsh:
                    proc = subprocess.run(
                        [pwsh, "-NoLogo", "-NoProfile", "-Command", command],
                        capture_output=True, text=True, shell=False
                    )
                else:
                    proc = subprocess.run(
                        ["cmd", "/c", command],
                        capture_output=True, text=True, shell=False
                    )
            else:
                bash_path = "/bin/bash" if os.path.exists("/bin/bash") else None
                if bash_path:
                    proc = subprocess.run(
                        [bash_path, "-lc", command],
                        capture_output=True, text=True, shell=False
                    )
                else:
                    proc = subprocess.run(
                        command, capture_output=True, text=True, shell=True
                    )

            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.strip() or f"Command failed with code {proc.returncode}")
            return proc.stdout
        except Exception as e:
            raise RuntimeError(f"Command failed: {e}") from e

    def restart(self) -> Dict[str, Any]:
        return {"status": "unsupported_in_local_mode", "reason": "Restart is disabled for safety."}

    def shutdown(self) -> Dict[str, Any]:
        return {"status": "unsupported_in_local_mode", "reason": "Shutdown is disabled for safety."}

    def status(self) -> Dict[str, Any]:
        try:
            size = self._pg().size()
            pos = self._pg().position()
        except Exception:
            size = None
            pos = None
        return {
            "mode": "local",
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "screen_size": {"width": getattr(size, "width", None), "height": getattr(size, "height", None)},
            "cursor_position": {"x": getattr(pos, "x", None), "y": getattr(pos, "y", None)},
            "pid": os.getpid(),
        }

@mcp.tool()
async def initialize_computer(
    api_key: str,
    project_id: Optional[str] = None,
    session_id: Optional[str] = None,
    base_api_url: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    ctx: Optional[Context] = None
) -> Dict[str, Any]:
    """Initialize a local computer session. No API key required; api_key is ignored for compatibility."""
    if ctx:
        await ctx.info(f"Initializing LOCAL computer for session: {session_id or 'default'}")
    try:
        # Set default configuration for screenshot optimization
        default_config = {
            "screenshot_max_width": 800,
            "screenshot_quality": 50,
            "screenshot_format": "PNG"
        }
        if config:
            default_config.update(config)
        computer = LocalComputer(config=default_config)
        session_id = registry.add(computer, session_id)
        status = computer.status()
        if ctx:
            await ctx.info("Local computer initialized.")
        return {"session_id": session_id, "project_id": None, "status": status}
    except ImportError as ie:
        if ctx:
            await ctx.error(str(ie))
        raise ValueError(str(ie))
    except Exception as e:
        if ctx:
            await ctx.error(f"Failed to initialize local computer: {str(e)}")
        raise ValueError(f"Computer initialization failed: {str(e)}")

@mcp.tool()
async def get_screenshot(
    session_id: Optional[str] = None,
    max_width: Optional[int] = None,
    max_height: Optional[int] = None,
    quality: Optional[int] = None,
    image_format: Optional[str] = "PNG",
    ctx: Optional[Context] = None
) -> Dict[str, str]:
    """Take a screenshot of the local computer's display (optionally scaled/compressed)."""
    computer = registry.get(session_id)
    if ctx:
        await ctx.info("Taking screenshot...")
    try:
        image_data = computer.screenshot_base64(
            max_width=max_width,
            max_height=max_height,
            quality=quality,
            fmt=image_format,
        )
        if not image_data:
            if ctx:
                await ctx.warning("No image data from screenshot_base64, trying fallback...")
            screenshot = computer.screenshot()
            q = int(quality) if quality is not None else int(getattr(computer, "_cfg", {}).get("screenshot_quality", 50))
            f = (image_format or "PNG")
            image_data = LocalComputer._as_base64_image(screenshot, quality=q, fmt=f)
        return {"image": image_data}
    except Exception as e:
        if ctx:
            await ctx.error(f"Screenshot failed: {str(e)}")
        raise ValueError(f"Screenshot failed: {str(e)}")

@mcp.tool()
async def left_click(
    x: int,
    y: int,
    session_id: Optional[str] = None,
    include_image: bool = False,
    max_width: Optional[int] = None,
    max_height: Optional[int] = None,
    quality: Optional[int] = None,
    image_format: Optional[str] = None,
    ctx: Optional[Context] = None
) -> Dict[str, Any]:
    """Perform a left mouse click at the specified coordinates."""
    computer = registry.get(session_id)
    if ctx:
        await ctx.info(f"Left-clicking at ({x}, {y})")
    try:
        computer.left_click(x, y)
        if include_image:
            image_data = computer.screenshot_base64(
                max_width=max_width, max_height=max_height, quality=quality, fmt=image_format
            )
            return {"message": f"Left-clicked at ({x}, {y})", "image": image_data}
        return {"message": f"Left-clicked at ({x}, {y})"}
    except Exception as e:
        if ctx:
            await ctx.error(f"Left-click failed: {str(e)}")
        raise ValueError(f"Left-click failed: {str(e)}")

@mcp.tool()
async def right_click(
    x: int,
    y: int,
    session_id: Optional[str] = None,
    include_image: bool = False,
    max_width: Optional[int] = None,
    max_height: Optional[int] = None,
    quality: Optional[int] = None,
    image_format: Optional[str] = None,
    ctx: Optional[Context] = None
) -> Dict[str, Any]:
    """Perform a right mouse click at the specified coordinates."""
    computer = registry.get(session_id)
    if ctx:
        await ctx.info(f"Right-clicking at ({x}, {y})")
    try:
        computer.right_click(x, y)
        if include_image:
            image_data = computer.screenshot_base64(
                max_width=max_width, max_height=max_height, quality=quality, fmt=image_format
            )
            return {"message": f"Right-clicked at ({x}, {y})", "image": image_data}
        return {"message": f"Right-clicked at ({x}, {y})"}
    except Exception as e:
        if ctx:
            await ctx.error(f"Right-click failed: {str(e)}")
        raise ValueError(f"Right-click failed: {str(e)}")

@mcp.tool()
async def double_click(
    x: int,
    y: int,
    session_id: Optional[str] = None,
    include_image: bool = False,
    max_width: Optional[int] = None,
    max_height: Optional[int] = None,
    quality: Optional[int] = None,
    image_format: Optional[str] = None,
    ctx: Optional[Context] = None
) -> Dict[str, Any]:
    """Perform a double click at the specified coordinates."""
    computer = registry.get(session_id)
    if ctx:
        await ctx.info(f"Double-clicking at ({x}, {y})")
    try:
        computer.double_click(x, y)
        if include_image:
            image_data = computer.screenshot_base64(
                max_width=max_width, max_height=max_height, quality=quality, fmt=image_format
            )
            return {"message": f"Double-clicked at ({x}, {y})", "image": image_data}
        return {"message": f"Double-clicked at ({x}, {y})"}
    except Exception as e:
        if ctx:
            await ctx.error(f"Double-click failed: {str(e)}")
        raise ValueError(f"Double-click failed: {str(e)}")

@mcp.tool()
async def scroll(
    direction: str = "down",
    amount: int = 1,
    session_id: Optional[str] = None,
    include_image: bool = False,
    max_width: Optional[int] = None,
    max_height: Optional[int] = None,
    quality: Optional[int] = None,
    image_format: Optional[str] = None,
    ctx: Optional[Context] = None
) -> Dict[str, Any]:
    """Scroll in the specified direction and amount."""
    computer = registry.get(session_id)
    if ctx:
        await ctx.info(f"Scrolling {direction} by {amount}")
    try:
        computer.scroll(direction, amount)
        if include_image:
            image_data = computer.screenshot_base64(
                max_width=max_width, max_height=max_height, quality=quality, fmt=image_format
            )
            return {"message": f"Scrolled {direction} by {amount}", "image": image_data}
        return {"message": f"Scrolled {direction} by {amount}"}
    except Exception as e:
        if ctx:
            await ctx.error(f"Scroll failed: {str(e)}")
        raise ValueError(f"Scroll failed: {str(e)}")

@mcp.tool()
async def type_text(
    text: str,
    session_id: Optional[str] = None,
    include_image: bool = False,
    max_width: Optional[int] = None,
    max_height: Optional[int] = None,
    quality: Optional[int] = None,
    image_format: Optional[str] = None,
    ctx: Optional[Context] = None
) -> Dict[str, Any]:
    """Type the specified text into the active window."""
    computer = registry.get(session_id)
    if ctx:
        await ctx.info(f"Typing text: {text[:50]}{'...' if len(text) > 50 else ''}")
    try:
        computer.type(text)
        if include_image:
            image_data = computer.screenshot_base64(
                max_width=max_width, max_height=max_height, quality=quality, fmt=image_format
            )
            return {"message": f"Typed: {text}", "image": image_data}
        return {"message": f"Typed: {text}"}
    except Exception as e:
        if ctx:
            await ctx.error(f"Type text failed: {str(e)}")
        raise ValueError(f"Type text failed: {str(e)}")

@mcp.tool()
async def press_key(
    key: str,
    session_id: Optional[str] = None,
    include_image: bool = False,
    max_width: Optional[int] = None,
    max_height: Optional[int] = None,
    quality: Optional[int] = None,
    image_format: Optional[str] = None,
    ctx: Optional[Context] = None
) -> Dict[str, Any]:
    """Press a key or key combination (e.g., 'Enter', 'ctrl+c')."""
    computer = registry.get(session_id)
    if ctx:
        await ctx.info(f"Pressing key: {key}")
    try:
        computer.key(key)
        if include_image:
            image_data = computer.screenshot_base64(
                max_width=max_width, max_height=max_height, quality=quality, fmt=image_format
            )
            return {"message": f"Pressed key: {key}", "image": image_data}
        return {"message": f"Pressed key: {key}"}
    except Exception as e:
        if ctx:
            await ctx.error(f"Key press failed: {str(e)}")
        raise ValueError(f"Key press failed: {str(e)}")

@mcp.tool()
async def wait(seconds: float, session_id: Optional[str] = None, ctx: Optional[Context] = None) -> str:
    """Wait for the specified number of seconds."""
    computer = registry.get(session_id)
    if ctx:
        await ctx.info(f"Waiting for {seconds} seconds")
    try:
        computer.wait(seconds)
        return f"Waited for {seconds} seconds"
    except Exception as e:
        if ctx:
            await ctx.error(f"Wait failed: {str(e)}")
        raise ValueError(f"Wait failed: {str(e)}")

@mcp.tool()
async def execute_bash(command: str, session_id: Optional[str] = None, ctx: Optional[Context] = None) -> str:
    """Execute a shell command on the local computer."""
    computer = registry.get(session_id)
    if ctx:
        await ctx.info(f"Executing shell command: {command}")
    try:
        output = computer.bash(command)
        return output
    except Exception as e:
        if ctx:
            await ctx.error(f"Command failed: {str(e)}")
        raise ValueError(f"Command failed: {str(e)}")

@mcp.tool()
async def restart_computer(session_id: Optional[str] = None, ctx: Optional[Context] = None) -> Dict[str, Any]:
    """Restart the local computer (disabled for safety)."""
    computer = registry.get(session_id)
    if ctx:
        await ctx.info("Restart requested (local mode)")
    try:
        return computer.restart()
    except Exception as e:
        if ctx:
            await ctx.error(f"Restart failed: {str(e)}")
        raise ValueError(f"Restart failed: {str(e)}")

@mcp.tool()
async def shutdown_computer(session_id: Optional[str] = None, ctx: Optional[Context] = None) -> Dict[str, Any]:
    """Shutdown/terminate the local computer (disabled for safety)."""
    computer = registry.get(session_id)
    if ctx:
        await ctx.info("Shutdown requested (local mode)")
    try:
        result = computer.shutdown()
        registry.remove(session_id)
        return result
    except Exception as e:
        logger.warning(f"Error during shutdown handling: {e}. Removing from registry anyway.")
        registry.remove(session_id)
        return {"status": "removed_from_registry", "warning": f"Local shutdown not executed: {str(e)}"}

@mcp.tool()
async def get_status(session_id: Optional[str] = None, ctx: Optional[Context] = None) -> Dict[str, Any]:
    """Get the current status of the local computer."""
    computer = registry.get(session_id)
    if ctx:
        await ctx.info("Getting computer status...")
    try:
        status = computer.status()
        return status
    except Exception as e:
        if ctx:
            await ctx.error(f"Status check failed: {str(e)}")
        raise ValueError(f"Status check failed: {str(e)}")

@mcp.tool()
async def list_sessions(ctx: Optional[Context] = None) -> Dict[str, List[str]]:
    """List all active computer sessions."""
    if ctx:
        await ctx.info("Listing all active sessions...")
    try:
        sessions = registry.list_sessions()
        return {"sessions": sessions}
    except Exception as e:
        if ctx:
            await ctx.error(f"Failed to list sessions: {str(e)}")
        raise ValueError(f"Failed to list sessions: {str(e)}")

@mcp.tool()
async def prompt(
    instruction: str,
    options: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    ctx: Optional[Context] = None
) -> Dict[str, Any]:
    """Orgo-agent natural language control is not available in local mode."""
    if ctx:
        await ctx.warning("prompt is unsupported in local mode (no Orgo backend).")
    raise ValueError("prompt is unsupported in local mode (no Orgo backend).")

from enum import Enum
from pydantic import BaseModel, Field, validator

class CapturePolicy(str, Enum):
    always = "always"
    on_error = "on_error"
    never = "never"

class BatchOptions(BaseModel):
    halt_on_error: bool = True
    capture: CapturePolicy = CapturePolicy.on_error
    max_steps: int = 25
    default_max_width: int = 800
    default_max_height: int = 0
    default_quality: int = 50
    image_format: str = "PNG"
    rate_limit_ms: int = 50
    max_output_chars: int = 4000
    default_step_timeout_sec: int = 10

    @validator("max_steps")
    def max_steps_positive(cls, v):
        if v <= 0 or v > 1000:
            raise ValueError("max_steps must be > 0 and reasonable")
        return v

    @validator("rate_limit_ms")
    def rate_non_negative(cls, v):
        if v < 0:
            raise ValueError("rate_limit_ms must be >= 0")
        return v

class StepModel(BaseModel):
    type: str
    x: Optional[int] = None
    y: Optional[int] = None
    direction: Optional[str] = None
    amount: Optional[int] = None
    text: Optional[str] = None
    key: Optional[str] = None
    seconds: Optional[float] = None
    command: Optional[str] = None
    include_image: Optional[bool] = None
    max_width: Optional[int] = None
    max_height: Optional[int] = None
    quality: Optional[int] = None
    image_format: Optional[str] = None
    timeout_sec: Optional[float] = None
    max_output_chars: Optional[int] = None

    @validator("type")
    def lower_type(cls, v):
        return (v or "").strip().lower()

class StepResult(BaseModel):
    index: int
    type: str
    ok: bool
    message: Optional[str] = None
    image: Optional[str] = None
    error: Optional[str] = None
    started_at: float
    ended_at: float
    duration_ms: int

class BatchResult(BaseModel):
    ok: bool
    results: List[StepResult]
    first_error_index: Optional[int] = None
    total: int = 0
    session_id: Optional[str] = None

# Disallowed/unsafe step types inside batches
_DISALLOWED_BATCH_STEPS = {"restart", "shutdown", "prompt"}

# Allowed step types
_ALLOWED_BATCH_STEPS = {
    "left_click",
    "right_click",
    "double_click",
    "scroll",
    "type_text",
    "press_key",
    "wait",
    "execute_bash",
    "get_screenshot",
}

async def batch_actions_impl(
    steps: List[dict],
    options: Optional[dict] = None,
    session_id: Optional[str] = None,
    ctx: Optional[Context] = None
) -> Dict[str, Any]:
    """
    Execute a sequence of local actions in a single request.
    See README for allowed step types and options.
    """
    # Parse/validate options and steps using pydantic
    opts = BatchOptions(**(options or {}))
    if not isinstance(steps, list) or len(steps) == 0:
        raise ValueError("steps must be a non-empty list")
    if len(steps) > opts.max_steps:
        raise ValueError(f"Number of steps ({len(steps)}) exceeds max_steps ({opts.max_steps})")

    parsed_steps: List[StepModel] = []
    for s in steps:
        if not isinstance(s, dict):
            raise ValueError("Each step must be an object/dict")
        step = StepModel(**s)
        if step.type in _DISALLOWED_BATCH_STEPS:
            raise ValueError(f"Step type '{step.type}' is disallowed in batch for safety")
        if step.type not in _ALLOWED_BATCH_STEPS:
            raise ValueError(f"Unknown step type: {step.type}")
        parsed_steps.append(step)

    computer = registry.get(session_id)
    results: List[StepResult] = []
    first_error_index: Optional[int] = None

    if ctx:
        await ctx.info(f"Starting batch_actions ({len(parsed_steps)} steps), halt_on_error={opts.halt_on_error}, capture={opts.capture}")

    for idx, step in enumerate(parsed_steps):
        start = time.time()
        image_data = None
        ok = True
        message = None
        error_msg = None

        # per-step capture decision and image params
        per_include = step.include_image if step.include_image is not None else False
        capture_now = opts.capture == CapturePolicy.always or per_include

        try:
            t = step.type
            if t == "left_click":
                if step.x is None or step.y is None:
                    raise ValueError("left_click requires x and y")
                computer.left_click(step.x, step.y)
                message = f"Left-clicked at ({step.x}, {step.y})"
            elif t == "right_click":
                if step.x is None or step.y is None:
                    raise ValueError("right_click requires x and y")
                computer.right_click(step.x, step.y)
                message = f"Right-clicked at ({step.x}, {step.y})"
            elif t == "double_click":
                if step.x is None or step.y is None:
                    raise ValueError("double_click requires x and y")
                computer.double_click(step.x, step.y)
                message = f"Double-clicked at ({step.x}, {step.y})"
            elif t == "scroll":
                if not step.direction or step.amount is None:
                    raise ValueError("scroll requires direction and amount")
                computer.scroll(step.direction, step.amount)
                message = f"Scrolled {step.direction} by {step.amount}"
            elif t == "type_text":
                if step.text is None:
                    raise ValueError("type_text requires text")
                computer.type(step.text)
                message = f"Typed text"
            elif t == "press_key":
                if step.key is None:
                    raise ValueError("press_key requires key")
                computer.key(step.key)
                message = f"Pressed key: {step.key}"
            elif t == "wait":
                if step.seconds is None:
                    raise ValueError("wait requires seconds")
                computer.wait(step.seconds)
                message = f"Waited {step.seconds} seconds"
            elif t == "execute_bash":
                if step.command is None:
                    raise ValueError("execute_bash requires command")
                try:
                    output = computer.bash(step.command)
                    max_out = step.max_output_chars if (step.max_output_chars is not None) else opts.max_output_chars
                    if output is None:
                        output = ""
                    if len(output) > max_out:
                        output = output[:max_out] + "...(truncated)"
                    message = f"Command output: {output}"
                except Exception as e:
                    raise RuntimeError(str(e))
            elif t == "get_screenshot":
                # per-step overrides or fallbacks from options
                mw = step.max_width if step.max_width is not None else opts.default_max_width
                mh = step.max_height if step.max_height is not None else opts.default_max_height
                q = step.quality if step.quality is not None else opts.default_quality
                fmt = step.image_format if step.image_format is not None else opts.image_format
                img = computer.screenshot_base64(max_width=mw, max_height=mh, quality=q, fmt=fmt)
                image_data = img
                message = "Screenshot captured"
            else:
                raise ValueError(f"Unknown step type: {step.type}")
        except Exception as e:
            ok = False
            error_msg = str(e)
            if first_error_index is None:
                first_error_index = idx
            if ctx:
                await ctx.error(f"Batch step {idx} failed: {error_msg}")

        # capture per policy on error
        if opts.capture == CapturePolicy.on_error and not ok:
            try:
                image_data = computer.screenshot_base64(
                    max_width=opts.default_max_width,
                    max_height=opts.default_max_height,
                    quality=opts.default_quality,
                    fmt=opts.image_format,
                )
            except Exception:
                # ignore capture failure
                image_data = None

        # capture if always policy and not already captured
        if opts.capture == CapturePolicy.always and image_data is None:
            try:
                image_data = computer.screenshot_base64(
                    max_width=opts.default_max_width,
                    max_height=opts.default_max_height,
                    quality=opts.default_quality,
                    fmt=opts.image_format,
                )
            except Exception:
                image_data = None

        end = time.time()
        duration_ms = int((end - start) * 1000)
        res = StepResult(
            index=idx,
            type=step.type,
            ok=ok,
            message=message,
            image=image_data,
            error=error_msg,
            started_at=start,
            ended_at=end,
            duration_ms=duration_ms
        )
        results.append(res)

        # rate limit between steps
        if idx < len(parsed_steps) - 1 and opts.rate_limit_ms and opts.rate_limit_ms > 0:
            time.sleep(opts.rate_limit_ms / 1000.0)

        if not ok and opts.halt_on_error:
            break

    summary_ok = all(r.ok for r in results)
    batch_result = BatchResult(
        ok=summary_ok,
        results=results,
        first_error_index=first_error_index,
        total=len(results),
        session_id=session_id
    )
    if ctx:
        await ctx.info(f"Batch completed: {len(results)} steps, ok={batch_result.ok}, first_error_index={batch_result.first_error_index}")
    return batch_result.model_dump()
 
# register the MCP tool wrapper while keeping the impl available for direct calls/tests
batch_actions = mcp.tool("batch_actions")(batch_actions_impl)
 
@mcp.resource("computer://server/info")
def server_info() -> Dict[str, Any]:
    """Information about the Computer MCP server."""
    return {
        "name": "Computer MCP (Local)",
        "description": "MCP interface for controlling your own computer (mouse/keyboard/screenshot/commands)",
        "version": "2.1.0-local",
        "active_sessions": len(registry.computers)
    }

@mcp.prompt()
def desktop_guidelines() -> str:
    """Guidelines for interacting with desktop environments (Windows/macOS/Linux)."""
    return """# Desktop Interaction Guidelines (Local)

## Essential Actions
* Opening apps/files: Double-click desktop icons or single-click taskbar/dock items
* Menu selections: Single-click menu items
* Window controls: Single-click close, minimize, maximize buttons

## Common Keyboard Shortcuts (Windows)
* Win+D: Show desktop
* Alt+Tab: Switch windows
* Win+E: Open File Explorer
* Ctrl+C / Ctrl+V: Copy / Paste
* Alt+F4: Close current window

## Best Practices
* Take a screenshot first to assess current state
* Prefer double_click for desktop icons; single-click for taskbar/dock
* Use Enter to submit forms
* Use wait for long operations
"""

if __name__ == "__main__":
    # mcp.run()
    mcp.run(transport="streamable-http", host="127.0.0.1", port=9000)