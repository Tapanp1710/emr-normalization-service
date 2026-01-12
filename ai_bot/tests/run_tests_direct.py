import sys
import importlib.util
from pathlib import Path
sys.path.insert(0, "config")

# Discover and run all test_*.py files in this directory
failed = False
for test_file in Path(__file__).parent.glob("test_*.py"):
    spec = importlib.util.spec_from_file_location(test_file.stem, str(test_file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    for name in dir(mod):
        if not name.startswith("test_"):
            continue
        fn = getattr(mod, name)
        if callable(fn):
            try:
                fn()
                print(f"{test_file.name}::{name}: PASSED")
            except AssertionError as e:
                print(f"{test_file.name}::{name}: FAILED")
                failed = True
                raise
            except Exception as ex:
                print(f"{test_file.name}::{name}: ERROR", ex)
                failed = True
                raise
if not failed:
    print("ALL TESTS PASSED")

