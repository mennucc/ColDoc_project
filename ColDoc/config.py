import os.path


# default for --blobs-dir argument in most commands
# and for `blobs_dir` in many calls in ColDoc.utils.py
# set this only if you have only one coldoc
ColDoc_as_blobs  = None

# relative to ColDoc_as_blobs
ColDoc_variables = 'variables'

ColDoc_lang = 'eng'

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
                       'usepackage','bibliography',
                       'part','chapter','section','subsection','paragraph')

# list of sectioning environments, in decreasing order
ColDoc_environments_sectioning = ('part','chapter','section','subsection')

# once assigned, these cannot be changed
ColDoc_environments_locked =  ('main_file','preamble','E_document','graphic_file','bibliography','E_thebibliography','usepackage')

# we cannot \\input inside these , so we put the \\begin\\end inside the blob
ColDoc_environment_inside_blob = ('E_thebibliography',)

# see description of `ColDoc_write_UUID`
ColDoc_do_not_write_uuid_in = ('E_document','main_file','preamble','input','include','input_preamble',
                               'usepackage','bibliography','E_thebibliography',)


# structure of the blob tree, 'E_*' is any begin...end , but for E_document and E_thebibliography
#  `False` means there is no parent. (`False` is short-circuited in most code)
ColDoc_environments_parent_child = {
    False : ('main_file',),
    'main_file' : ('preamble','E_document'),
    'preamble' : ('input_preamble','usepackage'),
    'input_preamble' : ('input_preamble','usepackage'),
    'input' :   ('chapter','section','subsection','paragraph','graphic_file','E_thebibliography','E_*'),
    'include' : ('chapter','section','subsection','paragraph','graphic_file','E_thebibliography','E_*'),
    'usepackage' : (),
    'bibliography': (),
    'part' : ('input','chapter','section','paragraph','graphic_file','E_thebibliography','E_*'),
    'chapter' : ('input','section','paragraph','graphic_file','E_thebibliography','E_*'),
    'section' : ('input','subsection','paragraph','graphic_file','E_thebibliography','E_*'),
    'subsection' : ('input','paragraph','graphic_file','E_thebibliography','E_*'),
    'paragraph' : ('graphic_file',),
    'E_document' : ('include','input','part','chapter','section','subsection','paragraph','bibliography','E_thebibliography','graphic_file','E_*',),
    'E_thebibliography' : (),
    'E_*' : ('input','paragraph','graphic_file','E_*'),
    }

# maps extension to environments
# any extension not listed here is necessarily a `graphic_file`
ColDoc_latex_mime = {
    '.tex': ('main_file','preamble','input','include','input_preamble','part','chapter','section','subsection','paragraph','E_document','E_thebibliography','E_*'),
    '.sty': ('usepackage',), 
    '.bbl': ('E_thebibliography',), # this appears also with '.tex' extension
    '.bib': ('bibliography',),
    }

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



ColDoc_environments_we_wont_latex = ( 'preamble' , 'input_preamble' , 'include_preamble',
                               'usepackage', 'bibliography', 'E_thebibliography','graphic_file' )

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

# copy these files from the `blobs` tree to the `anon` tree
ColDoc_anon_copy_paths = [ '.blob_inator-args.json', ]

# Logs that can be served to users with 'view_log' permission
ColDoc_allowed_logs = ['.aux','.log','.out','.toc','.idx','.bbl', '.blg', '.fls', '_plastex.bbl', '_plastex.log', '_plastex.stdout']

# defaults for the values in the DColDoc
# see description in the `permission` section of the documentation
ColDoc_latex_macros_private = '\\newif\\ifColDocPublic\\ColDocPublicfalse\n\\newif\\ifColDocOneUUID\\ColDocOneUUIDfalse\n'
ColDoc_latex_macros_public  = '\\newif\\ifColDocPublic\\ColDocPublictrue \n\\newif\\ifColDocOneUUID\\ColDocOneUUIDfalse\n'
ColDoc_latex_macros_uuid    = '\\newif\\ifColDocPublic\\ColDocPublicfalse\n\\newif\\ifColDocOneUUID\\ColDocOneUUIDtrue\n'
