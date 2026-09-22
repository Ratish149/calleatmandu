import django_filters

from message.models import Conversation, Message


class ConversationFilter(django_filters.FilterSet):
    platform = django_filters.CharFilter(
        field_name="platform", lookup_expr="iexact"
    )
    applicant_id = django_filters.CharFilter(field_name="applicant_id")
    contact_id = django_filters.CharFilter(field_name="contact_id")

    class Meta:
        model = Conversation
        fields = ["platform", "applicant_id", "contact_id"]


class MessageFilter(django_filters.FilterSet):
    direction = django_filters.CharFilter(field_name="direction")
    is_read = django_filters.BooleanFilter(field_name="is_read")

    class Meta:
        model = Message
        fields = ["direction", "is_read"]
