import ast
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]

ALLOWED_SHIMS = set()

# Registered core -> api imports (from dependency_exceptions.md)
ALLOWED_CORE_TO_API_EXCEPTIONS = set()

class ImportVisitor(ast.NodeVisitor):
    def __init__(self, file_path: Path):
        self.file_path = file_path
        # Compute relative path in POSIX style (e.g. backend/core/foo.py)
        try:
            self.rel_path = file_path.relative_to(BACKEND_DIR.parent).as_posix()
        except ValueError:
            self.rel_path = file_path.as_posix()
        self.violations = []

    def visit_Import(self, node):
        for alias in node.names:
            self._check_import(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            self._check_import(node.module)
        self.generic_visit(node)

    def _check_import(self, module_name: str):
        # 0. Test files are exempt from encapsulation rules
        if self.rel_path.startswith("backend/tests/"):
            return

        # 1. Rule: Core -> API dependency restriction
        if self.rel_path.startswith("backend/core/"):
            if module_name.startswith("backend.api") or module_name == "backend.api":
                if self.rel_path not in ALLOWED_CORE_TO_API_EXCEPTIONS:
                    self.violations.append(
                        f"Core violation: {self.rel_path} imports {module_name}. "
                        "Domain core must not depend on API layers."
                    )

        # 2. Rule: auth_account internal encapsulation restriction
        is_in_auth_account = self.rel_path.startswith("backend/api/modules/auth_account/")
        is_allowed_shim = self.rel_path in ALLOWED_SHIMS
        is_composition_root = self.rel_path == "backend/main.py"
        
        if not is_in_auth_account and not is_allowed_shim and not is_composition_root:
            # Match imports like backend.api.modules.auth_account.application.*
            prefix = "backend.api.modules.auth_account"
            if module_name.startswith(prefix):
                # The only allowed external import suffix is .public or the package root itself
                sub_path = module_name[len(prefix):].lstrip(".")
                if sub_path and not sub_path.startswith("public"):
                    self.violations.append(
                        f"Encapsulation violation: {self.rel_path} imports internal {module_name}. "
                        "Must import from backend.api.modules.auth_account.public instead."
                    )

        # 3. Rule: project_lifecycle internal encapsulation restriction
        is_in_project_lifecycle = self.rel_path.startswith("backend/api/modules/project_lifecycle/")
        
        if not is_in_project_lifecycle and not is_allowed_shim and not is_composition_root:
            # Match imports like backend.api.modules.project_lifecycle.application.*
            prefix = "backend.api.modules.project_lifecycle"
            if module_name.startswith(prefix):
                # The only allowed external import suffix is .public or .ports or the package root itself
                sub_path = module_name[len(prefix):].lstrip(".")
                if sub_path and not (sub_path.startswith("public") or sub_path.startswith("ports")):
                    self.violations.append(
                        f"Encapsulation violation: {self.rel_path} imports internal {module_name}. "
                        "Must import from backend.api.modules.project_lifecycle.public or ports instead."
                    )

        # 4. Rule: requirements_core internal encapsulation restriction
        is_in_requirements_core = self.rel_path.startswith("backend/api/modules/requirements_core/")
        
        if not is_in_requirements_core and not is_allowed_shim and not is_composition_root:
            # Match imports like backend.api.modules.requirements_core.*
            prefix = "backend.api.modules.requirements_core"
            if module_name.startswith(prefix):
                # The only allowed external import suffix is .public or .ports or the package root itself
                sub_path = module_name[len(prefix):].lstrip(".")
                if sub_path and not (sub_path.startswith("public") or sub_path.startswith("ports")):
                    self.violations.append(
                        f"Encapsulation violation: {self.rel_path} imports internal {module_name}. "
                        "Must import from backend.api.modules.requirements_core.public or ports instead."
                    )

        # 5. Rule: decision_workflow internal encapsulation restriction
        is_in_decision_workflow = self.rel_path.startswith("backend/api/modules/decision_workflow/")
        
        if not is_in_decision_workflow and not is_allowed_shim and not is_composition_root:
            # Match imports like backend.api.modules.decision_workflow.*
            prefix = "backend.api.modules.decision_workflow"
            if module_name.startswith(prefix):
                # The only allowed external import suffix is .public or .ports or the package root itself
                sub_path = module_name[len(prefix):].lstrip(".")
                if sub_path and not (sub_path.startswith("public") or sub_path.startswith("ports")):
                    self.violations.append(
                        f"Encapsulation violation: {self.rel_path} imports internal {module_name}. "
                        "Must import from backend.api.modules.decision_workflow.public or ports instead."
                    )

        # 6. Rule: ai_interaction internal encapsulation restriction
        is_in_ai_interaction = self.rel_path.startswith("backend/api/modules/ai_interaction/")
        
        if not is_in_ai_interaction and not is_allowed_shim and not is_composition_root:
            # Match imports like backend.api.modules.ai_interaction.*
            prefix = "backend.api.modules.ai_interaction"
            if module_name.startswith(prefix):
                # The only allowed external import suffix is .public or the package root itself
                sub_path = module_name[len(prefix):].lstrip(".")
                if sub_path and not sub_path.startswith("public"):
                    self.violations.append(
                        f"Encapsulation violation: {self.rel_path} imports internal {module_name}. "
                        "Must import from backend.api.modules.ai_interaction.public instead."
                    )

        # 7. Rule: diagnosis_quality internal encapsulation restriction
        is_in_diagnosis_quality = self.rel_path.startswith("backend/api/modules/diagnosis_quality/")
        
        if not is_in_diagnosis_quality and not is_allowed_shim and not is_composition_root:
            # Match imports like backend.api.modules.diagnosis_quality.*
            prefix = "backend.api.modules.diagnosis_quality"
            if module_name.startswith(prefix):
                # The only allowed external import suffix is .public or .ports or the package root itself
                sub_path = module_name[len(prefix):].lstrip(".")
                if sub_path and not (sub_path.startswith("public") or sub_path.startswith("ports")):
                    self.violations.append(
                        f"Encapsulation violation: {self.rel_path} imports internal {module_name}. "
                        "Must import from backend.api.modules.diagnosis_quality.public or ports instead."
                    )

        # 8. Rule: preview_convergence internal encapsulation restriction
        is_in_preview_convergence = self.rel_path.startswith("backend/api/modules/preview_convergence/")
        
        if not is_in_preview_convergence and not is_allowed_shim and not is_composition_root:
            # Match imports like backend.api.modules.preview_convergence.*
            prefix = "backend.api.modules.preview_convergence"
            if module_name.startswith(prefix):
                # The only allowed external import suffix is .public or .ports or the package root itself
                sub_path = module_name[len(prefix):].lstrip(".")
                if sub_path and not (sub_path.startswith("public") or sub_path.startswith("ports")):
                    self.violations.append(
                        f"Encapsulation violation: {self.rel_path} imports internal {module_name}. "
                        "Must import from backend.api.modules.preview_convergence.public or ports instead."
                    )

def test_architecture_dependency_rules():
    """Scan backend python files to verify module import dependency rules."""
    all_violations = []
    
    for root, _, files in os.walk(BACKEND_DIR):
        for file in files:
            if file.endswith(".py"):
                file_path = Path(root) / file
                
                with open(file_path, "r", encoding="utf-8") as f:
                    try:
                        tree = ast.parse(f.read(), filename=str(file_path))
                    except SyntaxError:
                        continue  # Skip unparsable python files if any
                
                visitor = ImportVisitor(file_path)
                visitor.visit(tree)
                all_violations.extend(visitor.violations)
                
    assert not all_violations, (
        "Architectural dependency violations detected:\n" + 
        "\n".join(all_violations)
    )


def test_no_legacy_imports_in_production_code():
    """Verify that no production code outside of compatibility shims imports legacy api routes, schemas, or services."""
    legacy_prefixes = ["backend.api.routes", "backend.api.schemas", "backend.api.services"]
    excluded_paths = []
    
    violations = []
    
    for root, _, files in os.walk(BACKEND_DIR):
        for file in files:
            if file.endswith(".py"):
                file_path = Path(root) / file
                try:
                    rel_path = file_path.relative_to(BACKEND_DIR.parent).as_posix()
                except ValueError:
                    rel_path = file_path.as_posix()
                    
                if any(rel_path.startswith(ex) for ex in excluded_paths):
                    continue
                    
                with open(file_path, "r", encoding="utf-8") as f:
                    try:
                        tree = ast.parse(f.read(), filename=str(file_path))
                    except SyntaxError:
                        continue
                        
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            for prefix in legacy_prefixes:
                                if alias.name == prefix or alias.name.startswith(prefix + "."):
                                    violations.append(f"{rel_path}:{node.lineno} imports legacy module {alias.name}")
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            for prefix in legacy_prefixes:
                                if node.module == prefix or node.module.startswith(prefix + "."):
                                    violations.append(f"{rel_path}:{node.lineno} imports legacy module {node.module}")
                    elif isinstance(node, ast.Call):
                        is_import_module = False
                        if isinstance(node.func, ast.Attribute):
                            if isinstance(node.func.value, ast.Name) and node.func.value.id == "importlib" and node.func.attr == "import_module":
                                is_import_module = True
                        elif isinstance(node.func, ast.Name) and node.func.id == "import_module":
                            is_import_module = True
                            
                        if is_import_module and node.args:
                            first_arg = node.args[0]
                            val = None
                            if isinstance(first_arg, ast.Constant):
                                val = first_arg.value
                            elif isinstance(first_arg, ast.Str):
                                val = first_arg.s
                                
                            if isinstance(val, str):
                                for prefix in legacy_prefixes:
                                    if val == prefix or val.startswith(prefix + "."):
                                        violations.append(f"{rel_path}:{node.lineno} dynamically imports legacy module '{val}' via import_module")
                                    
    assert not violations, f"Forbidden legacy imports found in production code:\n" + "\n".join(violations)


def test_no_circular_dependencies():
    """Verify that there are no circular dependencies among the top-level modules under backend/api/modules/."""
    modules_dir = BACKEND_DIR / "api" / "modules"
    modules = [d.name for d in modules_dir.iterdir() if d.is_dir() and d.name != "__pycache__"]
    
    # Build adjacency list: module -> set of imported modules
    dependencies = {m: set() for m in modules}
    
    for module in modules:
        module_path = modules_dir / module
        for root, _, files in os.walk(module_path):
            for file in files:
                if file.endswith(".py"):
                    file_path = Path(root) / file
                    with open(file_path, "r", encoding="utf-8") as f:
                        try:
                            tree = ast.parse(f.read(), filename=str(file_path))
                        except SyntaxError:
                            continue
                    
                    for node in ast.walk(tree):
                        imported_modules = []
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                imported_modules.append(alias.name)
                        elif isinstance(node, ast.ImportFrom) and node.module:
                            imported_modules.append(node.module)
                        
                        for imp in imported_modules:
                            # Match backend.api.modules.<module_name>
                            prefix = "backend.api.modules."
                            if imp.startswith(prefix):
                                parts = imp[len(prefix):].split(".")
                                if parts:
                                    target_module = parts[0]
                                    if target_module in modules and target_module != module:
                                        dependencies[module].add(target_module)
                                        
    # Check for cycles using DFS
    visited = {}  # name -> 0 (unvisited), 1 (visiting), 2 (visited)
    for m in modules:
        visited[m] = 0
        
    cycles = []
    
    def dfs(node, path):
        visited[node] = 1  # visiting
        for neighbor in dependencies[node]:
            if visited[neighbor] == 1:
                # Cycle detected
                cycle_path = path + [neighbor]
                cycle_start_idx = cycle_path.index(neighbor)
                cycles.append(" -> ".join(cycle_path[cycle_start_idx:]))
            elif visited[neighbor] == 0:
                dfs(neighbor, path + [neighbor])
        visited[node] = 2  # visited
        
    for m in modules:
        if visited[m] == 0:
            dfs(m, [m])
            
    assert not cycles, f"Circular module dependencies detected:\n" + "\n".join(cycles)


def test_legacy_directories_do_not_exist():
    """Ensure that the legacy directories (routes, schemas, services) have been fully deleted."""
    legacy_dirs = [
        BACKEND_DIR / "api" / "routes",
        BACKEND_DIR / "api" / "schemas",
        BACKEND_DIR / "api" / "services",
    ]
    for d in legacy_dirs:
        assert not d.exists(), f"Legacy directory still exists: {d}"


