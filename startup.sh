#!/bin/bash
set -e  # Exit on any error

# Enable command logging
set -x

echo "Starting startup.sh with enhanced logging..."

# Create log directories
mkdir -p /home/LogFiles/startup
mkdir -p /home/LogFiles/gunicorn
mkdir -p /home/LogFiles/chrome
chmod 777 /home/LogFiles/chrome

# Add debug logging for directory permissions
ls -la /home/site/chrome-data > /home/LogFiles/chrome-dir-permissions.txt


# Function to log messages
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a /home/LogFiles/startup/startup.log
}

log_message "Adding Chrome repository..."
if ! curl -sS -o - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -; then
    log_message "Failed to add Chrome signing key"
    exit 1
fi
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list

log_message "Updating package list..."
apt-get update

log_message "Installing Chrome..."
# Prevent services from starting automatically during install
echo "exit 101" > /usr/sbin/policy-rc.d
chmod +x /usr/sbin/policy-rc.d
apt-get install -y google-chrome-stable
rm /usr/sbin/policy-rc.d

# Disable Chrome's automatic updating and background services
log_message "Disabling Chrome services..."
if [ -f /etc/default/google-chrome ]; then
    echo "repo_add_once=false" >> /etc/default/google-chrome
fi

# Kill any existing Chrome processes
log_message "Cleaning up any existing Chrome processes..."
pkill chrome || true
pkill -f "chrome" || true

# Create and set permissions for Chrome data directory
log_message "Setting up Chrome data directory..."
mkdir -p /home/site/chrome-data
chmod 777 /home/site/chrome-data 

log_message "Installing Python dependencies..."
pip install --no-cache-dir -r requirements.txt

log_message "Setting up environment..."
if [[ $WEBSITE_HOSTNAME == *"-test"* ]]; then
    cp .env.test .env
    log_message "Copied test environment file"
else
    cp .env.prod .env
    log_message "Copied prod environment file"
fi

log_message "Adding startup delay for health checks..."
sleep 5

log_message "Starting gunicorn on port 8000..."
exec gunicorn \
    --bind=0.0.0.0:8000 \
    --timeout 600 \
    --workers 2 \
    --threads 4 \
    --worker-class gthread \
    --log-level debug \
    --access-logfile /home/LogFiles/gunicorn/access.log \
    --error-logfile /home/LogFiles/gunicorn/error.log \
    --capture-output \
    --preload \
    app:app 2>&1 | tee -a /home/LogFiles/startup/startup.log