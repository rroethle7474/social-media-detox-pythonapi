#!/bin/bash
set -e  # Exit on any error

# Enable command logging
set -x

echo "Starting startup.sh with enhanced logging..."

# Create log directories in persisted location
mkdir -p /home/site/wwwroot/logs/startup
mkdir -p /home/site/wwwroot/logs/gunicorn
mkdir -p /home/site/wwwroot/logs/chrome
chmod 777 /home/site/wwwroot/logs/chrome
chmod 777 /home/site/wwwroot/logs/startup
chmod 777 /home/site/wwwroot/logs/gunicorn

# Function to log messages
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a /home/site/wwwroot/logs/startup/startup.log
}

# Log environment information
log_message "Environment Information:"
log_message "PORT: $PORT"
log_message "WEBSITES_PORT: $WEBSITES_PORT"
log_message "WEBSITE_HOSTNAME: $WEBSITE_HOSTNAME"
log_message "Current directory: $(pwd)"
log_message "Directory contents: $(ls -la)"
log_message "Python version: $(python3 --version)"
log_message "Pip version: $(pip3 --version)"

# Ensure we're using Python 3.12
if command -v python3.12 &> /dev/null; then
    log_message "Using Python 3.12"
    python_cmd="python3.12"
else
    log_message "Python 3.12 not found, using default Python"
    python_cmd="python3"
fi

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

# Verify Chrome installation
if ! which google-chrome > /dev/null; then
    log_message "Chrome installation failed - not found in PATH"
    exit 1
fi

chrome_version=$(google-chrome --version)
log_message "Chrome version: $chrome_version"

# Create and set permissions for Chrome data directory
log_message "Setting up Chrome data directory..."
CHROME_DATA_DIR="/home/site/wwwroot/chrome-data"
mkdir -p $CHROME_DATA_DIR
chmod 777 $CHROME_DATA_DIR

# Clean up any existing Chrome processes and port files
log_message "Cleaning up Chrome processes and files..."
pkill -f "chrome" || true
rm -f $CHROME_DATA_DIR/.com.google.Chrome.* || true
rm -f $CHROME_DATA_DIR/SingletonLock || true
rm -f $CHROME_DATA_DIR/DevToolsActivePort || true

# Set Chrome data directory environment variable
export CHROME_USER_DATA_DIR=$CHROME_DATA_DIR
log_message "Chrome user data directory set to: $CHROME_USER_DATA_DIR"

log_message "Installing Python dependencies..."
$python_cmd -m pip install --upgrade pip
$python_cmd -m pip install --no-cache-dir -r requirements.txt

log_message "Setting up environment..."
if [[ $WEBSITE_HOSTNAME == *"-test"* ]]; then
    cp .env.test .env
    log_message "Copied test environment file"
else
    cp .env.prod .env
    log_message "Copied prod environment file"
fi

# Use WEBSITES_PORT if available, otherwise fallback to 8000
PORT="${WEBSITES_PORT:-8000}"
log_message "Starting gunicorn on port $PORT..."

# Start with minimal configuration first
exec gunicorn \
    --bind="0.0.0.0:${PORT}" \
    --timeout 120 \
    --workers 1 \
    --threads 2 \
    --worker-class sync \
    --log-level debug \
    --access-logfile /home/site/wwwroot/logs/gunicorn/access.log \
    --error-logfile /home/site/wwwroot/logs/gunicorn/error.log \
    --capture-output \
    --log-file=- \
    --pythonpath "${PWD}" \
    app:app 2>&1 | tee -a /home/site/wwwroot/logs/startup/startup.log