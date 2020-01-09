
import itertools, sys, os, io, copy, logging, shelve, unicodedata, re, pathlib
import os.path
from os.path import join as osjoin

import logging

logger = logging.getLogger(__name__)

from ColDoc.config import *


__all__ = ( "slugify", "absdict", "Metadata", "uuid_to_dir", "dir_to_uuid",
            "uuid_check_normalize", "uuid_to_int", "int_to_uuid", "new_uuid",
            "new_section_nr" , "uuid_symlink", "os_rel_symlink",
            "ColDocException", "ColDocFileNotFoundError",
            "choose_blob",
            )

class ColDocException(Exception):
    pass

class ColDocFileNotFoundError (FileNotFoundError,ColDocException):
    pass

#####################

# note that from python 3.6 on, `dict` preserves order
from collections import OrderedDict

class Metadata(OrderedDict):
    #
    def __init__(self, filename=None, **k):
        " If `filename` is provided, it will be the default for all writes"
        # the keys as a list (to preserve order)
        self._keys=[]
        assert filename is None or isinstance(filename, (str, pathlib.Path)),\
               "filename %r as type unsupported %r"%(filename,type(filename))
        self._filename = filename
        #if file is not None:
        #    self.read(file)
        return super().__init__(**k)
    #
    @property
    def filename(self):
        return self._filename
    @classmethod
    def open(cls, f):
        " read key/values from `f` ; if `f` is a string or a path, open that as file"
        self = cls()
        if isinstance(f, (str, pathlib.Path)):
            assert os.path.isfile(f),f
            self._filename = str(f)
            f = iter( j for j in open(f) )
        elif isinstance(f, io.IOBase):
            self._filename = f.name
        else:
            raise NotImplementedError('`f` has type: ',type(f))
        for j in f:
            if j[-1] == '\n':
                j = j[:-1]
            i = j.index('=')
            assert i > 0, "cannot parse '%r' as key=value " % j
            k,v = j[:i], j[i+1:]
            self.add(k,v)
        return self
    #
    def write(self, f =  None):
        """ return key/values as a list of strings;
        if `f` is a string, open it as file and write it
        if `f` is a file, write the metadata in that file
        if `f` is None, but a filename was provided when creating the class, write there
        """
        if f is None: f = self._filename
        l = []
        for k,v in self.items():
            for j in v:
                l.append(str(k)+'='+str(j)+'\n')
        if f is not None:
            if isinstance(f, str):
                f = open(f,'w')
            f.writelines(l)
        return l
    #
    def add(self, k, v):
        "add `v` as value for key `k` (only if the value is not present)"
        #assert isinstance(k,str) and isinstance(v,str)
        assert '=' not in str(k)
        if k not in self._keys:
            self._keys.append(k)
        if k in self:
            if v not in self[k]:
                super().__getitem__(k).append(v)
        else:
            super().__setitem__(k, [v])
        #super().setdefault(k,[]).append(v)
    def append(self, k, v):
        "append `v` as value for key `k` (even if the value is not present)"
        #assert isinstance(k,str) and isinstance(v,str)
        assert '=' not in str(k)
        if k not in self._keys:
            self._keys.append(k)
        if k in self:
            super().__getitem__(k).append(v)
        else:
            super().__setitem__(k, [v])
        #super().setdefault(k,[]).append(v)
    #
    def  __setitem__(self, k, v):
        " set one occurrence of `v` for `k`"
        if k not in self._keys:
            self._keys.append(k)
        super().__setitem__(k, [v])
    #
    def setdefault(**o):
        " unimplemented, may confuse users, semantic unclear"
        raise NotImplementedError("use `add` instead")
    #
    @property
    def uuid(self):
        return self.get('uuid',[None])[0]
    #
    def htmlitems(self):
        for key,vals in self.items():
            vallik = []
            for val in vals:
                link=''
                if  key == 'child_uuid' or key == 'parent_uuid':
                    link="/UUID/{val}".format(val=val)
                elif  key ==  'extension' :
                    link="/UUID/{UUID}/?extension={val}".format(UUID=self.uuid,val=val)
                vallik.append((val,link))
            yield (key,vallik)

###############

class absdict(dict):
    """ dict() where each key is converted to an absolute path relative to `basedir`"""
    def __init__(self, basedir, loggingname, **other):
        self._basedir = basedir
        self._loggingname = loggingname
        return super().__init__(**other)
    def _norm(self, k):
        if k != os.path.normpath(k):
            logger.warning('%s, weird key = %r',self._loggingname,k)
        k = os.path.normpath(k)
        if not os.path.isabs(k):
            k = osjoin(self._basedir, k)
        return k
    def __setitem__(self, k, v):
        #assert (not isinstance(v,str)) or (not os.path.isabs(v))
        k = self._norm(k)
        logger.debug("%s[%r] = %r", self._loggingname, k, v)
        return super().__setitem__(k, v)
    def __getitem__(self, k):
        k = self._norm(k)
        return super().__getitem__(k)
    def get(self, k, d = None):
        k = self._norm(k)
        r = super().get(k, d)
        logger.debug("%s.get(%r,%r) = %r", self._loggingname, k, d, r)
        return r
    def __contains__(self, k):
        k = self._norm(k)
        r = super().__contains__(k)
        logger.debug("%r in %s = %r", k, self._loggingname, r)
        return r


#####################

def resolve_uuid(uuid=None, uuid_dir=None, blobs_dir = ColDoc_as_blobs):
    " provide some flexibility in calling argument "
    assert not (uuid is None and uuid_dir is None), 'one of `uuid` or `uuid_dir` must be provided'
    assert blobs_dir is not None
    if isinstance(uuid,int):
        uuid = int_to_uuid(uuid)
    if uuid_dir is None:
        uuid_dir = uuid_to_dir(uuid, blobs_dir=blobs_dir)
    a = osjoin(blobs_dir, uuid_dir)
    #if not os.path.isdir(a):
    #    raise ColDocFileNotFoundError("no dir %r (corresponding to uuid %r)" % (a, uuid))
    m = Metadata.open(osjoin(a, 'metadata'))
    U = m['uuid']
    assert len(U) == 1
    if uuid==None:
        uuid = U[0]
    else:
        assert uuid_to_int(uuid) == uuid_to_int(U[0])
    return uuid, uuid_dir, m

def choose_blob(uuid=None, uuid_dir=None, blobs_dir = ColDoc_as_blobs, ext = '.tex', lang = ColDoc_lang):
    """ Choose a blob, trying to satisfy request for language and extension
    returns `filename`, `uuid`, `metadata`, `lang`, `ext`
    if `ext` is None, a random extension will be returned
    if `lang` is None, a random language will be returned
    """
    uuid, uuid_dir, m = resolve_uuid(uuid = uuid, uuid_dir = uuid_dir, blobs_dir = blobs_dir)
    # short circuit the case of given lang and ext
    if lang is not None and ext is not None:
        input_file = osjoin(blobs_dir, uuid_dir, 'blob_'+lang+ext)
        if os.path.exists(input_file):
            return input_file,uuid,m,lang,ext
        else:
            logger.error('Blob `%r` not available for lang = %r ext = %r', uuid, lang, ext)
            raise ColDocException()
    #
    E = m.get('extension',[''])
    assert len(E) >= 1
    if ext is not None:
        if ext not in E:
            logger.error('Extension %r is not available for uuid %r',ext, uuid)
            raise ColDocException()
        E = [ext]
    #
    L = copy.copy(m.get('lang',[]))
    # as a last resort, try a "no language" choice
    L.append('')
    if lang is not None:
        if lang not in L:
            logger.error('Language %r is not available for uuid %r',lang, uuid)
            raise ColDocException()
        L = [lang]
    for l in L:
        for e in E:
            ls = l
            if l:
                ls='_'+l
            input_file = osjoin(blobs_dir, uuid_dir, 'blob'+ls+e)
            if os.path.exists(input_file):
                return input_file,uuid,m,l,e
    logger.error('Blob `%r` not available for lang in %r, ext in %r', uuid, L, E)
    raise ColDocException('Blob `%r` not available for lang in %r, ext in %r'%(uuid, L, E))

#####################

# this part of code is taken (simplified) from  base32_crockford

# we omit vowels
symbols = '0123456789BCDFGHJKMNPQRSTVWXYZ'
base = len(symbols)
encode_symbols = dict((i, ch) for (i, ch) in enumerate(symbols))
decode_symbols = dict((ch, i) for (i, ch) in enumerate(symbols))

normalize_symbols = str.maketrans('IiLlOo', '111100')
valid_symbols = re.compile('^[%s]+$' % (symbols,))

def int_to_uuid(number):
    """ convert a positive integer to a UUID :
    a string of characters from `symbols` that is at least 3 letters long"""
    assert isinstance(number,int) and number >= 0
    if number == 0:
        return '000'
    symbol_string = ''
    while number > 0:
        remainder = number % base
        number //= base
        symbol_string = encode_symbols[remainder] + symbol_string
    return symbol_string.rjust(3,'0')

def uuid_check_normalize(symbol_string):
    " normalize a string and check that it is a valid UUID "
    norm_string = symbol_string.translate(normalize_symbols).upper()
    if not valid_symbols.match(norm_string):
        raise ValueError("string '%s' contains invalid characters" % symbol_string)
    return norm_string.rjust(3,'0')

def uuid_to_int(symbol_string):
    """  normalize `symbol_string`, check that it is a valid UUID, and convert to integer  """
    symbol_string = uuid_check_normalize(symbol_string)
    number = 0
    for symbol in symbol_string:
        number = number * base + decode_symbols[symbol]
    return number




#####################

def uuid_to_dir(u, blobs_dir = ColDoc_as_blobs, create = False):   #, ColDocContent = ColDocContent):
    " returns directory for UUID (relative to `blobs_dir`); it is a 3-level dir/dir/dir ; if `create` then all levels are created here"
    assert isinstance(u,str) and len(u) >= 1, 'type %r repr %r'%(type(u),repr(u))
    assert os.path.isdir(blobs_dir), blobs_dir
    #d = ColDocContent
    #pieces =  'UUIDs',u[-1],u[:-1]
    d = 'UUID'
    if len(u) < 3:
        u = u.rjust(3,'0')
    pieces =  u[0],u[1],u[2:]
    for j in pieces:
        d = osjoin(d, j)
        if create and not os.path.isdir( osjoin(blobs_dir,d) ):
            os.mkdir( osjoin(blobs_dir,d) )
    return d

def dir_to_uuid(directory):
    prefix = 'UUID/'
    assert directory[:len(prefix)] == prefix
    directory = directory[len(prefix):]
    assert directory[1] == directory[3] == os.path.sep
    return directory[0] + directory[2] + directory[4:]

def uuid_symlink(src, dst, blobs_dir = ColDoc_as_blobs, create = True ):
    " symlink src UUID to dst UUID "
    assert type(dst) == str and len(dst) >= 3
    assert type(src) == str and len(src) >= 3
    dst_dir = uuid_to_dir(src)
    #assert os.path.isdir(dst_dir)
    assert os.path.isdir(blobs_dir)
    d = blobs_dir
    pieces =  'UUID',dst[-1]
    for j in pieces:
        d = osjoin(d, j)
        if create and not os.path.isdir(d):
            os.mkdir(d)
    d = osjoin(d, dst[:-1])
    src_dir = osjoin('..',src[-1],src[:-1])
    if os.path.exists(d):
        assert os.path.islink(d)
    else:
        os.symlink(src_dir, d, target_is_directory=True)
    return d


def new_uuid(blobs_dir = ColDoc_as_blobs, variables = ColDoc_variables):
    " returns a new , unused UUID; creating needed directories "
    if not os.path.isabs(variables):
        variables = osjoin(blobs_dir, variables)
    with shelve.open(variables, flag='c') as v:
        n = v.get('last_uuid_n', 0)
        while True:
            n = n + 1
            uuid = int_to_uuid(n)
            uuid_dir = uuid_to_dir(uuid, blobs_dir = blobs_dir, create=False)
            if  os.path.exists(uuid_dir):
                logger.warning('directory exists for n = %r uuid = %r',n,uuid)
            else:
                uuid_to_dir(uuid, blobs_dir = blobs_dir, create = True)
                break
        v['last_uuid_n'] = n
    logger.debug('new uuid n = %r uuid = %r',n,uuid)
    return uuid


def new_section_nr(blobs_dir = ColDoc_as_blobs, variables = ColDoc_variables):
    " returns a new section nr; creating needed directories "
    if not os.path.isabs(variables):
        variables = osjoin(blobs_dir, variables)
    with shelve.open(variables, flag='c') as v:
        n = v.get('last_section_n', 0)
        n = n + 1
        v['last_section_n'] = n
    logger.debug('new section n = %r ' % (n,))
    return n


# https://github.com/django/django/blob/master/django/utils/text.py
def slugify(value, allow_unicode=False):
    """
    Convert to ASCII if 'allow_unicode' is False. Convert spaces to hyphens.
    Remove characters that aren't alphanumerics, underscores, or hyphens.
    Convert to lowercase. Also strip leading and trailing whitespace.
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize('NFKC', value)
    else:
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    return re.sub(r'[-\s]+', '-', value)

# https://stackoverflow.com/questions/295135/turn-a-string-into-a-valid-filename
#def slugify(value):
#    """
#    Normalizes string, converts to lowercase, removes non-alpha characters,
#    and converts spaces to hyphens.
#    """
#    import unicodedata
#    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')
#    value = unicode(re.sub('[^\w\s-]', '', value).strip().lower())
#    value = unicode(re.sub('[-\s]+', '-', value))

def os_rel_symlink(src, dst, basedir, target_is_directory, force = False, **kwargs):
    """ Create a symbolic link pointing to src named dst. Both must be relative paths,
    (relative to `basedir`). `target_is_directory` must be set. `force` will delete
    target if it exists and it is a symlink.
    """
    assert not os.path.isabs(src)
    assert not os.path.isabs(dst)
    assert os.path.isdir(basedir)
    src = os.path.abspath(os.path.join(basedir, src))
    dst = os.path.abspath(os.path.join(basedir, dst))
    dst_dir = os.path.dirname(dst) #if target_is_directory else 
    src = os.path.relpath(src, dst_dir)
    if not os.path.isdir(dst_dir):
        os.makedirs(dst_dir)
    if force and os.path.islink(dst):
        logger.warning(' substituting symlink %r' % dst)
        os.unlink(dst)
    logger.debug(" os.symlink (%r, %r )" % (src, dst) )
    os.symlink(src, dst, target_is_directory=target_is_directory, **kwargs)

############################

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'test_uuid':
        assert 1 == uuid_to_int('OOO1')
        #
        didnt=True
        try:
            uuid_check_normalize('/')
            didnt=False
        except ValueError:
            pass
        assert didnt
        #
        for j in range(0, base ** 4 + base**3, base+3):
            u = int_to_uuid(j)
            assert j == uuid_to_int(u)
            d = uuid_to_dir(u, blobs_dir='/tmp',create=False)
            u2 = dir_to_uuid(d)
            assert u == u2
    else:
        print(""" Commands:
%s test_uuid
""" % (sys.argv[0],))
