# -*- coding: utf8 -*-
import hashlib
import sys
import time
import os
from random import randint

import requests
import json
from urllib.request import urlretrieve
from datetime import datetime
from bson import ObjectId
import objects

params = {"access_token": os.environ["PAGE_ACCESS_TOKEN"]}
headers = {"Content-Type": "application/json"}


def new_session():
    h = hashlib.new("md5")
    session = str(datetime.timestamp(datetime.now()))
    h.update(bytearray(session.encode("utf8")))
    return h.hexdigest()


def log(event):  # simple wrapper for logging to stdout on heroku
    print(" [" + event.status + "][" + str(event.get_id()) + "] " + event.obs)
    sys.stdout.flush()


def get_timestamp(component='CORE'):
    return datetime.fromtimestamp(time.time()).strftime('[%Y.%m.%d %H:%M:%S.%f')[:-3] + '][' + component + ']'


def save_image(event):
    event.update("PRO", datetime.now(), "Saving Image")
    img = objects.ImgRequest(**objects.ImgRequest.get_image(event.get_id()))
    if img is None:
        return "Image request not found!", 404
    event.update("PRO", datetime.now(), "Downloading Image from: " + img.imgUrl)

    from urllib.error import HTTPError
    try:
        rsp = urlretrieve(img.imgUrl, img.fileName)
        event.update("OK ", datetime.now(), rsp[0] + " Saved successfully!")
        return True
    except HTTPError as e:
        event.update("ERR", datetime.now(), str(e.code) + " image " + e.msg)
        return False


def generate_response(event):
    event = event.get_last_event()
    for elem in event:
        if type(event[elem]) is ObjectId:
            event[elem] = str(event[elem])
    return event


def get_user_by_id(user_id):
    url = "https://graph.facebook.com/USER_ID?&access_token="
    url = url.replace("USER_ID", user_id) + os.environ["PAGE_ACCESS_TOKEN"]
    r = requests.get(url)
    if r.status_code != 200:
        return r.text
    else:
        return r.text


def send_message(recipient_id, message_text, event):
    event.update("PRO", datetime.now(), "sending message to {recipient}: {text}".format(recipient=recipient_id,
                                                                                        text=message_text))
    data = json.dumps({"recipient": {"id": recipient_id}, "message": {"text": message_text}})
    print(data)
    requests.post("https://graph.facebook.com/v2.6/me/messages", params=params, headers=headers, data=data)


def send_attachment(recipient_id, message, event):
    event.update("PRO", datetime.now(), "sending attachment to {recipient}".format(recipient=recipient_id))
    data = {"recipient": {"id": recipient_id}, "message": message}
    event.update("PRO", datetime.now(), "data: {}".format(json.dumps(data)))
    requests.post("https://graph.facebook.com/v2.6/me/messages", params=params, headers=headers, data=json.dumps(data))


def send_options(recipient_id, options, text, event):
    event.update("PRO", datetime.now(), "sending attachment to {recipient}".format(recipient=recipient_id))
    data = {"recipient": {"id": recipient_id}, "message": {"text": text, "quick_replies": []}}
    for option in options:
        data["message"]["quick_replies"].append(option)
        print(json.dumps(data))
    requests.post("https://graph.facebook.com/v2.6/me/messages", params=params, headers=headers, data=json.dumps(data))


def only_numeric(text, amount=False):
    numbs = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
    if amount:
        numbs.append('.')
    resp = ""
    for char in text:
        if char in numbs:
            resp += char
    if len(text) != len(resp) and len(resp) != 0:
        return {"rc": -123, "msg": "no todos los caracteres no son numeros", "numbers": resp}
    elif len(resp) == 0:
        return {"rc": -500, "msg": "no hay numeros en este texto", "numbers": resp}
    return {"rc": 0, "msg": "Process OK", "numbers": resp}


def random_with_n_digits(n):
    range_start = 10 ** (n - 1)
    range_end = (10 ** n) - 1
    return randint(range_start, range_end)


def get_user_document_type(user):
    if user["document"]["documentType"] == "cedula":
        return "CC"
    else:
        return "PA"


def get_account_from_pool(db):
    criteria = {"codMisc": "SA"}
    return db.accountPool.find_one(criteria)


def np_api_request(url, data, api_headers, event, api_params=None, http_method=None):
    event.update("PRO", datetime.now(), "Conectando a: " + url)
    if http_method is "GET":
        api_response = requests.get(url, headers=api_headers)
    else:
        print("Data:" + json.dumps(data))
        api_response = requests.post(url, params=api_params, headers=api_headers, data=json.dumps(data))

    event.update("PRO", datetime.now(), "response: " + api_response.text)
    event.update("PRO", datetime.now(), "status_code: " + str(api_response.status_code))
    if api_response.status_code == 401:
        os.environ["NP_OAUTH2_TOKEN"] = get_oauth_token()
        api_headers["Authorization"] = "Bearer " + os.environ["NP_OAUTH2_TOKEN"]
        return np_api_request(url, data, api_headers, api_params, http_method)
    else:
        return api_response


def get_oauth_token():
    api_headers = {"x-channel": "web",
                   "x-language": "es",
                   "accept": "application/json",
                   "Content-Type": "application/json"}

    data = {"grant_type": os.environ["NP_GTYPE"],
            "client_id": os.environ["NP_CID"],
            "client_secret": os.environ["NP_SRT"]}

    url = os.environ["NP_URL"] + os.environ["NP_OAUTH2"] + "token"
    api_response = requests.post(url, headers=api_headers, data=json.dumps(data))
    if api_response.status_code == 200:
        credentials = json.loads(api_response.text)
        return credentials["accessToken"]
