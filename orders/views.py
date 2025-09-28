from django.shortcuts import render, redirect
from carts.models import CartItem
from .forms import OrderForm
from .models import Order
import datetime
from decouple import config
from django.conf import settings
import requests
from django.core.exceptions import ObjectDoesNotExist


#$$$$ paypal - BE - django-paypal $$$$#
# from django.urls import reverse
# from paypal.standard.forms import PayPalPaymentsForm
# from django.conf import settings
# import uuid # unique user id for duplicate orders


# Create your views here.
# def payments(request):
#     return render(request, "orders/payments.html")


def place_order(request, proforma_order_number, total=0, quantity=0,):
    current_user = request.user

    # If the cart count <= 0, then redirect back to shop
    cart_items = CartItem.objects.filter(user=current_user)
    cart_count = cart_items.count()
    if cart_count <= 0:
        return redirect("store")
    
    tax = 0
    grand_total = 0

    for item in cart_items:
        total += (item.product.price * item.quantity)
        quantity += item.quantity

    tax = (total * 2) / 100
    grand_total = total + tax

    
    if request.method == "POST":
        # Check if order already exists:
        try:
            order = Order.objects.get(user=current_user, is_ordered=False, order_number=proforma_order_number)
        except ObjectDoesNotExist:
            order = Order()

        form = OrderForm(request.POST)
        if form.is_valid():
            order.user = current_user
            order.first_name = form.cleaned_data["first_name"]
            order.last_name = form.cleaned_data["last_name"]
            order.phone = form.cleaned_data["phone"]
            order.email = form.cleaned_data["email"]
            order.address_line_1 = form.cleaned_data["address_line_1"]
            order.address_line_2 = form.cleaned_data["address_line_2"]
            order.country = form.cleaned_data["country"]
            order.state = form.cleaned_data["state"]
            order.city = form.cleaned_data["city"]
            order.order_note = form.cleaned_data["order_note"]
            order.item_total = total
            order.tax = tax
            order.order_total = grand_total
            order.ip = request.META.get("REMOTE_ADDR")
            order.save()
            # # Generate order number
            # yr = int(datetime.date.today().strftime("%Y"))
            # dt = int(datetime.date.today().strftime("%d"))
            # mt = int(datetime.date.today().strftime("%m"))
            # d = datetime.date(yr, mt, dt)
            # current_date = d.strftime("%Y%m%d") #20250925
            order.order_number = proforma_order_number
            order.save()


            #$$$$ Paypal - django-paypal $$$$#
            # # (1) Get the host - tell PayPal where to send us back to
            # host = request.get_host()
            # print("http://{}{}".format(host, reverse("paypal-ipn")))
            # # (2) Create PayPal Form Dictionary
            # # Variables Full List: https://developer.paypal.com/api/nvp-soap/paypal-payments-standard/integration-guide/Appx-websitestandard-htmlvariables/
            # paypal_dict = {
            #     "business": settings.PAYPAL_RECEIVER_EMAIL,
            #     "amount": grand_total,
            #     "item_name": "Merchandise",
            #     "no_shipping": "2",
            #     "invoice": str(uuid.uuid4()),
            #     "currency_code": "USD",
            #     "notify_url": "http://{}{}".format(host, reverse("paypal-ipn")),
            #     "return_url": "http://{}{}".format(host, reverse("payment_success")),
            #     "cancel_return": "http://{}{}".format(host, reverse("payment_failed")),
            # }
            # # (3) Create actual paypal button
            # paypal_form = PayPalPaymentsForm(initial=paypal_dict)
            # # paypal_form = CustomPayPalPaymentsForm(initial=paypal_dict)

            context = {
                "order": order,
                "cart_items": cart_items,
                "total": total,
                "tax": tax,
                "grand_total": grand_total,
                # "paypal_form": paypal_form, # django-paypal
                "paypal_client_id": settings.PAYPAL_CLIENT_ID,
                "proforma_order_number": proforma_order_number,
            }

            return render(request, "orders/payments.html", context)
    else:
        return redirect('checkout')


##### BE - django-payapl #####
# def payment_success(request):
#     return render(request, "orders/payment_success.html")


# def payment_failed(request):
#     return render(request, "orders/payment_failed.html")

#$$$$ FE - paypal-server-sdk $$$$#


