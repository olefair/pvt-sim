from your_package_name import __version__
from your_package_name.cli import main


def test_version_present() -> None:
    assert __version__ == "0.1.0"


def test_cli_smoke(capsys) -> None:
    exit_code = main(["--name", "starter"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == "Hello, starter."
