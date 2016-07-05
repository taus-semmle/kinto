import mock
import re

from kinto.tests.support import (BaseWebTest, unittest, get_user_headers)


class HistoryWebTest(BaseWebTest, unittest.TestCase):

    def get_app_settings(self, extra=None):
        settings = super(HistoryWebTest, self).get_app_settings(extra)
        settings['includes'] = 'kinto.plugins.history'
        return settings


class HelloViewTest(HistoryWebTest):

    def test_history_capability_if_enabled(self):
        resp = self.app.get('/')
        capabilities = resp.json['capabilities']
        self.assertIn('history', capabilities)


class HistoryViewTest(HistoryWebTest):

    def setUp(self):
        self.bucket_uri = '/buckets/test'
        self.app.put(self.bucket_uri, headers=self.headers)

        self.collection_uri = self.bucket_uri + '/collections/col'
        resp = self.app.put(self.collection_uri, headers=self.headers)
        self.collection = resp.json['data']

        self.group_uri = self.bucket_uri + '/groups/grp'
        body = {'data': {'members': ['elle']}}
        resp = self.app.put_json(self.group_uri, body, headers=self.headers)
        self.group = resp.json['data']

        self.record_uri = '/buckets/test/collections/col/records/rec'
        body = {'data': {'foo': 42}}
        resp = self.app.put_json(self.record_uri, body, headers=self.headers)
        self.record = resp.json['data']

        self.history_uri = '/buckets/test/history'

    def test_only_get_on_collection_is_allowed(self):
        self.app.put(self.history_uri, headers=self.headers, status=405)
        self.app.patch(self.history_uri, headers=self.headers, status=405)
        self.app.delete(self.history_uri, headers=self.headers, status=405)

    def test_only_collection_endpoint_is_available(self):
        resp = self.app.get(self.history_uri, headers=self.headers)
        entry = resp.json['data'][0]
        url = '%s/%s' % (self.bucket_uri, entry['id'])
        self.app.get(url, headers=self.headers, status=404)
        self.app.put(url, headers=self.headers, status=404)
        self.app.patch(url, headers=self.headers, status=404)
        self.app.delete(url, headers=self.headers, status=404)

    def test_tracks_user_and_date(self):
        resp = self.app.get(self.history_uri, headers=self.headers)
        entry = resp.json['data'][-1]
        assert entry['userid'].startswith('basicauth:3a0c56')
        assert re.match('^\d{4}\-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}',
                        entry['date'])

    #
    # Bucket
    #

    def test_history_contains_bucket_creation(self):
        resp = self.app.get(self.history_uri, headers=self.headers)
        entry = resp.json['data'][-1]
        assert entry['resource_name'] == 'bucket'
        assert entry['bucket_id'] == 'test'
        assert entry['action'] == 'create'
        assert entry['uri'] == '/buckets/test'

    def test_tracks_bucket_attributes_update(self):
        body = {'data': {'foo': 'baz'}}
        self.app.patch_json(self.bucket_uri, body,
                            headers=self.headers)
        resp = self.app.get(self.history_uri, headers=self.headers)
        entry = resp.json['data'][0]
        assert entry['action'] == 'update'
        assert entry['target']['data']['foo'] == 'baz'

    def test_tracks_bucket_permissions_update(self):
        body = {'permissions': {'read': ['admins']}}
        self.app.patch_json(self.bucket_uri, body,
                            headers=self.headers)
        resp = self.app.get(self.history_uri, headers=self.headers)
        entry = resp.json['data'][0]
        assert entry['action'] == 'update'
        assert entry['target']['permissions']['read'] == ['admins']

    def test_bucket_delete_destroys_history(self):
        self.app.delete(self.bucket_uri, headers=self.headers)
        self.app.get(self.history_uri, headers=self.headers, status=403)

    #
    # Collection
    #

    def test_tracks_collection_creation(self):
        resp = self.app.get(self.history_uri, headers=self.headers)
        entry = resp.json['data'][2]
        cid = self.collection['id']
        assert entry['resource_name'] == 'collection'
        assert entry['bucket_id'] == 'test'
        assert entry['collection_id'] == cid
        assert entry['action'] == 'create'
        assert entry['uri'] == '/buckets/test/collections/%s' % cid

    def test_tracks_collection_attributes_update(self):
        body = {'data': {'foo': 'baz'}}
        self.app.patch_json(self.collection_uri, body,
                            headers=self.headers)
        resp = self.app.get(self.history_uri, headers=self.headers)
        entry = resp.json['data'][0]
        assert entry['action'] == 'update'
        assert entry['target']['data']['foo'] == 'baz'

    def test_tracks_collection_permissions_update(self):
        body = {'permissions': {'read': ['admins']}}
        self.app.patch_json(self.collection_uri, body,
                            headers=self.headers)
        resp = self.app.get(self.history_uri, headers=self.headers)
        entry = resp.json['data'][0]
        assert entry['action'] == 'update'
        assert entry['target']['permissions']['read'] == ['admins']

    def test_tracks_collection_delete(self):
        self.app.delete(self.collection_uri, headers=self.headers)
        resp = self.app.get(self.history_uri, headers=self.headers)
        entry = resp.json['data'][0]
        assert entry['action'] == 'delete'
        assert entry['target']['data']['deleted'] is True

    #
    # Group
    #

    def test_tracks_group_creation(self):
        resp = self.app.get(self.history_uri, headers=self.headers)
        entry = resp.json['data'][1]
        assert entry['resource_name'] == 'group'
        assert entry['bucket_id'] == 'test'
        assert entry['group_id'] == self.group['id']
        assert entry['action'] == 'create'
        assert entry['uri'] == '/buckets/test/groups/%s' % self.group['id']

    def test_tracks_group_attributes_update(self):
        body = {'data': {'foo': 'baz', 'members': ['lui']}}
        self.app.patch_json(self.group_uri, body,
                            headers=self.headers)
        resp = self.app.get(self.history_uri, headers=self.headers)
        entry = resp.json['data'][0]
        assert entry['action'] == 'update'
        assert entry['target']['data']['foo'] == 'baz'
        assert entry['target']['data']['members'] == ['lui']

    def test_tracks_group_permissions_update(self):
        body = {'permissions': {'read': ['admins']}}
        self.app.patch_json(self.group_uri, body,
                            headers=self.headers)
        resp = self.app.get(self.history_uri, headers=self.headers)
        entry = resp.json['data'][0]
        assert entry['action'] == 'update'
        assert entry['target']['permissions']['read'] == ['admins']

    def test_tracks_group_delete(self):
        self.app.delete(self.group_uri, headers=self.headers)
        resp = self.app.get(self.history_uri, headers=self.headers)
        entry = resp.json['data'][0]
        assert entry['action'] == 'delete'
        assert entry['target']['data']['deleted'] is True

    #
    # Record
    #

    def test_tracks_record_creation(self):
        resp = self.app.get(self.history_uri, headers=self.headers)
        entry = resp.json['data'][0]
        cid = self.collection['id']
        rid = self.record['id']
        assert entry['resource_name'] == 'record'
        assert entry['bucket_id'] == 'test'
        assert entry['collection_id'] == cid
        assert entry['record_id'] == rid
        assert entry['action'] == 'create'
        assert entry['uri'] == '/buckets/test/collections/%s/records/%s' % (cid, rid)  # NOQA
        assert entry['target']['data']['foo'] == 42
        assert entry['target']['permissions']['write'][0].startswith('basicauth:')  # NOQA

    def test_tracks_record_attributes_update(self):
        resp = self.app.patch_json(self.record_uri, {'data': {'foo': 'baz'}},
                                   headers=self.headers)
        resp = self.app.get(self.history_uri, headers=self.headers)
        entry = resp.json['data'][0]
        assert entry['action'] == 'update'
        assert entry['target']['data']['foo'] == 'baz'

    def test_tracks_record_permissions_update(self):
        body = {'permissions': {'read': ['admins']}}
        resp = self.app.patch_json(self.record_uri, body,
                                   headers=self.headers)
        resp = self.app.get(self.history_uri, headers=self.headers)
        entry = resp.json['data'][0]
        assert entry['action'] == 'update'
        assert entry['target']['permissions']['read'] == ['admins']

    def test_tracks_record_delete(self):
        resp = self.app.delete(self.record_uri, headers=self.headers)
        resp = self.app.get(self.history_uri, headers=self.headers)
        entry = resp.json['data'][0]
        assert entry['action'] == 'delete'
        assert entry['target']['data']['deleted'] is True


class FilteringTest(HistoryWebTest):

    def setUp(self):
        self.app.put('/buckets/bid', headers=self.headers)
        self.app.put('/buckets/bid/collections/cid',
                     headers=self.headers)
        body = {'data': {'foo': 42}}
        self.app.put_json('/buckets/bid/collections/cid/records/rid',
                          body,
                          headers=self.headers)
        body = {'data': {'foo': 'bar'}}
        self.app.patch_json('/buckets/bid/collections/cid/records/rid',
                            body,
                            headers=self.headers)
        self.app.delete('/buckets/bid/collections/cid/records/rid',
                        headers=self.headers)

    def test_filter_by_action(self):
        resp = self.app.get('/buckets/bid/history?action=delete',
                            headers=self.headers)
        assert len(resp.json['data']) == 1

    def test_filter_by_resource(self):
        resp = self.app.get('/buckets/bid/history?resource_name=bucket',
                            headers=self.headers)
        assert len(resp.json['data']) == 1

    def test_filter_by_uri(self):
        uri = '/buckets/bid/collections/cid/records/rid'
        resp = self.app.get('/buckets/bid/history?uri=%s' % uri,
                            headers=self.headers)
        assert len(resp.json['data']) == 3  # create / update / delete

    def test_filter_by_collection(self):
        uri = '/buckets/bid/history?bucket_id=bid&collection_id=cid'
        resp = self.app.get(uri,
                            headers=self.headers)
        assert len(resp.json['data']) == 4

    def test_limit_results(self):
        resp = self.app.get('/buckets/bid/history?_limit=2',
                            headers=self.headers)
        assert len(resp.json['data']) == 2
        assert 'Next-Page' in resp.headers

    def test_filter_returned_fields(self):
        resp = self.app.get('/buckets/bid/history?_fields=uri,action',
                            headers=self.headers)
        assert sorted(resp.json['data'][0].keys()) == ['action', 'id',
                                                       'last_modified', 'uri']


class BulkTest(HistoryWebTest):
    def setUp(self):
        body = {
            'defaults': {
                'method': 'POST',
                'path': '/buckets/bid/collections/cid/records',
            },
            'requests': [{
                'path': '/buckets/bid',
                'method': 'PUT'
            }, {
                'path': '/buckets/bid/collections',
                'body': {'data': {'id': 'cid'}}
            }, {
                'body': {'data': {'id': 'a', 'attr': 1}},
            }, {
                'body': {'data': {'id': 'b', 'attr': 2}},
            }, {
                'body': {'data': {'id': 'c', 'attr': 3}}
            }]
        }
        self.app.post_json('/batch', body, headers=self.headers)

    def test_post_on_collection(self):
        resp = self.app.get('/buckets/bid/history', headers=self.headers)
        entries = resp.json['data']
        assert len(entries) == 5
        assert entries[0]['uri'] == '/buckets/bid/collections/cid/records/c'
        assert entries[-2]['uri'] == '/buckets/bid/collections/cid'


class PermissionsTest(HistoryWebTest):

    def setUp(self):
        self.alice_headers = get_user_headers('alice:')
        self.julia_headers = get_user_headers('julia:')
        alice_principal = 'basicauth:845a151f1fbb0063738943a4531f8b7ef521fa488ed5ac7d077aa7ee1f349ef7'  # NOQA
        julia_principal = 'basicauth:2f5fcddb299319097b9ae72f609d071d99aaf46ef9c3bc82bcc0212d14e35c4f'  # NOQA
        bucket = {
            'permissions': {
                'read': [alice_principal]
            }
        }
        collection = {
            'permissions': {
                'read': [julia_principal]
            }
        }
        record = {
            'permissions': {
                'read': ['system.Authenticated'],
                'write': [alice_principal],
            }
        }
        self.app.put('/buckets/author-only',
                     headers=self.headers)
        self.app.put_json('/buckets/test',
                          bucket,
                          headers=self.headers)
        self.app.put_json('/buckets/test/groups/admins',
                          {'data': {'members': []}},
                          headers=self.headers)
        self.app.put_json('/buckets/test/collections/with-alice',
                          collection,
                          headers=self.headers)
        self.app.put_json('/buckets/test/collections/without-julia',
                          collection,
                          headers=self.headers)
        self.app.post_json('/buckets/test/collections/with-alice/records',
                           record,
                           headers=self.headers)

    def test_author_can_read_everything(self):
        resp = self.app.get('/buckets/test/history',
                            headers=self.headers)
        entries = resp.json['data']
        assert len(entries) == 5

    def test_read_permission_can_be_given_to_anybody_via_settings(self):
        with mock.patch.dict(self.app.app.registry.settings,
                             [('history_read_principals', 'system.Everyone')]):
            resp = self.app.get('/buckets/test/history',
                                headers=get_user_headers('tartan:pion'))
            entries = resp.json['data']
            assert len(entries) == 5

    def test_alice_can_read_everything_in_test_bucket(self):
        resp = self.app.get('/buckets/test/history',
                            headers=self.alice_headers)
        entries = resp.json['data']
        assert len(entries) == 5

        self.app.get('/buckets/author-only/history',
                     headers=self.alice_headers,
                     status=403)

    # def test_julia_can_read_everything_in_collection(self):
    #     resp = self.app.get('/buckets/test/history',
    #                         headers=self.julia_headers)
    #     entries = resp.json['data']
    #     assert len(entries) == 2

    # def test_any_authenticated_can_read_about_record(self):
    #     resp = self.app.get('/buckets/test/history',
    #                         headers=get_user_headers('jack:'))
    #     entries = resp.json['data']
    #     assert len(entries) == 1

    # def test_new_entries_are_not_readable_if_permission_is_removed(self):
    #     pass
