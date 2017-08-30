#!/usr/bin/env python3
"""A Flickr uploader for photos in Shotwell, to be run from the command line.
This is something you run out of a cron job, rather than with Shotwell's own
"publish" command."""

import sys, os, sqlite3, time
from gi.repository import GLib
import flickrapi # apt install python3-flickrapi
import flickr_config

SUPPORTED_SHOTWELL_SCHEMAS = [20]

def findShotwell():
    return os.path.join(GLib.get_user_data_dir(), "shotwell", "data", "photo.db")
def confirmOK(shotwell):
    def die(msg):
        print(msg)
        sys.exit(1)

    if not shotwell: die("%r is nothing" % shotwell)
    if not os.path.isfile(shotwell): die("%s does not exist" % shotwell)
    suri = GLib.filename_to_uri(shotwell) + "?mode=ro"
    db = sqlite3.connect(suri, uri=True, detect_types=sqlite3.PARSE_DECLTYPES)
    db.row_factory = sqlite3.Row
    cursor = db.execute("SELECT schema_version from VersionTable;")
    schema_version = cursor.fetchone()["schema_version"]
    if schema_version not in SUPPORTED_SHOTWELL_SCHEMAS:
        die(("Shotwell DB uses unsupported schema version %s. "
                   "Giving up, just to be safe.") % schema_version)
    return db

def flickrLogin():
    flickr = flickrapi.FlickrAPI(flickr_config.KEY, flickr_config.SECRET,
        cache=True, format='parsed-json')
    # Only do this if we don't have a valid token already
    if not flickr.token_valid(perms='write'):
        # Get a request token
        flickr.get_request_token(oauth_callback='oob')
        # Open a browser at the authentication URL. Do this however
        # you want, as long as the user visits that URL.
        authorize_url = flickr.auth_url(perms='write')
        print("Open url", authorize_url)
        # Get the verifier code from the user. Do this however you
        # want, as long as the user gives the application the code.
        verifier = str(input('Verifier code: '))
        # Trade the request token for an access token
        flickr.get_access_token(verifier)
    return flickr

def upload(shotwell, flickr):
    start = time.time()
    user_id = flickr.test.login()["user"]["id"]
    cursor = shotwell.execute("SELECT id,filename,md5 from phototable order by id asc;")
    for row in cursor:
        diff = time.time() - start
        if diff > 10:
            print("endit")
            break
        fn = row["filename"]
        shortfn = "%s/%s" % (os.path.basename(os.path.dirname(fn)), os.path.basename(fn))
        tag = "sil_md5_%s" % row["md5"]
        resp = flickr.photos.search(tags=tag, user_id=user_id)
        if resp["photos"]["pages"] == 0:
            print("Uploading", shortfn)
            resp = flickr.upload(filename=row["filename"], tags="%s" % tag,
                is_public="0", is_family="1", is_friend="1", format="rest")
            time.sleep(2) # give Flickr a chance to index this new upload
        else:
            print("Got", shortfn)

def main():
    shotwell_file = findShotwell()
    shotwell = confirmOK(shotwell_file)
    flickr = flickrLogin()
    upload(shotwell, flickr)

if __name__ == "__main__":
    main()