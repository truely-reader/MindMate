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
# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():
    return render_template("index.html")


# =========================================================
# REGISTER
# =========================================================

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


# =========================================================
# LOGIN
# =========================================================

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


# =========================================================
# DASHBOARD
# =========================================================

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


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out successfully.",
        "success"
    )

    return redirect(url_for("home"))


# =========================================================
# DAILY MOOD TRACKER
# =========================================================

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


# =========================================================
# MOOD HISTORY
# =========================================================

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


# =========================================================
# MOOD ANALYTICS
# =========================================================

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


# =========================================================
# JOURNAL
# =========================================================

@app.route("/journal", methods=["GET", "POST"])
def journal():

    if "student_id" not in session:

        flash(
            "Please login first.",
            "warning"
        )

        return redirect(url_for("login"))

    if request.method == "POST":

        title = request.form["title"].strip()
        content = request.form["content"].strip()

        # Basic validation
        if not content:

            flash(
                "Please write something in your journal.",
                "danger"
            )

            return redirect(url_for("journal"))

        # =====================================================
        # TEXTBLOB SENTIMENT ANALYSIS
        # =====================================================

        analysis = TextBlob(content)

        sentiment_score = round(
            analysis.sentiment.polarity,
            2
        )

        if sentiment_score > 0.1:

            sentiment = "Positive"

        elif sentiment_score < -0.1:

            sentiment = "Negative"

        else:

            sentiment = "Neutral"

        # =====================================================
        # DATABASE
        # =====================================================

        db = None
        cursor = None

        try:

            db = get_db_connection()
            cursor = db.cursor()

            cursor.execute(
                """
                INSERT INTO journals
                (
                    student_id,
                    title,
                    content,
                    sentiment,
                    sentiment_score
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    session["student_id"],
                    title,
                    content,
                    sentiment,
                    sentiment_score
                )
            )

            db.commit()

            flash(
                "Your journal entry has been saved successfully! 💜",
                "success"
            )

            return redirect(url_for("journal"))

        except Error as err:

            if db:
                db.rollback()

            flash(
                f"Database error: {err}",
                "danger"
            )

            return redirect(url_for("journal"))

        finally:

            if cursor:
                cursor.close()

            if db and db.is_connected():
                db.close()

    return render_template(
        "journal.html",
        student_name=session.get(
            "student_name",
            "Student"
        )
    )


# =========================================================
# JOURNAL HISTORY
# =========================================================

@app.route("/journal-history")
def journal_history():

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
                title,
                content,
                sentiment,
                sentiment_score,
                created_at
            FROM journals
            WHERE student_id = %s
            ORDER BY created_at DESC
            """,
            (session["student_id"],)
        )

        journals = cursor.fetchall()

        return render_template(
            "journal_history.html",
            journals=journals,
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

        return redirect(url_for("journal"))

    finally:

        if cursor:
            cursor.close()

        if db and db.is_connected():
            db.close()


# =========================================================
# RESOURCES
# =========================================================

@app.route("/resources")
def resources():

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
                title,
                description,
                category,
                link
            FROM resources
            ORDER BY id ASC
            """
        )

        resources = cursor.fetchall()

        return render_template(
            "resources.html",
            resources=resources,
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

        return redirect(url_for("dashboard"))

    finally:

        if cursor:
            cursor.close()

        if db and db.is_connected():
            db.close()

@app.route('/counselor')
def counselor():
    return render_template('counselor.html')

# =========================================================
# COUNSELOR - MY BOOKINGS
# =========================================================

@app.route('/my_bookings')
def my_bookings():

    if 'student_email' not in session:
        return redirect(url_for('login'))

    student_email = session['student_email']

    db = None
    cursor = None

    try:

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                id,
                counselor_name,
                appointment_date,
                appointment_time,
                reason,
                status,
                created_at
            FROM counselor_bookings
            WHERE student_email = %s
            ORDER BY appointment_date DESC, appointment_time DESC
        """, (student_email,))

        bookings = cursor.fetchall()

        return render_template(
            'my_bookings.html',
            bookings=bookings
        )

    except Error as err:

        print("MY BOOKINGS ERROR:", err)

        flash(
            "Unable to load your bookings right now.",
            "danger"
        )

        return redirect(url_for('counselor'))

    finally:

        if cursor:
            cursor.close()

        if db and db.is_connected():
            db.close()


# =========================================================
# COUNSELOR - BOOK APPOINTMENT
# =========================================================

@app.route('/book_counselor', methods=['POST'])
def book_counselor():

    if 'student_email' not in session:
        return redirect(url_for('login'))

    student_email = session['student_email']

    counselor_name = request.form.get('counselor_name')
    appointment_date = request.form.get('appointment_date')
    appointment_time = request.form.get('appointment_time')
    reason = request.form.get('reason')

    # Basic validation
    if not counselor_name or not appointment_date or not appointment_time:

        flash(
            "Please fill all required appointment details.",
            "danger"
        )

        return redirect(url_for('counselor'))

    db = None
    cursor = None

    try:

        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute("""
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
        """, (
            student_email,
            counselor_name,
            appointment_date,
            appointment_time,
            reason or '',
            'Pending'
        ))

        db.commit()

        flash(
            "Your appointment request has been submitted successfully.",
            "success"
        )

    except Error as err:

        print("COUNSELOR BOOKING ERROR:", err)

        if db:
            db.rollback()

        flash(
            "Something went wrong while submitting your appointment request.",
            "danger"
        )

    finally:

        if cursor:
            cursor.close()

        if db and db.is_connected():
            db.close()

    return redirect(url_for('counselor'))

#----------SOS HELP-----------------#

@app.route('/sos')
def sos():

    if 'student_id' not in session:
        return redirect(url_for('login'))

    student_email = session.get('student_email')

    db = None
    cursor = None
    contacts = []

    try:

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                id,
                contact_name,
                relationship,
                phone
            FROM emergency_contacts
            WHERE student_email = %s
            ORDER BY id DESC
        """, (student_email,))

        contacts = cursor.fetchall()

    except Error as err:

        print("SOS CONTACT ERROR:", err)

        flash(
            "Unable to load your trusted contacts right now.",
            "danger"
        )

    finally:

        if cursor:
            cursor.close()

        if db and db.is_connected():
            db.close()

    return render_template(
        'sos.html',
        contacts=contacts
    )

@app.route('/save_emergency_contact', methods=['POST'])
def save_emergency_contact():

    if 'student_email' not in session:
        return redirect(url_for('login'))

    student_email = session['student_email']

    contact_name = request.form.get('contact_name', '').strip()
    relationship = request.form.get('relationship', '').strip()
    phone = request.form.get('phone', '').strip()

    if not contact_name or not relationship or not phone:
        flash(
            "Please fill all emergency contact details.",
            "danger"
        )
        return redirect(url_for('sos'))

    db = None
    cursor = None

    try:
        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO emergency_contacts
            (
                student_email,
                contact_name,
                relationship,
                phone
            )
            VALUES (%s, %s, %s, %s)
        """, (
            student_email,
            contact_name,
            relationship,
            phone
        ))

        db.commit()

        flash(
            "Trusted contact saved successfully.",
            "success"
        )

    except Error as err:

        print("EMERGENCY CONTACT ERROR:", err)

        if db:
            db.rollback()

        flash(
            "Unable to save the contact right now.",
            "danger"
        )

    finally:

        if cursor:
            cursor.close()

        if db and db.is_connected():
            db.close()

    return redirect(url_for('sos'))


@app.route('/delete_emergency_contact/<int:contact_id>', methods=['POST'])
def delete_emergency_contact(contact_id):

    if 'student_email' not in session:
        return redirect(url_for('login'))

    student_email = session['student_email']

    db = None
    cursor = None

    try:

        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute("""
            DELETE FROM emergency_contacts
            WHERE id = %s
            AND student_email = %s
        """, (
            contact_id,
            student_email
        ))

        db.commit()

        flash(
            "Trusted contact removed successfully.",
            "success"
        )

    except Error as err:

        print("DELETE EMERGENCY CONTACT ERROR:", err)

        if db:
            db.rollback()

        flash(
            "Unable to remove the contact right now.",
            "danger"
        )

    finally:

        if cursor:
            cursor.close()

        if db and db.is_connected():
            db.close()

    return redirect(url_for('sos'))

# =========================================================
# VIEW JOURNAL
# =========================================================

@app.route("/journal/<int:journal_id>")
def view_journal(journal_id):

    # FIXED:
    # Previously this condition was accidentally reversed.
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
                title,
                content,
                sentiment,
                sentiment_score,
                created_at
            FROM journals
            WHERE id = %s
            AND student_id = %s
            """,
            (
                journal_id,
                session["student_id"]
            )
        )

        journal_entry = cursor.fetchone()

        if not journal_entry:

            flash(
                "Journal entry not found.",
                "danger"
            )

            return redirect(
                url_for("journal_history")
            )

        return render_template(
            "view_journal.html",
            journal=journal_entry,
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

        return redirect(
            url_for("journal_history")
        )

    finally:

        if cursor:
            cursor.close()

        if db and db.is_connected():
            db.close()


# =========================================================
# EDIT JOURNAL
# =========================================================

@app.route(
    "/journal/<int:journal_id>/edit",
    methods=["GET", "POST"]
)
def edit_journal(journal_id):

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

        # Get existing journal
        cursor.execute(
            """
            SELECT
                id,
                title,
                content,
                sentiment,
                sentiment_score,
                created_at
            FROM journals
            WHERE id = %s
            AND student_id = %s
            """,
            (
                journal_id,
                session["student_id"]
            )
        )

        journal_entry = cursor.fetchone()

        if not journal_entry:

            flash(
                "Journal entry not found.",
                "danger"
            )

            return redirect(
                url_for("journal_history")
            )

        # =====================================================
        # UPDATE JOURNAL
        # =====================================================

        if request.method == "POST":

            title = request.form["title"].strip()
            content = request.form["content"].strip()

            if not content:

                flash(
                    "Journal content cannot be empty.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "edit_journal",
                        journal_id=journal_id
                    )
                )

            # =================================================
            # TEXTBLOB SENTIMENT ANALYSIS
            # =================================================

            analysis = TextBlob(content)

            sentiment_score = round(
                analysis.sentiment.polarity,
                2
            )

            if sentiment_score > 0.1:

                sentiment = "Positive"

            elif sentiment_score < -0.1:

                sentiment = "Negative"

            else:

                sentiment = "Neutral"

            # =================================================
            # UPDATE DATABASE
            # =================================================

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
                    sentiment_score,
                    journal_id,
                    session["student_id"]
                )
            )

            db.commit()

            flash(
                "Your journal entry has been updated successfully! 💜",
                "success"
            )

            return redirect(
                url_for(
                    "view_journal",
                    journal_id=journal_id
                )
            )

        return render_template(
            "edit_journal.html",
            journal=journal_entry,
            student_name=session.get(
                "student_name",
                "Student"
            )
        )

    except Error as err:

        if db:
            db.rollback()

        flash(
            f"Database error: {err}",
            "danger"
        )

        return redirect(
            url_for("journal_history")
        )

    finally:

        if cursor:
            cursor.close()

        if db and db.is_connected():
            db.close()


# =========================================================
# DELETE JOURNAL
# =========================================================

@app.route(
    "/journal/<int:journal_id>/delete",
    methods=["POST"]
)  
def delete_journal(journal_id):

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
        cursor = db.cursor()

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

        db.commit()

        if cursor.rowcount == 0:

            flash(
                "Journal entry not found.",
                "danger"
            )

        else:

            flash(
                "Journal entry deleted successfully.",
                "success"
            )

        return redirect(
            url_for("journal_history")
        )

    except Error as err:

        if db:
            db.rollback()

        flash(
            f"Database error: {err}",
            "danger"
        )

        return redirect(
            url_for(
                "view_journal",
                journal_id=journal_id
            )
        )

    finally:

        if cursor:
            cursor.close()

        if db and db.is_connected():
            db.close()

# =========================================================
# AI SUPPORT - MINDMATE
# =========================================================

@app.route('/chat')
def chat():

    if 'student_id' not in session:
        return redirect(url_for('login'))

    student_email = session.get('student_email')

    db = None
    cursor = None
    chats = []

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                user_message,
                ai_reply,
                chat_date,
                chat_time
            FROM ai_chats
            WHERE student_email = %s
            ORDER BY id ASC
        """, (student_email,))

        chats = cursor.fetchall()

    except Error as err:

        print("CHAT HISTORY ERROR:", err)

    finally:

        if cursor:
            cursor.close()

        if db and db.is_connected():
            db.close()

    return render_template(
        'chat.html',
        student_name=session.get('student_name', 'Student'),
        chats=chats
    )


@app.route('/send_message', methods=['POST'])
def send_message():

    if 'student_email' not in session:
        return redirect(url_for('login'))

    student_email = session['student_email']
    user_message = request.form.get('message', '').strip()

    if not user_message:
        flash("Please enter a message.", "danger")
        return redirect(url_for('chat'))

    ai_reply = ""

    # -----------------------------------------------------
    # Gemini AI Response
    # -----------------------------------------------------

    if gemini_client:

        try:

            prompt = f"""
You are MindMate, a friendly AI support assistant for college students.

Your role is to provide supportive, calm and practical guidance.

Rules:
- Use simple and easy English.
- Keep the response around 50-100 words.
- Be warm and friendly, like a helpful senior student.
- Do not judge the student.
- Give practical suggestions when appropriate.
- Encourage healthy habits such as rest, talking to trusted people,
  taking breaks and seeking professional help when needed.
- Do not pretend to be a doctor, therapist or counselor.
- If the student needs professional support, gently suggest speaking
  with a qualified counselor or trusted person.
- Do not make a diagnosis.
- Answer the student's actual question directly.

Student's message:
{user_message}

Reply as MindMate.
"""

            response = gemini_client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt
            )

            ai_reply = response.text.strip()

        except Exception as err:

            print("GEMINI ERROR:", err)

            ai_reply = (
                "I'm sorry, I'm having trouble connecting right now. "
                "Please try again in a moment."
            )

    else:

        ai_reply = (
            "I'm currently unable to connect to the AI service. "
            "Please try again later."
        )

    # -----------------------------------------------------
    # Save Chat in Database
    # -----------------------------------------------------

    db = None
    cursor = None

    try:

        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO ai_chats
            (
                student_email,
                user_message,
                ai_reply,
                chat_date,
                chat_time
            )
            VALUES (%s, %s, %s, CURDATE(), CURTIME())
        """, (
            student_email,
            user_message,
            ai_reply
        ))

        db.commit()

    except Error as err:

        print("AI CHAT DATABASE ERROR:", err)

        if db:
            db.rollback()

        flash(
            "Message was answered, but chat history could not be saved.",
            "warning"
        )

    finally:

        if cursor:
            cursor.close()

        if db and db.is_connected():
            db.close()

    return redirect(url_for('chat'))

# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":
    app.run(debug=True)