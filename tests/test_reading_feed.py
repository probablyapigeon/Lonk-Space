import unittest
from unittest.mock import patch
import test_personal_towns as personal
from town_runtime import TownRuntime

ITEM = {'title':'Mushroom', 'text':'Fungi grow from spores.',
        'url':'https://en.wikipedia.org/wiki/Mushroom', 'kind':'encyclopedia'}

class ReadingFeedTests(unittest.TestCase):
    setUp = personal.PersonalTownTests.setUp
    tearDown = personal.PersonalTownTests.tearDown
    post = personal.PersonalTownTests.post
    register = personal.PersonalTownTests.register

    def queue(self, topic='Mushroom'):
        self.assertEqual(self.post(self.a,'/queue/surf', {'resident':self.own.load().lonks[0].id,
                         'source':'wiki','topic':topic}).status_code,302)

    def test_success_visible_in_activity_and_private_feed_with_source(self):
        self.queue()
        with patch('town_runtime.CachedReader.fetch',return_value=[ITEM]):
            TownRuntime(self.own).run_command()
        world=self.own.load()
        receipt=world.lonkspace_feed[-1]
        self.assertEqual(receipt.get('reading_source'), 'wiki')
        self.assertEqual(receipt.get('source_url'), ITEM['url'])
        self.assertIn(ITEM['text'],receipt['body'])
        self.assertIn(ITEM['url'].encode(),self.a.get('/feed').data)
        self.assertIn(b'Mushroom',self.a.get('/activity').data)
        self.assertNotIn(ITEM['text'].encode(),self.b.get('/feed').data)
        self.assertNotIn(ITEM['text'].encode(),self.b.get('/square').data)

    def test_live_activity_payload_and_hidden_reading(self):
        self.queue()
        with patch('town_runtime.CachedReader.fetch',return_value=[ITEM]):
            TownRuntime(self.own).run_command()
        data=self.a.get('/activity').get_json()
        self.assertEqual(data['readings'][0]['url'],ITEM['url'])
        self.assertEqual(self.b.get('/activity').get_json()['readings'],[])
        post_id=data['readings'][0]['id']
        self.assertEqual(self.post(self.a,'/hide/'+post_id).status_code,302)
        self.assertEqual(self.a.get('/activity').get_json()['readings'],[])

    def test_duplicate_and_empty_extract_do_not_make_success_posts(self):
        runtime=TownRuntime(self.own)
        self.queue()
        with patch.object(runtime.reader,'fetch',return_value=[ITEM]):
            runtime.run_command()
        before=len(self.own.load().lonkspace_feed)
        self.queue()
        with patch.object(runtime.reader,'fetch',side_effect=AssertionError('Use cache')):
            runtime.run_command()
        self.assertEqual(len(self.own.load().lonkspace_feed),before)
        with self.own.connect() as db:
            self.assertEqual(db.execute('SELECT state FROM commands ORDER BY id DESC LIMIT 1').fetchone()[0],'no_change')
        runtime=TownRuntime(self.own)
        self.queue('Empty')
        with patch.object(runtime.reader,'fetch',return_value=[dict(ITEM,text='')]):
            runtime.run_command()
        self.assertEqual(len(self.own.load().lonkspace_feed),before)

    def test_http_error_is_clear_and_does_not_teach_or_post(self):
        import requests
        self.queue()
        response=requests.Response();response.status_code=404
        with patch('town_runtime.CachedReader.fetch',side_effect=requests.HTTPError(response=response)):
            TownRuntime(self.own).run_command()
        data=self.a.get('/activity').get_json()
        self.assertIn('HTTP 404',str(data['logs']))
        self.assertIn('exact article title',str(data['logs']))
        self.assertFalse(data['readings'])
        self.assertFalse(hasattr(self.own.load().lonks[0],'reading_history'))
        with self.own.connect() as db:
            self.assertEqual(db.execute('SELECT state FROM commands ORDER BY id DESC LIMIT 1').fetchone()[0],'failed')

    def test_new_topic_during_cooldown_explains_wait_without_fetching(self):
        runtime=TownRuntime(self.own)
        self.queue()
        with patch.object(runtime.reader,'fetch',return_value=[ITEM]):
            runtime.run_command()
        self.queue('Black hole')
        with patch.object(runtime.reader,'fetch',side_effect=AssertionError('Respect cooldown')):
            runtime.run_command()
        data=self.a.get('/activity').get_json()
        self.assertIn('seconds before requesting a new topic',str(data['logs']))
        self.assertEqual(len(data['readings']),1)
