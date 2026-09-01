from django.http import HttpResponse
from django.utils.timezone import now
from django_filters import rest_framework as django_filters
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Order

from .filters import NPSTransactionFilterSet
from .models import NPSConfig, NPSTransaction
from .selectors import get_nps_config
from .serializers import (
    NPSConfigSerializer,
    NPSInitiatePaymentSerializer,
    NPSServiceChargeQuerySerializer,
    NPSTransactionSerializer,
)
from .services import (
    build_gateway_form_payload,
    fetch_payment_instruments,
    fetch_service_charge,
    generate_merchant_txn_id,
    get_process_id,
    verify_transaction_status,
)


def _update_order_on_success(order, merchant_txn_id):
    if not order:
        return
    update_fields = []
    if hasattr(order, "is_paid"):
        order.is_paid = True
        update_fields.append("is_paid")
    if hasattr(order, "order_status"):
        order.order_status = "Confirmed"
        update_fields.append("order_status")
    elif hasattr(order, "status"):
        order.status = "Confirmed"
        update_fields.append("status")
    if hasattr(order, "transaction_id"):
        order.transaction_id = merchant_txn_id
        update_fields.append("transaction_id")
    if update_fields:
        order.save(update_fields=update_fields)


class CustomPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class NPSConfigListCreateAPIView(generics.ListCreateAPIView):
    queryset = NPSConfig.objects.select_related("franchise").all()
    serializer_class = NPSConfigSerializer
    permission_classes = [IsAuthenticated]


class NPSConfigRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = NPSConfig.objects.select_related("franchise").all()
    serializer_class = NPSConfigSerializer
    permission_classes = [IsAuthenticated]


class NPSStatusAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        franchise_slug = request.query_params.get(
            "franchise"
        ) or request.query_params.get("franchise_slug")
        config = get_nps_config(
            franchise_identifier=franchise_slug, raise_exception=False
        )
        is_enabled = bool(config and config.is_enabled)
        return Response(
            {
                "is_enabled": is_enabled,
                "franchise": franchise_slug,
            },
            status=status.HTTP_200_OK,
        )


class NPSInstrumentsAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        franchise_slug = request.query_params.get(
            "franchise"
        ) or request.query_params.get("franchise_slug")
        config = get_nps_config(franchise_identifier=franchise_slug)
        try:
            res_data = fetch_payment_instruments(config)
            return Response(res_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"detail": f"Failed to fetch payment instruments: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class NPSServiceChargeAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = NPSServiceChargeQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        franchise_slug = serializer.validated_data.get("franchise")
        config = get_nps_config(franchise_identifier=franchise_slug)

        amount = serializer.validated_data["amount"]
        instrument_code = serializer.validated_data["instrument_code"]

        try:
            res_data = fetch_service_charge(config, str(amount), instrument_code)
            return Response(res_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"detail": f"Failed to fetch service charge: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class NPSInitiatePaymentAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = NPSInitiatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order_id = serializer.validated_data.get("order_id")
        amount = serializer.validated_data["amount"]
        remarks = serializer.validated_data.get("remarks", "")
        instrument_code = serializer.validated_data.get("instrument_code", "")
        response_url = serializer.validated_data.get("response_url", "")
        franchise_slug = serializer.validated_data.get("franchise")

        order = None
        if order_id:
            order = (
                Order.objects.filter(id=order_id).select_related("franchise").first()
            )
            if not order:
                return Response(
                    {"detail": f"Order with ID {order_id} not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        config = get_nps_config(franchise_identifier=franchise_slug, order=order)

        merchant_txn_id = generate_merchant_txn_id()

        # Step 1: Call GetProcessId from NPS
        try:
            success, process_res = get_process_id(config, str(amount), merchant_txn_id)
        except Exception as e:
            return Response(
                {"detail": f"Unable to reach NPS Gateway: {str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if not success or "data" not in process_res or not process_res["data"]:
            return Response(
                {
                    "detail": "Failed to generate ProcessId from NPS Gateway",
                    "nps_response": process_res,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        process_id = process_res["data"].get("ProcessId")

        # Step 2: Create NPSTransaction record
        NPSTransaction.objects.create(
            order=order,
            merchant_txn_id=merchant_txn_id,
            process_id=process_id,
            amount=amount,
            status="Pending",
            transaction_remarks=remarks,
            raw_response=process_res,
        )

        target_gateway_url = process_res.get("target_gateway_url", "")

        # Step 3: Build Gateway Redirection Form
        form_payload = build_gateway_form_payload(
            config=config,
            merchant_txn_id=merchant_txn_id,
            amount=str(amount),
            process_id=process_id,
            remarks=remarks,
            instrument_code=instrument_code,
            response_url=response_url,
            override_gateway_url=target_gateway_url,
        )

        return Response(
            {
                "merchant_txn_id": merchant_txn_id,
                "process_id": process_id,
                "gateway_form": form_payload,
            },
            status=status.HTTP_200_OK,
        )


class NPSWebhookListenerAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        merchant_txn_id = request.query_params.get(
            "MerchantTxnId"
        ) or request.query_params.get("merchant_txn_id")
        gateway_txn_id = (
            request.query_params.get("GatewayTxnId")
            or request.query_params.get("gateway_txn_id")
            or request.query_params.get("GatewayReferenceNo")
        )

        if not merchant_txn_id:
            return HttpResponse("invalid request", status=400)

        txn = (
            NPSTransaction.objects
            .filter(merchant_txn_id=merchant_txn_id)
            .select_related("order__franchise")
            .first()
        )
        if not txn:
            return HttpResponse("transaction not found", status=404)

        if txn.webhook_received_at is not None and txn.status.lower() == "success":
            return HttpResponse("already received", status=200)

        config = get_nps_config(order=txn.order)

        # Server-to-server check status verification
        success, status_res = verify_transaction_status(config, merchant_txn_id)
        txn.webhook_received_at = now()
        txn.raw_response = status_res

        if success and status_res.get("data"):
            data = status_res["data"]
            txn_status = data.get("Status", "Fail")
            txn.status = txn_status
            txn.institution = data.get("Institution", "")
            txn.instrument = data.get("Instrument", "")
            txn.cbs_message = data.get("CbsMessage", "")

            # According to NPS Gateway 2025 spec, the CheckTransactionStatus API returns 'GatewayReferenceNo' in data
            g_id = (
                data.get("GatewayReferenceNo")
                or data.get("GatewayTxnId")
                or data.get("GatewayTxnID")
            )
            if g_id:
                txn.gateway_txn_id = g_id
            elif gateway_txn_id:
                txn.gateway_txn_id = gateway_txn_id

            try:
                txn.service_charge = float(data.get("ServiceCharge", 0.0))
            except (ValueError, TypeError):
                pass

            order_id = request.query_params.get("order_id") or request.query_params.get(
                "order"
            )
            if not txn.order and order_id:
                order_obj = Order.objects.filter(id=order_id).first()
                if order_obj:
                    txn.order = order_obj

            if str(txn_status).strip().lower() in ["success", "0"]:
                txn.status = "Success"
                _update_order_on_success(txn.order, merchant_txn_id)
        else:
            if gateway_txn_id:
                txn.gateway_txn_id = gateway_txn_id
            txn.status = "Fail"

        txn.save()
        return HttpResponse("received", status=200)


class NPSVerifyTransactionAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        merchant_txn_id = request.query_params.get(
            "merchant_txn_id"
        ) or request.query_params.get("MerchantTxnId")
        if not merchant_txn_id:
            return Response(
                {"detail": "merchant_txn_id query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        txn = (
            NPSTransaction.objects
            .filter(merchant_txn_id=merchant_txn_id)
            .select_related("order__franchise")
            .first()
        )
        if not txn:
            return Response(
                {"detail": f"Transaction {merchant_txn_id} not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        franchise_slug = request.query_params.get(
            "franchise"
        ) or request.query_params.get("franchise_slug")
        config = get_nps_config(franchise_identifier=franchise_slug, order=txn.order)

        query_gateway_txn_id = (
            request.query_params.get("gateway_txn_id")
            or request.query_params.get("GatewayTxnId")
            or request.query_params.get("GatewayReferenceNo")
        )

        # Refresh transaction status from NPS
        success, status_res = verify_transaction_status(config, merchant_txn_id)
        if success and status_res.get("data"):
            data = status_res["data"]
            txn_status = data.get("Status", "Fail")
            txn.status = txn_status
            txn.institution = data.get("Institution", "")
            txn.instrument = data.get("Instrument", "")
            txn.cbs_message = data.get("CbsMessage", "")
            txn.raw_response = status_res

            # Extract GatewayReferenceNo / GatewayTxnId according to NPS 2025 spec
            g_id = (
                data.get("GatewayReferenceNo")
                or data.get("GatewayTxnId")
                or data.get("GatewayTxnID")
            )
            if g_id:
                txn.gateway_txn_id = g_id
            elif query_gateway_txn_id:
                txn.gateway_txn_id = query_gateway_txn_id

            try:
                txn.service_charge = float(data.get("ServiceCharge", 0.0))
            except (ValueError, TypeError):
                pass

            order_id = request.query_params.get("order_id") or request.query_params.get(
                "order"
            )
            if not txn.order and order_id:
                order_obj = Order.objects.filter(id=order_id).first()
                if order_obj:
                    txn.order = order_obj

            if str(txn_status).strip().lower() in ["success", "0"]:
                txn.status = "Success"
                _update_order_on_success(txn.order, merchant_txn_id)

            txn.save()
        elif query_gateway_txn_id and not txn.gateway_txn_id:
            txn.gateway_txn_id = query_gateway_txn_id
            txn.save()

        serializer = NPSTransactionSerializer(txn)
        return Response(serializer.data, status=status.HTTP_200_OK)


class NPSTransactionListAPIView(generics.ListAPIView):
    queryset = NPSTransaction.objects.select_related("order").all()
    serializer_class = NPSTransactionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [django_filters.DjangoFilterBackend]
    filterset_class = NPSTransactionFilterSet
    pagination_class = CustomPagination


class NPSTransactionRetrieveAPIView(generics.RetrieveAPIView):
    queryset = NPSTransaction.objects.select_related("order").all()
    serializer_class = NPSTransactionSerializer
    permission_classes = [IsAuthenticated]
