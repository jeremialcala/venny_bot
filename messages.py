import os
import json
from datetime import datetime
from urllib.request import urlretrieve

from objects import Messaging, Message, Attachments, Payload, Coordinates, Sender, Database, Event, ImgRequest
from tools import get_user_by_id, send_message, send_attachment, send_options


def process_message(msg: Messaging, event: Event):
    if msg.delivery is not None:
        return

    # Find this user
    sender = Sender(**msg.sender)
    message = Message(**msg.message)
    if message.is_echo is not None:
        return

    # ImgRequest(".png", user["profile_pic"]).save_request(event)
    # save_image(event)
    event.update("PRO", datetime.now(), "finding sender {} information".format(sender.id))
    user = who_send(sender)
    event.update("PRO", datetime.now(), "user found {first_name} status TyC {tyc}".format(first_name=user["first_name"]
                                                                                          , tyc=str(user["tyc"])))
    if user["tyc"] == 0:
        msg_text = get_speech("wellcome").format(user["first_name"])
        send_message(sender.id, msg_text, event)

        button = {"type": "web_url", "title": "+info", "url": "https://novopayment.com/privacy-policy/"}
        element = {"image_url": os.environ["VENNY_IMG"],
                   "title": "Venny",
                   "subtitle": "Terminos y Condiciones del Servicio",
                   "buttons": [button]}

        payload = {"template_type": "generic", "elements": [element]}
        attachment = {"type": "template", "payload": payload}
        response = {"attachment": attachment}
        send_attachment(recipient_id=sender.id, message=response, event=event)
        options = [{"content_type": "text", "title": "Acepto", "payload": "POSTBACK_PAYLOAD"},
                   {"content_type": "text", "title": "No Acepto", "payload": "POSTBACK_PAYLOAD"}]

        send_options(sender.id, options, get_speech("tyc_request"), event)
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
    db = Database(os.environ["SCHEMA"]).get_schema()
    result = db.users.find({"id": sender.id})
    if result.count() == 0:
        user = json.loads(get_user_by_id(sender.id))
        user["tyc"] = 0
        user["registerStatus"] = 0
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
