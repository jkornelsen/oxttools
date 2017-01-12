#!/usr/bin/python

import lxml.etree as et
import codecs, re, copy

tmpl = "{uri://nrsi.sil.org/template/0.1}"
tmpla = "{uri://nrsi.sil.org/template_attributes/0.1}"

class IterDict(object) :
    def __init__(self) :
        self.keys = {}
        self.values = []
        self.indices = []
        self.atstart = True

    def __setitem__(self, key, value) :
        if isinstance(value, basestring) or not hasattr(value, 'len') :
            value = [value]
        self.keys[key] = len(self.values)
        self.values.append(value)
        self.indices.append(0)

    def asdict(self) :
        res = {}
        for k, i in self.keys.items() :
            res[k] = str(self.values[i][self.indices[i]])
        return res

    def __iter__(self) :
        return self

    def next(self) :
        if self.atstart :
            self.atstart = False
            return self.asdict()
        for i in range(len(self.indices)) :
            if self.indices[i] + 1 < len(self.values[i]) : 
                self.indices[i] += 1
                return self.asdict()
        raise StopIteration

def asstr(v) :
    if isinstance(v, basestring) : return v
    elif isinstance(v, et._Element) : return v.text
    elif len(v) == 0 : return ''
    v = v[0]
    if isinstance(v, et._Element) :
        return v.text
    return v

class Templater(object) :

    def __init__(self) :
        self.vars = {}
        self.docs = {}
        self.fns = copy.copy(self.extensions)

    def define(self, name, val) :
        self.vars[name] = val

    def addfn(self, ns, name, fn) :
        self.fns[(ns, name)] = fn

    def parse(self, fname) :
        self.doc = et.parse(fname)

    def __str__(self) :
        return et.tounicode(self.doc)

    def process(self, root = None, context = None, nest = False) :
        if nest :
            oldvars = self.vars.copy()
        if root is None :
            root = self.doc.getroot()
        if context is None :
            context = root
        for c in list(root) :
            if str(c.tag).startswith(tmpl) :
                name = c.tag[len(tmpl):]
                if name == 'variable' :
                    self.processattrib(c, context)
                    k = c.attrib[tmpl+'name']
                    if not tmpl+"fallback" in c.attrib or not k in self.vars :
                        v = self.xpath(c.text, context, c)
                        if isinstance(v, (basestring, list)) and len(v) == 0 :
                            v = c.attrib.get(tmpl+'default', '')
                        self.vars[k] = v
                elif name == 'value' :
                    self.processattrib(c, context)
                    v = self.xpath(c.attrib[tmpl+"path"], context, c)
                    t = asstr(v)
                    root.text = t if tmpl+"cdata" not in c.attrib or t == '' else et.CDATA(t)
                elif name == 'if' :
                    self.processattrib(c, context)
                    v = self.xpath(c.attrib[tmpl+"path"], context, c)
                    if v :
                        index = root.index(c)
                        node = self.process(root = c, context = context, nest=True)
                        if node is None : node = []
                        for n in list(node) :
                            node.remove(n)
                            root.insert(index, n)
                            index += 1
                elif name == 'context' :
                    self.processattrib(c, context)
                    index = root.index(c)
                    node = self.process(root = c, context = self.xpath(c.attrib[tmpl+"path"], context, c), nest=True)
                    if node is None : node = []
                    for n in list(node) :
                        node.remove(n)
                        root.insert(index, n)
                        index += 1
                elif name == 'foreach' :
                    uppervars = self.vars.copy()
                    index = root.index(c)
                    itervars = IterDict()
                    nodes = []
                    for k, v in c.attrib.items() :
                        if k.startswith(tmpla) :
                            newk = k[len(tmpla):]
                            newv = self.xpath(v, context, c)
                            itervars[newk] = newv
                    for v in itervars :
                        self.vars = uppervars.copy()
                        self.vars.update(v)
                        if tmpl + "path" in c.attrib:
                            pathnodes = self.xpath(c.attrib[tmpl+"path"], context, c)
                            if not isinstance(pathnodes, list) :
                                pathnodes = [pathnodes]
                        else :
                            pathnodes = [context]
                        for n in pathnodes :
                            x = copy.deepcopy(c)
                            nodes.append(self.process(root = x, context = n, nest = True))
                    for n in nodes :
                        if n is None : continue
                        for r in n :
                            n.remove(r)
                            root.insert(index, r)
                            index += 1
                root.remove(c)
            elif len(c) :
                self.processattrib(c, context)
                self.process(c, context=context, nest=False)
        if nest :
            self.vars = oldvars
        return root

    def processattrib(self, node, context) :
        for k, v in node.attrib.items() :
            if k.startswith(tmpla) :
                newk = k[len(tmpla):]
                for t in node.attrib.keys() :
                    if t.endswith(newk) and (len(t) == len(newk) or (t[-len(newk)-1] == '}' and t[:-len(newk)] != tmpla)) :
                        newk = t[:-len(newk)] + newk
                        break
                newv = asstr(self.xpath(v, context, node))
                if newv != '' :
                    node.set(newk, newv)
                del node.attrib[k]

    def xpath(self, path, context, base) :
        # print path, self.vars
        try :
            res = context.xpath(path, extensions = self.fns, smart_strings=False, **self.vars)
        except Exception as e :
            raise et.XPathEvalError(e.message + ":\n" + path + ", at line " + str(base.sourceline))
        if not isinstance(res, basestring) and len(res) == 1 :
            res = res[0]
        return res

    @staticmethod
    def fn_doc(context, txt) :
        txt = asstr(txt)
        if txt not in self.docs :
            self.docs[txt] = et.parse(txt)
        return self.docs[txt].getroot()

    @staticmethod
    def fn_firstword(context, txt) :
        txt = asstr(txt)
        if txt == '' : return txt
        return txt.split()[0]

    @staticmethod
    def fn_findsep(context, val, index) :
        val = asstr(val)
        if val == '' : return val
        return val.split()[int(index)]

    @staticmethod
    def fn_replace(context, txt, regexp, repl) :
        txt = asstr(txt)
        repl = asstr(repl)
        try :
            res = re.sub(regexp, repl, txt)
        except Exception as e :
            raise et.XPathEvalError(e.message + ": txt = {}, regexp = {}, repl = {}".format(txt, regexp, repl))
        return res

    @staticmethod
    def fn_dateformat(context, txt, *formats) :
        """Converts LDML date/time format letters to LibreOffice corresponding codes"""
        txt = asstr(txt)
        return txt

    @staticmethod
    def fn_choose(context, test, a, b) :
        return a if test else b

    @staticmethod
    def fn_split(control, txt) :
        txt = asstr(txt)
        return txt.split()

    @staticmethod
    def fn_default(control, *vals) :
        for v in vals :
            x = asstr(v)
            if x is not '' :
                return x
        return ''
        
    extensions = {
        (None, 'doc') : fn_doc,
        (None, 'firstword') : fn_firstword,
        (None, 'findsep') : fn_findsep,
        (None, 'replace') : fn_replace,
        (None, 'dateformat') : fn_dateformat,
        (None, 'choose') : fn_choose,
        (None, 'split') : fn_split,
        (None, 'default') : fn_default
    }


if __name__ == '__main__' :
    import sys, os
    template = sys.argv[1]
    data = sys.argv[2]
    t = Templater()
    t.define('resdir', os.path.abspath(os.path.dirname(__file__)))
    t.parse(template)
    d = et.parse(data).getroot()
    t.process(context = d)
    with codecs.open(sys.argv[3], "w", encoding="utf-8") as of :
        of.write(unicode(t))

