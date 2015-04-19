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

    def put(self, api_path, data, query_params=None):
        return self.s.put(self.api_endpoint(api_path),
                          json=data,
                          params=query_params)

    def delete(self, api_path):
        return self.s.delete(self.api_endpoint(api_path))

    def lists(self):
        response = self.get("lists")

        if 200 == response.status_code:
            instance = [ContactList(self, raw) for raw in response.json()]
            return api_fetched(instance, response)
        else:
            return api_failure(response)

    def get_list(self, list_id):
        response = self.get('lists/'+str(list_id))

        if 200 == response.status_code:
            return ContactList(self, response.json())
        else:
            return None

    def create_list(self, name, status):
        data = dict(name=name, status=status)
        response = self.post('lists', data)

        if 201 == response.status_code:
            return api_creation(ContactList(self, response.json()), response)
        elif 409 == response.status_code:
            return api_acknowledged(response)
        else:
            return api_failure(response)

    @classmethod
    def action_by_query_param(cls, created_by_visitor=True):
        if created_by_visitor:
            return {'action_by': 'ACTION_BY_VISITOR'}
        else:
            return {'action_by': 'ACTION_BY_OWNER'}

    def create_contact(self, email, contact_list_ids, created_by_visitor=True, data=None, **kwargs):

        if data is None:
            data = {}

        user_data = dict(email_addresses=[{'email_address': email}],
                    lists=[{'id': i} for i in contact_list_ids])
        user_data.update(data)
        user_data.update(**kwargs)

        response = self.post('contacts', user_data, self.action_by_query_param(created_by_visitor))

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

    @classmethod
    def resource_ids(cls, ids):
        # We want to consume either single values or lists of values, so ids may be "foo" or ["foo", ContactList(id="bar")]

        def get_rid(obj):
            try:
                return obj.resource_id
            except AttributeError:
                return str(obj)

        if isinstance(ids, list):  # string is iterable, and CC ids are strings so I'm not sure what they best test is
            return list(map(get_rid, ids))
        else:
            return [get_rid(ids)]


class ConstantContactResource:

    @property
    def resource_id(self):
        raise NotImplemented


class Contact(ConstantContactResource):

    api_path = 'contacts'

    def __init__(self, api, raw=None):
        self.api = api
        self.raw = raw

    @property
    def contact_id(self):
        return self.raw['id']

    @property
    def resource_id(self):
        return self.contact_id

    @property
    def first_name(self):
        return self.raw['first_name']

    @property
    def last_name(self):
        return self.raw['last_name']

    @property
    def lists(self):
        return [ContactList(self.api, l) for l in self.raw['lists']]

    @property
    def email(self):
        return self.raw['email_addresses'][0]['email_address']

    def subscribe(self, contact_list, visitor_opt_in=True):

        desired_subscriptions = set(self.api.resource_ids(contact_list))
        current_subscriptions = set(self.api.resource_ids(self.lists))

        if not desired_subscriptions - current_subscriptions:
            return api_fetched(self, None)

        new_state = self.raw.copy()
        new_subscriptions = list(current_subscriptions | desired_subscriptions)
        new_state['lists'] = [{'id': clid} for clid in new_subscriptions]

        response = self.api.put([self.api_path, self.contact_id], new_state, self.api.action_by_query_param(visitor_opt_in))
        if 200 == response.status_code:
            return api_creation(Contact(self.api, new_state), response)
        else:
            return api_failure(response)

    def unsubscribe(self, contact_list):

        desired_removals = set(self.api.resource_ids(contact_list))
        current_subscriptions = set(self.api.resource_ids(self.lists))

        if not desired_removals & current_subscriptions:
            return api_fetched(self, None)

        new_state = self.raw.copy()
        new_subscriptions = list(current_subscriptions - desired_removals)
        new_state['lists'] = [{'id': clid} for clid in new_subscriptions]

        response = self.api.put([self.api_path, self.contact_id], new_state)
        if 200 == response.status_code:
            return api_creation(Contact(self.api, new_state), response)
        else:
            return api_failure(response)

    def is_member(self, contact_list_id):
        return contact_list_id in self.api.resource_ids(self.lists)

    def delete(self):

        response = self.api.delete([self.api_path, self.contact_id])
        result = api_deleted(response)
        if result.success:
            self.raw = None

        return result


class ContactList(ConstantContactResource):

    class Status:

        HIDDEN = "HIDDEN"
        ACTIVE = "ACTIVE"
        REMOVED = "REMOVED"

    def __init__(self, api, raw=None):
        self.api = api
        self.raw = raw

    @property
    def resource_id(self):
        return self.list_id

    @property
    def list_id(self):
        return self.raw['id']

    @property
    def name(self):
        return self.raw['name']

    @property
    def status(self):
        return self.raw['status']

    @property
    def created_date(self):
        return self.raw['created_date']

    @property
    def modified_date(self):
        return self.raw['modified_date']

    @property
    def contact_count(self):
        return self.raw['contact_count']




