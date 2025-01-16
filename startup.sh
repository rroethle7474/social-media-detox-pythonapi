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

echo "Starting gunicorn..."
exec gunicorn --bind=0.0.0.0 --timeout 600 app:app