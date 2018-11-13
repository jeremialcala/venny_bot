import os
import json
from datetime import datetime
from urllib.request import urlretrieve

import requests
from bson import ObjectId
from twilio.rest import Client

from objects import Messaging, Message, Attachments, Sender, Database, Event, ImgRequest, Element
from services import user_origination, get_user_face, validate_user_document, create_user_card, get_user_balance, \
    get_user_movements, get_user_by_name, execute_send_money, get_current_transaction
from tools import get_user_by_id, send_message, send_attachment, send_options, only_numeric, random_with_n_digits

params = {"access_token": os.environ["PAGE_ACCESS_TOKEN"]}
headers = {"Content-Type": "application/json"}


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

    if is_registering(msg, event):
        return

    event.update("PRO", datetime.now(), "finding sender {} information".format(sender.id))
    user = who_send(sender)
    event.update("PRO", datetime.now(), "user found {first_name} status TyC {tyc}".format(first_name=user["first_name"]
                                                                                          , tyc=str(user["tyc"])))
    db = Database(os.environ["SCHEMA"]).get_schema()

    if message.attachments is None:
        # This is only text
        generate_response(user, message.text, event)
        return
    else:
        attachments = Attachments(**message.attachments[0])
        # TODO: Validate attachment using faces!
        if user["registerStatus"] == 0:
            user["profile_pic"] = attachments.payload["url"]
            face = get_user_face(user, event)
            if face.status_code == 200:
                face_data = json.loads(face.text)
                prep_face_attachment(sender, face_data, event)
                if len(face_data["faces"]) == 0:
                    send_message(sender.id, get_speech("faces_not_found"), event)
                    return True

                db.users.update({"id": sender.id},
                                {"$set": {"tyc": True,
                                          "registerStatus": 1,
                                          "dateTyC": datetime.now(),
                                          "statusDate": datetime.now()}})
                event.update("PRO", datetime.now(), "user {} accepted tyc successfully".format(sender.id))

        if user["registerStatus"] == 4:
            send_message(sender.id, get_speech("validating"), event)
            db.users.update({"id": sender.id},
                            {"$set": {"registerStatus": 6,
                                      "statusDate": datetime.now()}})
            send_message(sender.id, get_speech("document_response"), event)
            return True

        if user["registerStatus"] == 5:
            send_message(sender.id, get_speech("validating"), event)
            user["profile_pic"] = attachments.payload["url"]
            document = validate_user_document(user, event)
            print(document.text)
            if document.status_code == 200:
                verify = json.loads(document.text)
                if not verify["match"]:
                    send_message(sender.id, get_speech("document_face_not_match"))
                    return True
                options = [{"content_type": "text", "title": "Correcto!", "payload": "RIGHT_DATA_PAYLOAD"},
                           {"content_type": "text", "title": "Esta mal!", "payload": "WRONG_DATA_PAYLOAD"}]
                send_options(sender.id, options, get_speech("document_information")
                             .format(firstName=user["firstName"],
                                     number=verify["number"],
                                     firstPName=verify["firstName"],
                                     middleName=verify["middleName"],
                                     lastName=verify["lastName"],
                                     secondSurname=verify["secondSurname"],
                                     birthDate=verify["birthDate"],
                                     expDate=verify["expDate"]), event)


def process_quick_reply(message, sender, event):
    event.update("PRO", datetime.now(), "Processing quick_reply")
    db = Database(os.environ["SCHEMA"]).get_schema()
    user = who_send(sender)

    if "ACCEPT_PAYLOAD" in message.quick_reply["payload"]:
        user = who_send(sender)
        face = get_user_face(user, event)
        if face.status_code == 200:
            face_data = json.loads(face.text)
            prep_face_attachment(sender, face_data, event)
            if len(face_data["faces"]) == 0:
                send_message(sender.id, get_speech("faces_not_found"), event)
                return True

            db.users.update({"id": sender.id},
                            {"$set": {"tyc": True,
                                      "registerStatus": 1,
                                      "dateTyC": datetime.now(),
                                      "statusDate": datetime.now()}})
            event.update("PRO", datetime.now(), "user {} accepted tyc successfully".format(sender.id))

        return True

    if "REJECT_PAYLOAD" in message.quick_reply["payload"]:
        event.update("PRO", datetime.now(), "user {} reject tyc!".format(sender.id))
        generate_response(who_send(sender), message.quick_reply["payload"], event)
        return True

    if "FIND_ACCOUNT_PAYLOAD" in message.quick_reply["payload"]:
        db.users.update({"id": sender.id},
                        {"$set": {"registerStatus": 2,
                                  "statusDate": datetime.now()}})
        send_message(sender.id, get_speech("gimme_account_number"), event)
        return True

    if "OPEN_ACCOUNT_PAYLOAD" in message.quick_reply["payload"]:
        db.users.update({"id": sender.id},
                        {"$set": {"registerStatus": 3,
                                  "statusDate": datetime.now()}})
        options = [{"content_type": "text", "title": "Pasaporte", "payload": "PASSPORT_PAYLOAD"},
                   {"content_type": "text", "title": "C. Elector", "payload": "CRELEC_PAYLOAD"}]
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
                                  "statusDate": datetime.now(),
                                  "document": {"documentType": "passporte"}}})

        send_message(sender.id, get_speech("gimme_picture_passport"), event)
        return True

    if "+" in message.quick_reply["payload"]:
        db.users.update({"id": sender.id},
                        {"$set": {"phoneNumber": message.quick_reply["payload"],
                                  "registerStatus": 7,
                                  "statusDate": datetime.now()}})
        options = [{"content_type": "user_email"}]
        send_options(sender.id, options, get_speech("confirm_email"), event)
        return True

    if "@" in message.quick_reply["payload"]:
        db.users.update({"id": sender.id},
                        {"$set": {"email": message.quick_reply["payload"],
                                  "registerStatus": 8,
                                  "statusDate": datetime.now()}})
        options = [{"content_type": "text", "title": "SMS", "payload": "SMS_CODE_PAYLOAD"},
                   {"content_type": "text", "title": "Email", "payload": "EMAIL_CODE_PAYLOAD"}]
        send_options(sender.id, options, get_speech("confirmation_code_send_location"), event)
        return True

    if "SMS_CODE_PAYLOAD" in message.quick_reply["payload"]:
        confirmation = random_with_n_digits(5)
        user = who_send(sender)
        client = Client(os.environ["ACCOUNT_ID"], os.environ["AUTH_TOKEN"])
        client.messages.create(
            from_=os.environ["SMS_ORI"],
            to=user["phoneNumber"],
            body="Tu clave de temporal es: " + str(confirmation)
        )
        db.users.update({"id": sender.id},
                        {"$set": {"confirmation": confirmation,
                                  "confirmationDate": datetime.now(),
                                  "registerStatus": 9,
                                  "statusDate": datetime.now()}})
        send_message(sender.id, get_speech("confirmation_code_send"), event)
        return True

    if "ACCOUNT_CONFIRM_PAYLOAD" in message.quick_reply["payload"]:
        send_message(sender.id, get_speech("account_creation_start"), event)
        origination = user_origination(user, db, event)
        if origination[1] == 200:
            card = create_user_card(user, event)
            if card.status_code == 200:
                card_data = json.loads(card.text)
                db.users.update({"id": sender.id},
                                {'$set': {"registerStatus": 11,
                                          "statusDate": datetime.now(),
                                          "cardId": card_data["card"]["_id"]}})
            else:
                db.users.update({"id": sender.id},
                                {'$set': {"registerStatus": 11,
                                          "statusDate": datetime.now()}})

            send_message(sender.id, get_speech("account_creation_success"), event)

            send_operation(user, db, event)
        else:
            send_message(sender.id, get_speech("account_creation_fail"), event)

    if "SEND_" in message.quick_reply["payload"]:
        action = message.quick_reply["payload"].split("_")
        transaction = db.transactions.find_one({"_id": ObjectId(action[2])})
        if transaction is None:
            send_message(user["id"], "oye " + user["fist_name"]
                         + ", no recuerdo a quien querias enviar dinero.", event)
            return "OK", 200

        if "OTHER" in message.quick_reply["payload"]:
            send_message(user["id"], "indicame el monto que quieres enviar", event)
            return "OK", 200

        db.transactions.update({"_id": ObjectId(transaction["_id"])},
                               {"$set": {"amount": action[1],
                                         "status": 3}})
        send_payment_receipt(transaction, db, event)
        options = [{"content_type": "text", "title": "Si", "payload": "TRX_Y_MSG_" + str(transaction["_id"])},
                   {"content_type": "text", "title": "No", "payload": "TRX_N_MSG_" + str(transaction["_id"])}]
        # send_options(user["id"], options, get_speech("money_send_description"), event)

    if "COLLECT_" in message.quick_reply["payload"]:
        action = message.quick_reply["payload"].split("_")
        transaction = db.transactions.find_one({"_id": ObjectId(action[2])})
        if transaction is None:
            send_message(user["id"], "oye " + user["fist_name"]
                         + ", no recuerdo a quien querias solicitar dinero.", event)
            return "OK", 200

        if "OTHER" in message.quick_reply["payload"]:
            send_message(user["id"], "indicame el monto que quieres solicitar", event)
            return "OK", 200

        db.transactions.update({"_id": ObjectId(transaction["_id"])},
                               {"$set": {"amount": action[1],
                                         "status": 3}})

        send_payment_receipt(transaction, db, event)
        options = [{"content_type": "text", "title": "Si", "payload": "TRX_Y_MSG_" + str(transaction["_id"])},
                   {"content_type": "text", "title": "No", "payload": "TRX_N_MSG_" + str(transaction["_id"])}]
        # send_options(user["id"], options, get_speech("money_collect_description"), event)

    if "TRX_" in message.quick_reply["payload"]:
        action = message.quick_reply["payload"].split("_")
        transaction = db.transactions.find_one({"_id": ObjectId(action[3])})

        for item in action:
            print(type(item))

        if action[1] is "N":
            send_payment_receipt(transaction, db, event)
            return "OK", 200

        if action[1] is "Y":
            send_message(user["id"], "indicame la descripcion de la operación?", event)
            send_message(user["id"], "colocala asi: \"pago por\" + \"motivo del pago\" ", event)
            return "OK", 200

        if "CONFIRM" in message.quick_reply["payload"]:
            send_message(transaction["sender"], "Ejecutando", event)
            execute_send_money(transaction, db, event)
            return "OK", 200

        if "CANCEL" in message.quick_reply["payload"]:
            send_message(user["id"], "Vale! cancelamos tu transaccion", event)
            db.transactions.update({"_id": ObjectId(transaction["_id"])},
                                   {"$set": {"status": 6}})
            return "OK", 200


def process_postback(msg: Messaging, event):
    event.update("PRO", datetime.now(), "Processing postback")
    sender = Sender(**msg.sender)
    event.update("PRO", datetime.now(), "finding sender {} information".format(sender.id))
    user = who_send(sender)
    event.update("PRO", datetime.now(), "user found {first_name} status TyC {tyc}".format(first_name=user["first_name"],
                                                                                          tyc=str(user["tyc"])))
    db = Database(os.environ["SCHEMA"]).get_schema()
    if "GET_STARTED_PAYLOAD" in msg.postback["payload"]:
        if not user["tyc"]:
            send_tyc(sender, user, event)
        elif is_registering(msg, event):
            return True
        else:
            send_operation(user, db, event)
        return True

    if "MY_FACE_IS_" in msg.postback["payload"]:
        faceId = msg.postback["payload"].split("_")[3]
        db.users.update({"id": sender.id},
                        {"$set": {"faceId": faceId,
                                  "faceDate": datetime.now()}})
        event.update("PRO", datetime.now(), "face information of {} save successfully".format(sender.id))

        send_message(sender.id, get_speech("intro"), event)
        return True

    if "BALANCE_PAYLOAD" in msg.postback["payload"]:
        get_user_balance(user, db, event)
        return True

    if "MOVEMENT" in msg.postback["payload"]:
        if "PAYLOAD" not in msg.postback["payload"]:
            mov_id = str(msg.postback["payload"]).split("_")
            print(mov_id[1])
            get_user_movements(user, db, event)
            return True

        get_user_movements(user, db, event)
        return True

    if "PAYBILL_PAYLOAD" in msg.postback["payload"]:
        send_message(sender.id, get_speech("money_send_start").format(user["first_name"]), event)
        db.users.update({"id": user['id']},
                        {'$set': {"operationStatus": 1}})

        return True

    if "COLLECT_PAYLOAD" in msg.postback["payload"]:
        send_message(sender.id, get_speech("money_collect_start").format(user["first_name"]), event)
        db.users.update({"id": user['id']},
                        {'$set': {"operationStatus": 2}})
        return True

    if "SEND_MONEY" in msg.postback["payload"]:
        action = msg.postback["payload"].split("|")
        friend = db.users.find_one({"id": action[1]})
        transaction = {"sender": user["id"], "recipient": friend["id"], "type": 1, "status": 2,
                       "status-date": datetime.now()}
        transaction_id = db.transactions.insert(transaction)

        options = [{"content_type": "text", "title": "$2", "payload": "SEND_2_" + str(transaction_id)},
                   {"content_type": "text", "title": "$5", "payload": "SEND_5_" + str(transaction_id)},
                   {"content_type": "text", "title": "$10", "payload": "SEND_10_" + str(transaction_id)}]
        send_options(sender.id, options, get_speech("money_send_amount"), event)

    if "COLLECT_MONEY" in msg.postback["payload"]:
        action = msg.postback["payload"].split("|")
        friend = db.users.find_one({"id": action[1]})
        transaction = {"sender": friend["id"], "recipient": user["id"], "type": 2, "status": 2,
                       "status-date": datetime.now()}
        transaction_id = db.transactions.insert(transaction)

        options = [{"content_type": "text", "title": "$2", "payload": "COLLECT_2_" + str(transaction_id)},
                   {"content_type": "text", "title": "$5", "payload": "COLLECT_5_" + str(transaction_id)},
                   {"content_type": "text", "title": "$10", "payload": "COLLECT_10_" + str(transaction_id)}]
        send_options(sender.id, options, get_speech("money_collect_amount"), event)


def is_registering(msg, event):
    event.update("PRO", datetime.now(), "Processing is_registered")
    sender = Sender(**msg.sender)
    event.update("PRO", datetime.now(), "finding sender {} information".format(sender.id))
    user = who_send(sender)
    event.update("PRO", datetime.now(), "user found {first_name} status TyC {tyc}".format(first_name=user["first_name"]
                                                                                      , tyc=str(user["tyc"])))
    if msg.message is not None:
        message = Message(**msg.message)
    db = Database(os.environ["SCHEMA"]).get_schema()

    if user["registerStatus"] == 1:
        options = [{"content_type": "text", "title": "Abrir cuenta", "payload": "OPEN_ACCOUNT_PAYLOAD"},
                    {"content_type": "text", "title": "Num. Cta.", "payload": "FIND_ACCOUNT_PAYLOAD"}]
        send_options(sender.id, options, get_speech("account_not_found").format(first_name=user["first_name"]), event)
        return True

    if user["registerStatus"] == 2:
        if message.text is not None:
            acc_num = only_numeric(message.text)
            if acc_num["rc"] == 0:
                options = [
                    {"content_type": "text", "title": "Abrir cuenta", "payload": "OPEN_ACCOUNT_PAYLOAD"},
                    {"content_type": "text", "title": "Escribir un email", "payload": "SEND_MAIL_PAYLOAD"}]
                send_options(sender.id, options, get_speech("account_not_found_msg").format(first_name=user["first_name"]),
                             event)
                return True
        send_message(sender.id, get_speech("gimme_account_number"), event)
        return True

    if user["registerStatus"] == 3:
        options = [{"content_type": "text", "title": "C. Elector", "payload": "CRELEC_PAYLOAD"},
                   {"content_type": "text", "title": "Pasaporte", "payload": "PASSPORT_PAYLOAD"}]
        send_options(sender.id, options, get_speech("origination"), event)
        return True

    if user["registerStatus"] == 4:
        if message.attachments is not None:
            if message.attachments[0]["type"] == "image":
                send_message(sender.id, get_speech("validating"), event)
                db.users.update({"id": sender.id},
                                {"$set": {"registerStatus": 6,
                                          "statusDate": datetime.now()}})
                send_message(sender.id, get_speech("document_response"), event)
                options = [{"content_type": "location"}]
                send_options(sender.id, options, get_speech("gimme_location"), event)
            return True
        send_message(sender.id, get_speech("gimme_picture_creelec"), event)
        return True

    if user["registerStatus"] == 5:
        if message.attachments is not None:
            if message.attachments[0]["type"] == "image":
                send_message(sender.id, get_speech("validating"), event)
                user["profile_pic"] = message.attachments[0]["payload"]["url"]
                document = validate_user_document(user, event)
                print(document.text)
                if document.status_code == 200:
                    verify = json.loads(document.text)
                    if not verify["match"]:
                        send_message(sender.id, get_speech("document_face_not_match"), event)
                        return True
                    send_message(sender.id, get_speech("document_information").format(firstName=user["first_name"],
                                                                                      documentType=user["document"]
                                                                                      ["documentType"],
                                                                                      number=verify["mrz"]
                                                                                      ["number"]), event)
                    db.users.update({"id": sender.id},
                                    {"$set": {"document": {"documentType": "passporte",
                                                           "documentNumber": verify["mrz"]["number"]},
                                              "registerStatus": 6,
                                              "statusDate": datetime.now()}})
                    options = [{"content_type": "location"}]
                    send_options(sender.id, options, get_speech("gimme_location"), event)
                    return True
        send_message(sender.id, get_speech("gimme_picture_passport"), event)
        return True

    if user["registerStatus"] == 6:
        if message.attachments is not None:
            if message.attachments[0]["type"] == "location":
                location = {"desc":  message.attachments[0]["title"], "url":  message.attachments[0]["url"],
                            "coordinates":  message.attachments[0]["payload"]["coordinates"]}
                db.users.update({"id": sender.id},
                                {"$set": {"registerStatus": 7,
                                          "statusDate": datetime.now(),
                                          "location": location,
                                          "locationDate": datetime.now()}})
                options = [{"content_type": "user_phone_number"}]
                send_options(sender.id, options, get_speech("confirm_phone_number"), event)
                return True
        options = [{"content_type": "location"}]
        send_options(sender.id, options, get_speech("gimme_location"), event)
        return True

    if user["registerStatus"] == 9:
        if message.text is not None:
            confirmation = only_numeric(message.text)
            if confirmation["rc"] == 0:
                if str(user["confirmation"]) == confirmation["numbers"]:
                    confirmationTime = datetime.now() - user["confirmationDate"]
                    if confirmationTime.seconds > 180:
                        send_message(user["id"], "El código ya expiro. ",event)
                        db.users.update({"id": sender.id},
                                        {"$set": {"registerStatus": 8,
                                                  "statusDate": datetime.now()}})
                        options = [{"content_type": "text", "title": "SMS", "payload": "SMS_CODE_PAYLOAD"},
                                   {"content_type": "text", "title": "Email", "payload": "EMAIL_CODE_PAYLOAD"}]
                        send_options(sender.id, options, get_speech("confirmation_code_send_location"), event)
                        return True
                    options = [
                        {"content_type": "text", "title": "Autorizar", "payload": "ACCOUNT_CONFIRM_PAYLOAD"},
                        {"content_type": "text", "title": "Cancelar", "payload": "CANCEL_PAYLOAD"}]
                    send_options(sender.id, options, get_speech("code_confirm").format(first_name=user["first_name"]),
                                 event)
                    db.users.update({"id": sender.id},
                                    {"$set": {"registerStatus": 10,
                                              "statusDate": datetime.now()}})
                    return True
                else:
                    send_message(sender.id, get_speech("confirmation_code_wrong"), event)
                return True
        send_message(sender.id, get_speech("confirmation_code_send"), event)
        return True

    if user["registerStatus"] == 10:
        options = [
            {"content_type": "text", "title": "Autorizar", "payload": "ACCOUNT_CONFIRM_PAYLOAD"},
            {"content_type": "text", "title": "Cancelar", "payload": "CANCEL_PAYLOAD"}]
        send_options(sender.id, options, get_speech("code_confirm").format(first_name=user["first_name"]),
                     event)

    return False
    # generate_response(user, "GET_STARTED_PAYLOAD", event)


def who_send(sender: Sender):
    db = Database(os.environ["SCHEMA"]).get_schema()
    result = db.users.find({"id": sender.id})
    if result.count() == 0:
        user = json.loads(get_user_by_id(sender.id))
        user["tyc"] = False
        user["registerStatus"] = 0
        user["operationStatus"] = 0
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
        csr = db.dictionary.find({"words": str(word).lower()})
        for concept in csr:
            concepts.append(concept["concept"])

    return concepts


def generate_response(user, text, event):
    concepts = get_concept(text=text, event=event)
    db = Database(os.environ["SCHEMA"]).get_schema()
    print("CONCEPTS: " + str(concepts))
    if "my_name" in concepts and user["registerStatus"] == 11:
        elements = []
        csr = db.operations.find()
        for elem in csr:
            elem = Element(**elem)
            elements.append(elem.to_json_obj())

        payload = {"template_type": "generic", "elements": elements}
        attachment = {"type": "template", "payload": payload}
        response = {"attachment": attachment}
        send_attachment(recipient_id=user["id"], message=response, event=event)

    if "balance" in concepts and user["registerStatus"] == 11:
        get_user_balance(user, db, event)
        return True

    if "movements" in concepts and user["registerStatus"] == 11:
        get_user_movements(user, db, event)
        return True

    if "money_send" in concepts and user["registerStatus"] == 11:
        send_message(user["id"], get_speech("money_send_start").format(user["first_name"]), event)
        db.users.update({"id": user['id']},
                        {'$set': {"operationStatus": 1}})
        return True

    if "money_collect" in concepts and user["registerStatus"] == 11:
        send_message(user["id"], get_speech("money_collect_start").format(user["first_name"]), event)
        db.users.update({"id": user['id']},
                        {'$set': {"operationStatus": 2}})
        return True

    if user["operationStatus"] == 1:
        rsp = get_user_by_name(name=text.split(" "), operation="SEND_MONEY", db=db)
        print(rsp)
        if rsp[1] == 200:
            send_message(user["id"], get_speech("money_send_select"), event)
            attachment = rsp[2]
            rsp_message = {"attachment": attachment}
            send_attachment(user["id"], rsp_message, event)
            db.users.update({"id": user['id']},
                            {'$set': {"operationStatus": 0}})
            return True

    if user["operationStatus"] == 2:
        rsp = get_user_by_name(name=text.split(" "), operation="COLLECT_MONEY", db=db)
        print(rsp)
        if rsp[1] == 200:
            send_message(user["id"], get_speech("money_collect_select"), event)
            attachment = rsp[2]
            rsp_message = {"attachment": attachment}
            send_attachment(user["id"], rsp_message, event)
            db.users.update({"id": user['id']},
                            {'$set': {"operationStatus": 0}})
            return True

    transaction = get_current_transaction(user)

    if transaction["status"] == 2:
        amount = only_numeric(text, amount=True)
        if amount["rc"] is 0:
            db.transactions.update({"_id": ObjectId(transaction["_id"])},
                                   {"$set": {"amount": amount["numbers"],
                                             "status": 3}})
            options = [
                {"content_type": "text", "title": "Si", "payload": "TRX_Y_MSG_" + str(transaction["_id"])},
                {"content_type": "text", "title": "No", "payload": "TRX_N_MSG_" + str(transaction["_id"])}]
            send_options(user["id"], options, "te gustaria enviar una descripción de tu pago?")
            return True

    if "payment" in concepts and transaction["status"] == 3:
        transaction["description"] = text
        send_payment_receipt(transaction, db, event)
        return True

    if len(concepts) == 0:
        msg_text = get_speech("wellcome").format(user["first_name"])
        send_message(user["id"], msg_text, event)
        return True


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


def send_operation(user, db, event):
    elements = []
    csr = db.operations.find()
    for elem in csr:
        elem = Element(**elem)
        elements.append(elem.to_json_obj())

    payload = {"template_type": "generic", "elements": elements}
    attachment = {"type": "template", "payload": payload}
    response = {"attachment": attachment}
    send_attachment(recipient_id=user["id"], message=response, event=event)


def prep_face_attachment(sender, face_data, event):
    img_url = os.environ["IMG_PROC"] + os.environ["FACES_API"] + "image?file="
    attachment = {"type": "template"}
    payload = {"template_type": "generic", "elements": []}

    send_message(sender.id, get_speech("faces_multiple_found").format(str(len(face_data["faces"]))), event)
    for image in face_data["faces"]:
        buttons = {}
        elements = {"buttons": [], "title": "Este es tu rostro?",
                    "image_url": img_url + image["fileName"]}
        buttons["title"] = "Si! lo es..."
        buttons["type"] = "postback"
        buttons["payload"] = "MY_FACE_IS_" + image["_id"]
        elements["buttons"].append(buttons)
        payload["elements"].append(elements)
    if len(face_data["faces"]) > 1:
        payload["template_type"] = "list"
        payload["top_element_style"] = "compact"
    attachment["payload"] = payload
    response = {"attachment": attachment}
    send_attachment(recipient_id=sender.id, message=response, event=event)


def send_payment_receipt(transaction, db, event):
    user = db.users.find_one({"id": transaction["sender"]})
    friend = db.users.find_one({"id": transaction["recipient"]})

    account = db.accountPool.find_one({"_id": ObjectId(user["accountId"])})

    payload = {"template_type": "receipt", "recipient_name": friend["first_name"],
               "order_number": str(transaction["_id"]), "currency": "USD",
               "payment_method": "VISA " + account["cardNumber"][2:], "order_url": "",
               "timestamp": str(datetime.timestamp(datetime.now())).split(".")[0],
               "summary": {"total_cost": transaction["amount"]}, "elements": []}

    element = {"title": "Envio de Dinero a " + friend["first_name"],
               "subtitle": "Envio de Dinero", "price": transaction["amount"], "currency": "USD",
               "image_url": friend["profile_pic"]}

    if "description" in transaction:
        element["subtitle"] = transaction["description"]
        db.transactions.update({"_id": ObjectId(transaction["_id"])},
                               {"$set": {"description": transaction["description"]}})

    payload["elements"].append(element)
    message = {"attachment": {"type": "template", "payload": payload}}
    data = {"recipient": {"id": user["id"]}, "message": message}
    db.transactions.update({"_id": ObjectId(transaction["_id"])},
                           {"$set": {"status": 4}})
    print(data)
    rsp = requests.post("https://graph.facebook.com/v2.6/me/messages", params=params,
                        headers=headers,
                        data=json.dumps(data))
    print(rsp.text)
    options = [
        {"content_type": "text", "title": "Confirmado", "payload": "TRX_DO_CONFIRM_" + str(transaction["_id"])},
        {"content_type": "text", "title": "Cancelar", "payload": "TRX_DO_CANCEL_" + str(transaction["_id"])}]

    send_options(user["id"], options, get_speech("money_send_confirm"), event)
    if transaction["type"] == 2:
        send_message(transaction["recipient"], get_speech("money_collect_confirm").format(user["first_name"]), event)
