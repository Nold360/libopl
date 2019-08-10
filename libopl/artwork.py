#!/usr/bin/env python3
####
# Artwork... nice, isn't it!
class Artwork():
    # url to this artwork's sourcefile
    url = None

    # Target filename
    filename = None
    type = None

    def __init__(self, url, art_type, filename=None, filetype=None):
     self.url = url
     self.filename = filename
     self.type = art_type
     self.filetype = filetype
    
    def set_filetype(self, filetype=None):
     if not filetype:
       self.filetype = filename.split('/')[:1]
     else:
       self.filetype = filetype
     
    def get_filename(self, opl_id=None):
        if opl_id:
            self.filename = opl_id+ "_" + self.type + "." + self.filetype
        return self.filename
