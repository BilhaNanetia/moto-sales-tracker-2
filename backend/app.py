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

        # Validate phone number format (simple check, you might want to use a more robust regex)
        if not phone_number.startswith('+254') or len(phone_number) != 13:
            return jsonify({
                'success': False,
                'error': 'Invalid phone number format. Use +254XXXXXXXXX'
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
        
        # If we don't get an error or a CheckoutRequestID, something unexpected happened
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