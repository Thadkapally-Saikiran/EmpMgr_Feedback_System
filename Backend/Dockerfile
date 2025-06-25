# Use a minimal Python 3.10 image to keep the container lightweight
FROM python:3.10-slim

# Ensure Python output is sent straight to the console (no buffering)
ENV PYTHONUNBUFFERED=1

# Set the working directory inside the container to /app
WORKDIR /app

# Update package lists and install wkhtmltopdf for PDF generation, then clean up
RUN apt-get update && apt-get install -y \
    wkhtmltopdf \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Provide SMTP credentials for sending emails from within the app
ENV SENDER_EMAIL=thadkapallysaikiran2001@gmail.com
ENV SENDER_PASS=ktvqinalsrseitjg
ENV SMTP_SERVER=smtp.gmail.com
ENV SMTP_PORT=587

# Copy only the requirements file first so Docker can cache dependency installs
COPY requirements.txt .

# Install project dependencies without caching wheels to save space
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application codebase into the container’s /app directory
COPY . .

# Declare that the container listens on port 5000 at runtime
EXPOSE 5000

# Tell Flask what file to use as the application entry point
ENV FLASK_APP=app.py

# Bind the Flask development server to all network interfaces
ENV FLASK_RUN_HOST=0.0.0.0

# Define the default command to launch the Flask dev server with debug enabled
CMD ["flask", "--debug", "run"]
