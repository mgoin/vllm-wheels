#!/usr/bin/env python3
"""Build the dependency-free static site and its Sites worker."""

from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE_DIR = ROOT / "site"
DATA_DIR = ROOT / "data"
DIST_DIR = ROOT / "dist"
CLIENT_DIR = DIST_DIR / "client"
SERVER_DIR = DIST_DIR / "server"

WORKER = """\
const DEFAULT_ORIGIN = "https://mgoin.github.io/vllm-wheels";

export default {
  async fetch(request, env) {
    const response = await env.ASSETS.fetch(request);
    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("text/html")) {
      return response;
    }

    const incomingOrigin = new URL(request.url).origin;
    const html = (await response.text()).replaceAll(DEFAULT_ORIGIN, incomingOrigin);
    const headers = new Headers(response.headers);
    headers.set("content-type", "text/html; charset=utf-8");
    return new Response(html, {
      status: response.status,
      statusText: response.statusText,
      headers,
    });
  },
};
"""


def main() -> None:
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    shutil.copytree(SITE_DIR, CLIENT_DIR)
    shutil.copytree(DATA_DIR, CLIENT_DIR / "data")
    SERVER_DIR.mkdir(parents=True)
    (SERVER_DIR / "index.js").write_text(WORKER, encoding="utf-8")
    print(f"Built site in {DIST_DIR}")


if __name__ == "__main__":
    main()

