"""Lets ``python -m resumex`` do exactly what the ``resumex`` command does."""

import sys

from resumex.cli import main

if __name__ == "__main__":
    sys.exit(main())
