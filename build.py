import base64
import os


def encode_string(text: str) -> str:
    """Кодирует строку в base64."""
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def create_template(modules_encoded: dict, entry_point_encoded: str) -> str:
    modules_repr = repr(modules_encoded)

    return f"""# -*- coding: utf-8 -*-
import base64
import sys
import types

_RAW_MODULES = {modules_repr}

class _InMemoryLoader:
    def __init__(self):
        self._cache = {{}}
        for name, data in _RAW_MODULES.items():
            self._cache[name] = {{
                "code": base64.b64decode(data["code"]).decode("utf-8"),
                "is_pkg": data["is_pkg"]
            }}

    def find_spec(self, fullname, path, target=None):
        if fullname in self._cache:
            from importlib.machinery import ModuleSpec
            is_pkg = self._cache[fullname]["is_pkg"]
            spec = ModuleSpec(fullname, self, is_package=is_pkg)
            if is_pkg:
                spec.submodule_search_locations = []
            return spec
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        mod_info = self._cache[module.__name__]
        code_str = mod_info["code"]
        if mod_info["is_pkg"]:
            module.__path__ = []
        module.__file__ = f"<in-memory:{{module.__name__}}>"

        compiled_code = compile(code_str, module.__file__, "exec")
        exec(compiled_code, module.__dict__)

# Регистрируем loader
sys.meta_path.insert(0, _InMemoryLoader())

# Декодируем и исполняем точку входа
_ENTRY_CODE = base64.b64decode("{entry_point_encoded}").decode("utf-8")
exec(compile(_ENTRY_CODE, "<in-memory:tui.py>", "exec"))
"""


def collect_src_modules(src_dir, entry_script_path):
    """
    Собирает все .py файлы из src/, не затирая реальные файлы пустышками.
    """
    modules = {}
    abs_src_dir = os.path.abspath(src_dir)
    abs_entry_path = os.path.abspath(entry_script_path)

    # 1. Сначала собираем реальные файлы
    for root, dirs, files in os.walk(abs_src_dir):
        for file in files:
            if not file.endswith(".py"):
                continue

            full_path = os.path.join(root, file)
            abs_full_path = os.path.abspath(full_path)

            if abs_full_path == abs_entry_path:
                continue

            rel_path = os.path.relpath(full_path, abs_src_dir)
            module_path = os.path.splitext(rel_path)[0]
            parts = module_path.split(os.sep)

            is_pkg = False
            if parts[-1] == "__init__":
                parts.pop()
                is_pkg = True

            if not parts:
                continue

            mod_name = ".".join(parts)

            with open(full_path, "r", encoding="utf-8") as f:
                code = f.read()

            modules[mod_name] = {"code": encode_string(code), "is_pkg": is_pkg}

    # 2. Добавляем виртуальные родительские пакеты ТОЛЬКО если их нет в словаре
    parent_packages = {}
    for mod_name in list(modules.keys()):
        parts = mod_name.split(".")
        # Перебираем префиксы (родительские папки)
        for i in range(1, len(parts)):
            parent_name = ".".join(parts[:i])
            if parent_name not in modules and parent_name not in parent_packages:
                parent_packages[parent_name] = {
                    "code": encode_string(""),
                    "is_pkg": True,
                }

    modules.update(parent_packages)
    return modules


def generate_bundle(src_dir="src", entry_script="src/tui.py", output_file="bundle.py"):
    modules_encoded = collect_src_modules(src_dir, entry_script)

    with open(entry_script, "r", encoding="utf-8") as f:
        entry_code = f.read()

    entry_encoded = encode_string(entry_code)

    bundle_content = create_template(modules_encoded, entry_encoded)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(bundle_content)

    print(f"Собрано модулей и пакетов: {len(modules_encoded)}")
    print(f"Итоговый файл: {output_file}")


if __name__ == "__main__":
    generate_bundle(
        src_dir="src",
        entry_script="src/tui.py",
        output_file="bundle.py",
    )
