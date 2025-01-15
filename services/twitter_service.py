from datetime import UTC, datetime
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from flask import jsonify
import json
import logging
import os
from models.twitter_result import TwitterResult
import time

logger = logging.getLogger(__name__)

class TwitterService:
    def __init__(self, driver_service, cache_service):
        self.driver_service = driver_service
        self.cache_service = cache_service
        self.base_url = os.getenv('TWITTER_BASE_URL', 'https://x.com')  # Default to 'https://x.com' if not set

    def perform_twitter_operation(self, url, search_queries, operation_type, isDefault=False):
        cache_key = f'{operation_type}_posts_isDefault_{isDefault}'
        
        if self.cache_service.has(cache_key):
            logger.info(f"Returning cached {operation_type} posts")
            return self.cache_service.get(cache_key), []
        
        if not search_queries:
            return None, ["No search queries provided"]

        driver = None
        results = {}
        errors = []
        try:
            driver = self.driver_service.setup_driver()
            # driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            #     'source': '''
            #         Object.defineProperty(navigator, 'webdriver', {
            #             get: () => undefined
            #         })
            #     '''
            # })
            driver.get(url)
            self.driver_service.login(driver)
            
            self.check_login_success(driver)
            #self.wait_for_login_page_load(driver)

            
            print("Waiting for page to load")
            print("Page loaded")
            driver.maximize_window() 
            for search_query in search_queries:
                try:
                    if operation_type == 'channel':
                        print(f"Performing channel search for {search_query}")
                        self.perform_channel_search(driver, search_query)
                    else:
                        self.perform_search(driver, search_query)
                        self.driver_service.click_latest_button(driver)
                    
                    recent_posts = self.get_recent_posts(driver)
                    results[search_query] = json.loads(recent_posts)
                except Exception as e:
                    error_message = f"Error processing query '{search_query}': {str(e)}"
                    logger.error(error_message)
                    errors.append(error_message)

            self.cache_service.set(cache_key, results)
            return results, errors

        except Exception as e:
            error_message = f"Error in perform_twitter_operation: {str(e)}"
            print("Encountered error in perform_twitter_operation")
            logger.error(error_message)
            errors.append(error_message)
            return None, errors
        finally:
            if driver:
                driver.quit()

    def perform_channel_search(self, driver, search_query):
        url = f"{self.base_url}/{search_query}"
        try:
            driver.get(url)
            # Wait for either the ScrollSnap-List or the "account doesn't exist" message
            element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="ScrollSnap-List"], [data-testid="emptyState"]'))
            )
        
            # Check if the account doesn't exist
            if element.get_attribute('data-testid') == 'emptyState':
                logger.info(f"Account {search_query} doesn't exist")
                raise Exception(f"Account {search_query} doesn't exist")
            
            logger.info(f"Channel Search performed successfully for query: {search_query}")
        except TimeoutException:
            logger.error(f"Timeout while searching for channel: {search_query}")
            raise;
        except Exception as e:
            logger.error(f"Error during channel search for {search_query}: {str(e)}")
            raise;
    
    def check_login_success(self, driver):
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="SideNav_AccountSwitcher_Button"]'))
            )
            logger.info("Login successful")
            return True
        except TimeoutException:
            logger.error("Login failed")
            raise Exception("Login failed")
        except Exception as e:
            logger.error(f"Error during login check: {str(e)}")
            raise;
        
    def wait_for_login_page_load(self, driver, timeout=10):
        try:
            # Wait for the account switcher button to be present (indicates successful login)
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="SideNav_AccountSwitcher_Button"]'))
            )
            
            # Wait for the main content area to be present
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'main[role="main"]'))
            )
            
            # Wait for network requests to complete (this is a custom condition)
            WebDriverWait(driver, timeout).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            
            logger.info("Page fully loaded and user logged in")
        except TimeoutException:
            logger.error("Timeout waiting for page to load or login to complete")
            raise Exception("Page load or login timeout")
        except Exception as e:
            logger.error(f"Error during page load wait: {str(e)}")
            raise
        
    def perform_search(self, driver, search_query):
        search_input_selector = "[data-testid='SearchBox_Search_Input']"
        try:
            search_input = WebDriverWait(driver, 5).until(
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
            raise;
        except Exception as e:
            logger.error(f"Error during search for {search_query}: {str(e)}")
            raise;
        
    def get_recent_posts(self, driver, num_posts=5):
        try:
            # Wait for tweets to load
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "article[data-testid='tweet']"))
                )
                
                # Get the page source and parse it with BeautifulSoup
                page_source = driver.page_source
                soup = BeautifulSoup(page_source, 'html.parser')
                # print(soup.prettify())
                # time.sleep(10)
                # Find all tweet articles
                tweets = soup.find_all('article', attrs={'data-testid': 'tweet'})
                # print("TWEETS", tweets)
                # time.sleep(10)
                recent_posts = []
                print(f"Number of tweets: {len(tweets)}")
                # pause any execution here so I can examine what the automated browser is seeing
                for tweet in tweets[:num_posts]:
                    try:
                        embed_url = self.__extract_tweet_url(tweet)
                        print(f"Embed URL: {embed_url}")
                        if self.is_invalid_embed_url(embed_url):
                            print(f"Invalid embed URL: {embed_url}")
                            continue;
                        
                        full_name = tweet.find('div', attrs={'data-testid': 'User-Name'}).text
                        channel, username = full_name.split('@', 1)
                        username = '@' + username  # Add @ back to the username
                        # Extract tweet text
                        tweet_text = tweet.find('div', attrs={'data-testid': 'tweetText'}).text if tweet.find('div', attrs={'data-testid': 'tweetText'}) else ''
                        # Extract timestamp
                        
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
                    except Exception as e:
                        logger.error(f"Error during tweet processing: {str(e)}")
                        continue;
                  
                logger.info(f"Retrieved {len(recent_posts)} recent posts")
                #input("Press Enter to continue...")
                tweet_dicts = [tweet.__dict__ for tweet in recent_posts]

                # Convert the list of dictionaries to JSON
                json_data = json.dumps(tweet_dicts, default=self.__datetime_to_iso)
                return json_data
        except Exception as e:
            logger.error(f"Error retrieving recent posts: {str(e)}")
            raise;
    
    
    # private method region
    def __extract_tweet_url(self, tweet_div):
        # Look for a link with data-testid="tweetText"
        tweet_link = tweet_div.find('a', {'data-testid': 'tweetText'})
        
        if tweet_link and 'href' in tweet_link.attrs:
            # Extract the relative URL
            relative_url = tweet_link['href']
            
            # Construct the full URL
            full_url = f"{self.base_url}{relative_url}"
            return full_url
        
        # Fallback: look for any link containing "/status/"
        status_link = tweet_div.find('a', href=lambda href: href and '/status/' in href)
        
        if status_link and 'href' in status_link.attrs:
            relative_url = status_link['href']
            full_url = f"{self.base_url}{relative_url}"
            return full_url
        
        # If no suitable link is found
        return None

    def __datetime_to_iso(self,obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError("Type not serializable")
    
    def is_invalid_embed_url(self, embed_url):
        return not embed_url or embed_url == '' or embed_url.strip().endswith('/analytics')
