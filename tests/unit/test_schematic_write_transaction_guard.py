"""Ratchet guard against raw ``.kicad_sch`` / ``.kicad_pcb`` writes (issue #193).

Schematic/PCB files must be mutated through the guarded, atomic transaction
(``_transactional_write_to_schematic_file`` — lock, normalize, validate, atomic
``temp.replace(target)``, cache-clear). Direct ``sch_file.write_text(...)`` /
``pcb_file.write_text(...)`` calls bypass that guard and risk silent corruption.

This test inventories every direct schematic/PCB content write in ``src`` and
fails when a **new** one appears outside the documented allowlist below. It uses
subset semantics: migrating a site (removing its raw write) keeps the test green,
so it never blocks the in-flight transaction migration — it only stops the debt
from growing. As sites are migrated, prune them from ``_ALLOWLIST``.

Detection heuristic: a ``<name>.write_text(...)`` call whose receiver is one of
the schematic/PCB file handles below. The codebase uses these names by
convention for ``.kicad_sch`` / ``.kicad_pcb`` paths; ``project_file`` (the
``.kicad_pro`` JSON) is intentionally excluded.
"""

from __future__ import annotations

import ast
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "kicad_mcp"
_FILE_HANDLE_NAMES = {"sch_file", "pcb_file", "board_file"}

# Known direct schematic/PCB writes, keyed "module.py::function", each pending a
# migration to the guarded transaction (or a documented exception). Remove an
# entry once its raw write is gone.
_ALLOWLIST: dict[str, str] = {
    # Brand-new project scaffolding: the files do not exist yet, so there is no
    # prior content to transact against — initial creation, not mutation.
    "project.py::kicad_create_new_project": "writes fresh empty .kicad_pcb/.kicad_sch files",
    # PCB SES routing apply. There is no PCB-side transactional writer yet;
    # tracked for migration once #193 extends the transaction to .kicad_pcb.
    "routing.py::route_apply_ses": "applies FreeRouting .ses result to the board",
    # Full schematic overwrite. Validates before writing but skips the lock +
    # atomic replace + cache-clear; pending migration to the transaction.
    "schematic.py::sch_build_circuit": "rebuilds the whole schematic from structured inputs",
    # Regex paper-size mutation; migration to the transactional writer is in
    # flight on fix/sch-sheet-size-transactional.
    "schematic.py::sch_set_sheet_size": "rewrites the (paper ...) declaration",
}


def _collect_raw_writes() -> dict[str, int]:
    """Map "module.py::function" -> count of raw schematic/PCB content writes."""
    sites: dict[str, int] = {}
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        _RawWriteVisitor(path.name, sites).visit(tree)
    return sites


class _RawWriteVisitor(ast.NodeVisitor):
    def __init__(self, module: str, sites: dict[str, int]) -> None:
        self._module = module
        self._sites = sites
        self._func_stack: list[str] = []

    def _visit_function(self, node: ast.AST) -> None:
        self._func_stack.append(getattr(node, "name", "<lambda>"))
        self.generic_visit(node)
        self._func_stack.pop()

    visit_FunctionDef = _visit_function  # noqa: N815  (ast.NodeVisitor dispatch name)
    visit_AsyncFunctionDef = _visit_function  # noqa: N815  (ast.NodeVisitor dispatch name)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "write_text"
            and isinstance(func.value, ast.Name)
            and func.value.id in _FILE_HANDLE_NAMES
        ):
            enclosing = self._func_stack[-1] if self._func_stack else "<module>"
            key = f"{self._module}::{enclosing}"
            self._sites[key] = self._sites.get(key, 0) + 1
        self.generic_visit(node)


def test_no_new_raw_schematic_or_pcb_writes() -> None:
    found = _collect_raw_writes()
    unlisted = sorted(set(found) - set(_ALLOWLIST))
    assert not unlisted, (
        "New direct .kicad_sch/.kicad_pcb write(s) bypass the guarded transaction "
        f"(issue #193): {unlisted}. Route the mutation through "
        "_transactional_write_to_schematic_file, or, if the write is genuinely "
        "exempt, add it to _ALLOWLIST with a justification."
    )
