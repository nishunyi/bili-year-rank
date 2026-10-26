import json
from pathlib import Path
import tempfile
import unittest

from bili_rank import (ApiError, Cancelled, Client, RiskStop, Store, bounds, collect,
                       count, export, normalize, wbi_query)


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / 'test.sqlite3')
        self.start, self.end = bounds(2018)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def item(self, **changes):
        return {'bvid': 'BV14b411w7zx', 'aid': 35311013, 'title': '<em>视频</em>',
                'author': 'UP', 'pubdate': self.start, 'play': 200, **changes}

    def test_beijing_year_boundaries_and_bad_data(self):
        self.assertEqual(self.start, 1514736000)
        self.assertEqual(self.end, 1546272000)
        self.assertIsNotNone(normalize(self.item(), 2018))
        self.assertIsNotNone(normalize(self.item(pubdate=self.end-1), 2018))
        for changes in ({'pubdate': self.start-1}, {'pubdate': self.end}, {'bvid': '../bad'},
                        {'play': '1.2万'}, {'play': -1}, {'pubdate': None}):
            self.assertIsNone(normalize(self.item(**changes), 2018))

    def test_deduplication_and_latest_stat_source(self):
        self.store.ingest([self.item()], 2018, '音乐')
        self.store.ingest([self.item(play=300)], 2018, '2018')
        rows = self.store.rows(2018)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['play'], 300)
        self.assertEqual(rows[0]['title'], '视频')
        self.assertIn('音乐', rows[0]['keywords'])
        self.store.verify(rows[0]['bvid'], {'view': 450})
        self.assertEqual(self.store.rows(2018)[0]['play'], 450)
        self.store.db.execute("UPDATE videos SET collected_at='2099-01-01T00:00:00+08:00',search_play=500")
        self.assertEqual(self.store.rows(2018)[0]['play'], 500)

    def test_export_escapes_content_and_discloses_scope(self):
        self.store.ingest([self.item(title='<em>&lt;script&gt;YEAR&lt;/script&gt;</em>', author='=1+1')], 2018, '测试')
        csv_path, html_path = export(self.store, 2018, 100, {}, Path(self.temp.name) / 'out')
        content = html_path.read_text(encoding='utf-8')
        self.assertIn('&lt;script&gt;YEAR&lt;/script&gt;', content)
        self.assertNotIn('<script>YEAR</script>', content)
        self.assertIn("'=1+1", csv_path.read_text(encoding='utf-8-sig'))
        self.assertFalse(json.loads(html_path.with_suffix('.json').read_text(encoding='utf-8'))['metadata']['sitewide_complete'])

    def test_pagination_repeat_guard_and_cache(self):
        class FakeClient:
            import threading
            cancel = threading.Event()
            calls = 0
            def search(fake, *args):
                fake.calls += 1
                return {'result': [self.item()], 'numPages': 5}
        client = FakeClient()
        meta = collect(client, self.store, 2018, ['词'], 5, 30, 6, lambda _: None)
        self.assertEqual(client.calls, 2)
        self.assertEqual(len(meta['pages']), 1)
        collect(client, self.store, 2018, ['词'], 1, 30, 6, lambda _: None)
        self.assertEqual(client.calls, 2)

    def test_risk_stop_preserves_progress_metadata(self):
        class FakeClient:
            import threading
            cancel = threading.Event()
            def search(fake, keyword, year, page, size):
                if page == 2:
                    raise RiskStop('HTTP 412')
                return {'result': [self.item()], 'numPages': 5}
        meta = {}
        with self.assertRaises(RiskStop):
            collect(FakeClient(), self.store, 2018, ['词'], 5, 30, 6, lambda _: None, meta)
        self.assertEqual(len(self.store.rows(2018)), 1)
        self.assertEqual(len(meta['pages']), 1)

    def test_no_empty_keyword_or_imprecise_count(self):
        with self.assertRaises(ValueError):
            Client().search('', 2018, 1, 30)
        self.assertIsNone(count('500万'))
        self.assertIsNone(count(True))
        self.assertEqual(count('12345'), 12345)


if __name__ == '__main__':
    unittest.main()
