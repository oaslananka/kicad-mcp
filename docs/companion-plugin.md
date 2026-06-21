# KiCad companion plugin

A small KiCad **Action Plugin** that connects the running pcbnew GUI to a local
kicad-mcp server. It lets an agent see what you have open and selected, and gates
any board-mutating action behind a confirmation dialog.

It is intentionally minimal-permission: it talks **only** to the loopback MCP
endpoint and never writes files itself.

## What it does

- Publishes the active project / file / selection context to the MCP server
  (via the existing `studio_push_context` tool).
- Surfaces health/status of the connection in a dialog.
- Provides a **safe-apply** confirmation gate (`confirm_safe_apply`) that mutating
  flows must pass before touching the board.

The plugin is a thin GUI shim; all of its logic lives in the dependency-free,
unit-tested `kicad_mcp.companion.context` module so it can evolve without a KiCad
in the loop.

## Install

1. Locate your KiCad plugins directory:
   - **Windows:** `%APPDATA%\kicad\<version>\scripting\plugins`
   - **macOS:** `~/Documents/KiCad/<version>/scripting/plugins`
   - **Linux:** `~/.local/share/kicad/<version>/scripting/plugins`
   (or open *Tools → External Plugins → Open Plugin Directory* in pcbnew).
2. Copy or symlink `packages/kicad-plugin` into that directory as
   `kicad_mcp_companion`.
3. Make the shared helpers importable from KiCad's Python by pointing
   `KICAD_MCP_HOME` at your kicad-mcp checkout (the folder containing `src/`):

   ```bash
   # set in your shell profile or KiCad launch environment
   export KICAD_MCP_HOME=/path/to/kicad-mcp
   export KICAD_MCP_URL=http://127.0.0.1:3334   # optional, this is the default
   export KICAD_MCP_AUTH_TOKEN=...              # only if the server requires auth
   ```

4. Restart pcbnew, then run *Tools → External Plugins → Refresh*. A
   **kicad-mcp companion** toolbar button appears.

## Smoke test plan

These steps require a real KiCad install and cannot be exercised in headless CI;
the dependency-free helpers are covered by `tests/unit/test_companion_context.py`.

1. Start the server: `uv run kicad-mcp-pro --transport streamable-http --port 3334`.
2. Open any `.kicad_pcb` in pcbnew.
3. Click **kicad-mcp companion**. Expect an information dialog confirming the
   context push to `http://127.0.0.1:3334`.
4. In another MCP client, read the `kicad://studio/context` resource and confirm
   the active file and project root match what is open in KiCad.
5. Select a footprint, push again, and confirm `selected_reference` updates.
6. Stop the server and push again. Expect a clear error dialog (no crash).
7. Trigger a mutating action and confirm the **safe-apply** dialog appears and
   that declining it leaves the board unchanged.

## Security notes

- The plugin connects to `127.0.0.1` only.
- It does not request filesystem or network permissions beyond the loopback POST.
- Mutating operations are listed in `SAFE_APPLY_ACTIONS` and always require an
  explicit confirmation via `confirm_safe_apply`.
