from flask import Flask, render_template, request, jsonify, session, redirect, url_for, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from config import get_db_connection
from init_db import init_db
import os
from calendar import monthrange
from datetime import date

# ---------- INIT DB ----------
init_db()

app = Flask(__name__)
app.secret_key = "travel_secret_key"

# ---------- FILE UPLOAD CONFIG ----------
STATE_UPLOAD = "static/uploads/states"
PLACE_UPLOAD = "static/uploads/places"
os.makedirs(STATE_UPLOAD, exist_ok=True)
os.makedirs(PLACE_UPLOAD, exist_ok=True)

# ---------- MONTH MAP ----------
MONTHS = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12
}

DUMMY_YEAR = 2000

# ---------- HELPERS ----------
def is_admin():
    return session.get("role") == "admin"


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session or session.get("role") != "admin":
            abort(403)
        return f(*args, **kwargs)
    return wrapper


# ---------- HOME ----------
@app.route("/")
def home():
    return render_template("login.html")


# ---------- REGISTER ----------
@app.route("/register", methods=["POST"])
def register():
    data = request.json
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("""
            INSERT INTO users (first_name, last_name, contact, email, password)
            VALUES (%s,%s,%s,%s,%s)
        """, (
            data["first_name"],
            data["last_name"],
            data["contact"],
            data["email"],
            generate_password_hash(data["password"])
        ))
        db.commit()
        return jsonify({"message": "Account created"}), 201
    except:
        return jsonify({"message": "Email already exists"}), 400
    finally:
        cursor.close()
        db.close()


# ---------- LOGIN ----------
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE email=%s", (data["email"],))
    user = cursor.fetchone()

    cursor.close()
    db.close()

    if user and check_password_hash(user["password"], data["password"]):
        session["user_id"] = user["id"]
        session["role"] = user["role"]
        session["name"] = user["first_name"]
        return jsonify({"message": "Login successful"})

    return jsonify({"message": "Invalid credentials"}), 401


# ---------- DASHBOARD ----------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("home"))

    return render_template("dashboard.html", role=session["role"])


# ---------- NATIONAL ----------
@app.route("/national")
def national():
    if "user_id" not in session:
        return redirect(url_for("home"))

    search = request.args.get("search", "")
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    if search:
        cursor.execute("""
            SELECT * FROM national_states
            WHERE state_name LIKE %s
            ORDER BY created_at DESC
        """, (f"%{search}%",))
    else:
        cursor.execute("SELECT * FROM national_states ORDER BY created_at DESC")

    states = cursor.fetchall()
    cursor.close()
    db.close()

    return render_template(
        "national.html",
        states=states,
        search=search,
        is_admin=is_admin()
    )


# ---------- CREATE STATE (ADMIN ONLY) ----------
@app.route("/create-state", methods=["POST"])
@admin_required
def create_state():
    image = request.files["state_image"]
    filename = secure_filename(image.filename)
    image.save(os.path.join(STATE_UPLOAD, filename))

    image_path = f"uploads/states/{filename}"

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO national_states (state_name, state_description, state_image)
        VALUES (%s,%s,%s)
    """, (
        request.form["state_name"],
        request.form["state_description"],
        image_path
    ))
    db.commit()
    cursor.close()
    db.close()

    return redirect(url_for("national"))


# ---------- STATE DETAILS ----------
@app.route("/state/<int:state_id>")
def state_details(state_id):
    if "user_id" not in session:
        return redirect(url_for("home"))

    search = request.args.get("search", "").strip()
    selected_types = request.args.getlist("type")
    selected_month = request.args.get("month", "")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM national_states WHERE id=%s", (state_id,))
    state = cursor.fetchone()

    if not state:
        abort(404)

    query = "SELECT * FROM places WHERE state_id=%s"
    params = [state_id]

    if search:
        query += " AND place_name LIKE %s"
        params.append(f"%{search}%")

    if selected_types:
        query += " AND (" + " OR ".join(["FIND_IN_SET(%s, type)"] * len(selected_types)) + ")"
        params.extend(selected_types)

    if selected_month in MONTHS:
        m = MONTHS[selected_month]
        filter_date = date(DUMMY_YEAR, m, 15)
        query += " AND %s BETWEEN best_time_from AND best_time_to"
        params.append(filter_date)

    query += " ORDER BY created_at DESC"

    cursor.execute(query, params)
    places = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "state.html",
        state=state,
        places=places,
        is_admin=is_admin(),
        selected_month=selected_month,
        selected_types=selected_types,
        search=search
    )


# ---------- ADD PLACE (ADMIN ONLY) ----------
@app.route("/add-place/<int:state_id>", methods=["POST"])
@admin_required
def add_place(state_id):
    image = request.files["image"]
    filename = secure_filename(image.filename)
    image.save(os.path.join(PLACE_UPLOAD, filename))
    image_path = f"uploads/places/{filename}"

    types_str = ",".join(request.form.getlist("type"))

    from_month = MONTHS[request.form["best_time_from"]]
    to_month = MONTHS[request.form["best_time_to"]]

    from_date = date(DUMMY_YEAR, from_month, 1)
    to_date = date(DUMMY_YEAR, to_month, monthrange(DUMMY_YEAR, to_month)[1])

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("""
        INSERT INTO places
        (state_id, place_name, district, description, image,
         location_link, type, best_time_from, best_time_to)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        state_id,
        request.form["place_name"],
        request.form["district"],
        request.form["description"],
        image_path,
        request.form["location_link"],
        types_str,
        from_date,
        to_date
    ))

    cursor.execute("""
        UPDATE national_states
        SET places_count = places_count + 1
        WHERE id=%s
    """, (state_id,))

    db.commit()
    cursor.close()
    db.close()

    return redirect(url_for("state_details", state_id=state_id))


# ---------- DELETE PLACE (ADMIN ONLY) ----------
@app.route("/delete-place/<int:place_id>/<int:state_id>", methods=["POST"])
@admin_required
def delete_place(place_id, state_id):
    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("DELETE FROM places WHERE id=%s", (place_id,))
    cursor.execute("""
        UPDATE national_states
        SET places_count = places_count - 1
        WHERE id=%s
    """, (state_id,))

    db.commit()
    cursor.close()
    db.close()

    return redirect(url_for("state_details", state_id=state_id))


# ---------- LOGOUT ----------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


# ---------- ERROR ----------
@app.errorhandler(403)
def forbidden(e):
    return render_template("403.html"), 403



if __name__ == "__main__":
    app.run(debug=True)
