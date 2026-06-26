"""Tests for backend/core/issue_capabilities.py

Validates:
1. Known codes are fully covered by capabilities
2. Capability kinds match actual solver dispatch in IssueRepairService
3. Unknown codes return unsupported
4. Module can be imported independently without triggering solver/Finding/service imports
5. Source module contains no forbidden imports
"""

import ast

import pytest

from backend.core.issue_capabilities import (
    IssueCapabilityKind,
    IssueCapabilityDefinition,
    KNOWN_ISSUE_CODES,
    ISSUE_CAPABILITIES,
    get_issue_capability,
    codes_with_capability,
)


class TestIssueCapabilities:
    """Capability registry correctness tests."""

    def test_known_codes_fully_covered(self):
        """Every known issue code must have a capability definition."""
        missing = KNOWN_ISSUE_CODES - ISSUE_CAPABILITIES.keys()
        assert not missing, f"Issue codes missing capability: {missing}"

    def test_no_extra_capabilities(self):
        """Capability definitions must correspond to known codes (no orphans)."""
        extra = ISSUE_CAPABILITIES.keys() - KNOWN_ISSUE_CODES
        assert not extra, f"Capabilities without known codes: {extra}"

    def test_all_capabilities_have_valid_kind(self):
        """Every capability must have a valid IssueCapabilityKind."""
        valid_kinds = set(IssueCapabilityKind)
        for code, cap in ISSUE_CAPABILITIES.items():
            assert cap.kind in valid_kinds, (
                f"{code} has invalid kind: {cap.kind}"
            )

    def test_all_capabilities_have_action_label(self):
        """Every capability must have a non-empty action_label."""
        for code, cap in ISSUE_CAPABILITIES.items():
            assert cap.action_label and cap.action_label.strip(), (
                f"{code} has empty action_label"
            )

    def test_unknown_code_returns_unsupported(self):
        """Unknown issue codes must return unsupported with disabled=False."""
        cap = get_issue_capability("UNKNOWN_CODE_XYZ")
        assert cap.kind == IssueCapabilityKind.UNSUPPORTED
        assert cap.enabled is False

    def test_known_code_returns_expected(self):
        """Known issue codes must return their defined capability."""
        cap = get_issue_capability("SCOPE_WITHOUT_REASON")
        assert cap.kind == IssueCapabilityKind.AI_REPAIR
        assert cap.action_label == "AI 修复"
        assert cap.enabled is True

    def test_codes_with_capability_smoke(self):
        """codes_with_capability must return the correct subsets."""
        ai_codes = codes_with_capability(IssueCapabilityKind.AI_REPAIR)
        gen_codes = codes_with_capability(IssueCapabilityKind.GENERATION_DRAFT)
        panel_codes = codes_with_capability(IssueCapabilityKind.OPEN_PANEL)

        assert "SCOPE_WITHOUT_REASON" in ai_codes
        assert "LEAF_FEATURE_WITHOUT_ACTOR" in ai_codes
        assert "SCENARIO_WITHOUT_ACCEPTANCE_CRITERIA" in gen_codes
        assert "LEAF_FEATURE_WITHOUT_SCOPE" in gen_codes
        assert "ACTOR_ACTION_STEP_WITHOUT_ACTOR" in panel_codes
        assert "JUDGMENT_STEP_WITH_TOO_FEW_BRANCHES" in panel_codes

        # All codes accounted for across the three actionable kinds
        all_actionable = ai_codes | gen_codes | panel_codes
        assert all_actionable == KNOWN_ISSUE_CODES, (
            f"Codes not in any actionable category: {KNOWN_ISSUE_CODES - all_actionable}"
        )

    def test_generation_draft_codes_match_registry(self):
        """GenerationDraftIssueSolver._draft_map codes must be GENERATION_DRAFT."""
        gen_draft_codes_in_registry = {
            "FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO",
            "SCENARIO_WITHOUT_ACCEPTANCE_CRITERIA",
            "LEAF_FEATURE_WITHOUT_SCOPE",
        }
        for code in gen_draft_codes_in_registry:
            cap = get_issue_capability(code)
            # FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO is ai_repair because
            # it has an AI solver (ScenarioCoverageSolver) that takes precedence.
            if code == "FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO":
                assert cap.kind == IssueCapabilityKind.AI_REPAIR, (
                    f"{code} should be ai_repair (AI solver takes precedence)"
                )
            else:
                assert cap.kind == IssueCapabilityKind.GENERATION_DRAFT, (
                    f"{code} should be generation_draft, got {cap.kind}"
                )

    def test_open_panel_codes_correct(self):
        """Codes that only have OpenPanelIssueSolver must be OPEN_PANEL."""
        panel_codes = {
            "ACTOR_ACTION_STEP_WITHOUT_ACTOR",
            "JUDGMENT_STEP_WITH_TOO_FEW_BRANCHES",
            "UNREACHABLE_FLOW_STEP",
        }
        for code in panel_codes:
            cap = get_issue_capability(code)
            assert cap.kind == IssueCapabilityKind.OPEN_PANEL, (
                f"{code} should be open_panel, got {cap.kind}"
            )


class TestIssueCapabilitiesImportIsolation:
    """Verify the module can be imported in isolation without side effects."""

    def test_module_imports_only_stdlib(self):
        """The module must only import from Python standard library."""
        with open("backend/core/issue_capabilities.py", "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())

        forbidden_keywords = [
            "findings", "issue_resolution", "api.", "database",
            "solver", "LLM", "services.",
        ]

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for kw in forbidden_keywords:
                        assert kw not in alias.name, (
                            f"Forbidden import '{alias.name}' in issue_capabilities.py"
                        )
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for kw in forbidden_keywords:
                    assert kw not in mod, (
                        f"Forbidden import 'from {mod}' in issue_capabilities.py"
                    )

    def test_import_does_not_trigger_solver_import(self):
        """Importing issue_capabilities must NOT import solvers, findings, or services."""
        import sys

        # Built-in modules are always loaded; track before/after
        before = set(sys.modules.keys())
        from backend.core.issue_capabilities import (  # noqa: F811
            IssueCapabilityKind,
        )
        after = set(sys.modules.keys())
        new = after - before

        forbidden_prefixes = [
            "backend.core.detectors.issue_solvers",
            "backend.core.findings",
            "backend.core.issue_resolution",
            "backend.api",
            "backend.database",
            "backend.services.LLM",
        ]
        for mod in new:
            for prefix in forbidden_prefixes:
                assert not mod.startswith(prefix), (
                    f"Importing issue_capabilities triggered: {mod}"
                )


class TestIssueCapabilitiesConsistencyWithIssueRepairService:
    """Verify capability registry aligns with IssueRepairService dispatch.

    These tests dynamically read from the actual _AI_SOLVERS dispatch table,
    so adding a new AI solver automatically requires updating the capability.
    """

    def test_ai_repair_codes_have_ai_solver(self):
        """Every code with an AI solver must be ai_repair in capability registry.
        Every ai_repair code must have an AI solver registered.
        """
        from backend.api.modules.diagnosis_quality.issue_repair.application.issue_repair_service import get_ai_solver_codes

        ai_solver_codes = get_ai_solver_codes()
        ai_cap_codes = codes_with_capability(IssueCapabilityKind.AI_REPAIR)

        missing_solver = ai_cap_codes - ai_solver_codes
        missing_capability = ai_solver_codes - ai_cap_codes

        assert not missing_solver, (
            f"Codes declared as ai_repair but missing AI solver: {missing_solver}"
        )
        assert not missing_capability, (
            f"Codes with AI solver but not declared as ai_repair: {missing_capability}"
        )

    def test_ai_solver_codes_subset_of_known(self):
        """All AI solver codes must be in KNOWN_ISSUE_CODES."""
        from backend.api.modules.diagnosis_quality.issue_repair.application.issue_repair_service import get_ai_solver_codes

        ai_solver_codes = get_ai_solver_codes()
        unknown = ai_solver_codes - KNOWN_ISSUE_CODES
        assert not unknown, (
            f"AI solver codes not in KNOWN_ISSUE_CODES: {unknown}"
        )

    def test_known_codes_consistency(self):
        """KNOWN_ISSUE_CODES is shared via import; verify the import chain works."""
        from backend.core.issue_resolution.registry import (
            KNOWN_ISSUE_CODES as REGISTRY_KNOWN_CODES,
        )
        assert REGISTRY_KNOWN_CODES is KNOWN_ISSUE_CODES, (
            "KNOWN_ISSUE_CODES must be the same object (imported, not duplicated)"
        )


class TestModuleStructureMigration:
    """Phase 5 structural anti-regression tests.

    Ensure the old detectors/issue_solvers package is fully removed.
    """

    _OLD_PACKAGE = "backend.core.detectors.issue_solvers"
    _ALLOWED_OLD_FILES = {"__pycache__"}

    def test_old_dir_contains_no_python_sources(self):
        """Old directory may only contain an untracked bytecode cache."""
        import os

        old_dir = os.path.join(
            "backend", "core", "detectors", "issue_solvers"
        )
        if not os.path.isdir(old_dir):
            return  # directory already removed — cleanest state

        actual = {f for f in os.listdir(old_dir)
                  if f not in self._ALLOWED_OLD_FILES}
        assert not actual, (
            f"Old directory still contains source files: {actual}"
        )

    def test_old_import_is_unavailable(self):
        """Old package must not remain as a compatibility import."""
        import importlib
        import pytest

        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(self._OLD_PACKAGE)

    def test_detectors_does_not_import_issue_resolution(self):
        """detectors/__init__.py must not import from issue_resolution."""
        import ast

        with open("backend/core/detectors/__init__.py", "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if "issue_resolution" in mod:
                    assert False, (
                        f"detectors/__init__.py must not import issue_resolution, "
                        f"found: from {mod}"
                    )

    def test_suggestions_does_not_import_issue_resolution(self):
        """suggestions/ must not import from issue_resolution."""
        import ast, glob

        for fpath in glob.glob("backend/core/suggestions/*.py"):
            with open(fpath, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    if "issue_resolution" in mod:
                        assert False, (
                            f"{fpath} must not import issue_resolution, "
                            f"found: from {mod}"
                        )

    def test_arbitrary_import_order_no_error(self):
        """findings, capabilities, issue_resolution can be imported in any order."""
        import sys

        # Track modules loaded by order-specific imports
        modules_to_test = [
            "backend.core.issue_capabilities",
            "backend.core.issue_resolution.registry",
            "backend.core.findings.what_finding_policy",
        ]

        for mod_name in modules_to_test:
            if mod_name in sys.modules:
                del sys.modules[mod_name]

        # Order 1: capabilities → findings → issue_resolution
        import backend.core.issue_capabilities  # noqa: F811
        import backend.core.findings.what_finding_policy  # noqa: F811
        import backend.core.issue_resolution.registry  # noqa: F811

        # Clean
        for mod_name in modules_to_test:
            if mod_name in sys.modules:
                del sys.modules[mod_name]

        # Order 2: issue_resolution → capabilities → findings
        import backend.core.issue_resolution.registry  # noqa: F811
        import backend.core.issue_capabilities  # noqa: F811
        import backend.core.findings.what_finding_policy  # noqa: F811
