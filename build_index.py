
import csv
import shutil
import sqlite3
import sys
from pathlib import Path

CSV_PATH = Path("wikipedia_articles.csv")
DB_PATH = Path("wikipedia_index.db")

BATCH_SIZE = 5_000
MIN_FREE_GB = 5
EXPECTED_ROWS = 10_468_881

# Allow unusually long Wikipedia abstracts.
csv.field_size_limit(10_000_000)


def free_gb():
    return shutil.disk_usage(DB_PATH.parent.resolve()).free / (1024 ** 3)


def main():
    if not CSV_PATH.exists():
        print(f"ERROR: CSV not found: {CSV_PATH.resolve()}")
        return

    if free_gb() < 10 and not DB_PATH.exists():
        print(f"Only {free_gb():.2f} GB free. Not starting.")
        return

    if not DB_PATH.exists():
        print("ERROR: Existing database not found.")
        print("This recovery script is intended to resume an existing import.")
        return

    db = sqlite3.connect(DB_PATH)

    try:
        db.execute("PRAGMA journal_mode=DELETE")
        db.execute("PRAGMA synchronous=NORMAL")
        db.execute("PRAGMA cache_size=-32000")
        db.execute("PRAGMA temp_store=FILE")

        table = db.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='articles'
        """).fetchone()

        if not table:
            print("ERROR: The database has no articles table.")
            print("The existing database has been preserved.")
            return

        # Resume after the number of rows already stored.
        existing = db.execute(
            "SELECT COUNT(*) FROM articles"
        ).fetchone()[0]

        print(f"Existing database rows: {existing:,}")

        if existing > EXPECTED_ROWS:
            print("ERROR: More rows than expected. Stopping safely.")
            return

        # Check whether the full-text index already exists.
        fts_exists = db.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='article_search'
        """).fetchone()

        if fts_exists:
            indexed = db.execute(
                "SELECT COUNT(*) FROM article_search"
            ).fetchone()[0]

            if indexed == existing == EXPECTED_ROWS:
                print("SUCCESS: All rows and search index already exist.")
                return

            print("An existing full-text index is incomplete.")
            print("Stopping rather than modifying it automatically.")
            print("The database has been preserved.")
            return

        total = existing
        print("Scanning CSV to resume at the next unimported row...")

        with CSV_PATH.open(
            "r", encoding="utf-8", newline=""
        ) as source:
            reader = csv.DictReader(source)

            # Skip rows already imported into SQLite.
            for _ in range(existing):
                skipped = next(reader, None)
                if skipped is None:
                    print("ERROR: CSV ended before the database row count.")
                    return

            while True:
                available = free_gb()

                if available < MIN_FREE_GB:
                    print(
                        f"STOPPED: Free storage is {available:.2f} GB, "
                        "below the 5 GB safety limit."
                    )
                    print(f"Rows stored so far: {total:,}")
                    return

                rows = []

                for _ in range(BATCH_SIZE):
                    row = next(reader, None)
                    if row is None:
                        break

                    rows.append((
                        row.get("title") or "",
                        row.get("abstract") or "",
                        row.get("url") or ""
                    ))

                if not rows:
                    break

                db.executemany("""
                    INSERT INTO articles(title, abstract, url)
                    VALUES (?, ?, ?)
                """, rows)

                db.commit()
                total += len(rows)

                print(
                    f"Imported {total:,}/{EXPECTED_ROWS:,} "
                    f"| Free storage: {free_gb():.2f} GB"
                )

                del rows

        actual = db.execute(
            "SELECT COUNT(*) FROM articles"
        ).fetchone()[0]

        if actual != EXPECTED_ROWS:
            print(
                f"Import incomplete: {actual:,} rows, "
                f"expected {EXPECTED_ROWS:,}."
            )
            return

        print("\nAll articles imported.")
        print("Checking storage before creating full-text index...")

        available = free_gb()
        if available < 8:
            print(f"Only {available:.2f} GB free.")
            print("Not creating the full-text index yet.")
            print("Article data remains saved in the database.")
            return

        print("Creating full-text search index. This may take a while...")

        db.execute("""
            CREATE VIRTUAL TABLE article_search
            USING fts5(
                title, abstract,
                content='articles',
                content_rowid='id'
            )
        """)

        db.commit()

        db.execute("""
            INSERT INTO article_search(rowid, title, abstract)
            SELECT id, title, abstract FROM articles
        """)

        db.commit()

        print("\nSUCCESS!")
        print(f"Articles stored: {actual:,}")
        print(f"Database: {DB_PATH.resolve()}")
        print(f"Database size: {DB_PATH.stat().st_size / (1024**3):.2f} GB")
        print(f"Free storage: {free_gb():.2f} GB")

    except KeyboardInterrupt:
        db.rollback()
        print("\nInterrupted. Committed batches remain saved.")
        print("You can run this script again to resume the import.")

    except Exception as error:
        db.rollback()
        print(f"\nERROR: {error}")
        print("Committed batches remain saved. Do not delete the database.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
