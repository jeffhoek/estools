# -*- coding: UTF-8 -*-
# (c)2013 Mik Kocikowski, MIT License (http://opensource.org/licenses/MIT)
# https://github.com/mkocikowski/estools

import argparse
import logging
import sys
import itertools
import json

import requests

import estools.common.api
import estools.common.log
import estools.load.data

logger = logging.getLogger(__name__)


def args_parser():

    parser = argparse.ArgumentParser(description="Elasticsearch data loader (%s)" % (estools.__version__, ), epilog="")
    parser.add_argument('--host', type=str, action='store', default='localhost', help="es host; (%(default)s)")
    parser.add_argument('--port', type=int, action='store', default=9200, help="es port; (%(default)s)")
    parser.add_argument('--mode', type=str, action='store', choices=['line', 'file'], default='line', help="one document per line of per file; (%(default)s)")
    parser.add_argument('--wipe', action='store_true', help="if set, wipe the index before inserting data; (%(default)s)")
    parser.add_argument('--strict', action='store_true', help="if set, barf on malformed json; (%(default)s)")
    parser.add_argument('--idpath', action='store', type=str, default='id', help="name of the source field containing docment ids (%(default)s)")
    parser.add_argument('--doctype', action='store', type=str, default='doc', help="doctype (follows index name in es path); (%(default)s)")
    parser.add_argument('index', type=str, action='store', help='name of the target ES index')
    parser.add_argument('uris', metavar='URIs', nargs="*", type=str, action='store', default=['/dev/stdin'], help="read data from URI(s); (%(default)s)")

    return parser


def _mapping(doctype=None, idpath=None):
    mapping = {
        doctype: {
            "_id": {"path": idpath},
            "_size": {"enabled": True, "store": "yes"},
        },
    }
    return json.dumps(mapping)


def main():

    estools.common.log.set_up_logging(level=logging.INFO)
    args = args_parser().parse_args()
    session = requests.Session()

    if args.wipe:
        response = estools.common.api.delete_index(session=session, host=args.host, port=args.port, index=args.index)

    response = estools.common.api.create_index(
                    session=session,
                    host=args.host,
                    port=args.port,
                    index=args.index,
    )
    response = estools.common.api.put_mapping(
                    session=session,
                    host=args.host,
                    port=args.port,
                    index=args.index,
                    doctype=args.doctype,
                    mapping=_mapping(
                        doctype=args.doctype,
                        idpath=args.idpath,
                    ),
    )

    # this is needed because until a new index is opened it is no allocated,
    # and until it is allocated the settings cannot be updated, so in effect
    # it needs to be opened, closed, updated, and opened
    response = estools.common.api.open_index(session=session, host=args.host, port=args.port, index=args.index)

    # closes the index, updates the settings, reopens the index
    estools.common.api.set_ignore_malformed(session=session, host=args.host, port=args.port, index=args.index, ignore=not args.strict)

    format_f = estools.load.data.format
    documents = itertools.imap(format_f, estools.load.data.documents(URIs=args.uris, mode=args.mode))
    for n, doc in enumerate((d for d in documents if d)):
        response = estools.common.api.index_document(session=session, host=args.host, port=args.port, index=args.index, doctype=args.doctype, docid=None, data=doc)


if __name__ == "__main__":
    main()
    sys.exit(0)


