import os
from os.path import join as osjoin

from django.db import transaction
from django.db.models import Q


import logging
logger = logging.getLogger(__name__)

import ColDocApp.models
import UUID.models
import ColDoc.utils

Text_Catalog = ColDocApp.models.Text_Catalog


def  update_text_catalog_for_uuid(html_input , text_output , coldoc, uuid, lang, *kk, **vv ):
    with transaction.atomic():
        Text_Catalog.objects.filter(coldoc=coldoc, uuid=uuid, lang=lang).delete()
        for line in open(text_output):
            Text_Catalog(coldoc=coldoc, uuid=uuid, lang=lang, text=line).save()

def  search_text_catalog(searchtext, coldoc, uuid=None, lang=None ):
    O = Text_Catalog.objects.filter(coldoc=coldoc)
    if uuid is not None:
        O = O.filter(uuid=uuid)
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
                update_text_catalog_for_uuid(html_input=None , text_output=a , coldoc=coldoc, uuid=blob.uuid, lang=lang)
