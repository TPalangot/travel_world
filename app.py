from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from config import get_db_connection
import os
from init_db import init_db

init_db()


app = Flask(__name__)
app.secret_key = "travel_secret_key"

# ---------- FILE UPLOAD CONFIG ----------
STATE_UPLOAD = "static/uploads/states"
PLACE_UPLOAD = "static/uploads/places"
os.makedirs(STATE_UPLOAD, exist_ok=True)
os.makedirs(PLACE_UPLOAD, exist_ok=True)

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
        return jsonify({"message": "Email exists"}), 400
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
        return jsonify({"message": "Login successful"})
    return jsonify({"message": "Invalid credentials"}), 401

# ---------- DASHBOARD ----------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("home"))

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM completed")
    completed_count = cursor.fetchone()[0]
    cursor.close()
    db.close()

    return render_template("dashboard.html", completed_count=completed_count)

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

    return render_template("national.html", states=states)

# ---------- CREATE STATE ----------
@app.route("/create-state", methods=["POST"])
def create_state():
    if "user_id" not in session:
        return redirect(url_for("home"))

    image = request.files["state_image"]
    filename = secure_filename(image.filename)

    save_path = os.path.join(STATE_UPLOAD, filename)
    image.save(save_path)

    db_path = f"uploads/states/{filename}"

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO national_states (state_name, state_description, state_image)
        VALUES (%s,%s,%s)
    """, (
        request.form["state_name"],
        request.form["state_description"],
        db_path
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

    search = request.args.get("search", "")
    place_type = request.args.get("type", "")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM national_states WHERE id=%s", (state_id,))
    state = cursor.fetchone()

    if not state:
        return "State not found", 404

    query = "SELECT * FROM places WHERE state_id=%s"
    params = [state_id]

    if search:
        query += " AND place_name LIKE %s"
        params.append(f"%{search}%")

    if place_type:
        query += " AND type LIKE %s"
        params.append(f"%{place_type}%")

    cursor.execute(query, tuple(params))
    places = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("state.html", state=state, places=places)

# ---------- ADD PLACE ----------
@app.route("/add-place/<int:state_id>", methods=["POST"])
def add_place(state_id):
    if "user_id" not in session:
        return redirect(url_for("home"))

    image = request.files["image"]
    filename = secure_filename(image.filename)
    image.save(os.path.join(PLACE_UPLOAD, filename))
    db_path = f"uploads/places/{filename}"

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("""
        INSERT INTO places
        (state_id, place_name, district, description, image, location_link, type, best_time_from, best_time_to)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        state_id,
        request.form["place_name"],
        request.form["district"],
        request.form["description"],
        db_path,
        request.form["location_link"],
        ",".join(request.form.getlist("type")),
        request.form["best_time_from"],
        request.form["best_time_to"]
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

# ---------- LOGOUT ----------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)
