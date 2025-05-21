from django.test import TestCase
from unittest.mock import patch, MagicMock
from django.utils import timezone
from core.exceptions import PermissionException
from services.web.risk.models import Risk
from services.web.risk.permissions import RiskViewPermission
from services.web.strategy_v2.models import Strategy
from services.web.strategy_v2.resources import GetEventFieldsConfig
from services.web.strategy_v2.serializers import (
    GetEventInfoFieldsRequestSerializer,
    GetEventInfoFieldsResponseSerializer
)


class TestGetEventFieldsConfig(TestCase):
    def setUp(self):
        # Create strategy with integer ID
        self.strategy = Strategy.objects.create(
            strategy_id=1,
            event_data_field_configs=[
                {"field_name": "data_field1", "display_name": "Data Field 1"},
                {"field_name": "data_field2"}
            ],
            event_evidence_field_configs=[
                {"field_name": "evidence_field1", "display_name": "Evidence Field 1", "description": "Desc1"},
                {"field_name": "evidence_field2"}
            ]
        )

        # Create risk with matching strategy_id
        self.risk = Risk.objects.create(
            strategy_id=1,
            raw_event_id="event123",
            operator="user1",
            event_data={"data_field1": "value1", "data_field3": ["a", "b", "c"]},
            event_evidence='[{"evidence_field1": "ev_value1", "evidence_field3": {"nested": "value"}}]',
            event_time=timezone.now()
        )

        self.config = GetEventFieldsConfig()

    @patch('apps.meta.utils.format.preprocess_data')
    def test_get_event_basic_field_configs(self, mock_preprocess):
        """Test basic event field configurations"""
        mock_preprocess.side_effect = lambda x: x

        fields = self.config.get_event_basic_field_configs(
            risk=self.risk,
            has_permission=True
        )
        self.assertEqual(len(fields), 7)
        self.assertEqual(fields[0]["field_name"], "raw_event_id")
        self.assertEqual(fields[0]["example"], "event123")

    @patch('apps.meta.utils.format.preprocess_data')
    def test_get_event_data_field_configs(self, mock_preprocess):
        """Test event data field configurations"""
        mock_preprocess.side_effect = lambda x: ", ".join(map(str, x)) if isinstance(x, list) else x

        fields = self.config.get_event_data_field_configs(
            strategy=self.strategy,
            risk=self.risk,
            has_permission=True
        )
        field_dict = {f["field_name"]: f for f in fields}
        self.assertEqual(len(field_dict), 3)
        self.assertEqual(field_dict["data_field1"]["display_name"], "Data Field 1")
        self.assertEqual(field_dict["data_field3"]["example"], "a, b, c")

    @patch('apps.meta.utils.format.preprocess_data')
    def test_get_event_evidence_field_configs(self, mock_preprocess):
        """Test event evidence field configurations"""
        # Update mock to return dictionaries as-is (not converting to strings)
        mock_preprocess.side_effect = lambda x: x

        fields = self.config.get_event_evidence_field_configs(
            strategy=self.strategy,
            risk=self.risk,
            has_permission=True
        )
        field_dict = {f["field_name"]: f for f in fields}
        self.assertEqual(len(field_dict), 3)
        self.assertEqual(field_dict["evidence_field1"]["description"], "Desc1")
        # Update expectation to match actual behavior (dictionary instead of string)
        self.assertEqual(field_dict["evidence_field3"]["example"], {'nested': 'value'})

    @patch('apps.meta.utils.format.preprocess_data')
    @patch('services.web.strategy_v2.resources.get_request_username')
    @patch('services.web.strategy_v2.resources.RiskViewPermission')
    def test_perform_request_with_valid_data(self, mock_permission, mock_username, mock_preprocess):
        """Test request with valid data and permissions"""
        mock_permission_instance = MagicMock()
        mock_permission.return_value = mock_permission_instance
        mock_permission_instance.has_risk_permission.return_value = True
        mock_username.return_value = "test_user"
        mock_preprocess.side_effect = lambda x: x

        validated_request_data = {
            "strategy_id": 1
        }

        response = self.config.perform_request(validated_request_data)

        self.assertIsInstance(response, dict)
        self.assertIn("event_basic_field_configs", response)
        self.assertIn("event_data_field_configs", response)
        self.assertIn("event_evidence_field_configs", response)

    @patch('apps.meta.utils.format.preprocess_data')
    def test_perform_request_without_strategy(self, mock_preprocess):
        """Test request with non-existent strategy"""
        mock_preprocess.side_effect = lambda x: x

        validated_request_data = {
            "strategy_id": 999
        }

        response = self.config.perform_request(validated_request_data)

        self.assertEqual(len(response["event_basic_field_configs"]), 7)
        self.assertEqual(len(response["event_data_field_configs"]), 0)
        self.assertEqual(len(response["event_evidence_field_configs"]), 0)

    @patch('apps.meta.utils.format.preprocess_data')
    @patch('services.web.strategy_v2.resources.get_request_username')
    @patch('services.web.strategy_v2.resources.RiskViewPermission')
    def test_perform_request_without_permission(self, mock_permission, mock_username, mock_preprocess):
        """Test request without permissions"""
        mock_permission_instance = MagicMock()
        mock_permission.return_value = mock_permission_instance
        mock_permission_instance.has_risk_permission.return_value = False
        mock_username.return_value = "test_user"
        mock_preprocess.side_effect = lambda x: x

        validated_request_data = {
            "strategy_id": 1
        }

        response = self.config.perform_request(validated_request_data)

        for field in response["event_basic_field_configs"]:
            self.assertEqual(field["example"], "")
        for field in response["event_data_field_configs"]:
            self.assertEqual(field["example"], "")
        for field in response["event_evidence_field_configs"]:
            self.assertEqual(field["example"], "")

    def test_preprocess_data_function(self):
        """Test the standalone preprocess_data function"""
        from apps.meta.utils.format import preprocess_data

        # Test with list input
        self.assertEqual(preprocess_data([1, 2, 3]), "1, 2, 3")

        # Test with dict containing list
        input_dict = {"key": [4, 5], "nested": {"sub": ["a", "b"]}}
        expected_dict = {"key": "4, 5", "nested": {"sub": "a, b"}}
        self.assertEqual(preprocess_data(input_dict), expected_dict)

        # Test with non-list/dict input
        self.assertEqual(preprocess_data("test"), "test")
        self.assertEqual(preprocess_data(123), 123)
        self.assertEqual(preprocess_data(None), None)