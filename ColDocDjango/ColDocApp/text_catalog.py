
from django.db import transaction
from django.db.models import Q


import logging
logger = logging.getLogger(__name__)

import ColDocApp.models

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
    O = O.filter(Q(text__contains=searchtext))
    return O.all()
