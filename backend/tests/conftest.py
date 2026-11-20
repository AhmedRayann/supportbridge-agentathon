import shutil
import subprocess
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import httpx
import pytest

from backend.main import app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as test_client:
        yield test_client


@pytest.fixture
def release_git_history() -> Callable[..., bytes]:
    """Read local provenance when Git and the pinned history are available."""
    root = Path(__file__).resolve().parents[2]
    if not (root / ".git").exists() or shutil.which("git") is None:
        pytest.skip("Local Git metadata/executable is unavailable")

    def read_git(*args: str) -> bytes:
        return subprocess.check_output(
            ["git", "-c", f"safe.directory={root.as_posix()}", *args],
            cwd=root,
            stderr=subprocess.PIPE,
        )

    try:
        repository = Path(read_git("rev-parse", "--show-toplevel").decode().strip())
        if repository.resolve() != root:
            pytest.skip("Tests are not inside the SupportBridge Git repository")
        for sha in (
            "a4eeea911604494f693e027cdaca5f2da2f78a7e",
            "c8473e4fcdb3f71630301c13c37fbf742c2a14ef",
        ):
            read_git("cat-file", "-e", f"{sha}^{{commit}}")
    except subprocess.CalledProcessError:
        pytest.skip("Pinned release history is unavailable in this checkout")
    return read_git
