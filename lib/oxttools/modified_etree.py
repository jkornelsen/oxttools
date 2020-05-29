#!/usr/bin/python

import xml.etree.ElementTree as et

namespaces_read = dict()  # definitions that were read from the input file

class CommentedTreeBuilder(et.TreeBuilder):
    def comment(self, data):
        self.start(et.Comment, {})
        self.data(data)
        self.end(et.Comment)

def register_all_namespaces(source):
    namespaces = dict([node for _, node in et.iterparse(source, events=['start-ns'])])
    for key, val in namespaces.items():
        #print("ns '{}' = {}".format(key, val))
        et.register_namespace(key, val)
        namespaces_read[key] = val
    if ('' in namespaces):
        # in case one of the namespace definitions overrode the default
        et.register_namespace('', namespaces[''])
        namespaces_read[''] = namespaces['']

def parse(source):
    register_all_namespaces(source)
    parser = et.XMLParser(target=CommentedTreeBuilder())
    return et.parse(source, parser)

