import os, sys, ast, argparse, shutil, re, time, subprocess
from collections import defaultdict
from typing import List, Set, Dict, Any, Optional, Tuple

# --- ⚖️ THE GUARDIAN: HEALER EDITION (MASTER PROJECT ARCHITECT) ---
# Purpose: Single point of truth for Architecture, Security, and Automated Healing.

# --- CONFIGURATION ---
MAX_LINES = 300
MAX_FUNC_LINES = 50
MAX_NESTING = 5
MAX_COMPLEXITY = 10
MAX_LINE_LENGTH = 100
SECRET_PATTERNS = [
    r'sk-[a-zA-Z0-9]{20,}',  # OpenAI
    r'[0-9]{8,10}:[a-zA-Z0-9_-]{35}', # Telegram
]

GLOBAL_ALIASES = {
    "select": "sqlalchemy", "func": "sqlalchemy", "update": "sqlalchemy", "delete": "sqlalchemy",
    "Router": "aiogram", "types": "aiogram", "F": "aiogram", "Bot": "aiogram", "Dispatcher": "aiogram",
    "BaseModel": "pydantic", "Field": "pydantic", "datetime": "datetime", "timedelta": "datetime",
    "AsyncMock": "unittest.mock", "MagicMock": "unittest.mock", "patch": "unittest.mock"
}

# --- RULE SYSTEM ---
class Violation:
    def __init__(self, category: str, message: str, line: int = 0):
        self.category = category
        self.message = message
        self.line = line

class FileContext:
    def __init__(self, path: str, pkg: str, layers: List[str]):
        self.path = path
        self.pkg = pkg
        self.layers = layers
        self.rel_path = os.path.relpath(path, pkg) if pkg in path else path
        self.folder = os.path.dirname(self.rel_path).replace(os.sep, "/")
        self.content = ""
        self.tree = None
        self.violations: List[Violation] = []
        # Harvested Stats
        self.imports: Dict[str, int] = {} # name -> line
        self.names_used: Set[str] = set()
        self.max_nesting = 0
        self.total_complexity = 0
        self.functions: List[Dict] = []
        self.classes: List[Dict] = []
        self.has_global = False
        self.silent_crashes: List[int] = []
        self.async_safety_violations: List[int] = []
        self.forbidden_calls_found: List[Tuple[str, int]] = []

class MasterVisitor(ast.NodeVisitor):
    def __init__(self, context: FileContext):
        self.ctx = context
        self.current_depth = 0
        self.in_async = False

    def visit_Import(self, node):
        for alias in node.names:
            name = alias.asname or alias.name
            self.ctx.imports[name] = node.lineno
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        for alias in node.names:
            name = alias.asname or alias.name
            self.ctx.imports[name] = node.lineno
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.ctx.names_used.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name):
            self.ctx.names_used.add(node.value.id)
        self.generic_visit(node)

    def _check_func(self, node):
        complexity = 1
        for sub in ast.walk(node):
            if isinstance(sub, (ast.If, ast.For, ast.While, ast.Try, ast.IfExp, ast.BoolOp)):
                complexity += 1
        
        doc = ast.get_docstring(node)
        self.ctx.functions.append({
            "name": node.name, "line": node.lineno,
            "length": node.end_lineno - node.lineno,
            "complexity": complexity, "has_doc": doc is not None
        })
        self.ctx.total_complexity += complexity

    def visit_FunctionDef(self, node):
        self._check_func(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        old = self.in_async; self.in_async = True
        self._check_func(node)
        self.generic_visit(node)
        self.in_async = old

    def visit_ClassDef(self, node):
        doc = ast.get_docstring(node)
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name): bases.append(base.id)
            elif isinstance(base, ast.Attribute): bases.append(base.attr)
        self.ctx.classes.append({
            "name": node.name, "line": node.lineno,
            "has_doc": doc is not None, "bases": bases
        })
        self.generic_visit(node)

    def visit_Global(self, node):
        self.ctx.has_global = True; self.generic_visit(node)

    def visit_Call(self, node):
        if self.in_async:
            if isinstance(node.func, ast.Attribute):
                if node.func.attr == 'sleep' and isinstance(node.func.value, ast.Name) and node.func.value.id == 'time':
                    self.ctx.async_safety_violations.append(node.lineno)
        
        call_name = ""
        if isinstance(node.func, ast.Name): call_name = node.func.id
        elif isinstance(node.func, ast.Attribute): call_name = node.func.attr
        if call_name: self.ctx.forbidden_calls_found.append((call_name, node.lineno))
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            self.ctx.silent_crashes.append(node.lineno)
        self.generic_visit(node)

    def generic_visit(self, node):
        cf = (ast.If, ast.For, ast.While, ast.Try, ast.With, ast.IfExp)
        if isinstance(node, cf):
            self.current_depth += 1
            self.ctx.max_nesting = max(self.ctx.max_nesting, self.current_depth)
        super().generic_visit(node)
        if isinstance(node, cf): self.current_depth -= 1

# --- 🏥 THE SURGEON (AUTO-HEALER) ---
class Surgeon:
    def __init__(self, target_dir, pkg, layers):
        self.target_dir = target_dir; self.pkg = pkg; self.layers = layers
        self.knowledge_graph: Dict[str, str] = {}
        self._build_knowledge_graph()

    def _build_knowledge_graph(self):
        self.knowledge_graph.update(GLOBAL_ALIASES)
        pkg_path = os.path.join(self.target_dir, self.pkg)
        if not os.path.exists(pkg_path): pkg_path = self.target_dir
        for root, _, files in os.walk(pkg_path):
            if any(x in root for x in [".git", "venv", "__pycache__"]): continue
            for file in files:
                if file.endswith(".py") and file != "guardian.py":
                    path = os.path.join(root, file)
                    rel = os.path.relpath(path, self.target_dir)
                    mod = os.path.splitext(rel)[0].replace(os.sep, ".")
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            tree = ast.parse(f.read())
                            for node in tree.body:
                                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                                    if not node.name.startswith("_"): self.knowledge_graph[node.name] = mod
                                elif isinstance(node, ast.Assign):
                                    for target in node.targets:
                                        if isinstance(target, ast.Name) and not target.id.startswith("_"): self.knowledge_graph[target.id] = mod
                    except: pass

    def _format_import(self, module, names):
        names = sorted(list(set(names)))
        base = f"from {module} import {', '.join(names)}"
        if len(base) < MAX_LINE_LENGTH: return base + "\n"
        joined = ",\n    ".join(names)
        return f"from {module} import (\n    {joined}\n)\n"

    def heal_file(self, file_path, missing_names):
        """Heals multiple names at once to prevent messy multi-pass formatting issues."""
        bak_path = file_path + ".bak"
        if not os.path.exists(bak_path): shutil.copy2(file_path, bak_path)
        
        with open(file_path, "r", encoding="utf-8") as f: content = f.read()

        # Group missing names by their required module
        module_map = defaultdict(set)
        for name in missing_names:
            if name in self.knowledge_graph: module_map[self.knowledge_graph[name]].add(name)

        for module, names in module_map.items():
            pattern = rf"^from {re.escape(module)} import\s+[\s\S]+?(?=\n[^\s]|$)"
            match = re.search(pattern, content, re.M)
            if match:
                existing_text = match.group(0)
                names_part = existing_text.split("import", 1)[1]
                all_names = {v.strip() for v in names_part.replace("\n", "").replace("(", "").replace(")", "").split(",") if v.strip()}
                all_names.update(names)
                new_import = self._format_import(module, all_names)
                content = content[:match.start()] + new_import.strip() + content[match.end():]
            else:
                new_import = self._format_import(module, names)
                doc_match = re.search(r'^\s*"""[\s\S]*?"""', content)
                if doc_match: content = content[:doc_match.end()] + "\n" + new_import + content[doc_match.end():]
                else: content = new_import + content

        with open(file_path, "w", encoding="utf-8") as f: f.write(content)
        return list(module_map.keys())

# --- THE GUARDIAN (MAIN ENGINE) ---
FOLDER_RULES = {
    "bot/handlers": {"forbid_classes": ["StatesGroup"], "forbid_calls": ["InlineKeyboardMarkup"], "cat": "UI Structure"},
    "data": {"forbid_imports": ["aiogram", "bot", "providers"], "cat": "Architecture"},
    "services": {"forbid_imports": ["aiogram", "bot"], "cat": "Architecture"},
    "providers": {"require_async_safety": True, "cat": "API Safety"}
}

class Guardian:
    def __init__(self, base_dir=".", pkg="app"):
        self.base_dir = base_dir; self.pkg = pkg; self.pkg_path = os.path.join(base_dir, pkg)
        self.layers = self._detect_layers(); self.all_violations: List[Violation] = []
        self.files_scanned = 0; self.total_complexity = 0
        self.import_graph = defaultdict(set); self.stats = defaultdict(int)
        self.surgeon = Surgeon(base_dir, pkg, self.layers)

    def _detect_layers(self):
        if not os.path.exists(self.pkg_path): return []
        return [d for d in os.listdir(self.pkg_path) if os.path.isdir(os.path.join(self.pkg_path, d)) and not d.startswith("__")]

    def _apply_rules(self, ctx: FileContext):
        if len(ctx.content.splitlines()) > MAX_LINES: ctx.violations.append(Violation("Quality", f"File too long ({len(ctx.content.splitlines())}/{MAX_LINES})"))
        if ctx.max_nesting > MAX_NESTING: ctx.violations.append(Violation("Quality", f"Deep nesting ({ctx.max_nesting}/{MAX_NESTING})"))
        for func in ctx.functions:
            if func["length"] > MAX_FUNC_LINES: ctx.violations.append(Violation("Quality", f"Monster Function '{func['name']}' ({func['length']} lines)", func['line']))
            if func["complexity"] > MAX_COMPLEXITY: ctx.violations.append(Violation("Quality", f"High Complexity '{func['name']}' (Score {func['complexity']})", func['line']))
            if not func["has_doc"]: ctx.violations.append(Violation("Constitution", f"Missing Docstring in '{func['name']}'", func['line']))
        for cls in ctx.classes:
            if not cls["has_doc"]: ctx.violations.append(Violation("Constitution", f"Missing Docstring in class '{cls['name']}'", cls['line']))
        if ctx.has_global: ctx.violations.append(Violation("Constitution", "Global State Detected"))
        for line in ctx.silent_crashes: ctx.violations.append(Violation("Constitution", "Silent Crash (except: pass)", line))
        rule_set = None; cat = "Architecture"
        for pat, rules in FOLDER_RULES.items():
            if ctx.folder.startswith(pat): rule_set = rules; cat = rules.get("cat", "Architecture"); break
        if rule_set:
            for forbid in rule_set.get("forbid_imports", []):
                for imp in ctx.imports:
                    if imp == forbid or imp.startswith(forbid + "."): ctx.violations.append(Violation(cat, f"Illegal mixing: '{imp}' not allowed here"))
            for forbid in rule_set.get("forbid_classes", []):
                for cls in ctx.classes:
                    if any(base == forbid for base in cls["bases"]): ctx.violations.append(Violation(cat, f"Illegal class: '{cls['name']}' inherits {forbid}", cls['line']))
            if rule_set.get("require_async_safety") and ctx.async_safety_violations:
                for line in ctx.async_safety_violations: ctx.violations.append(Violation("API Safety", "time.sleep() in async code", line))
        for pattern in SECRET_PATTERNS:
            if re.search(pattern, ctx.content): ctx.violations.append(Violation("Security", "Potential Hardcoded Secret"))

    def _check_cycles(self, ctx: FileContext):
        rel = os.path.splitext(ctx.rel_path)[0]; mod = f"{self.pkg}.{rel.replace(os.sep, '.')}"
        for imp in ctx.imports:
            full = imp
            if not imp.startswith(self.pkg + "."):
                first = imp.split('.')[0]
                if first in self.layers: full = f"{self.pkg}.{imp}"
            if full.startswith(self.pkg + "."): self.import_graph[mod].add(full)

    def scan(self, fix=False):
        print(f"\n--- THE GUARDIAN (Master Scan: {self.pkg}) ---")
        if fix:
            print("Initiating Auto-Healer Pass...")
            for _ in range(3):
                try:
                    cmd = [sys.executable, "-m", "pyflakes", self.pkg_path]
                    res = subprocess.run(cmd, capture_output=True, text=True)
                    errs = re.findall(r"(.*?):\d+:(\d+:)? undefined name '(.*?)'", res.stdout, re.M)
                    if not errs: break
                    file_map = defaultdict(set)
                    for f, _, n in errs: file_map[os.path.normpath(f)].add(n)
                    for file, names in file_map.items():
                        modules = self.surgeon.heal_file(file, names)
                        if modules: print(f"  [+] Healed {len(names)} names in {os.path.basename(file)} (linked to {', '.join(modules)})")
                except: break
        for root, dirs, files in os.walk(self.pkg_path):
            dirs[:] = [d for d in dirs if d not in [".git", "venv", "__pycache__", "env", ".env"]]
            for file in files:
                if file.endswith(".py") and file != "__init__.py" and file != "guardian.py":
                    path = os.path.join(root, file); self.files_scanned += 1
                    with open(path, "r", encoding="utf-8") as f: content = f.read()
                    ctx = FileContext(path, self.pkg, self.layers); ctx.content = content
                    try:
                        ctx.tree = ast.parse(content)
                        visitor = MasterVisitor(ctx); visitor.visit(ctx.tree); self._apply_rules(ctx); self._check_cycles(ctx)
                        if ctx.violations:
                            print(f"File: {ctx.rel_path}")
                            for v in ctx.violations: print(f"  [{v.category}] {v.message} {'(L'+str(v.line)+')' if v.line else ''}"); self.stats[v.category] += 1; self.all_violations.append(v)
                    except Exception as e: print(f"File: {ctx.rel_path} -> Error: {e}")
        cycle = self._detect_cycle()
        if cycle: print(f"GLOBAL: Circular Dependency: {' -> '.join(cycle)}"); self.stats["Architecture"] += 1
        self._print_summary()

    def _detect_cycle(self):
        def has_cycle(v, visited, stack, path):
            visited.add(v); stack.add(v); path.append(v)
            for n in self.import_graph[v]:
                if n not in visited:
                    if has_cycle(n, visited, stack, path): return True
                elif n in stack: path.append(n); return True
            stack.remove(v); path.pop(); return False
        visited, stack = set(), set()
        for node in list(self.import_graph.keys()):
            if node not in visited:
                path = []
                if has_cycle(node, visited, stack, path): return path
        return None

    def _print_summary(self):
        print("\n" + "="*50)
        grade = "A+"
        if self.all_violations:
            total = len(self.all_violations)
            if total > 15 or self.stats["Security"] > 0: grade = "F"
            elif total > 10: grade = "C"
            else: grade = "B"
        print(f"SUMMARY: {len(self.all_violations)} Violations found in {self.files_scanned} files.")
        for cat, cnt in sorted(self.stats.items()): print(f"  - {cat}: {cnt}")
        print(f"RESULT: {'PASSED' if not self.all_violations else 'FAILED'} | GRADE: {grade}")
        print("="*50)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pkg", default="app"); parser.add_argument("--fix", action="store_true")
    args = parser.parse_args()
    Guardian(pkg=args.pkg).scan(fix=args.fix)
