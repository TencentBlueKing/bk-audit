# -*- coding: utf-8 -*-
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from services.web.risk.views import EventsViewSet
from tests.base import TestCase


class EventsViewSetPermissionTest(TestCase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()

    def test_get_instance_id_returns_none_without_risk_id(self):
        view = EventsViewSet()
        view.request = Request(self.factory.get("/api/v1/events/"))

        self.assertIsNone(view.get_instance_id())

    def test_get_instance_id_returns_request_risk_id(self):
        view = EventsViewSet()
        view.request = Request(self.factory.get("/api/v1/events/", {"risk_id": "risk-1"}))

        self.assertEqual(view.get_instance_id(), "risk-1")
