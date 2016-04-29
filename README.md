# Adonis

## World of Warcraft Add-On upgrader

This has only been tested on Mac OS X (10.11). Any OS that has/can have python should be able to be added.

This currently works well enough to keep all of my installed addons updated.
It likely doesn't catch all of the corner cases yet.

Usage:

To be prompted for each addon to be updated (probably a good idea the first time), run:

`./addons.py`

To just update everything automatically:

`./addons.py -y`

## TODO

* Do more than just upgrade
 * Search
 * Recommendations
 * Etc
* Expand the server side to be more than just some scraped data in some flat files
* GUI
