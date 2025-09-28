from django import forms
from .models import Order
# from paypal.standard.forms import PayPalPaymentsForm


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["first_name", 
                  "last_name", 
                  "phone", 
                  "email", 
                  "address_line_1", 
                  "address_line_2",
                  "country",
                  "state",
                  "city",
                  "order_note",
                ]


# class CustomPayPalPaymentsForm(PayPalPaymentsForm):
#     def get_html_submit_element(self):
#         return """<button type="submit">Continue on PayPal website</button>"""