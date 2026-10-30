import sqlite3
con = sqlite3.connect('biosense.db')
cur = con.cursor()
cur.execute('PRAGMA table_info(users);')
cols = [c[1] for c in cur.fetchall()]

new_cols = [
    ('full_name', 'VARCHAR(120)'),
    ('institution', 'VARCHAR(150)'),
    ('research_focus', 'VARCHAR(200)'),
    ('bio', 'TEXT'),
    ('auth_provider', "VARCHAR(30) DEFAULT 'local'"),
    ('google_id', 'VARCHAR(100)')
]

for col_name, col_type in new_cols:
    if col_name not in cols:
        print(f"Adding column {col_name}...")
        cur.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type};")

con.commit()
con.close()
print("Migration complete!")
