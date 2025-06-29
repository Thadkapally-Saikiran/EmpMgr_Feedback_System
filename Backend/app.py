# ---------------------------------------------------
# app.py - Main Flask application with basic routes
# ---------------------------------------------------

from flask import Flask, render_template, request, redirect, url_for, session, flash, \
                make_response
from random import randint  # For generating OTPs
from database import fetch_user_by_email
# For sending mails
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText

from datetime import datetime              # For timestamps
from io import BytesIO                     # For PDF generation
from mysql.connector import IntegrityError  # For handling MySQL errors
import pdfkit                              # For PDF generation (you can switch to html-to-pdf with CSS)
import bcrypt           # For password hashing
import os               # For loading environment variables
from database import connect_db  # Import DB connection function
# import mysql     #  MySQL Connector for Python
# from werkzeug.security import generate_password_hash, check_password_hash



# Compute the absolute path of the directory containing this file (app.py)
BASE_DIR      = os.path.abspath(os.path.dirname(__file__))

#Build the path to the `Frontend/templates` folder by:
#    a) starting at BASE_DIR (i.e. Backend/)
#    b) going up one level (`..`) to the project root
#    c) descending into `Frontend/templates`
TEMPLATE_DIR  = os.path.join(BASE_DIR, '..', 'Frontend', 'templates')

# Build the path to the `Frontend/static` folder using the same pattern
STATIC_DIR    = os.path.join(BASE_DIR, '..', 'Frontend', 'static')




# Instantiate the Flask app, overriding the default template and static folders:
#    - __name__ tells Flask where this app is defined
#    - template_folder points Flask to our custom templates directory
#    - static_folder points Flask to our custom static assets directory
app = Flask(__name__,
    template_folder = TEMPLATE_DIR,
    static_folder   = STATIC_DIR
            )

# Secret key for session encryption (should be set via environment in production)
app.secret_key = os.environ.get("SECRET_KEY", "devsecretkey")





#----------------------------------------------
# Route: Manager View Feedback for each Employee
#-----------------------------------------------
@app.route('/manager/view_feedback/<int:emp_id>')  # URL route with employee ID parameter for manager
def manager_view_feedback(emp_id):  # Handler receives emp_id to show their feedback
    if 'user_id' not in session or session['role'] != 'manager':  # Ensure user is logged in and is a manager
        return redirect(url_for('login'))  # Redirect unauthorized access to login
    mgr_id = session['user_id']  # Get current manager’s user ID from session

    # Verify that employee reports to this manager
    db = connect_db()  # Open a database connection
    cur = db.cursor(dictionary=True)  # Use dict cursor to get column names as keys
    cur.execute(
        "SELECT id, name FROM users WHERE id=%s AND manager_id=%s",
        (emp_id, mgr_id)  # Parameterized query to prevent SQL injection
    )
    emp = cur.fetchone()  # Fetch employee record if they report to this manager
    if not emp:  # If no matching employee found
        flash("Invalid employee.", "danger")  # Show error message to manager
        cur.close(); db.close()  # Close cursor and connection to free resources
        return redirect(url_for('dashboard'))  # Redirect back to manager dashboard

    # Fetch feedbacks by this manager for that employee
    cur.execute(
        """
        SELECT f.id, f.strengths, f.improvements, f.sentiment, f.tags, f.created_at, f.updated_at
          FROM feedback f
         WHERE f.manager_id=%s AND f.employee_id=%s
         ORDER BY f.created_at DESC
        """,
        (mgr_id, emp_id)  # Query feedback table filtered by manager and employee
    )
    feedbacks = cur.fetchall()  # Retrieve all feedback rows as list of dicts

    # Gather all feedback IDs
    fids = [f['id'] for f in feedbacks]  # List comprehension to extract feedback IDs

    # Prepare defaults
    from collections import defaultdict  # Import defaultdict for grouping comments
    comments_map = defaultdict(list)  # Initialize map: feedback ID → list of comments

    if fids:  # Only proceed if there are feedback entries
        # Build a comma-separated list of %s placeholders (e.g. "%s,%s,%s")
        placeholder_str = ','.join(['%s'] * len(fids))  # Dynamically create placeholders

        # --- Load raw comments ---
        cur.execute(
            f"SELECT feedback_id, user_id, comment_text AS text "
            f"  FROM comments "
            f" WHERE feedback_id IN ({placeholder_str}) "
            f" ORDER BY created_at",   # Retain chronological order
            fids  # Pass feedback IDs as parameters tuple
        )
        raw_comments = cur.fetchall()  # Get all comment rows for those feedback IDs

        # --- Bulk name lookup for commenters ---
        commenter_ids = {row['user_id'] for row in raw_comments}  # Unique set of commenter IDs
        if commenter_ids:  # Only query if we have commenter IDs
            # reuse same placeholder_str technique
            name_placeholders = ','.join(['%s'] * len(commenter_ids))  # Placeholders for IN clause
            cur.execute(
                f"SELECT id, name FROM users WHERE id IN ({name_placeholders})",
                list(commenter_ids)  # Convert set to list for parameter passing
            )
            id_to_name = {r['id']: r['name'] for r in cur.fetchall()}  # Map user IDs to names
        else:
            id_to_name = {}  # No commenters means empty map

        # --- Build comments_map ---
        for row in raw_comments:  # Iterate over each comment record
            fid  = row['feedback_id']  # Which feedback this comment belongs to
            comments_map[fid].append({  # Append comment details to the appropriate list
                'user': id_to_name.get(row['user_id'], 'Unknown'),  # Lookup commenter name
                'text': row['text'],  # The comment text content
            })

    # close DB
    cur.close()  # Close the cursor to free resources
    db.close()   # Close the database connection

    # Render with both maps
    return render_template(
        'manager_view_feedback.html',  # Template for manager feedback view
        emp=emp,  # Pass employee info dictionary
        feedbacks=feedbacks,  # Pass list of feedback entries
        comments_map=comments_map,  # Pass mapping of comments by feedback ID
    )





# -------------------------------
# Route: Update Feedback (Manager only)
# -------------------------------
@app.route('/update_feedback/<int:fid>', methods=['GET','POST'])  # Map GET/POST requests with feedback ID to this view
def update_feedback(fid):  # Handler function receives the feedback primary key
    if 'user_id' not in session or session['role'] != 'manager':  # Ensure only logged-in managers proceed
        return redirect(url_for('login'))  # Redirect unauthorized users to login page
    mgr_id = session['user_id']  # Get current manager’s user ID from session
    db = connect_db()  # Open a connection to the database
    cur = db.cursor(dictionary=True)  # Use dict cursor for intuitive column access

    # Fetch feedback and verify ownership
    cur.execute("SELECT * FROM feedback WHERE id=%s AND manager_id=%s", (fid, mgr_id))  # Secure param query
    fb = cur.fetchone()  # Retrieve matching feedback or None
    if not fb:  # If feedback doesn’t exist or doesn’t belong to this manager
        flash("Feedback not found.", "danger")  # Inform manager of invalid request
        return redirect(url_for('dashboard'))  # Redirect back to the dashboard

    if request.method == 'POST':  # Handle form submission for updates
        strengths    = request.form['strengths']    # New strengths text from form
        improvements = request.form['improvements'] # New improvements text from form
        sentiment    = request.form['sentiment']    # Updated sentiment value
        tags         = request.form['tags']         # Updated comma-separated tags
        cur.execute(
            """
            UPDATE feedback
               SET strengths=%s,
                   improvements=%s,
                   sentiment=%s,
                   tags=%s,
                   updated_at   = NOW()
             WHERE id=%s
            """,
            (strengths, improvements, sentiment, tags, fid)  # Bind new values safely
        )
        db.commit()  # Persist changes to the database

        # Email notification to employee on update
        # Fetch employee email and name
        cur.execute("SELECT email, name FROM users WHERE id = %s", (fb['employee_id'],))  # Lookup employee info
        emp = cur.fetchone()  # Get their email & display name
        try:
            msg = MIMEMultipart()  # Create a multipart email message
            msg['From']    = SENDER_EMAIL  # Sender address from ENV
            msg['To']      = emp['email']  # Recipient employee’s email
            msg['Subject'] = "Your feedback has been updated"  # Informative subject line
            body = (
                f"Hi {emp['name']},\n\n"
                "Your manager has just updated the feedback previously provided to you. "
                "We encourage you to log in to the Feedback Management System to review "
                "the latest comments and action items.\n\n"
                "Keeping up with regular feedback helps you grow and align with team goals. "
                "If you have any questions or need further clarification, please don’t hesitate "
                "to reach out to your manager or HR.\n\n"
                "Best regards,\n"
                "The Feedback Management Team"
            )  # Construct the email body message
            msg.attach(MIMEText(body, "plain"))  # Attach plain-text payload

            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:  # Connect to SMTP server
                server.starttls()  # Secure the connection with TLS
                server.login(SENDER_EMAIL, SENDER_PASS)  # Authenticate with SMTP credentials
                server.send_message(msg)  # Send the notification email
        except Exception as e:
            app.logger.error(f"Failed to send update notification email: {e}")  # Log any send failures

        flash("Feedback updated successfully", "success")  # Feedback to manager on success
        cur.close(); db.close()  # Clean up DB cursor and connection
        return redirect(url_for('manager_view_feedback', emp_id=fb['employee_id']))  # Return to manager’s view page

    # GET: render form
    cur.close()  # Close cursor before rendering template
    db.close()   # Close DB connection
    return render_template('update_feedback.html', fb=fb)  # Show the update form with existing data



# -------------------------------
# Route: Home Page (redirect to login if not logged in)
# -------------------------------
@app.route('/')
def index():
    # If user already logged in, redirect to dashboard
    if 'user_id' in session:
        return redirect(url_for('dashboard')) # Redirect to dashboard if already logged in
    return redirect(url_for('login')) # Redirect to login page if not authenticated

# -------------------------------
# Route: Register New User
# -------------------------------
@app.route('/register', methods=['GET', 'POST'])           # Register endpoint supports displaying form and handling submissions
def register():                                            # Function to render or process the registration page
    # Fetch all existing managers for the dropdown 
    db       = connect_db()                                # Open connection to MySQL database
    cursor   = db.cursor()                                 # Create standard cursor for executing queries
    cursor.execute("SELECT id, name FROM users WHERE role = 'manager'")  # Retrieve all users with manager role
    managers = cursor.fetchall()                           # Fetch list of (id, name) tuples for the form dropdown
    cursor.close()                                         # Close cursor to free DB resources
    db.close()                                             # Close database connection now that managers are loaded

    if request.method == 'POST':                           # Check if the form was submitted via POST
        # Extract form data
        name = request.form.get('name', '').strip()        # Get and trim the 'name' field from the form
        email = request.form.get('email', '').strip()      # Get and trim the 'email' field from the form
        password = request.form.get('password', '')        # Get the 'password' field (no trimming to preserve spaces)
        role = request.form.get('role', 'employee')        # Get the 'role' dropdown, defaulting to 'employee'

        # 2) NEW: grab manager_id (only if you rendered a dropdown)
        manager_id = request.form.get('manager_id') or None  # Get selected manager ID or None if not provided

        # Input validations
        if not email:                                      # If email field is empty...
            flash('Email is required.', 'warning')         # Show warning message to user
            return render_template('register.html')        # Re-display registration form
        if not email.lower().endswith('@gmail.com'):      # Enforce Gmail addresses only
            flash('Email must end with @gmail.com.', 'warning')  # Warn if domain is invalid
            return render_template('register.html')        # Re-display form for correction
        if not password:                                   # If password field is empty...
            flash('Password is required.', 'warning')      # Inform user that password cannot be blank
            return render_template('register.html')        # Re-render form
        if len(password) <= 10:                            # Enforce minimum password length
            flash('Password must be more than 10 characters long.', 'warning')  # Warn about length rule
            return render_template('register.html')        # Show form again

        # Hash the password for secure storage
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())  # bcrypt hash with salt

        # Insert user into DB
        # Attempt to insert, catching duplicates
        db     = connect_db()                              # Re-open DB connection for insertion
        cursor = db.cursor()                               # Standard cursor for INSERT operation
        try:
            cursor.execute(                                # Execute INSERT SQL with placeholders
                "INSERT INTO users "
                "(name, email, password, role, manager_id) "
                "VALUES (%s, %s, %s, %s, %s)",
                (name, email, hashed_password, role, manager_id)  # Provide tuple of parameters
            )
            db.commit()                                    # Commit transaction to persist new user

        except IntegrityError as e:                        # Catch MySQL duplicate key error
            # MySQL error 1062 = duplicate entry for UNIQUE key
            if e.errno == 1062:                           # Check specific error code
                flash("That email is already registered. Please log in or use another email.", "warning")  # Duplicate email warning
                cursor.close()                            # Close cursor before returning
                db.close()                                # Close DB connection
                return redirect(url_for('register'))     # Redirect back to registration form
            # any other integrity error, re-raise
            cursor.close()                                # Clean up cursor
            db.close()                                    # Clean up connection
            raise                                         # Propagate unexpected errors

        cursor.close()                                    # Close cursor after successful insert
        db.close()                                        # Close DB connection

        # Send welcome email with user's full name
        try:
            # build MIME message
            msg = MIMEMultipart()                         # Create multipart email container
            msg['From']    = SENDER_EMAIL                 # Set sender address from environment
            msg['To']      = email                        # Set recipient to new user’s email
            msg['Subject'] = "Welcome to the Feedback System!"  # Friendly subject line
            body = (
                f"Hello {name},\n\n"
                f"Thank you for registering as a {role.capitalize()} on the DPDZero Feedback Management System.\n\n"
                "We're excited to have you on board! This platform is designed to help you give and receive constructive feedback, collaborate effectively, and foster a culture of continuous improvement.\n\n"
                "If you have any questions or need assistance, feel free to reach out to the support team.\n\n"
                "Best regards,\n"
                "DPDZero Team"

            )                                            # Email body text
            msg.attach(MIMEText(body, "plain"))          # Attach plain-text payload

            # send via SMTP
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:  # Connect to mail server
                server.starttls()                          # Secure connection with TLS
                server.login(SENDER_EMAIL, SENDER_PASS)    # Authenticate with SMTP credentials
                server.send_message(msg)                   # Dispatch the welcome email
        except Exception as e:
            app.logger.error(f"Failed to send welcome email: {e}")  # Log failures but do not break flow

        flash("Registration successful. Please login.", "success")  # Inform user of successful signup
        return redirect(url_for('login'))                     # Send them to login page next

    # For GET request, show registration form
    return render_template('register.html', managers=managers)  # Render form with list of managers




# -------------------------------
# Route: Login
# -------------------------------
@app.route('/login', methods=['GET', 'POST'])  # Define endpoint for login supporting both form display and submission
def login():  # Entry point for handling user login requests
    # On every fresh GET to /login, wipe any old counters or OTP state
    if request.method == 'GET':  # If this is a page load rather than a form submission
        session.pop('failed_logins', None)  # Clear previous failed login attempts count
        session.pop('login_otp',     None)  # Remove any stored one-time password
        session.pop('otp_email',     None)  # Remove any stored email for OTP flow
        return render_template('login.html')  # Render the login form template

    if request.method == 'POST':  # If the login form has been submitted
        email = request.form.get('email', '').strip()  # Retrieve and trim the entered email
        password = request.form.get('password', '')  # Retrieve the entered password

        # Input validations
        if not email:  # Ensure email field is not empty
            flash('Email is required.', 'warning')  # Show warning if missing
            return render_template('login.html')  # Re-render form for correction
        if not email.lower().endswith('@gmail.com'):  # Enforce Gmail-only addresses
            flash('Email must end with @gmail.com.', 'warning')  # Notify of invalid domain
            return render_template('login.html')  # Re-render form
        if not password:  # Ensure password field is not empty
            flash('Password is required.', 'warning')  # Warn if missing
            return render_template('login.html')  # Re-render form

        # 2) Fetch user record and their hash
        db     = connect_db()  # Open a connection to the database
        cursor = db.cursor(dictionary=True)  # Create a cursor returning rows as dicts
        cursor.execute(
            "SELECT id, name, password AS hashed_pw, role "
            "  FROM users WHERE email = %s",  # Parameterized SELECT for security
            (email,)
        )
        user = cursor.fetchone()  # Fetch the single matching user record
        cursor.close()  # Close cursor to free resources
        db.close()  # Close database connection

        if not user:  # If no user record was found
            flash('No account found with that email. Please register first.', 'danger')  # Inform user
            return redirect(url_for('register'))  # Redirect to registration page

        # 3) Now we have their hash
        stored_hash = user['hashed_pw']  # Extract the stored password hash

        # Initialize/Increment failed-attempts counter
        session.setdefault('failed_logins', 0)  # Ensure counter exists in session

        # Password check
        if not bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):  # Compare provided password with hash
            session['failed_logins'] += 1  # Increment failed attempt count

            # After 3rd wrong attempt, send OTP and redirect
            if session['failed_logins'] > 2:  # If too many failures
                # Generate 6-digit OTP
                otp = f"{randint(0, 999999):06d}"  # Create zero-padded random code
                session['login_otp'] = otp  # Store OTP in session
                session['otp_email'] = email  # Store email for OTP verification

                # Send OTP email
                msg = MIMEMultipart()  # Prepare multipart email message
                msg['From']    = SENDER_EMAIL  # Sender address from environment
                msg['To']      = email  # Recipient is the login email
                msg['Subject'] = "OTP Verification Required"  # Email subject line
                body = (
                  "You’ve exceeded 2 incorrect login attempts.\n\n"
                  "Please verify it’s really you by entering this OTP:\n\n"
                  f"{otp}\n\n"
                  "If this wasn’t you, please contact support immediately."
                )  # Construct email body
                msg.attach(MIMEText(body, 'plain'))  # Attach plain-text body
                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:  # Connect to SMTP server
                    server.starttls()  # Secure connection with TLS
                    server.login(SENDER_EMAIL, SENDER_PASS)  # Authenticate
                    server.send_message(msg)  # Send OTP email

                return redirect(url_for('otp_verification'))  # Redirect user to OTP entry page

            flash('Incorrect password. Please try again.', 'danger')  # Show error for wrong password
            return render_template('login.html')  # Re-render login form

        # Successful login
        # On successful login, reset counter
        session.pop('failed_logins', None)  # Clear failed attempt count
        session['user_id'] = user['id']  # Store user ID in session
        session['role']    = user['role']  # Store user role in session
        session['name']    = user['name']  # Store user name in session
        # flash('Logged in successfully!', 'success')
        return redirect(url_for('dashboard'))  # Navigate to user dashboard

    # GET request: show login form
    return render_template('login.html')  # Fallback render for non-POST requests





# -------------------------------
# Route: otp_verification
# -------------------------------
@app.route('/otp_verification', methods=['GET','POST'])  # Handle both form display and submission for OTP
def otp_verification():  # View function for verifying one-time passwords
    if request.method == 'POST':  # Process form submission when user posts OTP
        entered = request.form.get('otp', '').strip()  # Retrieve and trim the OTP input from the form
        if entered == session.get('login_otp'):  # Compare entered OTP against stored session value
            # Lookup the user by the email we stored earlier
            email = session.get('otp_email')  # Get the email address tied to this OTP from session
            user  = fetch_user_by_email(email)  # Fetch user record from DB by email (returns dict)

            if not user:  # If no matching user is found
                flash("Could not find your account. Please log in again.", "danger")  # Show error message
                return redirect(url_for('login'))  # Redirect back to login for safety
            

            # Clear the OTP & failed-login counters
            session.pop('login_otp', None)      # Remove the OTP from session storage
            session.pop('failed_logins', None)  # Reset the wrong-password counter

            # Now it's safe to use user['id'], user['role'], etc.
            session['user_id']   = user['id']    # Log the user in by setting session user_id
            session['role']      = user['role']  # Store the user’s role for access control
            session['name']      = user['name']  # Save the user’s display name in session
            return redirect(url_for('dashboard'))  # Send the user to their dashboard on success
        else:  # OTP did not match
            flash(
                "Invalid or expired OTP. Please try again. "
                "If you're not yet registered, you can create an account first.",
                "warning"
            )  # Inform user of the failure and next steps
            return redirect(url_for('register'))  # Show registration form if they need an account
    return render_template('otp_verification.html')  # On GET, render the OTP entry page





# -------------------------------
# Route: Logout
# -------------------------------
@app.route('/logout')  # Define URL endpoint for logging out users
def logout():  # Handler function for logout action
    # Clear the session
    session.clear()  # Remove all keys from Flask session (invalidates login)
    return redirect(url_for('login'))  # Redirect user back to login page after clearing session


# -------------------------------
# Route: Dashboard (Role-based)
# -------------------------------
@app.route('/dashboard')  # Define URL endpoint for dashboard view
def dashboard():  # Handler function for both manager and employee dashboards
    if 'user_id' not in session:  # Check if user is authenticated
        return redirect(url_for('login'))  # Redirect unauthenticated users to login page

    db  = connect_db()  # Establish a new database connection
    cur = db.cursor(dictionary=True)  # Create a dict-based cursor for readable column access
    m_id = session['user_id']  # Get the current user's ID from session

    if session['role'] == 'manager':  # Branch logic for manager role
        # 1) Load team members
        cur.execute("""
            SELECT u.id, u.name
              FROM users u
             WHERE u.role = 'employee'
               AND u.manager_id = %s
        """, (m_id,))  # Parameterized SQL to fetch employees under this manager
        employees = cur.fetchall()  # Retrieve all matching rows as list of dicts

        # 2) Total feedback count
        cur.execute("""
            SELECT COUNT(*) AS total
              FROM feedback
             WHERE manager_id = %s
        """, (m_id,))  # Count feedback entries authored by this manager
        total_feedbacks = cur.fetchone()['total']  # Extract the count from first row

        # 3) Sentiment breakdown
        cur.execute("""
            SELECT sentiment, COUNT(*) AS cnt
              FROM feedback
             WHERE manager_id = %s
             GROUP BY sentiment
        """, (m_id,))  # Group feedback by sentiment category
        stats = {r['sentiment']: r['cnt'] for r in cur.fetchall()}  # Build dict mapping sentiment→count
        positive_count = stats.get('positive', 0)  # Default to 0 if key missing
        neutral_count  = stats.get('neutral',  0) # Default to 0 if key missing
        negative_count = stats.get('negative', 0) # Default to 0 if key missing

        # 4) Per-employee feedback & last date
        cur.execute("""
            SELECT u.id,
                   u.name,
                   COUNT(f.id)       AS feedback_count,
                   MAX(f.created_at) AS last_feedback_date
              FROM users u
         LEFT JOIN feedback f
                ON f.employee_id = u.id
               AND f.manager_id  = %s
             WHERE u.role       = 'employee'
               AND u.manager_id = %s
          GROUP BY u.id, u.name
        """, (m_id, m_id))  # Left join to include employees with zero feedback
        employees = cur.fetchall()  # Overwrite employees with detailed stats list

        cur.close()  # Close cursor to free resources
        db.close()   # Close DB connection

        return render_template(  # Render manager dashboard template
            'dashboard.html',   # Template for manager dashboard
            role='manager',      # Role type for conditional rendering
            employees=employees, # List of employees with feedback stats
            total_feedbacks=total_feedbacks, # Total feedback count for this manager
            positive_count=positive_count, # Positive sentiment count
            neutral_count=neutral_count, # Neutral sentiment count
            negative_count=negative_count # Negative sentiment count
        )
    else:  # Branch logic for employee role
        # employee dashboard: fetch all feedback for this user
        cur.execute("""
            SELECT f.id,
                f.strengths,
                f.improvements,
                f.sentiment,
                f.tags,
                f.created_at,
                f.updated_at,
                u.name AS manager_name
            FROM feedback f
        LEFT JOIN users u ON u.id = f.manager_id
            WHERE f.employee_id = %s
        ORDER BY f.created_at DESC
        """, (session['user_id'],))  # Fetch feedback entries for this employee
        feedbacks = cur.fetchall()  # List of feedback dicts

        # --- determine display timestamp for each feedback ---
        for fb in feedbacks:  # Iterate each feedback entry
            if fb['updated_at'] and fb['updated_at'] != fb['created_at']:
                fb['display_ts'] = fb['updated_at']  # Use updated time if different
            else:
                fb['display_ts'] = fb['created_at']  # Otherwise, use creation time

        # --- load all comments for these feedback IDs ---
        fb_ids = [fb['id'] for fb in feedbacks]  # Extract feedback IDs list
        comments_map = {}  # Initialize mapping feedback_id→comments
        if fb_ids:  # Only query if there are feedback entries
            format_strings = ','.join(['%s'] * len(fb_ids))  # Build placeholders dynamically
            cur.execute(f"""
                SELECT c.feedback_id,
                    c.comment_text,
                    u.name AS user_name
                FROM comments c
            LEFT JOIN users u ON u.id = c.user_id
                WHERE c.feedback_id IN ({format_strings})
            ORDER BY c.created_at
            """, tuple(fb_ids))  # Query comments for all feedback IDs
            for row in cur.fetchall():  # Populate comments_map
                comments_map.setdefault(row['feedback_id'], []).append(row)

        # 3) Load acknowledgements for this employee
        ack_map = {}  # Initialize ack mapping
        cur.execute(
            "SELECT feedback_id, acknowledged_at"
            "  FROM acknowledgements"
            " WHERE employee_id = %s",
            (session['user_id'],)  # Query acknowledgement timestamps for this user
        )
        for row in cur.fetchall():  # Build ack_map
            ack_map[row['feedback_id']] = row['acknowledged_at']

        cur.close()  # Close cursor after all queries
        db.close()   # Close database connection

        return render_template(  # Render employee dashboard template
            'dashboard.html',  # Template for employee dashboard
            role='employee', # Role type for conditional rendering
            feedbacks=feedbacks,  # List of feedback entries with display timestamps
            comments_map=comments_map,  # Comments grouped by feedback ID
            ack_map=ack_map   # Acknowledgement timestamps for dimming & badges
        )




    

# -------------------------------
# SMTP email configuration
# -------------------------------
SMTP_SERVER   = os.environ.get("SMTP_SERVER",  "smtp.gmail.com")   # Load SMTP host from env or default to Gmail’s server  
SMTP_PORT     = int(os.environ.get("SMTP_PORT",    587))          # Load SMTP port (converted to int), defaulting to TLS port 587  
SENDER_EMAIL  = os.environ.get("SENDER_EMAIL",  "yourteam.feedback.bot@gmail.com")  # Bot’s “from” address from env or fallback  
SENDER_PASS   = os.environ.get("SENDER_PASS",   "kbht dsmu lotd gudu")   # Bot’s SMTP password from env or default (keep secret!)  



# -------------------------------
# Route: Submit Feedback (Manager only)
# -------------------------------
@app.route('/submit_feedback', methods=['GET', 'POST'])  # Define endpoint for submitting feedback via GET or POST
def submit_feedback():  # Handler function for feedback creation
    # Check login
    if 'user_id' not in session or session['role'] != 'manager':  # Ensure user is authenticated as manager
        return redirect(url_for('login'))  # Redirect unauthorized users to login

    # Connect to DB
    db = connect_db()  # Open a new database connection
    cursor = db.cursor(dictionary=True)  # Use dict cursor for named field access

    # On form submit
    if request.method == 'POST':  # Only run feedback logic on POST
        # First: count this manager’s direct reports
        cursor.execute("""
            SELECT COUNT(*) AS cnt
            FROM users
            WHERE role = 'employee'
            AND manager_id = %s
        """, (session['user_id'],))  # Securely parameterize manager ID
        emp_count = cursor.fetchone()['cnt']  # Fetch number of employees under this manager

        # If there are no employees *or* nobody was selected, bail out
        employee_id = request.form.get('employee_id')  # Read selected employee from form
        if emp_count == 0 or not employee_id:  # Check if manager has employees and one was chosen
            flash(
                "You have no employees assigned or you didn’t select one. So, you cannot submit feedback.",
                "warning"
            )  # Inform manager they cannot proceed
            return redirect(url_for('submit_feedback'))  # Reload the feedback form

        strengths    = request.form['strengths']     # Get strengths input
        improvements = request.form['improvements']  # Get improvements input
        sentiment    = request.form['sentiment']     # Get sentiment selection
        tags         = request.form['tags']          # Get comma-separated tags

        # 🔒 Validate that this employee actually reports to you
        # Before inserting feedback, verify employee actually reports to you
        cursor.execute("""
            SELECT manager_id
              FROM users
             WHERE id = %s
        """, (employee_id,))  # Query target employee’s manager_id
        row = cursor.fetchone()  # Fetch the result as dict
        if not row or row['manager_id'] != session['user_id']:  # Confirm manager match
            flash("Invalid employee selection.", "danger")  # Warn if someone tried unauthorized ID
            return redirect(url_for('submit_feedback'))  # Reload the form

        # Insert feedback
        cursor.execute("""
            INSERT INTO feedback (manager_id, employee_id, strengths, improvements, sentiment, tags)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (session['user_id'], employee_id, strengths, improvements, sentiment, tags))  # Secure insert
        db.commit()  # Save the new feedback row

        # Email notification (optional)
        cursor.execute("SELECT email, name FROM users WHERE id = %s", (employee_id,))  # Fetch employee contact
        emp = cursor.fetchone()  # Retrieve dict with email & name
        try:
            msg = MIMEMultipart()  # Create multi-part email container
            msg['From']    = SENDER_EMAIL  # Sender address from environment
            msg['To']      = emp['email']  # Recipient’s email address
            msg['Subject'] = "You've received new feedback!"  # Email subject line
            body = (
                f"Hi {emp['name']},\n\n"
                "Your manager has completed a feedback review of your recent performance. "
                "We value your contributions and encourage you to reflect on the comments provided. "
                "Please log in to your DPDZero Feedback Management System to view the detailed feedback, "
                "acknowledge receipt, and let us know if you have any questions.\n\n"
                "Thank you for your continued dedication and hard work.\n\n"
                "Best regards,\n"
                "The DPDZero Feedback Team"
            )  # Email body text
            msg.attach(MIMEText(body, "plain"))  # Attach plain-text payload

            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:  # Connect to SMTP server
                server.starttls()  # Start TLS encryption
                server.login(SENDER_EMAIL, SENDER_PASS)  # Authenticate SMTP credentials
                server.send_message(msg)  # Send constructed email
        except Exception as e:
            app.logger.error(f"Email send failed: {e}")  # Log email errors without interrupting flow

        flash("Feedback submitted successfully", "success")  # Inform manager of success
        return redirect(url_for('submit_feedback'))  # Redirect back to form for next feedback

    # On GET: Fetch only *this manager’s* direct reports
    cursor.execute("""
        SELECT id, name
        FROM users
        WHERE role = 'employee'
        AND manager_id = %s
    """, (session['user_id'],))  # Query employees under this manager
    employees = cursor.fetchall()  # Retrieve list of dicts for template

    return render_template('submit_feedback.html', employees=employees)  # Render form with employee options




# -------------------------------
# Route: View Feedback (Employee only)
# -------------------------------
@app.route('/view_feedback')  # Define GET route for employees to view their feedback
def view_feedback():  # Handler function for displaying employee feedback
    if 'user_id' not in session or session['role'] != 'employee':  # Check login and role
        return redirect(url_for('login'))  # Redirect unauthenticated or non-employee users

    db  = connect_db()  # Open a new database connection
    cur = db.cursor(dictionary=True)  # Use dictionary cursor for named column access

    # 1) Fetch all feedbacks for this user, now explicitly including updated_at
    cur.execute("""  
        SELECT 
            f.id,
            f.strengths,
            f.improvements,
            f.sentiment,
            f.tags,
            f.created_at,
            f.updated_at,              
            u.name AS manager_name
          FROM feedback f
     LEFT JOIN users u ON u.id = f.manager_id  # Join to pull manager’s name
         WHERE f.employee_id = %s              # Filter by current employee ID
      ORDER BY f.created_at DESC               # Show newest feedback first
    """, (session['user_id'],))
    feedbacks = cur.fetchall()  # Retrieve list of feedback dicts

    # 2) For each feedback, pick the timestamp we want to display
    for fb in feedbacks:  # Iterate feedback entries
        if fb['updated_at'] and fb['updated_at'] != fb['created_at']:  # If it was updated
            fb['display_ts'] = fb['updated_at']  # Show updated timestamp
        else:
            fb['display_ts'] = fb['created_at']  # Otherwise show original creation time

    # 3) Load comments for those feedback IDs
    fb_ids = [fb['id'] for fb in feedbacks]  # Extract all feedback IDs into list
    comments_map = {}  # Prepare map: feedback_id → list of comments
    if fb_ids:  # Only query if there are IDs
        fmt = ','.join(['%s'] * len(fb_ids))  # Build placeholder string for IN clause
        cur.execute(f"""
            SELECT c.feedback_id,
                   c.comment_text,
                   u.name AS user_name
              FROM comments c
         LEFT JOIN users u ON u.id = c.user_id  # Join commenter’s name
             WHERE c.feedback_id IN ({fmt})     # Filter by our list of IDs
          ORDER BY c.created_at                  # Order by comment timestamp
        """, tuple(fb_ids))
        for row in cur.fetchall():  # Iterate fetched comment rows
            comments_map.setdefault(row['feedback_id'], []).append(row)  # Group by feedback ID

    # 4) Load acknowledgements for dimming & badge
    ack_map = {}  # Prepare map: feedback_id → acknowledged timestamp
    cur.execute("""
        SELECT feedback_id, acknowledged_at
          FROM acknowledgements
         WHERE employee_id = %s
    """, (session['user_id'],))  # Fetch acknowledgements for this employee
    for row in cur.fetchall():  # Iterate results
        ack_map[row['feedback_id']] = row['acknowledged_at']  # Store timestamp in map

    cur.close()  # Close cursor to free resources
    db.close()   # Close database connection

    # 5) Render, passing in our new `display_ts`
    return render_template(
        'view_feedback.html',  # Template for employee feedback
        feedbacks=feedbacks,    # List of feedback dicts with display_ts
        comments_map=comments_map,  # Comments grouped by feedback ID
        ack_map=ack_map             # Acknowledgement timestamps
    )






# -------------------------------
# Route: Acknowledge Feedback
# -------------------------------
@app.route('/acknowledge/<int:fid>', methods=['POST'])  # Bind POST to /acknowledge/<feedback_id>
def acknowledge_feedback(fid):  # Handler takes feedback primary key
    # only employees can ack
    if 'user_id' not in session or session.get('role') != 'employee':  # Ensure logged-in & role is employee
        flash("Please log in as an employee to acknowledge feedback.", "warning")  # Show warning if not
        return redirect(url_for('login'))  # Redirect unauthorized users to login

    emp_id = session['user_id']  # Grab employee’s ID from session
    db = connect_db()  # Open a database connection
    cursor = db.cursor(dictionary=True)  # Use dict cursor for easy column access

    # 1) Insert acknowledgement if new
    cursor.execute(
        """
        INSERT IGNORE INTO acknowledgements (feedback_id, employee_id, acknowledged_at)
        VALUES (%s, %s, NOW())
        """,
        (fid, emp_id)  # Parameter tuple to prevent SQL injection
    )
    db.commit()  # Commit the new acknowledgement row

    # 2) Fetch all times + email info
    cursor.execute("""
        SELECT
          u.email             AS mgr_email,
          u.name              AS mgr_name,
          e.name              AS emp_name,
          f.created_at        AS fb_created,
          f.updated_at        AS fb_updated,
          a.acknowledged_at   AS ack_time
        FROM feedback f
        JOIN users u   ON u.id = f.manager_id     # Join to get manager info
        JOIN users e   ON e.id = f.employee_id    # Join to get employee info
        JOIN acknowledgements a
          ON a.feedback_id  = f.id                 # Join ack table on feedback ID
         AND a.employee_id  = %s                   # Filter ack by this employee
        WHERE f.id = %s                            # Filter feedback by feedback ID
    """, (emp_id, fid))
    info = cursor.fetchone()  # Fetch single row with all needed fields

    cursor.close()  # Close the cursor to free resources
    db.close()      # Close the database connection

    # 3) Send email to the manager
    if info and info['mgr_email']:  # Ensure we have a manager email to send to
        # format each timestamp
        created_str = info['fb_created'].strftime("%b %d, %H:%M")  # e.g. “Jun 25, 09:27”
        updated_str = info['fb_updated'].strftime("%b %d, %H:%M") if info['fb_updated'] else created_str  # fallback
        ack_str     = info['ack_time'].strftime("%b %d, %H:%M")  # time when ack happened

        try:
            msg = MIMEMultipart()  # Construct multipart email
            msg['Subject'] = f"{info['emp_name']} acknowledged your feedback"  # Dynamic subject
            msg['From']    = SENDER_EMAIL  # Sender from ENV
            msg['To']      = info['mgr_email']  # Manager’s email address

            body = (
                f"Hi {info['mgr_name']},\n\n"  # Personalized greeting
                f"{info['emp_name']} has acknowledged the feedback you gave:\n"
                f" • Originally created on: {created_str}\n"
                f" • Last updated on:     {updated_str}\n"
                f" • Acknowledged at:    {ack_str}\n\n"
                "Log in to review any further comments or updates.\n"
            )  # Build email body with bullet points
            msg.attach(MIMEText(body, "plain"))  # Attach plain-text payload

            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:  # Connect to SMTP server
                server.starttls()  # Upgrade to secure TLS
                server.login(SENDER_EMAIL, SENDER_PASS)  # Authenticate
                server.send_message(msg)  # Send the assembled email

        except Exception as e:
            app.logger.error(f"Failed to send acknowledgement email: {e}")  # Log any email errors

    # 4) Redirect back with a flash
    flash("Feedback acknowledged!", "success")  # Notify user of success
    return redirect(url_for('view_feedback'))  # Redirect employee to their feedback list





# -------------------------------
# Route: Add a comment to a feedback (markdown supported)
# -------------------------------
@app.route('/add_comment/<int:fid>', methods=['POST']) # Define route to add a comment to feedback by ID
def add_comment(fid): # Handler function to add a comment to a specific feedback entry
    # Only logged-in users can comment
    if 'user_id' not in session:   # Check if user is authenticated
        return redirect(url_for('login')) # Redirect unauthenticated users to login page

    commenter_id   = session['user_id'] # Get the ID of the user who is commenting
    commenter_role = session['role']  # Get the role of the user (manager or employee)
    commenter_name = session['name']  # Get the name of the user who is commenting
    # Trim and validate the submitted text
    comment_text = request.form.get('comment', '').strip() # Retrieve comment text from form and trim whitespace
    if not comment_text: # If comment is empty after trimming
        flash("Comment cannot be empty.", "warning") # Show warning message to user
        # Redirect back exactly as below according to role
        if commenter_role == 'manager':  # If the commenter is a manager
            db     = connect_db() # Open a new database connection
            cursor = db.cursor(dictionary=True) # Create a cursor that returns dict rows
            cursor.execute(
                "SELECT employee_id AS other_id FROM feedback WHERE id=%s",
                (fid,)
            ) # Query to get the employee ID associated with this feedback
            other_id = cursor.fetchone()['other_id'] # Fetch the employee ID from the result
            cursor.close(); db.close() # Close the cursor and database connection
            # Redirect to the manager's view of the feedback
            return redirect(url_for('manager_view_feedback', emp_id=other_id)) 
        else:   # If the commenter is an employee
            next_url = request.form.get('next') or url_for('dashboard') # Get the next URL from the form or default to dashboard
            return redirect(next_url) # Redirect to the next URL or dashboard

    # 1) Insert into comments table
    db     = connect_db() # Open a new database connection
    cursor = db.cursor() # Create a cursor for executing SQL commands
    cursor.execute(
        "INSERT INTO comments (feedback_id, user_id, comment_text) VALUES (%s, %s, %s)",
        (fid, commenter_id, comment_text)
    ) # Insert the new comment into the comments table
    db.commit() # Commit the transaction to save changes

    # 2) Determine the recipient
    if commenter_role == 'manager': # If the commenter is a manager
        cursor = db.cursor(dictionary=True) # Create a cursor that returns dict rows
        cursor.execute(
            "SELECT employee_id AS other_id FROM feedback WHERE id=%s",
            (fid,)
        ) # Query to get the employee ID associated with this feedback
    else: # If the commenter is an employee
        cursor = db.cursor(dictionary=True) # Create a cursor that returns dict rows
        cursor.execute(
            "SELECT manager_id AS other_id FROM feedback WHERE id=%s",
            (fid,)
        )  # Query to get the manager ID associated with this feedback
    other_id = cursor.fetchone()['other_id'] # Fetch the other user ID (employee or manager) from the result

    # 3) Lookup their email & name
    cursor.execute(
        "SELECT email, name FROM users WHERE id=%s",
        (other_id,)
    )  # Query to get the email and name of the other user
    other = cursor.fetchone() # Fetch the result as a dict
    cursor.close() # Close the cursor to free resources
    db.close() # Close the database connection

    # 4) Send notification email
    if other and other['email']: # Check if the other user exists and has an email address
        try: # If the other user exists and has an email address
            msg = MIMEMultipart()  # Create a new email message
            msg['From']    = SENDER_EMAIL  # Set the sender's email address from environment variable
            msg['To']      = other['email'] # Set the recipient's email address from the fetched user
            who = 'Manager' if commenter_role == 'manager' else 'Employee' # Determine who is commenting based on their role
            msg['Subject'] = f"New comment from {who} on Feedback #{fid}" # Set the email subject with the feedback ID and commenter role
            body = (
                f"Hi {other['name']},\n\n"
                f"{who} {commenter_name} just commented on feedback #{fid}:\n\n"
                f"\"{comment_text}\"\n\n"
                f"View it here: {request.url_root}view_feedback\n\n"
                "— Your Feedback System"
            ) # Construct the email body with comment details
            msg.attach(MIMEText(body, "plain")) # Attach the email body

            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server: # Connect to the SMTP server
                server.starttls() # Upgrade connection to secure TLS
                server.login(SENDER_EMAIL, SENDER_PASS) # Authenticate with SMTP server
                server.send_message(msg) # Send the email notification
        except Exception as e: # Catch any errors during email sending
            app.logger.error(f"Failed to send comment notification: {e}") # Log the error

    # 5) Flash & redirect to the correct view
    flash("Comment added and notification sent!", "success") # Show success message
    if commenter_role == 'manager': # If the commenter is a manager
        return redirect(url_for('manager_view_feedback', emp_id=other_id)) # Redirect to manager view
    else: # If the commenter is an employee
        next_url = request.form.get('next') or url_for('dashboard') # Get the next URL or default to dashboard
        return redirect(next_url) # Redirect to the next URL or dashboard if not found




# -------------------------------
# Route: Export a single feedback entry to PDF
# -------------------------------
@app.route('/export_feedback/<int:fid>')  # Define a Flask route with integer feedback ID
def export_feedback(fid):  # Controller function for exporting feedback as PDF
    if 'user_id' not in session:  # Ensure user is logged in
        return redirect(url_for('login'))  # Redirect unauthenticated users to login

    db = connect_db()  # Open a new database connection
    cursor = db.cursor(dictionary=True)  # Create a cursor that returns dict rows

    # Fetch the feedback entry from DB
    cursor.execute("SELECT * FROM feedback WHERE id = %s", (fid,))  # Query feedback by ID
    feedback = cursor.fetchone()  # Retrieve the single result row
    cursor.close()  # Close the cursor
    db.close()  # Close the database connection

    # Generate HTML content for PDF
    html_content = render_template('pdf_template.html', fb=feedback)  # Render feedback into HTML template

    
    # allow wkhtmltopdf to load local CSS & other assets
    options = {
         'enable-local-file-access': None  # Enable local file access for assets
    }
    # Convert HTML to PDF using pdfkit
    pdf = pdfkit.from_string(html_content, False, options=options)  # Generate PDF bytes from HTML

    # Return PDF as downloadable response
    response = make_response(pdf)  # Wrap PDF bytes in a Flask response
    response.headers['Content-Type'] = 'application/pdf'  # Set correct MIME type
    response.headers['Content-Disposition'] = f'attachment; filename=feedback_{fid}.pdf'  # Suggest download filename
    return response  # Send the PDF response back to the client





# -------------------------------
# Start Flask App (only run if not imported)
# -------------------------------
if __name__ == '__main__':
    # Run in debug mode for development
    app.run(debug=True)
