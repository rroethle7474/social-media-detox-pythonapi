#!/bin/bash
set -e  # Exit on any error

echo "Adding Chrome repository..."
curl -sS -o - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list

echo "Updating package list..."
apt-get update

echo "Installing Chrome..."
apt-get install -y google-chrome-stable

echo "Installing Python dependencies..."
pip install --no-cache-dir -r requirements.txt

echo "Setting up environment..."
if [[ $WEBSITE_HOSTNAME == *"-test"* ]]; then
    cp .env.test .env
else
    cp .env.prod .env
fi

# Create log directory if it doesn't exist
mkdir -p /home/LogFiles/gunicorn

echo "Starting gunicorn..."
exec gunicorn \
    --bind=0.0.0.0:8000 \
    --timeout 600 \
    --workers 2 \
    --threads 4 \
    --worker-class gthread \
    --log-level info \
    --access-logfile /home/LogFiles/gunicorn/access.log \
    --error-logfile /home/LogFiles/gunicorn/error.log \
    app:app