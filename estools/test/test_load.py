# -*- coding: UTF-8 -*-
# (c)2013 Mik Kocikowski, MIT License (http://opensource.org/licenses/MIT)
# https://github.com/mkocikowski/esbench


import unittest
import logging
import os

import requests

import estools.common.log as log
import estools.load.load as load


class LoadClientTest(unittest.TestCase):


    def setUp(self):

        self._tmp_put_mapping = load.api.put_mapping
        load.api.put_mapping = lambda **kvargs: kvargs

        self._tmp_create_index = load.api.create_index
        load.api.create_index = lambda **kvargs: kvargs


    def tearDown(self):

        load.api.put_mapping = self._tmp_put_mapping
        load.api.create_index = self._tmp_create_index


    def test_create_index(self):

        tests = (
            (
                "index1 doctype1",
                None,
                {'settings': {'number_of_replicas': 0}},
            ),
            (
                "index1 doctype1 --shards=5",
                None,
                {'settings': {'number_of_replicas': 0, 'number_of_shards': 5}},
            ),
            (
                "index1 doctype1 --shards=5",
                {'foo': 'bar'},
                {'foo': 'bar', 'settings': {'number_of_replicas': 0, 'number_of_shards': 5}},
            ),
            (
                "index1 doctype1",
                {'settings': {'number_of_replicas': 3, 'number_of_shards': 3}},
                {'settings': {'number_of_replicas': 0, 'number_of_shards': 3}},
            ),
        )

        for test in tests:
            params = load.args_parser().parse_args(test[0].split())
            result = load.create_index(params=params, settings=test[1])
            self.assertEqual(result, test[2])


    def test_put_mapping(self):

        tests = (
            (
                "index1 doctype1",
                None,
                {},
            ),
#            (
#                "index1 doctype1 --id-field='foo.bar'",
#                None,
#                {'_id': {'path': "'foo.bar'"}},
#            ),
#            (
#                "index1 doctype1",
#                {'foo': 'bar'},
#                {'foo': 'bar'},
#            ),
#            (
#                "index1 doctype1 --id-field='foo.bar'",
#                {'foo': 'bar'},
#                {'foo': 'bar', '_id': {'path': "'foo.bar'"}},
#            ),
        )

        for test in tests:
            params = load.args_parser().parse_args(test[0].split())
            result = load.put_mapping(params=params, mapping=test[1])
            self.assertEqual(result, test[2])


    def test_load_json(self):

        self.assertIsNone(load.load_json())
        self.assertIsNone(load.load_json(file_name=""))
        self.assertRaises(IOError, load.load_json, file_name="/")
        self.assertRaises(IOError, load.load_json, file_name="nosuchfile.json")
        self.assertRaises(ValueError, load.load_json, file_name=__file__) # bad json


    def test_chunker(self):

        chunks = load.chunker(iterable=range(5), chunklen=2)
        self.assertEqual(
            [list(c) for c in chunks],
            [[0, 1], [2, 3], [4]]
        )
        chunks = load.chunker(iterable="abcde", chunklen=2)
        self.assertEqual(
            [list(c) for c in chunks],
            [['a', 'b'], ['c', 'd'], ['e']]
        )

        self.assertRaises(TypeError, load.chunker, iterable=1, chunklen=2)

        chunks = load.chunker(iterable="abcde") # no chunklen
        with self.assertRaises(TypeError):
            c = [list(c) for c in chunks]


@unittest.skipIf(os.environ.get('SHORT', False), "invoke with SHORT=1 to skip functional test against es instance")
class FunctionalTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.session = requests.Session()


    @classmethod
    def tearDownClass(cls):
        requests.delete(url="http://127.0.0.1:9200/estools-test")


    def setUp(self):
        requests.delete(url="http://127.0.0.1:9200/estools-test")


    def test_functional(self):

        tests = (
            ("estools-test doc --wipe --shards=3 --silent", ['{"foo": 1}', '{"foo": 2}'], 2, 20, 0),
            ("estools-test doc --silent", ['{"foo": 1}', '{"foo": 2}'], 2, 20, 0),
            ("estools-test doc --wipe --alias=estools-test-alias --silent", ['{"foo": 1}', '{"foo": 2}'], 2, 20, 0),
            ("estools-test doc --silent", ['{"foo": 1}', '{"foo": "bar"}'], 2, 24, 0), # not counting errors
            ("estools-test doc --count-errors --silent", ['{"foo": 1}', '{"foo": "bar"}'], 2, 24, 1),
        )

        for test in tests:
            params = load.args_parser().parse_args(test[0].split())
            doc_count, size_b, error_count = load.run(params=params, session=self.session, input_i=test[1])
            self.assertEqual(doc_count, test[2])
            self.assertEqual(size_b, test[3])
            self.assertEqual(error_count, test[4])


    def test_abort(self):
        # issue #22: on abort don't close old index or alias new one

        try:
            params = load.args_parser().parse_args("estools-test doc --wipe --alias=estools-test-alias --silent".split())
            docs = ['{"foo": 1}', '{"foo": 2}']
            aliased = {"executed": False}

            def set_alias(params=None):
                aliased['executed'] = True
            _tmp_set_alias = load.api.set_alias
            load.api.set_alias = set_alias

            load.run(params=params, session=self.session, input_i=docs)
            self.assertTrue(aliased['executed'])

            def index(params=None, records=None):
                raise KeyboardInterrupt("simulating user interrupt")
            _tmp_index = load.index
            load.index = index
            aliased['executed'] = False
            self.assertRaises(KeyboardInterrupt, load.run, params=params, session=self.session, input_i=docs)
            self.assertFalse(aliased['executed'])

        finally:
            load.api.set_alias = _tmp_set_alias
            load.index = _tmp_index


if __name__ == "__main__":

    log.set_up_logging(level=logging.DEBUG)
    unittest.main()

