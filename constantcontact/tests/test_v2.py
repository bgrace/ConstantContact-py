import time
import unittest
import uuid
from constantcontact.v2.api import *


#
# IMPORTANT: DO NOT USE ON YOUR LIVE ACCOUNT. These tests are actually integration tests with the ConstantContact API,
# they will create and delete real artifacts. ConstantContact does not offer a developer sandbox. As of this writing
# the documentation recommends creating a trial account for testing purposes.
#
# Set your API key and token in your environment, CONSTANTCONTACT_TEST_API_KEY and CONSTANTCONTACT_TEST_API_TOKEN


def get_api_from_environment_vars():

    import os
    key = os.environ['CONSTANTCONTACT_TEST_API_KEY']
    token = os.environ['CONSTANTCONTACT_TEST_API_TOKEN']
    return ConstantContact(key, token)

test_email_address = "test1@example.com"
test_contact_list_one_name = "Test Contact List 1"
test_contact_list_two_name = "Test Contact List 2"
test_contact_list_three_name = "Test Contact List 3"

def random_email():
    return str(uuid.uuid4())+"@example.com"

class ConstantContactTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        api = get_api_from_environment_vars()
        result = api.create_list(test_contact_list_one_name, ContactList.Status.HIDDEN)
        result = api.create_list(test_contact_list_two_name, ContactList.Status.HIDDEN)
        result = api.create_list(test_contact_list_three_name, ContactList.Status.HIDDEN)
        result = api.lists()  # the only way to get the id of a list that already exists is by fetching all and searching by name

        cls.test_list_one_id = ''
        cls.test_list_two_id = ''
        cls.test_list_three_id = ''
        for contact_list in result.instance:
            # TODO this is getting out of hand
            if contact_list.name == test_contact_list_one_name:
                cls.test_list_one_id = contact_list.list_id
            if contact_list.name == test_contact_list_two_name:
                cls.test_list_two_id = contact_list.list_id
            if contact_list.name == test_contact_list_three_name:
                cls.test_list_three_id = contact_list.list_id

        if not cls.test_list_one_id:
            raise Exception("Failed to find the test list one, things are looking bad.")

        if not cls.test_list_two_id:
            raise Exception("Failed to find the test list two, things are looking bad.")

        if not cls.test_list_three_id:
            raise Exception("Failed to find the test list three, things are looking bad.")

        result = api.create_contact(test_email_address,
                                    [cls.test_list_one_id],
                                    created_by_visitor=False,
                                    first_name="Test",
                                    last_name="One")  # Make sure some test fixtures are in place

    def setUp(self):
        try:
            self.api = get_api_from_environment_vars()
            self.assertIsInstance(self.api, ConstantContact)
        except KeyError:
            self.assertFalse(True, "Couldn't create API, probably missing environment variables for key or token")

    def tearDown(self):
        time.sleep(1)  # sleep time in seconds

    def test_get_bad_contact_by_email_fails(self):
        result = self.api.get_contact_by_email(random_email())
        self.assertFalse(result.success)
        self.assertFalse(result.created)
        self.assertIsNone(result.instance)
        self.assertEqual(200, result.response.status_code)

    def test_get_okay_contact_by_email_succeeds(self):
        result = self.api.get_contact_by_email(test_email_address)
        # A failure here probably means that something modified the test fixture created in setUpClass
        self.assertTrue(result.success)
        self.assertFalse(result.created)
        self.assertIsInstance(result.instance, Contact)
        self.assertEqual(result.instance.first_name, "Test")
        self.assertEqual(result.instance.last_name, "One")
        self.assertEqual(200, result.response.status_code)

    def test_add_then_delete_new_contact(self):

        email = random_email()
        first_name = "RandomTestFirstName"
        last_name = "RandomTestLastName"

        # create the contact and test its properities
        result = self.api.create_contact(email, [self.test_list_one_id], created_by_visitor=False,
                                         first_name=first_name, last_name=last_name)
        self.assertTrue(result.success)
        self.assertTrue(result.created)
        self.assertEqual(201, result.response.status_code)
        instance = result.instance
        contact_id = instance.contact_id
        self.assertIsInstance(instance, Contact)
        self.assertEqual(instance.raw['email_addresses'][0]['opt_in_source'], "ACTION_BY_OWNER")
        self.assertEqual(instance.first_name, first_name)
        self.assertEqual(instance.last_name, last_name)
        self.assertEqual(len(instance.lists), 1)
        self.assertEqual(instance.lists[0].list_id, self.test_list_one_id)

        # Look to contact back up in the system and make sure it's the same
        #time.sleep(2)
        confirmation_result = self.api.get_contact_by_email(email)
        self.assertTrue(confirmation_result.success)
        self.assertEqual(instance.contact_id, confirmation_result.instance.contact_id)

        # Make sure we can't create another contact with the same email
        #time.sleep(2)
        retry_result = self.api.create_contact(email, [self.test_list_one_id], created_by_visitor=False,
                                               first_name=first_name + '2', last_name=last_name + '2')
        self.assertFalse(retry_result.success)
        self.assertFalse(retry_result.created)
        self.assertFalse(retry_result.error)
        self.assertEqual(retry_result.response.status_code, 409)

        # Delete the contact and confirm response is as expected
        #time.sleep(2)
        deleted_result = instance.delete()

        self.assertTrue(deleted_result.success)
        self.assertFalse(deleted_result.created)
        self.assertIsNone(deleted_result.instance)

        # Make sure the contact is no longer returned
        #time.sleep(2)
        lookup_result = self.api.get_contact_by_email(email)

        self.assertTrue(lookup_result.success)
        self.assertFalse(lookup_result.error)
        self.assertEqual(lookup_result.instance.raw['status'], "OPTOUT")


    def test_subscribe_single_list(self):
        result = self.api.get_contact_by_email(test_email_address)
        self.assertTrue(result.success)

        contact = result.instance
        contact_id = contact.contact_id
        self.assertEqual(contact.raw['first_name'], "Test")
        self.assertEqual(contact.raw['last_name'], "One")
        self.assertFalse(contact.is_member('0123'))
        self.assertTrue(contact.is_member(self.test_list_one_id))
        self.assertFalse(contact.is_member(self.test_list_two_id))

        result = contact.subscribe(self.test_list_two_id)
        self.assertEqual(result.response.status_code, 200)
        self.assertTrue(result.success)

        contact = result.instance
        # TODO fetch the contact by id and run tests on that instance, perhaps compare that with result.instance

        self.assertEqual(contact.raw['first_name'], "Test")
        self.assertEqual(contact.raw['last_name'], "One")
        self.assertFalse(contact.is_member('0123'))
        self.assertTrue(contact.is_member(self.test_list_one_id))
        self.assertTrue(contact.is_member(self.test_list_two_id))

        result = contact.unsubscribe(self.test_list_two_id)
        self.assertEqual(result.response.status_code, 200)
        self.assertTrue(result.success)
        contact = result.instance
        self.assertEqual(contact.raw['first_name'], "Test")
        self.assertEqual(contact.raw['last_name'], "One")
        self.assertFalse(contact.is_member('0123'))
        self.assertTrue(contact.is_member(self.test_list_one_id))
        self.assertFalse(contact.is_member(self.test_list_two_id))

        result = contact.unsubscribe('0123')
        self.assertTrue(result.success)
        self.assertIsNone(result.response)


    def test_subscribe_multiple_list(self):
        result = self.api.get_contact_by_email(test_email_address)
        self.assertTrue(result.success)
        contact = result.instance

        self.assertTrue(contact.is_member(self.test_list_one_id))
        self.assertFalse(contact.is_member(self.test_list_two_id))
        self.assertFalse(contact.is_member(self.test_list_three_id))
        result = contact.subscribe([self.test_list_two_id, self.test_list_three_id])
        self.assertEqual(result.response.status_code, 200)
        self.assertTrue(result.success)
        contact = result.instance

        self.assertTrue(contact.is_member(self.test_list_one_id))
        self.assertTrue(contact.is_member(self.test_list_two_id))
        self.assertTrue(contact.is_member(self.test_list_three_id))

        result = contact.unsubscribe([self.test_list_two_id, self.test_list_three_id])
        self.assertEqual(result.response.status_code, 200)
        self.assertTrue(result.success)
        contact = result.instance
        self.assertTrue(contact.is_member(self.test_list_one_id))
        self.assertFalse(contact.is_member(self.test_list_two_id))
        self.assertFalse(contact.is_member(self.test_list_three_id))

    # TODO test here that ConstantContactResource can be converted to a list of ids









