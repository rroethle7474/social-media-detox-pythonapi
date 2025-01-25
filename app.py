import platform
import subprocess
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import os
import logging
from models.twitter_result import TwitterResult
from datetime import datetime, UTC
import json
from cachetools import TTLCache
from selenium.webdriver.common.action_chains import ActionChains

from services.cache_service import CacheService
from services.driver_service import DriverService
from services.twitter_service import TwitterService


# Set up logging
log_handlers = [logging.StreamHandler()]

# Determine log file path based on environment
if os.getenv('WEBSITE_HOSTNAME'):  # Running in Azure
    log_path = '/home/LogFiles/app.log'
else:  # Running locally
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, 'app.log')

log_handlers.append(logging.FileHandler(log_path))

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=log_handlers
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Production configurations
app.config['PROPAGATE_EXCEPTIONS'] = True
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['JSON_SORT_KEYS'] = False

# Initialize services
try:
    driver_service = DriverService()
    cache_service = CacheService()
    twitter_service = TwitterService(driver_service, cache_service)
    logger.info("Services initialized successfully")
except Exception as e:
    logger.error(f"Error initializing services: {str(e)}")
    raise

@app.route('/')
def root():
    """Root endpoint for health checks"""
    try:
        return jsonify({
            "Success": True,
            "Message": "TimeHealer API is running",
            "Data": {
                "status": "healthy",
                "timestamp": datetime.now(UTC).isoformat()
            },
            "Errors": None
        })
    except Exception as e:
        logger.error(f"Error in root endpoint: {str(e)}")
        return jsonify({
            "Success": False,
            "Message": "Error in health check",
            "Data": None,
            "Errors": [str(e)]
        }), 500

# Add startup readiness check
ready = False

def init_app():
    """Initialize application resources"""
    global ready
    logger.info("Initializing services...")
    ready = True

@app.before_request
def check_ready():
    if not ready and request.endpoint != 'health_check':
        return jsonify({
            "Success": False,
            "Message": "Application is starting up",
            "Data": None,
            "Errors": ["Application not ready"]
        }), 503

# Initialize the app
with app.app_context():
    init_app()

@app.teardown_appcontext
def cleanup_context(exception=None):
    """Cleanup resources when the application context ends"""
    driver_service.cleanup_all_drivers()

# Register cleanup on process termination
import atexit
atexit.register(driver_service.cleanup_all_drivers)

# methods for the api
@app.route('/ChannelResults', methods=['POST'])
def channel_search_results():
    try:
        print("Retrieving channel search results")
        url = request.json.get('url')
        isDefault = request.json.get('isDefault', False)
        search_queries = request.json.get('search_queries', [])
        if not search_queries:
            return jsonify({
                "Success": False,
                "Message": "No search queries provided",
                "Data": None,
                "Errors": ["No search queries provided"]
            }), 400
        
        result, errors = twitter_service.perform_twitter_operation(url, search_queries, 'channel', isDefault)
        success = bool(result)
        return jsonify({
            "Success": success,
            "Message": "Channel search completed" if len(errors) == 0 else "Channel search completed with errors",
            "Data": result if result else None,
            "Errors": errors if errors else None
        })
    except Exception as e:
        return jsonify({
            "Success": False,
            "Message": "An error occurred during channel search",
            "Data": None,
            "Errors": [str(e)]
        }), 500

@app.route('/SearchResults', methods=['POST'])
def search_results():
    try:
        print("Retrieving search results")
        url = request.json.get('url')
        isDefault = request.json.get('isDefault', False)
        search_queries = request.json.get('search_queries', [])
        if not search_queries:
            return jsonify({
                "Success": False,
                "Message": "No search queries provided",
                "Data": None,
                "Errors": ["No search queries provided"]
            }), 400
        
        result, errors = twitter_service.perform_twitter_operation(url, search_queries, 'search', isDefault)
        success = bool(result)
        return jsonify({
            "Success": success,
            "Message": "Search completed" if len(errors) == 0 else "Search completed with errors",
            "Data": result if result else None,
            "Errors": errors if errors else None
        })
    except Exception as e:
        print("Encountered error in search_results")
        return jsonify({
            "Success": False,
            "Message": "An error occurred during search",
            "Data": None,
            "Errors": [str(e)]
        }), 500

@app.route('/ResetSearchCache', methods=['POST'])
def reset_cache():
    try:
        cache_service.clear()
        return jsonify({
            "Success": True,
            "Message": "Cache has been reset",
            "Data": None,
            "Errors": []
        })
    except Exception as e:
        return jsonify({
            "Success": False,
            "Message": "Error resetting cache",
            "Data": None,
            "Errors": [str(e)]
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    try:
        print("Checking health")
        chrome_version = "Not checked in local environment"
        if not ready:
            return jsonify({
                "Success": False,
                "Message": "Application starting",
            }), 503
        # Only check Chrome version in Azure environment
        if os.getenv('WEBSITE_HOSTNAME'):
            try:
                chrome_version = subprocess.check_output(['google-chrome', '--version']).decode().strip()
            except Exception as e:
                chrome_version = f"Chrome version detection failed: {str(e)}"

        return jsonify({
            "Success": True,
            "Message": "API is running",
            "Data": {
                "status": "healthy",
                "timestamp": datetime.now(UTC).isoformat(),
                "chrome_version": chrome_version,
                "python_version": platform.python_version(),
                "environment": os.getenv('WEBSITE_HOSTNAME', 'local'),
                "platform": platform.system(),
                "cache_stats": cache_service.get_stats()
            },
            "Errors": None
        })
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        return jsonify({
            "Success": False,
            "Message": "Health check failed",
            "Data": None,
            "Errors": [str(e)]
        }), 500
        
        
# @app.route('/SearchResults', methods=['POST'])
# def search_results():
#     global cache
#     url = request.json.get('url')
    
#     if 'recent_posts' in cache:
#         logger.info("Returning cached recent posts")
#         return jsonify({"data": cache['recent_posts']})
    
#     search_queries = request.json.get('search_queries', [])
#     if not search_queries:
#         return jsonify({"error": "No search queries provided"}), 400

#     driver = setup_driver()
#     try:
#         # Navigate to the URL
#         driver.get(url)

#         # Login (you'll need to customize this part)
#         username = os.getenv('TWITTER_USERNAME')
#         password = os.getenv('TWITTER_PASSWORD')

#         logger.info("Attempting to locate username input")
#         username_input = find_input_element(driver)
#         username_input.send_keys(username)
#         logger.info("Username entered successfully")
#         click_next_button(driver)

#         handle_optional_step(driver, username)

#         logger.info("Attempting to locate password input")
#         password_input = find_password_input(driver)
#         password_input.send_keys(password)
#         logger.info("Password entered successfully")
        
#         click_login_button(driver)
#         results = {}
#         for search_query in search_queries:
#             print("SEARCH QUERY", search_query)
#             perform_search(driver, search_query)
#             click_latest_button(driver)
#             print("CLICKED")
#             recent_posts = get_recent_posts(driver)
#             print("RECENT POSTS", recent_posts)
#             results[search_query] = json.loads(recent_posts)  # Ensure it's a JSON array, not a string

#         cache['recent_posts'] = results  # Cache the recent posts

#         return jsonify({"data": results})

#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

#     finally:
#         driver.quit()

# @app.route('/ChannelResults', methods=['POST'])
# def channel_search_results():
#     global cache
#     url = request.json.get('url')
    
#     if 'channel_posts' in cache:
#         logger.info("Returning cached recent posts")
#         return jsonify({"data": cache['channel_posts']})
    
#     search_queries = request.json.get('search_queries', [])
#     if not search_queries:
#         return jsonify({"error": "No search queries provided"}), 400

#     driver = setup_driver()
#     try:
#         # Navigate to the URL
#         driver.get(url)

#         # Login (you'll need to customize this part)
#         username = os.getenv('TWITTER_USERNAME')
#         password = os.getenv('TWITTER_PASSWORD')

#         logger.info("Attempting to locate username input")
#         username_input = find_input_element(driver)
#         username_input.send_keys(username)
#         logger.info("Username entered successfully")
#         click_next_button(driver)

#         handle_optional_step(driver, username)

#         logger.info("Attempting to locate password input")
#         password_input = find_password_input(driver)
#         password_input.send_keys(password)
#         password_input.send_keys(password)
#         logger.info("Password entered successfully")
        
#         click_login_button(driver)
#         results = {}
#         for search_query in search_queries:
#             print("Channel QUERY", search_query)
#             success_login = check_login_status(driver)
#             if not success_login:
#                 logger.error("Failed to login")
#                 return jsonify({"error": "Failed to login"}), 500
#             perform_channel_search(driver, search_query)
#             #click_latest_button(driver)
#             recent_posts = get_recent_posts(driver)
#             print("RECENT Channel POSTS", recent_posts)
#             results[search_query] = json.loads(recent_posts)  # Ensure it's a JSON array, not a string

#         cache['channel_posts'] = results  # Cache the recent posts
#         time.sleep(20)
#         return jsonify({"data": results})

#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

#     finally:
#         logger.info("Simulate Closing driver")
#         #driver.quit()

@app.errorhandler(Exception)
def handle_exception(e):
    # Log the error with traceback
    app.logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
    
    return jsonify({
        "Success": False,
        "Message": "An unexpected error occurred",
        "Data": None,
        "Errors": [str(e)]
    }), 500

if __name__ == '__main__':
    app.run(debug=True)
    
    
def extract_tweet_url(tweet_div):
    # Look for a link with data-testid="tweetText"
    tweet_link = tweet_div.find('a', {'data-testid': 'tweetText'})
    
    if tweet_link and 'href' in tweet_link.attrs:
        # Extract the relative URL
        relative_url = tweet_link['href']
        
        # Construct the full URL
        full_url = f"https://x.com{relative_url}"
        return full_url
        # URL encode the full URL
        #return urllib.parse.quote(full_url, safe='')
    
    # Fallback: look for any link containing "/status/"
    status_link = tweet_div.find('a', href=lambda href: href and '/status/' in href)
    
    if status_link and 'href' in status_link.attrs:
        relative_url = status_link['href']
        full_url = f"https://x.com{relative_url}"
        
        # URL encode the full URL
        #return urllib.parse.quote(full_url, safe='')
        return full_url
    
    # If no suitable link is found
    return None

def datetime_to_iso(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError("Type not serializable")

    
def get_recent_posts(driver, num_posts=5):
    try:
        # Wait for tweets to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article[data-testid='tweet']"))
        )
        
        # Get the page source and parse it with BeautifulSoup
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Find all tweet articles
        tweets = soup.find_all('article', attrs={'data-testid': 'tweet'})
        recent_posts = []
        for tweet in tweets[:num_posts]:
            # Extract username
            #username = tweet.find('div', attrs={'data-testid': 'User-Name'}).text
            full_name = tweet.find('div', attrs={'data-testid': 'User-Name'}).text
            channel, username = full_name.split('@', 1)
            username = '@' + username  # Add @ back to the username
            # Extract tweet text
            tweet_text = tweet.find('div', attrs={'data-testid': 'tweetText'}).text if tweet.find('div', attrs={'data-testid': 'tweetText'}) else ''
            # Extract timestamp
            embed_url = extract_tweet_url(tweet)
            timestamp_element = tweet.find('time')
            timestamp = timestamp_element['datetime'] if timestamp_element else datetime.now(UTC).isoformat()

            
            tweet = TwitterResult(  
                channel=channel,
                username=username,
                description=tweet_text,
                published_date=timestamp,
                embed_url=embed_url
            )
            recent_posts.append(tweet)
        
        logger.info(f"Retrieved {len(recent_posts)} recent posts")
        tweet_dicts = [tweet.__dict__ for tweet in recent_posts]

        # Convert the list of dictionaries to JSON
        json_data = json.dumps(tweet_dicts, default=datetime_to_iso)
        return json_data
    except Exception as e:
        logger.error(f"Error retrieving recent posts: {str(e)}")
        raise


def click_latest_button(driver):
    latest_button_xpath = "//span[text()='Latest']"
    try:
        latest_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, latest_button_xpath))
        )
        latest_button.click()
        logger.info("Latest button clicked successfully")
    except TimeoutException:
        logger.error("Latest button not found or not clickable")
        raise
    
def perform_channel_search(driver, search_query):
    
    url = "https://x.com/" + search_query
    try:
        driver.get(url)
        # Wait for either the ScrollSnap-List or the "account doesn't exist" message
        element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="ScrollSnap-List"], [data-testid="emptyState"]'))
        )
        
        #time.sleep(25)
        # Check if the account doesn't exist
        if element.get_attribute('data-testid') == 'emptyState':
            logger.info(f"Account {search_query} doesn't exist")
            return False  # Indicate that the search was unsuccessful
        
        logger.info(f"Channel Search performed successfully for query: {search_query}")
        return True  # Indicate that the search was successful
    except TimeoutException:
        logger.error(f"Timeout while searching for channel: {search_query}")
        return False
    except Exception as e:
        logger.error(f"Error during channel search for {search_query}: {str(e)}")
        return False
    
    
def setup_driver():
    # Setup Chrome options (you might need to adjust this based on your environment)
    chrome_options = webdriver.ChromeOptions()
    #chrome_options.add_argument("--headless")  # Run in headless mode
    return webdriver.Chrome(options=chrome_options)
    
def find_input_element(driver):
    selectors = [
        (By.CSS_SELECTOR, "input[name='text'][autocomplete='username']"),
        (By.CSS_SELECTOR, "input.r-30o5oe.r-1dz5y72.r-13qz1uu"),
        (By.XPATH, "//input[@autocapitalize='sentences' and @autocomplete='username']"),
        (By.CSS_SELECTOR, "input[type='text'][dir='auto']"),
    ]
    for by, selector in selectors:
        try:
            return WebDriverWait(driver, 10).until(EC.presence_of_element_located((by, selector)))
        except TimeoutException:
            continue
    raise NoSuchElementException("Could not find username input field")


def find_password_input(driver):
    selectors = [
        (By.CSS_SELECTOR, "input[name='password'][type='password']"),
        (By.CSS_SELECTOR, "input[autocomplete='current-password']"),
        (By.XPATH, "//input[@type='password' and contains(@class, 'r-30o5oe')]"),
    ]
    for by, selector in selectors:
        try:
            return WebDriverWait(driver, 10).until(EC.presence_of_element_located((by, selector)))
        except TimeoutException:
            continue
    raise NoSuchElementException("Could not find password input field")

def click_next_button(driver):
    next_button_xpath = "//button[@role='button']//span[contains(text(), 'Next')]"
    try:
        next_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, next_button_xpath))
        )
        next_button.click()
        logger.info("Next button clicked successfully")
    except TimeoutException:
        logger.error("Next button not found or not clickable")
        raise

def click_login_button(driver):
    login_button_selector = "[data-testid='LoginForm_Login_Button']"
    try:
        login_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, login_button_selector))
        )
        # Check if the button is disabled
        if login_button.get_attribute("disabled"):
            logger.warning("Login button is disabled. Waiting for it to become enabled...")
            WebDriverWait(driver, 10).until_not(
                EC.element_to_be_clickable((By.CSS_SELECTOR, login_button_selector + "[disabled]"))
            )
            login_button = driver.find_element(By.CSS_SELECTOR, login_button_selector)
        
        login_button.click()
        logger.info("Login button clicked successfully")
    except TimeoutException:
        logger.error("Login button not found or not clickable")
        raise
    
def handle_optional_step(driver):
    optional_step_text = "Enter your phone number or username"
    phone_number = os.getenv('TWITTER_PHONE_NUMBER')
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, f"//span[contains(text(), '{optional_step_text}')]"))
        )
        logger.info("Optional step detected")
        optional_input = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[data-testid='ocfEnterTextTextInput']"))
        )
        optional_input.send_keys(phone_number)
        logger.info("phone_number entered in optional step")
        click_next_button(driver)
    except TimeoutException:
        logger.info("Optional step not present, continuing with normal flow")
        
def perform_search(driver, search_query):
    search_input_selector = "[data-testid='SearchBox_Search_Input']"
    try:
        search_input = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, search_input_selector))
        )
        
        # Attempt 1: Use clear() method
        search_input.clear()
        if not search_input.get_attribute('value'):
            logger.info("Input cleared successfully using clear() method")
        else:
            # Attempt 2: Use CTRL+A and BACKSPACE
            ActionChains(driver).click(search_input).key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).send_keys(Keys.BACKSPACE).perform()
            if not search_input.get_attribute('value'):
                logger.info("Input cleared successfully using CTRL+A and BACKSPACE")
            else:
                # Attempt 3: Send a series of BACKSPACE keys
                current_value = search_input.get_attribute('value')
                for _ in range(len(current_value)):
                    search_input.send_keys(Keys.BACKSPACE)
                if not search_input.get_attribute('value'):
                    logger.info("Input cleared successfully using multiple BACKSPACE keys")
                else:
                    logger.warning("Failed to clear input field")

        search_input.send_keys(search_query)
        search_input.send_keys(Keys.RETURN)
        logger.info(f"Search performed with query: {search_query}")
    except TimeoutException:
        logger.error("Search input not found")
        raise
    
    def check_login_status(driver):
        search_input_selector = "[data-testid='SearchBox_Search_Input']"
        try:
            search_input = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, search_input_selector))
            )
            return True
        except TimeoutException:
            return False
        
def perform_twitter_operation(url, search_queries, operation_type):
    global cache
    cache_key = f'{operation_type}_posts'
    
    if cache_key in cache:
        logger.info(f"Returning cached {operation_type} posts")
        return jsonify({"data": cache[cache_key]})
    
    if not search_queries:
        return jsonify({"error": "No search queries provided"}), 400

    driver = setup_driver()
    try:
        driver.get(url)
        login(driver)
        
        results = {}
        for search_query in search_queries:
            if operation_type == 'channel':
                success = perform_channel_search(driver, search_query)
            else:
                perform_search(driver, search_query)
                click_latest_button(driver)
            
            recent_posts = get_recent_posts(driver)
            results[search_query] = json.loads(recent_posts)

        cache[cache_key] = results
        return jsonify({"data": results})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        driver.quit()
        
def login(driver):
    username = os.getenv('TWITTER_USERNAME')
    password = os.getenv('TWITTER_PASSWORD')

    username_input = find_input_element(driver)
    username_input.send_keys(username)
    click_next_button(driver)

    handle_optional_step(driver)

    password_input = find_password_input(driver)
    password_input.send_keys(password)
    
    click_login_button(driver)