#!/usr/bin/env python3
"""Find addon info online and generate info databases.

I know all this screen scraping is bad for the curse site (and my soul), but they leave me no
other option
"""
# pylint: disable=invalid-name, no-name-in-module, line-too-long, fixme, R0914
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

RCNTBASEURLS = ['http://mods.curse.com/addons/wow/updated',
                'http://mods.curse.com/addons/wow/downloads',
                'http://mods.curse.com/addons/wow/new',
                'http://mods.curse.com/addons/wow']

LOG = logging.getLogger(__name__)


def process_page(s, url, li):
    """Process a page from our data source.

    s = request object
    url = the url of the page... can we get this out of the request object somehow?
    li = the addon entry, we get the name and addon url from this
    """
    # name = li.a.text
    ao_url = urljoin(url, li.a['href'])
    LOG.info(ao_url)
    try:
        ao_resp = s.get(ao_url)
    except requests.exceptions.Timeout:  # requests.exceptions.ReadTimeout too new
        LOG.error('Read timeout: Internet connected?')
        sys.exit(1)
    except ConnectionResetError:
        LOG.error('Connection reset, skipping')
        return None

    ao_soup = BeautifulSoup(ao_resp.text, "html.parser")

    lic_url = 'curse_changed_formats_again'
    try:
        lic_name = ao_soup.find('li', class_='license').text.split(':')[-1].strip()
    except AttributeError:
        LOG.error("Unable to find the license info: %s", ao_url)
        lic_name = 'NOT FOUND'

    try:
        obf_file_url = ao_soup.find(class_='download-large').find('a').get('href')
        obf_dl_resp = s.get(urljoin(url, obf_file_url))
        if obf_dl_resp.status_code == 404:
            LOG.debug("404 when fetching the download link...")
            return None
        # LOG.debug(obf_dl_resp)
        obf_dl_soup = BeautifulSoup(obf_dl_resp.text, 'html.parser')
        # LOG.debug(obf_dl_soup)
        file_dl = obf_dl_soup.find('a', class_='download-link').get('data-href')
        CACHE.get(file_dl, session=s)
    except AttributeError:
        LOG.debug("Unable to find download link: %s", ao_url)
        # LOG.error(s)
        # LOG.error(url)
        # LOG.error(li)
        # LOG.error(ao_soup)
        return None

    # TODO need more ways of getting tags
    addon = {
        'name': ao_soup.head.find('meta', property='og:title').get('content'),
        'tags': [ao_soup.find('a', class_='main-category').get('title')],
        'authors': [x.a.text for x in ao_soup.find('ul', class_='authors').find_all('li')],
        'wowver': ao_soup.find('li', class_='version').text.split(' ')[-1],
        'forge': ao_soup.find('li', class_='curseforge').a.get('href'),
        'relqual': ao_soup.find('li', class_='release').text.split(' ')[-1],
        'latest': get_version(ao_soup.find('li', class_='newest-file').text.split(':')[-1].strip()),
        'created': ao_soup.find_all('li', class_='updated')[1].find('abbr').get('data-epoch'),
        'updated': ao_soup.find_all('li', class_='updated')[0].find('abbr').get('data-epoch'),
        'license': (lic_name, lic_url),
        'download': file_dl,
        'datetime': datetime.datetime.now(),
    }

    return addon


def age_out(addons):
    """Age out a random sampling of older DB entries.

    There's probably a better way to do this, but the thinking is this runs often enough that
    everything should get aged out properly eventually.
    """
    LOG.info("Aging 30 random entries out.")
    try:
        for key in random.sample(addons.keys(), 30):
            LOG.info('Delete key: %s', key)
            del addons[key]
    except ValueError:
        LOG.error("failed to age out (probably due to too small sample size), continuing anyway")


def clean_up_addons(addons):
    """Housekeeping."""
    # We got some bad data in the pickle at one point
    slugs_to_delete = []
    for slug, addon in addons.items():
        if 'mods.curse.com' in addon['download']:
            slugs_to_delete.append(slug)
    for slug in slugs_to_delete:
        del addons[slug]


def build_url_list():
    """Build up a list of URLs to check.

    This basically just adds a bunch of pages to a base list of URLs
    """
    url_list = []
    for baseurls in RCNTBASEURLS:
        for page in range(1, 10):
            url_list.append("{}?page={}".format(baseurls, page))
    return url_list


def main():
    """Main function to generate the addon database."""
    addons = CACHE.load()

    parser = argparse.ArgumentParser(description='Generate database of data about addons.')
    parser.add_argument('-w', dest='wipe', action='store_true', default=False,
                        help='Wipe existing data')
    parser.add_argument('-a', dest='age', action='store_true', default=False,
                        help='Age out random selection of existing data')
    parser.add_argument('-l', dest='log', action='store', default="WARNING",
                        help='Set logging level (INFO|DEBUG|Etc)')
    parser.add_argument('-c', dest='count', action='store', default=20,
                        help='Number of URLs to process')
    args = parser.parse_args()

    nlevel = getattr(logging, args.log.upper())
    if not isinstance(nlevel, int):
        raise ValueError('Invalid log level: {}'.format(args.log))
    logging.basicConfig(level=nlevel)

    # age out random records
    if args.age:
        age_out(addons)

    clean_up_addons(addons)

    # scan through the most recent addons on curse.com
    urls = build_url_list()

    s = requests.Session()
    for url in urls:
        count = int(args.count)
        resp = s.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")
        LOG.info('Page: %s (%s)', soup.title.text, url)

        # there are basically 2 different page styles, but thankfully they are really close
        titles = soup.find_all("td", class_="title") or soup.find_all("li", class_="title")

        if not titles:
            LOG.error('Something bad happened parsing %s', url)
            LOG.error(resp.text)

        try:
            for li in titles:
                # process each addon page
                slug = slugify(li.find('a').get('href').split('/')[-1])
                if slug in addons and not args.wipe:
                    # TODO we need a way to automatically age out old data/freshen/etc
                    continue
                LOG.info('Processing %s', slug)
                addon = process_page(s, url, li)
                LOG.debug(addon)
                if addon:
                    addons[slug] = addon

                count = count - 1
                if count is 0:
                    break
                # random sleep to throw off any scraping countermeasures they may have
                time.sleep(random.randrange(1, 4))
        except (KeyboardInterrupt, requests.exceptions.ConnectionError):
            # we still want to save everything we've done...
            # if we get a ctrl-c in here, it probably means I saw something I didn't like
            # if we get a conn error, it probably means we're being rate-limited
            LOG.debug("Caught an interrupt or conn err, saving work.")
            break
        LOG.debug("Addons: %s", addons)

    CACHE.dump(addons)

    # now output a json file with some basic info, we want this to be a small file so the clients
    # aren't constantly downloading a huge file
    latest = {}
    for slug, info in addons.items():
        LOG.debug("slug: %s", slug)
        LOG.debug("info: %s", info)
        latest[slug] = (info['latest'], info['download'])
    with open(os.path.join(CACHE.cachedir, 'latest.json'), 'wt') as jsonout:
        LOG.debug("Lastest: %s", latest)
        json.dump(latest, jsonout, indent=4)


if __name__ == '__main__':
    main()
