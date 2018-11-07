import os
import json
from datetime import datetime
from urllib.request import urlretrieve

from objects import Messaging, Message, Attachments, Payload, Coordinates, Sender, Database, Event, ImgRequest, Element
from tools import get_user_by_id, send_message, send_attachment, send_options


def process_message(msg: Messaging, event: Event):
    if msg.delivery is not None:
        return

    # Find this user
    sender = Sender(**msg.sender)
    message = Message(**msg.message)
    if message.is_echo is not None:
        return

    if message.quick_reply is not None:
        event.update("PRO", datetime.now(), json.dumps(message.quick_reply))
        process_quick_reply(message, sender, event)
        return

    event.update("PRO", datetime.now(), "finding sender {} information".format(sender.id))
    user = who_send(sender)
    event.update("PRO", datetime.now(), "user found {first_name} status TyC {tyc}".format(first_name=user["first_name"]
                                                                                          , tyc=str(user["tyc"])))

    if is_registered(msg, event):
        return

    if message.attachments is None:
        # This is only text
        generate_response(user, message.text, event)
        return

    else:
        attachments = Attachments(**message.attachments[0])
        # payload = Payload(**attachments.payload)
        # coodinates = Coordinates(**payload.coordinates)


def process_quick_reply(message, sender, event):
    event.update("PRO", datetime.now(), "Processing quick_reply")
    db = Database(os.environ["SCHEMA"]).get_schema()
    if "ACCEPT_PAYLOAD" in message.quick_reply["payload"]:
        db.users.update({"id": sender.id},
                        {"$set": {"tyc": True,
                                  "registerStatus": 1,
                                  "dateTyC": datetime.now(),
                                  "statusDate": datetime.now()}})

        event.update("PRO", datetime.now(), "user {} accepted tyc successfully".format(sender.id))
        send_message(sender.id, get_speech("intro"), event)

    if "REJECT_PAYLOAD" in message.quick_reply["payload"]:
        event.update("PRO", datetime.now(), "user {} reject tyc!".format(sender.id))
        generate_response(who_send(sender), message.quick_reply["payload"], event)

    if "FIND_ACCOUNT_PAYLOAD" in message.quick_reply["payload"]:
        db.users.update({"id": sender.id},
                        {"$set": {"registerStatus": 1,
                                  "statusDate": datetime.now()}})
        send_message(sender.id, get_speech("gimme_account_number"), event)
        return True

    if "OPEN_ACCOUNT_PAYLOAD" in message.quick_reply["payload"]:
        db.users.update({"id": sender.id},
                        {"$set": {"registerStatus": 3,
                                  "statusDate": datetime.now()}})
        options = [{"content_type": "text", "title": "Credencial de elector", "payload": "CRELEC_PAYLOAD"},
                   {"content_type": "text", "title": "pasaporte", "payload": "PASSPORT_PAYLOAD"}]
        send_options(sender.id, options, get_speech("origination"), event)
        return True

    if "CRELEC_PAYLOAD" in message.quick_reply["payload"]:
        db.users.update({"id": sender.id},
                        {"$set": {"registerStatus": 4,
                                  "statusDate": datetime.now()}})
        send_message(sender.id, get_speech("gimme_picture_creelec"), event)
        return True

    if "PASSPORT_PAYLOAD" in message.quick_reply["payload"]:
        db.users.update({"id": sender.id},
                        {"$set": {"registerStatus": 5,
                                  "statusDate": datetime.now()}})
        send_message(sender.id, get_speech("gimme_picture_passport"), event)
        return True


def process_postback(msg: Messaging, event):
    event.update("PRO", datetime.now(), "Processing postback")
    sender = Sender(**msg.sender)
    event.update("PRO", datetime.now(), "finding sender {} information".format(sender.id))
    user = who_send(sender)
    event.update("PRO", datetime.now(), "user found {first_name} status TyC {tyc}".format(first_name=user["first_name"]
                                                                                          , tyc=str(user["tyc"])))
    db = Database(os.environ["SCHEMA"]).get_schema()
    if "GET_STARTED_PAYLOAD" in msg.postback["payload"]:
        if not user["tyc"]:
            send_tyc(sender, user, event)
        else:
            generate_response(user, "GET_STARTED_PAYLOAD", event)
        return True

    if "PAYBILL_PAYLOAD" in msg.postback["payload"]:
        return True


def is_registered(msg, event):
    event.update("PRO", datetime.now(), "Processing postback")
    sender = Sender(**msg.sender)
    event.update("PRO", datetime.now(), "finding sender {} information".format(sender.id))
    user = who_send(sender)
    event.update("PRO", datetime.now(), "user found {first_name} status TyC {tyc}".format(first_name=user["first_name"]
                                                                                          , tyc=str(user["tyc"])))
    if user["registerStatus"] == 1:
        options = [{"content_type": "text", "title": "Ingresar nro de cuenta", "payload": "FIND_ACCOUNT_PAYLOAD"},
                   {"content_type": "text", "title": "Abrir una cuenta Venn", "payload": "OPEN_ACCOUNT_PAYLOAD"}]
        send_options(sender.id, options, get_speech("account_not_found").format(first_name=user["first_name"]), event)
        return True

    if user["registerStatus"] == 2:
        send_message(sender.id, get_speech("gimme_account_number"), event)
        return True

    if user["registerStatus"] == 3:
        options = [{"content_type": "text", "title": "Credencial de elector", "payload": "CRELEC_PAYLOAD"},
                   {"content_type": "text", "title": "pasaporte", "payload": "PASSPORT_PAYLOAD"}]
        send_options(sender.id, options, get_speech("origination"), event)
        return True

    if user["registerStatus"] == 3:
        send_message(sender.id, get_speech("gimme_picture_creelec"), event)
        return True

    if user["registerStatus"] == 4:
        send_message(sender.id, get_speech("gimme_picture_passport"), event)
        return True


def who_send(sender: Sender):
    db = Database(os.environ["SCHEMA"]).get_schema()
    result = db.users.find({"id": sender.id})
    if result.count() == 0:
        user = json.loads(get_user_by_id(sender.id))
        print(json.dumps(user))
        user["tyc"] = False
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


def get_concept(text, event):
    event.update("PRO", datetime.now(), "looking in our dictionary for concepts")
    db = Database(os.environ["SCHEMA"]).get_schema()
    concepts = []
    for word in text.split(" "):
        event.update("PRO", datetime.now(), "looking for word {}".format(word))
        csr = db.dictionary.find({"words": word})
        for concept in csr:
            concepts.append(concept["concept"])

    return concepts


def generate_response(user, text, event):
    concepts = get_concept(text=text, event=event)
    if len(concepts) == 0:
        msg_text = get_speech("wellcome").format(user["first_name"])
        send_message(user["id"], msg_text, event)

    if "my_name" in concepts:
        elements = []
        db = Database(os.environ["SCHEMA"]).get_schema()
        csr = db.operations.find()
        for elem in csr:
            elem = Element(**elem)
            elements.append(elem.to_json_obj())

        payload = {"template_type": "generic", "elements": elements}
        attachment = {"type": "template", "payload": payload}
        response = {"attachment": attachment}
        send_attachment(recipient_id=user["id"], message=response, event=event)


def send_tyc(sender, user, event):
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
    options = [{"content_type": "text", "title": "Acepto", "payload": "ACCEPT_PAYLOAD"},
               {"content_type": "text", "title": "No Acepto", "payload": "REJECT_PAYLOAD"}]

    send_options(sender.id, options, get_speech("tyc_request"), event)
