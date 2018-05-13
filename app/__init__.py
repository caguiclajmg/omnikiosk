import flask
import random
import os
import string
import requests
import json
import base64

with open('token-convertapi.txt', 'r') as f:
    token_convertapi = f.read()

app = flask.Flask('omnikiosk-backend')

def parse_pagestring(string):
    tokens = string.split(',')

    pages = 0
    for token in tokens:
        if '-' not in token:
            pages += 1
        else:
            p = token.split('-')
            pages += int(p[1]) - int(p[0]) + 1

    return pages

def generate_id(length):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

@app.route('/')
@app.route('/index')
def index():
    return flask.render_template('index.html')

@app.route('/help')
def help():
    return flask.render_template('help.html')

@app.route('/about')
def about():
    return flask.render_template('about.html')

@app.route('/upload', methods = ['POST'])
def upload():
    i = generate_id(4)

    while(os.path.exists(i)):
        i = generate_id(4)

    os.makedirs(i)
    f = flask.request.files['document']
    f.save(i + '/' + 'document.docx')

    resp = flask.make_response(flask.redirect(flask.url_for('props'), code = 302))
    resp.set_cookie('transaction_id', i)
    return resp

@app.route('/props', methods = ['GET', 'POST'])
def props():
    transaction_id = flask.request.cookies['transaction_id']

    if flask.request.method == 'GET':
        response = requests.post('https://v2.convertapi.com/docx/to/jpg?Secret={}'.format(token_convertapi), files = {'File' : open(str(transaction_id) + '/document.docx', 'rb')})
        data = json.loads(response.text)
        files = data['Files']

        response = flask.make_response(flask.render_template('props.html', images=files))
        response.set_cookie('pages', str(len(files)))

        return response
    elif flask.request.method == 'POST':
        if os.path.exists('props.cfg'): os.remove('props.cfg')

        props_color = flask.request.form['props_color']
        props_pages = flask.request.form['props_pages']
        props_copies = int(flask.request.form['props_copies'])

        if props_pages == '':
            count_page = int(flask.request.cookies['pages'])
        else:
            count_page = parse_pagestring(props_pages)

        with open(str(transaction_id) + '/props.cfg', 'w+') as f:
            f.write("True" if props_color == 'color' else "False")
            f.write('\n')
            f.write(props_pages)
            f.write('\n')
            f.write(str(props_copies))
            f.write('\n')

            price_page = 2 if props_color == 'color' else 1
            price_total = (price_page * count_page) * props_copies

            f.write(str(price_total))
            f.write('\n')
            f.write(str(count_page))
            f.write('\n')

        redirect = flask.redirect(flask.url_for('payment'), code=302)
        response = flask.make_response(redirect)
        response.set_cookie('amount', str(price_total))

        return response

@app.route('/payment', methods = ['GET', 'POST'])
def payment():
    if flask.request.method == 'GET':
        return flask.render_template('payment.html', amount=flask.request.cookies['amount'])
    elif flask.request.method == 'POST':
        payment_method = flask.request.form['payment_method']
        return flask.redirect(flask.url_for(payment_method), code = 302)

@app.route('/cash')
def cash():
    transaction_id = flask.request.cookies.get('transaction_id')
    return flask.redirect(flask.url_for('success', transaction_id = transaction_id), code = 302)

@app.route('/globe_prepaid', methods = ['GET', 'POST'])
def globe_prepaid():
    if flask.request.method == 'GET':
        return flask.render_template('globe_prepaid.html')
    elif flask.request.method == 'POST':
        with open('user_token.txt') as f:
            tokens = json.load(f)

        subscriber_number = flask.request.form['subscriber_number']
        if subscriber_number in tokens:
            access_token = tokens[subscriber_number]
            d = {
                'amount' : '1.00',
                'description' : 'OmniKiosk printing service',
                'endUserId' : 'tel:+63' + subscriber_number,
                'referenceCode' : '1194' + ''.join(random.choices(string.digits, k=7)),
                'transactionOperationStatus' : 'Charged'
            }

            r = requests.post('https://devapi.globelabs.com.ph/payment/v1/transactions/amount?access_token=' + access_token, data = d)

            # TODO: verify if payment was successful

            transaction_id = flask.request.cookies.get('transaction_id')
            return flask.redirect(flask.url_for('success', transaction_id = transaction_id), code = 302)

@app.route('/success')
def success():
    transaction_id = flask.request.cookies.get('transaction_id')
    return flask.render_template('success.html', transaction_id = transaction_id)

@app.route('/oauth', methods=['GET', 'POST'])
def oauth():
    if flask.request.method == 'GET':
        access_token = flask.request.args['access_token']
        subscriber_number = flask.request.args['subscriber_number']

        users = {}
        if os.path.exists('user_token.txt'):
            with open('user_token.txt', 'r+') as f:
                users = json.load(f)

        users[subscriber_number] = access_token

        with open('user_token.txt', 'w+') as f:
            json.dump(users, f)
    elif flask.request.method == 'POST':
        pass

    return ""

@app.route('/db')
def db():
    f = open('user_token.txt')
    d = json.load(f)
    return str(d)

@app.route('/backend/retrieve/document')
def backend_retrieve():
    transaction_id = flask.request.args.get('transaction_id')
    return flask.send_from_directory(str(transaction_id), 'document.docx', as_attachment=True)

@app.route('/backend/retrieve/props')
def backend_retrieve_settings():
    transaction_id = flask.request.args.get('transaction_id')
    return flask.send_from_directory(str(transaction_id), 'props.cfg', as_attachment=True)

@app.route('/backend/retrieve/price')
def price():
    transaction_id = flask.request.args.get('transaction_id')

    with open(str(transaction_id) + '/props.cfg', 'r+') as f:
        f.readline()
        f.readline()
        f.readline()

        return f.readline()

    return "0"