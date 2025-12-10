import requests
import sys
from typing import List, Dict, Any, Union
def search_books(query: str) -> List[Dict[str, Any]]:
    """Fetches book data from the Google Books API."""
    url = "https://www.googleapis.com/books/v1/volumes"
    params = {"q": query, "maxResults": 15}

    try:
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status() 
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Network Error: Failed to connect to Google Books API. Check your connection or the URL.\n Details: {e}\n")

        sys.exit(1)
        
    data = res.json()
    if "items" not in data:
        return []

    books = []
    for item in data["items"]:
        info = item.get("volumeInfo", {})
        
        authors = info.get("authors", ["Unknown"])
        if isinstance(authors, list):
            authors_str = ", ".join(authors)
        elif isinstance(authors, str):
            authors_str = authors
        else:
            authors_str = "Unknown"
        
        desc = info.get("description", "No description available.")
        desc_snippet = desc[:400].replace('\n', ' ').strip()
        desc_display = desc_snippet + ("..." if len(desc) > 400 else "")

        books.append({
            "title": info.get("title", "N/A"),
            "authors": authors_str,
            "desc": desc_display
        })
    return books

def main():
    """Runs the main command-line book search application."""
    print("\n📚 Google Books Terminal Search")
    print("-" * 35)
    
    query = input("Enter book name to search: ").strip()
    if not query:
        print("Please enter a valid search query.")
        return 

    print(f"\n🔍 Searching for '{query}'...")
    books = search_books(query)

    if not books:
        print(f"\nNo books found for '{query}'.")
        return

    print(f"\n--- Found {len(books)} Results ---")
    for i, book in enumerate(books, start=1):
        print(f"\n[{i:02d}] {book['title']}")
        print(f"  > By: {book['authors']}")
        print(f"  > Snippet: {book['desc']}")

if __name__ == "__main__":
    main()