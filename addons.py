#!/usr/bin/python
'''Search local dirs for AddOns
Check for new version online
Update local'''
from __future__ import print_function

import argparse
import json
import os
import platform
import zipfile

from six.moves import input  # pylint: disable=redefined-builtin

from utils import namemap, slugify, CACHE, FileNotFoundError, get_version, VERSIONMAP


# TODO Windows different versions go to different places
plat = platform.system()
if plat == "Darwin":
    ADDDIR = "/Applications/World of Warcraft/Interface/AddOns/"
elif plat == "Windows":
    ADDDIR = ""

LATESTURL = "https://iggy.ninja/latest.json"

ADDONS = {}
# most of these are ignored because they are bliz built-ins or they are part of "bundles"
IGNOREDADDONS = ['vuhdooptions', 'masterplana', 'msbtoptions', 'enchantrix-barker',
                 'titanxp', 'titanbag', 'titanclock', 'titangold', 'titanlocation', 'titanloottype',
                 'titanperformance', 'titanrepair', 'titanvolume',
                 'datastore_talents', 'datastore_stats', 'datastore_spells',
                 'datastore_reputations',
                 'datastore_quests', 'datastore_pets', 'datastore_mails', 'datastore_inventory',
                 'datastore_garrisons', 'datastore_currencies', 'datastore_crafts',
                 'datastore_agenda', 'datastore_achievements', 'datastore_auctions',
                 'blitz_options', 'blitz_progress',
                 'auc-advanced',
                 'auc-stat-stddev', 'auc-stat-simple', 'auc-util-fixah', 'auc-stat-purchased',
                 'auc-stat-ilevel', 'auc-stat-histogram', 'auc-scandata', 'auc-filter-basic',
                 'altoholic_achievements', 'altoholic_summary', 'altoholic_search',
                 'altoholic_guild', 'altoholic_grids', 'altoholic_characters', 'altoholic_agenda',]

parser = argparse.ArgumentParser(description='Check for and update WoW addons.')
parser.add_argument('-y', dest='yes', action='store_true', default=False,
                    help='Answer yes to prompts')
args = parser.parse_args()

for ent in os.listdir(ADDDIR):
    slug = namemap(slugify(ent))
    if slug in IGNOREDADDONS:
        continue
    ADDONS[slug] = {}
    try:
        toc = open(os.path.join(ADDDIR, "{}/{}.toc".format(ent, ent)))
        for line in toc.readlines():
            if line.startswith("##") and ":" in line:
                k, v = line.split(':', 1)
                ADDONS[slug][k.strip('# ').lower()] = v.strip('# \n').strip().strip(r'\r')

    except FileNotFoundError as err:
        # no toc file, that probably means this is a Bliz AddOn or just some random dir
        # print(err)
        pass

# So now we have a list of the the installed addons, check the online database to see if there's a
# new version
latest = json.load(CACHE.getfd(LATESTURL, refresh_age=60))

for slug, info in ADDONS.items():
    if slug in latest and 'version' in ADDONS[slug]:
        ver, url = latest[slug]
        instver = get_version(ADDONS[slug]['version'])
        latestver = get_version(ver)

        if slug in VERSIONMAP and instver in VERSIONMAP[slug]:
            instver = VERSIONMAP[slug][instver]


        print('Match found in database: {}'.format(slug))
        print('Installed version:     "{}"'.format(instver))
        print('Latest version:        "{}"'.format(latestver))

        if instver != latestver:
            if not args.yes:
                yn = input('Would you like to upgrade {} from {}? [Y/n] '.format(slug, url))
            if args.yes or yn is "" or yn.startswith('y') or yn.startswith('Y'):
                # do the upgrade
                print('Upgrading {} from {}, please wait...'.format(slug, url))
                ufd = CACHE.get(url)
                with zipfile.ZipFile(ufd) as zfile:
                    zfile.extractall(ADDDIR)
