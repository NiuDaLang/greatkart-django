from django.shortcuts import render, redirect, get_object_or_404
from store.models import Product
from .models import Cart, CartItem, ProformaInvoice
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse
from store.models import Variation
from django.contrib.auth.decorators import login_required
import datetime

# Create your views here.
def _cart_id(request):
    cart = request.session.session_key
    if not cart:
        cart = request.session.create()
    return cart


def add_cart(request, product_id):
    current_user = request.user
    product = Product.objects.get(id=product_id) # get the product

    # If the user is authenticated
    if current_user.is_authenticated:
        product_variation = []

        # check variation
        if request.method == "POST":
            for item in request.POST:
                key = item
                value = request.POST[key]
                try:
                    variation = Variation.objects.get(product=product, variation_category__iexact=key, variation_value__iexact=value)
                    product_variation.append(variation)
                except Exception as e:
                    print(e)

        # check cart-item
        cart_item_exists = CartItem.objects.filter(product=product, user=current_user).exists()

        if cart_item_exists:
            # check variation
            cart_item = CartItem.objects.filter(product=product, user=current_user)
            # existing_variations => database
            ex_var_list = [] # find all the existing variations
            id = []
            for item in cart_item:
                existing_variation = item.variations.all()
                ex_var_list.append(list(existing_variation))
                id.append(item.id)

            if product_variation in ex_var_list: # if current variation has already been chosen
                # increase the cart_item quantity
                index = ex_var_list.index(product_variation)
                item_id = id[index]
                item = CartItem.objects.get(product=product, id=item_id)
                item.quantity += 1
                item.save()
            else:
                # create a new cart-item
                item = CartItem.objects.create(product=product, user=current_user, quantity=1)
                if len(product_variation) > 0:
                    item.variations.clear()
                    item.variations.add(*product_variation) # adding the star will make sure that it will add all the product variations
                item.save()
        else:
            cart_item = CartItem.objects.create(
                product = product,
                quantity = 1,
                user = current_user,
            )
            if len(product_variation) > 0:
                cart_item.variations.clear()
                for item in product_variation:
                    cart_item.variations.add(*product_variation)
            cart_item.save()
        return redirect("cart")
        
    # If the user is not authenticated    
    else: 
        product_variation = []

        # check variation
        if request.method == "POST":
            for item in request.POST:
                key = item
                value = request.POST[key]
                try:
                    variation = Variation.objects.get(product=product, variation_category__iexact=key, variation_value__iexact=value)
                    product_variation.append(variation)
                except Exception as e:
                    print(e)

        # check cart
        try:
            cart = Cart.objects.get(cart_id=_cart_id(request)) # get the cart using the cart_id present
        except Cart.DoesNotExist: # first time
            cart = Cart.objects.create(
                cart_id = _cart_id(request),
            )
        cart.save()

        # check cart-item
        cart_item_exists = CartItem.objects.filter(product=product, cart=cart).exists()

        if cart_item_exists:
            # check variation
            cart_item = CartItem.objects.filter(product=product, cart=cart)
            # existing_variations => database
            ex_var_list = [] # find all the existing variations
            id = []
            for item in cart_item:
                existing_variation = item.variations.all()
                ex_var_list.append(list(existing_variation))
                id.append(item.id)

            if product_variation in ex_var_list: # if current variation has already been chosen
                # increase the cart_item quantity
                index = ex_var_list.index(product_variation)
                item_id = id[index]
                item = CartItem.objects.get(product=product, id=item_id)
                item.quantity += 1
                item.save()
            else:
                # create a new cart-item
                item = CartItem.objects.create(product=product, cart=cart, quantity=1)
                if len(product_variation) > 0:
                    item.variations.clear()
                    item.variations.add(*product_variation) # adding the star will make sure that it will add all the product variations
                item.save()
        else:
            cart_item = CartItem.objects.create(
                product = product,
                quantity = 1,
                cart = cart,
            )
            if len(product_variation) > 0:
                cart_item.variations.clear()
                for item in product_variation:
                    cart_item.variations.add(*product_variation)
            cart_item.save()
        return redirect("cart")


def remove_cart(request, product_id, cart_item_id):
    product = get_object_or_404(Product, id=product_id)
    try:
        if request.user.is_authenticated:
            cart_item = CartItem.objects.get(product=product, user=request.user, id=cart_item_id)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request)) # only if not logged in
            cart_item = CartItem.objects.get(product=product, cart=cart, id=cart_item_id)

        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save()
        else:
            cart_item.delete()
    except:
        pass
    return redirect("cart")


def remove_cart_item(request, product_id, cart_item_id):
    product = get_object_or_404(Product, id=product_id)

    if request.user.is_authenticated:
        cart_item = CartItem.objects.get(product=product, user=request.user, id=cart_item_id)
    else:
        cart = Cart.objects.get(cart_id=_cart_id(request))
        cart_item = CartItem.objects.get(product=product, cart=cart, id=cart_item_id)

    cart_item.delete()
    return redirect("cart")


def cart(request, total=0, quantity=0, cart_items=None):
    try:
        tax = 0
        grand_total = 0
        if request.user.is_authenticated:
            cart_items = CartItem.objects.filter(user=request.user, is_active=True)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_items = CartItem.objects.filter(cart=cart, is_active=True)

        for cart_item in cart_items:
            total += (cart_item.product.price * cart_item.quantity)
            quantity += cart_item.quantity
        tax = (2 * total) / 100
        grand_total = total + tax

    except ObjectDoesNotExist:
        pass
    
    context = {
        "total": total,
        "quantity": quantity,
        "cart_items": cart_items,
        "tax": tax,
        "grand_total": grand_total,
    }

    return render(request, "store/cart.html", context)


@login_required(login_url="login")
def checkout(request, total=0, quantity=0, cart_items=None):
    try:
        tax = 0
        grand_total = 0

        if request.user.is_authenticated:
            cart_items = CartItem.objects.filter(user=request.user, is_active=True)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_items = CartItem.objects.filter(cart=cart, is_active=True)
        for cart_item in cart_items:
            total += (cart_item.product.price * cart_item.quantity)
            quantity += cart_item.quantity
            print(f"total: {total}, quantity: {quantity}")
        tax = (2 * total) / 100
        grand_total = total + tax
        print(f"item_total: {total}, item_quantity: {quantity}")
    except:
        raise ObjectDoesNotExist(f"CartItem Doesn't Exist")

    try:
        # check if proforma for this cart already exists
        existing_proforma_invoice = ProformaInvoice.objects.get(user=request.user, is_ordered=False)
        print(f"existing_proforma_invoice ==> {existing_proforma_invoice}")

        # update cart contents if proforma for this cart was made before
        proforma_order_number = existing_proforma_invoice.proforma_order_number
        existing_proforma_invoice.item_total = total
        existing_proforma_invoice.tax = tax
        existing_proforma_invoice.order_total = grand_total
        existing_proforma_invoice.save()

    except ObjectDoesNotExist:
        # if proforma doesn't not exist, create a new one
        proforma = ProformaInvoice()
        proforma.user = request.user

        # Generate order number
        now = datetime.datetime.now()
        yr = str(now.strftime("%Y"))
        mt = str(now.strftime("%m"))
        dt = str(now.strftime("%d"))
        hr = str(now.strftime("%H"))
        mn = str(now.strftime("%M"))
        sc = str(now.strftime("%S"))
        current_date = yr + mt + dt + hr + mn + sc

        proforma.proforma_order_number = current_date + str(request.user)
        proforma.item_total = total
        proforma.tax = tax
        proforma.order_total = grand_total
        proforma.save()
        proforma_order_number = proforma.proforma_order_number

        proforma = ProformaInvoice.objects.get(proforma_order_number=proforma_order_number)
        print(f"new_proforma_invoice ==> {proforma}")


    context = {
        "total": total,
        "quantity": quantity,
        "cart_items": cart_items,
        "tax": tax,
        "grand_total": grand_total,
        "proforma_order_number": proforma_order_number,
    }
    return render(request, "store/checkout.html", context)