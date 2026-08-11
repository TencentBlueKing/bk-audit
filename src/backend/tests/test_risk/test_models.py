from unittest import mock

import pytest
from django.db.models import Q

from apps.permission.handlers.actions import ActionEnum
from services.web.risk.models import Risk


@pytest.mark.django_db
def test_authed_risk_filter_enabled(settings):
    settings.DISABLE_RISK_PERMISSION_FILTER = False

    ticket_queryset = mock.Mock()
    ticket_queryset.values.return_value = []

    with (
        mock.patch("services.web.risk.models.get_request_username", return_value="tester"),
        mock.patch(
            "services.web.risk.models.TicketPermission.objects.filter", return_value=ticket_queryset
        ) as ticket_filter,
        mock.patch("services.web.risk.models.PermissionService") as permission_service_cls,
    ):
        permission_service_cls.return_value.get_risk_filter.return_value = Q(pk__in=[])

        result = Risk.authed_risk_filter(ActionEnum.LIST_RISK)

    ticket_filter.assert_called_once()
    assert isinstance(result, Q)
