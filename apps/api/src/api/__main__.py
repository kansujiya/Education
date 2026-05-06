"""Make ``python -m api`` invoke the CLI."""

from api.cli.app import app

if __name__ == "__main__":
    app()
