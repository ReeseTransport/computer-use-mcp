Implementation notes

- Added batch batch_actions MCP tool and models in [batch_actions_impl()](./computer_mcp_server.py:632); registered wrapper as batch_actions to keep existing single-step tools unchanged. Server version bumped in [server_info()](./computer_mcp_server.py:805) to 2.1.0-local.
- Safety/validation: disallowed step types {"restart","shutdown","prompt"}; strict type/arg checks; default max_steps=25; capture policy always|on_error|never; per-step screenshot overrides; execute_bash output truncated (default 4000 chars) and non-zero exit treated as error.
- Defaults alignment: Single-step include_image semantics preserved; README clarified defaults and batch behavior; get_screenshot remains PNG lossless.
- Reviewer fixes: explicitly registered MCP tool as "batch_actions" via decorator in [batch_actions](./computer_mcp_server.py:820); clarified README note that per-step include_image within batch only affects [get_screenshot()](./computer_mcp_server.py:258); tests pass via `python -m unittest -v` per [test_computer_mcp_server.py](./test_computer_mcp_server.py).
- Tests: Deterministic, mocked LocalComputer via registry injection; validate validation, capture policy, halt_on_error behavior, shell truncation, and a short happy-path batch.
- Warnings: Pydantic v2 deprecation warnings remain for @validator; functional behavior OK; replaced dict() with model_dump() for result.
- Local test command: python -m unittest -v test_computer_mcp_server.py

Files touched

- [computer_mcp_server.py](./computer_mcp_server.py)
- [test_computer_mcp_server.py](./test_computer_mcp_server.py)
- [README.md](./README.md)

External references

- None (implementation followed existing code patterns and PLAN.md)