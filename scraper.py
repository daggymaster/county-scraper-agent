import csv
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

BASE_URL = "https://traviscad.org"
START_URL = "https://traviscad.org/property-search?search="
OUTPUT_FILE = "leads.csv"
MAX_PAGES = 5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


# ---------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------

def get_soup(url):
    """
    Download a page and return a BeautifulSoup object.
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except requests.RequestException as e:
        print(f"[ERROR] Failed to retrieve {url}: {e}")
        return None


def clean_text(value):
    """
    Normalize whitespace and safely return text.
    """
    if not value:
        return ""
    return " ".join(value.get_text(" ", strip=True).split())


def find_results_table(soup):
    """
    Locate the property results table.
    """
    table = soup.find("table", class_="table")
    if table:
        return table

    # Fallback: find any table with "table-striped"
    tables = soup.find_all("table")
    for tbl in tables:
        classes = tbl.get("class", [])
        if "table-striped" in classes:
            return tbl

    return None


def map_row_to_record(headers, row):
    """
    Convert a table row into a standardized dictionary.
    """
    cells = row.find_all(["td", "th"])
    values = [cell.get_text(" ", strip=True) for cell in cells]

    record = {
        "Parcel ID": "",
        "Property Address": "",
        "Owner Name": "",
        "Mailing Address": "",
        "Legal Description": "",
        "Tax Status": ""
    }

    for header, value in zip(headers, values):
        h = header.lower()

        if "parcel" in h or "prop id" in h or "property id" in h:
            record["Parcel ID"] = value

        elif "property address" in h or (
            "address" in h and "mail" not in h
        ):
            record["Property Address"] = value

        elif "owner" in h:
            record["Owner Name"] = value

        elif "mail" in h:
            record["Mailing Address"] = value

        elif "legal" in h:
            record["Legal Description"] = value

        elif "tax" in h and "status" in h:
            record["Tax Status"] = value

    return record


def extract_records_from_table(table):
    """
    Extract property records from the results table.
    """
    records = []

    header_row = table.find("thead")
    if header_row:
        headers = [
            clean_text(th)
            for th in header_row.find_all(["th", "td"])
        ]
    else:
        first_row = table.find("tr")
        headers = [
            clean_text(th)
            for th in first_row.find_all(["th", "td"])
        ] if first_row else []

    tbody = table.find("tbody")
    rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]

    for row in rows:
        try:
            record = map_row_to_record(headers, row)

            # Skip completely empty rows
            if any(record.values()):
                records.append(record)

        except Exception as e:
            print(f"[WARNING] Failed to parse row: {e}")

    return records


def find_next_page(soup, current_url):
    """
    Find the next pagination link.
    """
    # Look for pagination links containing "next"
    next_link = soup.find(
        "a",
        string=lambda s: s and "next" in s.lower()
    )

    if next_link and next_link.get("href"):
        return urljoin(current_url, next_link["href"])

    # Fallback: look for rel=next
    next_link = soup.find("a", attrs={"rel": "next"})
    if next_link and next_link.get("href"):
        return urljoin(current_url, next_link["href"])

    # Fallback: pagination item with class "next"
    next_item = soup.select_one(".next a")
    if next_item and next_item.get("href"):
        return urljoin(current_url, next_item["href"])

    return None


# ---------------------------------------------------------------------
# Main Scraper
# ---------------------------------------------------------------------

def scrape_properties():
    all_records = []
    url = START_URL
    page_num = 1

    while url and page_num <= MAX_PAGES:
        print(f"[INFO] Scraping page {page_num}: {url}")

        soup = get_soup(url)
        if not soup:
            break

        table = find_results_table(soup)

        if not table:
            print("[WARNING] No results table found on page.")
            break

        records = extract_records_from_table(table)
        print(f"[INFO] Extracted {len(records)} records.")

        all_records.extend(records)

        next_url = find_next_page(soup, url)

        if not next_url:
            print("[INFO] No additional pages found.")
            break

        url = next_url
        page_num += 1

        # Be polite to the server
        time.sleep(1)

    return all_records


def save_to_csv(records, filename):
    """
    Save extracted records to CSV.
    """
    fieldnames = [
        "Parcel ID",
        "Property Address",
        "Owner Name",
        "Mailing Address",
        "Legal Description",
        "Tax Status"
    ]

    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for record in records:
            writer.writerow(record)

    print(f"[INFO] Saved {len(records)} records to {filename}")


# ---------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------

if __name__ == "__main__":
    try:
        records = scrape_properties()

        if records:
            save_to_csv(records, OUTPUT_FILE)
        else:
            print("[INFO] No records were extracted.")

    except Exception as exc:
        print(f"[FATAL ERROR] {exc}")
