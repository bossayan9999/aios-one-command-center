from pathlib import Path


def test_local_file_launch_redirects_to_fastapi() -> None:
    html = Path("web/index.html").read_text(encoding="utf-8")
    assert 'window.location.protocol === "file:"' in html
    assert 'window.location.replace("http://127.0.0.1:8000/")' in html
