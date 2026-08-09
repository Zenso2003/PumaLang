#!/usr/bin/env python3
"""
PumaLang command-line shell for the modular interpreter.

Usage:
    python -m pumalang.shell                  # REPL (basic mode)
    python -m pumalang.shell script.pumalang      # run a script (basic mode)
    python -m pumalang.shell -d script.pumalang   # run with debug diagnostics
"""

import argparse
import os
import sys
from enum import Enum
from pathlib import Path


def _ensure_package_path():
    # Allow `python pumalang/shell.py` to resolve the pumalang package.
    if __package__:
        return
    root = Path(__file__).resolve().parent.parent
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


_ensure_package_path()

from pumalang.globals import create_program_scope
from pumalang.run import run


def _enable_windows_vt():
    # Enable ANSI escape sequences on legacy Windows consoles.
    if sys.platform != "win32":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return
        enable_vt = 0x0004
        kernel32.SetConsoleMode(handle, mode.value | enable_vt)
    except (AttributeError, OSError):
        pass


class TerminalStyle:
    """TTY styling with 24-bit true color when available."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # RGB palette used for true-color rendering.
    PALETTE = {
        "cyan": (86, 182, 194),
        "green": (152, 195, 121),
        "yellow": (229, 192, 123),
        "red": (224, 108, 117),
        "purple": (198, 120, 221),
        "blue": (97, 175, 239),
        "muted": (127, 132, 156),
        "gradient_start": (86, 182, 194),
        "gradient_end": (198, 120, 221),
    }

    # Fallback ANSI colors for terminals without true-color support.
    ANSI = {
        "cyan": "\033[36m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "red": "\033[31m",
        "purple": "\033[35m",
        "blue": "\033[34m",
        "muted": "\033[90m",
    }

    def __init__(self):
        _enable_windows_vt()
        self.enabled = self._color_enabled()
        self.truecolor = self.enabled and self._truecolor_supported()

    def _color_enabled(self):
        if os.environ.get("NO_COLOR") is not None:
            return False
        if os.environ.get("FORCE_COLOR") is not None:
            return True
        return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

    def _truecolor_supported(self):
        colorterm = os.environ.get("COLORTERM", "").lower()
        if colorterm in {"truecolor", "24bit"}:
            return True

        term = os.environ.get("TERM", "").lower()
        if "truecolor" in term or "24bit" in term:
            return True

        # Common modern terminals that support 24-bit color.
        if os.environ.get("WT_SESSION"):
            return True
        if os.environ.get("TERM_PROGRAM") in {"vscode", "Apple_Terminal", "iTerm.app"}:
            return True
        if sys.platform == "win32":
            return True

        return False

    def _true_fg(self, rgb):
        r, g, b = rgb
        return f"\033[38;2;{r};{g};{b}m"

    def paint(self, name, text="", *, bold=False, dim=False):
        if not self.enabled:
            return text

        prefix = ""
        if bold:
            prefix += self.BOLD
        if dim:
            prefix += self.DIM

        if self.truecolor and name in self.PALETTE:
            return f"{prefix}{self._true_fg(self.PALETTE[name])}{text}{self.RESET}"

        if name in self.ANSI:
            return f"{prefix}{self.ANSI[name]}{text}{self.RESET}"

        return f"{prefix}{text}{self.RESET}"

    def gradient_line(self, text, start_rgb, end_rgb):
        if not self.enabled or not text:
            return text

        visible = len(text)
        if visible == 0:
            return text

        if not self.truecolor:
            return self.paint("cyan", text, bold=True)

        parts = []
        for index, char in enumerate(text):
            ratio = index / max(visible - 1, 1)
            r = round(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * ratio)
            g = round(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * ratio)
            b = round(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * ratio)
            parts.append(f"{self._true_fg((r, g, b))}{char}")

        return f"{self.BOLD}{''.join(parts)}{self.RESET}"


style = TerminalStyle()


class RunMode(Enum):
    """Shell output mode."""

    BASIC = "basic"   # default: program output and errors only
    DEBUG = "debug"   # additionally show lexer/parser diagnostics


BANNER = r"""
"""

VERSION = "0.2.0"
EXIT_COMMANDS = {"exit", "quit", "bye"}


def print_banner(mode: RunMode):
    start = TerminalStyle.PALETTE["gradient_start"]
    end = TerminalStyle.PALETTE["gradient_end"]

    for line in BANNER.splitlines():
        if line.strip():
            print(style.gradient_line(line, start, end))
        else:
            print()

    mode_label = mode.value.upper()
    mode_color = "purple" if mode is RunMode.DEBUG else "green"
    title = style.paint("cyan", "PumaLang Shell ", bold=True)
    version = style.paint(mode_color, f"v{VERSION} [{mode_label}]", bold=True)
    print(f"{title}{version}")
    print(style.paint("muted", "Type exit, quit, bye, or press Ctrl+C to leave"))
    print(style.paint("muted", "=" * 60))


def execute_source(
    filename,
    source,
    *,
    mode: RunMode = RunMode.BASIC,
    echo_filename: bool = False,
    program_scope=None,
):
    """
    Compile and run source code.

    Basic mode : only runtime output from the program itself, plus errors.
    Debug mode : also prints lexer/parser diagnostics (no return-value echo).
    """
    debug = mode is RunMode.DEBUG

    if echo_filename and debug:
        print(style.paint("muted", f"Running: {filename}", dim=True))

    _result, error = run(filename, source, debug=debug, program_scope=program_scope)
    if error:
        print(style.paint("red", error.as_string()))
        return False

    return True


def run_repl(*, mode: RunMode = RunMode.BASIC):
    print_banner(mode)
    program_scope = create_program_scope()

    prompt = style.paint("green", "PumaLang > ", bold=True)

    while True:
        try:
            text = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print(f"\n{style.paint('yellow', 'Goodbye.')}")
            break

        if not text.strip():
            continue
        if text.strip().lower() in EXIT_COMMANDS:
            print(style.paint("yellow", "Session ended."))
            break

        execute_source("<stdin>", text, mode=mode, program_scope=program_scope)


def run_file(filepath: Path, *, mode: RunMode = RunMode.BASIC):
    if not filepath.is_file():
        print(style.paint("red", f"Error: file not found: {filepath}"))
        sys.exit(1)

    if filepath.suffix != ".pumalang":
        print(style.paint("yellow", "Warning: file does not use the .pumalang extension."))

    try:
        source = filepath.read_text(encoding="utf-8")
    except OSError as exc:
        print(style.paint("red", f"Failed to read file: {exc}"))
        sys.exit(1)

    if not execute_source(
        str(filepath.resolve()),
        source,
        mode=mode,
        echo_filename=True,
    ):
        sys.exit(1)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="pumalang",
        description="PumaLang modular interpreter shell",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m pumalang.shell\n"
            "  python -m pumalang.shell examples/hello_world.pumalang\n"
            "  python -m pumalang.shell -d examples/test_arithmetic.pumalang"
        ),
    )
    parser.add_argument(
        "file",
        nargs="?",
        type=Path,
        help="Optional .pumalang source file; opens REPL when omitted",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Enable debug mode (lexer/parser diagnostics only)",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"PumaLang {VERSION}",
    )
    return parser


def resolve_mode(debug_flag: bool) -> RunMode:
    return RunMode.DEBUG if debug_flag else RunMode.BASIC


def main(argv=None):
    args = build_parser().parse_args(argv)
    mode = resolve_mode(args.debug)

    if args.file:
        run_file(args.file, mode=mode)
    else:
        run_repl(mode=mode)


if __name__ == "__main__":
    main()
