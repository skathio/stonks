# =============================================================================
# Shared plumbing for the daily agent pipeline: config, HTTP, rate limiting,
# logging, JSON I/O.
#
# Stdlib only: the pipeline runs inside a Claude Code cloud session where
# nothing is installed and installs are not wanted.
#
# Credentials:
#   - Local runs read keys from the environment or a `.env` next to the repo
#     root (gitignored).
#   - Cloud runs (CLAUDE_CODE_REMOTE set) get Massive and Finnhub keys injected
#     into request headers by the agent proxy (network secrets). The process
#     never sees them, so missing env keys are expected there.
#   - FRED takes its key only as a URL parameter, so it is a plain env var.
# =============================================================================
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_DATA_DIR = os.path.join(REPO_ROOT, "site", "data")
TIMEOUT_S = 45
MAX_RETRIES = 4
BROWSER_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


def load_env_file(path):
    """Load KEY=VALUE lines into os.environ; already-exported values win."""
    if not os.path.isfile(path):
        return
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            value = value.strip().strip('"').strip("'")
            if value and not os.environ.get(name.strip()):
                os.environ[name.strip()] = value


load_env_file(os.environ.get("STONKS_ENV_FILE") or os.path.join(REPO_ROOT, ".env"))

IN_CLOUD = bool(os.environ.get("CLAUDE_CODE_REMOTE"))


def data_dir():
    """Private state repo (price history, prompt, run artifacts)."""
    path = os.environ.get("STONKS_DATA_DIR") or os.path.join(os.path.dirname(REPO_ROOT), "stonks-data")
    if not os.path.isdir(path):
        raise SystemExit(f"stonks-data repo not found at {path} (set STONKS_DATA_DIR)")
    return path


def log(event, **fields):
    """One structured line per event on stderr, so stdout stays machine-readable."""
    payload = " ".join(f"{k}={json.dumps(v) if not isinstance(v, (int, float)) else v}" for k, v in fields.items())
    print(f"[{time.strftime('%H:%M:%S')}] {event} {payload}".rstrip(), file=sys.stderr, flush=True)


# =============================================================================
# HTTP
# =============================================================================
class HttpError(Exception):
    def __init__(self, url, status, body):
        super().__init__(f"HTTP {status} for {redact(url)}: {body[:200]!r}")
        self.status = status
        self.body = body


def redact(url):
    parts = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    clean = [(k, "***" if k.lower() in ("api_key", "apikey", "token") else v) for k, v in query]
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(clean)))


def http_get(url, headers=None, retry_statuses=(429, 500, 502, 503, 504)):
    """GET with bounded exponential backoff. Returns body bytes or raises HttpError."""
    hdrs = {"User-Agent": BROWSER_UA, "Accept-Encoding": "gzip", **(headers or {})}
    delay = 2.0
    for attempt in range(MAX_RETRIES + 1):
        req = urllib.request.Request(url, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                body = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                return body
        except urllib.error.HTTPError as exc:
            body = exc.read()
            if exc.code in retry_statuses and attempt < MAX_RETRIES:
                log("http.retry", url=redact(url), status=exc.code, attempt=attempt + 1)
                time.sleep(delay)
                delay *= 2
                continue
            raise HttpError(url, exc.code, body.decode("utf-8", "replace")) from None
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt < MAX_RETRIES:
                log("http.retry", url=redact(url), error=str(exc), attempt=attempt + 1)
                time.sleep(delay)
                delay *= 2
                continue
            raise HttpError(url, None, str(exc)) from None
    raise AssertionError("unreachable")


def http_json(url, headers=None):
    return json.loads(http_get(url, headers))


class RateLimiter:
    """Minimum spacing between calls to one provider."""

    def __init__(self, min_interval_s):
        self.min_interval_s = min_interval_s
        self._last = 0.0

    def wait(self):
        gap = time.monotonic() - self._last
        if gap < self.min_interval_s:
            time.sleep(self.min_interval_s - gap)
        self._last = time.monotonic()


# =============================================================================
# JSON / files
# =============================================================================
def read_json(path, default=None):
    if not os.path.isfile(path):
        return default
    with open(path) as fh:
        return json.load(fh)


def write_json(path, obj, compact=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        if compact:
            json.dump(obj, fh, separators=(",", ":"), sort_keys=True)
        else:
            json.dump(obj, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)
