from collections import namedtuple
import requests

APIResult = namedtuple('APIResult', ['success', 'error', 'created', 'instance', 'response'])


def api_failure(response):
    return APIResult(success=False, error=True, created=False, instance=None, response=response)


def api_creation(instance, response):
    return APIResult(success=True, error=False, created=True, instance=instance, response=response)


def api_acknowledged(response):
    return APIResult(success=False, error=False, created=False, instance=None, response=response)


def api_fetched(instance, response):
    return APIResult(success=True, error=False, created=False, instance=instance, response=response)


def api_deleted(response):
    return APIResult(success=response.status_code == 204, error=False, created=False, instance=None, response=response)


class ConstantContact:

    def __init__(self, key, token, api_root="https://api.constantcontact.com/v2/"):
        self.key = key
        self.token = token
        self.query_params = {'api_key': self.key}
        self.headers = {'Authorization': "Bearer "+self.token}
        self.s = requests.Session()
        self.s.headers.update(self.headers)
        self.s.params.update(self.query_params)
        self.api_root = api_root

    def api_endpoint(self, api_path):

        if isinstance(api_path, str):
            return self.api_root + api_path
        else:
            return self.api_root + '/'.join(api_path)

    def get(self, api_path, query_params=None):

        return self.s.get(self.api_endpoint(api_path),
                          params=query_params)

    def post(self, api_path, data, query_params=None):

        return self.s.post(self.api_endpoint(api_path),
                           json=data,
                           params=query_params)

    def put(self, api_path, data):
        return self.s.put(self.api_endpoint(api_path),
                          json=data)

    def delete(self, api_path):
        return self.s.delete(self.api_endpoint(api_path))

    def lists(self):
        response = self.get("lists")

        if 200 == response.status_code:
            instance = [ContactList.from_dict(self, cl) for cl in response.json()]
            return api_fetched(instance, response)
        else:
            return api_failure(response)

    def get_list(self, list_id):
        response = self.get('lists/'+str(list_id))

        if 200 == response.status_code:
            return ContactList.from_dict(self, d=response.json())
        else:
            return None

    def create_list(self, name, status):
        data = dict(name=name, status=status)
        response = self.post('lists', data)

        if 201 == response.status_code:
            return api_creation(ContactList.from_dict(self, d=response.json()), response)
        elif 409 == response.status_code:
            return api_acknowledged(response)
        else:
            return api_failure(response)

    def create_contact(self, email, contact_list_ids, created_by_visitor=True, data=None, **kwargs):

        if data is None:
            data = {}

        if created_by_visitor:
            action_by = 'ACTION_BY_VISITOR'
        else:
            action_by = 'ACTION_BY_OWNER'

        user_data = dict(email_addresses=[{'email_address': email}],
                    lists=[{'id': i} for i in contact_list_ids])
        user_data.update(data)
        user_data.update(**kwargs)

        response = self.post('contacts', user_data, {'action_by': action_by})

        if 201 == response.status_code:
            return api_creation(Contact(api=self, raw=response.json()), response)
        elif 409 == response.status_code:
            return api_acknowledged(response)
        else:
            return api_failure(response)

    def get_contact_by_email(self, email):
        response = self.get('contacts', query_params=dict(email=email, status='ALL'))
        if 200 == response.status_code:
            jsond = response.json()
            matching_contacts = jsond['results']

            if not matching_contacts:
                return api_acknowledged(response)
            else:
                first_result = Contact(api=self, raw=matching_contacts[0])
                return APIResult(success=True, error=False, created=False, instance=first_result, response=response)
        else:
            return api_failure(response)


class Contact:

    api_path = 'contacts'

    def __init__(self, api, raw=None):
        self.api = api
        self.raw = raw

    @property
    def contact_id(self):
        return self.raw['id']

    @property
    def first_name(self):
        return self.raw['first_name']

    @property
    def last_name(self):
        return self.raw['last_name']

    @property
    def lists(self):
        return [ContactList(self.api, list_id=l['id'], status=l['status']) for l in self.raw['lists']]

    @property
    def email(self):
        return self.raw['email_addresses'][0]['email_address']

    def add_to_list(self, contact_list):

        if isinstance(contact_list, ContactList):
            clid = contact_list.list_id
        else:
            clid = str(contact_list)

        if self.is_member(contact_list):
            return api_fetched(self, None)

        new_state = self.raw.copy()
        new_state['lists'].append({'id': clid})

        response = self.api.put()

    def is_member(self, contact_list):
        if isinstance(contact_list, ContactList):
            clid = contact_list.list_id
        else:
            clid = str(contact_list)

        for contact_list in self.lists:
            if clid == contact_list.list_id:
                return True

        return False

    def delete(self):

        response = self.api.delete([self.api_path, self.contact_id])
        result = api_deleted(response)
        if result.success:
            self.raw = None

        return result


class ContactList:

    class Status:

        def __init__(self, status_str):
            pass

        HIDDEN = "HIDDEN"
        ACTIVE = "ACTIVE"
        REMOVED = "REMOVED"

    def __init__(self, api, list_id=None, name=None, status=None, created_date=None, modified_date=None, contact_count=None, raw=None):
        self.api = api
        self.list_id = list_id
        self.name = name
        self.status = status
        self.created_date = created_date
        self.modified_date = modified_date
        self.contact_count = contact_count
        self.raw = raw

    @classmethod
    def from_dict(cls, api, d):
        return cls(api, d['id'], d['name'], d['status'], d['created_date'], d['modified_date'], d['contact_count'], d)

    def members(self):
        pass

    def add(self, contact):
        pass

