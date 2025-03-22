from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import os
import logging
import tempfile
import shutil
from pathlib import Path
import time
import uuid  # Added for unique directory names
import psutil  # Added for process management

from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)

class DriverService:
    def __init__(self):
        self.active_drivers = set()
        self.temp_dirs = set()
        self._cleanup_existing_chrome_dirs()

    def _kill_chrome_processes(self):
        """Selectively kill Chrome processes that were started by this application"""
        logger.info("Starting Chrome process cleanup")
        try:
            # Only kill Chrome processes that match our specific pattern or were created by this script
            # This prevents killing the user's regular Chrome instances
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    # Check if it's a Chrome process
                    if any(browser in proc.info['name'].lower() for browser in ['chrome', 'chromium', 'chromedriver']):
                        # Check if it's one of our Chrome instances by looking for our temp directory in command line
                        cmdline = proc.cmdline() if 'cmdline' in proc.info else []
                        is_our_chrome = False
                        
                        # Check if this is a Chrome instance we started
                        for temp_dir in self.temp_dirs:
                            if any(temp_dir in cmd for cmd in cmdline if isinstance(cmd, str)):
                                is_our_chrome = True
                                break
                        
                        # Only kill if it's our Chrome instance or has no command line (likely a zombie process)
                        if is_our_chrome or not cmdline:
                            logger.info(f"Terminating process: {proc.info['name']} (PID: {proc.pid})")
                            try:
                                proc.kill()
                                # Wait for process to terminate
                                gone, alive = psutil.wait_procs([proc], timeout=5)
                                for p in alive:
                                    logger.warning(f"Failed to kill process {p.pid}, using SIGKILL")
                                    os.kill(p.pid, 9)
                            except psutil.NoSuchProcess:
                                continue
                except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError, Exception) as e:
                    logger.debug(f"Error checking process: {str(e)}")
                    continue
            logger.info("Chrome process cleanup completed")
        except Exception as e:
            logger.error(f"Error during Chrome process cleanup: {str(e)}")

    def _cleanup_existing_chrome_dirs(self):
        """Clean up any existing Chrome user data directories"""
        self._kill_chrome_processes()
        try:
            temp_root = '/home/site/chrome-data'  # Fixed path for Azure environment
            logger.info(f"Cleaning up Chrome directories in {temp_root}")
            
            if os.path.exists(temp_root):
                for item in os.listdir(temp_root):
                    item_path = os.path.join(temp_root, item)
                    try:
                        if os.path.isdir(item_path):
                            shutil.rmtree(item_path, ignore_errors=True)
                            logger.info(f"Removed directory: {item_path}")
                        else:
                            os.remove(item_path)
                            logger.info(f"Removed file: {item_path}")
                    except Exception as e:
                        logger.warning(f"Error removing {item_path}: {str(e)}")
        except Exception as e:
            logger.error(f"Directory cleanup error: {str(e)}")

    def setup_driver(self):
        """Create new Chrome driver instance with unique user directory"""
        # Selectively clean up only our Chrome processes
        self._kill_chrome_processes()
        
        chrome_options = webdriver.ChromeOptions()
        logger.info("Setting up Chrome options")
        
        # Configure Chrome user directory - use different paths for local vs Azure
        if os.getenv('WEBSITE_HOSTNAME'):  # Running in Azure
            base_dir = '/home/site/chrome-data'
        else:  # Running locally
            # Use a directory in the user's temp folder to avoid conflicts
            base_dir = os.path.join(tempfile.gettempdir(), 'timehealer-chrome-data')
            
        logging.info(f"Using Chrome profile base directory: {base_dir}")
        os.makedirs(base_dir, exist_ok=True)
        
        # Create a unique profile directory for this session
        temp_dir = os.path.join(base_dir, f'profile_{uuid.uuid4()}')  # Unique UUID-based directory
        os.makedirs(temp_dir, exist_ok=True)
        
        # Set directory permissions
        try:
            os.chmod(temp_dir, 0o777)
            logger.info(f"Set permissions for directory: {temp_dir}")
        except Exception as e:
            logger.error(f"Error setting directory permissions: {str(e)}")

        self.temp_dirs.add(temp_dir)
        logger.info(f"Created new Chrome profile: {temp_dir}")

        # Performance optimizations
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Performance optimizations
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-infobars')
        chrome_options.add_argument('--disable-popup-blocking')
        chrome_options.add_argument('--disable-translate')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--no-first-run')
        chrome_options.add_argument('--dns-prefetch-disable')  # Can speed up initial connection
        chrome_options.add_argument('--disable-background-networking')
        
        # Set a realistic user agent for Windows 10 and latest Chrome
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')

        # Chrome configuration
        chrome_options.add_argument(f'--user-data-dir={temp_dir}')
        
        # Use a random debugging port to avoid conflicts with user's Chrome
        import random
        debug_port = random.randint(9222, 9999)
        chrome_options.add_argument(f'--remote-debugging-port={debug_port}')
        
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        # Determine if we should run headless based on environment
        # In Azure, always run headless. Locally, make it configurable
        if os.getenv('WEBSITE_HOSTNAME') or os.getenv('RUN_HEADLESS', 'false').lower() == 'true':
            chrome_options.add_argument('--headless=new')
            logger.info("Running Chrome in headless mode")
        else:
            logger.info("Running Chrome in visible mode")
            
        # Additional headless configuration for better screenshots
        chrome_options.add_argument('--hide-scrollbars')
        chrome_options.add_argument('--force-device-scale-factor=1')
        
        # Set up logging directory
        log_dir = os.path.join(os.getcwd(), 'logs', 'chrome')
        os.makedirs(log_dir, exist_ok=True)
        chrome_options.add_argument('--enable-logging')  # Enables Chrome's internal logging
        chrome_options.add_argument('--v=1')  # Verbose logging level
        chrome_options.add_argument(f'--log-path={os.path.join(log_dir, "chromedriver.log")}')
        
        # Additional options to make the browser appear more realistic
        chrome_options.add_argument('--disable-notifications')
        chrome_options.add_argument('--lang=en-US,en')
        chrome_options.add_argument('--start-maximized')

        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Set shorter page load timeout to prevent hanging
            driver.set_page_load_timeout(30)
            
            # Set shorter script timeout
            driver.set_script_timeout(20)
            
            # Execute CDP commands to prevent detection
            driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
            })
            
            # Preload Twitter login page to warm up the browser
            try:
                driver.get("https://x.com/i/flow/login")
                logger.info("Preloaded Twitter login page")
            except Exception as e:
                logger.warning(f"Error preloading Twitter login page: {str(e)}")
            
            # Execute JavaScript to prevent detection
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.active_drivers.add(driver)
            logger.info("Chrome driver initialized successfully")
            return driver
        except Exception as e:
            logger.error(f"Driver initialization failed: {str(e)}")
            # Cleanup failed instance
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
                self.temp_dirs.discard(temp_dir)
                logger.info(f"Cleaned up failed driver directory: {temp_dir}")
            except Exception as cleanup_error:
                logger.error(f"Directory cleanup error: {str(cleanup_error)}")
            raise

    def login(self, driver):
        username = os.getenv('TWITTER_USERNAME')
        password = os.getenv('TWITTER_PASSWORD')
        logging.info(f"Logging in with username: {username} and password: {password}")
        
        try:
            # Check if we're already on the login page, if not navigate to it
            if "login" not in driver.current_url.lower():
                logger.info("Navigating to login page")
                driver.get("https://x.com/i/flow/login")
                
            # Wait for page to be ready
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            
            # Find username field with reduced timeout but multiple attempts
            username_input = self.find_username_element(driver)
            if not username_input:
                raise Exception("Could not find username input field")
                
            username_input.clear()
            username_input.send_keys(username)
            print("username entered")
            logging.info("username entered")
            
            # Click next with retry
            self.click_next_button(driver)
            print("next button clicked")
            logging.info("next button clicked")
            
            # Handle optional verification step
            self.handle_optional_step(driver)
            print("optional step handled")
            logging.info("optional step handled")
            
            # Find password field with improved strategy
            password_input = self.find_password_input(driver)
            if not password_input:
                raise Exception("Could not find password input field")
                
            password_input.clear()
            password_input.send_keys(password)
            print("password entered")
            
            # Click login button with retry
            self.click_login_button(driver)
            print("login button clicked")
            
            # Wait briefly for login to process
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            raise Exception(f"Login failed: {str(e)}")

    def find_username_element(self, driver):
        logger.info("Finding username input field...")
        selectors = [
            (By.CSS_SELECTOR, "input[name='text'][autocomplete='username']"),
            (By.CSS_SELECTOR, "input.r-30o5oe.r-1dz5y72.r-13qz1uu"),
            (By.XPATH, "//input[@autocapitalize='sentences' and @autocomplete='username']"),
            (By.CSS_SELECTOR, "input[type='text'][dir='auto']"),
            (By.CSS_SELECTOR, "input[data-testid='ocfEnterTextTextInput']"),
            (By.CSS_SELECTOR, "input[autocomplete='username']"),
            (By.CSS_SELECTOR, "input[type='text']")
        ]
        
        # Try each selector with a short timeout
        for by, selector in selectors:
            try:
                logger.info(f"Trying username selector: {selector}")
                element = WebDriverWait(driver, 3).until(EC.presence_of_element_located((by, selector)))
                # Ensure element is visible and interactable
                if element.is_displayed() and element.is_enabled():
                    logger.info(f"Username input found with selector: {selector}")
                    return element
            except Exception:
                continue
                
        # If all quick attempts fail, try one more time with a longer timeout
        try:
            logger.info("Trying generic input selector with longer timeout")
            return WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text']"))
            )
        except Exception as e:
            logger.error(f"Could not find username input field: {str(e)}")
            return None
            
    def find_password_input(self, driver):
        logger.info("Finding password input field...")
        
        # First try to find the login form to narrow the search context
        form_context = None
        try:
            form_context = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "form[data-testid='LoginForm']"))
            )
            logger.info("Login form found, searching within form context")
        except TimeoutException:
            logger.warning("Login form not found, searching in entire page")
            form_context = driver
            
        selectors = [
            (By.CSS_SELECTOR, "input[name='password'][type='password']"),
            (By.CSS_SELECTOR, "input[autocomplete='current-password']"),
            (By.XPATH, "//input[@type='password' and contains(@class, 'r-30o5oe')]"),
            (By.CSS_SELECTOR, "input[type='password']"),
            (By.CSS_SELECTOR, "[data-testid='password-field']"),
            (By.XPATH, "//input[contains(@class, 'password-field')]"),
            (By.XPATH, "//div[contains(@class, 'LoginForm')]//input[@type='password']")
        ]
        
        # Try each selector with a short timeout first
        for by, selector in selectors:
            try:
                logger.info(f"Trying password selector: {selector}")
                if form_context == driver:
                    element = WebDriverWait(driver, 3).until(
                        EC.presence_of_element_located((by, selector))
                    )
                else:
                    # Search within the form if we found it
                    element = form_context.find_element(by, selector)
                    
                # Ensure element is visible and interactable
                if element.is_displayed() and element.is_enabled():
                    logger.info(f"Password input found with selector: {selector}")
                    return element
            except Exception:
                continue
                
        # If all quick attempts fail, try one more time with a longer timeout
        try:
            logger.info("Trying generic password selector with longer timeout")
            return WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']"))
            )
        except Exception as e:
            logger.error(f"Could not find password input field: {str(e)}")
            return None

    def click_next_button(self, driver):
        next_button_selectors = [
            (By.XPATH, "//button[@role='button']//span[contains(text(), 'Next')]"),
            (By.XPATH, "//div[@role='button']//span[contains(text(), 'Next')]"),
            (By.XPATH, "//*[contains(text(), 'Next')][@role='button']"),
            (By.XPATH, "//button[.//span[contains(text(), 'Next')]]")
        ]
        
        for by, selector in next_button_selectors:
            try:
                logger.info(f"Trying next button selector: {selector}")
                next_button = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((by, selector))
                )
                
                # Try regular click first
                try:
                    next_button.click()
                except Exception:
                    # If regular click fails, try JavaScript click
                    driver.execute_script("arguments[0].click();", next_button)
                    
                logger.info("Next button clicked successfully")
                return True
            except Exception:
                continue
                
        # If all quick attempts fail, try one more time with a longer timeout
        try:
            logger.info("Trying generic next button selector with longer timeout")
            next_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Next')]"))
            )
            driver.execute_script("arguments[0].click();", next_button)
            logger.info("Next button clicked successfully with longer timeout")
            return True
        except Exception as e:
            logger.error(f"Next button not found or not clickable: {str(e)}")
            raise Exception("Next button not found or not clickable")

    def click_login_button(self, driver):
        login_button_selectors = [
            (By.CSS_SELECTOR, "[data-testid='LoginForm_Login_Button']"),
            (By.XPATH, "//button[@role='button']//span[contains(text(), 'Log in')]"),
            (By.XPATH, "//div[@role='button' and contains(., 'Log in')]"),
            (By.XPATH, "//button[contains(., 'Log in')]")
        ]
        
        for by, selector in login_button_selectors:
            try:
                logger.info(f"Trying login button selector: {selector}")
                login_button = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((by, selector))
                )
                
                # Check if the button is disabled
                if login_button.get_attribute("disabled"):
                    logger.warning("Login button is disabled. Waiting for it to become enabled...")
                    WebDriverWait(driver, 5).until_not(
                        lambda d: login_button.get_attribute("disabled")
                    )
                
                # Try regular click first
                try:
                    login_button.click()
                except Exception:
                    # If regular click fails, try JavaScript click
                    driver.execute_script("arguments[0].click();", login_button)
                    
                logger.info("Login button clicked successfully")
                return True
            except Exception:
                continue
                
        # If all quick attempts fail, try one more time with a longer timeout
        try:
            logger.info("Trying generic login button selector with longer timeout")
            login_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Log in')]"))
            )
            driver.execute_script("arguments[0].click();", login_button)
            logger.info("Login button clicked successfully with longer timeout")
            return True
        except Exception as e:
            logger.error(f"Login button not found or not clickable: {str(e)}")
            raise Exception("Login button not found or not clickable")

    def handle_optional_step(self,driver):
        optional_step_text = "Enter your phone number or username"
        phone_number = os.getenv('TWITTER_PHONE_NUMBER')
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, f"//span[contains(text(), '{optional_step_text}')]"))
            )
            logger.info("Optional step detected")
            optional_input = WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[data-testid='ocfEnterTextTextInput']"))
            )
            optional_input.send_keys(phone_number)
            logger.info("phone_number entered in optional step")
            self.click_next_button(driver)
        except TimeoutException:
            logger.info("Optional step not present, continuing with normal flow")
            
    
            
    def scroll_page(self, driver, scroll_pause_time=1):
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            WebDriverWait(driver, scroll_pause_time).until(lambda d: d.execute_script("return document.readyState") == "complete")
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
            
    def take_screenshot(self, driver, name=None):
        """
        Take a screenshot and save it to a screenshots directory.
        Args:
            driver: The WebDriver instance
            name: Optional name for the screenshot (default: timestamp)
        Returns:
            str: Path to the saved screenshot
        """
        try:
            # Create screenshots directory if it doesn't exist
            screenshots_dir = os.path.join(os.getcwd(), 'screenshots')
            os.makedirs(screenshots_dir, exist_ok=True)
            
            # Set permissions for Azure
            os.chmod(screenshots_dir, 0o777)
            
            # Generate filename
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            filename = f"{name}_{timestamp}.png" if name else f"screenshot_{timestamp}.png"
            filepath = os.path.join(screenshots_dir, filename)
            
            # Set window size to ensure full page is captured
            driver.set_window_size(1920, 1080)
            
            # Take screenshot
            driver.save_screenshot(filepath)
            logger.info(f"Screenshot saved to: {filepath}")
            
            # Set permissions for the file
            os.chmod(filepath, 0o666)
            
            return filepath
        except Exception as e:
            logger.error(f"Failed to take screenshot: {str(e)}")
            return None

    def close_driver(self, driver):
        """Safely close a Chrome driver instance and clean up resources"""
        if not driver:
            return
            
        logger.info("Closing Chrome driver")
        try:
            # Remove from active drivers set
            self.active_drivers.discard(driver)
            
            # Get the user data directory before closing
            user_data_dir = None
            try:
                command_line = driver.execute_script(
                    "return window.navigator.userAgent;"
                )
                for temp_dir in self.temp_dirs:
                    if temp_dir in str(command_line):
                        user_data_dir = temp_dir
                        break
            except Exception as e:
                logger.debug(f"Could not retrieve user data directory: {str(e)}")
            
            # Close the driver
            try:
                driver.close()
                logger.info("Driver closed successfully")
            except Exception as e:
                logger.warning(f"Error closing driver: {str(e)}")
                
            # Quit the driver
            try:
                driver.quit()
                logger.info("Driver quit successfully")
            except Exception as e:
                logger.warning(f"Error quitting driver: {str(e)}")
            
            # Clean up the specific user data directory
            if user_data_dir and os.path.exists(user_data_dir):
                try:
                    shutil.rmtree(user_data_dir, ignore_errors=True)
                    self.temp_dirs.discard(user_data_dir)
                    logger.info(f"Removed user data directory: {user_data_dir}")
                except Exception as e:
                    logger.error(f"Error removing user data directory: {str(e)}")
        except Exception as e:
            logger.error(f"Error during driver cleanup: {str(e)}")

    def cleanup_driver(self, driver):
        """Safely cleanup a specific driver instance"""
        if driver:
            try:
                driver.quit()
                logger.info("Driver quit successfully")
            except Exception as e:
                logger.error(f"Error quitting driver: {str(e)}")
            finally:
                self._kill_chrome_processes()
                self.active_drivers.discard(driver)
                
                # Cleanup associated directories
                for temp_dir in list(self.temp_dirs):
                    try:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        self.temp_dirs.discard(temp_dir)
                        logger.info(f"Cleaned up directory: {temp_dir}")
                    except Exception as e:
                        logger.error(f"Directory cleanup error: {str(e)}")

    def cleanup_all_drivers(self):
        """Cleanup all driver instances"""
        logger.info("Cleaning up all drivers")
        for driver in list(self.active_drivers):
            self.cleanup_driver(driver)
        self.active_drivers.clear()

    def check_login_status(self,driver):
        search_input_selector = "[data-testid='SearchBox_Search_Input']"
        try:
            search_input = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, search_input_selector))
            )
            return True
        except TimeoutException:
            return False

    def click_latest_button(self, driver):
        """Click the 'Latest' button on Twitter search results to get the most recent tweets"""
        logger.info("Attempting to click 'Latest' button")
        try:
            # Wait for search results to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="primaryColumn"]'))
            )
            
            # Try multiple selectors for the Latest tab
            latest_button_selectors = [
                '[data-testid="tab-latest"]',
                '[role="tab"][aria-selected="false"]:nth-child(2)',
                'a[href*="f=live"]',
                'span:contains("Latest")',
                '[data-testid="ScrollSnap-List"] div:nth-child(2)'
            ]
            
            # Try each selector
            for selector in latest_button_selectors:
                try:
                    # First check if element exists
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        # Try to click the first one
                        elements[0].click()
                        logger.info(f"Clicked 'Latest' button using selector: {selector}")
                        # Wait for content to update
                        time.sleep(2)
                        return True
                except Exception as e:
                    logger.debug(f"Failed to click using selector {selector}: {str(e)}")
            
            # If CSS selectors fail, try JavaScript approach
            try:
                # Try to find and click using JavaScript
                driver.execute_script("""
                    // Try to find Latest tab by text content
                    const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
                    const latestTab = tabs.find(tab => 
                        tab.textContent.toLowerCase().includes('latest') || 
                        tab.getAttribute('href')?.includes('f=live')
                    );
                    
                    if (latestTab) {
                        latestTab.click();
                        return true;
                    }
                    
                    // Try to find by position (usually second tab)
                    const tabList = document.querySelector('[role="tablist"]');
                    if (tabList) {
                        const secondTab = tabList.children[1];
                        if (secondTab) {
                            secondTab.click();
                            return true;
                        }
                    }
                    
                    return false;
                """)
                logger.info("Attempted to click 'Latest' button using JavaScript")
                time.sleep(2)
            except Exception as e:
                logger.warning(f"JavaScript click attempt failed: {str(e)}")
            
            # If we get here, we couldn't find the Latest button
            logger.warning("Could not find 'Latest' button, continuing with default results")
            return False
            
        except Exception as e:
            logger.error(f"Error clicking 'Latest' button: {str(e)}")
            return False