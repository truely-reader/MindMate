import getpass

import mysql.connector
from werkzeug.security import generate_password_hash

from config import DB_CONFIG


print("========================================")
print("        MindMate Admin Creation")
print("========================================")

full_name = input("Admin name: ").strip()
email = input("Admin email: ").strip()
password = getpass.getpass("Admin password: ")

if not full_name or not email or not password:
    print("\nAll fields are required.")
    raise SystemExit

try:
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    password_hash = generate_password_hash(password)

    cursor.execute(
        """
        INSERT INTO admins
        (full_name, email, password, status)
        VALUES (%s, %s, %s, %s)
        """,
        (
            full_name,
            email,
            password_hash,
            "Active"
        )
    )

    conn.commit()

    print("\n========================================")
    print("Admin created successfully!")
    print("========================================")
    print(f"Name  : {full_name}")
    print(f"Email : {email}")
    print("Status: Active")
    print("========================================")

except mysql.connector.Error as e:

    print("\nDatabase Error:")
    print(e)

finally:

    try:
        cursor.close()
        conn.close()
    except:
        pass