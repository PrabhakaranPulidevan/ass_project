# Django ETL Sales Project

GitHub Repository: [https://github.com/PrabhakaranPulidevan/ass_project](https://github.com/PrabhakaranPulidevan/ass_project)

This Django project reads Excel sales data from multiple regions, transforms it, loads it into a SQLite database, and displays results in a web page.

---

## Project Structure

```
your_project/
│
├── data/                       # Folder to store Excel files and transformed CSV
│   ├── order_region_a.xlsx
│   ├── order_region_b.xlsx
│   └── transformed_sales.csv   # Generated after ETL runs
├── ex_fil/                      # Django app containing views and URLs
├── manage.py
├── db.sqlite3
└── README.md
```

---

## Prerequisites

* Python 3.9+
* pip (Python package manager)
* Django 4.x
* pandas
* SQLAlchemy
* openpyxl (for reading Excel)
* sqlite3 (built-in with Python)

---

## Setup Instructions

1. **Clone the repository**:

```bash
git clone https://github.com/PrabhakaranPulidevan/ass_project
cd ass_project
```

2. **Create and activate a virtual environment**:

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python -m venv venv
source venv/bin/activate
```

3. **Install required Python packages**:

```bash
pip install django pandas sqlalchemy openpyxl
```

4. **Download the Excel data files**:

* Download `order_region_a.xlsx` and `order_region_b.xlsx` and place them inside the `data/` folder.

5. **Ensure the `data/` folder exists**:

```bash
mkdir data
```

---

## Running the Django Project

1. **Apply migrations**:

```bash
python manage.py migrate
```

2. **Run the development server**:

```bash
python manage.py runserver
```

3. **Access the ETL page**:

```
http://127.0.0.1:8000/ass_pro/etl-sales/
```

* View transformed sales data (first 10 rows) and validation results.
* The transformed CSV file will be saved as `data/transformed_sales.csv`.

---

## Notes

* The ETL view handles Excel files and calculates `total_sales` and `net_sale`.
* SQLite is used by default. For another database, edit `views.py`.
* Make sure the `data/` folder exists to store CSV and SQLite files.

---

## License

This project is open-source and free to use or modify.
