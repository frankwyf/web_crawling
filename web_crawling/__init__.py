"""Web crawler package entry metadata."""

__all__ = ["main"]
__version__ = "0.2.0"


def main():
    from .cli import main as cli_main

    cli_main()
