import collections
import datetime
import json
import logging
import os
import random
import re
import requests
import time
import traceback

from bs4 import BeautifulSoup, Tag
from copy import deepcopy
from os.path import (exists, join, isfile, isdir)
from selenium.common.exceptions import TimeoutException

# local dependencies
from config import *
from inspire_com import InspireCom
from util import *


def main_download(debug=False, headless=True):

    # hibernation time
    HIBER_TIME = 1
    tracker_fn = './data/tracker.txt'

    if not exists(tracker_fn):
        # this line below won't work for Windows
        os.mknod(tracker_fn)

    # load all diagnosis
    all_classes = load_all_classes_names()

    while True:
        # remove completed done diagnosis
        done_diags = []
        try:
            with open(tracker_fn, 'r') as infile:
                done_diags = infile.readlines()
        except Exception as e:
            logging.exception(e)

        # logic is, for completely done diagnosis, it shall have a start_time and end_time
        done_diags = sorted(done_diags, key=lambda x: ','.join([c for c in x.split(',')[:-3]]), reverse=False)
        splitter = collections.defaultdict(list)
        for d in done_diags:
            tmp_name = ','.join([x for x in d.split(',')[:-3]])
            splitter[tmp_name].append(d.split(',')[-3])
        # save a list of completely finished diagnosis
        safe_diags = []
        for k,v in splitter.items():
            if 'end_time' in v:
                safe_diags.append(k)

        # run a new iteration, randomly pick an unfinished diagnosis
        remain_diags = list(set(all_classes).difference(set(safe_diags)))
        print('\n## -- by {}, remaining # of diagnosis to be scraped is {} -- ##'.format(
            datetime.datetime.now(), len(remain_diags)
        ))

        # if nothing remains, break the loop
        if not remain_diags:
            break
        else:
            this_diag = random.choice(remain_diags)
            #this_diag = 'Melanoma'
            # handles single slash
            this_diag = this_diag.replace('/', '_')
            print(f'randomly picked diagnosis=[{this_diag}]')
            # run
            try:
                inspire_com = InspireCom(
                    diagnosis=this_diag,
                    tracker_fn=tracker_fn,
                    headless=headless
                )
                inspire_com.scrape_worker()
                inspire_com.tear_down()

            except Exception as e:
                logging.exception(e)
                print(f'Exception={e} occurs, move on to next one...')
                pass
            # sleeping...
            ran_hiber_time = HIBER_TIME # + random.randint(1,5)
            print(f'hibernating for {ran_hiber_time} seconds.')
            time.sleep(ran_hiber_time)


if __name__ == '__main__':

    main_download(False, True)