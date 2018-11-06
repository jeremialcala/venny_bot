# -*- coding: utf8 -*-
import bson
import json
import pymongo
import os
from bson import ObjectId
from tools import log


class Object:
    def __init__(self, _id):
        self._id = _id

    def to_json(self):
        for element in self.__dict__:
            if type(self[element]) is ObjectId:
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

    def to_json(self):
        self._id = str(self._id)
        return json.dumps(self.__dict__, sort_keys=True, indent=4, separators=(',', ': '))


class EventLog(Event):
    def __init__(self, event_id, status, status_date, obs):
        self._id = bson.objectid.ObjectId()
        self.eventId = event_id
        self.status = status
        self.statusDate = str(status_date)
        self.obs = obs


class Database(object):
    def __init__(self, schema):
        self.schema = schema
        self.client = pymongo.MongoClient(os.environ["MONGO"])
        self.db = self.client[schema]

    def get_schema(self):
        return self.db


class ImgRequest(object):
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
