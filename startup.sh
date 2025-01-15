#!/bin/bash
set -e  # Exit on any error

# Check if Chrome is installed
if ! command -v google-chrome &> /dev/null; then
    echo "Installing Chrome..."
    curl -sS -o - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list
    apt-get update
    apt-get install -y google-chrome-stable
fi

# Set environment name based on app service name
if [[ $WEBSITE_HOSTNAME == *"-test"* ]]; then
    cp .env.test .env
else
    cp .env.prod .env
fi

# Start the application with gunicorn
exec gunicorn --bind=0.0.0.0 --timeout 600 --workers 2 --threads 2 app:app