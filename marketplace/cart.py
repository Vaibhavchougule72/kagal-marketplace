from decimal import Decimal
from .models import Product


class Cart:

    def __init__(self, request):
        self.session = request.session
        cart = self.session.get('cart')

        if not cart:
            cart = self.session['cart'] = {
                'store_id': None,
                'items': {}
            }

        self.cart = cart

    def add(self, product, quantity=1):

        product_id = str(product.id)

        # Single Store Restriction
        if self.cart['store_id'] and self.cart['store_id'] != product.store.id:
            self.cart['items'] = {}

        self.cart['store_id'] = product.store.id

        if product_id not in self.cart['items']:
            self.cart['items'][product_id] = {
                'quantity': 0,
                'price': str(product.price)
            }

        self.cart['items'][product_id]['quantity'] += quantity
        self.save()

    def decrease(self, product):
        product_id = str(product.id)

        if product_id in self.cart['items']:
            self.cart['items'][product_id]['quantity'] -= 1

            if self.cart['items'][product_id]['quantity'] <= 0:
                del self.cart['items'][product_id]

        self.save()

    def remove(self, product):
        product_id = str(product.id)

        if product_id in self.cart['items']:
            del self.cart['items'][product_id]

        self.save()

    def clear(self):
        self.session['cart'] = {
            'store_id': None,
            'items': {}
        }
        self.save()

    def save(self):
        self.session.modified = True