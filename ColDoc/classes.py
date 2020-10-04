""" Base classes for ColDoc
We do not use `abc` since Django plays too much magick in `Models`
"""

import pathlib


class DuplicateLabel(ValueError):
    """ Duplicate LaTeX label """
    def __init__(self, *args, **kwargs):
        pass

class MetadataBase(object):
    """ a base class for blob's metadata .
    """
    # these are expected to be single valued
    _single_valued_keys = ('uuid','environ')
    ########### create / initialize save
    def __init__(self, basepath=None, *args, **kwargs):
        assert basepath is None or isinstance(basepath, (str, pathlib.Path)),\
               "basepath %r as type unsupported %r"%(basepath,type(basepath))
        self._basepath = basepath
    #
    @property
    def basepath(self):
        return self._basepath
    #
    @classmethod
    def load_by_file(cls, filename):
        "Returns an instance, reading from a file. This should be used only for testing"
        raise NotImplementedError
    @classmethod
    def load_by_uuid(cls, uuid, coldoc=None, basepath=None):
        " returns an instance that matches the `uuid` in the `coldoc` or in the `basepath`"
        raise NotImplementedError
    #
    def save(self, filename=None):
        "saves data, optionally in a file"
        raise NotImplementedError
    ################# manipulate data
    ##
    def get(self,key, default=[None]):
        "returns a list of all values associated to `key` ; it returns the list even when `key` is known to be singlevalued"
        raise NotImplementedError
    #
    def __getitem__(self,key):
        "returns a list of all values associated to `key` ; it returns the list even when `key` is known to be singlevalued"
        raise NotImplementedError
    #
    def __setitem__(self,key,value):
        " set value `value` for `key` (as one single value, even if multivalued)"
        raise NotImplementedError
    #
    def singled_items(self):
        " yields all (key,value) pairs, where each `key` may be repeated multiple times"
        raise NotImplementedError
    #
    def add(self,key, value):
        """ if `key` is single-valued, set `key` to `value`; it `key` is multiple-valued,
        adds a `value` for `key` (only if the value is not present); """
        raise NotImplementedError
    ##
    #def set(self,key, value):
    #    "sets this value for `key`"
    #    raise NotImplementedError
    #
    def __delitem__(self,key):
        "delete all values for `key`"
        raise NotImplementedError
    #
    def delete(self,k,v):
        "delete a key/value"
        raise NotImplementedError
    ################ convenience property to obtain values
    @property
    def coldoc(self):
        "returns the ColDoc (a class implementing `AbstractColDoc` , or the `nickname` as a str )"
        raise NotImplementedError
    @property
    def uuid (self):
        "returns the `uuid` as `str` or `int`"
        raise NotImplementedError
    @property
    def environ(self):
        "returns the environ, as `str`"
        raise NotImplementedError
    @property
    def extension(self):
        "returns a list of extensions (that encode the file type) available for this blob"
        raise NotImplementedError
    @property
    def lang(self):
        "returns a list of languages available for this blob"
        raise NotImplementedError
    #@property
    #def lang_ext(self):
    #    "returns a list of languages and extensions available for this blob; each is a string; language and extension are separated by '/'"
    #    raise NotImplementedError
    @property
    def child_uuid(self):
        "returns a list of children of this blob: a list of strings or integers "
        raise NotImplementedError
    @property
    def parent_uuid(self):
        "returns a list of parents of this blob: a list of strings or integers (usually, 0 or 1 item)"
        raise NotImplementedError

