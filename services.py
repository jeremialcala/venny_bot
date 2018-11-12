import json
import os
from datetime import datetime

import requests
from bson import ObjectId

from objects import Database
from tools import get_user_document_type, random_with_n_digits, get_account_from_pool, np_api_request, send_message

params = {"access_token": os.environ["PAGE_ACCESS_TOKEN"]}
headers = {"Content-Type": "application/json"}


def user_origination(user, db, event):
    data = {"card-number": "000712", "exp-date": "0320", "document-type": "CC", "document-number": "16084701",
            "name-1": " ", "name-2": " ", "last-name-1": "", "last-name-2": " ",
            "birth-date": "01/06/1982", "birth-place": "MEXICO", "nationality": "THEWORLD", "sex": "M",
            "marital-status": "S", "phone-1": " ", "phone-2": "00000000000", "phone-3": "00000000000",
            "email": "yecidaltahona1990@hotmail.com", "address-1": "Carrera 11 # 10 - 12",
            "code-address-1": "11001",
            "address-2": "Carrera 11 # 10 - 12", "code-address-2": "11001", "ocupation": "SOME",
            "work-status": "1", "work-center": "SOME PLACE", "work-center-id": "00000000",
            "work-center-position": "SOMEINFO", "monthly-income": "1.000,00", "govt-emp": "0",
            "govt-center": "", "branch-id": "1", "request-user": "JMENESES"}

    account = get_account_from_pool(db)

    data["card-number"] = account["cardNumber"]
    data["exp-date"] = account["fechaExp"]
    data["document-type"] = get_user_document_type(user)
    data["document-number"] = user["document"]["documentNumber"]
    data["name-1"] = user["first_name"]
    data["last-name-1"] = user["last_name"]
    data["last-name-2"] = user["last_name"]
    # data["birth-place"] = user["location"]["Address"]["Country"]
    data["phone-1"] = user["phoneNumber"]
    # data["address-2"] = user["location"]["Address"]["Label"]

    api_headers = {"x-country": "Usd",
                   "language": "es",
                   "channel": "API",
                   "accept": "application/json",
                   "Content-Type": "application/json",
                   "Authorization": "Bearer $OAUTH2TOKEN$"}

    api_headers["Authorization"] = api_headers["Authorization"].replace("$OAUTH2TOKEN$", os.environ["NP_OAUTH2_TOKEN"])

    url = os.environ["NP_URL"] + os.environ["CEOAPI"] + os.environ["CEOAPI_VER"] + \
          account["indx"] + "/employee?trxid=" + str(random_with_n_digits(10))
    print(url)

    api_response = np_api_request(url=url, data=data, api_headers=api_headers, event=event)
    print(api_response.text)
    if api_response.status_code == 200:
        db.accountPool.update({"_id": ObjectId(account["_id"])},
                              {"$set": {"codMisc": "AF"}})
        db.users.update({"id": user["id"]},
                        {'$set': {"accountId": account["_id"]}})
        return "OK", 200, account
    else:
        return api_response.text, api_response.status_code


def get_user_balance(user, db, event):
    account = db.accountPool.find_one({"_id": user["accountId"]})

    url = os.environ["NP_URL"] + os.environ["CEOAPI"] + os.environ["CEOAPI_VER"] \
          + account["indx"] + "/employee/" + user["document"]["documentNumber"] \
          + "/balance-inq?trxid=" + str(random_with_n_digits(10))

    api_headers = {"x-country": "Usd",
                   "language": "es",
                   "channel": "API",
                   "accept": "application/json",
                   "Content-Type": "application/json",
                   "Authorization": "Bearer $OAUTH2TOKEN$"}

    api_headers["Authorization"] = api_headers["Authorization"].replace("$OAUTH2TOKEN$", os.environ["NP_OAUTH2_TOKEN"])
    api_response = np_api_request(url=url, data=None, api_headers=api_headers, http_method="GET", event=event)

    if api_response.status_code == 200:
        attachment = {"type": "template"}
        payload = {"template_type": "generic", "elements": []}
        balance = json.loads(api_response.text)
        elements = {"title": "Cuenta: " + balance["card-number"],
                    "subtitle": "Saldo Disponible: " + balance["available-balance"],
                    "image_url": os.environ["IMG_PROC"] + os.environ["FACES_API"] + "card?Id=" + user["cardId"]}
        payload["elements"].append(elements)
        attachment["payload"] = payload
        recipient = {"id": user["id"]}
        rsp_message = {"attachment": attachment}
        data = {"recipient": recipient, "message": rsp_message}
        requests.post("https://graph.facebook.com/v2.6/me/messages", params=params,
                      headers=headers, data=json.dumps(data))
        return "OK", 200
    else:
        attachment = {"type": "template"}
        payload = {"template_type": "generic", "elements": []}
        elements = {"title": "En estos momentos no pude procesar tu operación.",
                    "subtitle": "available-balance: 0.00",
                    "image_url": os.environ["IMG_PROC"] + os.environ["FACES_API"] + "card?Id=" + user["cardId"]}
        payload["elements"].append(elements)
        attachment["payload"] = payload
        recipient = {"id": user["id"]}
        rsp_message = {"attachment": attachment}
        data = {"recipient": recipient, "message": rsp_message}
        requests.post("https://graph.facebook.com/v2.6/me/messages", params=params,
                      headers=headers, data=json.dumps(data))
        # send_message(user["id"], "En estos momentos no pude procesar tu operación.")
        return "OK", 200


def get_user_movements(user, db, event, mov_id=None):
    account = db.accountPool.find_one({"_id": user["accountId"]})
    if mov_id is None:
        url = os.environ["NP_URL"] + os.environ["CEOAPI"] + os.environ["CEOAPI_VER"] \
              + account["indx"] + "/employee/" + user["document"]["documentNumber"] \
              + "/mov-inq?trxid=" + str(random_with_n_digits(10))

        api_headers = {"x-country": "Usd",
                       "language": "es",
                       "channel": "API",
                       "accept": "application/json",
                       "Content-Type": "application/json",
                       "Authorization": "Bearer $OAUTH2TOKEN$"}

        api_headers["Authorization"] = api_headers["Authorization"]\
            .replace("$OAUTH2TOKEN$", os.environ["NP_OAUTH2_TOKEN"])

        api_response = np_api_request(url=url, data=None, api_headers=api_headers, http_method="GET", event=event)
        if api_response.status_code == 200:
            response = json.loads(api_response.text)

            if "mov-list" in response:
                movements = {
                    "userId": user["id"],
                    "movements": [],
                    "count": 1,
                    "page": 0,
                    "status": 1
                }
                print(type(response["mov-list"]))
                if type(response["mov-list"]) is dict:
                    movements["movements"].append(response["mov-list"])
                else:
                    movements["movements"] = response["mov-list"]
                    movements["count"] = len(response["mov-list"])

            mov_id = db.movements.insert(movements)
            movements["_id"] = mov_id
            create_mov_attachment(user, movements, db)
            return "OK", 200
        elif api_response.status_code == 404:
            send_message(user["id"], "No tienes movimientos registrados.", event)
        else:
            send_message(user["id"], "En estos momentos no pudimos procesar tu operación.", event)
            return "OK", 200

    else:
        criteria = {"_id": ObjectId(mov_id), "status": 1}
        movements = db.movements.find_one(criteria)

        if movements is None:
            send_message(user["id"], "No se encontraron movimientos...")
            return "OK", 200

        if movements["status"] == 0 or movements["page"] >= movements["count"]:
            db.movements.update({"_id": ObjectId(mov_id)},
                                {'$set': {"status": 0}})
            send_message(user["id"], "No hay mas movimientos...", event)
            return "OK", 200

        create_mov_attachment(user, movements, event)

        return "OK", 200


def create_mov_attachment(user, mov_list, db):
    attachment = {"type": "template"}
    payload = {"template_type": "generic", "elements": []}
    mov_count = mov_list["page"]

    while len(payload["elements"]) < 4 and mov_count < len(mov_list["movements"]):
        payload["elements"].append(
            {
                "title": mov_list["movements"][mov_count]["mov-desc"],
                "subtitle": "💰" + mov_list["movements"][mov_count]["mov-amount"] +
                            "\n🗓️" + mov_list["movements"][mov_count]["mov-date"]
            })
        mov_count = mov_count + 1

    if len(payload["elements"]) > 1:
        payload["top_element_style"] = "compact"
        payload["template_type"] = "list"

    if mov_list["count"] > 4 and (mov_list["count"] - mov_count) > 0:
        payload["buttons"] = [{"title": "View More", "type": "postback", "payload": "MOVEMENT_" +
                                                                                    str(mov_list["_id"])}]

    attachment["payload"] = payload
    recipient = {"id": user["id"]}
    rsp_message = {"attachment": attachment}
    data = {"recipient": recipient, "message": rsp_message}
    rsp = requests.post("https://graph.facebook.com/v2.6/me/messages", params=params,
                        headers=headers, data=json.dumps(data))
    print(rsp)
    db.movements.update({"_id": ObjectId(mov_list["_id"])},
                        {'$set': {"page": mov_count}})


def execute_send_money(transaction, db, event):
    print(transaction)
    api_headers = {"x-country": "Usd",
                   "language": "es",
                   "channel": "API",
                   "accept": "application/json",
                   "Content-Type": "application/json",
                   "Authorization": "Bearer $OAUTH2TOKEN$"}

    api_headers["Authorization"] = api_headers["Authorization"] \
        .replace("$OAUTH2TOKEN$", os.environ["NP_OAUTH2_TOKEN"])

    sender = db.users.find_one({"id": transaction["sender"]})
    print(sender)
    account_s = db.accountPool.find_one({"_id": ObjectId(sender["accountId"])})

    url = os.environ["NP_URL"] + os.environ["CEOAPI"] + os.environ["CEOAPI_VER"] + \
          account_s["indx"] + "/employee/" + sender["document"]["documentNumber"] + \
          "/debit-inq?trxid=" + str(random_with_n_digits(10))

    data = {"description": "Envio de dinero FB", "amount": transaction["amount"],
            "fee": "0.00", "ref-number": str(transaction["_id"])}
    api_response = np_api_request(url=url, data=data, api_headers=api_headers, http_method=None, event=event)
    response = json.loads(api_response.text)
    print(response)

    if api_response.status_code == 200:
        recipient = db.users.find_one({"id": transaction["recipient"]})
        account = db.accountPool.find_one({"_id": ObjectId(recipient["accountId"])})
        url = os.environ["NP_URL"] + os.environ["CEOAPI"] + os.environ["CEOAPI_VER"] \
              + account["indx"] + "/employee/" + recipient["document"]["documentNumber"] \
              + "/credit-inq?trxid=" + str(random_with_n_digits(10))
        api_response = np_api_request(url=url, data=data, api_headers=api_headers, http_method=None, event=event)
        if api_response.status_code == 200:
            send_message(sender["id"], "envio de dinero exitoso", event)
            send_message(recipient["id"], "Hola " + recipient["first_name"] + " hemos depositado en tu cuenta "
                         + transaction["amount"] + " a nombre de " + sender["first_name"], event)
            db.transactions.update({"_id": ObjectId(transaction["_id"])},
                                   {"$set": {"status": 5, "observations": response["msg"]}})
            return "OK", 200
        else:
            url = os.environ["NP_URL"] + os.environ["CEOAPI"] + os.environ["CEOAPI_VER"] \
                  + account_s["indx"] + "/employee/" + sender["document"]["documentNumber"] \
                  + "/credit-inq?trxid=" + str(random_with_n_digits(10))
            data = {"description": "Reverso envio de dinero FB", "amount": transaction["amount"],
                    "fee": "0.00", "ref-number": str(transaction["_id"])}
            api_response = np_api_request(url=url, data=data, api_headers=api_headers, http_method="GET", event=event)
            if api_response.status_code == 200:
                send_message(sender["id"], "no logramos hacer el envio, hemos ya reversado los fondos en tu cuenta.", event)
                db.transactions.update({"_id": ObjectId(transaction["_id"])},
                                       {"$set": {"status": 6, "observations": response["msg"]}})
    elif api_response.status_code == 400:
        response = json.loads(api_response.text)
        if response["rc"] == "51":
            send_message(sender["id"], "no cuentas con suficiente saldo, recarga el saldo en tu cuenta "
                                       "o intenta con un monto menor", event)
            db.transactions.update({"_id": ObjectId(transaction["_id"])},
                                   {"$set": {"status": 6, "observations": response["msg"]}})
            return "OK", 200
        else:
            send_message(sender["id"], response["msg"])
            db.transactions.update({"_id": ObjectId(transaction["_id"])},
                                   {"$set": {"status": 6}})
            return "OK", 200
    else:
        send_message(sender["id"], "no logramos hacer el envio, por favor intenta mas tarde.", event)
        db.transactions.update({"_id": ObjectId(transaction["_id"])},
                               {"$set": {"status": 6, "observations": response["msg"]}})
        return "OK", 200


def get_user_face(user, event):
    event.update("PRO", datetime.now(), "Processing get_user_face")
    headers = {"Content-Type": "application/json"}
    img_proc_url = os.environ["IMG_PROC"] + os.environ["FACES_API"] + "detect"
    data = {"imgUrl": user["profile_pic"], "imgType": ".jpg"}
    return requests.post(url=img_proc_url, headers=headers, data=json.dumps(data))


def validate_user_document(user, event):
    event.update("PRO", datetime.now(), "Processing validate_user_document")
    headers = {"Content-Type": "application/json"}
    img_proc_url = os.environ["IMG_PROC"] + os.environ["FACES_API"] + "verify"
    data = {"imgUrl": user["profile_pic"], "imgType": ".jpg", "docType": user["document"]["documentType"],
            "faceId": user["faceId"]}
    return requests.post(url=img_proc_url, headers=headers, data=json.dumps(data))


def create_user_card(user, event):
    event.update("PRO", datetime.now(), "Processing validate_user_document")
    db = Database("venny").get_schema()
    user = db.users.find_one({"id": user["id"]})
    account = db.accountPool.find_one({"_id": user["accountId"]})
    headers = {"Content-Type": "application/json"}
    img_proc_url = os.environ["IMG_PROC"] + os.environ["FACES_API"] + "card"
    data = {"firstName": user["first_name"], "lastName": user["last_name"], "account": account["cardNumber"],
            "faceId": user["faceId"]}
    return requests.post(url=img_proc_url, headers=headers, data=json.dumps(data))


def get_current_transaction(user):
    db = Database(os.environ["SCHEMA"]).get_schema()
    transactions = db.transactions.find({"sender": user["id"], "status": {"$gte": 2, "$lte": 3}})
    ccurr_transaction = {"status": 0, "observation": "Not Transaction found"}
    if transactions is None:
        return ccurr_transaction

    for transaction in transactions:
        print(transaction)
        transactionTime = datetime.now() - transaction["status-date"]
        print(transactionTime.seconds)
        if transactionTime.seconds > 180:
            db.transactions.update({"_id": ObjectId(transaction["_id"])},
                                   {"$set": {"status": 0}})
        else:
            return transaction

    return ccurr_transaction


def get_user_by_name(name, operation, db):
    if len(name) > 1:
        criteria = {"first_name": {"$regex": name[0]}, "last_name": {"$regex": name[1]}}
    else:
        criteria = {"first_name": {"$regex": name[0]}}
    print(criteria)
    result = db.users.find(criteria)

    attachment = {"type": "template"}
    payload = {"template_type": "generic", "elements": []}
    print(result.count())
    if result.count() is 0:
        return "No se encontraron usuarios", 404
    else:
        for friend in result:
            buttons = {}
            elements = {"buttons": [], "title": friend["first_name"] + " " + friend["last_name"],
                        "subtitle": friend["location"]["desc"],
                        "image_url": friend["profile_pic"]}
            buttons["title"] = "Enviar Dinero"
            buttons["type"] = "postback"
            buttons["payload"] = operation + "|" + friend["id"]
            elements["buttons"].append(buttons)
            payload["elements"].append(elements)
        if result.count() > 1:
            payload["template_type"] = "list"
            payload["top_element_style"] = "compact"
        attachment["payload"] = payload
        return "OK", 200, attachment
