import logging
import os
import random
import re
import requests
import selenium
import shutil
import time
import traceback

from bs4 import BeautifulSoup
from copy import deepcopy
from html.parser import HTMLParser
from os.path import (exists,join,isdir,isfile)
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from typing import List, Any
from urllib.request import urlopen, urlretrieve
from webdriver_manager.chrome import ChromeDriverManager

# local dependencies
from config import *
from util import *


class InspireCom:

    def __init__(self, diagnosis=None, tracker_fn=None, headless=True):
        # Each instance is responsible for scraping images for one diagnosis.Let's do it slowly.

        # shall go to https://www.inspire.com/search/posts/?query=&p=1&sec=&g=&r=0&s=false
        self.base_url = 'https://www.inspire.com/search/posts/?query=&p=1&sec=&g=&r=0&s=false'
        self.diagnosis, self.headless = diagnosis, headless
        # get a driver object
        self.driver = InspireCom.init_driver(self.headless)
        # tracker file
        self.tracker_fn = tracker_fn
        # default delay time for page loading (unit in seconds)
        self.delay = 10

    def log_in(self):
        '''Logs in with credentials.'''
        print('[{}] Signing in with credentials...'.format(InspireCom.log_in.__name__))
        time.sleep(5)
        username, password = get_login_credential()

        num_tries, max_allow = 0, 1

        while num_tries < max_allow:            
            # find username and password button, assuming we can find it normally
            try:
                username_button, password_button = InspireCom.find_username_and_password_button(self.driver)
                print('[{}] found the two buttons rather easily, we can leave'.format(
                    InspireCom.log_in.__name__))
                break
            except Exception as e:
                # try one more click
                print('[{}] trying to find another log-in button that navigates us to credential signing page...'.format(
                    InspireCom.log_in.__name__))
                num_tries += 1
                #time.sleep(1000)
                # to the 'Log In' button in the middle of the page
                mid_login_button = self.driver.find_element_by_link_text('/signin.pl?slt=itt')
                print('DEBUG: ', mid_login_button)
                mid_login_button.click()

        username_button.send_keys(username)
        password_button.send_keys(password)

        # login submit
        submit_button = self.driver.find_element_by_xpath("//button[@name='submit' and @type='submit']")
        submit_button.click()

        print('[{}] Signed in successfully!'.format(InspireCom.log_in.__name__))
        time.sleep(random.randint(2, 5))

    def tear_down(self):
        try:
            self.driver.quit()
        except Exception as e:
            logging.exception(e)
            pass

    def scrape_worker(self, op_dir='./data'):
        '''Major worker function responsible for scraping images for one diagnosis.'''
        # [1] Preparation
        url, split_token = self.base_url, 'query='
        url = url.split(split_token)[0] + split_token + self.diagnosis + url.split(split_token)[-1]
        self.driver.get(url)
        time.sleep(10)

        # require login or not?
        login_button = None
        try:
            login_button = self.driver.find_element_by_xpath("//a[contains(text(),'{}') and @class='noTextDec nav__authBtn options__link']".format(
                "Log In "
            ))
        except Exception as e:
            logging.exception(e)
            print('[{}] Could not find login button!'.format(InspireCom.scrape_worker.__name__))

        # if asks us to login, do it
        if login_button:
            login_button.click()
            print('[{}] it requires us to sign in...'.format(InspireCom.scrape_worker.__name__))
            try:
                self.log_in()
                # re-get the url with query string b\c the page has been refreshed
                new_url = url
                new_url = '&'.join([x for x in new_url.split('&')[:-2]]) + '&s=false'
                self.driver.get(new_url)
            except Exception as e:
                logging.exception(e)
                print(f'[{InspireCom.scrape_worker.__name__}] Error={e} occurs, shutting down...')
                self.tear_down()

        # [2] Proceed for downloading
        # if not specified op_dir, make one
        cur_op_dir = op_dir + '/' + self.diagnosis
        if not exists(cur_op_dir):
            os.makedirs(cur_op_dir)

        # keep expanding the 'show me more' button
        show_more_button = None
        while True:
            try:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                show_more_button = WebDriverWait(self.driver, self.delay).until(
                    EC.presence_of_element_located((By.XPATH, "//button[contains(text(),'{}')]".format('Show me more...')))
                )
            except Exception as e:
                break
            if show_more_button is None:
                print('[{}] no \'show me more\' button found!'.format(InspireCom.scrape_worker.__name__))
                break
            else:
                print('[{}] finds one \'show me more\' button, click, scroll to bottom and wait!'.format(
                    InspireCom.scrape_worker.__name__))
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                try:
                    show_more_button.click()
                except Exception as e:
                    break
                time.sleep(random.randint(2,5))

        # [3] Find all relevant links
        # process current page
        page = self.driver.find_element_by_xpath('//*').get_attribute('outerHTML')
        soup = BeautifulSoup(page, 'lxml')
        # find all posts
        posts = soup.find_all('h2', attrs={'class': 'post__title'})
        # find their immediate parents, those are the href links we actually want
        root_url = 'https://www.inspire.com'
        href_links = []
        for post in posts:
            href_links.append(root_url + post.parent.get('href'))

        num_links, scraped_links, failed_links = len(href_links), 0, 0
        print(f'[{InspireCom.scrape_worker.__name__}] total number href links found: {num_links}')

        # [4] Open link one by one, do the dirty work
        # write to a tracker
        InspireCom.write2tracker(self.tracker_fn, self.diagnosis, num_links, True)
        # if cannot find any link, directly terminate
        if num_links == 0:
            InspireCom.write2tracker(self.tracker_fn, self.diagnosis, num_links, False)
            return

        # keep scraping links, while not allow failure rate to exceed 50%
        print('[{}] start to work on each link...'.format(InspireCom.scrape_worker.__name__))
        while scraped_links < num_links and failed_links < 0.5 * num_links:
            # grab a link
            href_link = href_links.pop(0)
            # make a subdirectory to store
            temp_op_dir = cur_op_dir + '/link=' + str(scraped_links)
            if not exists(temp_op_dir):
                os.makedirs(temp_op_dir)
            # do it
            res = InspireCom.scrape_one_post(href_link, temp_op_dir, self.headless)
            if res is True:
                scraped_links += 1
            else:
                failed_links += 1
            time.sleep(random.randint(1, 2))

        # write a tracker fn
        InspireCom.write2tracker(self.tracker_fn, self.diagnosis, scraped_links, False)

    @staticmethod
    def scrape_one_post(link, op_dir, headless):
        '''Given an url link with the post and image we want, download them.'''
        driver = InspireCom.init_driver(headless)
        driver.get(link)
        print('[{}] Loading new page...'.format(InspireCom.scrape_one_post.__name__))
        time.sleep(random.randint(1, 2))
        scrape_res = False

        # locate and store post content
        post_ele = driver.find_element_by_xpath("//p[@id='post-inner-content']")
        post_op_fn, post_content = join(op_dir, 'post_content.txt'), f'Original Post URL: {link}\n--------[ Separator Line ]----------\n' + post_ele.text
        InspireCom.write_post_content(post_content, post_op_fn)
        # if we save the post, consider True
        scrape_res = True

        # if we need to login again to see the photos
        img_ele = None
        img_ele = WebDriverWait(driver, random.randint(2, 4)).until(
            EC.presence_of_element_located((By.XPATH, "//img[@alt='Log in to see member uploaded photos.']"))
        )
        if img_ele is not None:
            InspireCom.re_login_post_page(driver)
        print('[{}] we already logged in; move on to find all images and store locally'.format(InspireCom.scrape_one_post.__name__))

        # retrieve the images
        loaded_imgs = driver.find_element_by_class_name('lozad')
        # filter
        loaded_imgs = list(map(lambda x: str(x.get_attribute('data-src')), loaded_imgs))
        loaded_imgs = list(filter(lambda x: x.startswith('https:'), loaded_imgs))
        # load and save
        for idx, img_link in enumerate(loaded_imgs):
            img_fn = join(op_dir, str(idx + 1) + '.jpg')
            urlretrieve(img_link, img_fn)

        return scrape_res

    @staticmethod
    def init_driver(headless=True):
        '''Returns a new web driver object.'''

        # incongito mode
        chrome_options = webdriver.ChromeOptions()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--incognito")
        
        driver = webdriver.Chrome(ChromeDriverManager().install(), chrome_options=chrome_options)
        # browser settings
        driver.set_window_size(800, 1200)
        driver.set_window_position(0, 0)
        
        return driver

    @staticmethod
    def write2tracker(tracker_fn, d_name, num_links, start=True):
        '''Write some messages to a text file.'''
        if not 'txt' in tracker_fn or tracker_fn is None:
            raise TypeError('Verify tracker file!')

        time_str = 'start_time' if start is True else 'end_time'

        with open(tracker_fn, 'a') as outfile:
            msgs = [d_name, time_str, time.time(), num_links]
            outfile.write(','.join([str(x) for x in msgs]) + '\n')
        outfile.close()

    @staticmethod
    def write_post_content(text_str, op_fn):
        with open(op_fn, 'a') as outfile:
            outfile.write(text_str)
        outfile.close()

    @staticmethod
    def find_username_and_password_button(driver):
        u_btn, p_btn = None, None
        try:
            u_btn = driver.find_element_by_xpath("//input[@id='email' and @type='text']")
            p_btn = driver.find_element_by_xpath("//input[@id='pw' and @type='password']")
        except Exception as e:
            pass

        return u_btn, p_btn

    @staticmethod
    def re_login_post_page(driver):
        '''Re-logins for scraping the webpage for individual posts.'''
        print('[{}] we are now re-logging in...'.format(InspireCom.re_login_post_page.__name__))
        login_button = driver.find_element_by_xpath("//a[@class='btn-header btn-header-login']")
        login_button.click()
        time.sleep(random.randint(1,2))
        # find buttons for credentials
        username_button, password_button = InspireCom.find_username_and_password_button(driver)
        username, password = get_login_credential()
        # send keys
        username_button.send_keys(username)
        password_button.send_keys(password)
        time.sleep(random.randint(1,2))
        # find the submit button
        submit_button = driver.find_element_by_xpath("//input[@name='submit' and @type='submit' and @class='button']")
        submit_button.click()
        print('[{}] job complete, leave.'.format(InspireCom.re_login_post_page.__name__))
        time.sleep(random.randint(1,2))