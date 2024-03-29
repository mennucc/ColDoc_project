#!/usr/bin/env python3

def _(s):
    "mark translatable strings; no attempt is made to translate them, since part of this code is used as a library"
    return s

__doc__  = _("""
This program does some actions that `manage` does not. Possible commands:

    deploy
        create a new ColDoc site

    set_site [name] [url]
        set the SITE

    create_fake_users
        creates some fake users, to interact with the Django site

    add_blob
        add a an empty blob to a document
        (to import new LaTeX material in a document, use `blob_inator`)
    
    reparse_all
         reparse all blobs
    
    gen_lang
         generate all languages (for multilanguage content)
    
    check_tree
        check that tree is connected and has no loops;
        and consistency of metadata and LaTeX content

    count_untranslated_chars
        count how many characters have to be translates; 
        TeX macros, equations and so count as "one character"

    list_authors
        ditto

    send_test_email TO
        ditto
    
    create_text_catalogs
        recreate the text catalogs

    recompute_order
        recompute the order of blobs along the document

     list_uncompiled_saves
         list blobs where there are uncompiled saves
""")

import os, sys, argparse, json, pickle, io, copy, tempfile, re, functools, subprocess, difflib
from os.path import join as osjoin


if __name__ == '__main__':
    for j in ('','.'):
        while j in sys.path:
            sys.stderr.write('Warning: deleting %r from sys.path\n' % (j,))
            del sys.path[sys.path.index(j)]
    #
    a = os.path.realpath(sys.argv[0])
    a = os.path.dirname(a)
    a = os.path.dirname(a)
    assert os.path.isdir(a), a
    COLDOC_SRC_ROOT=a
    a = osjoin(a, 'ColDocDjango')
    if a not in sys.path:
        sys.path.insert(0, a)
    os.environ['COLDOC_SRC_ROOT'] = COLDOC_SRC_ROOT
    del a
    #
    from ColDoc import loggin

from ColDoc.utils import ColDocException, get_blobinator_args, uuid_to_dir, parent_cmd_env_child, \
     replace_language_in_inputs, strip_language_lines, gen_lang_coldoc, gen_lang_metadata


import logging
logger = logging.getLogger('helper')

##################


def tmptestsite_deploy(coldoc_site_root):
    logger.setLevel(logging.INFO)
    tempdir = tempfile.mkdtemp(prefix='ColDocDjangoTest_')
    if coldoc_site_root:
        logger.warning('COLDOC_SITE_ROOT was hijacked from %r to %r', coldoc_site_root, tempdir)
    else:
        logger.info('COLDOC_SITE_ROOT was set to %r',tempdir)
    # set up temporary site
    import helper
    helper.deploy(tempdir)
    # activate wallet
    a = os.path.join(tempdir,'config.ini')
    s = open(a).readlines()
    for n in range(len(s)):
        if s[n].startswith('use_wallet'):
            s[n] = 'use_wallet = True\n'
    with open(a,'w') as f:
        f.write(''.join(s))
    return tempdir


##################

DEPLOY_DATABASES = ('sqlite3', 'mysql')

def deploy(target, database = 'sqlite3', coldoc_src_root=None):
    if coldoc_src_root is None:
        coldoc_src_root = os.environ.get('COLDOC_SRC_ROOT')
    assert  coldoc_src_root is not None and os.path.isdir(coldoc_src_root)
    #
    assert database in DEPLOY_DATABASES
    from ColDocDjango import config
    if os.path.exists(target):
        if not os.path.isdir(target):
            sys.stderr.write('exists and not dir: %r\n' % target)
            return False
        elif os.listdir(target):
            sys.stderr.write('exists and not empty: %r\n' % target)
            return False
    else:
        os.mkdir(target)
    #
    a = osjoin(target,'config.ini')
    if os.path.exists(a) or os.path.islink(a):
        sys.stderr.write("Won't overwrite: %r\n"%(a,))
        return False
    config.deploy(a)
    #
    from django.core.management.utils import get_random_string
    suffix = get_random_string(5)
    #
    COLDOC_SITE_SETTINGS = os.path.join(target,'settings.py')
    F = open(COLDOC_SITE_SETTINGS,'w')
    F.write("""# settings specific for this instance
# This file will be executed after the `settings.py` file in the ColDocDjango directory
# in the source code.
""")
    # comment out
    a = open(osjoin(coldoc_src_root,'ColDocDjango/settings_suggested.py')).readlines()
    a = [l.strip('\n') for l in a]
    commenter = lambda l : ( ('#'+l) if l else l)
    if database == "mysql" :
        s = 'settings_mysql.py'
        commenter = lambda l : ( ('#'+l) if ( l and s not in l ) else l)
    a = [commenter(l)  for l in a ]
    F.write('\n'.join(a))
    F.close()
    #
    init = os.path.join(target,'init.py')
    F = open(init,'w')
    F.write("""# initialization code specific for this instance
# This file will be executed after all the apps are loaded
# see in ColDocDjango/init_example.py for some example code
""")
    #
    newconfig = config.get_config(target)
    for j in ( 'coldocs' , 'www' , 'lock', 'run'):
        os.mkdir(osjoin(target,j))
    # create 'media', , 'static_local', 'static_root':
    for j in 'media_root', 'template_dirs', 'static_root', 'static_local', 'dedup_root':
        a = newconfig['django'][j]
        os.makedirs(a)
    a = newconfig.get('django','sqlite_database')
    if a is not None:
        a = os.path.dirname(a)
        if not os.path.isdir(a):
            os.makedirs(a)
    #
    a = osjoin(coldoc_src_root,'ColDocDjango','ColDocDjango','wsgi.py')
    b = osjoin(target, 'wsgi.py')
    os.symlink(a, b)
    #
    a = osjoin(coldoc_src_root,'ColDocDjango','etc','apache2_template.conf')
    z = open(a).read()
    z = z.replace('@COLDOC_SITE_ROOT@', target)
    z = z.replace('@coldoc_src_root@', coldoc_src_root)
    z = z.replace('@RANDSUFFIX@', suffix)
    v = ''
    if 'VIRTUAL_ENV' in os.environ:
        v = 'python-home=' + os.environ['VIRTUAL_ENV']
    z = z.replace('@VIRTUAL_ENV@', v)
    b = osjoin(target, 'apache2.conf')
    with open(b,'w') as f_:
        f_.write(z)
    #
    import shlex
    for j, c in (('environment', str), \
                 ('environment.sh', lambda x: '"' + shlex.quote(x) + '"')):
        b = osjoin(target, j)
        with open(b,'w') as f_:
            f_.write('coldoc_src_root=%s\nCOLDOC_SITE_ROOT=%s\nPATH=%s\n' % \
                     (c(coldoc_src_root), c(target), c(os.environ.get('PATH',''))))
            if 'VIRTUAL_ENV' in os.environ:
                f_.write('VIRTUAL_ENV='  +  c(os.environ['VIRTUAL_ENV'])  +  '\n')
    #
    MYSQL_USERNAME = 'coldoc_user_' + suffix
    MYSQL_PASSWORD = get_random_string(10)
    MYSQL_DATABASE = 'coldoc_db_'   + suffix
    for l in 'mysql.cnf', 'mysql.sql', 'settings_mysql.py':
        a = osjoin(coldoc_src_root,'ColDocDjango','etc',l)
        z = open(a).read()
        z = z.replace('@MYSQL_DATABASE@'  ,  MYSQL_DATABASE)
        z = z.replace('@MYSQL_USERNAME@'  ,  MYSQL_USERNAME)
        z = z.replace('@MYSQL_PASSWORD@'  , MYSQL_PASSWORD)
        z = z.replace('@RANDSUFFIX@', suffix)
        z = z.replace('@COLDOC_SITE_ROOT@', target)
        b = osjoin(target, l)
        with open(b,'w') as f_:
            f_.write(z)
        os.chmod(b,0o600)
    #
    return True

def set_site(site_name='ColDoc', site_url = 'localhost:8000', *ignored):
    from django.contrib.sites.models import Site
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ColDocDjango.settings')
    import django
    from django.conf import settings
    django.setup()
    one = Site.objects.filter(id=settings.SITE_ID).get()
    one.domain = site_url
    one.name = site_name
    one.save()
    print("Set site id = %r domain %r name %r" % (one.id , one.domain, one.name))
    return True

def _build_fake_email(e):
    from django.conf import settings
    #import email
    a = settings.DEFAULT_FROM_EMAIL
    if not a or '@' not in a:
        return e + '@test.local'
    j = a.index('@')
    return a[:j] + '+' + e + a[j:]

fake_users_passwords = (('buyer', 'barfoo'), ('jsmith',"123456"), ('jdoe',"345678"), ('ed_itor','345678'), ('reviewer','marvel'))

fake_users = [up[0] for up in fake_users_passwords]

def create_fake_users(COLDOC_SITE_ROOT=None, log=print):
    from django.db.utils import IntegrityError
    from django.contrib.contenttypes.models import ContentType
    from django.contrib.auth.models import Permission
    from django.conf import settings
    import django.contrib.auth as A
    UsMo = A.get_user_model()
    for U,P in fake_users_passwords:
        log('*** creating user %r password %r' % (U,P))
        E=_build_fake_email(U)
        try:
            UsMo.objects.create_user(U,email=E,password=P).save()
        except IntegrityError as e:
            logger.debug("Already exists? %r",e)
        except Exception as e:
            log('Cannot create user %r : %r' %(U,e))
    #
    from UUID.models import DMetadata
    for U in  'reviewer', :
        user = UsMo.objects.filter(username=U).get()
        Per = "view_view", "view_blob" , "download"
        log('*** adding permissions to user %r: %r' % (U,Per))
        metadata_content_type = ContentType.objects.get_for_model(DMetadata)
        for pn in Per:
            permission = Permission.objects.get(content_type = metadata_content_type,
                                                codename=pn)
            user.user_permissions.add(permission)
            permission.save()
            user.save()
    #
    if settings.USE_WALLET:
        import wallet, wallet.utils
        from wallet.models import Wallet, Transaction
        wallet_content_type = ContentType.objects.get_for_model(Wallet)
        transaction_content_type = ContentType.objects.get_for_model(Transaction)
        for U in  'buyer', :
            user = UsMo.objects.filter(username=U).get()
            Per = (wallet_content_type, "operate"), (wallet_content_type , "view_wallet") , (transaction_content_type, "view_transaction")
            log('*** adding permissions to user %r: %s' % (U,Per))
            for ct, pn in Per:
                permission = Permission.objects.get(content_type = ct,
                                                    codename=pn)
                user.user_permissions.add(permission)
                permission.save()
                user.save()
            log('*** giving 200 coins to %r' % (U,))
            wallet.utils.deposit(200, U)
    #
    log('*** creating superuser "napoleon" password "adrian"')
    try:
        UsMo.objects.create_superuser('napoleon',email=_build_fake_email('napoleon'),password='adrian').save()
    except IntegrityError:
        pass
    except Exception as e:
        log('Cannot create user %r : %r' %(U,e))    
    return True 

def add_blob(logger, user, COLDOC_SITE_ROOT, coldoc_nick, parent_uuid, environ, p_lang, c_lang, selection_start = None, selection_end = None, add_beginend = True):
    " returns (success, message, new_uuid)"
    #
    from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
    #
    from ColDoc.utils import slug_re
    assert isinstance(coldoc_nick,str) and slug_re.match(coldoc_nick), coldoc_nick
    assert ((isinstance(p_lang,str) and slug_re.match(p_lang))), p_lang
    assert ((isinstance(c_lang,str) and slug_re.match(c_lang))), c_lang
    assert isinstance(parent_uuid,str) and slug_re.match(parent_uuid), parent_uuid
    assert isinstance(environ,str), environ
    if isinstance(selection_end,int) and selection_end<0: selection_end = None
    if isinstance(selection_start,int) and selection_start<0: selection_start = None
    #
    import ColDoc.config as CC
    #
    p_lang_ = '_' + p_lang
    c_lang_ = '_' + c_lang
    #
    if environ.startswith('E_'):
        extension = '.tex'
    elif environ == 'graphic_file':
        extension = '.png'
    else:
        extension = None
        for k in CC.ColDoc_latex_mime:
            if environ in CC.ColDoc_latex_mime[k]:
                extension = k
    #
    coldoc_dir = osjoin(COLDOC_SITE_ROOT,'coldocs', coldoc_nick)
    assert os.path.exists(coldoc_dir), ('Does not exist coldoc_dir=%r\n'%(coldoc_dir))
    #
    blobs_dir = osjoin(coldoc_dir, 'blobs')
    #
    blobinator_args = get_blobinator_args(blobs_dir)
    #
    if environ[:2] == 'E_':
        if environ[2:] not in (blobinator_args['split_environment'] + blobinator_args['split_list']):
            a = 'The environ %r was never splitted when the document was first created '%environ
            logger.error(a)
            return False, a, None
    else:
        if environ not in CC.ColDoc_environments:
            a="Cannot add a child with unknown environ %r"%environ
            logger.error(a)
            return False, a, None
    #
    if selection_start is not None and selection_end != selection_start:
        if extension is None or environ == 'graphic_file':
            a=("cannot select region when adding a non-TeX file")
            logger.error(a)
            return False, a, None
    #
    if isinstance(user,str):
        import django.contrib.auth as A
        M = A.get_user_model()
        try:
            user_ = M.objects.get(username=user)
        except ObjectDoesNotExist:
            logger.error('No such user %r',user)
            return False, 'No such user', None
        user = user_
        logger.debug("Resolved user as %r",user)
    #
    from ColDoc import utils
    import ColDocApp.models as coldocapp_models
    import UUID.models as  blob_models
    metadata_class=blob_models.DMetadata
    #
    #try:
    parent_uuid_, parent_uuid_dir, parent_metadata = utils.resolve_uuid(uuid=parent_uuid, uuid_dir=None,
                                                   blobs_dir = blobs_dir, coldoc = coldoc_nick,
                                                   metadata_class=metadata_class)
    logger.debug('Resolved parent as %r', parent_uuid_dir)
    #
    coldoc = parent_metadata.coldoc
    Clangs = coldoc.get_languages()
    Blangs =  parent_metadata.get_languages()
    if p_lang not in Blangs:
        a="Parent does not have language %r" % p_lang
        logger.error(a)
        return False, a, None
    #
    if c_lang not in Clangs and c_lang not in ('mul','und','zxx'):
        a="ColDoc %r does not allow language %r" % (coldoc_nick, c_lang)
        logger.error(a)
        return False, a, None
    #
    if 'mul' in Blangs and (p_lang != 'mul' or c_lang not in ('mul','und','zxx')):
        logger.warning("This is weird Blangs=%r p_lang=%r c_lang=%r" , Blangs, p_lang, c_lang)
    #
    if '.tex' not in parent_metadata.get('extension'):
        a="Only '.tex' blobs can have children"
        logger.error(a)
        return False, a, None
    #
    from ColDoc.utils import tree_environ_helper
    parent_environ = parent_metadata.environ
    teh = tree_environ_helper(parent = parent_environ, blobs_dir = blobs_dir)
    if not teh.child_is_allowed(environ, extension=extension):
        if environ[:2] == 'E_':
            a="Cannot add a \\begin{%s}..\\end{%s} to a blob that has environ=%r " % (environ[2:],environ[2:],parent_environ)
        else:
            a="Cannot add a child with environ %r extension %r to a parent with environ %r"% (parent_environ, extension, environ)
        logger.error(a)
        return False, a, None
    #
    #from ColDocDjango.users import user_has_perm
    user.associate_coldoc_blob_for_has_perm(parent_metadata.coldoc, parent_metadata)
    if not user.has_perm('UUID.view_blob',parent_metadata):
        logger.error("Permission denied (view_blob)")
        return False, "Permission denied (view_blob)", None
    try:
        parent_metadata.author.get(id=user.id)
    except ObjectDoesNotExist :
        logger.debug("User %r is not an author of %r",user,parent_uuid)
        if  not user.has_perm('ColDocApp.add_blob'):
            a=("Permission denied (add_blob) and %s is not an author of %s " %(user, parent_uuid))
            logger.error(a)
            return False, a, None
    else:
        logger.debug("User %r is an author of %r",user,parent_uuid)
    #
    # FIXME TODO maybe we should insert the "input" for all languages available?
    parent_abs_filename = os.path.join(blobs_dir, parent_uuid_dir, 'blob' + p_lang_ + '.tex')
    if not os.path.exists(parent_abs_filename):
        a="Parent does not exists %r"%parent_abs_filename
        logger.error(a)
        return False, a, None
    #
    filename = None
    while not filename:
        new_uuid = utils.new_uuid(blobs_dir=blobs_dir)
        new_dir = utils.uuid_to_dir(new_uuid, blobs_dir=blobs_dir, create=True)
        filename = osjoin(new_dir,'blob' + c_lang_ + extension)
        filename_no_ext = osjoin(new_dir,'blob' + c_lang_)
        if os.path.exists( osjoin(blobs_dir, filename) ):
            logger.error(' output exists %r, trying next UUID' % filename)
            filename = None
    #
    child_metadata = metadata_class(coldoc=parent_metadata.coldoc, uuid=new_uuid)
    #child_metadata.add('uuid', new_uuid)
    if extension is not None:
        child_metadata.add('extension',extension)
    child_metadata.add('environ',environ)
    child_metadata.add('lang', c_lang)
    if environ[:2] == 'E_' and environ[2:] in blobinator_args['private_environment']:
        child_metadata.add('access', 'private')
    child_metadata.save()
    child_metadata.add('author',user)
    parent_metadata.add('child_uuid',new_uuid)
    child_metadata.save()
    child_uuid = child_metadata.uuid
    #
    placeholder='placeholder'
    parent_file = open(parent_abs_filename).read()
    if selection_start is not None and selection_end != selection_start:
        placeholder = parent_file[selection_start:selection_end]
    if environ in CC.ColDoc_environments_sectioning:
        sources = ['','','{placeholder}']
        if ('\\' + environ)  in placeholder:
            from UUID.views import _parse_for_section
            weird_prologue = []
            p1, p2 , sources = _parse_for_section(placeholder, environ, child_metadata.uuid, weird_prologue)
            placeholder = p1 + p2
            # FIXME should pass back weird_prologue to caller
        else:
            from ColDoc.blob_inator import _rewrite_section
            ignore_me, src = _rewrite_section(sources, new_uuid, environ)
            placeholder = src + '\n' + placeholder
        child_metadata.add('optarg', json.dumps(sources))
        child_metadata.save()
    else:
        placeholder = ("\\uuid{%s}%%\n" % (new_uuid,)) + placeholder
    with open(parent_abs_filename,'w') as f:
        if selection_start is None :
            f.write(parent_file)
        else:
            f.write(parent_file[:selection_start])
        f.write("%\n")
        #utils.environ_stub(environ)
        if environ[:2] == 'E_':
            if add_beginend: f.write("\\begin{"+environ[2:]+"}")
            if environ[2:] in blobinator_args['split_list']:
                f.write("\\item")
        if environ == 'graphic_file':
            t = coldoc.graphic_template
            if 'mul' in Blangs:
                t = coldoc.graphic_mul_template
            l = locals()
            l = dict( (a,l[a]) for a in l if (not a.startswith('_') and isinstance(l[a],str)))
            f.write(t % l)
        else: 
            f.write("\\input{"+filename+"}")
        if environ[:2] == 'E_' and add_beginend:
            f.write("\\end{"+environ[2:]+"}")
        f.write("\n")
        if selection_start is not None :
            f.write(parent_file[selection_end:])
    #
    if environ == 'graphic_file':
        import shutil
        child_metadata.original_filename = child_metadata.uuid + '.png'
        child_metadata.save()
        shutil.copy(osjoin(os.environ['COLDOC_SRC_ROOT'],'ColDocDjango/assets/placeholder.png'),osjoin(blobs_dir,filename))
    else:
        with open(osjoin(blobs_dir,filename),'w') as f:
            f.write(placeholder+'\n')
        gen_lang_metadata(child_metadata, blobs_dir, child_metadata.coldoc.get_languages())
    #
    # write  the metadata (including, a a text copy in filesytem)
    parent_metadata.save()
    return True, ("Created blob with UUID %r, please edit %r to properly input it (a stub \\input was inserted for your convenience)"%(new_uuid,parent_uuid)), new_uuid
    #except Exception as e:
    #    logger.error("Exception %r",e)
    #    return False, "Exception %r"%e


def reparse_all(writelog, COLDOC_SITE_ROOT, coldoc_nick, lang = None, act=True):
    " `writelog(s,a)` is a function where `s` is a translatable string, `a` its arguments "
    #
    from ColDoc.utils import slug_re, get_blobinator_args
    assert isinstance(coldoc_nick,str) and slug_re.match(coldoc_nick), coldoc_nick
    assert ((isinstance(lang,str) and slug_re.match(lang)) or lang is None), lang
    #
    if lang is None:
        lang_ = ''
    else:
        lang_ = '_'+lang
    #
    coldoc_dir = osjoin(COLDOC_SITE_ROOT,'coldocs', coldoc_nick)
    assert os.path.exists(coldoc_dir), ('Does not exist coldoc_dir=%r\n'%(coldoc_dir))
    #
    blobs_dir = osjoin(coldoc_dir, 'blobs')
    #
    blobinator_args = get_blobinator_args(blobs_dir)
    #
    from ColDocApp.models import DColDoc
    coldoc = list(DColDoc.objects.filter(nickname = coldoc_nick))
    coldoc = coldoc[0]
    #if not coldoc:
    #    return HttpResponse("No such ColDoc %r." % (NICK,), status=http.HTTPStatus.NOT_FOUND)
    from ColDoc.utils import reparse_blob, choose_blob
    from ColDocDjango.utils import load_unicode_to_latex
    reparse_options = {'unicode_to_latex' : load_unicode_to_latex(coldoc_dir)}
    from UUID.models import DMetadata
    for metadata in DMetadata.objects.filter(coldoc = coldoc, extension='.tex\n'):
        for avail_lang in metadata.get('lang'):
            try:
                filename, uuid, metadata, lang, ext = choose_blob(blobs_dir=blobs_dir, ext='.tex', lang=avail_lang, metadata=metadata)
            except ColDocException:
                pass
            else:
                wl = reparse_blob(filename, metadata, lang, blobs_dir, act=act, options=reparse_options)
                for msg, args in wl:
                    writelog( _('Parsing uuid %r lang %r : %s'), (uuid, lang, msg%args))


list_uncompiled_saves_html = _("""
<style>
   table.diff {font-family:Courier; border:medium;}
   .diff_header {background-color:#e0e0e0}
   td.diff_header {text-align:right}
   .diff_next {background-color:#c0c0c0}
   .diff_add {background-color:#aaffaa}
   .diff_chg {background-color:#ffff77}
   .diff_sub {background-color:#ffaaaa}
   </style>
Dear user,
<br>
here is a list of blobs where you saved a new version but never compiled it.
<ul>
%s
</ul>
""")

list_uncompiled_saves_text = _("""
Dear user,

here is a list of blobs where you saved a new version but never compiled it.

%s

""")


@functools.lru_cache()
def _get_user(userid, UsMo=None):
    if UsMo is None:
        from django.contrib.auth import get_user_model
        UsMo = get_user_model()
    user = None
    userinfo = str(userid) + ' (not in database)'
    try:
        user = UsMo.objects.filter(id=userid).get()
        userinfo = str(user)
    except:
        logger.exception(' while looking for user %r',userid)
    return user, userinfo

def list_uncompiled_saves(COLDOC_SITE_ROOT, coldoc_nick):
    from ColDocApp.models import DColDoc
    from ColDoc.utils import recurse_tree, uuid_to_dir
    from UUID.models import DMetadata
    from functools import partial
    #
    coldoc = DColDoc.objects.get(nickname = coldoc_nick)
    coldoc_dir = osjoin(COLDOC_SITE_ROOT,'coldocs', coldoc_nick)
    blobs_dir = osjoin(coldoc_dir, 'blobs')
    load_by_uuid = partial(DMetadata.load_by_uuid, coldoc=coldoc)
    #
    myre_ = re.compile( r'blob_(...)_([0-9]*)_editstate.json'  )
    user_uuid_dict = {}
    def action(uuid, metadata, branch, *v , **k):
        dir_ = uuid_to_dir(uuid, blobs_dir)
        for fn in os.listdir( osjoin(blobs_dir, dir_) ):
            m = myre_.fullmatch(fn)
            if m:
                lang, userid = m.groups()
                if lang not in metadata.get_languages():
                    logger.warning('leftover edistate uuid %r userid %r lang %r',
                                   uuid, userid, lang)
                    continue
                dfn = osjoin(blobs_dir, dir_, fn)
                try:
                    with open(dfn) as f:
                        j = json.load( f )
                    if 'blobcontent' in j:
                        bfn = osjoin(blobs_dir, dir_, 'blob_' + lang + j.get('ext','.tex') )
                        with open(bfn) as b:
                            bcn = b.read()
                        bco = j['blobcontent']
                        if  bco != bcn:
                            d = user_uuid_dict.setdefault(userid,[])
                            d.append( (uuid,lang,bfn,bco,bcn) )
                except:
                    logger.exception('while loading %r', dfn)
                #d = user_uuid_dict.setdefault(user,[])
                #d.append( (uuid,lang) )
        return True
    recurse_tree(load_by_uuid, action)
    return user_uuid_dict

def _txt_diff(bfn,bco,bcn):
    " returns the diff of bco, bcn as a list of text stringss "
    t =tempfile.NamedTemporaryFile('w',delete=False)
    with t:
        t.write(bco)
    P = subprocess.run(['diff', '-su', bfn, t.name ],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       check=False, universal_newlines=True )
    os.unlink(t.name)
    if P.returncode not in (0,1):
        logger.warning('diff returned code %r and stderr %r',
                       P.returncode, P.stderr)
    s = P.stdout.splitlines()
    s = s[2:]
    return s

def print_uncompiled_saves(user_uuid_dict, showdiff=True):
    for userid in user_uuid_dict:
        user, userinfo = _get_user(userid)
        print('** User', userinfo)
        for uuid,lang,bfn,bco,bcn in user_uuid_dict[userid]:
            print('  uuid %r lang %r' % (uuid,lang))
            if showdiff:
                s = _txt_diff(bfn, bco, bcn)
                s = [ ('     '+j) for j in s]
                print('\n'.join(s))


def email_uncompiled_saves(user_uuid_dict, coldoc_nick, url_base=None, showdiff=True):
    assert url_base is None or isinstance(url_base,str)
    #
    ##from django.contrib.auth import get_user_model
    ##UsMo = get_user_model()
    from django.core.mail import EmailMultiAlternatives
    from django.urls import reverse
    from django.conf import settings
    from ColDocDjango.utils import get_email_for_user
    #
    for userid in user_uuid_dict:
        user, userinfo = _get_user(userid)
        if not user:
            continue
        # default
        url = '#'
        if url_base and url_base[-1] == '/':
            url_base = url_base[:-1]
        try:
            r = get_email_for_user(user)
            if r is None:
                logger.warning('No valid email for user %r', user)
                continue
            a = _('Uncompiled saves in %r') % (coldoc_nick,)
            E = EmailMultiAlternatives(subject = a,
                                       from_email = settings.DEFAULT_FROM_EMAIL,
                                       to= [r],
                                       reply_to = [r])
            lit = []
            lih = []
            for uuid,lang,bfn,bco,bcn in user_uuid_dict[userid]:
                if url_base:
                    url = url_base + reverse('UUID:index', kwargs={'NICK':coldoc_nick,'UUID':uuid})
                    if lang not in ('mul', 'und', 'zxx'):
                        url +=  '?lang=' + lang
                lit.append(  ' - %r / %r' %   (uuid,lang) )
                if showdiff:
                    H = difflib.HtmlDiff()
                    blobdiff = H.make_table(bco.splitlines(),
                                            bcn.splitlines(),
                                           _('Saved on disk'),_('Your content'), True)
                    lih.append( '<li> <a href="%s"> %s / %s </a> %s </li>' %
                                (url, uuid, lang, blobdiff) )
                    s = _txt_diff(bfn, bco, bcn)
                    lit += [ ('     '+j) for j in s]
                else:
                    lih.append( '<li> <a href="%s"> %s / %s </a> </li>' %
                                (url, uuid, lang) )
                lit.append('')
            lit = '\n'.join( lit)
            lih = '\n'.join( lih )
            E.attach_alternative(list_uncompiled_saves_text % ( lit, ), 'text/plain')
            E.attach_alternative(list_uncompiled_saves_html % ( lih, ), 'text/html')
            E.send()
        except:
            logger.exception(' while emailing user %r',userinfo)#

def recompute_order_in_document(coldoc_nick):
    from ColDocApp.models import DColDoc
    from ColDoc.utils import recurse_tree
    from UUID.models import DMetadata
    from functools import partial
    #
    coldoc = DColDoc.objects.get(nickname = coldoc_nick)
    load_by_uuid = partial(DMetadata.load_by_uuid, coldoc=coldoc)
    #
    available = set(DMetadata.objects.filter(coldoc = coldoc)) #.values_list('id',flat=True))
    seen_list = []
    def action(uuid, metadata, branch, *v , **k):
        seen_list.append(metadata)
        available.discard(metadata)
        return True
    recurse_tree(load_by_uuid, action)
    for nr, met in enumerate(seen_list):
        met.order_in_document = nr
        met.save(write_metadata_backup_file=False)
    for met in available:
        met.order_in_document = 0x7fffffff
        met.save(write_metadata_backup_file=False)

def check_tree(warn, COLDOC_SITE_ROOT, coldoc_nick, checklang = None):
    " returns `problems`, a list of problems found in tree; `warn(s,a)` is a function where `s` is a translatable string, `a` its arguments"
    #
    from functools import partial
    from ColDoc.utils import recurse_tree
    from UUID.models import DMetadata
    #
    from ColDoc.utils import slug_re
    assert isinstance(coldoc_nick,str) and slug_re.match(coldoc_nick), coldoc_nick
    # this is currently unused
    assert ((isinstance(checklang,str) and slug_re.match(checklang)) or checklang is None), checklang
    #
    coldoc_dir = osjoin(COLDOC_SITE_ROOT,'coldocs', coldoc_nick)
    assert os.path.exists(coldoc_dir), ('Does not exist coldoc_dir=%r\n'%(coldoc_dir))
    #
    blobs_dir = osjoin(coldoc_dir, 'blobs')
    #
    from ColDoc.utils import tree_environ_helper
    teh = tree_environ_helper(blobs_dir=blobs_dir)
    #
    from ColDocApp.models import DColDoc
    coldoc = DColDoc.objects.get(nickname = coldoc_nick)
    CDlangs = set(coldoc.get_languages())
    #
    from ColDoc.latex import prepare_options_for_latex
    options = prepare_options_for_latex(coldoc_dir, blobs_dir, DMetadata, coldoc) 
    #
    from UUID.models import DMetadata, uuid_replaced_by
    #
    seen = set()
    available = set()
    all_metadata = {}
    problems = []
    untranslated = []
    #
    for metadata in DMetadata.objects.filter(coldoc = coldoc):
        available.add( metadata.uuid)
        all_metadata[metadata.uuid] = metadata
    # each one of those is equivalent
    load_by_uuid = partial(DMetadata.load_by_uuid, coldoc=coldoc)
    load_by_uuid = lambda uuid: all_metadata[uuid]
    #
    def actor(uuid, metadata, branch, teh, seen, available, warn, problems, *v , **k):
        if uuid in branch:
            s,a = _("loop detected along branch %r") , (branch+[uuid],)
            warn(s,a)
            problems.append(("LOOP", uuid, s, a))
        ret = True
        if uuid in seen:
            ret = False
            s,a = _("duplicate node %r in tree"), (uuid,)
            warn(s, a)
            problems.append(("DUPLICATE", uuid, s, a))
        if uuid in available:
            available.discard(uuid)
        else:
            ret = False
            warn(_("already deleted from queue %r") , uuid)
        seen.add(uuid)
        if len(branch) > 1:
            c = load_by_uuid(branch[-1])
            p = load_by_uuid(branch[-2])
            if not teh.child_is_allowed(c.environ, p.environ, c.get('extension')):
                s,a = _("The node %r %r cannot be a child of %r %r"), (c.uuid,c.environ,p.uuid,p.environ)
                problems.append(("WRONG_LINK", uuid, s, a))
                warn(s, a)
                ret = False
            #else:
            #    warn("The node %r %r can be a child of %r %r" %(c.uuid,c.environ,p.uuid,p.environ))                
        Blangs = set(all_metadata[uuid].get_languages())
        if 'mul' not in Blangs  and 'und' not in Blangs and 'zxx' not in Blangs and  CDlangs != Blangs:
            untranslated.append((uuid,Blangs))
        return ret
    #
    action = partial(actor, teh=teh, seen=seen, available=available, warn=warn, problems=problems)
    ret = recurse_tree(load_by_uuid, action, problems=problems)
    # self check
    assert bool(problems) ^ (bool(ret)), (ret,problems, bool(ret), bool(problems))
    #
    if available:
        s,a = _("Disconnected nodes %r") , available
        warn(s, a)
        s = _("Disconnected node %r")
        r = _("Disconnected node %r, replaced by %r")
        for j in available:
            rep = uuid_replaced_by(coldoc, j)
            if rep:
                rep = [a.uuid for a in rep]
                problems.append(('DISCONNECTED_REPLACED', j, r, (j,rep) ))
            else:
                problems.append(('DISCONNECTED', j, s, (j,) ))
    # load back_maps
    from ColDoc.utils import uuid_to_dir, parent_cmd_env_child
    back_maps = {}
    for uuid in all_metadata :
        a = osjoin(blobs_dir, uuid_to_dir(uuid), '.back_map.pickle')
        if os.path.exists(a):
            back_maps[uuid] = pickle.load(open(a,'rb'))
        else:
            M = all_metadata[uuid]
            if M.get('extension') == ['.tex']:
                logger.warning('UUID %r does not have back_map',uuid)
    # check environ
    environments = {}
    for uuid, M in all_metadata.items() :
        env = M.get('environ')
        if len(env) != 1 :
            s, a = _('UUID %r environ %r') , (uuid, env)
            logger.error(a)
            problems.append(("WRONG environ", uuid, s, a))
            continue
        environments[uuid] = env[0]
    # check that the environment of the child corresponds to the LaTex \begin/\end used in the parent
    split_graphic = options.get("split_graphic",[])
    allowed_parenthood = options.get("allowed_parenthood",{})
    for uuid, M in all_metadata.items() :
        parents = M.get('parent_uuid')
        child_env = environments.get(uuid)
        if  child_env is None:
            continue
        for parent_uuid in parents:
            back_map = back_maps.get(parent_uuid)
            if back_map is None:
                logger.error('Parent %r of %r does not have back_map', parent_uuid, uuid)
                continue
            cmd, file, parent_uses_env = back_map[uuid]
            wrong = parent_cmd_env_child(parent_uses_env, cmd, child_env, split_graphic, allowed_parenthood)
            if wrong:
                #a = 'child env %r parent_env %r parent_cmd %r' %(child_env,parent_uses_env,cmd))
                s = _('Parent %r includes child %r using cmd %r environ %r but child %r thinks it is environ %r')
                a =  (parent_uuid, uuid, cmd, parent_uses_env, uuid , child_env)
                warn(s, a)
                problems.append(('CMD_PARENT_CHILD', uuid, s, a))
    #
    private_environment = options.get("private_environment",[])
    from ColDoc.config import ColDoc_environments_sectioning
    for uuid, M in all_metadata.items() :
        env = environments.get(uuid)
        D = osjoin(blobs_dir, uuid_to_dir(uuid, blobs_dir))
        if os.path.exists(osjoin(D,'.check_ok')):
            continue
        problems_len=len(problems)
        # check protection
        if private_environment:
            if (env[:2] == 'E_') and ( bool(env[2:] in private_environment) != bool( M.access == 'private')):
                s, a = _('UUID %r environ %r access %r') ,  (uuid, env, M.access)
                warn(s, a)
                problems.append(('WRONG access', uuid, s, a))

        # check that header is consistent
        Blangs = M.get_languages()
        env = environments.get(uuid)
        if env and env in ColDoc_environments_sectioning:
            try:
                for lang in Blangs:
                    j = 'blob_' + lang + '.tex'
                    l = open( osjoin(D,j) ).readlines(4096)
                    while l :
                        a = l[0].strip()
                        if a.startswith('%') or a == '\\ColDocUUIDcheckpoint':
                            l.pop(0)
                        else:
                            break
                    if l and not l[0].startswith('\\'+ env):
                            s = _('UUID %r file %r environ %r first line %r')
                            a = (uuid, j, env, l[0])
                            warn(s, a)
                            problems.append(('WRONG_HEADER', uuid, s, a))
            except:
                logger.exception('while checking headers in %r', uuid)
        # check inputs
        try:
          if '.tex' in env:
            abm =  ['blob']
            IMs = {}
            for lang in Blangs:
                a = osjoin(blobs_dir, uuid_to_dir(uuid), '.input_map_'+lang+'.pickle')
                if os.path.exists(a):
                    IMs[lang] = pickle.load(open(a,'rb'))
                else:
                    logger.warning('UUID %r does not have input_map',uuid)
            Umaps = {}
            for lang, IM in IMs.items():
                more_langs = [lang] + ['zxx','und']
                allowed_blob_lang = set( (a+'_'+l) for a in abm  for l in more_langs)
                Uset = set()
                for macroname, argSource, inputfile, thisuuid, thisblob in IM:
                    if thisblob is not None:
                        blob_base, blob_ext = os.path.splitext(thisblob)
                        if blob_base not in allowed_blob_lang:
                            s = _('In language %(lang)s macro \\%(macroname)s %(argSource)s {%(inputfile)r} is including an incorrect blob %(thisblob)s')
                            locals_ = copy.copy(locals())
                            warn(s, locals_)
                            problems.append(('WRONG_INPUT', uuid, s, locals_))
                    if thisuuid is None or thisblob is None:
                        s = _('Unparsable input  \\%s %s {%r} -> uuid %r blob %r')
                        a = (macroname, argSource, inputfile, thisuuid, thisblob)
                        warn(s, a)
                        problems.append(('WRONG_INPUT', uuid, s, a))
                    elif thisuuid in Uset:
                        s = _('inputs UUID %r filename %r twice')
                        a = (thisuuid,inputfile)
                        warn(s, a)
                        problems.append(('DUP_INPUT', uuid, s, a))
                    if thisuuid:
                        Uset.add(thisuuid)
                Umaps[lang]=Uset
            if len(IMs) > 1:
                Uall = set( u for l in Umaps for u in Umaps[l])
                for lang , Uset in Umaps.items():
                    if Uset != Uall:
                        s = _('language %r does not input UUIDs: %r')
                        a = (lang , Uall.symmetric_difference(Uset))
                        warn(s, a)
                        problems.append(('MISSING_INPUT', uuid, s, a))
        except:
            logger.exception('while checking input maps in %r', uuid)
        # mark as checked for these controls
        if problems_len == len(problems):
            open( osjoin(D,'.check_ok') , 'w+' ).write('ok')
    #
    if untranslated:
        s = 'There are %d untranslated UUIDs' 
        a = (len(untranslated),)
        if len(untranslated) > 16:
            s = _('There are %d untranslated UUIDs, showing some')
            untranslated = untranslated[:16]
        problems.append(('N_UNTRASLATED',None,s,a))
        for uuid,b in untranslated:
            s = _('translated to: %r')
            problems.append(('UNTRANSLATED',uuid, s, b))
    return problems


def list_authors(warn, COLDOC_SITE_ROOT, coldoc_nick, as_django_user = True):
    " if as_django_user is true, authors will be returned as django user whenever possible"
    #
    from ColDoc.utils import slug_re
    assert isinstance(coldoc_nick,str) and slug_re.match(coldoc_nick), coldoc_nick
    #
    coldoc_dir = osjoin(COLDOC_SITE_ROOT,'coldocs', coldoc_nick)
    assert os.path.exists(coldoc_dir), ('Does not exist coldoc_dir=%r\n'%(coldoc_dir))
    #
    blobs_dir = osjoin(coldoc_dir, 'blobs')
    #
    from ColDocApp.models import DColDoc
    coldoc = list(DColDoc.objects.filter(nickname = coldoc_nick))
    coldoc = coldoc[0]
    #
    from UUID.models import DMetadata
    #
    authors = {}
    #
    def smartappend(user_ , uuid_):
        if user_ not in authors:
            authors[user_] = [uuid_]
        else:
            authors[user_].append(uuid_)
    #
    from itertools import chain
    for metadata in DMetadata.objects.filter(coldoc = coldoc):
        uuid = metadata.uuid
        m1 = metadata.get('M_author')
        if as_django_user:
            m2 = metadata.author.all()
        else:
            m2 = metadata.get('author') #[a.username for a in metadata.get('author')]
        for u in chain(m1, m2 ):
            smartappend(u, uuid)
        if not m1 and not m2:
            smartappend(None, uuid)
    return authors

def send_test_email(email_to):
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ColDocDjango.settings')
    import django
    from django.conf import settings
    django.setup()
    from django.core.mail import EmailMessage
    E = EmailMessage(subject="test email",
                     from_email=settings.DEFAULT_FROM_EMAIL,
                     to=[email_to],)
    E.body = 'test email'
    E.send()


def count_untranslated_chars(COLDOC_SITE_ROOT, coldoc_nick, messages=[]):
    #
    from ColDocApp.models import DColDoc
    from UUID.models import DMetadata
    from ColDoc import utils, transform
    #
    
    if isinstance(coldoc_nick, str):
        coldoc = DColDoc.objects.filter(nickname = coldoc_nick).get()
    elif isinstance(coldoc_nick,DColDoc):
        coldoc = coldoc_nick
        coldoc_nick = coldoc.nickname
    else:
        raise ValueError('Argument coldoc_nick cannot be type %r' %( type(coldoc_nick)))
    #
    coldoc_dir = osjoin(COLDOC_SITE_ROOT,'coldocs', coldoc_nick)
    assert os.path.exists(coldoc_dir), ('Does not exist coldoc_dir=%r\n'%(coldoc_dir))
    blobs_dir = osjoin(coldoc_dir, 'blobs')
    #
    CDlangs = set(coldoc.get_languages())
    #CDlangs.add('rus')
    #CDlangs.add('deu')
    #
    extension = '.tex'
    #
    n_chars = 0
    
    for metadata in DMetadata.objects.filter(coldoc = coldoc):
        L = metadata.get_languages()
        if not L:
            messages.append('UUID %r NO LANGUAGE?' % (metadata.uuid))
            continue
        lang = L[0]
        Blangs = set(L)
        Mlangs = CDlangs - Blangs
        if 'mul' not in Blangs  and 'und' not in Blangs and 'zxx' not in Blangs and  CDlangs != Blangs:
            new_dir = utils.uuid_to_dir(metadata.uuid, blobs_dir=blobs_dir)
            filename = osjoin(new_dir,'blob_' + lang + extension)
            out = io.StringIO()
            helper = transform.squash_helper_token2unicode()
            f = osjoin(blobs_dir,filename)
            if not os.path.isfile(f):
                messages.append('UUID %r NO file %r?' % (metadata.uuid,filename))
                continue
            transform.squash_latex(open(f),out,{},helper)
            l = len(out.getvalue())
            messages.append('filename %r -> %d * %d ' % (filename,l, len(Mlangs)))
            n_chars += l * len(Mlangs)
    return n_chars

###################################

def create_text_catalogs(COLDOC_SITE_ROOT, coldoc, coldoc_nick):
    assert coldoc is not None or coldoc_nick is not None
    if coldoc is not None:
        if coldoc_nick is None:
            coldoc_nick = coldoc.nick
        else:
            assert  coldoc_nick == coldoc.nick
    else:
        from ColDocApp.models import DColDoc
        coldoc = DColDoc.objects.get(nickname = coldoc_nick)
    #
    coldoc_dir = osjoin(COLDOC_SITE_ROOT,'coldocs', coldoc_nick)
    assert os.path.exists(coldoc_dir), ('Does not exist coldoc_dir=%r\n'%(coldoc_dir))
    blobs_dir = osjoin(coldoc_dir, 'blobs')
    #
    Clangs = coldoc.get_languages()
    from ColDocApp.text_catalog import create_text_catalog
    for lang in Clangs:
        create_text_catalog(coldoc, blobs_dir)

#####################################
def main(argv):
    doc = __doc__
    parser = argparse.ArgumentParser(description=_("helper functions"),        epilog=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    COLDOC_SITE_ROOT = os.environ.get('COLDOC_SITE_ROOT')
    parser.add_argument('--coldoc-site-root',type=str,\
                        help='root of the coldoc portal (default from env `COLDOC_SITE_ROOT`)', default=COLDOC_SITE_ROOT,
                        required=(COLDOC_SITE_ROOT is None))
    parser.add_argument('--verbose','-v',action='count',default=0)
    if any([j in sys.argv for j in ( 'add_blob' , 'reparse_all' , 'check_tree' , 'list_authors' , 'gen_lang',\
                                     'recompute_order','list_uncompiled_saves',\
                                     'count_untranslated_chars', 'create_text_catalogs') ]):
        parser.add_argument('--coldoc-nick',type=str,required=True,\
                            help='nickname of the coldoc document')
        parser.epilog = None
    if 'reparse_all' in sys.argv or 'check_tree' in sys.argv:
        parser.add_argument('--lang','--language',type=str,\
                            help='restrict operation to this language')
    if 'reparse_all' in sys.argv:
        parser.add_argument('--no-act',action='store_true',\
                            help='apply changes')
    if 'list_uncompiled_saves'  in sys.argv:
        parser.add_argument('--email',action='store_true',\
                            help='send email to users (instead of printing to stdout)')
        parser.add_argument('--diff',action='store_true',\
                            help='add diff to output')
        parser.add_argument('--url-base',type=str,\
                            help='URL of the website hosting the portal')
    if 'add_blob' in sys.argv:
        parser.add_argument('--p_lang','--parent-language',type=str,\
                            required=True,
                            help='language of the parent blob')
        parser.add_argument('--c_lang','--child-language',type=str,\
                            required=True,
                            help='language of  newly created blob')
        parser.add_argument('--parent-uuid',type=str,required=True,\
                            help='parent of the newly created blob')
        parser.add_argument('--user',type=str,required=True,\
                            help='user creating the blob')
        parser.add_argument('--environ',type=str,required=True,\
                            help='environment of  newly created blob')
    if 'deploy' in sys.argv:
        parser.add_argument('--database',type=str,default='sqlite3',\
                            help=('type of database, one of %s' % ','.join(DEPLOY_DATABASES)))
    parser.add_argument('command', help='specific command',nargs='+')
    args = parser.parse_args()
    #
    verbose = args.verbose
    assert type(verbose) == int and verbose >= 0
    if verbose > 1:
        logging.getLogger().setLevel(logging.DEBUG)
    elif verbose:
        logging.getLogger().setLevel(logging.INFO)
    else:
        logging.getLogger().setLevel(logging.WARNING)
    #
    argv = args.command
    #
    COLDOC_SITE_ROOT = os.environ['COLDOC_SITE_ROOT'] = args.coldoc_site_root
    #
    if argv[0] != 'deploy':
        if COLDOC_SITE_ROOT is None or not os.path.isfile(os.path.join(COLDOC_SITE_ROOT,'config.ini')):
            logger.error("""\
The directory
    COLDOC_SITE_ROOT={COLDOC_SITE_ROOT}
does not contain the file `config.ini`
""".format_map(locals()) )
            return False
    #
    if argv[0] != 'deploy':
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ColDocDjango.settings')
        import django
        django.setup()
        from django.utils.translation import gettext, activate
        activate(os.environ.get('LANG','en-US'))
        from django.conf import settings
    #
    if argv[0] == 'deploy':
        if args.database not in DEPLOY_DATABASES:
            sys.stderr.write('The --database=%r is not one of %r.' % (args.database, DEPLOY_DATABASES ))
            return (1)
        else:
            ret = deploy(COLDOC_SITE_ROOT, database=args.database)
            if args.database == "mysql" :
                print('You should create the database, the user and set permissions,\n'
                      ' maybe using this command:\n'
                      ' # sudo mysql < %s' % (osjoin(COLDOC_SITE_ROOT,'mysql.sql'))
                      )
            print("Then: `manage.py migrate`; `manage.py collectstatic`, customize and install apache2.conf")
            return ret
    #
    elif argv[0] == 'set_site':
        return set_site(* (argv[1:]) )
    elif argv[0] == 'create_fake_users':
        return create_fake_users(COLDOC_SITE_ROOT)
    elif argv[0] == 'add_blob':
        ret = add_blob(logger, args.user, COLDOC_SITE_ROOT, args.coldoc_nick,
                        args.parent_uuid, args.environ, args.p_lang, args.c_lang )
        print(ret[1])
        return ret[0] #discard message
    #
    elif argv[0] == 'reparse_all':
        def writelog(msg, args):
            s = gettext(msg) % args
            sys.stdout.write('>> '+ s + '\n')
        reparse_all(writelog, COLDOC_SITE_ROOT, args.coldoc_nick, args.lang, not args.no_act)
        return True
    #
    elif argv[0] == 'gen_lang':
        gen_lang_coldoc(COLDOC_SITE_ROOT, args.coldoc_nick)
        return True
    #
    elif argv[0] == 'check_tree':
        def warn(s,a):
            print(gettext('Warning') + ' : ' + gettext(s) % a)
        problems = check_tree(warn, COLDOC_SITE_ROOT, args.coldoc_nick)
        if problems:
            print(gettext('Problems') + ' : ')
            for a in problems:
                try:
                    a =  (str(a[1] or '')) + ' : ' + ( gettext(a[-2]) % a[-1] )
                except:
                    print('  (!formatting error)')
                print(' ' + str(a))
        else:
            print(gettext("Tree for coldoc %r is fine") % (args.coldoc_nick,))
        return not bool(problems)
    #
    elif argv[0] == 'send_test_email':
        return send_test_email(argv[1])
    elif argv[0] == 'list_authors':
        authors = list_authors(logger.warning, COLDOC_SITE_ROOT, args.coldoc_nick)
        for a in authors:
            print(repr(a) + '→' + repr(authors[a]))
        return True
    elif argv[0] == 'count_untranslated_chars':
        n_chars = count_untranslated_chars(COLDOC_SITE_ROOT, args.coldoc_nick)
        print('total %d' % n_chars)
        return True
    elif argv[0] == 'create_text_catalogs':
        create_text_catalogs(COLDOC_SITE_ROOT, None, args.coldoc_nick)
        return True
    elif argv[0] == "recompute_order":
        recompute_order_in_document(args.coldoc_nick)
        return True
    elif argv[0] == "list_uncompiled_saves":
        list_ = list_uncompiled_saves(COLDOC_SITE_ROOT, args.coldoc_nick)
        if args.email:
            if args.url_base is None:
                args.url_base = 'http://' + settings.ALLOWED_HOSTS[0]
                logger.warning(' parameter --url-base was set to %r', args.url_base)
            email_uncompiled_saves(list_, args.coldoc_nick, args.url_base,args.diff)
        else:
            print_uncompiled_saves(list_,args.diff)
        return True
    else:
        sys.stderr.write("command not recognized : %r\n" % (argv,))
        sys.stderr.write(__doc__%{'arg0':sys.argv[0]})
        return False
    return ret



if __name__ == '__main__':
    ret = main(sys.argv)
    sys.exit(0 if ret else 13)

