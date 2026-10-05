from django.urls import path
from .views import TezCheckWebhookView

urlpatterns = [
    path("tezcheck/", TezCheckWebhookView.as_view(), name="tezcheck-webhook"),
]
