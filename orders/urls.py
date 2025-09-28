from django.urls import path
from . import views, paypal

urlpatterns = [
    path("place_order/<str:proforma_order_number>/", views.place_order , name="place_order"),
    path("paypal_orders/", paypal.paypal_orders, name="paypal_orders"),
    path("paypal_orders/<order_id>/capture/", paypal.paypal_capture_orders, name="paypal_capture_orders"),
    path("paypal_orders/<order_id>/failure/", paypal.paypal_order_failure, name="paypal_order_failure"),
    path("paypal_orders/<order_id>/success/", paypal.paypal_order_success, name="paypal_order_success"),
    path("paypal_orders/order_complete/", paypal.order_complete, name="order_complete"),
    
    # path("payments/", views.payments, name="payments"),
    # path("payment_success/", views.payment_success, name="payment_success"),
    # path("payment_failed/", views.payment_failed, name="payment_failed"),
]
