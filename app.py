import os

from flask import Flask, render_template, request, redirect, url_for, flash, session

from google import genai

import mysql.connector

from mysql.connector import Error

from werkzeug.security import generate_password_hash, check_password_hash

from textblob import TextBlob

from datetime import date, timedelta

from config import DB_CONFIG


app = Flask(__name__)

app.secret_key = "mindmate-secret-key"


# =====================================================
# GEMINI AI CONFIGURATION
# =====================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

gemini_client = None

if GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)


# =====================================================
# ADMIN SECRET KEY
# =====================================================

ADMIN_SECRET = os.getenv("MINDMATE_ADMIN_KEY")


# =====================================================
# DATABASE CONNECTION
# =====================================================

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


# =====================================================
# HOME
# =====================================================

@app.route("/")
def home():
    return render_template("index.html")


# =====================================================
# REGISTER
# =====================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        full_name = request.form["full_name"].strip()
        age = request.form["age"]
        gender = request.form["gender"]
        course = request.form["course"].strip()
        year = request.form["year"]
        semester = request.form["semester"]
        college_name = request.form["college_name"].strip()
        phone = request.form["phone"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        # Required field validation

        if (
            not full_name
            or not age
            or not gender
            or not course
            or not year
            or not semester
            or not college_name
            or not email
            or not password
        ):

            flash(
                "Please fill in all required fields.",
                "danger"
            )

            return redirect(url_for("register"))

        # Password validation

        if len(password) < 6:

            flash(
                "Password must contain at least 6 characters.",
                "danger"
            )

            return redirect(url_for("register"))

        # Age validation

        if not age.isdigit() or int(age) < 13 or int(age) > 100:

            flash(
                "Please enter a valid age.",
                "danger"
            )

            return redirect(url_for("register"))

        db = None
        cursor = None

        try:

            db = get_db_connection()
            cursor = db.cursor()

            # Check if email already exists

            cursor.execute(
                """
                SELECT id
                FROM students
                WHERE email = %s
                """,
                (email,)
            )

            existing_student = cursor.fetchone()

            if existing_student:

                flash(
                    "An account with this email already exists.",
                    "warning"
                )

                return redirect(url_for("register"))

            # Hash password

            hashed_password = generate_password_hash(password)

            # Insert student

            cursor.execute(
                """
                INSERT INTO students
                (
                    full_name,
                    age,
                    gender,
                    course,
                    year,
                    semester,
                    college_name,
                    phone,
                    email,
                    password
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    full_name,
                    int(age),
                    gender,
                    course,
                    int(year),
                    int(semester),
                    college_name,
                    phone,
                    email,
                    hashed_password
                )
            )

            db.commit()

            flash(
                "Account created successfully! You can now login.",
                "success"
            )

            return redirect(url_for("login"))

        except Error as err:

            if db:
                db.rollback()

            flash(
                f"Database error: {err}",
                "danger"
            )

            return redirect(url_for("register"))

        finally:

            if cursor:
                cursor.close()

            if db and db.is_connected():
                db.close()

    return render_template("register.html")


# =====================================================
# LOGIN
# =====================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if not email or not password:

            flash(
                "Please enter email and password.",
                "danger"
            )

            return redirect(url_for("login"))

        db = None
        cursor = None

        try:

            db = get_db_connection()
            cursor = db.cursor(dictionary=True)

            cursor.execute(
                """
                SELECT
                    id,
                    full_name,
                    email,
                    password
                FROM students
                WHERE email = %s
                """,
                (email,)
            )

            student = cursor.fetchone()

            # Verify password

            if student and check_password_hash(
                student["password"],
                password
            ):

                session["student_id"] = student["id"]
                session["student_name"] = student["full_name"]
                session["student_email"] = student["email"]

                flash(
                    "Login successful!",
                    "success"
                )

                return redirect(url_for("dashboard"))

            else:

                flash(
                    "Invalid email or password.",
                    "danger"
                )

                return redirect(url_for("login"))

        except Error as err:

            flash(
                f"Database error: {err}",
                "danger"
            )

            return redirect(url_for("login"))

        finally:

            if cursor:
                cursor.close()

            if db and db.is_connected():
                db.close()

    return render_template("login.html")


# =====================================================
# DASHBOARD
# =====================================================

@app.route("/dashboard")
def dashboard():

    if "student_id" not in session:

        flash(
            "Please login first.",
            "warning"
        )

        return redirect(url_for("login"))

    db = None
    cursor = None

    try:

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # =====================================================
        # QUOTE OF THE DAY
        # =====================================================

        cursor.execute(
            """
            SELECT
                quote_text,
                author
            FROM quotes
            ORDER BY RAND()
            LIMIT 1
            """
        )

        quote = cursor.fetchone()

        # =====================================================
        # OVERALL MOOD DATA
        # =====================================================

        cursor.execute(
            """
            SELECT
                mood,
                COUNT(*) AS mood_count
            FROM moods
            WHERE student_id = %s
            GROUP BY mood
            """,
            (session["student_id"],)
        )

        mood_data = cursor.fetchall()

        mood_labels = [
            row["mood"]
            for row in mood_data
        ]

        mood_counts = [
            row["mood_count"]
            for row in mood_data
        ]

        total_moods = sum(mood_counts)

        positive_count = 0
        neutral_count = 0
        negative_count = 0

        for row in mood_data:

            mood_value = row["mood"].lower()

            if mood_value in [
                "happy",
                "very happy",
                "good",
                "positive"
            ]:

                positive_count += row["mood_count"]

            elif mood_value in [
                "sad",
                "very sad",
                "bad",
                "negative"
            ]:

                negative_count += row["mood_count"]

            else:

                neutral_count += row["mood_count"]

        if total_moods > 0:

            positive_percentage = round(
                positive_count / total_moods * 100
            )

            neutral_percentage = round(
                neutral_count / total_moods * 100
            )

            negative_percentage = (
                100
                - positive_percentage
                - neutral_percentage
            )

        else:

            positive_percentage = 0
            neutral_percentage = 0
            negative_percentage = 0

        mood_percentages = {
            "positive": positive_percentage,
            "neutral": neutral_percentage,
            "negative": negative_percentage,
            "total": total_moods
        }

        # =====================================================
        # LAST 7 DAYS MOOD TREND
        # =====================================================

        today = date.today()

        last_7_days = [
            today - timedelta(days=i)
            for i in range(6, -1, -1)
        ]

        cursor.execute(
            """
            SELECT
                mood_date,
                COUNT(*) AS mood_count
            FROM moods
            WHERE student_id = %s
            AND mood_date >= %s
            AND mood_date <= %s
            GROUP BY mood_date
            ORDER BY mood_date ASC
            """,
            (
                session["student_id"],
                last_7_days[0],
                last_7_days[-1]
            )
        )

        weekly_data = cursor.fetchall()

        mood_by_date = {
            row["mood_date"]: row["mood_count"]
            for row in weekly_data
        }

        weekly_labels = [
            day.strftime("%a")
            for day in last_7_days
        ]

        weekly_values = [
            mood_by_date.get(day, 0)
            for day in last_7_days
        ]

        return render_template(
            "dashboard.html",
            student_name=session.get(
                "student_name",
                "Student"
            ),
            quote=quote,
            mood_data=mood_data,
            mood_labels=mood_labels,
            mood_counts=mood_counts,
            mood_percentages=mood_percentages,
            weekly_labels=weekly_labels,
            weekly_values=weekly_values
        )

    except Error as err:

        flash(
            f"Database error: {err}",
            "danger"
        )

        return render_template(
            "dashboard.html",
            student_name=session.get(
                "student_name",
                "Student"
            ),
            quote=None,
            mood_data=[],
            mood_labels=[],
            mood_counts=[],
            mood_percentages={
                "positive": 0,
                "neutral": 0,
                "negative": 0,
                "total": 0
            },
            weekly_labels=[],
            weekly_values=[]
        )

    finally:

        if cursor:
            cursor.close()

        if db and db.is_connected():
            db.close()


# =====================================================
# LOGOUT
# =====================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out successfully.",
        "success"
    )

    return redirect(url_for("home"))


# =====================================================
# DAILY MOOD TRACKER
# =====================================================

@app.route("/mood", methods=["GET", "POST"])
def mood():

    if "student_id" not in session:

        flash(
            "Please login first.",
            "warning"
        )

        return redirect(url_for("login"))

    if request.method == "POST":

        mood_value = request.form["mood"]
        note = request.form["note"].strip()

        if not mood_value:

            flash(
                "Please select your mood.",
                "danger"
            )

            return redirect(url_for("mood"))

        db = None
        cursor = None

        try:

            db = get_db_connection()
            cursor = db.cursor()

            cursor.execute(
                """
                INSERT INTO moods
                (
                    student_id,
                    mood,
                    note,
                    mood_date
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    CURDATE()
                )
                """,
                (
                    session["student_id"],
                    mood_value,
                    note
                )
            )

            db.commit()

            flash(
                "Your mood has been saved successfully! 💜",
                "success"
            )

            return redirect(url_for("mood"))

        except Error as err:

            if db:
                db.rollback()

            flash(
                f"Database error: {err}",
                "danger"
            )

            return redirect(url_for("mood"))

        finally:

            if cursor:
                cursor.close()

            if db and db.is_connected():
                db.close()

    return render_template(
        "mood.html",
        student_name=session.get(
            "student_name",
            "Student"
        )
    )


# =====================================================
# MOOD HISTORY
# =====================================================

@app.route("/mood-history")
def mood_history():

    if "student_id" not in session:

        flash(
            "Please login first.",
            "warning"
        )

        return redirect(url_for("login"))

    db = None
    cursor = None

    try:

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                id,
                mood,
                note,
                mood_date,
                created_at
            FROM moods
            WHERE student_id = %s
            ORDER BY mood_date DESC, created_at DESC
            """,
            (session["student_id"],)
        )

        moods = cursor.fetchall()

        return render_template(
            "mood_history.html",
            moods=moods,
            student_name=session.get(
                "student_name",
                "Student"
            )
        )

    except Error as err:

        flash(
            f"Database error: {err}",
            "danger"
        )

        return redirect(url_for("mood"))

    finally:

        if cursor:
            cursor.close()

        if db and db.is_connected():
            db.close()


# =====================================================
# MOOD ANALYTICS
# =====================================================

@app.route("/mood-analytics")
def mood_analytics():

    if "student_id" not in session:

        flash(
            "Please login first.",
            "warning"
        )

        return redirect(url_for("login"))

    db = None
    cursor = None

    try:

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                mood,
                COUNT(*) AS mood_count
            FROM moods
            WHERE student_id = %s
            GROUP BY mood
            ORDER BY mood_count DESC
            """,
            (session["student_id"],)
        )

        mood_data = cursor.fetchall()

        return render_template(
            "mood_analytics.html",
            mood_data=mood_data,
            student_name=session.get(
                "student_name",
                "Student"
            )
        )

    except Error as err:

        flash(
            f"Database error: {err}",
            "danger"
        )

        return redirect(url_for("mood_history"))

    finally:

        if cursor:
            cursor.close()

        if db and db.is_connected():
            db.close()

  # ============================================================
# JOURNAL
# ============================================================

@app.route("/journal", methods=["GET", "POST"])
def journal():

    if "student_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()

        if not title or not content:
            flash("Please enter both title and journal content.", "danger")
            return redirect(url_for("journal"))

        # Sentiment analysis
        blob = TextBlob(content)
        polarity = blob.sentiment.polarity

        if polarity > 0.1:
            sentiment = "Positive"
        elif polarity < -0.1:
            sentiment = "Negative"
        else:
            sentiment = "Neutral"

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO journals
            (student_id, title, content, sentiment, sentiment_score)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                session["student_id"],
                title,
                content,
                sentiment,
                polarity
            )
        )

        conn.commit()
        cursor.close()
        conn.close()

        flash("Your journal has been saved privately.", "success")
        return redirect(url_for("journal_history"))

    return render_template("journal.html")


# ============================================================
# JOURNAL HISTORY
# ============================================================

@app.route("/journal-history")
def journal_history():

    if "student_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM journals
        WHERE student_id = %s
        ORDER BY created_at DESC
        """,
        (session["student_id"],)
    )

    journals = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "journal_history.html",
        journals=journals
    )


# ============================================================
# RESOURCES
# ============================================================

@app.route("/resources")
def resources():

    if "student_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT id, title, description, category, link
        FROM resources
        ORDER BY id DESC
        """
    )

    resources_data = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "resources.html",
        resources=resources_data
    )


# ============================================================
# ADMIN LOGIN
# ============================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        secret_key = request.form.get("secret_key", "").strip()

        # Check all three fields
        if not email or not password or not secret_key:
            flash(
                "Please enter your email, password and admin secret key.",
                "danger"
            )
            return redirect(url_for("admin_login"))

        # Check admin secret key
        if not ADMIN_SECRET or secret_key != ADMIN_SECRET:
            flash(
                "Invalid admin secret key.",
                "danger"
            )
            return redirect(url_for("admin_login"))

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT *
            FROM admins
            WHERE email = %s
            LIMIT 1
            """,
            (email,)
        )

        admin = cursor.fetchone()

        cursor.close()
        conn.close()

        if not admin:
            flash("Invalid admin email or password.", "danger")
            return redirect(url_for("admin_login"))

        # Check admin account status
        if admin["status"] != "Active":
            flash(
                "This admin account is currently inactive.",
                "danger"
            )
            return redirect(url_for("admin_login"))

        # Check password
        if not check_password_hash(
            admin["password"],
            password
        ):
            flash("Invalid admin email or password.", "danger")
            return redirect(url_for("admin_login"))

        # Admin session
        session.clear()

        session["admin_id"] = admin["id"]
        session["admin_name"] = admin["full_name"]
        session["admin_email"] = admin["email"]

        flash("Admin login successful.", "success")

        return redirect(url_for("admin_dashboard"))

    return render_template("admin_login.html")


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@app.route("/admin/dashboard")
def admin_dashboard():

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Total students
        cursor.execute("SELECT COUNT(*) AS total FROM students")
        total_students = cursor.fetchone()["total"]

        # Total counselors
        # Currently counselor profiles are dummy/static,
        # so we will set this properly when counselor management is created.
        total_counselors = 3

        # Total appointments
        cursor.execute(
            "SELECT COUNT(*) AS total FROM counselor_bookings"
        )
        total_appointments = cursor.fetchone()["total"]

        # Pending appointments
        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM counselor_bookings
            WHERE status = 'Pending'
            """
        )
        pending_appointments = cursor.fetchone()["total"]

        return render_template(
            "admin_dashboard.html",
            admin_name=session.get("admin_name", "Admin"),
            total_students=total_students,
            total_counselors=total_counselors,
            total_appointments=total_appointments,
            pending_appointments=pending_appointments
        )

    except Error as e:
        print("Admin Dashboard Error:", e)

        flash(
            "Unable to load dashboard statistics.",
            "danger"
        )

        return render_template(
            "admin_dashboard.html",
            admin_name=session.get("admin_name", "Admin"),
            total_students=0,
            total_counselors=0,
            total_appointments=0,
            pending_appointments=0
        )

    finally:
        cursor.close()
        conn.close()


# ============================================================
# ADMIN LOGOUT
# ============================================================

@app.route("/admin/logout")
def admin_logout():

    session.pop("admin_id", None)
    session.pop("admin_name", None)
    session.pop("admin_email", None)

    flash("Admin logged out successfully.", "success")

    return redirect(url_for("admin_login"))


# ============================================================
# COUNSELOR PAGE
# ============================================================

@app.route("/counselor")
def counselor():

    if "student_id" not in session:
        return redirect(url_for("login"))

    # Temporary dummy counselor profiles.
    # Later these will come from the counselor/admin system.

    counselors = [
        {
            "name": "Dr. Ananya Sharma",
            "specialization": "Student & Mental Wellness Counselor",
            "availability": "Mon-Fri, 10 AM-2 PM"
        },
        {
            "name": "Dr. Riya Mehta",
            "specialization": "Emotional Wellness Counselor",
            "availability": "Mon-Thu, 2 PM-6 PM"
        },
        {
            "name": "Dr. Neha Patil",
            "specialization": "Academic & Stress Counselor",
            "availability": "Tue-Sat, 11 AM-4 PM"
        }
    ]

    return render_template(
        "counselor.html",
        counselors=counselors
    )


# ============================================================
# MY BOOKINGS
# ============================================================

@app.route("/my_bookings")
def my_bookings():

    if "student_id" not in session:
        return redirect(url_for("login"))

    student_email = session.get("student_email")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM counselor_bookings
        WHERE student_email = %s
        ORDER BY appointment_date DESC, appointment_time DESC
        """,
        (student_email,)
    )

    bookings = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "my_bookings.html",
        bookings=bookings
    )


# ============================================================
# BOOK COUNSELOR
# ============================================================

@app.route("/book_counselor", methods=["POST"])
def book_counselor():

    if "student_id" not in session:
        return redirect(url_for("login"))

    counselor_name = request.form.get(
        "counselor_name",
        ""
    ).strip()

    appointment_date = request.form.get(
        "appointment_date",
        ""
    ).strip()

    appointment_time = request.form.get(
        "appointment_time",
        ""
    ).strip()

    reason = request.form.get(
        "reason",
        ""
    ).strip()

    if not counselor_name or not appointment_date or not appointment_time:
        flash(
            "Please select counselor, date and time.",
            "danger"
        )
        return redirect(url_for("counselor"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO counselor_bookings
        (
            student_email,
            counselor_name,
            appointment_date,
            appointment_time,
            reason,
            status
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            session["student_email"],
            counselor_name,
            appointment_date,
            appointment_time,
            reason,
            "Pending"
        )
    )

    conn.commit()

    cursor.close()
    conn.close()

    flash(
        "Counselor appointment request submitted successfully.",
        "success"
    )

    return redirect(url_for("my_bookings"))


# ============================================================
# SOS SUPPORT
# ============================================================

@app.route("/sos")
def sos():

    if "student_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM emergency_contacts
        WHERE student_email = %s
        ORDER BY created_at DESC
        """,
        (session["student_email"],)
    )

    contacts = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "sos.html",
        contacts=contacts
    )


# ============================================================
# SAVE EMERGENCY CONTACT
# ============================================================

@app.route("/save_emergency_contact", methods=["POST"])
def save_emergency_contact():

    if "student_id" not in session:
        return redirect(url_for("login"))

    contact_name = request.form.get(
        "contact_name",
        ""
    ).strip()

    relationship = request.form.get(
        "relationship",
        ""
    ).strip()

    phone = request.form.get(
        "phone",
        ""
    ).strip()

    if not contact_name or not relationship or not phone:
        flash(
            "Please fill all emergency contact details.",
            "danger"
        )
        return redirect(url_for("sos"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO emergency_contacts
        (
            student_email,
            contact_name,
            relationship,
            phone
        )
        VALUES (%s, %s, %s, %s)
        """,
        (
            session["student_email"],
            contact_name,
            relationship,
            phone
        )
    )

    conn.commit()

    cursor.close()
    conn.close()

    flash(
        "Emergency contact saved successfully.",
        "success"
    )

    return redirect(url_for("sos"))


# ============================================================
# DELETE EMERGENCY CONTACT
# ============================================================

@app.route(
    "/delete_emergency_contact/<int:contact_id>",
    methods=["POST"]
)
def delete_emergency_contact(contact_id):

    if "student_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM emergency_contacts
        WHERE id = %s
        AND student_email = %s
        """,
        (
            contact_id,
            session["student_email"]
        )
    )

    conn.commit()

    cursor.close()
    conn.close()

    flash(
        "Emergency contact deleted successfully.",
        "success"
    )

    return redirect(url_for("sos"))

          # ============================================================
# VIEW JOURNAL
# ============================================================

@app.route("/journal/<int:journal_id>")
def view_journal(journal_id):

    if "student_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM journals
        WHERE id = %s
        AND student_id = %s
        LIMIT 1
        """,
        (
            journal_id,
            session["student_id"]
        )
    )

    journal_data = cursor.fetchone()

    cursor.close()
    conn.close()

    if not journal_data:
        flash("Journal entry not found.", "danger")
        return redirect(url_for("journal_history"))

    return render_template(
        "view_journal.html",
        journal=journal_data
    )


# ============================================================
# EDIT JOURNAL
# ============================================================

@app.route(
    "/journal/<int:journal_id>/edit",
    methods=["GET", "POST"]
)
def edit_journal(journal_id):

    if "student_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get journal
    cursor.execute(
        """
        SELECT *
        FROM journals
        WHERE id = %s
        AND student_id = %s
        LIMIT 1
        """,
        (
            journal_id,
            session["student_id"]
        )
    )

    journal_data = cursor.fetchone()

    if not journal_data:
        cursor.close()
        conn.close()

        flash("Journal entry not found.", "danger")
        return redirect(url_for("journal_history"))

    # Update journal
    if request.method == "POST":

        title = request.form.get(
            "title",
            ""
        ).strip()

        content = request.form.get(
            "content",
            ""
        ).strip()

        if not title or not content:
            cursor.close()
            conn.close()

            flash(
                "Title and journal content are required.",
                "danger"
            )

            return redirect(
                url_for(
                    "edit_journal",
                    journal_id=journal_id
                )
            )

        # Recalculate sentiment
        blob = TextBlob(content)
        polarity = blob.sentiment.polarity

        if polarity > 0.1:
            sentiment = "Positive"
        elif polarity < -0.1:
            sentiment = "Negative"
        else:
            sentiment = "Neutral"

        cursor.execute(
            """
            UPDATE journals
            SET
                title = %s,
                content = %s,
                sentiment = %s,
                sentiment_score = %s
            WHERE id = %s
            AND student_id = %s
            """,
            (
                title,
                content,
                sentiment,
                polarity,
                journal_id,
                session["student_id"]
            )
        )

        conn.commit()

        cursor.close()
        conn.close()

        flash(
            "Journal updated successfully.",
            "success"
        )

        return redirect(
            url_for(
                "view_journal",
                journal_id=journal_id
            )
        )

    cursor.close()
    conn.close()

    return render_template(
        "edit_journal.html",
        journal=journal_data
    )


# ============================================================
# DELETE JOURNAL
# ============================================================

@app.route(
    "/journal/<int:journal_id>/delete",
    methods=["POST"]
)
def delete_journal(journal_id):

    if "student_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM journals
        WHERE id = %s
        AND student_id = %s
        """,
        (
            journal_id,
            session["student_id"]
        )
    )

    conn.commit()

    cursor.close()
    conn.close()

    flash(
        "Journal deleted successfully.",
        "success"
    )

    return redirect(url_for("journal_history"))


# ============================================================
# AI SUPPORT
# ============================================================

@app.route("/chat")
def chat():

    if "student_id" not in session:
        return redirect(url_for("login"))

    student_email = session.get("student_email")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            id,
            user_message,
            ai_reply,
            chat_date,
            chat_time
        FROM ai_chats
        WHERE student_email = %s
        ORDER BY created_at ASC
        """,
        (student_email,)
    )

    chats = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "chat.html",
        chats=chats
    )


# ============================================================
# SEND MESSAGE TO AI
# ============================================================

@app.route(
    "/send_message",
    methods=["POST"]
)
def send_message():

    if "student_id" not in session:
        return redirect(url_for("login"))

    user_message = request.form.get(
        "message",
        ""
    ).strip()

    if not user_message:
        flash(
            "Please enter a message.",
            "danger"
        )
        return redirect(url_for("chat"))

    ai_reply = None

    # --------------------------------------------------------
    # Gemini AI response
    # --------------------------------------------------------

    if gemini_client:

        try:

            prompt = f"""
You are MindMate, a friendly and supportive student
mental wellness assistant.

Talk like a kind senior student.

Use simple English and keep the response around
50-100 words.

Do not diagnose mental health conditions.
Do not recommend medicines or medication.
Do not pretend to be a doctor or counselor.

Give practical, safe and supportive suggestions.

When appropriate, remind the student about MindMate
features such as:
- Mood Tracker
- Private Journal
- Stress Relief
- Book Recommendations
- Inspiring Stories
- Counselor Support

Student message:
{user_message}
"""

            response = gemini_client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt
            )

            ai_reply = response.text.strip()

        except Exception as e:

            print("Gemini Error:", e)

            ai_reply = (
                "I'm having trouble responding right now. "
                "You can try again in a moment or explore "
                "the MindMate resources and counselor support."
            )

    else:

        ai_reply = (
            "MindMate AI is currently unavailable. "
            "Please try again later or explore the "
            "MindMate resources and counselor support."
        )

    # --------------------------------------------------------
    # Save chat in database
    # --------------------------------------------------------

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO ai_chats
        (
            student_email,
            user_message,
            ai_reply,
            chat_date,
            chat_time
        )
        VALUES (%s, %s, %s, CURDATE(), CURTIME())
        """,
        (
            session["student_email"],
            user_message,
            ai_reply
        )
    )

    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for("chat"))


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":
    app.run(debug=True)