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
        """Forcefully kill all Chrome-related processes with improved reliability"""
        logger.info("Starting Chrome process cleanup")
        try:
            for proc in psutil.process_iter(['pid', 'name', 'status']):
                try:
                    if any(browser in proc.info['name'].lower() for browser in ['chrome', 'chromium', 'chromedriver']):
                        logger.info(f"Terminating process: {proc.info}")
                        try:
                            proc.kill()
                            # Wait for process to terminate
                            gone, alive = psutil.wait_procs([proc], timeout=5)
                            for p in alive:
                                logger.warning(f"Failed to kill process {p.pid}, using SIGKILL")
                                os.kill(p.pid, 9)
                        except psutil.NoSuchProcess:
                            continue
                except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError):
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
        self._kill_chrome_processes()
        chrome_options = webdriver.ChromeOptions()
        logger.info("CHROME OPTIONS", chrome_options)
        # Configure Chrome user directory
        base_dir = '/home/site/chrome-data'
        logging.info("BASE DIR", base_dir)
        temp_dir = os.path.join(base_dir, f'profile_{uuid.uuid4()}')  # Unique UUID-based directory
        os.makedirs(temp_dir, exist_ok=True)
        
        # Set directory permissions (crucial for Azure)
        try:
            os.chmod(temp_dir, 0o777)
            logger.info(f"Set permissions for directory: {temp_dir}")
        except Exception as e:
            logger.error(f"Error setting directory permissions: {str(e)}")

        self.temp_dirs.add(temp_dir)
        logger.info(f"Created new Chrome profile: {temp_dir}")

        # Anti-detection measures
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Set a realistic user agent for Windows 10 and latest Chrome
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')

        # Chrome configuration
        chrome_options.add_argument(f'--user-data-dir={temp_dir}')
        chrome_options.add_argument('--remote-debugging-port=0')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--headless=new')  # Enable headless mode for production
        # Additional headless configuration for better screenshots
        chrome_options.add_argument('--hide-scrollbars')
        chrome_options.add_argument('--force-device-scale-factor=1')
        
        chrome_options.add_argument('--enable-logging')  # Enables Chrome's internal logging
        chrome_options.add_argument('--v=1')  # Verbose logging level
        chrome_options.add_argument(f'--log-path=/home/site/wwwroot/logs/chrome/chromedriver.log')
        
        # Additional options to make the browser appear more realistic
        chrome_options.add_argument('--disable-notifications')
        chrome_options.add_argument('--lang=en-US,en')
        chrome_options.add_argument('--start-maximized')

        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Execute CDP commands to prevent detection
            driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
            })
            
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

    def take_screenshot(self, driver, name=None):
        """
        Take a screenshot and save it to a screenshots directory in wwwroot.
        Args:
            driver: The WebDriver instance
            name: Optional name for the screenshot (default: timestamp)
        Returns:
            str: Path to the saved screenshot
        """
        try:
            # Create screenshots directory in wwwroot
            screenshots_dir = '/home/site/wwwroot/screenshots'
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

    def login(self, driver):
        username = os.getenv('TWITTER_USERNAME')
        password = os.getenv('TWITTER_PASSWORD')
        logging.info(f"Logging in with username: {username} and password: {password}")
        try:
            username_input = self.find_username_element(driver)
            username_input.send_keys(username)
            print("username entered")
            self.take_screenshot(driver, "login_page")
            logging.info("username entered")
            self.click_next_button(driver)
            print("next button clicked")
            logging.info("next button clicked")
            self.take_screenshot(driver, "optional_step_page")
            self.handle_optional_step(driver)
            print("optional step handled")
            logging.info("optional step handled")
            self.take_screenshot(driver, "password_page")
            password_input = self.find_password_input(driver)
            password_input.send_keys(password)
            print("password entered")
            self.click_login_button(driver)
            print("login button clicked")
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            raise Exception("Login failed")

    def find_username_element(self,driver):
        selectors = [
            (By.CSS_SELECTOR, "input[name='text'][autocomplete='username']"),
            (By.CSS_SELECTOR, "input.r-30o5oe.r-1dz5y72.r-13qz1uu"),
            (By.XPATH, "//input[@autocapitalize='sentences' and @autocomplete='username']"),
            (By.CSS_SELECTOR, "input[type='text'][dir='auto']"),
        ]
        for by, selector in selectors:
            try:
                return WebDriverWait(driver, 5).until(EC.presence_of_element_located((by, selector)))
            except TimeoutException:
                continue
        raise NoSuchElementException("Could not find username input field")

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
            
    
            
    def find_password_input(self,driver):
        logger.info("Finding password input field...")
        # First wait for password form/container to be present
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "form[data-testid='LoginForm']"))
            )
            logger.info("Login form found, searching for password input...")
        except TimeoutException:
            logger.warning("Login form not found, attempting to find password input directly...")

        selectors = [
            (By.CSS_SELECTOR, "input[name='password'][type='password']"),
            (By.CSS_SELECTOR, "input[autocomplete='current-password']"),
            (By.XPATH, "//input[@type='password' and contains(@class, 'r-30o5oe')]"),
            (By.CSS_SELECTOR, "input[type='password']"),
            (By.CSS_SELECTOR, "[data-testid='password-field']"),
            (By.XPATH, "//input[contains(@class, 'password-field')]"),
            (By.XPATH, "//div[contains(@class, 'LoginForm')]//input[@type='password']")
        ]
        
        for by, selector in selectors:
            try:
                logger.info(f"Trying selector: {selector}")
                element = WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((by, selector))
                )
                # Additional check to ensure element is interactable
                WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((by, selector))
                )
                logger.info("Password input field found successfully")
                return element
            except TimeoutException:
                logger.debug(f"Selector {selector} not found, trying next...")
                continue
            
        error_msg = "Could not find password input field after trying all selectors"
        logger.error(error_msg)
        raise NoSuchElementException(error_msg)


    def click_latest_button(self, driver):
        try:
            # Increase wait time and add multiple selectors for better reliability
            selectors = [
                "//span[text()='Latest']",
                "//span[contains(text(),'Latest')]",
                "//*[@role='tab']//span[text()='Latest']"
            ]
            
            latest_button = None
            for selector in selectors:
                try:
                    latest_button = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    # Ensure element is in viewport
                    driver.execute_script("arguments[0].scrollIntoView(true);", latest_button)
                    # Add a small wait after scroll
                    WebDriverWait(driver, 2).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    break
                except TimeoutException:
                    continue
            
            if latest_button is None:
                raise TimeoutException("Latest button not found with any selector")
                
            # Try JavaScript click if regular click fails
            try:
                latest_button.click()
            except Exception:
                driver.execute_script("arguments[0].click();", latest_button)
                
        except TimeoutException:
            logger.warning("Latest button not found or not clickable after trying all selectors")
            raise
        except Exception as e:
            logger.error(f"Error clicking latest button: {str(e)}")
            raise

    def scroll_page(self, driver, scroll_pause_time=1):
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            WebDriverWait(driver, scroll_pause_time).until(lambda d: d.execute_script("return document.readyState") == "complete")
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
            
    def click_next_button(self,driver):
        next_button_xpath = "//button[@role='button']//span[contains(text(), 'Next')]"
        try:
            next_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, next_button_xpath))
            )
            next_button.click()
            logger.info("Next button clicked successfully")
        except Exception as e:
            logger.error("Next button not found or not clickable")
            raise Exception("Next button not found or not clickable")

    def click_login_button(self,driver):
        login_button_selector = "[data-testid='LoginForm_Login_Button']"
        try:
            login_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, login_button_selector))
            )
            # Check if the button is disabled
            if login_button.get_attribute("disabled"):
                logger.warning("Login button is disabled. Waiting for it to become enabled...")
                WebDriverWait(driver, 5).until_not(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, login_button_selector + "[disabled]"))
                )
                login_button = driver.find_element(By.CSS_SELECTOR, login_button_selector)
            
            login_button.click()
            logger.info("Login button clicked successfully")
        except TimeoutException:
            logger.error("Login button not found or not clickable")
            raise
        
    def check_login_status(self,driver):
        search_input_selector = "[data-testid='SearchBox_Search_Input']"
        try:
            search_input = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, search_input_selector))
            )
            return True
        except TimeoutException:
            return False