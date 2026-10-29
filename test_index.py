
import csv
import sqlite3
from pathlib import Path

CSV_PATH = Path("wikipedia_articles.csv")
DB_PATH = Path("test_index.db")

if not CSV_PATH.exists():
    print("ERROR: wikipedia_articles.csv not found.")
    raise SystemExit

if DB_PATH.exists():
    print("ERROR: test_index.db already exists.")
    print("Delete or rename the old test database before retrying.")
    raise SystemExit

connection = sqlite3.connect(DB_PATH)

try:
    connection.execute("""
        CREATE VIRTUAL TABLE articles
        USING fts5(title, abstract, url)
    """)

    with CSV_PATH.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        rows = []

        for row in reader:
            rows.append((
                row.get("title", ""),
                row.get("abstract", ""),
                row.get("url", "")
            ))

            if len(rows) == 1000:
                connection.executemany(
                    "INSERT INTO articles VALUES (?, ?, ?)",
                    rows
                )
                rows.clear()
                break

        if rows:
            connection.executemany(
                "INSERT INTO articles VALUES (?, ?, ?)",
                rows
            )

    connection.commit()

    print("Test records:", connection.execute(
        "SELECT COUNT(*) FROM articles"
    ).fetchone()[0])

    results = connection.execute("""
        SELECT title, url
        FROM articles
        WHERE articles MATCH ?
        LIMIT 5
    """, ("Python",)).fetchall()

    print("\nSearch results for Python:")
    for title, url in results:
        print("-", title, "|", url)

    print("\nTEST COMPLETED")

finally:
    connection.close()
