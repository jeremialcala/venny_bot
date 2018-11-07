import os
import json
from datetime import datetime
from urllib.request import urlretrieve

from objects import Messaging, Message, Attachments, Payload, Coordinates, Sender, Database, Event, ImgRequest
from tools import get_user_by_id, send_message


def process_message(msg: Messaging, event: Event):
    # Find this user
    sender = Sender(**msg.sender)
    event.update("PRO", datetime.now(), "finding sender {} information".format(sender.id))
    message = Message(**msg.message)
    user = who_send(sender)
    ImgRequest(".png", user["profile_pic"]).save_request(event)
    save_image(event)
    if msg.delivery is not None:
        return
    if message.is_echo is not None:
        return

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
    result = db.users.find({"id": sender.id})
    if result.count() == 0:
        user = json.loads(get_user_by_id(sender.id))
        db.users.insert_one(user)
    else:
        for doc in result:
            return doc
    return user


def get_speech(type):
    db = Database(os.environ["SCHEMA"]).get_schema()
    text = "Hola"
    speech = db.speeches.find({"type": type})
    for elem in speech:
        text = elem["messages"][0]
    return text


def save_image(event):
    event.update("PRO", datetime.now(), "Saving Image")
    img = ImgRequest(**ImgRequest.get_image(event.get_id()))
    if img is None:
        return
    if img.saved:
        return
    event.update("PRO", datetime.now(), "Downloading Image from: " + img.imgUrl)
    from urllib.error import HTTPError
    try:
        rsp = urlretrieve(img.imgUrl, img.fileName)
        img.update_image()
        event.update("OK ", datetime.now(), rsp[0] + " Saved successfully!")
        return
    except HTTPError as e:
        event.update("ERR", datetime.now(), str(e.code) + " image " + e.msg)
        return
