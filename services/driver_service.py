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

from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)

class DriverService:
    def __init__(self):
        self.active_drivers = set()
        self.temp_dirs = set()
        # Clean up any existing Chrome user data directories at startup
        self._cleanup_existing_chrome_dirs()

    def _kill_chrome_processes(self):
        """Forcefully kill all Chrome-related processes"""
        try:
            import psutil
            for proc in psutil.process_iter(['name', 'pid', 'status']):
                try:
                    # Check for both 'chrome' and 'chromium' processes
                    if any(browser in proc.info['name'].lower() for browser in ['chrome', 'chromium']):
                        logger.info(f"Found Chrome process: PID={proc.info['pid']}, Status={proc.info['status']}")
                        try:
                            # First try SIGTERM
                            proc.terminate()
                            try:
                                proc.wait(timeout=3)
                            except psutil.TimeoutExpired:
                                # If SIGTERM didn't work, use SIGKILL
                                logger.warning(f"Process {proc.info['pid']} didn't terminate, using SIGKILL")
                                proc.kill()
                                proc.wait(timeout=3)
                        except psutil.NoSuchProcess:
                            logger.info(f"Process {proc.info['pid']} already terminated")
                        except Exception as e:
                            logger.error(f"Failed to kill process {proc.info['pid']}: {str(e)}")
                            
                        # Double check if process is really gone
                        try:
                            if psutil.pid_exists(proc.info['pid']):
                                logger.error(f"Process {proc.info['pid']} still exists after kill attempt")
                            else:
                                logger.info(f"Successfully terminated process {proc.info['pid']}")
                        except:
                            pass
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    logger.warning(f"Error accessing process: {str(e)}")
        except ImportError:
            logger.warning("psutil not available for Chrome process cleanup")
        except Exception as e:
            logger.error(f"Error during Chrome process cleanup: {str(e)}", exc_info=True)

    def _cleanup_existing_chrome_dirs(self):
        """Clean up any existing Chrome user data directories and processes in the temp folder"""
        try:
            # First, kill all Chrome processes
            self._kill_chrome_processes()
            
            # Then clean up directories
            temp_root = tempfile.gettempdir()
            logger.info(f"Cleaning up Chrome directories in {temp_root}")
            
            # Look for both Chrome user data directories and any other Chrome-related temp files
            chrome_patterns = [
                'chrome_user_data_*',
                'chrome-*',
                'chromium-*',
                '.com.google.chrome.*',
                'chrome_*',
                '*Chrome*'
            ]
            
            import glob
            for pattern in chrome_patterns:
                pattern_path = os.path.join(temp_root, pattern)
                for item_path in glob.glob(pattern_path):
                    if os.path.isdir(item_path):
                        try:
                            logger.info(f"Removing Chrome-related directory: {item_path}")
                            shutil.rmtree(item_path, ignore_errors=True)
                        except Exception as e:
                            logger.warning(f"Failed to remove Chrome directory {item_path}: {str(e)}")
                    elif os.path.isfile(item_path):
                        try:
                            logger.info(f"Removing Chrome-related file: {item_path}")
                            os.remove(item_path)
                        except Exception as e:
                            logger.warning(f"Failed to remove Chrome file {item_path}: {str(e)}")
            
            # Verify cleanup
            remaining_chrome_dirs = []
            for pattern in chrome_patterns:
                pattern_path = os.path.join(temp_root, pattern)
                remaining_chrome_dirs.extend(glob.glob(pattern_path))
            
            if remaining_chrome_dirs:
                logger.warning(f"Some Chrome directories could not be removed: {remaining_chrome_dirs}")
            else:
                logger.info("Chrome directory cleanup completed successfully")
                
        except Exception as e:
            logger.error(f"Error during Chrome cleanup: {str(e)}", exc_info=True)

    def setup_driver(self):
        # Kill any existing Chrome processes before starting
        self._kill_chrome_processes()
        
        chrome_options = webdriver.ChromeOptions()
        
        # Use dedicated Chrome data directory with unique subdirectory
        base_dir = '/home/site/chrome-data'
        temp_dir = os.path.join(base_dir, f'profile_{int(time.time())}_{os.getpid()}')
        os.makedirs(temp_dir, exist_ok=True)
        logger.info(f"Created new Chrome user data directory: {temp_dir}")
        
        # Verify the directory is empty and accessible
        if os.path.exists(temp_dir):
            contents = os.listdir(temp_dir)
            if contents:
                logger.warning(f"New temp directory is not empty: {contents}")
            
            # Verify permissions
            try:
                test_file = os.path.join(temp_dir, 'test.txt')
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                logger.info("Successfully verified temp directory permissions")
            except Exception as e:
                logger.error(f"Permission test failed on temp directory: {str(e)}")
        
        self.temp_dirs.add(temp_dir)
        
        # Chrome configuration
        chrome_options.add_argument(f'--user-data-dir={temp_dir}')
        chrome_options.add_argument('--remote-debugging-port=0')  # Use random port
        chrome_options.add_argument('--no-first-run')
        chrome_options.add_argument('--no-service-autorun')
        chrome_options.add_argument('--password-store=basic')
        chrome_options.add_argument('--no-default-browser-check')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-background-networking')
        chrome_options.add_argument('--disable-default-apps')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-sync')
        chrome_options.add_argument('--disable-translate')
        chrome_options.add_argument('--metrics-recording-only')
        chrome_options.add_argument('--mute-audio')
        chrome_options.add_argument('--no-first-run')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('--disable-notifications')
        chrome_options.add_argument('--disable-popup-blocking')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        try:
            service = Service(ChromeDriverManager().install())
            print("ABOUT TO HAVE AN ERROR")
            driver = webdriver.Chrome(service=service, options=chrome_options)
            self.active_drivers.add(driver)
            logger.info("Successfully created new Chrome driver instance")
            return driver
        except Exception as e:
            logger.error(f"Failed to create Chrome driver: {str(e)}", exc_info=True)
            # Clean up the temp directory if driver creation failed
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
                self.temp_dirs.remove(temp_dir)
                logger.info(f"Cleaned up temp directory after failed driver creation: {temp_dir}")
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up temp directory: {str(cleanup_error)}")
            raise

    def cleanup_driver(self, driver):
        """Safely cleanup a specific driver instance"""
        if driver:
            try:
                driver.quit()
            except Exception as e:
                logger.error(f"Error cleaning up driver: {str(e)}")
            finally:
                # Kill any remaining Chrome processes
                self._kill_chrome_processes()
                
                if driver in self.active_drivers:
                    self.active_drivers.remove(driver)
                # Clean up the temporary directory after the driver is quit
                for temp_dir in list(self.temp_dirs):
                    try:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        self.temp_dirs.remove(temp_dir)
                    except Exception as e:
                        logger.error(f"Error cleaning up temporary directory {temp_dir}: {str(e)}")

    def cleanup_all_drivers(self):
        """Cleanup all active driver instances"""
        for driver in list(self.active_drivers):
            self.cleanup_driver(driver)
        self.active_drivers.clear()

    def login(self, driver):
        username = os.getenv('TWITTER_USERNAME')
        password = os.getenv('TWITTER_PASSWORD')

        try:
            username_input = self.find_username_element(driver)
            username_input.send_keys(username)
            print("username entered")
            self.click_next_button(driver)
            print("next button clicked")
            self.handle_optional_step(driver)
            print("optional step handled")
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
            WebDriverWait(driver, 3).until(
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
        print("Finding password input")
        selectors = [
            (By.CSS_SELECTOR, "input[name='password'][type='password']"),
            (By.CSS_SELECTOR, "input[autocomplete='current-password']"),
            (By.XPATH, "//input[@type='password' and contains(@class, 'r-30o5oe')]"),
        ]
        for by, selector in selectors:
            try:
                return WebDriverWait(driver, 3).until(EC.presence_of_element_located((by, selector)))
            except TimeoutException:
                continue
        raise NoSuchElementException("Could not find password input field")


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