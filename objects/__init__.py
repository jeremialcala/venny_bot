# -*- coding: utf8 -*-
import bson
import json
import pymongo
import os
from bson import ObjectId
from tools import log


class Object(object):
    def __init__(self, _id):
        pass

    def to_json(self):
        for element in self.__dict__:
            if type(self.__dict__[element]) is ObjectId:
                self[element] = str(element)
        return json.dumps(self.__dict__, sort_keys=False, indent=4, separators=(',', ': '))


class Event(Object):
    def __init__(self, start_date, event_type, status, status_date, obs=""):
        self._id = bson.objectid.ObjectId()
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
    def __init__(self, imgType, imgUrl, eventId=None, _id=None, fileName=None):
        self._id = bson.objectid.ObjectId()
        self.eventId = eventId
        self.imgType = imgType
        self.imgUrl = imgUrl
        self.fileName = fileName

    def save_request(self, event):
        self.eventId = event.get_id()
        self.fileName = event.type + "/" + str(event.get_id()) + self.imgType
        db = Database(os.environ["SCHEMA"]).get_schema()
        db.images.insert(self.__dict__)

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
    def __init__(self, mid, seq, attachments: list=None, text=None):
        self.mid = mid
        self.seq = seq
        self.text = text
        self.attachments = attachments


class Messaging(Object):
    def __init__(self, sender, recipient, timestamp, postback, message: Message, delivery=None):
        self.sender = sender
        self.recipient = recipient
        self.timestamp = timestamp
        self.postback = postback
        self.delivery = delivery
        self.message = message


class Postback(Object):
    def __init__(self, payload, title):
        self.payload = payload
        self.title = title


class Entry(Object):
    def __init__(self, id, time, messaging: list=None):
        self.id = id
        self.time = time
        self.messaging = messaging


class Sender(Object):
    def __init__(self, id):
        self.id = id
