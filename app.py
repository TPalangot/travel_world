from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from config import get_db_connection
from init_db import init_db
import pymysql
import os
from flask import jsonify

# ================= MONTH HELPER =================
def is_month_in_range(selected_month, from_month, to_month):
    """Check if selected month falls within the range from_month to to_month"""
    month_order = ["January", "February", "March", "April", "May", "June", 
                   "July", "August", "September", "October", "November", "December"]
    
    try:
        selected_idx = month_order.index(selected_month)
        from_idx = month_order.index(from_month)
        to_idx = month_order.index(to_month)
    except ValueError:
        return False
    
    # If range doesn't wrap around year (e.g., Jan to Mar)
    if from_idx <= to_idx:
        return selected_idx >= from_idx and selected_idx <= to_idx
    # If range wraps around year (e.g., Nov to Feb)
    else:
        return selected_idx >= from_idx or selected_idx <= to_idx

# ================= INIT DATABASE =================
init_db()

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ================= UPLOAD CONFIG =================
UPLOAD_FOLDER = os.path.join("static", "uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# =====================================================
# 🔐 LOGIN REQUIRED DECORATOR
# =====================================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return decorated_function

# =====================================================
# 🔐 ADMIN REQUIRED DECORATOR
# =====================================================
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("role") != "admin":
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# =====================================================
# 🏠 HOME
# =====================================================
@app.route("/")
def home():
    return render_template("login.html")

# =====================================================
# 🔑 LOGIN
# =====================================================
@app.route("/login", methods=["POST"])
def login():
    email = request.form["email"]
    password = request.form["password"]

    db = get_db_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    cursor.close()
    db.close()

    if user and check_password_hash(user["password"], password):
        session["user_id"] = user["id"]
        session["role"] = user["role"]
        return redirect(url_for("dashboard"))

    flash("Invalid email or password")
    return redirect(url_for("home"))

# =====================================================
# 📝 REGISTER
# =====================================================
@app.route("/register", methods=["POST"])
def register():
    first_name = request.form["first_name"]
    last_name = request.form["last_name"]
    contact = request.form["contact"]
    email = request.form["email"]
    password = generate_password_hash(request.form["password"])

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    existing_user = cursor.fetchone()

    if existing_user:
        cursor.close()
        db.close()
        flash("Email already exists!")
        return redirect(url_for("home"))

    cursor.execute("""
        INSERT INTO users (first_name, last_name, contact, email, password)
        VALUES (%s, %s, %s, %s, %s)
    """, (first_name, last_name, contact, email, password))
    db.commit()
    cursor.close()
    db.close()

    flash("Account created successfully! Please login.")
    return redirect(url_for("home"))

# =====================================================
# 🎯 TRIP TYPE
# =====================================================
@app.route("/trip_type")
@login_required
@admin_required
def trip_type():
    return render_template("trip_type.html")

# =====================================================
# 📋 PLANNING PAGE
# =====================================================
@app.route("/planning")
@login_required
def planning():
    trip_type = request.args.get("type", "national")
    
    db = get_db_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)
    
    # Get all destinations of the selected type
    cursor.execute("SELECT id, name FROM destinations WHERE type=%s", (trip_type,))
    destinations = cursor.fetchall()
    
    # Get all places from these destinations
    places = []
    if destinations:
        dest_ids = [d['id'] for d in destinations]
        placeholders = ','.join(['%s'] * len(dest_ids))
        cursor.execute(f"""
            SELECT p.id, p.name, p.description, p.district, p.map_link, p.image, 
                   p.things_to_do, p.best_time_from, p.best_time_to, d.name as destination_name
            FROM places p
            JOIN destinations d ON p.destination_id = d.id
            WHERE p.destination_id IN ({placeholders})
        """, tuple(dest_ids))
        places = cursor.fetchall()
    
    cursor.close()
    db.close()
    
    return render_template(
        "planning.html",
        trip_type=trip_type,
        destinations=destinations,
        places=places,
        user_id=session.get("user_id")
    )

# =====================================================
# 👁 PREVIEW PAGE
# =====================================================
@app.route("/preview")
@login_required
def preview():
    return render_template("preview.html")

# =====================================================
# 📅 UPCOMING TRIPS PAGE
# =====================================================
@app.route("/upcoming")
@login_required
def upcoming():
    user_id = session.get("user_id")
    
    db = get_db_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)
    
    # Get all trips for the logged-in user, ordered by creation date
    cursor.execute("""
        SELECT t.id, t.title, t.trip_type, t.estimated_budget, t.created_at
        FROM trips t
        WHERE t.user_id = %s
        ORDER BY t.created_at DESC
    """, (user_id,))
    
    trips = cursor.fetchall()
    
    # For each trip, fetch its days and places
    trips_with_details = []
    for trip in trips:
        cursor.execute("""
            SELECT td.id as day_id, td.day_number
            FROM trip_days td
            WHERE td.trip_id = %s
            ORDER BY td.day_number ASC
        """, (trip['id'],))
        
        days = cursor.fetchall()
        
        # For each day, get the places
        days_with_places = []
        for day in days:
            cursor.execute("""
                SELECT tp.place_name, tp.things_to_do, tp.food, tp.things_to_buy, tp.time_to_spend, tp.distance_to_next, tp.time_to_next, tp.notes
                FROM trip_places tp
                WHERE tp.trip_day_id = %s
            """, (day['day_id'],))
            
            places = cursor.fetchall()
            days_with_places.append({
                'day_number': day['day_number'],
                'places': places
            })
        
        trip['days'] = days_with_places
        trips_with_details.append(trip)
    
    cursor.close()
    db.close()
    
    return render_template("upcoming.html", trips=trips_with_details, user_id=user_id)

# =====================================================
# 📊 DASHBOARD
# =====================================================
@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session.get("user_id")
    db = get_db_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)
    # Fetch current user's first name
    cursor.execute("SELECT first_name FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    user_name = user["first_name"] if user else "User"
    # Fetch all users for admin dashboard
    cursor.execute("SELECT id, first_name, last_name, email, role FROM users")
    users = cursor.fetchall()
    cursor.close()
    db.close()

    return render_template(
        "dashboard.html",
        role=session.get("role"),
        users=users,
        user_name=user_name  # Pass user_name to template
    )

# =====================================================
# 🌍 STATE OR COUNTRY PAGE
# =====================================================
@app.route("/stateorcountry")
@login_required
def stateorcountry():
    travel_type = request.args.get("type", "national")
    search = request.args.get("search", "")

    db = get_db_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    if search:
        cursor.execute("""
            SELECT * FROM destinations
            WHERE type=%s AND name LIKE %s
        """, (travel_type, f"%{search}%"))
    else:
        cursor.execute("""
            SELECT * FROM destinations
            WHERE type=%s
        """, (travel_type,))

    destinations = cursor.fetchall()  # <-- This is a LIST of destinations
    cursor.close()
    db.close()

    return render_template(
        "stateorcountry.html",
        destinations=destinations,  # <-- You pass "destinations" not "destination"
        type=travel_type,
        role=session.get("role")
    )


# =====================================================
# ➕ CREATE DESTINATION (ADMIN ONLY)
# =====================================================
@app.route("/create", methods=["POST"])
@login_required
@admin_required
def create_destination():
    name = request.form["name"]
    description = request.form["description"]
    travel_type = request.args.get("type", "national")
    image = request.files.get("image")

    filename = ""
    if image and image.filename != "":
        filename = secure_filename(image.filename)
        image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO destinations (name, type, description, image)
        VALUES (%s, %s, %s, %s)
    """, (name, travel_type, description, filename))
    db.commit()
    cursor.close()
    db.close()

    flash("Destination created successfully!")
    return redirect(url_for("stateorcountry", type=travel_type))

# =====================================================
# 📍 PLACES PAGE
# =====================================================
@app.route("/places/<int:destination_id>")
@login_required
def places(destination_id):
    db = get_db_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    # Get destination details
    cursor.execute("SELECT * FROM destinations WHERE id=%s", (destination_id,))
    destination = cursor.fetchone()

    # Get filter parameters
    search = request.args.get("search", "").strip()
    month = request.args.get("month", "").strip()
    activities = request.args.getlist("activity")

    # Initial query - get all places for this destination
    cursor.execute("SELECT * FROM places WHERE destination_id=%s", (destination_id,))
    places = cursor.fetchall()

    # Filter by search
    if search:
        places = [p for p in places if search.lower() in p['name'].lower() or 
                 search.lower() in p.get('description', '').lower() or 
                 search.lower() in p.get('district', '').lower()]

    # Filter by month range
    if month:
        places = [p for p in places if is_month_in_range(month, p['best_time_from'], p['best_time_to'])]

    # Filter by activities if selected
    if activities:
        filtered_places = []
        for place in places:
            things = place.get('things_to_do', '')
            if any(activity.lower() in things.lower() for activity in activities):
                filtered_places.append(place)
        places = filtered_places

    # --- Fetch completed place IDs for this user ---
    user_id = session.get("user_id")
    cursor.execute("""
        SELECT DISTINCT ctp.place_id
        FROM completed_trips ct
        JOIN completed_trip_places ctp ON ct.id = ctp.completed_trip_id
        WHERE ct.user_id = %s
    """, (user_id,))
    completed_place_ids = [row['place_id'] for row in cursor.fetchall()]

    cursor.close()
    db.close()

    # --- Sort places: completed first ---
    completed_places = [p for p in places if p['id'] in completed_place_ids]
    not_completed_places = [p for p in places if p['id'] not in completed_place_ids]
    sorted_places = completed_places + not_completed_places

    return render_template(
        "places.html",
        destination=destination,
        places=sorted_places,  # <-- Sorted list
        role=session.get("role"),
        completed_place_ids=completed_place_ids  # <-- Pass to template
    )

# =====================================================
# ➕ ADD PLACE (ADMIN ONLY)
# =====================================================
@app.route("/add_place/<int:destination_id>", methods=["POST"])
@login_required
@admin_required
def add_place(destination_id):
    name = request.form["name"]
    district = request.form["district"]
    description = request.form["description"]
    map_link = request.form.get("map_link", "")
    best_from = request.form["best_from"]
    best_to = request.form["best_to"]
    image = request.files.get("image")

    # Collect selected "Things To Do" from checkboxes
    things_to_do_list = request.form.getlist("things_to_do")
    things_to_do = ", ".join(things_to_do_list) if things_to_do_list else ""

    filename = ""
    if image and image.filename != "":
        filename = secure_filename(image.filename)
        image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO places (destination_id, name, district, description, map_link, things_to_do, best_time_from, best_time_to, image)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (destination_id, name, district, description, map_link, things_to_do, best_from, best_to, filename))
    db.commit()
    cursor.close()
    db.close()

    flash("Place added successfully!")
    return redirect(url_for("places", destination_id=destination_id))

# =====================================================
# 🗑 DELETE DESTINATION / USER
# =====================================================
@app.route("/delete_destination/<int:id>")
@login_required
@admin_required
def delete_destination(id):
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM destinations WHERE id=%s", (id,))
    db.commit()
    cursor.close()
    db.close()
    flash("Destination deleted successfully!")
    return redirect(request.referrer)

@app.route("/delete_place/<int:place_id>/<int:destination_id>")
@login_required
@admin_required
def delete_place(place_id, destination_id):
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM places WHERE id=%s", (place_id,))
    db.commit()
    cursor.close()
    db.close()
    flash("Place deleted successfully!")
    return redirect(url_for("places", destination_id=destination_id))

@app.route("/delete_user/<int:user_id>")
@login_required
@admin_required
def delete_user(user_id):
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
    db.commit()
    cursor.close()
    db.close()
    flash("User deleted successfully")
    return redirect(url_for("dashboard"))

# =====================================================
# � SAVE TRIP
# =====================================================
@app.route("/save_trip", methods=["POST"])
@login_required
def save_trip():
    import json
    
    data = request.get_json()
    user_id = session.get("user_id")
    trip_name = data.get("trip_name", "My Trip")
    trip_type = data.get("trip_type", "national")
    estimated_budget = data.get("estimated_budget", "")
    days_data = data.get("days", [])
    
    db = get_db_connection()
    cursor = db.cursor()
    
    try:
        # Insert trip with estimated_budget
        cursor.execute("""
            INSERT INTO trips (user_id, title, trip_type, estimated_budget, created_at)
            VALUES (%s, %s, %s, %s, NOW())
        """, (user_id, trip_name, trip_type, estimated_budget))
        db.commit()
        
        trip_id = cursor.lastrowid
        
        # Insert trip days and places
        for day_data in days_data:
            day_num = day_data.get("day")
            places_list = day_data.get("places", [])
            
            cursor.execute("""
                INSERT INTO trip_days (trip_id, day_number)
                VALUES (%s, %s)
            """, (trip_id, day_num))
            db.commit()
            
            trip_day_id = cursor.lastrowid
            
            # Insert places for this day
            for place in places_list:
                cursor.execute("""
                    INSERT INTO trip_places (trip_day_id, place_name, things_to_do, food, things_to_buy, time_to_spend, distance_to_next, time_to_next, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    trip_day_id,
                    place.get("name"),
                    place.get("thingsToDo"),
                    place.get("food"),
                    place.get("thingsToBuy"),
                    place.get("timeToSpend"),
                    place.get("distanceToNext"),
                    place.get("timeToNext"),
                    place.get("notes")
                ))
                db.commit()
        
        cursor.close()
        db.close()
        
        return {"success": True, "message": "Trip saved successfully!", "trip_id": trip_id}
    
    except Exception as e:
        cursor.close()
        db.close()
        return {"success": False, "message": str(e)}, 500

# =====================================================# 🗑 DELETE TRIP
# =====================================================
@app.route("/delete_trip", methods=["POST"])
@login_required
def delete_trip():
    data = request.get_json()
    trip_id = data.get("trip_id")
    user_id = session.get("user_id")
    
    db = get_db_connection()
    cursor = db.cursor()
    
    try:
        # Verify trip belongs to user before deleting
        cursor.execute("SELECT user_id FROM trips WHERE id=%s", (trip_id,))
        trip = cursor.fetchone()
        
        if not trip or trip[0] != user_id:
            return {"success": False, "message": "Unauthorized"}, 403
        
        # Delete trip (cascade deletes trip_days and trip_places)
        cursor.execute("DELETE FROM trips WHERE id=%s", (trip_id,))
        db.commit()
        cursor.close()
        db.close()
        
        return {"success": True, "message": "Trip deleted successfully!"}
    
    except Exception as e:
        cursor.close()
        db.close()
        return {"success": False, "message": str(e)}, 500

# =====================================================# �🚪 LOGOUT
# =====================================================
# =====================================================
# ✅ COMPLETED TRIP PAGE
# =====================================================
@app.route("/completed_trip")
@login_required
def completed_trip():
    db = get_db_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    # Show all trips for admin, only user's trips for user
    if session.get("role") == "admin":
        cursor.execute("""
            SELECT p.id, p.name, d.name as destination_name
            FROM places p
            JOIN destinations d ON p.destination_id = d.id
            ORDER BY d.name, p.name
        """)
        places = cursor.fetchall()
    else:
        user_id = session.get("user_id")
        cursor.execute("""
            SELECT p.id, p.name, d.name as destination_name
            FROM places p
            JOIN destinations d ON p.destination_id = d.id
            WHERE p.id IN (
                SELECT ctp.place_id
                FROM completed_trips ct
                JOIN completed_trip_places ctp ON ct.id = ctp.completed_trip_id
                WHERE ct.user_id = %s
            )
            ORDER BY d.name, p.name
        """, (user_id,))
        places = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("completed_trip.html", places=places)

# ================= GET COMPLETED TRIPS (AJAX) =================
@app.route("/get_completed_trips")
@login_required
def get_completed_trips():
    db = get_db_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    # Show all completed trips to everyone
    cursor.execute("""
        SELECT * FROM completed_trips 
        ORDER BY visit_date DESC, created_at DESC
    """)
    trips = cursor.fetchall()

    # For each trip, get places and people met
    trips_with_details = []
    for trip in trips:
        cursor.execute("""
            SELECT ctp.id, p.name, d.name as destination_name
            FROM completed_trip_places ctp
            JOIN places p ON ctp.place_id = p.id
            JOIN destinations d ON p.destination_id = d.id
            WHERE ctp.completed_trip_id = %s
        """, (trip['id'],))
        places = cursor.fetchall()

        cursor.execute("""
            SELECT name, contact, email, image FROM people_met 
            WHERE completed_trip_id = %s
        """, (trip['id'],))
        people = cursor.fetchall()

        trip['places'] = places
        trip['people'] = people
        trips_with_details.append(trip)

    cursor.close()
    db.close()

    return {"trips": trips_with_details}

# =====================================================
# 💾 SAVE COMPLETED TRIP
# =====================================================
@app.route("/save_completed_trip", methods=["POST"])
@login_required
def save_completed_trip():
    import json
    
    user_id = session.get("user_id")
    trip_title = request.form.get("title")
    experience = request.form.get("experience")
    visit_date = request.form.get("visit_date")
    budget = request.form.get("budget")
    google_drive_link = request.form.get("google_drive_link")
    places = request.form.getlist("places")
    title_image = request.files.get("title_image")
    
    # Handle title image upload
    title_image_filename = ""
    if title_image and title_image.filename != "":
        title_image_filename = secure_filename(f"trip_cover_{int(visit_date.replace('-', ''))}.{title_image.filename.split('.')[-1]}")
        title_image.save(os.path.join(app.config["UPLOAD_FOLDER"], title_image_filename))
    
    db = get_db_connection()
    cursor = db.cursor()
    
    try:
        # Insert completed trip with experience, google drive link, and title image
        cursor.execute("""
            INSERT INTO completed_trips (user_id, title, description, visit_date, budget, google_drive_link, title_image)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (user_id, trip_title, experience, visit_date, budget, google_drive_link, title_image_filename))
        db.commit()
        
        trip_id = cursor.lastrowid
        
        # Insert places (using place_id from form)
        for place_id in places:
            if place_id:  # Only insert non-empty place IDs
                cursor.execute("""
                    INSERT INTO completed_trip_places (completed_trip_id, place_id)
                    VALUES (%s, %s)
                """, (trip_id, int(place_id)))
                db.commit()
        
        # Insert people met with image handling
        people_count = int(request.form.get("people_count", 0))
        for i in range(people_count):
            name = request.form.get(f"people_name_{i}")
            contact = request.form.get(f"people_contact_{i}")
            email = request.form.get(f"people_email_{i}")
            image = request.files.get(f"people_image_{i}")
            
            # Only insert if name is provided
            if name:
                filename = ""
                if image and image.filename != "":
                    filename = secure_filename(f"person_{trip_id}_{i}_{image.filename}")
                    image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                
                cursor.execute("""
                    INSERT INTO people_met (completed_trip_id, name, contact, email, image)
                    VALUES (%s, %s, %s, %s, %s)
                """, (trip_id, name, contact, email, filename))
                db.commit()
        
        cursor.close()
        db.close()
        
        return {"success": True, "message": "Completed trip saved successfully!", "trip_id": trip_id}
    
    except Exception as e:
        cursor.close()
        db.close()
        return {"success": False, "message": str(e)}, 500

# =====================================================
# 🗑 DELETE COMPLETED TRIP
# =====================================================
@app.route("/delete_completed_trip", methods=["POST"])
@login_required
def delete_completed_trip():
    data = request.get_json()
    trip_id = data.get("trip_id")
    user_id = session.get("user_id")
    
    db = get_db_connection()
    cursor = db.cursor()
    
    try:
        # Verify trip belongs to user
        cursor.execute("SELECT user_id FROM completed_trips WHERE id=%s", (trip_id,))
        trip = cursor.fetchone()
        
        if not trip or trip[0] != user_id:
            return {"success": False, "message": "Unauthorized"}, 403
        
        # Delete trip (cascades delete places and people)
        cursor.execute("DELETE FROM completed_trips WHERE id=%s", (trip_id,))
        db.commit()
        cursor.close()
        db.close()
        
        return {"success": True, "message": "Trip deleted successfully!"}
    
    except Exception as e:
        cursor.close()
        db.close()
        return {"success": False, "message": str(e)}, 500

# =====================================================
# 🚪 LOGOUT
# =====================================================
@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("home"))

# =====================================================
# 📋 PLAN COMPLETED PAGE
# =====================================================
@app.route("/plan_completed")
@login_required
def plan_completed():
    db = get_db_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    # Get all completed trips
    cursor.execute("""
        SELECT * FROM completed_trips 
        ORDER BY visit_date DESC, created_at DESC
    """)
    trips = cursor.fetchall()

    # Get all unique years from visit_date
    cursor.execute("""
        SELECT DISTINCT YEAR(visit_date) as year
        FROM completed_trips
        WHERE visit_date IS NOT NULL
        ORDER BY year ASC
    """)
    years = [row['year'] for row in cursor.fetchall() if row['year']]

    trips_with_details = []
    for trip in trips:
        cursor.execute("""
            SELECT ctp.id, p.name, d.name as destination_name
            FROM completed_trip_places ctp
            JOIN places p ON ctp.place_id = p.id
            JOIN destinations d ON p.destination_id = d.id
            WHERE ctp.completed_trip_id = %s
        """, (trip['id'],))
        places = cursor.fetchall()
        trip['places'] = places
        trip.pop('budget', None)
        trip.pop('people', None)
        trips_with_details.append(trip)
    cursor.close()
    db.close()
    return render_template("plan_completed.html", trips=trips_with_details, years=years)

@app.route("/gallery.html")
@login_required
def gallery():
    return render_template("gallery.html")

@app.route("/edit_place/<int:place_id>", methods=["POST"])
@login_required
@admin_required
def edit_place(place_id):
    name = request.form["name"]
    district = request.form["district"]
    description = request.form["description"]
    map_link = request.form.get("map_link", "")
    best_from = request.form["best_from"]
    best_to = request.form["best_to"]
    things_to_do = request.form.get("things_to_do", "")
    image = request.files.get("image")

    db = get_db_connection()
    cursor = db.cursor()

    # If a new image is uploaded, update it
    if image and image.filename != "":
        filename = secure_filename(image.filename)
        image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        cursor.execute("""
            UPDATE places SET name=%s, district=%s, description=%s, map_link=%s, things_to_do=%s, best_time_from=%s, best_time_to=%s, image=%s
            WHERE id=%s
        """, (name, district, description, map_link, things_to_do, best_from, best_to, filename, place_id))
    else:
        cursor.execute("""
            UPDATE places SET name=%s, district=%s, description=%s, map_link=%s, things_to_do=%s, best_time_from=%s, best_time_to=%s
            WHERE id=%s
        """, (name, district, description, map_link, things_to_do, best_from, best_to, place_id))

    db.commit()
    cursor.close()
    db.close()
    flash("Place updated successfully!")
    # Redirect back to the places page for the destination
    destination_id = request.args.get("destination_id")
    if not destination_id:
        # Get destination_id from DB if not provided
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT destination_id FROM places WHERE id=%s", (place_id,))
        row = cursor.fetchone()
        destination_id = row[0] if row else ""
        cursor.close()
        db.close()
    return redirect(url_for("places", destination_id=destination_id))

@app.route("/get_place/<int:place_id>")
@login_required
@admin_required
def get_place(place_id):
    db = get_db_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM places WHERE id=%s", (place_id,))
    place = cursor.fetchone()
    cursor.close()
    db.close()
    if not place:
        return jsonify({}), 404
    return jsonify(place)



# =====================================================
# ▶ RUN
# =====================================================
if __name__ == "__main__":
    app.run(debug=True)

@app.route("/gallery.html")
@login_required
def gallery():
    return render_template("gallery.html")

# =====================================================
# 🚫 ERROR HANDLER
# =====================================================
@app.errorhandler(403)
def forbidden(e):
    return "<h1>403 - Access Denied</h1><p>You are not allowed to access this page.</p>", 403

