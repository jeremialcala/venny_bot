# -*- coding: utf8 -*-
import json
import os
import urllib.request
from datetime import datetime
from flask import Flask, request

from messages import process_message, process_postback
from objects import Event, Entry, Messaging, Attachments, Message, Payload, Coordinates

app = Flask(__name__)


@app.route('/', methods=['GET'])
def verify():
    event = Event(None, datetime.now(), "verify", "INI", datetime.now(), "New Verification")
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        event.update("PRO", datetime.now(), "hub.challenge")
        if not request.args.get("hub.verify_token") == os.environ["VERIFY_TOKEN"]:
            event.update("ERR", datetime.now(), "Verification token mismatch")
            return "Verification token mismatch", 403
        event.update("OK ", datetime.now(), "Verification OK")
        return request.args["hub.challenge"], 200
    return "Hello world", 200


@app.route("/", methods=["POST"])
def get_message():
    data = request.get_json()
    print(json.dumps(data))
    if "standby" in data["entry"][0]:
        Event(data["entry"][0]["standby"][0]["sender"]["id"], datetime.now(), "get_message", "INI", datetime.now(),
              "New Message from {}".format(data["entry"][0]["standby"][0]["sender"]["id"]))
        return "OK", 200

    event = Event(data["entry"][0]["messaging"][0]["sender"]["id"], datetime.now(), "get_message", "INI", datetime.now(),
                  "New Message from {}".format(data["entry"][0]["messaging"][0]["sender"]["id"]))

    # event.update("OK ", datetime.now(), json.dumps(data))
    entry = Entry(**data["entry"][0])
    message = Messaging(**entry.messaging[0])
    if "message" in entry.messaging[0]:
        process_message(message, event)
        event.update("OK ", datetime.now(), "Receive OK!")
        return "OK", 200

    if "postback" in entry.messaging[0]:
        process_postback(message, event)
        event.update("OK ", datetime.now(), "Receive OK!")
        return "OK", 200

    event.update("OK ", datetime.now(), "Receive OK!")
    return "OK", 200


if __name__ == '__main__':
    app.run(debug=True)
