import json
from requests import get, post

from factory import db
from shop_module.models import Dispatcher, Order, Store

def confirm_payment(trans_id, currency, value, flw_sec_key):
    print('Started confirm_payment')
    '''
    Note: Flutterwave only checks if the given payment exists.
    It does not tell me if it has been formerly used previously
    used on this platform.
    Thus, calling functions have to check its usability.
    '''
    flw_resp = get(
        'https://api.flutterwave.com/v3/transactions/' + str(
            trans_id) + '/verify',
        headers={"Content-Type": "application/json",
                 'Authorization': 'Bearer ' + flw_sec_key}
    ).json()
    if flw_resp['data']['status'] == 'successful':
      # confirm currency and amount
        if flw_resp['data']['currency'] == currency:
            if flw_resp['data']['amount'] >= float(value):
                print('True confirm_payment')
                return flw_resp['data']['txref']
    print('False confirm_payment')
    return False


def confirm_store_reg(trans_id, store_reg_amt, flw_sec_key):
    value, currency = store_reg_amt.split(' ')
    tx_ref = confirm_payment(trans_id, currency, value, flw_sec_key)
    if tx_ref:
        # Check if the txref is still usable
        # Recall, txref = store/user_id/number_of_stores.
        # Confirm that the current user matches the reference id
        _, user_id, store_num = tx_ref.split('/')
        if int(user_id) == current_user.id:
            # confirm is number of stores is valid
            if int(store_num) == len(current_user.stores):
                # Now, it's too good not to be true
                # Proceed with dummy store creation
                # We want to randomly fix a store to a dispatcher
                dispatcher = db.session.query(
                    Dispatcher).order_by(db.func.random()).first().id
                store = Store(
                    name=trans_id,
                    about='Give your store a short Description',
                    iso_code='USD',
                    dispatcher_id=dispatcher,
                    user_id=current_user.id,
                )
                db.session.add(store)
                db.session.commit()
                # Note: trans_id has been used to create a store
                return trans_id
    return False


def confirm_sales_payment(trans_id, flw_sec_key):
    # get the order data for comparism and verification
    order = Order.cart().filter_by(user_id=current_user.id).first()
    tx_ref = confirm_payment(trans_id, order.iso_code, order.amount,
                             flw_sec_key)
    if tx_ref:
        # Recall, txref = order/user_id/order_id.
        # Here user_id is no longer needed as order_id is sufficient
        if int(tx_ref.split('/')[2]) == order.id:
            # Now, it's too good not to be true
            # We can now certify the order
            order.status = 'done'
            order.paid = True
            db.session.commit()
            return True
    return False


def subaccount(partner_data, mode='update', type=None):
    url = "https://api.flutterwave.com/v3/subaccounts"

    headers = {
        'Authorization': 'Bearer FLWSECK_TEST-SANDBOXDEMOKEY-X',
        'Content-Type': 'application/json'
    }
    payload = {
        'account_bank': '044',
        'account_number': '0690000037',
        'business_name': 'aSDF gdfdf',
        'country': 'NG',
        'split_value': '0.85',
        'business_mobile': '090890382',
        'business_email': 'fsgfgf@ffdgd.com'
    }
    response = post(url, headers=headers, data=json.dumps(payload),)
    print(response.json())
