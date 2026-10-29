
import csv
import shutil
import zipfile
from pathlib import Path

import pyarrow.parquet as pq

ZIP_PATH = Path(r"C:\Users\harsh\Downloads\archive.zip")
OUTPUT_PATH = Path("wikipedia_articles.csv")

BATCH_SIZE = 5_000
MIN_FREE_GB = 3
PROGRESS_EVERY = 10


def main():
    if not ZIP_PATH.exists():
        print(f"ERROR: ZIP file not found: {ZIP_PATH}")
        return

    # Never overwrite an existing output file accidentally.
    if OUTPUT_PATH.exists():
        print(f"ERROR: {OUTPUT_PATH} already exists.")
        print("Rename or move it before starting a new extraction.")
        return

    total_saved = 0
    files = []

    try:
        with zipfile.ZipFile(ZIP_PATH) as archive:
            files = sorted(
                name for name in archive.namelist()
                if name.endswith(".parquet")
            )

            print(f"Found {len(files)} Parquet files.")
            print("Starting extraction. Keep this terminal open.")

            with OUTPUT_PATH.open(
                "w", newline="", encoding="utf-8"
            ) as output:
                writer = csv.writer(output)
                writer.writerow(["title", "abstract", "url"])

                for file_number, name in enumerate(files, start=1):
                    free_gb = (
                        shutil.disk_usage(OUTPUT_PATH.parent.resolve()).free
                        / (1024 ** 3)
                    )

                    if free_gb < MIN_FREE_GB:
                        print(
                            f"\nSTOPPED: Only {free_gb:.2f} GB "
                            "of free storage remains."
                        )
                        print(f"Saved {total_saved:,} records so far.")
                        print("The partial CSV has been preserved.")
                        return

                    print(
                        f"\nFile {file_number}/{len(files)}: {name}"
                    )

                    # Read only the three fields we need.
                    # Read the ZIP member in memory, not onto disk.
                    with archive.open(name) as member:
                        parquet_file = pq.ParquetFile(member)

                        for batch in parquet_file.iter_batches(
                            batch_size=BATCH_SIZE,
                            columns=["name", "abstract", "url"]
                        ):
                            data = batch.to_pydict()
                            rows = zip(
                                data["name"],
                                data["abstract"],
                                data["url"]
                            )

                            writer.writerows(
                                (
                                    title or "",
                                    abstract or "",
                                    url or ""
                                )
                                for title, abstract, url in rows
                            )

                            total_saved += batch.num_rows
                            output.flush()

                    if file_number % PROGRESS_EVERY == 0:
                        print(f"Records saved: {total_saved:,}")

        print("\nSUCCESS!")
        print(f"Total records saved: {total_saved:,}")
        print(f"Output file: {OUTPUT_PATH.resolve()}")
        print(
            f"CSV size: "
            f"{OUTPUT_PATH.stat().st_size / (1024 ** 3):.2f} GB"
        )

    except KeyboardInterrupt:
        print("\nStopped by user. Partial CSV has been preserved.")
        print(f"Records saved before stopping: {total_saved:,}")

    except Exception as error:
        print(f"\nERROR: {error}")
        print("Check the error before attempting another run.")


if __name__ == "__main__":
    main()
