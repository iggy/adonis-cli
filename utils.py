"""Some utility functions for the addon scripts.

This is used by both the addon DB generator and the client
"""
# pylint: disable=redefined-builtin
import datetime
import logging
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
REPLRE = re.compile(r'(\W*)(Release|Beta|Alpha|\(.*?\)|^v)(\W*)', re.I)

# map server names to local names
NAMEMAP = {
    'titan': 'titanpanel',
    'aucadvanced': 'auctioneer',
    'datastore_containers': 'datastore',
    'datastore_characters': 'datastore',
}
# version map... for things like altoholic that report version r165, but are actually 6.2.007
# should probably be something downloaded so it's uptodate
VERSIONMAP = {
    'altoholic': {
        '165': '6.2.007',
        '170': '7.0.005',
        '171': '7.0.006',
        '172': '7.1.001',
        '179': '7.2.002',
    },
    'auctioneer': {
        '5.21f.5579': '5.21f',
        '7.2.5688': '7.2r5688',
        '7.4.5714': '7.4r5714',
    },
    'datastore': {
        '56': '6.0.002',
        '58': '6.0.002',
        '59': '6.0.002',
        '60': '6.0.002',
        '63': '6.0.002',
    },
}

LOG = logging.getLogger(__name__)


class Cache(object):
    """functions for more easily interacting with the cache directory."""

    def __init__(self):
        """Stop initialize."""
        self.cachedir = os.path.join(os.path.expanduser('~'), '.adonis/')
        self.picklefile = os.path.join(self.cachedir, 'addons.pickle')

        if not os.path.isdir(self.cachedir):
            os.mkdir(self.cachedir)

    def get(self, url, refresh_age=None, session=None):
        """Get a file from a local cache or fetch it from a url.

        url - The url to fetch
        refresh_age - refresh if file is older than this
        session - the requests session object for downloading files from curse since it wants to
            obfuscate things
        """
        filename = os.path.split(url)[-1]
        filepath = os.path.join(self.cachedir, 'download', filename)
        if not os.path.isdir(os.path.join(self.cachedir, 'download')):
            os.mkdir(os.path.join(self.cachedir, 'download'))
        if refresh_age and os.path.isfile(filepath):
            new_enough = datetime.datetime.now() - datetime.timedelta(seconds=-int(refresh_age))
            if datetime.datetime.fromtimestamp(os.stat(filepath).st_mtime) < new_enough:
                os.unlink(filepath)

        if not os.path.isfile(filepath):
            try:
                os.unlink(filepath)
            except OSError:
                # we don't really care if the unlink fails, it's basically just here to avoid
                # symlink attacks
                pass
            if not session:
                urlretrieve(url, filepath)
            else:
                resp = session.get(url, stream=True)
                with open(filepath, 'wb') as filep:
                    filep.write(resp.content)

        return filepath

    def getfd(self, url, refresh_age=None):
        """Return the opened fd."""
        filepath = self.get(url, refresh_age=refresh_age)
        return open(filepath)

    def load(self):
        """Load pickled data from previous runs... we don't need no stinking databases."""
        LOG.debug("Loading data from picklefile")
        if os.path.isfile(self.picklefile):
            with open(self.picklefile, 'rb') as pick:
                return pickle.load(pick)

    def dump(self, data):
        """Put data into the pickle file in the cache directory."""
        LOG.debug("Dumping data to picklefile")
        with open(self.picklefile, 'wb') as pick:
            pickle.dump(data, pick, pickle.HIGHEST_PROTOCOL)


CACHE = Cache()


def slugify(text):
    """Convert the text into something computer friendly.

    This is slightly different than the normal slugify functions...

    it also strips out some punctuation that we kind of don't want
    """
    text = COMPILEDRE.sub('', text)
    text = text.lower()

    return text


def namemap(name):
    """Lookup the name in NAMEMAP to see if we should be looking for a different local name."""
    if name in NAMEMAP:
        return NAMEMAP[name]

    return name


def get_version(text):
    """Return a version string from the version data scraped off the page."""
    return REPLRE.sub('', text).split(' ')[-1].strip()
