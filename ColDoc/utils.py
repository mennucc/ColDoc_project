
import itertools, sys, os, io, copy, logging, shelve, unicodedata, re
import os.path
from os.path import join as osjoin

import ColDocLogging

import logging

logger = logging.getLogger(__name__)

from config import *


__all__ = ( "slugify", "uuid_to_dir", "dir_to_uuid",
            "uuid_check_normalize", "uuid_to_int", "int_to_uuid", "new_uuid",
            "new_section_nr" , "uuid_symlink", "os_rel_symlink")

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
        raise ValueError("string '%s' contains invalid characters" % norm_string)
    return norm_string

def uuid_to_int(symbol_string):
    """  normalize `symbol_string`, check that it is a valid UUID, and convert to integer  """
    symbol_string = uuid_check_normalize(symbol_string)
    number = 0
    for symbol in symbol_string:
        number = number * base + decode_symbols[symbol]
    return number




#####################

def uuid_to_dir(u, blobs_dir = ColDoc_as_blobs, create = False):   #, ColDocContent = ColDocContent):
    " returns directory for UUID (relative to `blobs_dir`); it is a two-level dir/dir/ ; if `create` then both levels are created here"
    assert type(u) == str and len(u) >= 3
    assert os.path.isdir(blobs_dir)
    #d = ColDocContent
    #pieces =  'UUIDs',u[-1],u[:-1]
    d = 'UUID'
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
    if force and os.path.islink(dst):
        logger.warning(' substituting symlink %r' % dst)
        os.unlink(dst)
    logger.debug(" os.symlink (%r, %r )" % (src, dst) )
    os.symlink(src, dst, target_is_directory=target_is_directory, **kwargs)
