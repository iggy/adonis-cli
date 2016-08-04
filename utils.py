'''Some utility functions for the addon scripts

'''
# pylint: disable=redefined-builtin
from __future__ import print_function

import datetime
import os.path
import pickle
import re

# import six.moves.cPickle as pickle  # currently only using pickle in 3.x code
from six.moves.urllib.request import urlretrieve  # pylint: disable=import-error


# some python2/3 compat stuff because Apple doesn't ship python3
try:
    FileNotFoundError
except NameError:
    FileNotFoundError = IOError

COMPILEDRE = re.compile(r"\W*")
REPLRE = re.compile('(\W*)(Release|Beta|Alpha|\(.*?\)|^v)(\W*)', re.I)  # pylint: disable=anomalous-backslash-in-string

# map server names to local names
NAMEMAP = {
    'titan': 'titanpanel',
    'aucadvanced': 'auctioneer',
}
# version map... for things like altoholic that report version r165, but are actually 6.2.007
# should probably be something downloaded so it's uptodate
VERSIONMAP = {
    'altoholic': {
        '165': '6.2.007',
        '170': '7.0.005',
    },
    'auctioneer': {
        '5.21f.5579': '5.21f',
    },
    'datastore':{
        '58': '6.0.002'
    },
    'datastore_containers': {
        '53': '6.0.002'
    },
    'datastore_characters': {
        '36': '6.0.002'
    }
}


class Cache(object):
    """functions for more easily interacting with the cache directory"""
    def __init__(self):
        self.cachedir = os.path.join(os.path.expanduser('~'), '.adonis/')
        self.picklefile = os.path.join(self.cachedir, 'addons.pickle')

        if not os.path.isdir(self.cachedir):
            os.mkdir(self.cachedir)

    def get(self, url, refresh_age=None):
        '''get a file from a local cache or fetch it from a url'''
        filename = os.path.split(url)[-1]
        filepath = os.path.join(self.cachedir, 'download', filename)
        if not os.path.isdir(os.path.join(self.cachedir, 'download')):
            os.mkdir(os.path.join(self.cachedir, 'download'))
        if refresh_age and os.path.isfile(filepath):
            new_enough = datetime.datetime.now() - datetime.timedelta(seconds=-refresh_age)
            if datetime.datetime.fromtimestamp(os.stat(filepath).st_mtime) < new_enough:
                os.unlink(filepath)

        if not os.path.isfile(filepath):
            try:
                os.unlink(filepath)
            except OSError:
                # we don't really care if the unlink fails, it's basically just here to avoid
                # symlink attacks
                pass
            urlretrieve(url, filepath)

        return filepath

    def getfd(self, url, refresh_age=None):
        '''return the opened fd'''
        filepath = self.get(url, refresh_age=refresh_age)
        return open(filepath)

    def load(self):
        '''load pickled data from previous runs... we don't need no stinking databases'''
        if os.path.isfile(self.picklefile):
            with open(self.picklefile, 'rb') as pick:
                return pickle.load(pick)

    def dump(self, data):
        '''put data into the pickle file in the cache directory'''
        with open(self.picklefile, 'wb') as pick:
            pickle.dump(data, pick, pickle.HIGHEST_PROTOCOL)

CACHE = Cache()

def slugify(text):
    '''this is slightly different than the normal slugify functions... it also strips out some
    punctuation that we kind of don't want
    '''
    text = COMPILEDRE.sub('', text)
    text = text.lower()

    return text

def namemap(name):
    '''lookup the name in NAMEMAP to see if we should be looking for a different local name
    '''
    if name in NAMEMAP:
        return NAMEMAP[name]
    else:
        return name

def get_version(text):
    '''return a version string from the version data scraped off the page...'''
    return REPLRE.sub('', text).split(' ')[-1].strip()
