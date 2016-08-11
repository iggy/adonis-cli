#!/usr/bin/env python3
'''Find addon info online and generate info databases

I know all this screen scraping is bad for the curse site (and my soul), but they leave me no
other option
'''
# pylint: disable=invalid-name, no-name-in-module, line-too-long, fixme
import argparse
import datetime
import json
import logging
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


LOG = logging.getLogger(__name__)

def process_page(s, rcnturl, li):
    name = li.a.text
    ao_url = urljoin(rcnturl, li.a['href'])
    LOG.info(ao_url)
    try:
        ao_resp = s.get(ao_url)
    except requests.exceptions.ReadTimeout:
        LOG.error('Read timeout: Internet connected?')
        sys.exit(1)
    except ConnectionResetError:
        LOG.error('Connection reset, skipping')
        return None
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
    addon = {
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

    return addon


def main():
    addons = CACHE.load() or {}

    parser = argparse.ArgumentParser(description='Generate database of data about addons.')
    parser.add_argument('-w', dest='wipe', action='store_true', default=False,
                        help='Wipe existing data')
    parser.add_argument('-a', dest='age', action='store_true', default=False,
                        help='Age out random selection of existing data')
    parser.add_argument('-l', dest='log', action='store', default="WARNING",
                        help='Set logging level')
    args = parser.parse_args()

    nlevel = getattr(logging, args.log.upper())
    if not isinstance(nlevel, int):
        raise ValueError('Invalid log level: {}'.format(args.log))
    logging.basicConfig(level=nlevel)

    # age out random records
    # TODO handle aging out records correctly
    if args.age:
        LOG.info("Aging 30 random entries out.")
        for key in random.sample(addons.keys(), 30):
            LOG.info('Delete key: {}'.format(key))
            del addons[key]

    # scan through the most recent addons on curse.com
    rcntbaseurls = ['http://mods.curse.com/addons/wow/updated',
                    'http://mods.curse.com/addons/wow/downloads',
                    'http://mods.curse.com/addons/wow/new',
                    'http://mods.curse.com/addons/wow']
    rcnturls = []
    for baseurls in rcntbaseurls:
        for page in range(1, 10):
            rcnturls.append("{}?page={}".format(baseurls, page))

    s = requests.Session()
    for rcnturl in rcnturls:
        count = 20
        resp = s.get(rcnturl)
        soup = BeautifulSoup(resp.text, "html.parser")
        LOG.info('Page: {} ({})'.format(soup.title.text, rcnturl))

        # there are basically 2 different page styles, but thankfully they are really close
        titles = soup.find_all("td", class_="title") or soup.find_all("li", class_="title")

        if not titles:
            LOG.error('Something bad happened parsing {}'.format(rcnturl))
            LOG.error(resp.text)

        try:
            for li in titles:
                # process each addon page
                slug = slugify(li.find('a').get('href').split('/')[-1])
                if slug in addons and not args.wipe:
                    # TODO we need a way to automatically age out old data/freshen/etc
                    continue
                LOG.info('Processing {}'.format(slug))
                addon = process_page(s, rcnturl, li)
                if addon:
                    addons[slug] = addon

                count = count - 1
                if count is 0:
                    break
                # random sleep to throw off any scraping countermeasures they may have
                srt = random.randrange(1, 4)
                time.sleep(srt)
        except (KeyboardInterrupt, requests.exceptions.ConnectionError):
            # we still want to save everything we've done...
            # if we get a ctrl-c in here, it probably means I saw something I didn't like
            # if we get a conn error, it probably means we're being rate-limited
            pass

    CACHE.dump(addons)

    # now output a json file with some basic info, we want this to be a small file so the clients
    # aren't constantly downloading a huge file
    latest = {}
    for slug, info in addons.items():
        latest[slug] = (info['latest'], info['download'])
    with open(os.path.join(CACHE.cachedir, 'latest.json'), 'wt') as jsonout:
        json.dump(latest, jsonout)

if __name__ == '__main__':
    main()
