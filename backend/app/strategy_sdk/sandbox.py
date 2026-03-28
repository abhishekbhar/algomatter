import importlib

ALLOWED_MODULES = {
    "math", "statistics", "datetime", "collections", "itertools",
    "functools", "decimal", "json", "dataclasses", "typing",
    "enum", "abc", "copy", "operator", "bisect", "heapq", "random",
    # Third-party (pre-installed)
    "numpy", "pandas", "ta", "pandas_ta",
}

BLOCKED_MODULES = {
    "os", "sys", "subprocess", "socket", "http", "urllib", "requests",
    "ctypes", "importlib", "pickle", "shelve", "multiprocessing",
    "threading", "signal", "shutil", "pathlib", "io", "builtins",
}


class SafeImporter:
    def __call__(self, name: str, *args, **kwargs):
        top_level = name.split(".")[0]
        if top_level in BLOCKED_MODULES:
            raise ImportError(f"Module '{name}' is not allowed in strategy code")
        if top_level in ALLOWED_MODULES or top_level.startswith("app.strategy_sdk"):
            return importlib.import_module(name)
        raise ImportError(f"Module '{name}' is not allowed in strategy code")
