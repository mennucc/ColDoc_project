import os.path


# default for --blobs-dir argument in most commands
# and for `blobs_dir` in many calls in ColDoc.utils.py
# set this only if you have only one coldoc
ColDoc_as_blobs  = None

# relative to ColDoc_as_blobs
ColDoc_variables = 'variables'

ColDoc_lang = 'it_IT'

# assign an UUID early to blobs, so that each blob can refer to the parent blob
# caveat: if the blob is renamed before saving, that UUID will be unused
ColDoc_early_UUID = True

# filename extensions that are presented as text
ColDoc_show_as_text = ('.tex', '.sty', '.bbl', '.bib')

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
ColDoc_environments = ('main_file','preamble','input','include','input_preamble',
                       'graphic_file',
                       'usepackage','bibliography','section','paragraph')

# see description of `ColDoc_write_UUID`
ColDoc_do_not_write_uuid_in = ('E_document','main_file','preamble','input','include','input_preamble',
                               'usepackage','bibliography')

# cannot add children to these environments in an existing coldoc
ColDoc_cant_add_children_to_environments =  'main_file','usepackage','bibliography','paragraph'
# note that 'main_file' can have and should have two children : 'preamble' and 'document' ; but we cant add others

# cannot add begin/end children to these environments in an existing coldoc
ColDoc_cant_add_begin_end_children_to_environments =  'main_file','preamble','input_preamble','include_preamble','usepackage','bibliography','paragraph'
# structure of the blob tree, 'E_*' is any begin...end , but for E_document
ColDoc_environments_parent_child = {
    'main_file' : ('preamble','E_document'),
    'preamble' : ('input_preamble','usepackage'),
    'input_preamble' : ('input_preamble','usepackage'),
    'input' : ('section','paragraph','graphic_file','E_*'),
    'include' : ('section','paragraph','graphic_file','E_*'),
    'usepackage' : (),
    'bibliography': (),
    'section' : ('input','paragraph','graphic_file','E_*'),
    'paragraph' : (),
    'E_document' : ('include','input','section','graphic_file','paragraph','E_*'),
    'E_*' : ('input','paragraph','graphic_file','E_*'),
    }


# cannot be added as children in an existing coldoc
ColDoc_environments_cant_be_added_as_children =  ('main_file','E_document','preamble')

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
ColDoc_pdflatex_fakemain_reuse_extensions = ['.aux','.toc','.idx','.bbl','.out']

# after compiling with latex a file, these files are saved as 
# blobs/UUID/N/N/N/YYYY_ll_LL.XXX or
ColDoc_pdflatex_fakemain_preserve_extensions = ColDoc_pdflatex_fakemain_reuse_extensions + ['.tex','.log','.pdf','.fls','.blg']

# Before compiling with plastex a file, these files are copied back from 
# blobs/UUID/N/N/N/YYYY_ll_LL.XXX or
ColDoc_plastex_fakemain_reuse_extensions = [('_plastex.paux','.paux'), ('.bbl','.bbl')]

# Moreover these are preserved when recreating the anon tree
ColDoc_anon_keep_extensions = ColDoc_pdflatex_fakemain_reuse_extensions + ['.paux']

# Logs that can be served to users with 'view_log' permission
ColDoc_allowed_logs = ['.aux','.log','.out','.toc','.idx','.bbl', '.blg', '.fls', '_plastex.bbl', '_plastex.log', '_plastex.stdout']

# defaults for the values in the DColDoc
# see description in the `permission` section of the documentation
ColDoc_latex_macros_private = '\\newif\\ifColDocPublic\\ColDocPublicfalse\n\\newif\\ifColDocOneUUID\\ColDocOneUUIDfalse\n'
ColDoc_latex_macros_public  = '\\newif\\ifColDocPublic\\ColDocPublictrue \n\\newif\\ifColDocOneUUID\\ColDocOneUUIDfalse\n'
ColDoc_latex_macros_uuid    = '\\newif\\ifColDocPublic\\ColDocPublicfalse\n\\newif\\ifColDocOneUUID\\ColDocOneUUIDtrue\n'
