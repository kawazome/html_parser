import re
import debug as debug
from enum import IntEnum

class element_type(IntEnum):
    none = 0
    begin = 1
    end = 2
    begin_end = 3
    text = 4
    comment = 5

class html_attr(object):

    def __init__(self, key, value):
        self._key = None
        self._value = None
        if not isinstance(key, str): return
        if not isinstance(value, str): return
        self._key = key
        self._value = value

    def key(self): return self._key
    def value(self): return self._value

    def get(self,key):
        if key == self._key: return self.value()
        return None

    def attr_string(self):
        if self._key and self._value: return self._key + "=\"" + self._value + "\""
        return ""

    @classmethod
    def parse(cls,string):
        attrs = []
        pattern = "(\\S+)=[\"\']?((?:.(?![\"\']?\\s+(?:\\S+)=|[>\"\']))+.)[\"\']?"
        for result in re.finditer(pattern,string,re.MULTILINE):
            if result: attrs.append(cls(result.groups()[0], result.groups()[1]))
        return attrs

class html_element(object):

    log = debug.logger("html_element")

    def __init__(self, string):
        self._name = None
        self._type = element_type.none
        self._attrs = []
        self._text = None
        self._comment = None
        self._next = None
        if isinstance(string, str): self.parse(string.lstrip())

    def parse(self, string):
        rest_string = self.detect_element(string)
        if rest_string: self._next = html_element(rest_string)

    def detect_element(self,string):
        begin = string.find('<!--')
        if begin == 0: return self.detect_comment(string[4:])
        begin = string.find('<')
        end = string.find('>')
        if begin != 0 or end < 0: return self.detect_text(string)
        buf = string[begin+1:end].replace('\n', '')
        element = self.detect_escape(buf)
        self.detect_name(element)
        return string[end+1:]

    def detect_escape(self, string):
        if string.startswith('/'):
            self._type = element_type.end
            return string.lstrip('/')
        if string.endswith('/'):
            self._type = element_type.begin_end
            return string.rstrip('/')
        self._type = element_type.begin
        return string

    def detect_name(self, string):
        self._name = string.split()[0]
        self._attrs = html_attr.parse(string.lstrip(self._name).strip())

    def detect_text(self, string):
        end = string.find('<')
        self._text = string[0:end].replace('\n', '')
        self._type = element_type.text
        return string[end:]

    def detect_comment(self, string):
        end = string.find('-->')
        self._comment = string[0:end]
        self._type = element_type.comment
        return string[end+3:]

    def name(self): return self._name
    def next(self): return self._next
    def text(self): return self._text
    def comment(self): return "<!--" + self._comment + "-->"
    def type(self): return self._type
    def attrs(self): return self._attrs

    def attrs_string(self):
        array = []
        for attr in self._attrs: array.append(attr.attr_string())
        return ' '.join(array)

    def get_attr(self,key):
        for attr in self._attrs:
            if attr.get(key): return attr.get(key)
        return None

    def check(self, tag_name, attr_name, attr_value):
        if self.check_tagname(tag_name): return self.get_attr(attr_name) == attr_value

    def check_tagname(self,name):
        if self.type() == element_type.begin or self.type() == element_type.begin_end: return self.name() == name
        return False

    def check_id(self, id): return self.get_attr("id") == id

    def tag_string(self):
        if not self._name: return ''
        if self._type == element_type.begin:
            if self._attrs: return '<' + self._name + ' ' + str(self.attrs_string()) + '>'
            return '<' + self._name + '>'
        if self._type == element_type.end: return '</' + self._name + '>'
        if self._type == element_type.begin_end:
            if self._attrs: return '<' + self._name + ' ' + str(self.attrs_string()) + '/>'
            return '<' + self._name + '/>'
        return ''

    def element_string(self):
        if self._text: return self.text()
        if self._comment: return self.comment()
        return self.tag_string()

    def debug_print_all(self, nest=0):
        if self._type == element_type.end: nest -= 1
        self.debug_print(nest)
        if self._type == element_type.begin: nest += 1
        if self._next: self._next.debug_print_all(nest)

    def debug_print(self, nest=0):
        tab = ''
        for i in range(nest): tab = tab + '  '
        html_element.log.put(tab + self.element_string())

class html_node(object):

    log = debug.logger("html_node")

    def __init__(self,element, parent=None):
        self._element = None
        self._parent = None
        self._childs = []
        if isinstance(element, html_element): self._element = element
        if isinstance(parent, html_node): self._parent = parent

    def element(self): return self._element
    def parent(self): return self._parent
    def childs(self): return self._childs

    def level(self):
        if self.parent(): return self.parent().level() + 1
        else: return 0

    def parse(self):
        if not self.element(): return None
        # <any> begin tag ------------
        if self.element().type() == element_type.begin:
            return self.parse_child(self.element().next())
        # none tag -------------------
        # </any> end tag -------------
        # <any/> begin and end tag ---
        return self.element().next()

    def parse_child(self, element):
        if not isinstance(element, html_element): return None
        child = html_node(element, self)
        next = child.parse()
        # </any> end tag -----
        if element.type() == element_type.end:
            if self.element().name() == element.name(): return element
        self.childs().append(child)
        return self.parse_child(next)

    def find_by_id(self, id):
        if self.element().check_id(id): return self
        for child in self.childs():
            if child.find_by_id(id): return child.find_by_id(id)
        return None

    def get(self,tag_name,attr_name,attr_value):
        array = []
        if not tag_name: return array
        if self.element().check(tag_name,attr_name,attr_value): array.append(self)
        for child in self.childs():
            for element in child.get(tag_name,attr_name,attr_value): array.append(element)
        return array

    def get_by_tagname(self,name):
        array= []
        if not name: return array
        if self.element().check_tagname(name): array.append(self)
        for child in self.childs():
            for element in child.get_by_tagname(name): array.append(element)
        return array

    def get_by_attr(self,name,value):
        array = []
        if self.element().get_attr(name) == value: array.append(self)
        for child in self.childs():
            for element in child.get_by_attr(name,value): array.append(element)
        return array

    def elements_string(self,insert_tab=False):
        array = []
        tab = ''
        if insert_tab:
            for i in range(self.level()-1): tab = tab + '  '
        array.append(tab + self.element().element_string())
        for child in self.childs():
            for element in child.elements_string(insert_tab): array.append(element)
        return array

    def debug_print(self):
        if self.element(): self.element().debug_print(nest=self.level()-1)
        for child in self.childs(): child.debug_print()


class html_root(html_node):

    def __init__(self,string):
        super().__init__(html_element(""))
        self.parse_child(html_element(string))

    def write(self,file):
        with open(file,'w',encoding='UTF-8') as f:
            f.write('\n'.join(self.elements_string(insert_tab=True)))
            f.close()

    @classmethod
    def read(cls, file):
        with open(file) as f: return cls(f.read())
        return None

if __name__ == '__main__':
    debug.start("html_parser.debug")
    root = html_root.read("./get-started.html")
    if root: root.write("foo.html")
    debug.end()
    