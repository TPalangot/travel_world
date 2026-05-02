import csv
import os
from config import get_server_connection

def export_all_tables_to_csv(output_dir="db_exports"):
    db = get_server_connection()
    cursor = db.cursor()

    cursor.execute("SHOW DATABASES LIKE 'travel_world'")
    if not cursor.fetchone():
        print("Database 'travel_world' does not exist.")
        return

    cursor.execute("USE travel_world")
    cursor.execute("SHOW TABLES")
    tables = [row[0] for row in cursor.fetchall()]

    os.makedirs(output_dir, exist_ok=True)

    for table in tables:
        cursor.execute(f"SELECT * FROM `{table}`")
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]

        csv_path = os.path.join(output_dir, f"{table}.csv")
        with open(csv_path, "w", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(rows)
        print(f"✅ Exported {table} to {csv_path}")

    cursor.close()
    db.close()
    print("✅ All tables exported.")

if __name__ == "__main__":
    export_all_tables_to_csv()