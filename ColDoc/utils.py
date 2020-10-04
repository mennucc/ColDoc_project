import itertools, sys, os, io, copy, logging, shelve, unicodedata
import re, pathlib, subprocess, datetime
import tempfile, shutil, json
import os.path
from os.path import join as osjoin

if __name__ == '__main__':
    for j in ('','.'):
        if j in sys.path:
            sys.stderr.write('Warning: deleting %r from sys.path\n',j)
            del sys.path[sys.path.index(j)]
    #
    a = os.path.realpath(sys.argv[0])
    a = os.path.dirname(a)
    a = os.path.dirname(a)
    assert os.path.isdir(a), a
    if a not in sys.path:
        sys.path.insert(0, a)
    COLDOC_SRC_ROOT=a
    del a
    #
    from ColDoc import loggin

import logging
logger = logging.getLogger(__name__)

from ColDoc.config import *
from ColDoc.classes import MetadataBase


__all__ = ( "slugify", "slug_re", "absdict", "FMetadata", "uuid_to_dir",
            "dir_to_uuid", "file_to_uuid",
            "uuid_check_normalize", "uuid_to_int", "int_to_uuid",
            "new_uuid", "backtrack_uuid",
            "new_section_nr" , "uuid_symlink", "os_rel_symlink",
            "ColDocException", "ColDocFileNotFoundError",
            "sort_extensions", "choose_blob", "plastex_invoke",
            "metadata_html_items",
            'prepare_anon_tree',
            )

class ColDocException(Exception):
    pass

class ColDocFileNotFoundError (FileNotFoundError,ColDocException):
    pass

#####################

# note that from python 3.6 on, `dict` preserves order
from collections import OrderedDict

class FMetadata(dict, MetadataBase):
    "an implementation of `MetadataBase` that stores data in a file"
    #
    __protected_fields = ('uuid',)
    #
    def __init__(self, filename=None, basepath=None, coldoc=None, *args, **kwargs):
        """ If `filename` is provided, it will be the default for all writes
        (this is deprecated and should be used only for testing).
        If `filename` is `None` and `basepath` is given, then the filename will be of the form
        `UUID/N/N/N/metadata` inside the `basepath`
        """
        # the keys as a list (to preserve order)
        self._keys=list(self._single_valued_keys)
        #
        assert filename is None or isinstance(filename, (str, pathlib.Path)),\
               "filename %r as type unsupported %r"%(filename,type(filename))
        self._filename = filename
        #
        assert basepath is None or isinstance(basepath, (str, pathlib.Path)),\
               "basepath %r as type unsupported %r"%(basepath,type(basepath))
        self._basepath = basepath
        if coldoc is not None:
            kwargs['coldoc'] = [coldoc,]
        return super().__init__(*args, **kwargs)
    #
    @property
    def filename(self):
        return self._filename
    @classmethod
    def load_by_file(cls, f):
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
            if k == 'uuid':
                self.uuid = v
            else:
                self.add(k,v)
        return self
    #
    @classmethod
    def load_by_uuid(cls, uuid, coldoc=None, basepath=None):
        "`coldoc` is ignored, `basepath` must be given"
        assert isinstance(basepath, (str, pathlib.Path))
        assert isinstance(uuid,str)
        return cls.load_by_file( osjoin(basepath,uuid_to_dir(uuid),'metadata') )
    #
    def save(self, f =  None):
        """ return key/values as a list of strings;
        if `f` is a string, open it as file and write it
        if `f` is a file, write the metadata in that file
        if `f` is None, but a `filename` or `basepath` was provided when creating the class, write there
        """
        if 'saved_by_django' in super().keys():
            raise RuntimeError('This metadata was saved by `django`, saving it here would disalign the database')
        if f is None:
            if self._filename is not None:
                f = self._filename
            elif self._basepath is not None:
                f = osjoin(self._basepath, uuid_to_dir(self.uuid, blobs_dir=self._basepath),'metadata')
        assert f is not None
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
        """ if `key` is single-valued, set `key` to `value`; if `key` is multiple-valued,
        adds a `value` for `key` (only if the value is not present); """
        #assert isinstance(k,str) and isinstance(v,str)
        if k in self.__protected_fields:
            raise RuntimeError('Cannot set protected field %r to %r'%(k, v))
        assert '=' not in str(k)
        if k in self._single_valued_keys:
            return super().__setitem__(k, [v])
        if k not in self._keys:
            self._keys.append(k)
        if k in self:
            if v not in self[k]:
                return super().__getitem__(k).append(v)
        else:
            return super().__setitem__(k, [v])
        #super().setdefault(k,[]).append(v)
    def append(self, k, v):
        """append `v` as value for key `k` (even if the value is not present);
        deprecated, I now see no need to have repeated values
        """
        #assert isinstance(k,str) and isinstance(v,str)
        logger.warning('Deprecated `append`')
        assert '=' not in str(k)
        if k not in self._keys:
            self._keys.append(k)
        if k in self:
            super().__getitem__(k).append(v)
        else:
            super().__setitem__(k, [v])
        #super().setdefault(k,[]).append(v)
    #
    def get(self, k, default=None):
        if default is not None:
            logger.error('FMetadata.get default is not implemented, key=%r',k)
        return super().get(k,[])
    #
    def  __setitem__(self, k, v):
        " set value `v` for `k` (as one single value, even if multivalued)"
        if k not in self._keys:
            self._keys.append(k)
        super().__setitem__(k, [v])
    #
    def setdefault(**o):
        " unimplemented, may confuse users, semantic unclear"
        raise NotImplementedError("use `add` instead")
    #
    # property calls for single-valued elements
    #
    @property
    def uuid(self):
        return super().get('uuid',[None])[0]
    @uuid.setter
    def uuid(self, uuid):
        if super().get('uuid') is not None:
            a = super().get('uuid')[0]
            if  a != uuid:
                raise RuntimeError(' UUID is alreaady set to %r, cannot set it twice (to %r)'%(uuid, a))
        super().__setitem__('uuid',[uuid])
    @property
    def environ(self):
        return super().get('environ',[None])[0]
    @property
    def coldoc(self):
        return super().get('coldoc',[None])[0]
    #
    @property
    def blob_modification_time(self):
        return super().get('blob_modification_time',[None])[0]
    def blob_modification_time_update(self, default=None):
        if default is None: default=datetime.datetime.now()
        super().__setitem__('blob_modification_time', [default])
    #
    @property
    def latex_time(self):
        return super().get('latex_time',[None])[0]
    def latex_time_update(self, default=None):
        if default is None: default=datetime.datetime.now()
        super().__setitem__('latex_time', [default])
    #
    def singled_items(self):
        " yields all (key,value) pairs, where each `key` may be repeated multiple times"
        for k in self.keys():
            for v in self[k]:
                yield k,v
    #
    def delete(self,k,v):
        "delete a key/value"
        if k in self:
            z = self[k]
            while v in z:
                z.pop(z.index(v))
            self[k] = z
    #
    def htmlitems(self):
        return metadata_html_items(self, super().get('coldoc',[''])[0] )


def metadata_html_items(metadata, nick):
        for key,vals in metadata.items():
            vallik = []
            for val in vals:
                link=''
                if  key == 'child_uuid' or key == 'parent_uuid':
                    link="/UUID/{nick}/{val}".format(val=val,nick=nick)
                elif  key ==  'extension' :
                    if val[0] == '.': val=val[1:]
                    link="/UUID/{nick}/{UUID}/?ext={val}".format(UUID=metadata.uuid,nick=nick,val=val)
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

def resolve_uuid(uuid=None, uuid_dir=None, blobs_dir = ColDoc_as_blobs,
                 metadata_class=FMetadata, coldoc=None):
    " provide some flexibility in calling argument "
    assert not (uuid is None and uuid_dir is None), 'one of `uuid` or `uuid_dir` must be provided'
    if uuid is None:
        uuid_str = dir_to_uuid(uuid_dir)
        uuid_int = uuid_to_int(uuid_str)
    elif isinstance(uuid,int):
        uuid_str = int_to_uuid(uuid)
        uuid_int = uuid
    else:
        uuid_str = str(uuid)
        uuid_int = uuid_to_int(uuid_str)
    if uuid_dir is None:
        uuid_dir = uuid_to_dir(uuid_str, blobs_dir=blobs_dir)
    #a = osjoin(blobs_dir, uuid_dir)
    #if not os.path.isdir(a):
    #    raise ColDocFileNotFoundError("no dir %r (corresponding to uuid %r)" % (a, uuid))
    # currently `load_by_uuid` needs one of those
    assert blobs_dir is not None or coldoc is not None
    m = metadata_class.load_by_uuid(uuid, coldoc=coldoc, basepath=blobs_dir)
    if m is None:
        logger.error('Metadata `%r` not available for basepath %r coldoc %r', uuid, blobs_dir, coldoc)
        raise ColDocException('Metadata `%r` not available for basepath %r coldoc %r'%(uuid, blobs_dir, coldoc))
    U = m.get('uuid')
    assert uuid_int == uuid_to_int(U[0])
    return uuid, uuid_dir, m

def sort_extensions(E):
    # FIXME should look in request
    P = {a:4 for a in ('.jpg','.jpeg','.png','.tif','.tiff','.gif')}
    P.update({'.svg':2,'.pdf':7})
    E.sort(key = lambda x: P.get(x,10))
    return E

def choose_blob(uuid=None, blobs_dir = ColDoc_as_blobs, ext = '.tex',
                lang = ColDoc_lang, metadata_class=FMetadata, coldoc=None, metadata=None):
    """ Choose a blob, trying to satisfy request for language and extension
    returns `filename`, `uuid`, `metadata`, `lang`, `ext`
    if `ext` is None, an extension will be returned following `sort_extensions`
    if `lang` is None, a random language will be returned
    """
    assert metadata is not None or (uuid is not None and coldoc is not None)
    assert isinstance(uuid,str) or uuid is None
    #
    if metadata is None:
        m = metadata_class.load_by_uuid(uuid=uuid,coldoc=coldoc,basepath=blobs_dir)
    else:
        m = metadata
        uuid = metadata.uuid
    #
    uuid_dir = uuid_to_dir(uuid)
    #
    if m is None:
        logger.error('Metadata `%r` not available for coldoc %r', uuid, coldoc)
        raise ColDocException('Metadata `%r` not available for coldoc %r'%(uuid, coldoc))
    # short circuit the case of given lang and ext
    if lang is not None and ext is not None:
        lang_ = ('_' + lang) if lang else ''
        input_file = osjoin(blobs_dir, uuid_dir, 'blob' + lang_ + ext)
        if os.path.exists(input_file):
            return input_file,uuid,m,lang,ext
        else:
            logger.error('Blob `%r` not available for lang = %r ext = %r', uuid, lang, ext)
            raise ColDocException('Blob `%r` not available for lang = %r ext = %r' % ( uuid, lang, ext))
    #
    E = sort_extensions(m.get('extension'))
    assert len(E) >= 1
    if ext is not None:
        if ext not in E:
            logger.error('Extension %r is not available for uuid %r',ext, uuid)
            raise ColDocException('Extension %r is not available for uuid %r'%(ext, uuid))
        E = [ext]
    #
    L = copy.copy(m.get('lang'))
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

uuid_normalize_symbols = str.maketrans('IiLlOo', '111100')
uuid_valid_symbols = re.compile('^[%s]+$' % (symbols,))

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
    norm_string = symbol_string.translate(uuid_normalize_symbols).upper()
    if not uuid_valid_symbols.match(norm_string):
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
    assert create is False or os.path.isdir(blobs_dir), blobs_dir
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
    directory = os.path.normpath(directory)
    assert directory[:len(prefix)] == prefix, (directory, prefix)
    directory = directory[len(prefix):].split(os.path.sep)
    return directory[0] + directory[1] + directory[2]

def file_to_uuid(filename, blobs_dir):
    """given a file or directory, tracks down symlinks,
    returns (UUID, basename)  where `basename` is the filename inside the UUID directory,
    or `None` if `filename` was a directory"""
    blobs_dir = os.path.realpath(blobs_dir)
    if not os.path.isabs(filename):
        filename = os.path.join(blobs_dir,filename)
    filename = os.path.realpath(filename)
    blobs_dir += os.path.sep
    assert filename[:len(blobs_dir)] == blobs_dir, (filename, blobs_dir)
    if os.path.isfile(filename):
        filename, base = os.path.split(filename)
    else:
        base = None
    filename = filename[len(blobs_dir):]
    uuid = dir_to_uuid(filename)
    return uuid, base
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
                L=os.listdir(uuid_dir)
                if L:
                    logger.warning('directory exists for uuid = %r and contains %r',uuid,L)
                else:
                    logger.debug('reusing empty directory for uuid = %r',uuid)
                    break
            else:
                # create the directory
                uuid_to_dir(uuid, blobs_dir = blobs_dir, create = True)
                break
        v['last_uuid_n'] = n
    logger.debug('new uuid n = %r uuid = %r',n,uuid)
    return uuid

def backtrack_uuid(uuid, blobs_dir = ColDoc_as_blobs, variables = ColDoc_variables):
    " tries to backtrack the UUID, so that it may be reused"
    if not os.path.isabs(variables):
        variables = osjoin(blobs_dir, variables)
    if isinstance(uuid,str):
        uuid=uuid_to_int(uuid)
    with shelve.open(variables, flag='c') as v:
        n = v.get('last_uuid_n', 0)
        if n == uuid and n >= 1:
            n = n - 1
            v['last_uuid_n'] = n
            logger.debug("Backtrack before uuid %s",int_to_uuid(uuid))
            return True
        else:
            logger.warning("Cannot backtrack %s , we are at %s ",
                           int_to_uuid(uuid),int_to_uuid(n))
            return False


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

# taken from Django, for convenience
slug_re = re.compile(r'^[-a-zA-Z0-9_]+\Z')

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

def plastex_invoke(cwd_, stdout_ , argv_):
    "invoke plastex with given args. Currently by subprocess. TODO internally, caching some stuff"
    p = subprocess.Popen(['plastex']+argv_, cwd=cwd_, stdin=open(os.devnull),
                         stdout=stdout_, stderr=subprocess.STDOUT)
    p.wait()
    return p.returncode

############################




def prepare_anon_tree_recurse(blobs_dir, temp_dir, uuid, lang, warn, metadata_class):
    " subrouting for `prepare_anon_tree` "
    warn = logging.WARNING if warn else logging.DEBUG
    uuid_, uuid_dir, metadata = resolve_uuid(uuid=uuid, uuid_dir=None,
                                                   blobs_dir = blobs_dir,
                                                   metadata_class=metadata_class)
    ret = 0
    bd = osjoin(blobs_dir,uuid_dir)
    td = osjoin(temp_dir,uuid_dir)
    os.makedirs(td)
    publ = metadata.get('access')[0] in ('open','public')
    for j in os.listdir(bd):
        f = osjoin(bd,j)
        t = osjoin(td,j)
        if j == 'metadata':
            ret += 1
            logger.debug('did copy %r',f)
            shutil.copy2(f,t, follow_symlinks=False)
        elif j.startswith('blob') and os.path.isfile(f): # or os.path.islink(f):
            # extract extension
            B,E = os.path.splitext(j)
            # extract language, with underscore
            L = B[4:]
            if lang is not None and L and lang != L[1:]:
                # If `lang` is not None, skip any blob that has a language that is not None
                logger.debug('did not copy %r wrong language',f)
                continue
            ret += 1
            if publ:
                try:
                    os.link(f,t)
                    logger.debug('did link %r',f)
                except:
                    logger.debug('could not link , rather copy %r',f)
                    shutil.copy2(f,t, follow_symlinks=False)
            elif  E == '.tex':
                # mask content, preserve tree
                F = open(t,'w')
                F.write('\\uuid{%s}'%uuid)
                for u in metadata.get('child_uuid'):
                    # We include all LaTeX children, to keep tree connectivity
                    sub_uuid_, sub_uuid_dir, sub_metadata = resolve_uuid(uuid=u, uuid_dir=None,
                                                                         blobs_dir = blobs_dir,
                                                                         metadata_class=metadata_class)
                    if '.tex' in sub_metadata.get('extension'):
                        F.write('\\input{%s/blob%s.tex}'%(sub_uuid_dir,L))
                F.close()
                logger.debug('did mask private %r',f)
            else:
                try:
                    os.link(f,t)
                    logger.debug('did link %r',f)
                except:
                    logger.debug('could not link , rather copy %r',f)
                    shutil.copy2(f,t, follow_symlinks=False)
        else:
            logger.log(logging.DEBUG,'did not copy %r',f)
    for u in metadata.get('child_uuid'):
        logger.debug('moving down from node %r to node %r',uuid,u)
        ret += prepare_anon_tree_recurse(blobs_dir, temp_dir, u, lang, warn, metadata_class)
    return ret
    

def prepare_anon_tree(coldoc_dir, uuid=None, lang=None,
                      warn=False, metadata_class=FMetadata):
    """ copy the whole tree, starting from `uuid`, and masking private content;
    returns `(n,anon)` , where `n` is the number of copied files, and
    `anon` is the anonymous directory (or `None` in case of failure).
    If `lang` is not None, skip any blob that has a language that is not None.
    """
    warn = logging.WARNING if warn else logging.DEBUG
    if uuid is None:
        uuid = '001'
    blobs_dir = osjoin(coldoc_dir, 'blobs')
    assert os.path.isdir(blobs_dir)
    anon_dir = osjoin(coldoc_dir, 'anon')
    temp_dir = tempfile.mkdtemp(dir=coldoc_dir)
    logger.log(warn, 'Preparing anon tree in %s', temp_dir)
    r = 0
    try:
        r = prepare_anon_tree_recurse(blobs_dir, temp_dir, uuid, lang, warn, metadata_class)
        for dirpath, dirnames, filenames in os.walk(blobs_dir,followlinks=False):
            tmp_path = osjoin(temp_dir,dirpath[1+len(blobs_dir):])
            os.makedirs(tmp_path, exist_ok=True)
            for j in (filenames + dirnames):
                src = osjoin(dirpath,j)
                dst = osjoin(tmp_path,j)
                if os.path.islink(src):
                    k = os.readlink(src)
                    r += 1
                    logger.debug('symlink %s -> %s',src,k)
                    os.symlink(k,dst)
                #else:
                #    logger.debug('not symlink %s',src)
        # preserve certain files when rebuilding anon tree
        extensions = ColDoc_anon_keep_extensions
        for dirpath, dirnames, filenames in os.walk(anon_dir,followlinks=False):
            tmp_path = osjoin(temp_dir,dirpath[1+len(anon_dir):])
            os.makedirs(tmp_path, exist_ok=True)
            for j in filenames:
                if  os.path.splitext(j)[1] in extensions:
                    src = osjoin(dirpath,j)
                    dst = osjoin(tmp_path,j)
                    if os.path.isfile(src):
                        if os.path.isfile(dst):
                            os.unlink(dst)
                        logger.debug("preserve across anon runs %s %s" % (src,dst))
                        shutil.copy2(src,dst, follow_symlinks=False)
            
    except:
        logger.exception("failed")
        shutil.rmtree(temp_dir)
        return r, None
    else:
        if os.path.isdir(anon_dir):
            shutil.rmtree(anon_dir)
        os.rename(temp_dir, anon_dir)
    return r, anon_dir



############################


def recurse_tree(coldoc_nick, blobs_dir, metadata_class, action, uuid=None, depth=0):
    """ recurse tree starting from `uuid` , for each node call 
    `action(uuid=uuid, uuid_dir=uuid_dir, metadata=metadata, depth=depth)` which should return a boolean"""
    #
    if uuid is None:
        logger.debug('Assuming root_uuid = 001')
        uuid = '001'
    import ColDoc
    uuid_, uuid_dir, metadata = ColDoc.utils.resolve_uuid(uuid=uuid, uuid_dir=None,
                                                   blobs_dir = blobs_dir,
                                                   coldoc = coldoc_nick,
                                                   metadata_class=metadata_class)
    #
    ret = action(uuid=uuid, uuid_dir=uuid_dir, metadata=metadata, depth=depth)
    #
    for u in metadata.get('child_uuid'):
        logger.debug('moving down from node %r to node %r',uuid,u)
        r = recurse_tree(coldoc_nick, blobs_dir, metadata_class, action, uuid=u, depth=(depth+1))
        ret = ret and r
    return ret

############################


def reparse_blob(filename, metadata, blobs_dir, warn=None, act=True, ignore_uuid=True):
    " reparse a blob to extract and update all metadata "
    if warn is None:
        warn = logger.warning
    #
    a = osjoin(blobs_dir, '.blob_inator-args.json')
    options = json.load(open(a))
    #
    from ColDoc.transform import reparse_metadata
    parsed_back_map, parsed_metadata = reparse_metadata(filename, metadata, blobs_dir, options)
    #
    # insert changes regarding children
    old_children = metadata.get('child_uuid')
    old_children_set = set(old_children)
    if act:
        del metadata['child_uuid']
        new_children_set = set()
        for childuuid in parsed_back_map:
            if childuuid in new_children_set:
                warn('In %r the child %r is referenced twice'%(uuid,childuuid))
            else:
                metadata.add('child_uuid',childuuid)
            new_children_set.add(childuuid)
    else:
        new_children_set = set(parsed_back_map)
    #
    if old_children_set != new_children_set:
        if old_children_set.difference(new_children_set):
            warn('Warning connection to these children was disconnected: %r'%(old_children_set.difference(new_children_set),))
        if new_children_set.difference(old_children_set):
            warn('New connection to these children: %r'%(new_children_set.difference(old_children_set),))
    #
    # insert changes regarding extrametadata
    #
    from ColDoc.latex import environments_we_wont_latex
    if metadata.environ in environments_we_wont_latex:
        metadata.save()
        return
    old_metadata_set = set()
    for key, value in metadata.items():
        if key.startswith('M_') or key.startswith('S_'):
            for v in value:
                old_metadata_set.add( (key,v) )
    if ignore_uuid:
        new_metadata_set = set((k,v) for k,v in parsed_metadata if k!='M_uuid')
    else:
        new_metadata_set = set(parsed_metadata)
    if old_metadata_set != new_metadata_set:
        if old_metadata_set.difference(new_metadata_set):
            warn('Deleted metadata: %r'%(old_metadata_set.difference(new_metadata_set),))
        if new_metadata_set.difference(old_metadata_set):
            warn('New metadata: %r'%(new_metadata_set.difference(old_metadata_set),))
    #
    if act:
        for key in metadata.keys():
            if key.startswith('M_') or key.startswith('S_'):
                del metadata[key]
        for key, value in parsed_metadata:
            if key == 'M_uuid':
                if value != ('{'+metadata.uuid+'}'):
                    warn('Warning: there is a `uuid` command with value %s instead of {%s}'%(value,metadata.uuid))
                if not ignore_uuid:
                    metadata.add(key,value)
            else:
                metadata.add(key,value)
    metadata.save()


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
    elif len(sys.argv) > 2 and sys.argv[1] == 'prepare_anon':
        logger.setLevel(0)
        logging.getLogger().setLevel(0)
        r = prepare_anon_tree(sys.argv[2])
        print('Copied %d'%(r,))
    else:
        print(""" Commands:
%s test_uuid
  
  prepare_anon coldoc_dir
""" % (sys.argv[0],))


