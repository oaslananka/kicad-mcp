"""pcbnew Action Plugin entry point for the kicad-mcp companion (issue #157).

This module is only imported inside KiCad (it depends on ``pcbnew`` and ``wx``).
All testable logic lives in ``kicad_mcp.companion.context``; this file is the thin
GUI shim that reads the live board and drives that logic.
"""

from __future__ import annotations

import os
import sys

import pcbnew  # type: ignore[import-not-found]  # provided by KiCad


def _ensure_companion_importable() -> None:
    """Make ``kicad_mcp.companion`` importable from KiCad's bundled Python.

    Honours ``KICAD_MCP_HOME`` (the repo root or an installed package's parent) so
    the plugin can find the shared, dependency-free helpers without requiring a
    system-wide install.
    """
    home = os.environ.get("KICAD_MCP_HOME")
    if home:
        src = os.path.join(home, "src")
        for path in (src, home):
            if os.path.isdir(path) and path not in sys.path:
                sys.path.insert(0, path)


class KiCadMcpCompanionPlugin(pcbnew.ActionPlugin):
    """Publish live KiCad context to kicad-mcp and gate mutating actions."""

    def defaults(self) -> None:
        self.name = "kicad-mcp companion"
        self.category = "kicad-mcp"
        self.description = "Publish active board context to a running kicad-mcp server."
        self.show_toolbar_button = True

    def Run(self) -> None:
        import wx  # type: ignore[import-not-found]  # provided by KiCad

        _ensure_companion_importable()
        try:
            from kicad_mcp.companion.context import BoardInfo, StudioContextClient, build_studio_context
        except Exception as exc:  # noqa: BLE001 - surfaced to the user
            wx.MessageBox(
                f"kicad-mcp companion helpers not found.\n"
                f"Set KICAD_MCP_HOME to the kicad-mcp checkout.\n\n{exc}",
                "kicad-mcp companion",
                wx.ICON_ERROR,
            )
            return

        info = self._read_board_info(BoardInfo)
        base_url = os.environ.get("KICAD_MCP_URL", "http://127.0.0.1:3334")
        auth_token = os.environ.get("KICAD_MCP_AUTH_TOKEN", "")
        client = StudioContextClient(base_url, auth_token=auth_token)
        try:
            client.push(build_studio_context(info))
            wx.MessageBox(
                f"Pushed context for {info.file_name or 'active board'} to {base_url}.",
                "kicad-mcp companion",
                wx.ICON_INFORMATION,
            )
        except Exception as exc:  # noqa: BLE001 - network/server errors are user-facing
            wx.MessageBox(
                f"Could not reach kicad-mcp at {base_url}:\n{exc}",
                "kicad-mcp companion",
                wx.ICON_ERROR,
            )

    def _read_board_info(self, board_info_cls: type) -> object:
        board = pcbnew.GetBoard()
        file_name = board.GetFileName() if board else ""
        project_root = os.path.dirname(file_name) if file_name else ""
        selected_reference = ""
        selected_net = ""
        for footprint in board.GetFootprints() if board else []:
            if footprint.IsSelected():
                selected_reference = footprint.GetReference()
                break
        return board_info_cls(
            file_name=file_name,
            file_type="pcb",
            project_root=project_root,
            project_file=file_name,
            selected_reference=selected_reference,
            selected_net=selected_net,
        )

    @staticmethod
    def confirm_safe_apply(action: str) -> bool:
        """Show a confirmation dialog before a mutating action; return user choice."""
        import wx  # type: ignore[import-not-found]

        from kicad_mcp.companion.context import requires_confirmation

        if not requires_confirmation(action):
            return True
        result = wx.MessageBox(
            f"Allow kicad-mcp to apply '{action}' to the board?",
            "kicad-mcp safe apply",
            wx.YES_NO | wx.ICON_WARNING,
        )
        return result == wx.YES
