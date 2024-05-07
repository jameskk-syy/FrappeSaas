# Copyright (c) 2024, James and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document

class Registration(Document):
    def validate(self):
        pass
        


@frappe.whitelist(allow_guest=True)
def register(data):
    datac = json.dumps(data)
    try:
    
        doc_dict = json.loads(datac)
        #saving data to the database
        registers = frappe.get_doc({
            "doctype":"Registration",
            "company_name":doc_dict.get('company'),
            "email_address":doc_dict.get('email'),
            "phone_number":doc_dict.get('phone'),
            "country":doc_dict.get('country'),
            "language":doc_dict.get('language'),
            "currency":doc_dict.get('currency'),
            "password":doc_dict.get('password')
        }).insert(ignore_permissions=True)
        
        frappe.db.commit()
        create_user_or_update(doc_dict)
        return {"status": 200, "message": "User registered successfully"}

    except Exception as e:
        frappe.log_error(f"Error registering user: {e}")
        return {"status": 500, "message": f"Failed to create User: {e}","data": doc_dict}
    
    
    
#method to create user
def create_user_or_update(doc):
    existing_user = frappe.get_all("User", filters={"email": doc.get('email')}, fields=["name"])
    
    if existing_user:
        # User exists, update the existing user
        user_doc = frappe.get_doc("User", existing_user[0].name)
        user_doc.update({
            "first_name": doc.get('company'),
            "last_name": doc.get('company'),
            "full_name": doc.get('company'),
            "enabled": 1,
        })
        user_doc.save()
    else:
        # User does not exist, create a new user
        new_user = frappe.get_doc({
            "doctype": "User",
            "email": doc.get('email'),
            "first_name": doc.get('company'),
            "last_name": doc.get('company'),
            "new_password": doc.get('password'),
            "enabled": 1,
        })
        new_user.append("roles", {
            "role": "",
        })
        new_user.insert(ignore_permissions=True)
    
    
    
    
    

@frappe.whitelist( allow_guest=True )
def login(usr,pwd):
    try:
        login_manager = frappe.auth.LoginManager()
        login_manager.authenticate(user=usr, pwd=pwd)
        login_manager.post_login()
    except frappe.exceptions.AuthenticationError:
        frappe.clear_messages()
        frappe.local.response["message"] = {
            "success_key":0,
            "message":"Authentication Error!"
        }

        return

    api_generate = generate_keys(frappe.session.user)
    user = frappe.get_doc('User', frappe.session.user)

    frappe.response["message"] = {
        "success_key":1,
        "message":"Authentication success",
        "sid":frappe.session.sid,
        "api_key":user.api_key,
        "api_secret":api_generate,
        "username":user.username,
        "email":user.email
    }


def generate_keys(user):
    user_details = frappe.get_doc('User', user)
    api_secret = frappe.generate_hash(length=15)

    if not user_details.api_key:
        api_key = frappe.generate_hash(length=15)
        user_details.api_key = api_key

    user_details.api_secret = api_secret
    user_details.save()

    return api_secret

    
