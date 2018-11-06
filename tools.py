# -*- coding: utf8 -*-
import hashlib
import sys
import time
from urllib.request import urlretrieve
from datetime import datetime
from bson import ObjectId
import objects


def new_session():
    h = hashlib.new("md5")
    session = str(datetime.timestamp(datetime.now()))
    h.update(bytearray(session.encode("utf8")))
    return h.hexdigest()


def log(event):  # simple wrapper for logging to stdout on heroku
    print(" [" + event.status + "][" + str(event.get_id()) + "] " + event.obs)
    sys.stdout.flush()


def get_timestamp(component='CORE'):
    return datetime.fromtimestamp(time.time()).strftime('[%Y.%m.%d %H:%M:%S.%f')[:-3] + '][' + component + ']'


def save_image(event):
    event.update("PRO", datetime.now(), "Saving Image")
    img = objects.ImgRequest(**objects.ImgRequest.get_image(event.get_id()))
    if img is None:
        return "Image request not found!", 404
    event.update("PRO", datetime.now(), "Downloading Image from: " + img.imgUrl)

    from urllib.error import HTTPError
    try:
        rsp = urlretrieve(img.imgUrl, img.fileName)
        event.update("OK ", datetime.now(), rsp[0] + " Saved successfully!")
        return True
    except HTTPError as e:
        event.update("ERR", datetime.now(), str(e.code) + " image " + e.msg)
        return False


def generate_response(event):
    event = event.get_last_event()
    for elem in event:
        if type(event[elem]) is ObjectId:
            event[elem] = str(event[elem])
    return event
