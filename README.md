# 📚 The Book Finder

> A sleek, modern command-line tool to search the world's books — powered by the **Google Books API**. Get titles, authors, years, categories, and description snippets, all beautifully formatted right in your terminal. ✨

---

## ✨ Features

- 🔍 Search by title, author, topic, or any keyword
- 📖 Returns up to **15 results** per query
- 🗂️ Displays title, author(s), year, category & description snippet
- 🛡️ Graceful error handling for network issues, timeouts & API errors
- 🎨 Clean terminal output with box-drawing characters & word-wrapped text
- ⚡ Fast, lightweight — zero bloat, one dependency

---

## 🧰 Requirements

- 🐍 Python **3.10+**
- 📦 [`requests`](https://pypi.org/project/requests/) library

---

## 🚀 Installation

**1. Clone or download the script**

```bash
git clone https://github.com/your-username/book-finder.git
cd book-finder
```

**2. Install the dependency**

```bash
pip install requests
```

---

## 🖥️ Usage

```bash
python book_search.py
```

You'll be prompted to enter a search term:

```
           THE BOOK FINDER
          Google Books Search
────────────────────────────────────────────────────────────────────────

  Search: dune frank herbert
```

**🔎 Example output:**

```
  6 results for  "dune frank herbert"
────────────────────────────────────────────────────────────────────────

  [01]  Dune
        Frank Herbert  ·  1965  ·  Fiction

    Set on the desert planet Arrakis, Dune is the story of the boy Paul
    Atreides, heir to a noble family tasked with ruling an inhospitable
    world where the only thing of value is the spice melange…
  ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
```

> 💡 Press `Ctrl+C` at any time to exit gracefully.

---

## ⚙️ Configuration

Tweak these constants at the top of `book_search.py` to suit your preferences:

| Constant | Default | Description |
|---|---|---|
| `MAX_RESULTS` | `15` | 📋 Max books returned per search |
| `DESC_MAX_CHARS` | `400` | ✂️ Max characters shown in description |
| `DESC_WIDTH` | `90` | 📐 Terminal column width for word wrapping |

---

## 🗂️ Project Structure

```
📁 book-finder/
├── 🐍 book_search.py   # Main script
└── 📄 README.md
```

---

## 🛡️ Error Handling

The script handles all common failure cases cleanly — no ugly tracebacks:

| Scenario | Behaviour |
|---|---|
| 🌐 No internet connection | Exits with a clear message |
| ⏱️ Request timeout (10s) | Exits with a timeout notice |
| ❌ HTTP / API error | Reports the status code and exits |
| 🔇 No results found | Informs the user and exits cleanly |
| ⌨️ `Ctrl+C` interrupt | Prints a friendly goodbye and exits |

---

## 🌐 Data Source

All book data is fetched live from the [Google Books API](https://developers.google.com/books) 📡. No API key required for standard search queries.

---

## 📄 License

**MIT** — free to use, modify, and distribute. Do whatever you like with it! 🎉
