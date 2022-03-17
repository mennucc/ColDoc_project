import itertools, sys, os, io, copy, logging, shelve, unicodedata
import re, pathlib, subprocess, datetime, json
import tempfile, shutil, json, hashlib, importlib
import functools, inspect
import traceback, contextlib
import os.path
from os.path import join as osjoin
from bs4 import BeautifulSoup


def _(s):
    "mark translatable strings; no attempt is made to translate them, since this is a library"
    return s

import plasTeX

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


__all__ = ( "slugify", "slug_re", "slugp_re",
            "absdict", "FMetadata", "uuid_to_dir",
            "dir_to_uuid", "file_to_uuid",
            "uuid_check_normalize", "uuid_to_int", "int_to_uuid",
            "new_uuid", "backtrack_uuid",
            "new_section_nr" , "uuid_symlink", "os_rel_symlink",
            "ColDocException", "ColDocFileNotFoundError",
            "sort_extensions", "choose_blob", "plastex_invoke",
            "metadata_html_items",
            'prepare_anon_tree',
            'json_to_dict', 'dict_to_json', 'dict_save_or_del',
            'split_blob',
            'tree_environ_helper',
            'is_image_blob',
            'get_blobinator_args',
            'parenthesizes',
            'hash_tree',
            'replace_with_hash_symlink',
            'parent_cmd_env_child',
            'html2text',
            'iso3lang2word', 'iso3lang_to_iso2',
            'replace_language_in_inputs','strip_language_lines', 'gen_lang_coldoc', 'gen_lang_metadata',
            'multimerge', 'multimerge_lookahead',
            'text_linechar2pos', 'text_pos2linechar',
            'line_with_language_lines', 'line_without_language_lines',
            'parse_latex_log',
            'recreate_symlinks',
            'TeX_add_packages',
            'log_debug',
            )

class ColDocException(Exception):
    pass

class ColDocFileNotFoundError (FileNotFoundError,ColDocException):
    pass

######################
# 
def log_debug(fun):
    @functools.wraps(fun)
    def log_call(*args, **kwds):
        S=inspect.signature(fun)
        B=S.bind(*args, **kwds)
        B.apply_defaults()
        globals()['logger'].debug('Calling function %s  %s ', fun, B)
        return fun(*args, **kwds)
    return log_call



#####################

try:
    import pycountry
except ImportError:
    pycountry = None
    iso3lang2word = lambda x : x
else:
    def iso3lang2word(val):
        L = pycountry.languages.get(alpha_3=val)
        if L:
            return( L.name)
        return val

def iso3lang_to_iso2(l):
    if len(l) == 2:
        return l
    elif len(l) == 3:
        L = pycountry.languages.get(alpha_3=l)
        return L.alpha_2

#####################


def TeX_add_packages(thetex,options):
    mydocument = thetex.ownerDocument
    mycontext = mydocument.context
    config = thetex.ownerDocument.config
    config['general']['load-tex-packages'] = False
    # give it some context
    latex_class = options.get('documentclass','article')
    latex_class_options = options.get('documentclassoptions','')
    if latex_class:
        # FIXME use latex_class_options
        latex_class_options = parenthesizes(latex_class_options, '[]')
        mycontext.loadPackage(thetex, latex_class + '.cls', {})
    # fallback
    f = ['graphicx', 'amsmath', 'amssymb', 'amsthm', 'iftex', 'hyperref']
    f = [ (a,'') for a in f]
    # load latex packages
    latex_packages = options.get('latex_packages', f)
    for p, o in latex_packages:
        # FIXME use options
        try:
            mycontext.loadPackage(thetex, p + '.sty', {})
        except:
            logger.exception('While loading package %r',p)

######################

def parse_latex_log(blobs_dir, uuid, lang, ext, prefix='view', context=10):
    base_dir = osjoin(blobs_dir, uuid_to_dir(uuid, blobs_dir))
    errors = []
    try:
        log = os.path.join(base_dir, prefix + '_' + lang + ext)
        if not os.path.exists(log):
            logger.warning('cannot find a log for %r %r %r %r',base_dir, prefix, lang, ext)
            return []
        F = iter(open(log))
        for z in F:
            if z.startswith('./UUID/') or z.startswith('UUID/') \
               or z.startswith('./SEC/') or z.startswith('SEC/'):
                k = z.split(':', 2)
                if len(k) >= 3:
                    s = k[2] 
                    try:
                        err_uuid , base = file_to_uuid(k[0], blobs_dir)
                    except:
                        logger.exception("file_to_uuid(%r, blobs_dir)" %( k[0],))
                        err_uuid = k[0]
                    l = k[1]
                    c = context
                    try:
                        z = next(F)
                        while z.strip() and c>0:
                            c -= 1
                            s += z
                            z = next(F)
                        s += z
                        z = next(F)
                        while z.strip() and c>0:
                            c -= 1
                            s += z
                            z = next(F)
                    except StopIteration:
                        pass
                    errors.append((err_uuid, l ,s))
    except:
        logger.exception("parse_latex_log({blobs_dir!r}, {uuid!r}, {lang!r}, {ext!r}, {prefix!r}, {context!r})".format_map(locals()))
    return errors

#########################

def text_pos2linechar(text, pos):
    " `pos` is an absolute position in `text` , returns `line` and `char` in line"
    if isinstance(text, str):
        text = text.splitlines(keepends=True)
    line = 0
    for z in text:
        l = len(z)
        if pos < l:
            return line, pos
        pos -= l
        line += 1
    return line, pos

def text_linechar2pos(text, line, char):
    " given `line` and `char`  in `text` , returns `pos`  an absolute position "
    if isinstance(text, str):
        text = text.splitlines(keepends=True)
    return sum(len(z) for z in text[:line]) + char

#####################

def parenthesizes(s, p='{}', also_when_empty=None):
    """ strip extra spaces from `s` and add parentheses `p`  ;
        if `s` is empty (after stripping), parentheses are added if `also_when_empty` is `True` ;
        if `also_when_empty` is not given it is `True` for `p=='{}'` """
    assert len(p) == 2
    assert p in ('()','[]','{}','<>')
    if not isinstance(s, str):
        logger.warning('Cannot parenthesize object %r of type %r',s,type(s))
        return s
    if also_when_empty is None:
        also_when_empty = (p == '{}')
    s = s.strip()
    if not s:
        if also_when_empty :
            return p
        else:
            return s
    else:
        if s[0] != p[0]:
            if s[-1] == p[-1]:
                logger.warning('Unbalanced parentheses in %r ?',s)
            return p[0] + s + p[1]
        else:
            return s

#####################

def get_blobinator_args(blobs_dir):
    # currently they are written in this text file)
    f = osjoin(blobs_dir, '.blob_inator-args.json')
    assert os.path.exists(f), ("File of blob_inator args does not exit: %r\n"%(f,))
    with open(f) as a:
        blobinator_args = json.load(a)
    # these would interfere with proper settings
    import ColDoc.blob_inator
    for k in ColDoc.blob_inator.blob_inator_orig_keys:
        blobinator_args.pop(k, False)
    assert isinstance(blobinator_args,dict)
    return blobinator_args

#####################

def is_image_blob(metadata, content_type):
    " check that this is an image blob"
    return metadata.environ == 'graphic_file' and  content_type is not None \
           and ( content_type.startswith('image/') or content_type in ('application/pdf',) )

#####################

def dict_save_or_del(d,k,v):
    " delete `k` from `d` if `v` is True, otherwise `d[k]=v` "
    if v is True:
        if k in d:
            del d[k]
    else:
        d[k] = v

def json_to_dict(thestr):
    thedict = {}
    try:
        if thestr:
            thedict = json.loads(thestr)
        assert isinstance(thedict, dict)
    except:
        thedict = {}
        logger.exception('While json loading thestr')
    return thedict


def dict_to_json(thedict):
    if not thedict:
        return ''
    return json.dumps(thedict)


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
    @property
    def lang(self):
        return super().get('lang',[''])[0]
    @lang.setter
    def lang(self, lang):
        super().__setitem__('lang', [lang])
    #
    def get_languages(self):
        " return list of languages, correctly formatted"
        L = self.lang.splitlines()
        if any([ (len(z)!=3) for z in L]):
            logger.warning('Malformed languages %r in %s', self.lang, self)
        return [z for z in L if len(z) == 3]


def metadata_html_items(metadata, nick):
        for key,vals in metadata.items():
            vallik = []
            for val in vals:
                link=''
                if  key == 'child_uuid' or key == 'parent_uuid':
                    link="/UUID/{nick}/{val}".format(val=val,nick=nick)
                elif  key ==  'extension' :
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
                lang = ColDoc_lang, accept_lang = {}, 
                metadata_class=FMetadata, coldoc=None, metadata=None):
    """ Choose a blob, trying to satisfy request for language and extension
    returns `filename`, `uuid`, `metadata`, `lang`, `ext`
    possibly following the preferences of `accept_lang`
    if `ext` is None, an extension will be returned following `sort_extensions`
    if `lang` is None, a random language will be returned
    """
    assert blobs_dir is not None
    assert metadata is not None or (uuid is not None and (metadata_class == FMetadata or coldoc is not None))
    assert isinstance(uuid,str) or uuid is None
    assert lang is None or (len(lang) == 3 and slug_re.match(lang))
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
            logger.error('Blob `%r` not available for lang = %r ext = %r : %r', uuid, lang, ext, input_file)
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
    L = copy.copy(m.get_languages())
    if 'mul' in L:
        L = copy.copy(m.coldoc.get_languages())
    #
    if accept_lang:
        L.sort(key = lambda x : accept_lang.get(x,0), reverse=True)
    # as a last resort, try a "no language" choice
    L.append('')
    #
    if lang is not None:
        if lang not in L:
            logger.error('Language %r is not available for uuid %r',lang, uuid)
            raise ColDocException()
        L = [lang]
    #
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
        raise ValueError("UUID %r contains invalid characters" % symbol_string)
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
    assert directory.startswith(prefix), ('dir_to_uuid: directory %r does not start with prefix %r' % (directory, prefix))
    directory = directory[len(prefix):].split(os.path.sep)
    return directory[0] + directory[1] + directory[2]

def file_to_uuid(filename, blobs_dir):
    """given a file or directory, tracks down symlinks,
    returns (UUID, basename)  where `basename` is the filename inside the UUID directory,
    or `None` if `filename` was a directory"""
    assert isinstance(filename, str)
    if len(filename) < 5 :
        raise ValueError('filename too short: %r' % filename)
    blobs_dir = os.path.realpath(blobs_dir)
    if not os.path.isabs(filename):
        filename = os.path.join(blobs_dir,filename)
    # try adding some extensions, to resolve links such as \input{main} -> main.tex
    if not os.path.exists(filename):
        for j in '.tex','.sty':
            if os.path.exists(filename+j):
                filename += j
                break
    filename = os.path.realpath(filename)
    blobs_dir += os.path.sep
    assert filename.startswith(blobs_dir), ('filename %r does not start with %r' %(filename, blobs_dir))
    if os.path.isdir(filename) or filename[-1] == os.pathsep:
        base = None
    else:
        filename, base = os.path.split(filename)
    #
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

# allow point as well
slugp_re = re.compile(r'^[-a-zA-Z0-9_.]+\Z')

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
    """ Create a symbolic link pointing to src named dst. Both must be either relative paths,
    (relative to `basedir`) or subpaths of `basedir`. `target_is_directory` must be set. `force` will delete
    target if it exists and it is a symlink.
    """
    basedir = os.path.normpath(basedir)
    assert os.path.isdir(basedir)
    # make sure `dst` is absolute
    if os.path.isabs(dst):
        dst = os.path.normpath(dst)
        assert dst.startswith(basedir)
    else:
        dst = os.path.abspath(os.path.join(basedir, dst))
    #
    dst_dir = os.path.dirname(dst) #if target_is_directory else
    #
    # make sure `src_abs` is the absolute path
    if os.path.isabs(src):
        src_abs = os.path.normpath(src)
        assert src_abs.startswith(basedir)
    else:
        src_abs = os.path.abspath(os.path.join(basedir, src))
    #  now `src` is relative to `dst_dir`
    src = os.path.relpath(src_abs, dst_dir)
    #
    if not os.path.isdir(dst_dir):
        os.makedirs(dst_dir)
    if force and os.path.islink(dst):
        dstL = os.readlink(dst)
        if dstL != src:
            logger.warning(' substituting symlink %r, was pointing to %r and will point to %r' , dst, dstL, src)
        os.unlink(dst)
    logger.debug(" os.symlink (%r, %r )" % (src, dst) )
    os.symlink(src, dst, target_is_directory=target_is_directory, **kwargs)

############################


def collect_renderer_config(config):
    plastex_dir = os.path.dirname(os.path.realpath(plasTeX.__file__))
    renderers_dir = os.path.join(plastex_dir, 'Renderers')
    renderers = next(os.walk(renderers_dir))[1]
    for renderer in renderers:
        try:
            conf = importlib.import_module('plasTeX.Renderers.'+renderer+'.Config')
        except ImportError as msg:
            continue

        conf.addConfig(config)

def plastex_main(argv):
    """ Main program routine , taken from bin/plastex"""
    import plasTeX
    from argparse import ArgumentParser
    from plasTeX.Compile import run
    from plasTeX.Config import defaultConfig

    config = defaultConfig()
    collect_renderer_config(config)

    parser = ArgumentParser(prog="plasTeX")

    group = parser.add_argument_group("External Configuration Files")
    group.add_argument("--config", "-c", dest="config", help="Config files to load. Non-existent files are silently ignored", action="append")

    config.registerArgparse(parser)

    parser.add_argument("file", help="File to process")

    data = parser.parse_args(argv)
    data = vars(data)
    if data["config"] is not None:
        config.read(data["config"])

    config.updateFromDict(data)

    filename = data["file"]

    run(filename, config)

def plastex_invoke(cwd_, stdout_ , argv_, logfile):
    "invoke plastex with given args.  TODO cache some stuff"
    #
    assert isinstance(stdout_, str)
    with open(stdout_,'w') as f_:
        f_.write('start at %s\n'% (datetime.datetime.isoformat(datetime.datetime.now())))
    #
    exception = None
    if True:
        stdout_d = open(stdout_,'a')
        p = subprocess.Popen(['plastex']+argv_, cwd=cwd_, stdin=open(os.devnull),
                             stdout=stdout_d, stderr=subprocess.STDOUT)
        p.wait()
        stdout_d.write('end at %s\n'% (datetime.datetime.isoformat(datetime.datetime.now())))
        return p.returncode
    # unfortunately this code is unstable, it crashes on long runs
    # (probably the plastex library uses too much memory on repeated calls)
    cwdO = os.getcwd()
    os.chdir(cwd_)
    try:
        with contextlib.redirect_stdout(open(stdout_,'a')):
            plastex_main(argv_)
    except Exception as msg:
        logger.exception('There was an exception running %r internally.', argv_)
        exception = sys.exc_info()
    F = open(stdout_,'a')
    if exception:
        F.write('—' * 80 + '\n')
        F.write('There was an exception running %r internally\n' % argv_)
        traceback.print_exception(*exception, file = F)
        L = open(logfile,'a')
        L.write('—' * 80 + '\n')
        L.write('There was an exception running %r internally\n' % argv_)
        traceback.print_exception(*exception, file = L)
        L.close()
    F.write('end at %s\n'% (datetime.datetime.isoformat(datetime.datetime.now())))
    F.close()
    os.chdir(cwdO)
    return 0 if (exception is None) else 1

############################




def prepare_anon_tree_recurse(blobs_dir, temp_dir, uuid, lang, metadata_class, coldoc):
    " subrouting for `prepare_anon_tree` "
    uuid_dir = uuid_to_dir(uuid, blobs_dir=blobs_dir)
    langs = [lang] if lang is not None else coldoc.get_languages()
    try:
        uuid_, uuid_dir, metadata = resolve_uuid(uuid=uuid, uuid_dir=uuid_dir,
                                                   blobs_dir = blobs_dir,
                                                   metadata_class=metadata_class, coldoc=coldoc)
    except ColDocException:
        uuid_ = None
    if uuid_ is None:
        td = osjoin(temp_dir,uuid_dir)
        os.makedirs(td)
        for ll in langs:
            b = osjoin(td,'blob_' + ll + '.tex')
            with open(b,'w') as f:
                f.write(r'\texttt{[MISSING UUID %r]}\errmessage{UUID %r missing, using fake content}' % (uuid,uuid))
            logger.warning('Created fake %r', b)
        return len(langs)
    #
    ret = 0
    bd = osjoin(blobs_dir,uuid_dir)
    td = osjoin(temp_dir,uuid_dir)
    if os.path.exists(td):
        logger.warning('Already created %r, skipping',td)
        return 0
    os.makedirs(td)
    publ = metadata.get('access')[0] in ('open','public')
    files = os.listdir(bd)
    if '.tex'  in metadata.get('extension'):
        files += [ ('blob_' + ll + '.tex') for ll in langs ]
    for j in  files:
        f = osjoin(bd,j)
        t = osjoin(td,j)
        if  os.path.exists(t):
            continue
        if j == 'metadata':
            ret += 1
            logger.debug('did copy %r',f)
            shutil.copy2(f,t, follow_symlinks=False)
        elif j.startswith('blob'):
            # extract extension
            B,E = os.path.splitext(j)
            # extract language, without underscore
            L = B[5:]
            if lang is not None and L and lang != L:
                # If `lang` is not None, skip any blob that has a language that is not None
                logger.debug('did not copy %r wrong language',f)
                continue
            ret += 1
            if publ and os.path.exists(f):
                try:
                    os.link(f,t)
                    logger.debug('did link %r',f)
                except:
                    logger.debug('could not link , rather copy %r',f)
                    shutil.copy2(f,t, follow_symlinks=False)
            elif  E == '.tex':
                # mask content, preserve tree
                F = open(t,'w')
                a = r'{UNACCESSIBLE UUID %r}' % (uuid,)
                if not os.path.exists(f):
                    F.write(r'\message{UUID %r untranslated, using fake content}' % (uuid,))
                    a = r'{UNTRANSLATED UUID %r}' % (uuid,)
                    logger.warning('Added untranslate stub for UUID %r lang %r', uuid, L)
                F.write('\\uuidplaceholder{%s}{%s}'% (uuid,a))
                for u in metadata.get('child_uuid'):
                    # We include all LaTeX children, to keep tree connectivity
                    sub_metadata = None
                    try:
                        sub_uuid_, sub_uuid_dir, sub_metadata = resolve_uuid(uuid=u, uuid_dir=None,
                                                                         blobs_dir = blobs_dir,
                                                                         metadata_class=metadata_class, coldoc=coldoc)
                    except ColDocException:
                        continue
                    if sub_metadata is not None and '.tex' in sub_metadata.get('extension'):
                        F.write('\\input{%s/blob_%s.tex}'%(sub_uuid_dir,L))
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
        ret += prepare_anon_tree_recurse(blobs_dir, temp_dir, u, lang, metadata_class, coldoc)
    return ret
    

def prepare_anon_tree(coldoc_dir, uuid=None, lang=None,
                      metadata_class=FMetadata, coldoc=None):
    """ copy the whole tree, starting from `uuid`, and masking private content;
    returns `(n,anon)` , where `n` is the number of copied files, and
    `anon` is the anonymous directory (or `None` in case of failure).
    If `lang` is not None, skip any blob that has a language that is not None.
    """
    if uuid is None:
        uuid = '001'
    blobs_dir = osjoin(coldoc_dir, 'blobs')
    assert os.path.isdir(blobs_dir)
    anon_dir = osjoin(coldoc_dir, 'anon')
    temp_dir = tempfile.mkdtemp(dir=coldoc_dir)
    logger.info('Preparing anon tree in %s', temp_dir)
    r = 0
    try:
        r = prepare_anon_tree_recurse(blobs_dir, temp_dir, uuid, lang, metadata_class, coldoc)
        for dirpath, dirnames, filenames in os.walk(blobs_dir,followlinks=False):
            tmp_path = osjoin(temp_dir,dirpath[1+len(blobs_dir):])
            os.makedirs(tmp_path, exist_ok=True)
            for j in (filenames + dirnames):
                src = osjoin(dirpath,j)
                dst = osjoin(tmp_path,j)
                if os.path.islink(src):
                    k = os.readlink(src)
                    r += 1
                    logger.debug('symlink %s -> %s',k,dst)
                    os.symlink(k,dst)
                elif os.path.isfile(src) and j in  ColDoc_anon_copy_paths:
                    shutil.copy2(src,dst, follow_symlinks=False)
                #else:
                #    logger.debug('not symlink %s',src)
        # preserve certain files when rebuilding anon tree
        assert all(isinstance(j,str)  for j in ColDoc_anon_keep_extensions)
        extensions = set(ColDoc_anon_keep_extensions)
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


def recurse_tree(load_metadata_by_uuid, action, uuid='001', seen=None, branch=None, problems=None):
    """ recurse tree starting from `uuid` , for each node call 
    `action(uuid=uuid, metadata=metadata, branch=branch)` which should return a boolean.
    `load_metadata_by_uuid(uuid)` is a function that returns the metadata
    `recurse_tree` will return `and` of all return values of `action`
    """
    if seen == None:
        seen = set()
    if branch is None:
        branch = []
    problems = problems if problems is not None else []
    assert isinstance(seen, set)
    assert isinstance(branch, list)
    return recurse_tree__(load_metadata_by_uuid, action, uuid, seen, branch, problems)


def recurse_tree__(load_metadata_by_uuid, action, uuid, seen, branch, problems):
    """ you may want to see `recurse tree`"""
    #
    try:
        metadata = load_metadata_by_uuid(uuid)
    except Exception as e:
        s = ('Exception %r when loading UUID %r')
        logger.error(s, e, uuid)
        ## nope
        #problems.append(('MISSING_UUID',uuid,s,uuid))
        ## by returning None, the caller will add to `problems`
        return None
    #
    if uuid in branch:
        logger.warning("loop detected along branch %r",branch)
    #
    b = copy.copy(branch)
    b.append(uuid)
    #
    ret = action(uuid=uuid, metadata=metadata, branch=branch)
    #
    if uuid not in seen:
        seen.add(uuid)
        for u in metadata.get('child_uuid'):
            ## disabled, to speed up
            #logger.debug('moving down '+('→'*len(branch))+'from node %r to node %r',uuid,u)
            r = recurse_tree__(load_metadata_by_uuid, action, uuid=u, seen=seen, branch=b,problems=problems)
            if r is None:
                s = _('Missing child %(child)r of UUID %(uuid)s')
                a = { 'child' : u , 'uuid' : uuid }
                logger.error(s % a)
                problems.append(('MISSING_CHILD',uuid,s,a))
                r = False
            #
            ret = ret and r
    else:
        logger.warning("skipping duplicate node %r", uuid)
    return ret

############################


def reparse_blob(filename, metadata, lang, blobs_dir, warn=None, act=True, ignore_uuid=True, load_uuid=None):
    " reparse a blob to extract and update all metadata ; `warn(s,a)` is a function where `s` is a translatable string, `a` its arguments"
    if warn is None:
        def warn(s,a):
            logger.warning(s % a)
    #
    options =  get_blobinator_args(blobs_dir)
    #
    from ColDoc.transform import reparse_metadata
    parsed_back_map, parsed_metadata, errors = reparse_metadata(filename, metadata, lang, blobs_dir, options, load_uuid=load_uuid)
    for s,a in errors:
        warn(s, a)
    #
    # insert changes regarding children
    old_children = metadata.get('child_uuid')
    old_children_set = set(old_children)
    if act:
        del metadata['child_uuid']
        new_children_set = set()
        for childuuid in parsed_back_map:
            # TODO fixme this is useless, parsed_back_map is a dict
            #if childuuid in new_children_set:
            #    warn(_('In UUID %(uuid)r the child %(childuuid)r is referenced twice') ,
            #         {'uuid':metadata.uuid,'childuuid':childuuid})
            #else:
            metadata.add('child_uuid',childuuid)
            new_children_set.add(childuuid)
    else:
        new_children_set = set(parsed_back_map)
    #
    if old_children_set != new_children_set:
        if old_children_set.difference(new_children_set):
            warn(_('Warning connection to these children was disconnected: %r'), (old_children_set.difference(new_children_set),))
        if new_children_set.difference(old_children_set):
            warn(_('New connection to these children: %r'), (new_children_set.difference(old_children_set),))
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
            warn(_('Deleted metadata: %r'),(old_metadata_set.difference(new_metadata_set),))
        if new_metadata_set.difference(old_metadata_set):
            warn(_('New metadata: %r'),(new_metadata_set.difference(old_metadata_set),))
    #
    if act:
        for key in metadata.keys():
            if key.startswith('M_') or key.startswith('S_'):
                del metadata[key]
        for key, value in parsed_metadata:
            if key == 'M_uuid':
                if value != ('{'+metadata.uuid+'}'):
                    warn(_('Warning: there is a `uuid` command with value %(value)s instead of {%(uuid)s}'),
                         {"value":value,'uuid':metadata.uuid})
                if not ignore_uuid:
                    metadata.add(key,value)
            else:
                metadata.add(key,value)
    metadata.save()

############################

re_document_class = re.compile(r'^[ \t]*\\documentclass')
re_document = re.compile(r'^[ \t]*\\begin{document}')
re_uuid = re.compile(r'^[ \t]*\\uuid')
re_comment = re.compile(r'^[ \t]*%')
re_emptyline = re.compile(r'^[ \t]*$')
re_section = re.compile(r'^[ \t]*\\section')

def split_blob(blob):
    " split LaTeX document in prologue, preamble, body, epilogue "
    if isinstance(blob,str):
        blob = blob.splitlines(keepends = True)
    if isinstance(blob, (tuple,list)):
        blob = iter(blob)
    prologue = []
    preamble = []
    body = []
    epilogue = []
    try:
        while True:
            a = next(blob)
            if re_comment.match(a) or re_emptyline.match(a):
                prologue.append(a)
            else:
                break
        if re_document_class.match(a) or re_uuid.match(a) or re_section.match(a):
            try:
                i = a.index('}')
                prologue.append(a[:(i+1)])
                if re_document_class.match(a):
                    preamble.append(a[(i+1):])
                else:
                    prologue.append(a[(i+1):])
            except ValueError:
                logger.warning('No "}" in %r',a)
                prologue.append(a)
        else:
            body.append(a)
        while True:
            body.append(next(blob))
    except StopIteration:
        pass
    while body and ( re_comment.match( body[-1]) or re_emptyline.match( body[-1]) ):
        epilogue.insert(0,body.pop())
    j = [bool(re_document.match(j)) for j in body]
    if any(j):
        if not preamble:
            logger.warning('\\documentclass without \\begin{document}')
        i = j.index(True)
        preamble += body[:(i)]
        body = body[(i):]
    return prologue, preamble, body, epilogue

############################

class tree_environ_helper(object):
    " checks some consistencies rules"
    #
    env_not_star = ['document' , 'thebibliography']
    #
    def __init__(self, blobs_dir, parent=None):
        self.scan_E(blobs_dir)
        if parent is not None:
            self.set_parent(parent)
        else:
            self._parent = None
    #
    def scan_E(self, blobs_dir):
        "prepare internal list of begin...end environments, but for `document`"
        choices = []
        children = []
        try:
            blobinator_args = get_blobinator_args(blobs_dir)
        except:
            logger.error("File of blob_inator args does not exit: %r\n"%(f,))
        else:
            for a in (blobinator_args['split_environment'] + blobinator_args['split_list']):
                if a  not in self.env_not_star :
                    choices.append(( 'E_'+a , '\\begin{'+a))
                    children.append('E_'+a)
        self.E_choices = sorted(choices)
        self.E_children = sorted(children)
    #
    def set_parent(self, parent):
        " parent=`False` means that there is no parent , the only 'child' can be 'main_file' "
        if parent is False:
            self._parent = False
            return
        assert isinstance(parent,str)
        assert parent.startswith('E_') or parent in ColDoc_environments
        if parent.startswith('E_') and parent[2:] not in self.env_not_star:
            parent = 'E_*'
        self._parent = parent
        logger.debug('parent coded as %r',parent)
    #
    def child_is_allowed(self, child, parent=None, extension=None):
        """ checks if the environ `child` can be child of `parent`
         parent=`False` means that there is no parent i.e. child== `main_file` 
         `extension` may be a list or tuple of extensions, or a string,
         it is related to the child
         """
        if extension is not None:
            if isinstance(extension,(list,tuple)):
                if len(extension) != 1:
                    logger.debug(' len != 1  %r',extension)
                    return child == 'graphic_file'
                extension = extension[0]
            else:
                assert isinstance(extension,str)
            if extension not in ColDoc_latex_mime:
                logger.debug(' not latex  %r',extension)
                return child == 'graphic_file'
        if parent is False:
            return child == 'main_file'
        if parent is not None:
            self.set_parent(parent)
        else:
            assert self._parent is not None , "Call `set_parent` to initialize"
        assert isinstance(child,str)
        assert child.startswith('E_') or child in ColDoc_environments
        if child.startswith('E_') and child[2:] not in self.env_not_star:
            if child not in self.E_children:
                logger.warning('Should not get this child environ: '+child)
                return False
            child = 'E_*'
        if extension in ColDoc_latex_mime and child not in ColDoc_latex_mime[extension]:
            logger.debug('test link c %r p %r ext %r -> %r'%(child,self._parent,extension,False))
            return False
        r = child in ColDoc_environments_parent_child[self._parent]
        logger.debug('test link c %r p %r ext %r -> %r'%(child,self._parent,extension,r))
        return r
    #
    def iter_allowed_choices(self, parent=None, extension=None):
        if parent is False:
            yield ('main_file','main_file',)
            return
        if extension is not None:
            if isinstance(extension,(list,tuple)):
                if len(extension) != 1:
                    yield ('graphic_file','graphic_file')
                    return
                extension = extension[0]
            assert isinstance(extension,str)
            if extension not in ColDoc_latex_mime:
                yield ('graphic_file','graphic_file')
                return
            allowed_by_mime =  ColDoc_latex_mime[extension]
        else:
            allowed_by_mime =  True
        if parent is not None:
            self.set_parent(parent)
        assert self._parent is not None , "Call `set_parent` to initialize"
        for child in ColDoc_environments_parent_child[self._parent]:
            if  allowed_by_mime is not True and (not (child in allowed_by_mime)):
                logger.debug('not allowed by mime %r %r',child,child)
                continue
            if child == 'E_*':
                for z in self.E_choices:
                    logger.debug('allowed %r',z)
                    yield z
            else:
                yield (child,child)
                logger.debug('allowed %r %r',child,child)
    #
    def list_allowed_choices(self, parent=None, extension=None):
        return list(self.iter_allowed_choices(parent,extension))
    #
    def list_allowed_children(self):
        for a,b in self.list_allowed_choices():
            yield a
    #
    def list_all_choices(self):
        yield ('','')
        for child in ColDoc_environments:
            yield (child,child)
        for z in self.E_choices:
            yield z
    #
    def list_all_children(self):
        for a,b in self.list_all_choices():
            yield a
    #

#############
    
def parent_cmd_env_child(parent_uses_env, parent_uses_cmd, child_env, split_graphic, allowed_parenthood):
    "checks if it is ok that the parent includes the child using command  `parent_uses_cmd` inside environ `parent_uses_env` and the child has env `child_env`"
    E_type = child_env.startswith('E_')
    wrong = False
    if  E_type:
        if parent_uses_cmd != 'input':
            wrong = True
        if ( child_env != 'E_thebibliography' ):
            if  child_env != parent_uses_env:
                if parent_uses_env in allowed_parenthood:
                    wrong = child_env not in allowed_parenthood[parent_uses_env]
                else:
                    wrong = True
    else:
        if child_env == 'graphic_file':
            wrong = parent_uses_cmd not in split_graphic
        else:
            if parent_uses_cmd == child_env:
                wrong = parent_uses_cmd not in ('usepackage','bibliography','include','input')
            else:
                wrong = parent_uses_cmd not in ('input','include')
    return wrong

################################

def to_bytes(s):
    return s.encode(errors='ignore') if isinstance(s,str) else bytes(s)

def hash_tree(S, thehash = hashlib.md5):
    " returns an hash of the contents of the directory S, or of the file S if it is a file"
    H = thehash()
    sep = b'\x00'
    H.update(b'START:' + sep)
    #
    def recurse(p, n = None):
        if os.path.isfile(p):
            if n is not None:
                H.update(sep + b'FILE:' + n + sep)
            H.update(open(p,'rb').read())
        elif os.path.isdir(p):
            if n is not None:
                H.update(sep + b'SUBDIR:' + n + sep)
            for l in sorted(os.listdir(p)):
                k = osjoin(p,l)
                recurse(k, to_bytes(l))
        elif os.path.islink(p):
            r = os.readlink(p)
            if '..' in p.split(os.sep):
                logger.warning('This link is reentrant! %r → %r', p,r)
            if n is not None:
                H.update(sep + b'LINK:' + n + sep)
            H.update(sep + b'LINKDST:' + to_bytes(r) + sep)
        else:
            H.update(sep + b'OTHER:' + to_bytes(str(os.stat(p))) + sep)
            logger.warning('TODO cannot properly hash %r', p)
    #
    recurse(S)
    dig = H.hexdigest()
    return dig


def replace_with_hash_symlink(base_dir, src_dir , dedup_dir , obj):
    """ inside `base_dir` there is a directory `src_dir` that contains an `obj`
    (either a file or a directory containing only files)
    then an appropriate directory/file named `dedup` is created inside `dedup_dir`
    where the content is moved and a symlink is created in its place; if successful, it returns  `dedup`.
    Both  `src_dir` , `dedup_dir` must be non-absolute paths or otherwise subpaths of `base_dir`
    """
    assert os.path.isabs(base_dir)
    base_dir = os.path.normpath(base_dir)
    #
    if os.path.isabs(src_dir):
        src_dir_abs =  os.path.normpath(src_dir)
        assert src_dir_abs.startswith(base_dir)
        src_dir = os.path.relpath(src_dir_abs, base_dir)
    #
    if os.path.isabs(dedup_dir):
        dedup_dir_abs =  os.path.normpath(dedup_dir)
        assert dedup_dir_abs.startswith(base_dir)
        dedup_dir = os.path.relpath(dedup_dir_abs, base_dir)
    #
    if not os.path.isdir(dedup_dir): os.makedirs(dedup_dir)
    # symlink common files
    S = osjoin(src_dir_abs, obj)
    if os.path.islink(S):
        a = os.readlink(S)
        a,b = os.path.split(a)
        # fixme should check if it is inside dst
        return b
    # check if known
    dig = hash_tree(S)
    a,b = os.path.splitext(obj)
    dedup = a + '--' + dig + b
    D = osjoin(dedup_dir_abs, dedup)
    if os.path.isdir(S):
        if not os.path.exists(D):
            shutil.copytree(S,D)
        else: assert os.path.isdir(D)
        shutil.rmtree(S)
        os_rel_symlink(D, S, base_dir, target_is_directory=True)
    elif os.path.isfile(S):
        if not os.path.exists(D):
            shutil.copy2(S,D)
        else: assert os.path.isfile(D)
        os.unlink(S)
        os_rel_symlink(D, S, base_dir, target_is_directory=False)
    return dedup

##################


def recreate_symlinks(metadata, blobs_dir):
    """ metadata.original_filename starting with'/' is either '/preamble.tex' or '/document.tex' and we create language symlinks for it  """
    a = metadata.get('original_filename')
    if len(a) != 1:
        return
    a = a[0]
    if  a and a[0] == '/' and a[-4:] == '.tex':
        a = a[1:-4]
        langs = metadata.get_languages()
        ud = uuid_to_dir(metadata.uuid)
        if 'mul' in langs and not isinstance(metadata, FMetadata):
            # `mul` documents are not supported outside of Django
            langs = metadata.coldoc.get_languages()
        for l in langs:
            al_link = osjoin(ud, 'blob_' + l + '.tex')
            al_src = osjoin(blobs_dir, a + '_' + l + '.tex')
            if os.path.islink(al_src):
                if os.readlink(al_src) != al_link:
                    logger.error('symlink %r -> %r does not point to %r',
                                 al_src, os.readlink(al_src), al_link)
                try:
                    u, b = file_to_uuid(os.readlink(al_src), blobs_dir)
                except:
                    u = None
                if u != metadata.uuid:
                    logger.error('symlink %r -> %r does not point to UUID %r but to UUID %r',
                                 al_src, os.readlink(al_src), metadata.uuid, u)
                else:
                    logger.debug('symlink %r correctly points to %r', al_src, u)
            elif os.path.exists(al_src):
                logger.error('Is not a symlink: %r', al_src)
            else:
                os.symlink(al_link, al_src)

###################

def html2text(some_html_string):
    " https://stackoverflow.com/a/39899612/5058564 "
    #return '\n'.join(BeautifulSoup(some_html_string, "html.parser").findAll(text=True))
    return ' '.join(BeautifulSoup(some_html_string, "html.parser").stripped_strings)

################### 

def multimerge(sources):
    """ `sources` is a dictionary , where each value is a list ;
    `output` is a list of pairs (key,value) , where `key` is
    a `key` from `strings.
    
     This algorithm will put in `output` all elements of all lists in
     `sources` , labelling them with `key`.
     
     Warning: `sources` will be destroyed.
    """    
    output = []
    assert isinstance(sources, dict)
    assert all(isinstance(sources[z], list) for z in sources)
    sources = {z:sources[z] for z in sources if sources[z]}
    while sources:
        newsources = {}
        for ll in sources:
            L = sources[ll]
            a = L.pop(0)
            if L:
                newsources[ll] = L
            output.append( (ll , a) )
        sources = newsources
    return output

def multimerge_lookahead(sources, keyequal, depth=32, alsoempty = True):
    """ `sources` is a dictionary , where each value is a list ;
    `output` is a list of pairs (key,value) , where `key` is either
       a `key` from `strings` or `keyequal` .
    
     This algorithm will put in `output` all elements of all lists in
     `sources` , labelling them with `key` , or `keyequal`
     when the same element is found in all `sources`;
     it will try to maximize the number of equal elements.
     
     Warning: `sources` will be destroyed.
    """
    output = []
    assert isinstance(sources, dict)
    assert all(isinstance(sources[z], list) for z in sources)
    sources = {z:sources[z] for z in sources if sources[z]}
    while len(sources) > 1:
        firstlines = [z[0] for z in sources.values()]
        # first lines are all equal, this is very good, pop them all
        if len(set(firstlines)) == 1 :
            output.append((keyequal , firstlines[0]))
            for ll in list(sources.keys()):
                L = sources[ll]
                L.pop(0)
                if L:
                    sources[ll] = L
                else:
                    del sources[ll]
        # firstlines are not all equal
        else:
            howfar = []
            for ll in sources:
                thisfirstline = sources[ll][0]
                # for lines that are significant
                if alsoempty or thisfirstline.strip():
                    for zz in sources:
                        if zz != ll:
                            # look ahead in all other sources to find a copy
                            othersource = sources[zz][1:depth]
                            try:
                                I = othersource.index(thisfirstline)
                            except ValueError:
                                howfar.append(( depth + 1 , zz,ll))
                            else:
                                howfar.append((I, zz,ll))
            if howfar:
                howfar.sort()
                # get a line so that the nearest copy gets even nearer
                nfl = howfar.pop(0)[1]
            else:
                lengths = [ (-len(sources[z]),z) for z in sources]
                lengths.sort()
                nfl = lengths.pop()[1]
            # pop it
            L = sources[nfl]
            a = L.pop(0)
            if L:
                sources[nfl] = L
            else:
                del sources[nfl]
            output.append( (nfl , a) )
    # only one source remaining, output it all
    if sources:
        for ll in sources:
            for line in sources[ll]:
                output.append( (ll , line ))
    return output

################### replacements by regular expressions

def replace_language_in_inputs(string,oldlang,newlang):
    " if oldlang is None, replace all languages (but this is a bad idea)"
    assert oldlang is None or len(oldlang) == 3 
    assert len(newlang) == 3
    if oldlang is  None:
        oldlang = '\w\w\w'
    pattern = '{UUID/(\w+)/(\w+)/(\w+)/blob_(' + oldlang + ').(\w\w+)}'
    replacement = '{UUID/\g<1>/\g<2>/\g<3>/blob_' + newlang + '.\g<5>}'
    string = re.sub(pattern ,replacement, string)
    #
    pattern = '{UUID/(\w+)/(\w+)/(\w+)/blob_(' + oldlang + ')}'
    replacement = '{UUID/\g<1>/\g<2>/\g<3>/blob_' + newlang + '}'
    string = re.sub(pattern ,replacement, string)
    #
    pattern = '{SEC/([^/]+)/blob_(' + oldlang + ').(\w\w+)}'
    replacement = '{SEC/\g<1>/blob_' + newlang + '.\g<3>}'
    string = re.sub(pattern ,replacement, string)
    #
    pattern = '{SEC/([^/]+)/blob_(' + oldlang + ')}'
    replacement = '{SEC/\g<1>/blob_' + newlang + '}'
    string = re.sub(pattern ,replacement, string)
    #
    return re.sub(pattern ,replacement, string)

def strip_language_lines(string, thelang , header = ColDoc_language_header_prefix):
    " delete all lines with wrong language header"
    if not header:
        # no processing
        return string
    assert len(thelang) == 3
    lines = string.splitlines()
    newlines = []
    correctheader = header + thelang
    N = len(correctheader)
    for l in lines:
        r = l.lstrip()
        if r.startswith(correctheader):
            newlines.append(r[N:])
        elif not r.startswith(header):
            if header in l:
                logger.warning('misplaced language header')
                l += '%misplaced language header'
            newlines.append(l)
    return '\n'.join(newlines)+'\n'

def line_without_language_lines(text, line, thelang , header = ColDoc_language_header_prefix):
    " count how many lines matching `thelang` there are before line n=`line` (starting from zero)"
    assert isinstance(line,int)
    if isinstance(text, str):
        text = text.splitlines()
    if not header:
        # no processing
        return line
    assert len(thelang) == 3
    newline = 0
    correctheader = header + thelang
    for l in text:
        r = l.lstrip()
        if r.startswith(correctheader):
            newline += 1
        elif not r.startswith(header):
            newline += 1
        line -= 1
        if line < 0:
            return newline
    return newline

def line_with_language_lines(text, line, thelang , header = ColDoc_language_header_prefix):
    " count n=`line` lines matching `thelang` and return the line where it stopped"
    assert isinstance(line,int)
    if isinstance(text, str):
        text = text.splitlines()
    if not header:
        # no processing
        return line
    assert len(thelang) == 3
    newline = 1
    correctheader = header + thelang
    for l in text:
        r = l.lstrip()
        if r.startswith(correctheader):
            line -= 1
        elif not r.startswith(header):
            line -= 1
        if line <= 0:
            return newline
        newline += 1
    return newline


def gen_lang_metadata(metadata, blobs_dir, coldoc_languages):
    " call 'recreate_symlinks' ; for `mul` blobs : create all language versions "
    # just in case
    recreate_symlinks(metadata, blobs_dir)
    #
    languages = metadata.get_languages()
    if 'mul' not in languages:
        return
    uuid = metadata.uuid
    src = osjoin(blobs_dir, uuid_to_dir(uuid), 'blob_mul.tex')
    if not os.path.isfile(src):
        logger.error('is not a file: %r',src)
        return
    string = open(src).read()
    for lang in coldoc_languages:
        if lang in ('mul','zxx','und'):
            continue
        string2 = strip_language_lines(string, lang)
        string3 = replace_language_in_inputs(string2, 'mul', lang)
        dst = osjoin(blobs_dir, uuid_to_dir(uuid), 'blob_' + lang + '.tex')
        try:
            with open(dst,'w') as f_:
                f_.write('%% this content was automatically generated from %r\n%% ********** DO NOT EDIT *********** \n' % src)
                f_.write(string3)
        except:
            logger.exception(dst)
        else:
            logger.debug(' src %r dst %r',src,dst)


def gen_lang_coldoc(COLDOC_SITE_ROOT, coldoc_nick):
    " "
    #
    from ColDoc.utils import slug_re
    assert isinstance(coldoc_nick,str) and slug_re.match(coldoc_nick), coldoc_nick
    coldoc_dir = osjoin(COLDOC_SITE_ROOT,'coldocs', coldoc_nick)
    assert os.path.exists(coldoc_dir), ('Does not exist coldoc_dir=%r\n'%(coldoc_dir))
    #
    blobs_dir = osjoin(coldoc_dir, 'blobs')
    assert os.path.exists(blobs_dir), ('Does not exist blobs_dir=%r\n'%(blobs_dir))
    #
    from ColDocApp.models import DColDoc
    coldoc = DColDoc.objects.get(nickname = coldoc_nick)
    coldoc_languages = coldoc.get_languages()
    #
    #
    from UUID.models import DMetadata
    for metadata in DMetadata.objects.filter(coldoc = coldoc):
        gen_lang_metadata(metadata, blobs_dir, coldoc_languages)

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
    elif len(sys.argv) > 1 and sys.argv[1] == 'split_blob':
        F = (sys.argv[2]) if (len(sys.argv) > 2) else os.path.join(os.path.dirname(sys.argv[0]),'../test/paper/paper.tex')
        p,r,b,e = split_blob(open(F))
        if '-v' in sys.argv:
            print('prologue\n> ',end='')
            print('> '.join(p))
            print('preamble\n> ',end='')
            print('> '.join(r))
            print('body\n> ',end='')
            print('> '.join(b))
            print('epilogue\n> ',end='')
            print('> '.join(e))
        s = ''
        for j in p,r,b,e:
            s += ''.join(j)
        import tempfile
        t = tempfile.NamedTemporaryFile(delete=False)
        t.write(s.encode())
        t.close()
        r = os.system('diff -us %r %r'%(t.name,F))
        os.unlink(t.name)
        sys.exit(r)
    elif len(sys.argv) > 1 and sys.argv[1] in ( 'multimerge' , 'multimerge_lookahead'):
        sources = {}
        A = sys.argv[2:]
        m = max(len(a) for a in A)
        for ll in A:
            sources[ll.ljust(m+1) ] = open(ll).read().splitlines()
        if sys.argv[1] == 'multimerge':
            output = multimerge(sources)
        else:
            output = multimerge_lookahead(sources, '=' * m + ' ')
        output = [ (''.join(a)) for a in output ]
        sys.stdout.write('\n'.join(output)+'\n')
        sys.exit(0)
    else:
        print(""" Commands:
%s test_uuid
  
  prepare_anon coldoc_dir

  split_blob FILENAME

  multimerge  FILES

  multimerge_lookahead  FILES

""" % (sys.argv[0],))


