
import logging
logger = logging.getLogger(__name__)

from ColDoc import transform

from UUID.models import ExtraMetadata

class squash_helper_ref(transform.squash_input_uuid):
    "convert refs"
    __macros_refs = ('eqref','ref','pageref')
    def __init__(self, coldoc, *v, **k):
        self.coldoc = coldoc
        super().__init__(*v, **k)
    def process_macro(self, macroname):
        r = super().process_macro(macroname)
        if r is not None:
            return r
        if macroname not in self.__macros_refs:
            return None
        label = self.thetex.readArgument(type=str)
        # shortcircuit labels where UUID is evident
        if label.startswith('UUID:'):
            a = label[5:].strip()
            return '\\uuidplaceholder{%s}{%s}' % (a,a)
        #
        label = '{' + label + '}'
        blob = None
        key = None
        logger.debug('searching label %r',label)
        for j in ExtraMetadata.objects.filter(value=label):
            if j.blob.coldoc == self.coldoc and j.key.endswith('M_label') and\
               self.metadata.uuid != j.blob.uuid : # no need to rewrite refs inside the same blob
                if blob is not None:
                    logger.warning('duplicate label %r in %r and in %r',
                                   label,blob,j.blob)
                blob = j.blob
                key = j.key
        if blob is None:
            # fixme, you cannot stack other actions over this
            # maybe should push back tokens in thetex
            return '\\'+macroname+label
        if key != 'M_label':
            # TODO this will link to any label inside the blob,
            # w/o specifying if it is the main label of the blob,
            # or if it is a label inside another envi the blob
            logger.warning('TODO cannot properly reference from [%s] \\%s%s to key %r inside [%s]',
                           self.metadata.uuid , macroname, label ,
                           key , blob.uuid)
        a = '\\uuidplaceholder{%s}{%s}' % (blob.uuid, blob.uuid)
        logger.debug('convert %s%s  to %s',macroname,label,a)
        return a
