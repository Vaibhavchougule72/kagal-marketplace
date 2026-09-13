from decimal import Decimal

def cart_count(request):
    cart = request.session.get('cart', {'items': {}})
    count = sum(item['quantity'] for item in cart['items'].values())
    return {'cart_item_count': count}

def maintenance(request):

    if request.path.startswith("/admin"):
        return {
            "maintenance_mode": True
        }

    return {
        "maintenance_mode": True
    }