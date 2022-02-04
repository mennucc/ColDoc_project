import requests, uuid, json, sys

import logging
logger = logging.getLogger(__name__)

from ColDoc.utils import iso3lang_to_iso2

def translator_Azure(text, fromlang, tolang, subscription_key, location):
    fromlang = iso3lang_to_iso2(fromlang)
    tolang = iso3lang_to_iso2(tolang)
    
    endpoint = "https://api.cognitive.microsofttranslator.com"
    
    path = '/translate'
    constructed_url = endpoint + path
    
    params = {  
        'api-version': '3.0',
        'from': fromlang,
        'to': [tolang,]
    }
    constructed_url = endpoint + path
    
    headers = {
        'Ocp-Apim-Subscription-Key': subscription_key,
        'Ocp-Apim-Subscription-Region': location,
        'Content-type': 'application/json',
        'X-ClientTraceId': str(uuid.uuid4())
    }
    
    # You can pass more than one object in body.
    body = [{
        'text': text,
    }]
    
    request = requests.post(constructed_url, params=params, headers=headers, json=body)
    response = request.json()
    if isinstance(response, (list,tuple)):
        if len(response) != 1:
            sys.stderr.write('Len %d for response ??:\n  %r\n' % (len(response),response) )
        response = response[0]
    if isinstance(response, dict):
        translations = response['translations']
        if isinstance(translations, (list,tuple)):
            for T in translations:
                newtext = T['text']
                if T['to'] != tolang:
                    logger.warning('Language %r for response ??:\n  %r\n' % (translations['to'], ))
                else:
                    return newtext
    raise Exception('Failed translation %r %r %r' % (text, fromlang, tolang))
