#!/usr/bin/env python3


"""
This program does some actions that `manage` does not. Possible commands:

    deploy
        create a new ColDoc site

    set_site
        set the SITE

    create_fake_users
        creates some fake users, to interact with the Django site

    add_blob
        add a an empty blob to a document
        (to import new LaTeX material in a document, use `blob_inator`)
    
    reparse_all
         reparse all blobs
    
    check_tree
        check that tree is connected and has no loops

    list_authors
        ditto

    send_test_email TO
        ditto
"""

import os, sys, argparse, json, pickle
from os.path import join as osjoin


if __name__ == '__main__':
    for j in ('','.'):
        if j in sys.path:
            sys.stderr.write('Warning: deleting %r from sys.path\n',j)
            del sys.path[sys.path.index(j)]
    #
    a = os.path.realpath(sys.argv[0])
    a = os.path.dirname(a)
    a = os.path.dirname(a)
    assert os.path.isdir(a), a
    if a not in sys.path:
        sys.path.insert(0, a)
    COLDOC_SRC_ROOT=a
    os.environ['COLDOC_SRC_ROOT'] = COLDOC_SRC_ROOT
    del a
    #
    from ColDoc import loggin

from ColDoc.utils import ColDocException, get_blobinator_args

import logging
logger = logging.getLogger('helper')

try:
    import django_pursed
except ImportError:
    django_pursed = None


def deploy(target):
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
    COLDOC_SITE_SETTINGS = os.path.join(target,'settings.py')
    F = open(COLDOC_SITE_SETTINGS,'w')
    F.write("""# settings specific for this instance
# This file will be executed after the `settings.py` file in the ColDocDjango directory
# in the source code.
""")
    # comment out
    a = open(osjoin(COLDOC_SRC_ROOT,'ColDocDjango/settings_suggested.py')).readlines()
    a = [l.strip('\n') for l in a]
    a = [ ( ('#'+l) if l else l) for l in a ]
    F.write('\n'.join(a))
    F.close()
    #
    newconfig = config.get_config(target)
    for j in ( 'coldocs' , ):
        os.mkdir(osjoin(target,j))
    # create 'media', , 'static_local', 'static_root':
    for j in 'media_root', 'template_dirs', 'static_root', 'static_local':
        a = newconfig['django'][j]
        os.makedirs(a)
    a = newconfig.get('django','sqlite_database')
    if a is not None:
        a = os.path.dirname(a)
        if not os.path.isdir(a):
            os.makedirs(a)
    #
    a = osjoin(COLDOC_SRC_ROOT,'ColDocDjango','wsgi.py')
    b = osjoin(target, 'wsgi.py')
    os.symlink(a, b)
    #
    a = osjoin(COLDOC_SRC_ROOT,'ColDocDjango','apache2_template.conf')
    z = open(a).read()
    z = z.replace('@COLDOC_SITE_ROOT@', target)
    z = z.replace('@COLDOC_SRC_ROOT@', COLDOC_SRC_ROOT)
    v = ''
    if 'VIRTUAL_ENV' in os.environ:
        v = 'python-home=' + os.environ['VIRTUAL_ENV']
    z = z.replace('@VIRTUAL_ENV@', v)
    b = osjoin(target, 'apache2.conf')
    open(b,'w').write(z)
    #
    print("TODO : migrate, collectstatic, customize and install apache2.conf")
    return True

def set_site(site_url = None):
    if site_url is None : site_url =  'localhost:8000'
    from django.contrib.sites.models import Site
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ColDocDjango.settings')
    import django
    from django.conf import settings
    django.setup()
    one = Site.objects.filter(id=settings.SITE_ID).get()
    one.domain = site_url
    one.name = 'ColDoc test'
    one.save()
    print("Set site id = %r domain %r name %r" % (one.id , one.domain, one.name))
    return True

def _build_fake_email(e):
    from django.conf import settings
    import email
    a = settings.DEFAULT_FROM_EMAIL
    if not a or '@' not in a:
        return e + '@test.local'
    j = a.index('@')
    return a[:j] + '+' + e + a[j:]


def create_fake_users(COLDOC_SITE_ROOT):
    from django.db.utils import IntegrityError
    from django.contrib.contenttypes.models import ContentType
    from django.contrib.auth.models import Permission
    from django.conf import settings
    import django.contrib.auth as A
    UsMo = A.get_user_model()
    for U,P in ('foobar', 'barfoo'), ('jsmith',"123456"), ('ed_itor','345678'), ('reviewer','marvel'):
        print('*** creating user %r password %r' % (U,P))
        E=_build_fake_email(U)
        try:
            UsMo.objects.create_user(U,email=E,password=P).save()
        except IntegrityError as e:
            logger.debug("Already exists? %r",e)
        except Exception as e:
            print('Cannot create user %r : %r' %(U,e))
    #
    from ColDocDjango.UUID.models import DMetadata
    for U in  'reviewer', :
        user = UsMo.objects.filter(username=U).get()
        Per = "view_view", "view_blob" , "download"
        print('*** adding permissions to user %r: %r' % (U,Per))
        metadata_content_type = ContentType.objects.get_for_model(DMetadata)
        for pn in Per:
            permission = Permission.objects.get(content_type = metadata_content_type,
                                                codename=pn)
            user.user_permissions.add(permission)
            permission.save()
            user.save()
    #
    if settings.USE_WALLET:
        from django_pursed.wallet.models import Wallet, Transaction
        wallet_content_type = ContentType.objects.get_for_model(Wallet)
        transaction_content_type = ContentType.objects.get_for_model(Transaction)
        for U in  'foobar', :
            user = UsMo.objects.filter(username=U).get()
            Per = (wallet_content_type, "operate"), (wallet_content_type , "view_wallet") , (transaction_content_type, "view_transaction")
            print('*** adding permissions to user %r: %s' % (U,Per))
            for ct, pn in Per:
                permission = Permission.objects.get(content_type = ct,
                                                    codename=pn)
                user.user_permissions.add(permission)
                permission.save()
                user.save()
    #
    print('*** creating superuser "napoleon" password "adrian"')
    try:
        UsMo.objects.create_superuser('napoleon',email=_build_fake_email('napoleon'),password='adrian').save()
    except IntegrityError:
        pass
    except Exception as e:
        print('Cannot create user %r : %r' %(U,e))    
    return True 

def add_blob(logger, user, COLDOC_SITE_ROOT, coldoc_nick, parent_uuid, environ, lang, selection_start = None, selection_end = None, add_beginend = True):
    " returns (success, message, new_uuid)"
    #
    from ColDoc.utils import slug_re
    assert isinstance(coldoc_nick,str) and slug_re.match(coldoc_nick), coldoc_nick
    assert ((isinstance(lang,str) and slug_re.match(lang)) or lang is None), lang
    assert isinstance(parent_uuid,str) and slug_re.match(parent_uuid), parent_uuid
    assert isinstance(environ,str), environ
    if isinstance(selection_end,int) and selection_end<0: selection_end = None
    if isinstance(selection_start,int) and selection_start<0: selection_start = None
    #
    import ColDoc.config as CC
    #
    if lang is None:
        lang_ = ''
    else:
        lang_ = '_'+lang
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
        from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
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
    import ColDocDjango.ColDocApp.models as coldocapp_models
    import ColDocDjango.UUID.models as  blob_models
    metadata_class=blob_models.DMetadata
    #
    #try:
    parent_uuid_, parent_uuid_dir, parent_metadata = utils.resolve_uuid(uuid=parent_uuid, uuid_dir=None,
                                                   blobs_dir = blobs_dir, coldoc = coldoc_nick,
                                                   metadata_class=metadata_class)
    logger.debug('Resolved parent as %r', parent_uuid_dir)
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
    if not user.has_perm('UUID.change_blob',parent_metadata):
        logger.error("Permission denied (change_blob)")
        return False, "Permission denied (change_blob)", None
    if not user.has_perm('UUID.change_dmetadata',parent_metadata):
        logger.error("Permission denied (change_dmetadata)")
        return False, "Permission denied (change_dmetadata)", None
    try:
        parent_metadata.author.get(id=user.id)
    except ObjectDoesNotExist :
        logger.debug("User %r is not an author of %r",user,parent_uuid)
        if  not user.has_perm('ColDoc.add_blob'):
            a=("Permission denied (add_blob) and %r is not an author of %r"%(user,parent_uuid))
            logger.error(a)
            return False, a, None
    else:
        logger.debug("User %r is an author of %r",user,parent_uuid)
    #
    # FIXME TODO maybe we should insert the "input" for all languages available?
    parent_abs_filename = os.path.join(blobs_dir, parent_uuid_dir, 'blob' + lang_ + '.tex')
    if not os.path.exists(parent_abs_filename):
        a="Parent does not exists %r"%parent_abs_filename
        logger.error(a)
        return False, a, None
    #
    filename = None
    while not filename:
        new_uuid = utils.new_uuid(blobs_dir=blobs_dir)
        new_dir = utils.uuid_to_dir(new_uuid, blobs_dir=blobs_dir, create=True)
        filename = osjoin(new_dir,'blob' + lang_ + extension)
        if os.path.exists( osjoin(blobs_dir, filename) ):
            logger.error(' output exists %r, trying next UUID' % filename)
            filename = None
    #
    child_metadata = metadata_class(coldoc=parent_metadata.coldoc, uuid=new_uuid)
    #child_metadata.add('uuid', new_uuid)
    if extension is not None:
        child_metadata.add('extension',extension)
    child_metadata.add('environ',environ)
    if lang is not None:
        child_metadata.add('lang',lang)
    if environ[:2] == 'E_' and environ[2:] in blobinator_args['private_environment']:
        child_metadata.add('access', 'private')
    child_metadata.save()
    child_metadata.add('author',user)
    parent_metadata.add('child_uuid',new_uuid)
    child_metadata.save()
    #
    placeholder='placeholder'
    parent_file = open(parent_abs_filename).read()
    if selection_start is not None and selection_end != selection_start:
        placeholder = parent_file[selection_start:selection_end]
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
            f.write("\\includegraphics{"+filename+"}")
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
            f.write("\\uuid{%s}%%\n" % (new_uuid,))
            f.write(placeholder+'\n')
    #
    # write  the metadata (including, a a text copy in filesytem)
    parent_metadata.save()
    return True, ("Created blob with UUID %r, please edit %r to properly input it (a stub \\input was inserted for your convenience)"%(new_uuid,parent_uuid)), new_uuid
    #except Exception as e:
    #    logger.error("Exception %r",e)
    #    return False, "Exception %r"%e


def reparse_all(writelog, COLDOC_SITE_ROOT, coldoc_nick, lang = None, act=True):
    " returns (success, message, new_uuid)"
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
    from ColDocDjango.ColDocApp.models import DColDoc
    coldoc = list(DColDoc.objects.filter(nickname = coldoc_nick))
    coldoc = coldoc[0]
    #if not coldoc:
    #    return HttpResponse("No such ColDoc %r." % (NICK,), status=http.HTTPStatus.NOT_FOUND)
    from ColDoc.utils import reparse_blob, choose_blob
    from ColDocDjango.UUID.models import DMetadata
    for metadata in DMetadata.objects.filter(coldoc = coldoc, extension='.tex\n'):
        for avail_lang in metadata.get('lang'):
            try:
                filename, uuid, metadata, lang, ext = choose_blob(blobs_dir=blobs_dir, ext='.tex', lang=avail_lang, metadata=metadata)
            except ColDocException:
                pass
            else:
                def warn(msg):
                    writelog('Parsing uuid %r lang %r : %s'%(uuid,lang,msg))
                reparse_blob(filename, metadata, blobs_dir, warn, act=act)


def check_tree(warn, COLDOC_SITE_ROOT, coldoc_nick, lang = None):
    " returns `problems`, a list of problems found in tree"
    # TODO implement some tree check regarding `lang`
    #
    from functools import partial
    from ColDoc.utils import recurse_tree
    from ColDocDjango.UUID.models import DMetadata
    #
    from ColDoc.utils import slug_re
    assert isinstance(coldoc_nick,str) and slug_re.match(coldoc_nick), coldoc_nick
    assert ((isinstance(lang,str) and slug_re.match(lang)) or lang is None), lang
    #
    coldoc_dir = osjoin(COLDOC_SITE_ROOT,'coldocs', coldoc_nick)
    assert os.path.exists(coldoc_dir), ('Does not exist coldoc_dir=%r\n'%(coldoc_dir))
    #
    blobs_dir = osjoin(coldoc_dir, 'blobs')
    #
    from ColDoc.utils import tree_environ_helper
    teh = tree_environ_helper(blobs_dir=blobs_dir)
    #
    from ColDocDjango.ColDocApp.models import DColDoc
    coldoc = DColDoc.objects.get(nickname = coldoc_nick)
    #
    from ColDoc.latex import prepare_options_for_latex
    options = prepare_options_for_latex(coldoc_dir, blobs_dir, DMetadata, coldoc) 
    #
    from ColDocDjango.UUID.models import DMetadata
    #
    seen = set()
    available = set()
    all_metadata = {}
    problems = []
    #
    for metadata in DMetadata.objects.filter(coldoc = coldoc):
        available.add( metadata.uuid)
        all_metadata[metadata.uuid] = metadata
    # each one of those is equivalent
    load_by_uuid = partial(DMetadata.load_by_uuid, coldoc=coldoc)
    load_by_uuid = lambda uuid: all_metadata[uuid]
    #
    def actor(teh, seen, available, warn, problems, uuid, branch, *v , **k):
        if uuid in branch:
            warn("loop detected along branch %r",branch)
            problems.append(("LOOP", branch + [uuid]))
        ret = True
        if uuid in seen:
            ret = False
            warn("duplicate %r" % uuid)
            problems.append(("DUPLICATE", uuid))
        if uuid in available:
            available.discard(uuid)
        else:
            ret = False
            warn("already deleted from queue %r" % uuid)
        seen.add(uuid)
        if len(branch) > 1:
            c = load_by_uuid(branch[-1])
            p = load_by_uuid(branch[-2])
            if not teh.child_is_allowed(c.environ, p.environ, c.get('extension')):
                a = "The node %r %r cannot be a child of %r %r" %(c.uuid,c.environ,p.uuid,p.environ)
                problems.append(("WRONG_LINK", a))
                warn(a)
                ret = False
            #else:
            #    warn("The node %r %r can be a child of %r %r" %(c.uuid,c.environ,p.uuid,p.environ))                
        return ret
    #
    action = partial(actor, teh=teh, seen=seen, available=available, warn=warn, problems=problems)
    ret = recurse_tree(load_by_uuid, action)
    # self check
    assert bool(problems) ^ (bool(ret)), (ret,problems, bool(ret), bool(problems))
    #
    if available:
        a = ("Disconnected nodes %r"%available)
        warn(a)
        for j in available:
            problems.append(('DISCONNECTED',j))
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
    for uuid in all_metadata :
        M = all_metadata[uuid]
        env = M.get('environ')
        if len(env) != 1 :  
            logger.error('UUID %r environ %r', uuid, env)
            problems.append(("WRONG environ", uuid))
            continue
        environments[uuid] = env[0]
    # check protection
    private_environment = options.get("private_environment",[])
    if private_environment:
        for uuid in all_metadata :
            env = environments.get(uuid)
            M = all_metadata[uuid]
            if (env[:2] == 'E_') and ( bool(env[2:] in private_environment) != bool( M.access == 'private')):
                logger.warning('UUID %r environ %r access %r', uuid, env, M.access)
                problems.append(('WRONG access',uuid))
    # check that the environment of the child corresponds to the LaTex \begin/\end used in the parent
    split_graphic = options.get("split_graphic",[])
    allowed_parenthood = options.get("allowed_parenthood",{})
    for uuid in all_metadata :
        M = all_metadata[uuid]
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
                logger.warning('Parent %r includes child %r using cmd %r environ %r but child %r thinks it is environ %r',
                               parent_uuid, uuid, cmd, parent_uses_env, uuid , child_env )
                problems.append((('child env %r parent_env %r parent_cmd %r' %(child_env,parent_uses_env,cmd)),uuid))
    #
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
    from ColDocDjango.ColDocApp.models import DColDoc
    coldoc = list(DColDoc.objects.filter(nickname = coldoc_nick))
    coldoc = coldoc[0]
    #
    from ColDocDjango.UUID.models import DMetadata
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

def main(argv):
    doc = __doc__
    if django_pursed is not None:
        from django_pursed.helper import __doc__ as a
        doc += '\n'.join(a.splitlines()[5:-1])
    #
    parser = argparse.ArgumentParser(description=doc,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    COLDOC_SITE_ROOT = os.environ.get('COLDOC_SITE_ROOT')
    parser.add_argument('--coldoc-site-root',type=str,\
                        help='root of the coldoc portal (default from env `COLDOC_SITE_ROOT`)', default=COLDOC_SITE_ROOT,
                        required=(COLDOC_SITE_ROOT is None))
    parser.add_argument('--verbose','-v',action='count',default=0)
    if 'add_blob' in sys.argv or  'reparse_all' in sys.argv or 'check_tree' in sys.argv or 'list_authors' in sys.argv:
        parser.add_argument('--coldoc-nick',type=str,required=True,\
                            help='nickname of the coldoc document')
        parser.add_argument('--lang',type=str,\
                            help='language of  newly created blob')
    if 'reparse_all' in sys.argv:
        parser.add_argument('--no-act',action='store_true',\
                            help='apply changes')
    if 'add_blob' in sys.argv:
        parser.add_argument('--parent-uuid',type=str,required=True,\
                            help='parent of the newly created blob')
        parser.add_argument('--user',type=str,required=True,\
                            help='user creating the blob')
        parser.add_argument('--environ',type=str,required=True,\
                            help='environment of  newly created blob')
    parser.add_argument('command', help='specific command',nargs='+')
    if django_pursed is not None:
            from django_pursed.helper import parser_add_arguments
            parser_add_arguments(parser, argv)
    #
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
    #
    if argv[0] == 'deploy':
        return deploy(COLDOC_SITE_ROOT)
    elif argv[0] == 'set_site':
        return set_site(argv[1] if (len(argv) >= 2) else None)
    elif argv[0] == 'create_fake_users':
        return create_fake_users(COLDOC_SITE_ROOT)
    elif argv[0] == 'add_blob':
        ret = add_blob(logger, args.user, COLDOC_SITE_ROOT, args.coldoc_nick,
                        args.parent_uuid, args.environ, args.lang )
        print(ret[1])
        return ret[0] #discard message
    #
    elif argv[0] == 'reparse_all':
        def writelog(s):
            sys.stdout.write(' '+ s + '\n')
        ret = reparse_all(writelog, COLDOC_SITE_ROOT, args.coldoc_nick, args.lang, not args.no_act)
    #
    elif argv[0] == 'check_tree':
        problems = check_tree(logger.warning, COLDOC_SITE_ROOT, args.coldoc_nick)
        if problems:
            print('Problems:')
            for a in problems:
                print(' '+repr(a))
        else:
            print("Tree for coldoc %r is fine" % (args.coldoc_nick,))
        return not bool(problems)
    #
    elif argv[0] == 'send_test_email':
        return send_test_email(argv[1])
    elif argv[0] == 'list_authors':
        authors = list_authors(logger.warning, COLDOC_SITE_ROOT, args.coldoc_nick)
        for a in authors:
            print(repr(a) + '→' + repr(authors[a]))
        return True
    elif django_pursed is not None:
        from django_pursed.helper import main_call
        from django_pursed.wallet import utils
        ret = main_call(utils, argv, args)
        if ret is not None:
            return ret
        else:
            sys.stderr.write("command not recognized : %r\n" % (argv,))
            sys.stderr.write(__doc__%{'arg0':sys.argv[0]})
            return False
    else:
        sys.stderr.write("command not recognized : %r\n" % (argv,))
        sys.stderr.write(__doc__%{'arg0':sys.argv[0]})
        return False
    return ret



if __name__ == '__main__':
    ret = main(sys.argv)
    sys.exit(0 if ret else 13)

