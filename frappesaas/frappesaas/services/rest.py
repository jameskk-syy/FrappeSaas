import requests
import uuid
import frappe
from passlib.hash import pbkdf2_sha256




class FLAGSMS:
    def __init__(self):
        self.access_token = None
    
    def get_access_token(self):
        url = "https://vas-api.flag42.com/api/login"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        data = {
            "email": "info@pesaswap.com",
            "password": "jODXtHruznlVlsx"
        }
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            response_data = response.json()
            self.access_token = response_data.get("access_token")
            return True
        else:
            return False
    
    def send_sms(self, mobile, message):
        if not self.access_token:
            success = self.get_access_token()
            if not success:
                return "Failed to obtain access token"
        
        url = "https://vas-api.flag42.com/api/send_sms/single"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        data = {
            "from": "PESASWAP",
            "msisdn": self.format_mobile_number(mobile),
            "message": message
        }
        
        response = requests.post(url, headers=headers, json=data)

        status_match = re.search(r'\[status\]\s*=>\s*(\w+)', response.content.decode())
        if status_match:
            status = status_match.group(1)

        self.insert_message_status(self.format_mobile_number(mobile), message, status)

        return response.text
    
    def insert_message_status(self, msisdn, message, status):

        external_uuid = str(uuid.uuid4())
        unique_id = external_uuid.replace("-", "")[:13]

        message_status = frappe.get_doc({
            "doctype": "Message Status",
            "unique_id": unique_id,
            "mobile_number": msisdn,
            "message": message,
            "status": status
        })

        message_status.insert(ignore_permissions=True)
    
    def format_mobile_number(self, mobile):
        mobile = mobile.replace(" ", "")
        filtered_mobile = mobile[-9:]
        mobile = "254" + filtered_mobile
        return mobile
    
    
flag_comm = FLAGSMS()


@frappe.whitelist(allow_guest=True)
def generate_keys(user):
    user_details = frappe.get_doc('User', user)
    api_secret = frappe.generate_hash(length=15)

    if not user_details.api_key:
        api_key = frappe.generate_hash(length=15)
        user_details.api_key = api_key

    user_details.api_secret = api_secret
    user_details.save()

    return api_secret


@frappe.whitelist(allow_guest=True)
def get_pesaswap_setting():
    pesaswap_setting = frappe.get_single("Pesaswap Setting")

    return pesaswap_setting

@frappe.whitelist(allow_guest=True)
def get_access_token():
    try:
        pesaswap_setting = get_pesaswap_setting()
        consumer_key = pesaswap_setting.consumer_key
        api_key = pesaswap_setting.api_key

        url = "https://devpesaswap-csharp.azurewebsites.net/api/tokenization"
        payload = {
            "ConsumerKey": consumer_key,
            "ApiKey": api_key
        }
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            return response.json().get("accessToken")
        else:
            frappe.log_error( frappe.get_traceback(), f'Failed to get access token. Status code: {response.status_code}')
            raise ValueError(f"Failed to get access token. Status code: {response.status_code}")
    except Exception as e:
        frappe.log_error( frappe.get_traceback(), f'An error occurred while getting access token: {str(e)}')
        raise ValueError(f"An error occurred while getting access token: {str(e)}")



@frappe.whitelist(allow_guest=True)
def send_c2b_collection_payment(customer, amount, mobile,billref, currency):
    try:
        access_token = get_access_token()

        if len(mobile) == 10 and mobile.startswith('0'):
            mobile = '254' + mobile[1:]

        external_uuid = str(uuid.uuid4())
        external_id = external_uuid.replace("-", "")[:13]

        pesaswap_setting = get_pesaswap_setting()
        paybill_description = pesaswap_setting.paybill_description

        payload = {
            "PaybillDescription": paybill_description,
            "Country": "KE",
            "Currency": currency,
            "Amount": int(round(float(amount))),
            "PhoneNumber": mobile,
            "TransactionExternalId": external_id,
            "Comment": billref,
            "Processor": "mpesa"
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        url = "https://devpesaswap-csharp.azurewebsites.net/api/collection-payment"
        response = requests.post(url, json=payload, headers=headers)


        if response.status_code == 200:
            create_transaction(external_id, amount, mobile, billref, customer)
            return response.json()  
        else:
            frappe.log_error( frappe.get_traceback(), f'Failed to create C2B collection payment. Status code: {response.status_code}')
            return {"error": f"Failed to create C2B collection payment. Status code: {response.status_code}"}

    except Exception as e:
        frappe.log_error( frappe.get_traceback(), f'{e}')
        return {"error": f"An error occurred: {str(e)}"}


@frappe.whitelist(allow_guest=True)
def create_c2b_billref_collection(customer, mobile, billref, amount):
    try:
        access_token = get_access_token()

        if len(mobile) == 10 and mobile.startswith('0'):
            mobile = '254' + mobile[1:]

        external_uuid = str(uuid.uuid4())
        external_id = external_uuid.replace("-", "")[:13]

        pesaswap_setting = get_pesaswap_setting()
        paybill_description = pesaswap_setting.paybill_description
        paybill = pesaswap_setting.paybill

        bill_number = billref.split('-')[-1]
        bill_number = str(int(bill_number))
        billref_formatted = "INV" + bill_number

        payload = {
            "PaybillDescription": paybill_description,
            "Amount": int(round(float(amount))),
            "CommandId": "CustomerPayBillOnline",
            "Msisdn": mobile,
            "ExternalId": external_id,
            "BillRefNumber": billref_formatted
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        url = "https://devpesaswap-csharp.azurewebsites.net/api/mpesa-c2b-billrefno"
        response = requests.post(url, json=payload, headers=headers)


        if response.status_code == 200:

            create_transaction(external_id, amount, mobile, billref, customer)

            flag_comm = FLAGSMS()

            message = f"Dear {customer},\pay your subscription {amount}.\nGo to MPESA Paybill\nBusiness No: {paybill}\nAccount No: {billref_formatted}\nAmount: {amount}"

            flag_comm.send_sms(mobile, message) 

            return response.json()
        else:
            frappe.log_error( frappe.get_traceback(), f'Failed to create C2B billref collection. Status code: {response.status_code}')
            return {"error": f"Failed to create C2B billref collection. Status code: {response.status_code}"}

    except Exception as e:
        frappe.log_error( frappe.get_traceback(), f'{e}')
        return {"error": f"An error occurred: {str(e)}"}


@frappe.whitelist(allow_guest=True)
def create_transaction(external_id, amount, mobile, billref, customer = None):
    try:
        pesaswap_transaction = frappe.get_doc({
            "doctype": 'Pesaswap Transaction',
            "transaction_external_id": external_id,
            "amount": amount,
            "status": 'Pending',
            "customer": customer,
            "phone": mobile,
            "bill_ref": billref
        })

        pesaswap_transaction.insert(ignore_permissions=True)

        return {"status": "success", "message": "Transaction data submitted successfully."}

    except Exception as e:
        frappe.log_error( frappe.get_traceback(), f'{e}')
        return {"status": "Error handling callback:", "message": str(e)}
    

@frappe.whitelist(allow_guest=True)
def get_price_per_module():
    pesaswap_setting = frappe.get_single("Pesaswap Settings")
    
    if pesaswap_setting:
        return pesaswap_setting.module_price
    
    return None  


@frappe.whitelist(allow_guest=True)
def get_modes_of_payment():
    try:
        mode_of_payments = frappe.db.get_all("Mode of Payment", filters={"name": ["in", ["Mpesa", "Airtel Money"]]}, fields=["mode_of_payment"])
        if mode_of_payments:
            print(f"\n\n\n\n{mode_of_payments}")
            return {
                "status": "success",
                "modes_of_payment": mode_of_payments
            }
        else:
            return {
                "status": "error",
                "message": "Mode of payment not found in Mode of Payment document"
            }
    except Exception as e:
        frappe.log_error(("Error in get_modes_of_payment: {0}").format(str(e)))
        return {
            "status": "error",
            "message": "An error occurred while fetching modes of payment"
        }



@frappe.whitelist(allow_guest=True)
def create_customer_and_user(company_name,email_address, mobile_number, territory, password):

        try:
         
            existing_territory = frappe.get_all("Territory", filters={"territory_name": territory})
            if not existing_territory:
                territory_doc = frappe.get_doc({
                    "doctype": "Territory",
                    "territory_name": territory
                })
                territory_doc.insert(ignore_permissions=True)

            customer = frappe.get_doc({
                "doctype": "Customer",
                "customer_name": company_name,
                "customer_type": "Individual",
                "customer_group": "Individual",
                "territory": territory,
                "mobile_no":mobile_number,
                "default_price_list": "Standard Selling"
            })

            customer.insert(ignore_permissions=True)

            user_name = None
            user = frappe.get_doc({
                "doctype": "User",
                "first_name": company_name,
                "email": email_address,
                "phone": mobile_number,
                "mobile_no": mobile_number,
                "send_welcome_email": 0
            })
            user.insert(ignore_permissions=True)
            user_name = user.name

            encrypted_password = pbkdf2_sha256.hash(password)
        
            insert_query = f"""
                INSERT INTO
                    __Auth (doctype, name, fieldname, password)
                VALUES
                    ('User', '{user_name}', 'Password', '{encrypted_password}')
            """
            
            frappe.db.sql(insert_query)

            contact = frappe.get_doc({
                "doctype": "Contact",
                "first_name": company_name,
                "email_id": email_address,
                "mobile_no": mobile_number,
                "is_primary_contact": 1,
                "is_billing_contact": 1,
                "user": user_name
            })

            contact.append("phone_nos", {
                "phone": mobile_number,
                "is_primary_mobile_no": 1
            })

            contact.append("email_ids", {
                "email_id" : email_address,
                "is_primary": 1
            })

            contact.append("links", {
                "link_doctype" : "Customer",
                "link_name": customer.name
            })

            contact.insert(ignore_permissions=True)

            frappe.db.set_value("Customer", customer.name, "customer_primary_contact", contact.name)
            frappe.db.set_value("Customer", customer.name, "mobile_no", mobile_number)
            frappe.db.set_value("Customer", customer.name, "email_id", email_address)

            return {"status": "success", "message": "Customer created successfully."}

        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Error creating new Customer: {}".format(str(e)))
            return {"status": "error", "message": str(e)}