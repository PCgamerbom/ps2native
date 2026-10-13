"""Ponto de entrada da GUI (usado também pelo PyInstaller)."""
import sys

from ps2native.gui import run

if __name__ == "__main__":
    sys.exit(run())
