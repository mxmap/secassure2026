"""Functional battery for the keyless basemap (js/map-shared.js).

Context: CARTO put its raster basemaps behind API keys (watermark rollout
2026-08-28, enforcement 2026-09-23). The keyless URLs kept answering
**HTTP 200** while serving a fixed "API KEY REQUIRED" watermark tile —
the map broke *silently*: no 4xx, no console error, invisible to any
status check. This battery is the tripwire for that failure class, on
two levels:

STRUCTURAL (offline, deterministic) — the basemap config stays coherent:
keyless templates only, the axis-order rule per host (Esri is
``/tile/{z}/{y}/{x}``, INVERTED vs slippy ``/{z}/{x}/{y}`` — a mismatch
renders the wrong place on Earth with zero errors), the label-overlay
blend CSS, the runtime failover wiring, preconnects aligned.

FUNCTIONAL (network) — real tiles actually arrive, from the primary AND
from the reserve (the fallback must not turn out dead the day it is
needed): HTTP 200 + image/* + a minimum size on LAND tiles (Rome, Milan
— never open sea, which yields tiny uniform tiles) + the decisive
ANTI-PLACEHOLDER check: two different coordinates MUST return different
bytes. A watermark is identical everywhere; real tiles never are.
"""

from __future__ import annotations

import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAP_JS = ROOT / "js" / "map-shared.js"
MAP_CSS = ROOT / "css" / "map.css"
UA = "secassure2026-basemap-battery/1.0 (+https://github.com/mxmap/secassure2026)"

# Sample tiles at z=6 on European LAND (Rome, Milan), slippy order (z, x, y).
SAMPLE_TILES = [(6, 34, 23), (6, 33, 22)]

# A real land base tile at z=6 weighs >5 KB; the CARTO "API KEY REQUIRED"
# placeholder was 2049 fixed bytes. Label-only tiles are sparse -> lower bar.
MIN_BYTES_BASE = 3000
MIN_BYTES_LABELS = 800

BASEMAP_FIELD_RE = re.compile(r"^\s*(base|fallbackBase|fallbackLabels):\s*'([^']+)'", re.M)


@pytest.fixture(scope="module")
def map_js() -> str:
    return MAP_JS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def templates(map_js: str) -> dict[str, str]:
    found = dict(BASEMAP_FIELD_RE.findall(map_js))
    assert set(found) == {"base", "fallbackBase", "fallbackLabels"}, (
        f"BASEMAP templates not found in js/map-shared.js: {sorted(found)}"
    )
    return found


def _host(template: str) -> str:
    return urlsplit(template.replace("{s}", "a")).hostname or ""


def _tile_url(template: str, z: int, x: int, y: int) -> str:
    return (
        template.replace("{s}", "a")
        .replace("{r}", "")
        .replace("{z}", str(z))
        .replace("{x}", str(x))
        .replace("{y}", str(y))
    )


def _fetch(url: str, retries: int = 2) -> tuple[int, str, bytes]:
    """GET with retry/backoff on transient errors only (network, 5xx)."""
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.status, r.headers.get("Content-Type", ""), r.read()
        except urllib.error.HTTPError as e:
            if e.code >= 500 and attempt < retries:
                last = e
                time.sleep(5 * (attempt + 1))
                continue
            return e.code, e.headers.get("Content-Type", ""), e.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last = e
            if attempt < retries:
                time.sleep(5 * (attempt + 1))
    pytest.fail(f"unreachable after {retries + 1} attempts: {url} — {last!r}")


def _assert_axis_rule(template: str) -> None:
    host = _host(template)
    for var in ("{z}", "{x}", "{y}"):
        assert var in template, f"variable {var} missing in template {template}"
    if host.endswith("arcgisonline.com"):
        assert "/tile/{z}/{y}/{x}" in template, (
            f"Esri uses /tile/{{z}}/{{y}}/{{x}} (inverted vs slippy), got: {template}"
        )
        assert "{s}" not in template and "{r}" not in template, (
            f"Esri supports neither {{s}} subdomains nor {{r}} retina: {template}"
        )
    elif host.endswith("cartocdn.com") or host.endswith("openstreetmap.org"):
        assert "/{z}/{x}/{y}" in template, f"{host} uses slippy /{{z}}/{{x}}/{{y}} order, got: {template}"


def _assert_real_tiles(template: str, min_bytes: int) -> None:
    payloads = []
    for z, x, y in SAMPLE_TILES:
        url = _tile_url(template, z, x, y)
        status, ctype, body = _fetch(url)
        assert status == 200, f"tile {url}: HTTP {status}"
        assert ctype.startswith("image/"), f"tile {url}: Content-Type '{ctype}'"
        assert len(body) >= min_bytes, (
            f"tile {url}: {len(body)} bytes < {min_bytes} — likely a placeholder "
            "or error hidden behind HTTP 200 (the CARTO incident class)"
        )
        payloads.append(body)
    assert payloads[0] != payloads[1], (
        f"ANTI-PLACEHOLDER: {template} returns IDENTICAL bytes for Rome and "
        "Milan — that is an everywhere-identical watermark (e.g. 'API KEY "
        "REQUIRED'), not a real basemap"
    )


# ── STRUCTURAL (offline) ─────────────────────────────────────────────────────


def test_templates_are_keyless(templates: dict[str, str], map_js: str) -> None:
    for name, template in templates.items():
        assert "key=" not in template and "apikey" not in template.lower(), (
            f"basemap template {name} must not require a key: {template}"
        )
    assert "cartocdn.com" not in map_js, (
        "keyless CARTO reintroduced: dead since 2026-09 (serves only an 'API KEY REQUIRED' watermark, with HTTP 200!)"
    )
    assert "CARTO_KEY" not in map_js, "CARTO_KEY machinery must stay removed"


def test_axis_order_per_host(templates: dict[str, str]) -> None:
    for template in templates.values():
        _assert_axis_rule(template)


def test_label_overlay_css_contract() -> None:
    """The blend pane is what keeps place names ABOVE the data polygons;
    without it OSM's baked-in labels are covered. Hidden by default +
    @supports guard so unsupported browsers never get opaque tiles over
    the data."""
    css = MAP_CSS.read_text(encoding="utf-8")
    for marker in (
        ".leaflet-basemap-labels-pane",
        "mix-blend-mode: darken",
        "@supports (mix-blend-mode: darken)",
        ".leaflet-layer.basemap-muted",
    ):
        assert marker in css, f"basemap CSS contract: missing '{marker}' in css/map.css"


def test_failover_wiring_present(map_js: str) -> None:
    for marker in (
        "createPane('basemap-labels')",
        "on('tileerror'",
        "failoverThreshold",
        "activateBasemapFailover",
        "window.__forceBasemapFailover",
    ):
        assert marker in map_js, f"basemap failover: missing '{marker}' in js/map-shared.js"


def test_preconnects_aligned() -> None:
    for page in ("providers.html", "security.html"):
        html = (ROOT / page).read_text(encoding="utf-8")
        assert 'rel="preconnect" href="https://tile.openstreetmap.org"' in html, (
            f"{page}: missing preconnect to the tile host"
        )
        assert "cartocdn.com" not in html, f"{page}: stale cartocdn preconnect"


# ── FUNCTIONAL (network) ─────────────────────────────────────────────────────


def test_primary_tiles_are_real(templates: dict[str, str]) -> None:
    _assert_real_tiles(templates["base"], MIN_BYTES_BASE)


def test_fallback_tiles_are_real(templates: dict[str, str]) -> None:
    """The reserve is exercised with the same criteria as the primary, so
    it cannot rot unnoticed until the day the failover actually fires."""
    _assert_real_tiles(templates["fallbackBase"], MIN_BYTES_BASE)
    _assert_real_tiles(templates["fallbackLabels"], MIN_BYTES_LABELS)
