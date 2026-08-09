#!/usr/bin/env python3
"""
PumaLang single-file shell (onefile/pumalang.py)

Usage:
    python onefile/shell.py                      # interactive REPL
    python onefile/shell.py script.pumalang      # run a script
"""

import argparse
import sys
from pathlib import Path

ONEFILE_DIR = Path(__file__).resolve().parent
if str(ONEFILE_DIR) not in sys.path:
    sys.path.insert(0, str(ONEFILE_DIR))

import pumalang


class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"


BANNER = r"""

"""

VERSION = "0.1.0 (onefile)"
EXIT_COMMANDS = {"exit", "quit", "bye"}


def format_value(value):
    if value is None:
        return None
    if hasattr(value, "elements"):
        if len(value.elements) == 1:
            return repr(value.elements[0])
        return repr(value.elements)
    return repr(value)


def print_banner():
    print(f"{Colors.CYAN}{Colors.BOLD}{BANNER}{Colors.RESET}")
    print(f"{Colors.GREEN}PumaLang Shell v{VERSION}{Colors.RESET}")
    print("Type exit, quit, bye, or press Ctrl+C to leave")
    print("=" * 60)


def execute_source(filename, source, *, echo_filename=False):
    if echo_filename:
        print(f"{Colors.GREEN}Running: {filename}{Colors.RESET}")

    result, error = pumalang.run(filename, source)
    if error:
        print(f"{Colors.RED}{error.as_string()}{Colors.RESET}")
        return False

    formatted = format_value(result)
    if formatted is not None:
        print(f"{Colors.CYAN}{formatted}{Colors.RESET}")
    return True


def run_repl():
    print_banner()

    while True:
        try:
            text = input(f"{Colors.GREEN}{Colors.BOLD}PumaLang (onefile) > {Colors.RESET}")
        except (EOFError, KeyboardInterrupt):
            print(f"\n{Colors.YELLOW}Goodbye.{Colors.RESET}")
            break

        if not text.strip():
            continue
        if text.strip().lower() in EXIT_COMMANDS:
            print(f"{Colors.YELLOW}Session ended.{Colors.RESET}")
            break

        execute_source("<stdin>", text)


def run_file(filepath: Path):
    if not filepath.is_file():
        print(f"{Colors.RED}Error: file not found: {filepath}{Colors.RESET}")
        sys.exit(1)

    if filepath.suffix != ".pumalang":
        print(f"{Colors.YELLOW}Warning: file does not use the .pumalang extension.{Colors.RESET}")

    try:
        source = filepath.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"{Colors.RED}Failed to read file: {exc}{Colors.RESET}")
        sys.exit(1)

    if not execute_source(str(filepath.resolve()), source, echo_filename=True):
        sys.exit(1)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="pumalang-onefile",
        description="PumaLang single-file interpreter shell",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python onefile/shell.py\n"
            "  python onefile/shell.py examples/hello_world.pumalang"
        ),
    )
    parser.add_argument(
        "file",
        nargs="?",
        type=Path,
        help="Optional .pumalang source file; opens REPL when omitted",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"PumaLang {VERSION}",
    )

    args = parser.parse_args(argv)

    if args.file:
        run_file(args.file)
    else:
        run_repl()


if __name__ == "__main__":
    main()
