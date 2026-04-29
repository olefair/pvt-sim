"""Enable `python -m your_package_name`."""

from .cli import main


if __name__ == "__main__":
    raise SystemExit(main())
