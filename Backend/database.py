# -----------------------------------------------
# database.py - handles MySQL DB connection setup
# -----------------------------------------------

import mysql.connector  # Import the MySQL Connector/Python library
from mysql.connector import Error  # Import exception class for DB errors

# Create a reusable database connection function
def connect_db():
    # Establish a MySQL connection using the connector with given credentials
    connection = mysql.connector.connect(
        host="localhost",      # Database host, could be container hostname
        user="root",           # MySQL username with appropriate privileges
        password="SaiKiran@2001",  # Password for MySQL user
        database="feedback_system"  # Specific database to connect to
    )
    return connection  # Return the open connection object for queries



# new helper
def fetch_user_by_email(email: str):
    """
    Returns a dict with keys 'id', 'email', 'password_hash', 'role', 'name', 'manager_id', ...
    or None if no such user.
    """
    conn = None  # Initialize connection variable for cleanup
    try:
        conn = connect_db()  # Open a new DB connection
        cursor = conn.cursor(dictionary=True)  # Use dict cursor for named-column access
        cursor.execute(
            "SELECT id, email, password_hash AS hashed_pw, role, name, manager_id "
            "FROM users WHERE email = %s",
            (email,)  # Parameter tuple to safely insert email into query
        )
        user = cursor.fetchone()  # Fetch the first matching row or None if no match
        return user  # Return the user dict or None
    except Error as e:
        print("Database error:", e)  # Output error for debugging purposes
        return None  # Return None on failure to signal no user found
    finally:
        if cursor:
            cursor.close()  # Always close cursor to free resources
        if conn:
            conn.close()  # Always close connection to avoid leaks
