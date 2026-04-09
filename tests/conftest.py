import sys
import types


if "dotenv" not in sys.modules:
    dotenv = types.ModuleType("dotenv")

    def load_dotenv(*args, **kwargs):  # pragma: no cover - no-op test stub
        return False

    dotenv.load_dotenv = load_dotenv
    sys.modules["dotenv"] = dotenv


if "anthropic" not in sys.modules:
    anthropic = types.ModuleType("anthropic")

    class _FakeMessages:
        async def create(self, *args, **kwargs):  # pragma: no cover - fail fast if a test hits the real scoring path
            raise AssertionError("Tests must not call the real Anthropic API")

    class AsyncAnthropic:  # pragma: no cover - import-only stub
        def __init__(self, *args, **kwargs):
            self.messages = _FakeMessages()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class Anthropic:  # pragma: no cover - import-only stub
        def __init__(self, *args, **kwargs):
            self.messages = _FakeMessages()

    anthropic.AsyncAnthropic = AsyncAnthropic
    anthropic.Anthropic = Anthropic
    anthropic.RateLimitError = Exception
    anthropic.APIError = Exception
    sys.modules["anthropic"] = anthropic


if "httpx" not in sys.modules:
    httpx = types.ModuleType("httpx")

    class AsyncClient:  # pragma: no cover - import-only stub
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *args, **kwargs):
            raise AssertionError("Tests must not perform real HTTPX requests")

    httpx.AsyncClient = AsyncClient
    sys.modules["httpx"] = httpx


if "aiohttp" not in sys.modules:
    aiohttp = types.ModuleType("aiohttp")

    class ClientSession:  # pragma: no cover - import-only stub
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def get(self, *args, **kwargs):
            raise AssertionError("Tests must not perform real aiohttp requests")

    class TCPConnector:  # pragma: no cover - import-only stub
        def __init__(self, *args, **kwargs):
            pass

    class ClientTimeout:  # pragma: no cover - import-only stub
        def __init__(self, *args, **kwargs):
            pass

    aiohttp.ClientSession = ClientSession
    aiohttp.TCPConnector = TCPConnector
    aiohttp.ClientTimeout = ClientTimeout
    sys.modules["aiohttp"] = aiohttp
