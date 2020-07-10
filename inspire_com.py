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
from urllib.request import urlopen
from webdriver_manager.chrome import ChromeDriverManager

# local dependencies
from config import *


class InspireCom:

    def __init__(self, diagnosis=None, tracker_fn=None, headless=True):
        # Each instance is responsible for scraping images for one diagnosis.Let's do it slowly.

        # shall go to https://www.inspire.com/search/posts/?query=&p=1&sec=&g=&r=0&s=false
        self.base_url = 'https://www.inspire.com/search/posts/?query=&p=1&sec=&g=&r=0&s=false'
        self.diagnosis = diagnosis

        # incongito mode
        chrome_options = webdriver.ChromeOptions()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--incognito")
        self.driver = webdriver.Chrome(ChromeDriverManager().install())
        # browser settings
        #self.driver.set_window_size(800,1200)
        self.driver.set_window_position(0,0)

        # tracker file
        self.tracker_fn = tracker_fn
        # default delay time for page loading (unit in seconds)
        self.delay = 10

    def log_in(self):
        '''Logs in with credentials.'''
        print('Signing in with credentials...')
        time.sleep(5)

        # find username button
        username_button = self.driver.find_element_by_xpath("//input[@id='email' and @type='text']")
        username_button.send_keys(USERNAME)
        # find password button
        password_button = self.driver.find_element_by_xpath("//input[@id='pw' and @type='password']")
        password_button.send_keys(PASSWORD)

        # login submit
        submit_button = self.driver.find_element_by_xpath("//button[@name='submit' and @type='submit']")
        submit_button.click()

        print('Signed in successfully!')
        time.sleep(random.randint(2,5))

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
            print('Could not find login button!')

        # if asks us to login, do it
        if login_button:
            login_button.click()
            print('it requires us to sign in...')
            try:
                self.log_in()
                # re-get the url with query string b\c the page has been refreshed
                new_url = url
                new_url = '&'.join([x for x in new_url.split('&')[:-2]]) + '&s=false'
                self.driver.get(new_url)
            except Exception as e:
                logging.exception(e)
                print(f'Error={e} occurs, shutting down...')
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
                print('no \'show me more\' button found!')
                break
            else:
                print('finds one \'show me more\' button, click, scroll to bottom and wait!')
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
        root_url = 'www.inspire.com/'
        href_links = []
        for post in posts:
            href_links.append(root_url + post.parent.get('href'))

        num_links, scraped_links, failed_links = len(href_links), 0, 0
        print(f'total number href links found: {num_links}')

        # [4] Open link one by one, do the dirty work
        # write to a tracker
        InspireCom.write2tracker(self.tracker_fn, self.diagnosis, num_links, True)
        # if cannot find any link, directly terminate
        if num_links == 0:
            InspireCom.write2tracker(self.tracker_fn, self.diagnosis, num_links, False)
            return

        # keep scraping links, while not allow failure rate to exceed 50%
        while scraped_links < num_links and failed_links < 0.5 * num_links:
            # grab a link
            href_link = href_links.pop(0)
            # make a subdirectory to store
            temp_op_dir = cur_op_dir + '/link=' + str(scraped_links)
            if not exists(temp_op_dir):
                os.makedirs(temp_op_dir)
            # do it
            res = InspireCom.scrape_one_post(self.driver, href_link, soup, temp_op_dir)
            if res is True:
                scraped_links += 1
            else:
                failed_links += 1

        # write a tracker fn
        InspireCom.write2tracker(self.tracker_fn, self.diagnosis, scraped_links, False)

    @staticmethod
    def scrape_one_post(driver_obj, link, soup_obj, op_dir):
        '''Given an url link with the post and image we want, download them.'''
        driver = deepcopy(driver_obj)
        driver.get(link)
        print('Hanging on...')
        time.sleep(120)



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