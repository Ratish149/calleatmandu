from django.urls import path

from customer.views import CustomerOrderActivityListAPIView

urlpatterns = [
    path(
        "customers/order-activity/",
        CustomerOrderActivityListAPIView.as_view(),
        name="customer-order-activity",
    )
]
