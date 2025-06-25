# EmpMgr Feedback System

A lightweight, full-stack **Employee-Manager Feedback System** built with Python (Flask), MySQL, and a simple HTML/CSS/JS frontend. This tool enables structured, ongoing feedback between managers and their direct reports, complete with comments, acknowledgements, PDF export, and email notifications.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Features](#features)
3. [Tech Stack](#tech-stack)
4. [System Compatibility](#system-compatibility)
5. [Project Structure](#project-structure)
6. [Database Schema](#database-schema)
7. [Setup & Installation](#setup--installation)
8. [Requirements](#requirements)
9. [Running with Docker](#running-with-docker)
10. [Usage](#usage)
11. [AI Assistance](#ai-assistance)
12. [Design Decisions & Notes](#design-decisions--notes)
13. [License](#license)

---

## Project Overview

This application allows:

* **Managers** to submit, update, and view structured feedback for team members.
* **Employees** to view received feedback, acknowledge it, and add comments (with Markdown support).
* **Real-time notifications** (via email) for comments, acknowledgements, and feedback updates.
* **PDF export** of individual feedback entries.

All interactions are secured by role-based authentication, with an OTP fallback after failed login attempts.

---

## Features

* **Authentication & Roles**: Manager and Employee user roles with bcrypt-hashed passwords and OTP verification.
* **Feedback Workflow**:

  * Submit strengths, areas to improve, sentiment (positive/neutral/negative), and tags.
  * View editable history with timestamps.
* **Visibility Controls**:

  * Managers see only their direct reports.
  * Employees see only their own feedback.
* **Acknowledgements**: Employees can acknowledge feedback; managers receive email notifications.
* **Comments**: Both parties can comment on feedback; comments rendered in Markdown and trigger email alerts.
* **Dashboard**:

  * Managers: team overview, feedback count, sentiment breakdown.
  * Employees: chronological timeline of feedback.
* **Extras**: Tag filtering, PDF export (wkhtmltopdf + pdfkit), Dockerized backend.

---

## Tech Stack

* **Backend**: Python 3.10, Flask 3.x
* **Database**: MySQL (connector: `mysql-connector-python`)
* **Frontend**: Jinja2 templates, HTML5, CSS3, JavaScript (+ Bootstrap 5)
* **Email**: SMTP via `smtplib`, MIME formatting
* **PDF Generation**: `pdfkit` + `wkhtmltopdf`
* **Containerization**: Docker
* **AI Tools**: Assisted development using ChatGPT and Google Gemini

---

## System Compatibility

* **Operating Systems**: Windows 10+, macOS 10.15+, Linux (Ubuntu 20.04+)
* **Python Version**: 3.10–3.12
* **MySQL Server**: 5.7+ or MariaDB 10.3+
* **Docker**: 20.10+ (for containerized deployment)

---

## Project Structure

```plaintext
EmpMgr_Feedback_System/
├─ Backend/
│  ├─ app.py
│  ├─ database.py
│  ├─ Dockerfile
│  └─ requirements.txt
├─ Database/
│  └─ schema.sql
└─ Frontend/
   ├─ static/
   │  ├─ images/EmpMGR_Feedback_System.jpg
   │  ├─ script.js
   │  └─ styles.css
   └─ templates/
      ├─ dashboard.html
      ├─ login.html
      ├─ manager_view_feedback.html
      ├─ otp_verification.html
      ├─ pdf_template.html
      ├─ register.html
      ├─ submit_feedback.html
      ├─ update_feedback.html
      └─ view_feedback.html
```

---

## Database Schema

The core tables are:

### `users`

| Column      | Type        | Description                          |
| ----------- | ----------- | ------------------------------------ |
| id          | INT PK AI   | Unique user identifier               |
| name        | VARCHAR     | Full name                            |
| email       | VARCHAR\_UQ | Login email (Gmail only)             |
| password    | VARCHAR     | Bcrypt-hashed password               |
| role        | ENUM        | `manager` or `employee`              |
| manager\_id | INT FK      | References `users(id)` for employees |
| created\_at | TIMESTAMP   | Record creation time                 |

### `feedback`

| Column       | Type      | Description                     |
| ------------ | --------- | ------------------------------- |
| id           | INT PK AI | Unique feedback ID              |
| manager\_id  | INT FK    | Manager who created feedback    |
| employee\_id | INT FK    | Employee receiving feedback     |
| strengths    | TEXT      | Positive comments               |
| improvements | TEXT      | Areas to improve                |
| sentiment    | ENUM      | `positive`,`neutral`,`negative` |
| tags         | VARCHAR   | Comma-separated tags            |
| created\_at  | TIMESTAMP | Timestamp of creation           |
| updated\_at  | TIMESTAMP | Timestamp of last update        |

### `acknowledgements`

| Column           | Type      | Description                    |
| ---------------- | --------- | ------------------------------ |
| feedback\_id     | INT FK    | References `feedback(id)`      |
| employee\_id     | INT FK    | References `users(id)`         |
| acknowledged\_at | TIMESTAMP | When the employee acknowledged |

### `comments`

| Column        | Type      | Description                   |
| ------------- | --------- | ----------------------------- |
| id            | INT PK AI | Unique comment ID             |
| feedback\_id  | INT FK    | References `feedback(id)`     |
| user\_id      | INT FK    | Author (manager or employee)  |
| comment\_text | TEXT      | Markdown-supported comment    |
| created\_at   | TIMESTAMP | Timestamp of comment creation |




### ER Diagram

```plaintext
+------------+       +-----------+       +-------------+
|   users    |1---*  | feedback  |*---1  |   users     |
| (managers) |       |           |       |(employees)  |
+------------+       +-----------+       +-------------+
      ^                    |
      |                    |
      |                    *                +----------------+
      |                +-----+    1---*    | acknowledgements|
      +----------------|comments|------------|                |
                       +-----+              +----------------+
```


---

## Setup & Installation

1. **Clone the repo**

   ```bash
   git clone https://github.com/yourusername/EmpMgr_Feedback_System.git
   cd EmpMgr_Feedback_System/Backend
   ```
2. **Database**

   * Install MySQL and create a database named `feedback_system`.
   * Run the schema:

     ```bash
     mysql -u root -p feedback_system < ../Database/schema.sql
     ```
3. **Python environment**

   ```bash
   python3 -m venv venv
   source venv/bin/activate   # macOS/Linux
   venv\Scripts\activate    # Windows
   pip install -r requirements.txt
   ```
4. **Environment variables**

   ```bash
   export SENDER_EMAIL=you@example.com
   export SENDER_PASS=<app-password>
   export SECRET_KEY=<your-secret>
   ```
5. **Run locally**

   ```bash
   python app.py
   ```

   Open your browser at `http://localhost:5000`.

---

## Requirements

All Python dependencies are pinned in `Backend/requirements.txt`. To install them:

```bash
pip install -r Backend/requirements.txt
```

System package:

* `wkhtmltopdf` (required by `pdfkit` for PDF export)

---

## Running with Docker

Build and run the backend container:

```bash
cd Backend
docker build -t feedback-backend .
docker run -d -p 5000:5000 --name feedback-api feedback-backend
```

Visit `http://localhost:5000`.

---

## Usage

1. **Register** as Manager or Employee (Gmail only).
2. **Managers**:

   * Submit feedback under **Submit Feedback**.
   * View your team and analytics on **Dashboard**.
3. **Employees**:

   * View and acknowledge feedback in **My Feedback**.
   * Add comments and receive notifications.
4. **Export** any feedback entry to PDF or filter by tags.

---

## AI Assistance

This project was developed with the help of **ChatGPT** and **Google Gemini** for code suggestions and design brainstorming. All AI-generated code was reviewed and adapted for clarity, security, and coherence.

---

## Design Decisions & Notes

* **OTP flow** triggers after 3 failed login attempts for added security.
* **Dictionary cursors** (`cursor(dictionary=True)`) allow named-field access.
* **Dockerfile** focuses on backend; static frontend assets are served by Flask.
* **Bonus Features**:

  * Proactive employee feedback requests – *not yet implemented*
  * Anonymous peer feedback – *not yet implemented*
  * Public deployment link – *optional (provided via video demo)*

---

## License

[MIT](LICENSE) © Thadkapally Saikiran
