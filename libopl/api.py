#!/usr/bin/env python3
#####
# API Class
# Handles all the online stuff
# Needs to be configured to a hosted api
#
# API Sourcecode: https://github.com/Nold360/opengamedb
# Config Example: https://github.com/Nold360/libopl/example.opl.ini
from os import path
from libopl.artwork import Artwork
from libopl.common import slugify, exists, config

import re
import json
import requests
import unicodedata

class API():
    # API Version
    VERSION='1'

    # is API available/configured? 
    # Needs to be configured to obtain game titles and
    # artwork. If False, it's simly deactivated.
    enabled=False

    # URL to API & static host
    URL=None
    STATIC_URL=None
    config = None

    def __init__(self):
        self.URL=config("API", "URL")
        self.STATIC_URL=config("API", "STATIC_URL")
            
        if not self.URL or not self.STATIC_URL:
            print("""
Info: API is not configured! Downloading artwork 
& renaming/fixing of images will be disabled.
Please create a ~/.config/opl.ini

Example: http://github.com/Nold360/libopl/example.opl.ini
""")
        else:
            self.enabled = True
            

    # Get metadata for title_id
    # returns json-dict
    def get_metadata(self, title_id):
        if not self.enabled:
            return False

        try:
            r = requests.get(self.URL + title_id)
        except Exception as e:
            print("Oops! Error while downloading metadata from API:")
            print(e)
            return False

        try:
            json_data = json.loads(r.text)
            return json_data
        except:
            print("Oops! API didn't return JSON?")
            print(r.text)
            return None

    # Returns list of Artwork Objects
    # Incl. url & art_type
    def get_artwork(self, game):
        if not self.enabled:
            return False

        artworks = []
        meta = game.get("meta")
        try:
           meta["artwork"] 
        except Exception as e: 
            print("Oops: No Artworks found in Metadata.")
            return None

        for art_type in meta["artwork"]:
            if type(meta["artwork"][art_type]) == list:
                filename = meta["artwork"][art_type][0]
            else: filename = meta["artwork"][art_type]
            filetype = filename.split('.')[1]
            a = Artwork(self.STATIC_URL + "artwork/" + filename, art_type, filetype=filetype)
            artworks.append(a)
        return artworks
        
    # Download Artwork for "game" to "opl_drive"/ART/
    # Return: Number of failed downloads/writes
    def download_artwork(self, game, opl_drive, override=False):
        if not self.enabled:
            return False

        game.artworks = self.get_artwork(game)
        if game.artworks == []:
            print("No Artwork available for this title atm... sorry!")
            return False

        filebase = game.get("opl_id")
        ret = 0
        if not game.get("artwork"):
            print("No artwork to download...")
            return False

        for art in game.get("artwork"):
            filename = filebase + "_" + art.type + "." + art.filetype
            filepath = path.join(opl_drive, "ART", filename)
            if exists(filepath) and not override:
                print("Skipped: %s (File exists)" % filename)
                continue

            print("Downloading Artwork: " + filename)
            try:
                r = requests.get(art.url)
            except Exception as e: 
                print(" -> Error downloading artwork:")
                print(e)
                ret+=1
                continue

            try:
                if not exists(filepath) or override:
                    with open(filepath, 'wb') as f:
                        f.write(r.content)
            except Exception as e: 
                print(" -> Error writing artwork to opl_drive:")
                print(e)
                ret+=1
                continue

        print("Download completed!")
        return ret
