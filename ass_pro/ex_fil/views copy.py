#!/usr/bin/env python3
"""
etl_sales.py
Read region files (CSV or XLSX), transform per business rules,
load into SQLite, and run validation queries printing results.
"""

import os
import pandas as pd
from sqlalchemy import create_engine, text

# ------------------ CONFIG ------------------
DATA_DIR = "data"
REGION_FILES = {
    "A": os.path.join(DATA_DIR, r'C:\Users\prabh\Downloads\order_region_a.xlsx'),  # or .csv
    "B": os.path.join(DATA_DIR, r'C:\Users\prabh\Downloads\order_region_b.xlsx'),
}
SQLITE_DB = os.path.join(DATA_DIR, "sales_data.db")
TABLE_NAME = "sales_data"
# ------------------------------------------------

def read_region_file(path, region_label):
    """Read CSV or Excel into DataFrame, normalize column names, add region."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"file not found: {path}")

    # choose parser by extension
    ext = os.path.splitext(path)[1].lower()
    if ext in [".csv", ".txt"]:
        df = pd.read_csv(path, dtype=str)
    elif ext in [".xls", ".xlsx"]:
        df = pd.read_excel(path, dtype=str)
    else:
        raise ValueError("Unsupported file extension: " + ext)

    # strip column names
    df.columns = [c.strip() for c in df.columns]

    # map common variations to expected names
    col_map = {}
    for c in df.columns:
        k = c.lower().replace(" ", "").replace("_", "")
        if k in ("orderid", "order_id"):
            col_map[c] = "OrderId"
        elif k in ("orderitemid", "order_itemid", "orderitem"):
            col_map[c] = "OrderItemId"
        elif k in ("quantityordered", "quantity", "quantityordered"):
            col_map[c] = "QuantityOrdered"
        elif k in ("itemprice", "price", "item_price"):
            col_map[c] = "ItemPrice"
        elif k in ("promotiondiscount", "promotion_discount", "discount"):
            col_map[c] = "PromotionDiscount"

    df = df.rename(columns=col_map)

    # ensure required cols exist
    req_cols = ["OrderId", "OrderItemId", "QuantityOrdered", "ItemPrice", "PromotionDiscount"]
    for rc in req_cols:
        if rc not in df.columns:
            df[rc] = pd.NA

    # clean whitespace on string identifiers
    df["OrderId"] = df["OrderId"].astype(str).str.strip()
    df["OrderItemId"] = df["OrderItemId"].astype(str).str.strip()
    df["region"] = region_label
    # keep only necessary cols (in case source has extras)
    return df[["OrderId", "OrderItemId", "QuantityOrdered", "ItemPrice", "PromotionDiscount", "region"]]


def to_numeric_safe(series):
    """Convert strings to numeric, removing commas/spaces; empty->NaN."""
    s = series.fillna("").astype(str).str.replace(",", "").str.strip()
    s = s.replace({"": pd.NA, "nan": pd.NA})
    return pd.to_numeric(s, errors="coerce")


def transform_combine(dfs):
    df = pd.concat(dfs, ignore_index=True)

    # numeric conversions
    df["QuantityOrdered"] = to_numeric_safe(df["QuantityOrdered"])
    df["ItemPrice"] = to_numeric_safe(df["ItemPrice"])
    df["PromotionDiscount"] = to_numeric_safe(df["PromotionDiscount"]).fillna(0.0)

    # total_sales and net_sale
    df["total_sales"] = df["QuantityOrdered"] * df["ItemPrice"]
    df["net_sale"] = df["total_sales"] - df["PromotionDiscount"]

    # filter out rows where net_sale <= 0 or total_sales is NaN
    df = df[df["net_sale"] > 0].copy()

    # remove duplicates based on OrderId (keep first)
    before = len(df)
    df = df.drop_duplicates(subset=["OrderId"], keep="first")
    dropped = before - len(df)
    if dropped:
        print(f"Notice: dropped {dropped} duplicate rows based on OrderId (kept first).")

    # final tidy columns and types
    df = df[["OrderId", "OrderItemId", "region", "QuantityOrdered", "ItemPrice", "PromotionDiscount", "total_sales", "net_sale"]]
    # ensure floats
    for c in ["QuantityOrdered", "ItemPrice", "PromotionDiscount", "total_sales", "net_sale"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    return df


def load_to_sqlite(df, db_path=SQLITE_DB, table_name=TABLE_NAME):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    df.to_sql(table_name, engine, if_exists="replace", index=False)
    print(f"Loaded {len(df)} rows into {db_path} -> table '{table_name}'")
    return engine


def run_validations(engine, table_name=TABLE_NAME):
    queries = {
        "total_records": f"SELECT COUNT(*) AS total_records FROM {table_name};",
        "sales_by_region": f"SELECT region, SUM(total_sales) AS total_sales_sum FROM {table_name} GROUP BY region;",
        "avg_net_sale": f"SELECT ROUND(AVG(net_sale), 2) AS avg_net_sale FROM {table_name};",
        "duplicate_orderids": f"SELECT OrderId, COUNT(*) AS cnt FROM {table_name} GROUP BY OrderId HAVING cnt > 1;"
    }
    print("\nValidation results:")
    with engine.connect() as conn:
        for name, q in queries.items():
            print(f"\n-- {name} --\n{q}")
            result = conn.execute(text(q)).fetchall()
            # pretty print
            if result:
                for row in result:
                    print(tuple(row))
            else:
                print("(no rows returned)")
    print("\nValidations complete.")


def main():
    # Read files
    dfs = []
    for rlabel, path in REGION_FILES.items():
        try:
            print(f"Reading region {rlabel} file: {path}")
            dfs.append(read_region_file(path, rlabel))
        except FileNotFoundError as e:
            print("ERROR:", e)
            print("Please download the file from SharePoint to the above path and re-run.")
            return
        except Exception as e:
            print("ERROR reading file:", e)
            return

    # Transform
    print("Transforming data ...")
    transformed = transform_combine(dfs)

    # Save transformed CSV for inspection
    out_csv = os.path.join(DATA_DIR, r'C:\Users\prabh\Downloads\transformed_sales.csv')
    transformed.to_csv(out_csv, index=False)
    print(f"Saved transformed data to: {out_csv}")

    # Load into SQLite
    engine = load_to_sqlite(transformed, SQLITE_DB, TABLE_NAME)

    # Run validations and print results
    run_validations(engine, TABLE_NAME)

    # dispose engine
    engine.dispose()


if __name__ == "__main__":
    main()
