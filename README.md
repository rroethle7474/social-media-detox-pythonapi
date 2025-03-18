# TimeHealerV3 - Twitter Scraper Application

## Project Description
This is a Flask-based web application that uses Selenium and BeautifulSoup4 to scrape and extract data from Twitter (now X) based on search terms and channel identifiers (the user homepage on x).

This will use selenium to login to the user's account using their credentials. Due to bot detection, expect an email to be generated to your account saying a new login has been detected but no limits have currently been observed from this or restrictions.

Based on web scraping the records, if any UI changes are made on Twitter(X)'s end, the scraping code may need to be adjusted.

## Environment Setup

1. Copy `.env.example` to `.env.local`
2. Update the values in `.env.local` with your local configuration
3. Never commit `.env.local` to source control

Required environment variables:
- TWITTER_USERNAME: Your Twitter email
- TWITTER_PASSWORD: Your Twitter password
- TWITTER_PHONE_NUMBER: Your phone number
- TWITTER_BASE_URL: Twitter base URL 

## Key Technologies and Dependencies

### Core Technologies:
1. **Flask**: Web framework for creating the API endpoints
2. **Selenium**: Browser automation tool for navigating Twitter/X
3. **BeautifulSoup4**: HTML parsing library for extracting tweet content
4. **Gunicorn**: WSGI HTTP server for running the Flask application in production
5. **Chrome WebDriver**: Used by Selenium to automate Chrome browser

### Supporting Libraries:
- **python-dotenv**: For loading environment variables
- **flask-cors**: For handling Cross-Origin Resource Sharing (CORS)
- **cachetools**: For in-memory caching of Twitter API responses
- **psutil**: For process management and cleanup of Chrome processes
- **webdriver-manager**: For managing Chrome WebDriver versions

## Architecture

The application follows a service-oriented architecture with three main services:

1. **DriverService**: Manages Selenium WebDriver instances, browser automation, and handles Twitter login
2. **TwitterService**: Handles Twitter-specific operations like searching and extracting tweet data
3. **CacheService**: Provides caching functionality to avoid redundant Twitter scraping

## Technical Details

### Selenium with Chrome WebDriver
- The application uses Chrome in headless mode for web scraping
- Anti-detection measures are implemented to avoid being detected as a bot
- The system creates a unique Chrome user profile for each session
- Process management for reliable cleanup of Chrome instances

### BeautifulSoup4 for Content Parsing
- Used to parse Twitter's HTML content after Selenium loads the page
- Extracts structured data like tweet text, usernames, timestamps, and URLs
- Creates normalized data structures (TwitterResult model) from raw HTML

### Caching System
- Time-To-Live (TTL) cache to minimize requests to Twitter
- Default cache lifetime is 1 hour
- Cache keys are based on operation type and search query
- API provided to clear or reset the cache

### Environment Configuration
- Requires Twitter credentials (username, password, phone number)
- Configuration via environment variables (stored in .env.local for development)
- Different environment configurations for test and production environments

### Running in Azure
- The project includes Azure pipeline configuration
- Special handling for Azure App Service environment
- Logging configured for Azure's expected paths (/home/LogFiles)

## Running the Project Locally
Recommend to run using a Python Virtual Environment first (venv)

### Installing Dependencies

```bash
pip install -r requirements.txt
```

### Running with Gunicorn

For development with the specific address http://127.0.0.1:5000:
```bash
gunicorn --bind="127.0.0.1:5000" --timeout 120 --workers 1 --threads 2 app:app
```

For development (default):
```bash
gunicorn --bind="0.0.0.0:8000" --timeout 120 --workers 1 --threads 2 app:app
```

For production:
```bash
gunicorn --bind="0.0.0.0:8000" --timeout 120 --workers 2 --threads 4 --worker-class sync --log-level info app:app
```

### Chrome Requirements

The application requires Google Chrome to be installed. For local development:
1. Ensure Chrome is installed on your system
2. The WebDriver will be automatically downloaded by webdriver-manager

## API Endpoints

1. **POST /ChannelResults**: Search tweets from specific Twitter channels/accounts
   - Accepts: URL, search queries, and isDefault flag
   - Returns: Structured tweet data for the specified channels

2. **POST /SearchResults**: Run search queries on Twitter
   - Accepts: URL, search queries, and isDefault flag
   - Returns: Structured tweet data matching the search queries

3. **POST /ResetSearchCache**: Clears the cache to force fresh data fetching
   - Returns: Success/failure message

4. **GET /health** and **GET /api/health**: Health check endpoints
   - Returns: System health information including Chrome version and cache stats

## Key Implementation Notes

1. **Twitter Login Automation**:
   - The system handles Twitter's multi-step login process
   - Includes error handling for various login scenarios
   - Detects login success/failure conditions

2. **Anti-Bot Detection Measures**:
   - Uses realistic user agents
   - Disables automation flags
   - Implements random delays and natural scrolling behavior

3. **Error Handling and Resilience**:
   - Comprehensive error handling for Selenium operations
   - Process cleanup to prevent resource leaks
   - Request locking to prevent concurrent Chrome sessions

4. **Performance Considerations**:
   - Caching to minimize Twitter requests
   - Screenshot capabilities for debugging
   - Session reuse where possible
   - Memory management for long-running instances

## Common Issues and Troubleshooting

1. **Chrome Process Handling**: 
   - Chrome processes might not clean up properly; the system includes explicit process termination
   - Temporary directories need proper cleanup to avoid disk space issues

2. **Twitter Login Challenges**:
   - Twitter's login page structure changes frequently; the code contains fallbacks for various selectors
   - Phone verification handling is implemented but may need updates as Twitter changes

3. **Rate Limiting**:
   - Twitter may rate-limit or block automated access; implement appropriate delays between requests
   - Consider rotating IP addresses for production use

## Security Considerations

1. Credentials are stored in environment variables, never hardcoded
2. The .env.local file should never be committed to source control
3. API endpoints may need additional authentication in production environments 