from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import os
import logging

from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)

class DriverService:
    def __init__(self):
        self.active_drivers = set()

    def setup_driver(self):
        chrome_options = webdriver.ChromeOptions()
        # chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        # Version mismatch handling
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--ignore-certificate-errors')
        
        # Stealth settings
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('--disable-notifications')
        chrome_options.add_argument('--disable-popup-blocking')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        self.active_drivers.add(driver)
        return driver

    def cleanup_driver(self, driver):
        """Safely cleanup a specific driver instance"""
        if driver:
            try:
                driver.quit()
            except Exception as e:
                logger.error(f"Error cleaning up driver: {str(e)}")
            finally:
                if driver in self.active_drivers:
                    self.active_drivers.remove(driver)

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