from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.access import can, module_for_path


class RoleDeskTests(TestCase):
    def setUp(self):
        self.User = get_user_model()

    def test_hr_sees_people_and_not_money(self):
        hr = self.User.objects.create_user(email='hr@example.com', password='testpass1', role='hr')
        self.assertTrue(can(hr, 'people'))
        self.assertTrue(can(hr, 'team'))
        self.assertFalse(can(hr, 'billing'))
        self.assertFalse(can(hr, 'leads'))

    def test_finance_sees_money_and_not_the_floor(self):
        finance = self.User.objects.create_user(email='fin@example.com', password='testpass1', role='finance')
        self.assertTrue(can(finance, 'billing'))
        self.assertTrue(can(finance, 'clients'))
        self.assertFalse(can(finance, 'people'))
        self.assertFalse(can(finance, 'leads'))

    def test_custom_permission_adds_a_section(self):
        hr = self.User.objects.create_user(
            email='hr2@example.com',
            password='testpass1',
            role='hr',
            custom_permissions=['whatsapp', 'finance'],
        )
        self.assertTrue(can(hr, 'whatsapp'))
        self.assertTrue(can(hr, 'billing'))

    def test_paths_match_the_desk(self):
        self.assertEqual(module_for_path('/api/finance/invoices/'), 'billing')
        self.assertEqual(module_for_path('/api/reports/sales/'), 'leads')
        self.assertIsNone(module_for_path('/api/team/attendance/check-in/'))
        self.assertIsNone(module_for_path('/api/whatsapp/webhook/'))
        self.assertEqual(module_for_path('/api/whatsapp/conversations/'), 'whatsapp')
