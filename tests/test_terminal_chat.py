import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from webapp import create_app
from terminal_chat import TownChat

class TerminalChatTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)/'town.db'
        self.app = create_app({'TESTING':True,'DATABASE':str(self.path),'SECRET_KEY':'test-secret'})
        self.client = self.app.test_client()
        self.client.get('/')
        with self.client.session_transaction() as s: csrf=s['csrf']
        self.client.post('/register',data={'username':'TownHuman','password':'a-long-test-password','csrf':csrf})
        self.chat = TownChat(self.path)
        self.chat.login('TownHuman','a-long-test-password')

    def tearDown(self): self.tmp.cleanup()

    def test_say_reaches_existing_resident_and_browser(self):
        before=self.app.extensions['town'].load()
        target=before.lonks[0]
        with contextlib.redirect_stdout(io.StringIO()):
            self.chat.command('say '+target.id+' moonmoss hello')
        after=self.app.extensions['town'].load()
        self.assertEqual(after.tick,before.tick)
        self.assertEqual([l.id for l in after.lonks],[l.id for l in before.lonks])
        self.assertEqual(after.lonks[0].vocabulary['moonmoss'],1)
        post=after.lonkspace_feed[-1]
        self.assertEqual(post['author'],'TownHuman')
        self.assertEqual(post['comments'][-1]['author_id'],target.id)
        page=self.client.get('/thread/'+post['id']).get_data(as_text=True)
        self.assertIn('moonmoss',page)
        self.assertIn(target.name,page)

    def test_missing_database_never_creates_world(self):
        path=Path(self.tmp.name)/'missing.db'
        with self.assertRaises(ValueError): TownChat(path)
        self.assertFalse(path.exists())

    def test_wrong_password_and_no_login_cannot_write(self):
        chat=TownChat(self.path)
        with self.assertRaises(ValueError):chat.login('TownHuman','incorrect-password')
        with self.assertRaises(ValueError):chat.command('post Hello | world')

    def test_cooldown_shared_with_website(self):
        self.chat.command('post Hello | hello neighbors')
        with self.assertRaises(ValueError):self.chat.command('post Again | hello')
        with self.client.session_transaction() as s: csrf=s['csrf']
        self.assertEqual(self.client.post('/post',data={'csrf':csrf,'title':'Again','body':'hello'}).status_code,429)

    def test_duplicate_names_do_not_pick_arbitrary_resident(self):
        with self.app.extensions['town'].world_change() as world:
            world.lonks[0].name = world.lonks[1].name = 'Twins'
        count=len(self.chat.store.load().lonkspace_feed)
        with self.assertRaisesRegex(ValueError,'Several residents'):
            self.chat.command('say Twins hello')
        self.assertEqual(len(self.chat.store.load().lonkspace_feed), count)

    def test_reply_and_read_commands_share_existing_thread(self):
        with self.app.extensions['town'].world_change() as world:
            post=world.add_post('SYSTEM','A shared thread',author_type='system')
            post_id=post['id']
        self.chat.command('reply '+post_id+' moonmoss')
        self.assertIn('moonmoss',self.client.get('/thread/'+post_id).get_data(as_text=True))
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.chat.command('thread '+post_id)
            self.chat.command('feed')
            self.chat.command('status')
            self.chat.command('inspect '+self.chat.store.load().lonks[0].id)
        self.assertIn('moonmoss',output.getvalue())
        self.assertEqual(self.chat.store.load().tick,0)

    def test_failed_login_attempts_persist(self):
        chat=TownChat(self.path)
        for _ in range(10):
            with self.assertRaises(ValueError):chat.login('TownHuman','wrong-password')
        with self.assertRaisesRegex(ValueError,'Too many'):
            chat.login('TownHuman','a-long-test-password')

if __name__=='__main__': unittest.main()
