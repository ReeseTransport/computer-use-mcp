# Changelog

## Unreleased
- feat(mcp): Added batch_actions tool with strict validation, capture policy (always | on_error | never), per-step overrides, and safe shell output truncation. Implementation at [batch_actions_impl()](./computer_mcp_server.py:632).
- docs(readme): Added “Batch actions” section with examples, settings, and safety notes; clarified single-step screenshot flags. See [README.md](./README.md).
- test(server): Added unit and mocked-integration tests covering validation, capture policy, halt_on_error, and shell output truncation in [test_computer_mcp_server.py](./test_computer_mcp_server.py).
- chore(version): Bumped server version to 2.1.0-local in [server_info()](./computer_mcp_server.py:805).
- fix(mcp): Registered MCP tool explicitly as "batch_actions" via decorator; aligns API with docs. See [batch_actions](./computer_mcp_server.py:820).
- docs(readme): Clarified that per-step include_image in batch only affects [get_screenshot()](./computer_mcp_server.py:258); other steps follow capture policy. See [README.md](./README.md).