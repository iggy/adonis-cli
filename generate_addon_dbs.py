#!/usr/bin/env python3
'''Find addon info online and generate info databases

I know all this screen scraping is bad for the curse site (and my soul), but they leave me no
other option
'''
# pylint: disable=invalid-name, no-name-in-module, line-too-long, fixme
from __future__ import print_function

import argparse
import datetime
import json
import os.path
import random
import sys
import time
from urllib.parse import urljoin

try:
    import requests
except ImportError:
    sys.exit("Please install requests: pip3 install requests")
try:
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("Please install BeautifulSoup: pip3 install beautifulsoup4")

from utils import slugify, CACHE, get_version


ADDONS = CACHE.load()

parser = argparse.ArgumentParser(description='Generate database of data about addons.')
parser.add_argument('-w', dest='wipe', action='store_true', default=False,
                    help='Wipe existing data')
parser.add_argument('-a', dest='age', action='store_true', default=False,
                    help='Age out random selection of existing data')
args = parser.parse_args()

# age out random records
# TODO handle aging out records correctly
if args.age:
    print("Aging 30 random entries out.")
    for key in random.sample(ADDONS.keys(), 30):
        print('Delete key: {}'.format(key))
        del ADDONS[key]

# scan through the most recent addons on curse.com
RCNTBASEURLS = ['http://mods.curse.com/addons/wow/updated',
                'http://mods.curse.com/addons/wow/downloads',
                'http://mods.curse.com/addons/wow/new',
                'http://mods.curse.com/addons/wow']
RCNTURLS = []
for baseurls in RCNTBASEURLS:
    for page in range(1, 10):
        RCNTURLS.append("{}?page={}".format(baseurls, page))

s = requests.Session()
for RCNTURL in RCNTURLS:
    COUNT = 20
    resp = s.get(RCNTURL)
    soup = BeautifulSoup(resp.text, "html.parser")
    print('Page: {}'.format(soup.title.text))

    # there are basically 2 different page styles, but thankfully they are really close
    titles = soup.find_all("td", class_="title") or soup.find_all("li", class_="title")

    if not titles:
        print('Something bad happened parsing {}'.format(RCNTURL))
        print(resp.text)

    try:
        for li in titles:
            # process each addon page
            slug = slugify(li.find('a').get('href').split('/')[-1])
            if slug in ADDONS and not args.wipe:
                # TODO we need a way to automatically age out old data/freshen/etc
                continue
            print('Processing {}'.format(slug))
            name = li.a.text
            ao_url = urljoin(RCNTURL, li.a['href'])
            # print(ao_url)
            try:
                ao_resp = s.get(ao_url)
            except requests.exceptions.ReadTimeout:
                print('Read timeout: Internet connected?')
                sys.exit(1)
            except ConnectionResetError:
                print('Connection reset, skipping')
                continue
            ao_soup = BeautifulSoup(ao_resp.text, "html.parser")

            det = ao_soup.find('div', class_='main-details')

            cfurl = det.find('li', class_='curseforge').a.get('href')
            if cfurl[0:2] == '//':
                # They started returning url's without http(s)
                cfurl = "http:" + cfurl
            cfresp = s.get(cfurl)
            cfsoup = BeautifulSoup(cfresp.text, 'html.parser')

            # the curseforge page has an info pane with a lot of stuff we want
            cfip = cfsoup.find('div', class_='lastUnit')
            cfdl = urljoin(cfresp.url, cfip.find('li', class_='user-action-download').a.get('href'))
            # cffacts = cfip.find('div', class_='content-box-inner')
            cffacts = cfip.find('h3', text='Facts').parent
            # this gets us a unix timestamp for created date
            cfcreated = cffacts.find('dt', text="Date created").find_next('dd').span.get('data-epoch')
            cfupdated = cffacts.find('dt', text="Last update").find_next('dd').span.get('data-epoch')
            cflicurl = cffacts.find('a', class_='license').get('href')
            cflicname = cffacts.find('a', class_='license').text

            # find the most recent download
            # TODO older releases, notes, etc
            cfdlresp = s.get(cfdl)
            cfdlsoup = BeautifulSoup(cfdlresp.text, 'html.parser')
            cfdlfile = cfdlsoup.find('li', class_='user-action-download').a.get('href')
            CACHE.get(cfdlfile)

            # TODO need more ways of getting tags
            ADDONS[slug] = {
                'name': name,
                'tags': [det.find('a', class_='main-category').get('title')],
                'authors': [x.li.a.text for x in det.find_all('ul', class_='authors')],
                'wowver': det.find('li', class_='version').text.split(' ')[-1],
                'forge': det.find('li', class_='curseforge').a.get('href'),
                'relqual': det.find('li', class_='release').text.split(' ')[-1],
                'latest': get_version(det.find('li', class_='newest-file').text),
                'created': cfcreated,
                'updated': cfupdated,
                'license': (cflicname, cflicurl),
                'download': cfdlfile,
                'datetime': datetime.datetime.now(),
            }

            COUNT = COUNT - 1
            if COUNT is 0:
                break
            # random sleep to throw off any scraping countermeasures they may have
            srt = random.randrange(1, 4)
            time.sleep(srt)
    except (KeyboardInterrupt, requests.exceptions.ConnectionError):
        # we still want to save everything we've done...
        # if we get a ctrl-c in here, it probably means I saw something I didn't like
        # if we get a conn error, it probably means we're being rate-limited
        pass

CACHE.dump(ADDONS)

# now output a json file with some basic info, we want this to be a small file so the clients
# aren't constantly downloading a huge file
latest = {}
for slug, info in ADDONS.items():
    latest[slug] = (info['latest'], info['download'])
with open(os.path.join(CACHE.cachedir, 'latest.json'), 'wt') as jsonout:
    json.dump(latest, jsonout)
