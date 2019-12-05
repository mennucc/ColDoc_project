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
#   but it will be commented out in `ColDoc_comment_out_uuid_in` blobs.
#   Moreover it will be added after each '\section' command.
#- If `write_UUID` is `False`, no UUID will be written.
ColDoc_write_UUID = 'auto'

# see description of `ColDoc_write_UUID`
ColDoc_comment_out_uuid_in = ('document','main_file','preamble','section','input','include')

# strips the last lines in blobs if they are all made of whitespace
ColDoc_blob_rstrip = True

# `blob_inator` will add it, `deblob_inator` will remove it
ColDoc_commented_newline_after_blob_input = True
