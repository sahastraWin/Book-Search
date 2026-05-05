"""
book_search.py  –  Google Books terminal search
Requires: requests  (pip install requests)
"""

from __future__ import annotations

import sys
import textwrap
from typing import TypedDict

import requests

API_URL = "https://www.googleapis.com/books/v1/volumes"
MAX_RESULTS = 15
DESC_WIDTH = 90
DESC_MAX_CHARS = 400


class Book(TypedDict):
    index: int
    title: str
    authors: str
    year: str
    category: str
    desc: str


# ─── API ─────────────────────────────────────────────────────────────────────

def fetch_books(query: str) -> list[Book]:
    try:
        response = requests.get(
            API_URL,
            params={"q": query, "maxResults": MAX_RESULTS},
            timeout=10,
        )
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        _die("No network connection. Check your internet and try again.")
    except requests.exceptions.Timeout:
        _die("Request timed out. The Google Books API is not responding.")
    except requests.exceptions.HTTPError as exc:
        _die(f"API returned an error: {exc.response.status_code}")
    except requests.exceptions.RequestException as exc:
        _die(f"Unexpected network error: {exc}")

    items = response.json().get("items", [])
    return [_parse_item(i, item) for i, item in enumerate(items, start=1)]


def _parse_item(index: int, item: dict) -> Book:
    info = item.get("volumeInfo", {})

    raw_authors = info.get("authors", [])
    authors = ", ".join(raw_authors) if raw_authors else "Unknown"

    raw_desc = info.get("description", "").replace("\n", " ").strip()
    if len(raw_desc) > DESC_MAX_CHARS:
        raw_desc = raw_desc[:DESC_MAX_CHARS].rstrip() + "…"
    desc = raw_desc or "No description available."

    categories = info.get("categories", [])
    category = categories[0] if categories else ""

    year = info.get("publishedDate", "")[:4]

    return Book(
        index=index,
        title=info.get("title", "Untitled"),
        authors=authors,
        year=year,
        category=category,
        desc=desc,
    )


# ─── Display ─────────────────────────────────────────────────────────────────

DIVIDER = "─" * 72
THIN    = "┄" * 72


def _header() -> None:
    print(f"\n{'THE BOOK FINDER':^72}")
    print(f"{'Google Books Search':^72}")
    print(DIVIDER)


def _render_book(book: Book) -> None:
    idx       = f"[{book['index']:02d}]"
    byline    = book["authors"]
    if book["year"]:
        byline += f"  ·  {book['year']}"
    if book["category"]:
        byline += f"  ·  {book['category']}"

    wrapped = textwrap.fill(
        book["desc"],
        width=DESC_WIDTH,
        initial_indent="    ",
        subsequent_indent="    ",
    )

    print(f"\n  {idx}  {book['title']}")
    print(f"        {byline}")
    print(wrapped)
    print(f"  {THIN}")


def _render_results(books: list[Book], query: str) -> None:
    count_line = f"  {len(books)} results for  \"{query}\""
    print(f"\n{count_line}")
    print(DIVIDER)
    for book in books:
        _render_book(book)
    print()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _die(message: str) -> None:
    print(f"\n  Error  {message}\n", file=sys.stderr)
    sys.exit(1)


# ─── Entry point ─────────────────────────────────────────────────────────────

def main() -> None:
    _header()

    try:
        query = input("\n  Search: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n  Goodbye.\n")
        return

    if not query:
        print("  Please enter a search term.\n")
        return

    print(f"\n  Searching …\n")
    books = fetch_books(query)

    if not books:
        print(f"  No results found for \"{query}\".\n")
        return

    _render_results(books, query)


if __name__ == "__main__":
    main()
