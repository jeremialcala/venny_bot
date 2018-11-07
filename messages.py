import os
import json
from datetime import datetime

from objects import Messaging, Message, Attachments, Payload, Coordinates, Sender, Database, Event
from tools import get_user_by_id, send_message


def process_message(msg: Messaging, event: Event):
    # Find this user
    sender = Sender(**msg.sender)
    event.update("PRO", datetime.now(), "finding sender {} information".format(sender.id))
    message = Message(**msg.message)
    user = who_send(sender)
    print(user)
    if message.attachments is None:
        # This is only text
        msg_text = get_speech("wellcome").format(user["first_name"])
        send_message(sender.id, msg_text, event)
    else:
        attachments = Attachments(**message.attachments[0])
        # payload = Payload(**attachments.payload)
        # coodinates = Coordinates(**payload.coordinates)


def who_send(sender: Sender):
    db = Database("venny").get_schema()
    user = db.users.find({"id": sender.id})
    if user.count() == 0:
        user = json.loads(get_user_by_id(sender.id))
        if "first_name" not in user:
            user["first_name"] = "Friend"
    return user


def get_speech(type):
    db = Database(os.environ["SCHEMA"]).get_schema()
    text = "Hola"
    speech = db.speeches.find({"type": type})
    for elem in speech:
        text = elem["messages"][0]
    return text
