import os

from bson import ObjectId

from tools import get_user_document_type, random_with_n_digits, get_account_from_pool, np_api_request


def user_origination(user, db):
    data = {"card-number": "000712", "exp-date": "0320", "document-type": "CC", "document-number": "16084701",
            "name-1": " ", "name-2": " ", "last-name-1": "", "last-name-2": " ",
            "birth-date": "01/06/1982", "birth-place": " ", "nationality": "THEWORLD", "sex": "M",
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
    data["birth-place"] = user["location"]["Address"]["Country"]
    data["phone-1"] = user["cellphone"]
    data["address-2"] = user["location"]["Address"]["Label"]

    api_headers = {"x-country": "Usd",
                   "language": "es",
                   "channel": "API",
                   "accept": "application/json",
                   "Content-Type": "application/json",
                   "Authorization": "Bearer $OAUTH2TOKEN$"}

    api_headers["Authorization"] = api_headers["Authorization"].replace("$OAUTH2TOKEN$", os.environ["NP_OAUTH2_TOKEN"])

    url = os.environ["NP_URL"] + os.environ["CEOAPI"] + os.environ["CEOAPI_VER"] \
          + account["indx"] + "/employee?trxid=" + str(random_with_n_digits(10))

    api_response = np_api_request(url=url, data=data, api_headers=api_headers)
    if api_response.status_code == 200:
        db.accountPool.update({"_id": ObjectId(account["_id"])},
                              {"$set": {"codMisc": "AF"}})
        db.users.update({"id": user["id"]},
                        {'$set': {"accountId": account["_id"]}})
        return "OK", 200, account
    else:
        return api_response.text, api_response.status_code