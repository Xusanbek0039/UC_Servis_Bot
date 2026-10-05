import json
import logging
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework import status
from .services import PaymentService

logger = logging.getLogger("apps.payments.webhook")


class TezCheckWebhookView(APIView):
    """
    TezCheck webhook receiver endpoint.
    POST /api/webhooks/tezcheck/
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        signature = (
            request.headers.get("X-Signature")
            or request.headers.get("Signature")
            or request.data.get("signature")
        )

        logger.info(f"Received TezCheck webhook with signature: {signature}")

        payload = request.data
        if not isinstance(payload, dict):
            try:
                payload = json.loads(request.body.decode("utf-8"))
            except Exception:
                return JsonResponse({"status": "error", "message": "Invalid JSON body"}, status=400)

        success, message = PaymentService.process_tezcheck_webhook(
            payload=payload,
            signature=signature,
        )

        if not success:
            logger.warning(f"TezCheck webhook processing returned error: {message}")
            return JsonResponse({"status": "error", "message": message}, status=400)

        return JsonResponse({"status": "success", "message": message}, status=200)
