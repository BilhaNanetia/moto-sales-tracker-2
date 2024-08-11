from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from requests.auth import HTTPBasicAuth
import sqlite3
import datetime
import os
import requests
import base64
import logging
import uuid

# Set up Flask app
template_dir = os.path.abspath('../frontend/templates')
static_dir = os.path.abspath('../frontend/static')

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
app.config['SECRET_KEY'] = 'your_secret_key_here'  # Change this to a random secret key

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# Set up Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

MPESA_ENVIRONMENT = 'sandbox'  # Change to 'production' when moving to production
CONSUMER_KEY = 'OAa4XdMA4ONufa3eyk7PLpKD7KH9oTfSWNewuMDA0ZCaj1YZ'
CONSUMER_SECRET = '4AqHGRBEIbVASnObx1B3xOvW64xV6rnOw7uAjNQ6eFDzTUIdahpHgBetJpbhYogL'
SHORTCODE = '174379'
LIPA_NA_MPESA_PASSKEY = 'bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919'

AIRTEL_CLIENT_ID='a7189115-9ead-47d8-9904-bc419b949983'
AIRTEL_CLIENT_SECRET='****************************'


def get_mpesa_access_token():
    url = f'https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
    if MPESA_ENVIRONMENT == 'sandbox':
        url = f'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
    response = requests.get(url, auth=HTTPBasicAuth(CONSUMER_KEY, CONSUMER_SECRET))
    return response.json()['access_token']

def lipa_na_mpesa_online(phone_number, amount):
    access_token = get_mpesa_access_token()
    api_url = f'https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
    if MPESA_ENVIRONMENT == 'sandbox':
        api_url = f'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest'

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    password = base64.b64encode(f'{SHORTCODE}{LIPA_NA_MPESA_PASSKEY}{timestamp}'.encode()).decode('utf-8')

    payload = {
        'BusinessShortCode': SHORTCODE,
        'Password': password,
        'Timestamp': timestamp,
        'TransactionType': 'CustomerPayBillOnline',
        'Amount': amount,
        'PartyA': phone_number,
        'PartyB': SHORTCODE,
        'PhoneNumber': phone_number,
        'CallBackURL': 'https://mydomain.com/path',
        'AccountReference': 'BeeMoto Sales',
        'TransactionDesc': 'Payment for motorbike spares'
    }

    logger.debug(f"Sending request to M-Pesa API: {api_url}")
    logger.debug(f"Headers: {headers}")
    logger.debug(f"Payload: {payload}")

    response = requests.post(api_url, json=payload, headers=headers)

    logger.debug(f"M-Pesa API response status code: {response.status_code}")
    logger.debug(f"M-Pesa API response content: {response.text}")

    return response.json()

def get_airtel_money_access_token():
    url = "https://openapi.airtel.africa/auth/oauth2/token"
    auth_data = {
        'client_id': AIRTEL_CLIENT_ID,
        'client_secret': AIRTEL_CLIENT_SECRET,
        'grant_type': 'client_credentials'
    }

    app.logger.debug(f"Requesting Airtel Money access token from: {url}")
    app.logger.debug(f"Auth data: {auth_data}")

    try:
        response = requests.post(url, data=auth_data)
        response.raise_for_status()  # This will raise an exception for HTTP errors
        
        app.logger.debug(f"Airtel Money token response: {response.text}")
        
        token = response.json().get('access_token')
        if not token:
            app.logger.error("No access token in Airtel Money response")
            return None
        return token
    except requests.RequestException as e:
        app.logger.error(f"Error getting Airtel Money access token: {str(e)}")
        return None

def initiate_airtel_money_payment(phone_number, amount):
    try:
        app.logger.info("Getting Airtel Money access token")
        access_token = get_airtel_money_access_token()
        if not access_token:
            raise ValueError("Failed to obtain Airtel Money access token")

        api_url = 'https://openapi.airtel.africa/merchant/v1/payments/'
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'amount': amount, 
            'phone_number': phone_number,
            'currency': 'KES',
            'transaction_reference': str(uuid.uuid4()),
            'transaction_description': 'Payment for motorbike spares'
        }

        app.logger.debug(f"Sending request to Airtel Money API: {api_url}")
        app.logger.debug(f"Headers: {headers}")
        app.logger.debug(f"Payload: {payload}")

        response = requests.post(api_url, json=payload, headers=headers)
        app.logger.debug(f"Airtel Money API response status code: {response.status_code}")
        app.logger.debug(f"Airtel Money API response content: {response.text}")

        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        app.logger.error(f"Airtel Money API request failed: {str(e)}", exc_info=True)
        raise
    except ValueError as e:
        app.logger.error(f"Airtel Money payment initiation error: {str(e)}", exc_info=True)
        raise
    except Exception as e:
        app.logger.error(f"Unexpected error in Airtel Money payment initiation: {str(e)}", exc_info=True)
        raise

class User(UserMixin):
    def __init__(self, id, username, email, password):
        self.id = id
        self.username = username
        self.email = email
        self.password = password

def get_db_connection():
    db_path = os.path.abspath('../sales_record.db')  
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if user:
        return User(user['id'], user['username'], user['email'], user['password'])
    return None

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? OR email = ?', (username, email)).fetchone()
        if user:
            flash('Username or email already exists')
            return redirect(url_for('signup'))
        hashed_password = generate_password_hash(password)
        conn.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)', (username, email, hashed_password))
        conn.commit()
        conn.close()
        flash('Account created successfully')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            user_obj = User(user['id'], user['username'], user['email'], user['password'])
            login_user(user_obj)
            return redirect(url_for('index'))
        flash('Invalid username or password')
    return render_template('login.html')

class SalesRecord:
    def __init__(self, db_name=os.path.abspath('../sales_record.db')):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()

    def add_sale(self, item, quantity, price):
        date = datetime.date.today().isoformat()
        self.cursor.execute('''
            INSERT INTO sales (date, item, quantity, price)
            VALUES (?, ?, ?, ?)
        ''', (date, item, quantity, price))
        self.conn.commit()

    def get_daily_total(self, date):
        self.cursor.execute('''
            SELECT SUM(quantity * price)
            FROM sales
            WHERE date = ?
        ''', (date,))
        result = self.cursor.fetchone()[0]
        return result if result else 0

    def get_daily_sales(self, date):
        self.cursor.execute('''
            SELECT id, item, quantity, price
            FROM sales
            WHERE date = ?
        ''', (date,))
        return self.cursor.fetchall()
    
    def delete_sale(self, sale_id):
        self.cursor.execute('''
            DELETE FROM sales
            WHERE id = ?
        ''', (sale_id,))
        self.conn.commit()
        return self.cursor.rowcount > 0  # Returns True if a row was deleted, False otherwise

    def get_monthly_total(self, year, month):
        start_date = f"{year}-{month:02d}-01"
        end_date = f"{year}-{month:02d}-31"  # This works for all months
        self.cursor.execute('''
            SELECT SUM(quantity * price)
            FROM sales
            WHERE date BETWEEN ? AND ?
        ''', (start_date, end_date))
        result = self.cursor.fetchone()[0]
        return result if result else 0

    def get_yearly_total(self, year):
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"
        self.cursor.execute('''
            SELECT SUM(quantity * price)
            FROM sales
            WHERE date BETWEEN ? AND ?
        ''', (start_date, end_date))
        result = self.cursor.fetchone()[0]
        return result if result else 0

record = SalesRecord()

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/add_sale', methods=['POST'])
def add_sale():
    data = request.json
    record.add_sale(data['item'], data['quantity'], data['price'])
    return jsonify({'success': True})

@app.route('/initiate_payment', methods=['POST'])
def initiate_payment():
    try:
        data = request.json
        phone_number = data.get('phone_number')
        amount = data.get('amount')

        # Validate input
        if not phone_number or not amount:
            return jsonify({
                'success': False,
                'error': 'Phone number and amount are required'
            }), 400

        # Validate phone number format 
        if not (phone_number.startswith('254') or len(phone_number) == 12):
            return jsonify({
                'success': False,
                'error': 'Invalid phone number format. Use 254XXXXXXXXX'
            }), 400

        # Validate amount (assuming amount should be positive)
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Invalid amount. Must be a positive number'
            }), 400

        # Initiate M-Pesa payment
        response = lipa_na_mpesa_online(phone_number, amount)

        # Check if the response is valid and contains the expected fields
        if not isinstance(response, dict):
            raise ValueError("Invalid response from M-Pesa API")

        
        if 'errorCode' in response:
            return jsonify({
                'success': False,
                'error': f"M-Pesa API error: {response.get('errorMessage', 'Unknown error')}",
                'errorCode': response.get('errorCode')
            }), 400

        # If successful, the response should contain a CheckoutRequestID
        if 'CheckoutRequestID' in response:
            return jsonify({
                'success': True,
                'message': 'Payment initiated successfully',
                'checkoutRequestId': response['CheckoutRequestID']
            }), 200
        
        # If we don't get an error or a CheckoutRequestID
        raise ValueError("Unexpected response from M-Pesa API")
  
    except ValueError as e:
        app.logger.error(f"Value error in initiate_payment: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except requests.RequestException as e:
        # Handle any network-related errors
        app.logger.error(f"Network error in initiate_payment: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Network error occurred: {str(e)}'
        }), 500
    except Exception as e:
        # Catch any other unexpected errors
        app.logger.error(f'Unexpected error in initiate_payment: {str(e)}')
        return jsonify({
            'success': False,
            'error': 'An unexpected error occurred'
        }), 500
    
@app.route('/initiate_airtel_payment', methods=['POST'])
def initiate_airtel_payment():
    try:
        app.logger.info("Initiating Airtel Money payment")
        data = request.json
        app.logger.debug(f"Received data: {data}")

        phone_number = data.get('phone_number')
        amount = data.get('amount')

        app.logger.info(f"Phone number: {phone_number}, Amount: {amount}")

        if not phone_number or not amount:
            app.logger.warning("Missing phone number or amount")
            return jsonify({
                'success': False,
                'error': 'Phone number and amount are required'
            }), 400

        if not (phone_number.startswith('254') and len(phone_number) == 12):
            app.logger.warning(f"Invalid phone number format: {phone_number}")
            return jsonify({
                'success': False,
                'error': 'Invalid phone number format. Use 254XXXXXXXXX'
            }), 400

        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except ValueError:
            app.logger.warning(f"Invalid amount: {amount}")
            return jsonify({
                'success': False,
                'error': 'Invalid amount. Must be a positive number'
            }), 400

        app.logger.info("Calling initiate_airtel_money_payment function")
        response = initiate_airtel_money_payment(phone_number, amount)
        app.logger.debug(f"Airtel Money API response: {response}")

        if 'error' in response:
            app.logger.error(f"Airtel Money API error: {response.get('error')}")
            return jsonify({
                'success': False,
                'error': f"Airtel Money API error: {response.get('error', 'Unknown error')}",
                'errorCode': response.get('errorCode')
            }), 400

        if 'transaction_id' in response:
            app.logger.info(f"Payment initiated successfully. Transaction ID: {response['transaction_id']}")
            return jsonify({
                'success': True,
                'message': 'Payment initiated successfully',
                'transaction_id': response['transaction_id']
            }), 200

        app.logger.warning("Unexpected response from Airtel Money API")
        return jsonify({
            'success': False,
            'error': 'Unexpected response from Airtel Money API'
        }), 500

    except requests.exceptions.RequestException as e:
        app.logger.error(f"Network error in initiate_airtel_payment: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Network error occurred: {str(e)}'
        }), 500
    except Exception as e:
        app.logger.error(f'Unexpected error in initiate_airtel_payment: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'error': 'An unexpected error occurred'
        }), 500
    

@app.route('/get_daily_total', methods=['GET'])
def get_daily_total():
    date = request.args.get('date')
    total = record.get_daily_total(date)
    return jsonify({'total': total})

@app.route('/get_daily_sales', methods=['GET'])
def get_daily_sales():
    date = request.args.get('date')
    sales = record.get_daily_sales(date)
    return jsonify({'sales': [{'id': sale[0], 'item': sale[1], 'quantity': sale[2], 'price': sale[3]} for sale in sales]})

@app.route('/delete_sale', methods=['POST'])
@login_required
def delete_sale():
    data = request.json
    sale_id = data.get('id')
    if sale_id is None:
        return jsonify({'success': False, 'error': 'No sale ID provided'}), 400
    
    success = record.delete_sale(sale_id)
    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Sale not found'}), 404

@app.route('/get_monthly_total', methods=['GET'])
def get_monthly_total():
    year = int(request.args.get('year'))
    month = int(request.args.get('month'))
    total = record.get_monthly_total(year, month)
    return jsonify({'total': total})

@app.route('/get_yearly_total', methods=['GET'])
def get_yearly_total():
    year = int(request.args.get('year'))
    total = record.get_yearly_total(year)
    return jsonify({'total': total})

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)