# -*- coding: utf8 -*-
import bson
import json
import pymongo
import os
from bson import ObjectId
from tools import log


class Object(object):
    def __init__(self):
        pass

    def to_json(self):
        for element in self.__dict__:
            if type(self.__dict__[element]) is ObjectId:
                self.__dict__[element] = str(self.__dict__[element])
        return json.dumps(self.__dict__, sort_keys=False, indent=4, separators=(',', ': '))

    def to_json_obj(self):
        obj = json.loads(self.to_json())
        obj.pop("_id")
        return obj


class Event(Object):
    def __init__(self, user_id, start_date, event_type, status, status_date, obs=""):
        self._id = bson.objectid.ObjectId()
        self.user_id = user_id
        self.startDate = str(start_date)
        self.type = event_type
        self.status = status
        self.statusDate = str(status_date)
        self.obs = obs
        log(self)
        db = Database(os.environ["SCHEMA"]).get_schema()
        db.events.insert(self.__dict__)
        db.events_log.insert(EventLog(self._id, status, status_date, obs).__dict__)

    def get_id(self):
        return self._id

    def update(self, status, status_date, obs):
        self.status = status
        self.statusDate = str(status_date)
        self.obs = obs
        log(self)
        db = Database(os.environ["SCHEMA"]).get_schema()
        db.events.update_one({"_id": self._id},
                             {"$set": {"status": self.status, "statusDate": self.statusDate, "obs": self.obs}})
        db.events_log.insert(EventLog(self._id, status, status_date, obs).__dict__)


class EventLog(Event):
    def __init__(self, event_id, status, status_date, obs):
        self._id = bson.objectid.ObjectId()
        self.eventId = event_id
        self.status = status
        self.statusDate = str(status_date)
        self.obs = obs


class Database(Object):
    def __init__(self, schema):
        self.schema = schema
        self.client = pymongo.MongoClient(os.environ["MONGO"])
        self.db = self.client[schema]

    def get_schema(self):
        return self.db


class ImgRequest(Object):
    def __init__(self, imgType, imgUrl, eventId=None, _id=None, fileName=None, saved=False):
        self._id = bson.objectid.ObjectId()
        self.eventId = eventId
        self.imgType = imgType
        self.imgUrl = imgUrl
        self.fileName = fileName
        self.saved = saved

    def save_request(self, event):
        self.eventId = event.get_id()
        self.fileName = "profile/" + str(event.user_id) + self.imgType
        db = Database(os.environ["SCHEMA"]).get_schema()
        db.images.insert(self.__dict__)

    def update_image(self):
        db = Database(os.environ["SCHEMA"]).get_schema()
        db.images.update({"_id": self._id},
                         {"$set": {"saved": True}})

    @staticmethod
    def get_image(eventId):
        db = Database(os.environ["SCHEMA"]).get_schema()
        return db.images.find_one({"eventId": eventId})


# FACEBOOK OBJECTS

class Coordinates(Object):
    def __init__(self, lat, long):
        self.lat = lat
        self.long = long


class Payload(Object):
    def __init__(self, url=None, coordinates: Coordinates=None):
        self.url = url
        self.coordinates = coordinates


class Attachments(Object):
    def __init__(self, type=None, title=None, url=None, payload=None):
        self.title = title
        self.url = url
        self.type = type
        self.payload = payload


class Message(Object):
    def __init__(self, mid=None, seq=None, attachments: list=None, text=None, is_echo=None, app_id=None,
                 quick_reply=None, sticker_id=None):
        self.mid = mid
        self.seq = seq
        self.text = text
        self.attachments = attachments
        self.is_echo = is_echo
        self.quick_reply = quick_reply
        self.app_id = app_id
        self.sticker_id = sticker_id


class Messaging(Object):
    def __init__(self, sender, recipient, timestamp, message: Message = None, read=None, postback=None, delivery=None):
        self.sender = sender
        self.recipient = recipient
        self.timestamp = timestamp
        self.read = read
        self.postback = postback
        self.delivery = delivery
        self.message = message


class Postback(Object):
    def __init__(self, payload, title):
        self.payload = payload
        self.title = title


class Entry(Object):
    def __init__(self, id, time, standby: list=None, messaging: list = None):
        self.id = id
        self.time = time
        self.standby = standby
        self.messaging = messaging


class Sender(Object):
    def __init__(self, id):
        self.id = id


class Element(Object):
    def __init__(self, _id=None, title=None, subtitle=None, buttons: list = None):
        self._id = _id
        self.title = title
        self.subtitle = subtitle
        self.buttons = buttons


class Store(Object):
    def __init__(self, _id=None, title=None, tags=None, image_url=None, subtitle=None, buttons: list = None):
        self._id = _id
        self.title = title
        self.tags = tags
        self.image_url = image_url
        self.subtitle = subtitle
        self.buttons = buttons

    def get_store(self):
        obj = self.to_json_obj()
        obj = obj.pop("tags")
        return obj
