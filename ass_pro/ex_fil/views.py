from django.http import HttpResponse
import os
import pandas as pd
from sqlalchemy import create_engine, text

# ------------------ CONFIG ------------------
DATA_DIR = "data"

REGION_FILES = {
    "A": os.path.join(DATA_DIR, "order_region_a.xlsx"),
    "B": os.path.join(DATA_DIR, "order_region_b.xlsx"),
}
SQLITE_DB = os.path.join(DATA_DIR, "sales_data.db")
TABLE_NAME = "sales_data"
# ------------------------------------------------

# ------------------ ETL FUNCTIONS ------------------

def read_region_file(path, region_label):
    if not os.path.exists(path):
        raise FileNotFoundError(f"file not found: {path}")

    ext = os.path.splitext(path)[1].lower()
    if ext in [".csv", ".txt"]:
        df = pd.read_csv(path, dtype=str)
    elif ext in [".xls", ".xlsx"]:
        df = pd.read_excel(path, dtype=str)
    else:
        raise ValueError("Unsupported file extension: " + ext)

    df.columns = [c.strip() for c in df.columns]

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

    req_cols = ["OrderId", "OrderItemId", "QuantityOrdered", "ItemPrice", "PromotionDiscount"]
    for rc in req_cols:
        if rc not in df.columns:
            df[rc] = pd.NA

    df["OrderId"] = df["OrderId"].astype(str).str.strip()
    df["OrderItemId"] = df["OrderItemId"].astype(str).str.strip()
    df["region"] = region_label

    return df[["OrderId", "OrderItemId", "QuantityOrdered", "ItemPrice", "PromotionDiscount", "region"]]

def to_numeric_safe(series):
    s = series.fillna("").astype(str).str.replace(",", "").str.strip()
    s = s.replace({"": pd.NA, "nan": pd.NA})
    return pd.to_numeric(s, errors="coerce")

def extract_discount_amount(s):
    """Convert dict-like string to numeric amount."""
    try:
        if pd.isna(s):
            return 0.0
        # Convert string to dict
        d = ast.literal_eval(s)
        return float(d.get("Amount", 0))
    except Exception:
        return 0.0

def transform_combine(dfs):
    df = pd.concat(dfs, ignore_index=True)
    df["QuantityOrdered"] = to_numeric_safe(df["QuantityOrdered"])
    df["ItemPrice"] = to_numeric_safe(df["ItemPrice"])
    df["PromotionDiscount"] = df["PromotionDiscount"].apply(extract_discount_amount)  # <-- fixed
    df["total_sales"] = df["QuantityOrdered"] * df["ItemPrice"]
    df["net_sale"] = df["total_sales"] - df["PromotionDiscount"]
    df = df[df["net_sale"] > 0].copy()
    df = df.drop_duplicates(subset=["OrderId"], keep="first")
    df = df[["OrderId", "OrderItemId", "region", "QuantityOrdered", "ItemPrice", "PromotionDiscount", "total_sales", "net_sale"]]
    for c in ["QuantityOrdered", "ItemPrice", "PromotionDiscount", "total_sales", "net_sale"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    return df


def load_to_sqlite(df, db_path=SQLITE_DB, table_name=TABLE_NAME):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    df.to_sql(table_name, engine, if_exists="replace", index=False)
    return engine

def run_validations(engine, table_name=TABLE_NAME):
    queries = {
        "total_records": f"SELECT COUNT(*) AS total_records FROM {table_name};",
        "sales_by_region": f"SELECT region, SUM(total_sales) AS total_sales_sum FROM {table_name} GROUP BY region;",
        "avg_net_sale": f"SELECT ROUND(AVG(net_sale), 2) AS avg_net_sale FROM {table_name};",
        "duplicate_orderids": f"SELECT OrderId, COUNT(*) AS cnt FROM {table_name} GROUP BY OrderId HAVING cnt > 1;"
    }
    results = {}
    with engine.connect() as conn:
        for name, q in queries.items():
            results[name] = conn.execute(text(q)).fetchall()
    return results

# ------------------ DJANGO VIEW ------------------

def etl_sales_view(request):
    dfs = []
    errors = []

    for rlabel, path in REGION_FILES.items():
        try:
            dfs.append(read_region_file(path, rlabel))
        except FileNotFoundError as e:
            errors.append(str(e))
        except Exception as e:
            errors.append(str(e))

    if errors:
        return HttpResponse("<br>".join(errors))

    transformed = transform_combine(dfs)

    # Ensure data directory exists before saving CSV
    os.makedirs(DATA_DIR, exist_ok=True)
    out_csv = os.path.join(DATA_DIR, "transformed_sales.csv")
    transformed.to_csv(out_csv, index=False)

    engine = load_to_sqlite(transformed, SQLITE_DB, TABLE_NAME)
    validation_results = run_validations(engine, TABLE_NAME)
    engine.dispose()

    html = "<h2>ETL Sales Data Results</h2>"
    html += "<h3>Transformed Data Sample</h3>"
    html += transformed.head(10).to_html(index=False)
    html += "<h3>Validation Results</h3>"

    for name, rows in validation_results.items():
        html += f"<h4>{name}</h4>"
        if rows:
            html += "<table border='1'><tr>"
            for i in range(len(rows[0])):
                html += f"<th>Col{i+1}</th>"
            html += "</tr>"
            for row in rows:
                html += "<tr>" + "".join(f"<td>{v}</td>" for v in row) + "</tr>"
            html += "</table>"
        else:
            html += "(no rows returned)<br>"

    return HttpResponse(html)
