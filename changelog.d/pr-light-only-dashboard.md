## PR: Light-only dashboard (2026-10-07)

- The dashboard now always shows the light palette, whatever the device setting or a previously saved theme choice.
- Remove the Dark mode toggle, the pre-paint theme script and every dark color token. Light colors are unchanged.
- Replace the dark theme contrast checks with tests that assert the light-only contract.
