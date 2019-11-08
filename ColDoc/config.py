import os.path


# default for --blobs-dir argument
ColDoc_as_blobs  = None

# relative to ColDoc_as_blobs
ColDoc_variables = 'variables'

ColDoc_lang = 'it_IT'

# assign an UUID early to blobs, so that each blob can refer to the parent blob
# caveat: if the blob is renamed before saving, that UUID will be unused
ColDoc_early_UUID = True


#- If `write_UUID` is `True`, the UUID will be written at the beginning of the blob.
#- If `write_UUID` is 'auto', the UUID will be written,
#   but it will be commented out in 'document', 'MainFile', 'Preamble', 'section' blobs.
#   Moreover it will be added after each '\section' command.
#- If `write_UUID` is `False`, no UUID will be written.
ColDoc_write_UUID = 'auto'
