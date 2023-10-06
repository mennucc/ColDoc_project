import os
from os.path import join as osjoin

from django.db import transaction
from django.db.models import Q


import logging
logger = logging.getLogger(__name__)

import ColDocApp.models
import UUID.models
import ColDoc.utils

Text_Catalog = UUID.models.Text_Catalog


def  update_text_catalog_for_uuid(html_input , text_output , blob=None, coldoc=None, uuid=None, lang=None, *kk, **vv ):
    if blob is None:
        blob = UUID.models.DMetadata.objects.filter(coldoc=coldoc, uuid=uuid).get()
    else:
        if coldoc is not None and coldoc != blob.coldoc:
            logger.warning('internal discrepancy 304vna')
        if uuid is not None and coldoc != blob.uuid:
            logger.warning('internal discrepancy 30Bvna')
    with transaction.atomic():
        Text_Catalog.objects.filter(blob=blob, lang=lang).delete()
        for line, text in enumerate(open(text_output)):
            Text_Catalog(blob=blob, lang=lang, text=text, line=line).save()

def  search_text_catalog(searchtext, coldoc, uuid=None, lang=None ):
    O = Text_Catalog.objects.filter(blob__coldoc=coldoc)
    if uuid is not None:
        O = O.filter(blob__uuid=uuid)
    if lang is not None:
        O = O.filter(lang=lang)
    O = O.filter(Q(text__icontains=searchtext))
    return O.all()

def create_text_catalog(coldoc, blobs_dir):
    Clangs = coldoc.get_languages()
    for blob in UUID.models.DMetadata.objects.filter(coldoc=coldoc) :
        langs = blob.get_languages()
        if 'mul' in langs:
            langs = Clangs
        d =  ColDoc.utils.uuid_to_dir(blob.uuid, blobs_dir)
        for lang in langs:
            a = osjoin(blobs_dir,d,'view_' + lang + '_html.txt')
            if os.path.isfile(a):
                update_text_catalog_for_uuid(html_input=None , text_output=a , blob=blob, lang=lang)
