import importlib.util
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

def load_function_from_file(filepath):
    module_name = os.path.splitext(os.path.basename(filepath))[0]
    spec = importlib.util.spec_from_file_location(module_name, filepath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    func = getattr(module, module_name, None)
    if func is None:
        raise AttributeError(f"No function named '{module_name}' found in '{filepath}'")
    return func

def main():
    if len(sys.argv) < 2:
        print(f"Usage: python run_function.py <script.py> [arg1 arg2 ...]")
        sys.exit(1)

    filepath = sys.argv[1]
    if not os.path.isfile(filepath):
        print(f"Error: File '{filepath}' not found.")
        sys.exit(1)

    func_args = sys.argv[2:]

    func = load_function_from_file(filepath)

    try:
        result = func(*func_args)
        if result is not None:
            sys.exit(result)
    except ValueError:
        sys.exit(1)


if __name__ == '__main__':
    main()