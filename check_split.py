
import csv
from pathlib import Path

data_folder = Path("data")

files = [
    "Opportunity.csv",
    "Opportunity_train.csv",
    "Opportunity_test.csv",
    "opportunity_split.csv"
]

for filename in files:
    file_path = data_folder / filename

    if file_path.exists():
        with open(file_path, "r", newline="", encoding="utf-8") as file:
            rows = list(csv.DictReader(file))
            print(f"{filename}: {len(rows)} rows")
    else:
        print(f"{filename}: FILE NOT FOUND")

print("\nSplit verification:")

with open(data_folder / "Opportunity_train.csv", newline="", encoding="utf-8") as file:
    train = list(csv.DictReader(file))

with open(data_folder / "Opportunity_test.csv", newline="", encoding="utf-8") as file:
    test = list(csv.DictReader(file))

if train and test:
    latest_train = max(row["created_at"] for row in train)
    earliest_test = min(row["created_at"] for row in test)

    print("Latest training date:", latest_train)
    print("Earliest testing date:", earliest_test)
    print("Chronological split valid:", latest_train < earliest_test)
else:
    print("Training or testing dataset is empty.")
