from config import get_server_connection
from werkzeug.security import generate_password_hash


def init_db():
    db = get_server_connection()
    cursor = db.cursor()

    # ==============================
    # CREATE DATABASE
    # ==============================
    cursor.execute("CREATE DATABASE IF NOT EXISTS travel_world")
    cursor.execute("USE travel_world")

    # ==============================
    # USERS TABLE
    # ==============================
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

    # ==============================
    # DESTINATIONS TABLE (States/Countries)
    # ==============================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS destinations (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        type ENUM('national', 'international') NOT NULL,
        description TEXT NOT NULL,
        image VARCHAR(255) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ==============================
    # PLACES TABLE (Inside Each Destination)
    # ==============================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS places (
        id INT AUTO_INCREMENT PRIMARY KEY,
        destination_id INT NOT NULL,
        name VARCHAR(150) NOT NULL,
        district VARCHAR(150),
        description TEXT,
        map_link VARCHAR(500),
        image VARCHAR(255),
        things_to_do TEXT,
        best_time_from VARCHAR(20),
        best_time_to VARCHAR(20),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (destination_id) REFERENCES destinations(id)
        ON DELETE CASCADE
    )
    """)

    # ==============================
    # VISITED PLACES TABLE (User Tracking)
    # ==============================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS visited_places (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        place_id INT NOT NULL,
        visited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE,
        FOREIGN KEY (place_id) REFERENCES places(id)
        ON DELETE CASCADE,
        UNIQUE(user_id, place_id)
    )
    """)

    # ==============================
    # TRIPS TABLE (User Trip Plans)
    # ==============================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trips (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        title VARCHAR(150),
        trip_type ENUM('national', 'international') NOT NULL,
        estimated_budget VARCHAR(100),
        start_date DATE,
        end_date DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE
    )
    """)

    # Add estimated_budget column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE trips ADD COLUMN estimated_budget VARCHAR(100)")
    except:
        pass  # Column already exists

    # ==============================
    # TRIP DAYS TABLE
    # ==============================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trip_days (
        id INT AUTO_INCREMENT PRIMARY KEY,
        trip_id INT NOT NULL,
        day_number INT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (trip_id) REFERENCES trips(id)
        ON DELETE CASCADE
    )
    """)

    # ==============================
    # TRIP PLACES TABLE (Itinerary Items)
    # ==============================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trip_places (
        id INT AUTO_INCREMENT PRIMARY KEY,
        trip_day_id INT NOT NULL,
        place_id INT,
        place_name VARCHAR(150),
        things_to_do TEXT,
        food TEXT,
        things_to_buy TEXT,
        time_to_spend VARCHAR(50),
        distance_to_next VARCHAR(100),
        time_to_next VARCHAR(100),
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (trip_day_id) REFERENCES trip_days(id)
        ON DELETE CASCADE,
        FOREIGN KEY (place_id) REFERENCES places(id)
        ON DELETE SET NULL
    )
    """)

    # ==============================
    # COMPLETED TRIPS TABLE
    # ==============================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS completed_trips (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        title VARCHAR(150),
        description TEXT,
        visit_date DATE,
        budget VARCHAR(100),
        google_drive_link VARCHAR(500),
        title_image VARCHAR(255),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE
    )
    """)

    # Add google_drive_link and title_image columns if they don't exist
    try:
        cursor.execute("ALTER TABLE completed_trips ADD COLUMN google_drive_link VARCHAR(500)")
    except:
        pass  # Column already exists

    try:
        cursor.execute("ALTER TABLE completed_trips ADD COLUMN title_image VARCHAR(255)")
    except:
        pass  # Column already exists

    # ==============================
    # COMPLETED TRIP PLACES TABLE
    # ==============================
    # First, check if table exists and has the old schema, then drop it
    try:
        cursor.execute("DESC completed_trip_places")
        columns = [col[0] for col in cursor.fetchall()]
        if 'place_id' not in columns:  # Old schema detected
            cursor.execute("DROP TABLE IF EXISTS completed_trip_places")
            print("ℹ️ Dropped old completed_trip_places table")
    except:
        pass  # Table doesn't exist yet
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS completed_trip_places (
        id INT AUTO_INCREMENT PRIMARY KEY,
        completed_trip_id INT NOT NULL,
        place_id INT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (completed_trip_id) REFERENCES completed_trips(id)
        ON DELETE CASCADE,
        FOREIGN KEY (place_id) REFERENCES places(id)
        ON DELETE CASCADE
    )
    """)

    # ==============================
    # PEOPLE MET TABLE
    # ==============================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS people_met (
        id INT AUTO_INCREMENT PRIMARY KEY,
        completed_trip_id INT NOT NULL,
        name VARCHAR(150),
        contact VARCHAR(50),
        email VARCHAR(100),
        image VARCHAR(255),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (completed_trip_id) REFERENCES completed_trips(id)
        ON DELETE CASCADE
    )
    """)

    # Add email column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE people_met ADD COLUMN email VARCHAR(100)")
    except:
        pass  # Column already exists

    # Add image column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE people_met ADD COLUMN image VARCHAR(255)")
    except:
        pass  # Column already exists

    # ==============================
    # DEFAULT ADMIN USER
    # ==============================
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
