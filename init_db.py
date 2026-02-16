from config import get_server_connection
from werkzeug.security import generate_password_hash

def init_db():
    db = get_server_connection()
    cursor = db.cursor()

    # ---------------- CREATE DATABASE ----------------
    cursor.execute("CREATE DATABASE IF NOT EXISTS travel_world")
    cursor.execute("USE travel_world")

    # ---------------- USERS TABLE ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        first_name VARCHAR(100),
        last_name VARCHAR(100),
        contact VARCHAR(20),
        email VARCHAR(150) UNIQUE,
        password VARCHAR(255),
        role ENUM('user', 'admin') DEFAULT 'user',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ---------------- NATIONAL STATES ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS national_states (
        id INT AUTO_INCREMENT PRIMARY KEY,
        state_name VARCHAR(100),
        state_description TEXT,
        state_image VARCHAR(255),
        places_count INT DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ---------------- PLACES ----------------
    # ---------------- PLACES ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS places (
    id INT AUTO_INCREMENT PRIMARY KEY,
    state_id INT,
    place_name VARCHAR(150),
    district VARCHAR(100),
    description TEXT,
    image VARCHAR(255),
    location_link TEXT,
    type VARCHAR(255),
    best_time_from DATE,
    best_time_to DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (state_id) REFERENCES national_states(id) ON DELETE CASCADE
    )
    """)

    # ---------------- COMPLETED ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS completed (
        id INT AUTO_INCREMENT PRIMARY KEY,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ---------------- CREATE DEFAULT ADMIN ----------------
    admin_email = "admin@123"
    admin_password = generate_password_hash("password")

    cursor.execute("""
        SELECT id FROM users WHERE email = %s
    """, (admin_email,))

    admin_exists = cursor.fetchone()

    if not admin_exists:
        cursor.execute("""
            INSERT INTO users (first_name, last_name, email, password, role)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            "Admin",
            "User",
            admin_email,
            admin_password,
            "admin"
        ))
        print("✅ Admin user created")

    db.commit()
    cursor.close()
    db.close()

    print("✅ Database & tables created successfully")
