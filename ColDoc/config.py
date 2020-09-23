import os.path


# default for --blobs-dir argument
ColDoc_as_blobs  = None

# relative to ColDoc_as_blobs
ColDoc_variables = 'variables'

ColDoc_lang = 'it_IT'

# assign an UUID early to blobs, so that each blob can refer to the parent blob
# caveat: if the blob is renamed before saving, that UUID will be unused
ColDoc_early_UUID = True

## this regulates the way that `blob_inator` adds \uuid tags in blobs
##
#- If `write_UUID` is `True`, the UUID will be written at the beginning of the blob,
#  or after \section{}
#
#- If `write_UUID` is 'auto', the UUID will be written as above
#   but not in blobs with environ listed in`ColDoc_do_not_write_uuid_in`.
#
#- If `write_UUID` is `False`, no UUID will be written.
ColDoc_write_UUID = 'auto'

# list of environments that are not coming from  \begin....\end statements
ColDoc_environments = ('main_file','preamble','input','include','input_preamble','include_preamble',
                       'usepackage','bibliography','section','paragraph')

# see description of `ColDoc_write_UUID`
ColDoc_do_not_write_uuid_in = ('E_document','main_file','preamble','input','include','input_preamble','include_preamble',
                               'usepackage','bibliography')

# strips the last lines in blobs if they are all made of whitespace
ColDoc_blob_rstrip = True

# `blob_inator` will add it, `deblob_inator` will remove it
ColDoc_commented_newline_after_blob_input = True

# 
ColDoc_url_placeholder = '@URLPLACEHOLDER91HDLP@'

# better not use such nicknames, may confuse the user and/or the programmer

ColDoc_invalid_nickname = ['static','static_collect','static_root','static_local','media',
                            'coldoc','ColDoc','all','search',
                            'http','https','html','www',
                            'usr','var','lib','etc','src','tmp',
                            'pdf','doc',
                            'jpeg','jpg','tiff','tif','gif','svg']


# Before compiling with latex a file, these files are copied back from 
# blobs/UUID/N/N/N/YYYY_ll_LL.XXX or
# (where YYYY is `main` or `view` )
ColDoc_pdflatex_fakemain_reuse_extensions = ['.aux','.toc','.idx','.bbl']

# after compiling with latex a file, these files are saved as 
# blobs/UUID/N/N/N/YYYY_ll_LL.XXX or
ColDoc_pdflatex_fakemain_preserve_extensions = ColDoc_pdflatex_fakemain_reuse_extensions + ['.tex','.log','.pdf','.out','.fls','.blg']

# Before compiling with plastex a file, these files are copied back from 
# blobs/UUID/N/N/N/YYYY_ll_LL.XXX or
ColDoc_plastex_fakemain_reuse_extensions = [('_plastex.paux','.paux'), ('.bbl','.bbl')]

# Moreover these are preserved when recreating the anon tree
ColDoc_anon_keep_extensions = ColDoc_pdflatex_fakemain_reuse_extensions + ['.paux']

