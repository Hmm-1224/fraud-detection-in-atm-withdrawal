from flask import Flask, request, render_template, redirect, url_for, jsonify, session
from customer_database import db, Customer, Transaction
import random
import os
import re
from sqlalchemy.exc import IntegrityError
from twilio.rest import Client
from dotenv import load_dotenv
import cv2
import numpy as np
from deepface import DeepFace
import base64

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = '888efe30bc802bd88d98eb3990828e2a'  # Change this in production!
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///banking_app.db'
db.init_app(app)

with app.app_context():
    db.create_all()

TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_customer_id_by_name', methods=['GET'])
def get_customer_id_by_name():
    name = request.args.get('name')

    if not name:
        return jsonify({"error": "Name parameter is required."}), 400

    customer = Customer.query.filter_by(name=name).first()

    if customer:
        return jsonify({"customer_id": customer.customer_id}), 200
    else:
        return jsonify({"error": "Customer not found."}), 404

@app.route('/get_phone_number_by_name', methods=['GET'])
def get_phone_number_by_name():
    name = request.args.get('name')

    if not name:
        return jsonify({"error": "Name parameter is required."}), 400

    customer = Customer.query.filter_by(name=name).first()

    if customer:
        return jsonify({"phone_number": customer.phone}), 200
    else:
        return jsonify({"error": "Customer not found."}), 404

@app.route('/get_customer_details_by_phone', methods=['GET'])
def get_customer_details_by_phone():
    phone = request.args.get('phone')

    if not phone:
        return jsonify({"error": "Phone number parameter is required."}), 400

    customer = Customer.query.filter_by(phone=phone).first()

    if customer:
        return jsonify({
            "name": customer.name,
            "customer_id": customer.customer_id
        }), 200
    else:
        return jsonify({"error": "Customer not found."}), 404

# Add a new customer
@app.route('/add_customer', methods=['POST'])
def add_customer():
    name = request.form['name']
    phone = request.form['phone']
    total_amount = float(request.form['total_amount'])
    min_limit = float(request.form['min_limit'])
    face_data = request.form.get('face_data')

    if not is_valid_phone(phone):
        return jsonify({"error": "Phone number must include valid country code!"}), 400

    customer_id = generate_unique_customer_id()

    if Customer.query.filter_by(phone=phone).first():
        return jsonify({"error": "Phone number already exists!"}), 400

    try:
        new_customer = Customer(name=name, customer_id=customer_id, phone=phone,
                                face_data=face_data, total_amount=total_amount, min_limit=min_limit)
        db.session.add(new_customer)
        db.session.commit()
        return jsonify({"message": "Customer added successfully!", "customer_id": customer_id}), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Failed to add customer due to integrity error!"}), 500

def generate_unique_customer_id():
    while True:
        customer_id = str(random.randint(10000000000000, 99999999999999))
        if not Customer.query.filter_by(customer_id=customer_id).first():
            return customer_id

def is_valid_phone(phone):
    # Add your phone number validation logic here (e.g., regex for country code)
    pattern = re.compile(r'^\+\d{1,3}\d{1,14}$')  # Example pattern
    return pattern.match(phone) is not None

# Request OTP for updating mobile number
@app.route('/request_update_otp', methods=['POST'])
def request_update_otp():
    customer_id = request.form['customer_id']
    customer = Customer.query.filter_by(customer_id=customer_id).first()

    if not customer:
        return jsonify({"error": "Customer not found"}), 404

    otp = random.randint(100000, 999999)

    try:
        twilio_client.messages.create(
            body=f"Your OTP for updating your mobile number is {otp}",
            from_=TWILIO_PHONE_NUMBER,
            to=customer.phone
        )
        session['update_otp'] = otp
        session['update_customer_id'] = customer_id
        return jsonify({"message": "OTP sent to the registered mobile number."}), 200

    except Exception as e:
        print(f"Error sending OTP: {e}")
        return jsonify({"error": "Failed to send OTP. Please try again."}), 500

@app.route('/update_mobile', methods=['POST'])
def update_mobile():
    new_mobile = request.form.get('new_mobile')
    otp_input = request.form.get('otp')

    if not new_mobile or not otp_input:
        return jsonify({"error": "Missing new_mobile or otp"}), 400

    try:
        otp_input = int(otp_input)
    except ValueError:
        return jsonify({"error": "Invalid OTP format!"}), 400

    # Check if the OTP matches
    if str(otp_input) == str(session.get('update_otp')):
        customer_id = session.get('update_customer_id')
        if not customer_id:
            return jsonify({"error": "Customer ID is missing!"}), 400

        customer = Customer.query.filter_by(customer_id=customer_id).first()

        if customer:
            # Update the phone number and allow reuse of the old number
            old_phone = customer.phone
            customer.phone = new_mobile
            db.session.commit()

            # Clear session data
            session.pop('update_otp', None)
            session.pop('update_customer_id', None)

            # Allow another user to take the old phone number
            if old_phone:
                # Optionally, here you could log the change or notify the previous owner, etc.
                pass

            return jsonify({"message": "Mobile number updated successfully!"}), 200

        return jsonify({"error": "Customer not found!"}), 404  # Customer not found case

    return jsonify({"error": "Invalid OTP!"}), 400  # Invalid OTP case

# Request OTP for withdrawal
@app.route('/request_otp_withdraw/<customer_id>', methods=['GET'])
def request_otp_withdraw(customer_id):
    customer = Customer.query.filter_by(customer_id=customer_id).first()

    if not customer:
        return jsonify({"error": "Customer not found"}), 404

    otp = random.randint(100000, 999999)

    try:
        twilio_client.messages.create(
            body=f"Your OTP for withdrawal is {otp}",
            from_=TWILIO_PHONE_NUMBER,
            to=customer.phone
        )
        session['withdraw_otp'] = otp
        session['withdraw_customer_id'] = customer_id
        return jsonify({"message": "OTP sent to the registered mobile number."}), 200

    except Exception as e:
        print(f"Error sending OTP: {e}")
        return jsonify({"error": "Failed to send OTP. Please try again."}), 500

@app.route('/verify_otp_withdraw', methods=['POST'])
def verify_otp_withdraw():
    data = request.get_json()
    otp_input = data.get('otp')
    customer_id = data.get('customer_id')

    if str(otp_input) == str(session.get('withdraw_otp')):
        # After OTP verification, initiate face recognition
        return jsonify({"verified": True}), 200

    return jsonify({"verified": False}), 400

@app.route('/verify_face', methods=['POST'])
def verify_face():
    data = request.get_json()
    image_base64 = data.get('image')

    # Decode the base64 image
    img_data = base64.b64decode(image_base64.split(',')[1])
    np_arr = np.frombuffer(img_data, np.uint8)
    captured_image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    # Load the stored image of the customer
    customer_id = session.get('withdraw_customer_id')
    customer = Customer.query.filter_by(customer_id=customer_id).first()

    if not customer or not customer.face_data:
        return jsonify({"success": False, "message": "Customer not found or face data not available."}), 404

    # Assuming face_data is stored as a file path or Base64
    customer_image_data = base64.b64decode(customer.face_data)
    customer_image = cv2.imdecode(np.frombuffer(customer_image_data, np.uint8), cv2.IMREAD_COLOR)

    try:
        # Use DeepFace to compare the two images
        result = DeepFace.verify(captured_image, customer_image)

        if result["verified"]:
            # Proceed with withdrawal logic
            return jsonify({"success": True, "message": "Face recognition successful! Withdrawal processed."}), 200
        else:
            return jsonify({"success": False, "message": "Face recognition failed!"}), 403

    except Exception as e:
        print(f"Face verification error: {e}")
        return jsonify({"success": False, "message": "Face verification error."}), 500

@app.route('/withdraw', methods=['POST'])
def withdraw():
    data = request.get_json()
    amount = data.get('amount')
    customer_id = data.get('customer_id')

    customer = Customer.query.filter_by(customer_id=customer_id).first()

    if not customer:
        return jsonify({"error": "Customer not found."}), 404

    if amount > customer.total_amount:
        return jsonify({"error": "Insufficient balance."}), 400

    customer.total_amount -= amount

    new_transaction = Transaction(customer_id=customer.customer_id, amount=amount)
    db.session.add(new_transaction)

    try:
        db.session.commit()
        return jsonify({"message": "Withdrawal successful!"}), 200
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Failed to record transaction!"}), 500

if __name__ == '__main__':
    app.run(debug=True)

