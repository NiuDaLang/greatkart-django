from django.conf import settings
import requests
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from decouple import config
from store.models import Product
from .models import Order, OrderProduct, Payment
from carts.models import ProformaInvoice, CartItem
import json
from django.template.loader import render_to_string
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMessage

#$$$$ paypal - SDK - paypal-server-sdk $$$$#
import logging

from paypalserversdk.http.auth.o_auth_2 import ClientCredentialsAuthCredentials
from paypalserversdk.logging.configuration.api_logging_configuration import (
    LoggingConfiguration,
    RequestLoggingConfiguration,
    ResponseLoggingConfiguration,
)
from paypalserversdk.paypal_serversdk_client import PaypalServersdkClient
from paypalserversdk.controllers.orders_controller import OrdersController
from paypalserversdk.controllers.payments_controller import PaymentsController
from paypalserversdk.models.amount_breakdown import AmountBreakdown
from paypalserversdk.models.amount_with_breakdown import AmountWithBreakdown
from paypalserversdk.models.checkout_payment_intent import CheckoutPaymentIntent
from paypalserversdk.models.order_request import OrderRequest
from paypalserversdk.models.capture_request import CaptureRequest
from paypalserversdk.models.money import Money
from paypalserversdk.models.shipping_details import ShippingDetails
from paypalserversdk.models.shipping_option import ShippingOption
from paypalserversdk.models.shipping_type import ShippingType
from paypalserversdk.models.purchase_unit_request import PurchaseUnitRequest
from paypalserversdk.models.payment_source import PaymentSource
from paypalserversdk.models.card_request import CardRequest
from paypalserversdk.models.card_attributes import CardAttributes
from paypalserversdk.models.card_verification import CardVerification
from paypalserversdk.models.orders_card_verification_method import OrdersCardVerificationMethod
from paypalserversdk.models.item import Item
from paypalserversdk.models.item_category import ItemCategory
from paypalserversdk.models.payment_source import PaymentSource
from paypalserversdk.models.paypal_wallet import PaypalWallet
from paypalserversdk.models.paypal_wallet_experience_context import (
    PaypalWalletExperienceContext,
)
from paypalserversdk.models.shipping_preference import ShippingPreference
from paypalserversdk.models.paypal_experience_landing_page import (
    PaypalExperienceLandingPage,
)
from paypalserversdk.models.paypal_experience_user_action import (
    PaypalExperienceUserAction,
)
from paypalserversdk.exceptions.error_exception import ErrorException
from paypalserversdk.api_helper import ApiHelper

paypal_client: PaypalServersdkClient = PaypalServersdkClient(
    client_credentials_auth_credentials=ClientCredentialsAuthCredentials(
        o_auth_client_id=config("PAYPAL_CLIENT_ID"),
        o_auth_client_secret=config("PAYPAL_CLIENT_SECRET"),
    ),
    logging_configuration=LoggingConfiguration(
        log_level=logging.INFO,
        # Disable masking of sensitive headers for Sandbox testing.
        # This should be set to True (the default if unset)in production.
        mask_sensitive_headers=False,
        request_logging_config=RequestLoggingConfiguration(
            log_headers=True, log_body=True
        ),
        response_logging_config=ResponseLoggingConfiguration(
            log_headers=True, log_body=True
        ),
    ),
)

orders_controller: OrdersController = paypal_client.orders
payments_controller: PaymentsController = paypal_client.payments


def paypal_orders(request, proforma_order_number=None):
      proforma_order_number = request.GET.get('proforma_order_number')

      proforma_order = ProformaInvoice.objects.get(proforma_order_number=proforma_order_number)
      cartItems = CartItem.objects.filter(user=proforma_order.user)

      # use the cart information passed from the front-end to calculate the order amount details
      order = orders_controller.create_order({
          "body": OrderRequest(
              intent=CheckoutPaymentIntent.CAPTURE,
              purchase_units=[
                  PurchaseUnitRequest(
                      amount=AmountWithBreakdown(
                          currency_code="USD",
                          value=proforma_order.order_total,
                          breakdown=AmountBreakdown(
                              item_total=Money(currency_code="USD", value=proforma_order.item_total),
                              tax_total=Money(currency_code="USD", value=proforma_order.tax),
                          ),
                      ),
                      items=[
                          Item(
                              name=item.product.product_name,
                              unit_amount=Money(currency_code="USD", value=item.product.price),
                              quantity=item.quantity,
                              description=item.product.description,
                              sku=f"{[variation for variation in [item.variations.all()]]}",
                              category=ItemCategory.PHYSICAL_GOODS,
                          ) for item in cartItems
                      ],
                  )
              ],
          )
      })

      response = HttpResponse(ApiHelper.json_serialize(order.body), status=200)
      response['mimetype'] = "application/json"
      return response


def paypal_capture_orders(request, order_id=None):
    # order_id ==> transaction id
    order = orders_controller.capture_order(
        {"id": order_id, "prefer": "return=representation"}
    )
    response = HttpResponse(ApiHelper.json_serialize(order.body), status=200)
    response['mimetype'] = "application/json"
    
    return response


def paypal_order_failure(request, order_id=None):
     user = request.user
     context = {
        "user": user,
        "order_id": order_id,
     }
     return render(request, "orders/payment_failure.html", context)


def paypal_order_success(request, order_id=None):
    body = json.loads(request.body)
    order = Order.objects.get(user=request.user, is_ordered=False, order_number=body["order_number"])
    purchase = body["purchase"]
    amount_paid = 0
    for unit in purchase:
        amount_paid += float(unit['amount']['value'])

    # (1) Store transaction details inside Payment model
    payment = Payment(
         user = request.user,
         payment_id = body["transcation_id"],
         payment_method = body["payment_method"],
         amount_paid = amount_paid,
         status = body["status"],
    )
    payment.save()

    order.payment = payment
    order.is_ordered = True
    order.save()

    # (2) Move the Cart Items to OrderProduct table
    cart_items = CartItem.objects.filter(user=request.user)

    for item in cart_items:
        orderproduct = OrderProduct()
        orderproduct.order_id = order.id
        orderproduct.payment = payment
        orderproduct.user_id = request.user.id
        orderproduct.product_id = item.product_id
        orderproduct.quantity = item.quantity
        orderproduct.product_price = item.product.price
        orderproduct.ordered = True
        orderproduct.save()

        cart_item = CartItem.objects.get(id=item.id)
        product_variation = cart_item.variations.all()
        orderproduct = OrderProduct.objects.get(id=orderproduct.id)
        orderproduct.variations.set(product_variation)
        orderproduct.save()

        # (3) Reduce the quantity of the sold products
        product = Product.objects.get(id=item.product.id)
        product.stock -= item.quantity
        product.save()

    # (4) Clear Cart & Proforma Invoice
    CartItem.objects.filter(user=request.user).delete()
    print("cart item cleared")
    proforma_order = ProformaInvoice.objects.get(proforma_order_number=order.order_number)
    proforma_order.is_ordered = True
    proforma_order.save()

    # (5) Send order received email to customer
    mail_subject = "Thank you for your order!"
    message = render_to_string("orders/order_received_email.html", {
        "user": request.user,
        "order": order,
    })
    to_email = request.user.email
    send_email = EmailMessage(mail_subject, message, to=[to_email])
    send_email.send()

    # (6) Send order number and payment transaction id back to front-end onApprove() via JsonResponse
    data = {
         "order_number": order.order_number,
         "transaction_id": body["transcation_id"],
    }
    return JsonResponse(data)


def order_complete(request):
    order_number = request.GET.get("order_number")
    transaction_id = request.GET.get("transaction_id")
    try:
        order = Order.objects.get(order_number=order_number, is_ordered=True)
        ordered_products = OrderProduct.objects.filter(order_id=order.id)

        context = {
            "order": order,
            "ordered_products": ordered_products,
            "transaction_id": transaction_id,
        }
        return render(request, "orders/payment_success.html", context)
    except (Payment.DoesNotExist, Order.DoesNotExist):
        return redirect("home")