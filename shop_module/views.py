''' Defination of all shop views in `shop` blueprint '''
from requests import get

from flask import Blueprint, current_app, flash, make_response, \
    redirect, render_template, request, Response, url_for
from flask_login import current_user, login_required

from factory import db
from .models import AccountDetail, Currency, Dispatcher, \
    Order, OrderLine, Product, Store
from . import utilities
from users_module.forms import ExtendedRegisterForm
from.forms import StoreRegisterForm

# ---------- Declaring the blueprint ----------
shop = Blueprint('shop', __name__, template_folder='templates')


@shop.before_request
def before_request():
    ''' Make sure that the currency is always known '''
    if not(request.cookies.get('iso_code')):
        response = make_response(redirect(request.path))
        code = get('https://ipapi.co/currency/').text
        if not((code,) in Currency.query.with_entities(Currency.code).all()):
            code = 'USD'
        response.set_cookie('iso_code', code, samesite='None')
        return response


@shop.route('/')
def index():
    return render_template('home.html')


@shop.route('/callback/store_payment', methods=['POST'])
def callback_store_payment():
    flw_data = request.json
    print(flw_data)
    store_name = utilities.confirm_store_reg(
        flw_data['transaction_id'],
        current_app.config['STORE_REG_AMT'],
        current_app.config['FLW_SEC_KEY'])
    if store_name:
        flash("Payment confirmed, thank you", 'success')
        return {'redirect': url_for('.store_edit', store_name=store_name)}
    flash("Unable to confirm payment, contact us", 'danger')
    return {'redirect': url_for('.dashboard')}


@shop.route('/callback/sales_payment', methods=['POST'])
def callback_sales_payment():
    flw_data = request.json
    print(flw_data)
    if utilities.confirm_sales_payment(
            flw_data['transaction_id'], flw_data['tx_ref'],
            flw_data['currency'], flw_data['amount'],
            current_app.config['FLW_SEC_KEY']):
        flash("Payment confirmed, thank you", 'success')
    else:
        flash("Unable to confirm payment, contact us", 'danger')
    return {'redirect': url_for('.market')}


@shop.route('/cart', methods=['GET'])
@login_required
def cart():
    iso_code = request.cookies.get('iso_code')
    prod_str = request.args.get('prod_id')
    # Check if the current user has an hanging cart
    cart = Order.cart().filter_by(user_id=current_user.id).first()
    if prod_str:
        # ---- The user is adding a product to cart ------
        prod_id = int(prod_str)
        # Get the selected product detail
        cart_line = Product.public().filter_by(id=prod_id).first()
        if cart:
            # Check if this product already exist in the cart
            prev_prod_line = db.session.query(OrderLine).filter_by(
                order_id=cart.id, product_id=prod_id).first()
            if prev_prod_line:
                # Add one to the quantity of this product
                prev_prod_line.qty += 1
            else:
                # Include this product in the previous cart
                db.session.add(OrderLine(order_id=cart.id,
                                         product_id=cart_line.id,
                                         price=cart_line.price,))
        else:
            # Take the product with price tag and add it to an new cart
            cart_line = OrderLine(product_id=cart_line.id,
                                  price=cart_line.price,)
            cart = Order(user_id=current_user.id, iso_code=iso_code,
                         orderlines=[cart_line])
            db.session.add(cart_line)
            db.session.add(cart)
        db.session.commit()
        return redirect('/cart')
    if cart:
        cart = OrderLine.query.filter_by(order_id=cart.id).all()
    return render_template('cart.html', cart=cart)


@shop.route('/checkout', methods=['GET'])
@login_required
def checkout():
    iso_code = request.cookies.get('iso_code')
    # Get the last hanging cart
    cart_lines = None
    cart = Order.cart().filter_by(user_id=current_user.id).first()
    if cart:
        cart_lines = OrderLine.query.filter_by(order_id=cart.id).all()
        # For security reason, let's update all the order line prices again
        for line in db.session.query(OrderLine).filter_by(order_id=1).all():
            line.price = line.product.sale_price(
                current_app.config['PRODUCT_PRICING'], iso_code)
        db.session.commit()  # To ensure the updated figures are picked up
    # Summarize the cart items by Store>>store_amt_sum>>store_qty_sum
    # Why sum of quantities per store? Recall, dispatchers rates are per qty
    store_value_sq = db.session.query(
        Product.store_id.label('store_id'),
        db.func.sum(OrderLine.qty * OrderLine.price).label('store_amt_sum'),
        db.func.sum(OrderLine.qty).label(
            'store_qty_sum').label('store_qty_sum'),
    ).join(Product).filter(OrderLine.order_id == cart.id).group_by(
        Product.store_id).subquery()
    # All other payment data are related to the store
    pay_data = db.session.query(
        Store, store_value_sq.c.store_amt_sum,
        store_value_sq.c.store_qty_sum).join(
        store_value_sq, Store.id == store_value_sq.c.store_id).all()
    # Compute amounts
    store_value = utilities.amounts_sep(iso_code, pay_data)
    return render_template('checkout.html', cart=cart_lines,
                           store_value=store_value,
                           pay_data=pay_data)


@shop.route('/dashboard', methods=['GET'])
@login_required
def dashboard():
    return render_template('dashboard.html')


@shop.route('/img/product/<int:id>', methods=['GET'])
def product_img(id):
    product = Product.query.get_or_404(id)
    return Response(product.image, mimetype='image/jpg')


@shop.route('/market', methods=['GET'])
def market():
    iso_code = request.cookies.get('iso_code')
    products = Product.public()
    return render_template('market.html', products=products,
                           iso_code=iso_code)


@shop.route('/store/new', methods=['GET', 'POST'])
@login_required
def store_new():
    return render_template('store_new.html',
                           store_num=len(current_user.stores))


@ shop.route('/store/<string:store_name>/edit', methods=['GET', 'POST'])
@ login_required
def store_edit(store_name):
    # get the current store object
    store = Store.query.filter_by(name=store_name).first()
    form = StoreRegisterForm()
    if form.validate_on_submit():
        store.name = form.name.data
        store.about = form.about.data
        store.iso_code = form.iso_code.data
        store.logo = form.logo.data.read()
        store.user_id = current_user.id
        # We don't want to change account details
        if not(store.account):
            account = AccountDetail(
                account_name=form.account_name.data,
                account_num=form.account_num.data,
                bank_name=form.bank_name.data)
            db.session.add(account)
            store.account = account
        db.session.add(store)
        db.session.commit()
        flash('Succesfully edited', 'success')
        return redirect(url_for('.index'))
    # Pre-populating the form
    form.name.data = store.name
    form.about.data = store.about
    form.iso_code.data = store.iso_code
    # New stores don't posses account details
    if store.account:
        form.account_name.data = store.account.account_name
        form.account_num.data = store.account.account_num
        form.bank_name.data = store.account.bank_name
    return render_template('store_edit.html', form=form)


@ shop.route('/profile')
@ login_required
def profile():
    return render_template('profile.html')
