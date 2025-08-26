import asyncio
import unittest

from computer_mcp_server import batch_actions_impl, registry

class FakeLocalComputer:
    def __init__(self, screenshot_data="IMGDATA", bash_output=None):
        self._screenshot = screenshot_data
        self._bash_output = bash_output or ("OUT" * 2000)

    def left_click(self, x, y):
        # no-op
        return None

    def right_click(self, x, y):
        return None

    def double_click(self, x, y):
        return None

    def scroll(self, direction, amount):
        return None

    def type(self, text):
        return None

    def key(self, key):
        return None

    def wait(self, seconds):
        return None

    def bash(self, command):
        # Simulate long output
        if "fail" in command:
            raise RuntimeError("command failed")
        return self._bash_output

    def screenshot_base64(self, max_width=None, max_height=None, quality=None, fmt=None):
        return self._screenshot

class BatchActionsTests(unittest.TestCase):
    def setUp(self):
        # Ensure fresh registry state and a default fake computer
        registry.computers.clear()
        self.fake = FakeLocalComputer()
        registry.add(self.fake, session_id="default")

    def run_async(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_validation_unknown_step_type(self):
        with self.assertRaises(ValueError):
            self.run_async(batch_actions_impl(steps=[{"type": "unknown_step"}], options={}, session_id="default"))

    def test_max_steps_enforced(self):
        with self.assertRaises(ValueError):
            self.run_async(batch_actions_impl(steps=[{"type": "left_click", "x": 1, "y": 2}] * 3, options={"max_steps": 1}, session_id="default"))

    def test_disallowed_restart_shutdown_prompt(self):
        for t in ("restart", "shutdown", "prompt"):
            with self.assertRaises(ValueError):
                self.run_async(batch_actions_impl(steps=[{"type": t}], options={}, session_id="default"))

    def test_capture_policy_always_returns_images(self):
        steps = [{"type": "left_click", "x": 1, "y": 2}]
        result = self.run_async(batch_actions_impl(steps=steps, options={"capture": "always"}, session_id="default"))
        self.assertIn("results", result)
        self.assertEqual(len(result["results"]), 1)
        self.assertTrue(result["results"][0]["ok"])
        # capture=always should include an image (from fake)
        self.assertIsNotNone(result["results"][0].get("image"))

    def test_capture_on_error_includes_image(self):
        # First step will fail (missing x), capture on_error should include image for that step
        steps = [{"type": "left_click"}, {"type": "left_click", "x": 5, "y": 6}]
        result = self.run_async(batch_actions_impl(steps=steps, options={"capture": "on_error", "halt_on_error": True}, session_id="default"))
        self.assertIn("results", result)
        self.assertEqual(len(result["results"]), 1)  # halted on first error
        self.assertFalse(result["results"][0]["ok"])
        self.assertIsNotNone(result["results"][0].get("image"))
        self.assertEqual(result["first_error_index"], 0)

    def test_halt_on_error_false_continues_and_reports_first_error(self):
        steps = [{"type": "left_click"}, {"type": "left_click", "x": 5, "y": 6}]
        result = self.run_async(batch_actions_impl(steps=steps, options={"capture": "on_error", "halt_on_error": False}, session_id="default"))
        self.assertEqual(len(result["results"]), 2)
        self.assertFalse(result["results"][0]["ok"])
        self.assertTrue(result["results"][1]["ok"])
        self.assertEqual(result["first_error_index"], 0)

    def test_execute_bash_truncation_and_error(self):
        # Provide a bash output longer than max_output_chars and verify truncation
        long_output = "A" * 5000
        self.fake = FakeLocalComputer(screenshot_data="IMG", bash_output=long_output)
        registry.computers.clear()
        registry.add(self.fake, session_id="default")

        steps = [{"type": "execute_bash", "command": "echo long"}]
        result = self.run_async(batch_actions_impl(steps=steps, options={"max_output_chars": 100}, session_id="default"))
        self.assertEqual(len(result["results"]), 1)
        msg = result["results"][0]["message"]
        self.assertIn("truncated", msg)

        # Non-zero exit should surface as error
        self.fake = FakeLocalComputer(screenshot_data="IMG", bash_output="OK")
        # override bash to raise
        def failing_bash(command):
            raise RuntimeError("non-zero")
        self.fake.bash = failing_bash
        registry.computers.clear()
        registry.add(self.fake, session_id="default")
        result2 = self.run_async(batch_actions_impl(steps=[{"type": "execute_bash", "command": "fail"}], options={"halt_on_error": False}, session_id="default"))
        self.assertFalse(result2["ok"])
        self.assertEqual(result2["first_error_index"], 0)

    def test_short_integration_type_press_screenshot(self):
        # A small batch: type_text, press_key, get_screenshot
        self.fake = FakeLocalComputer(screenshot_data="BASE64IMG")
        registry.computers.clear()
        registry.add(self.fake, session_id="default")
        steps = [
            {"type": "type_text", "text": "hello"},
            {"type": "press_key", "key": "enter"},
            {"type": "get_screenshot"}
        ]
        result = self.run_async(batch_actions_impl(steps=steps, options={"capture": "always"}, session_id="default"))
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["results"]), 3)
        # final step should include image (screenshot)
        self.assertIsNotNone(result["results"][2].get("image"))

if __name__ == "__main__":
    unittest.main()