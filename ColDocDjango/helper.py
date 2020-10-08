#!/usr/bin/env python3


"""
This program does some actions that `manage` does not. Possible commands:

    deploy
        create a new ColDoc site

    create_fake_users
        creates some fake users, to interact with the Django site

    add_blob
        add a an empty blob to a document
        (to import new LaTeX material in a document, use `blob_inator`)
    
    reparse_all
         reparse all blobs
    
    check_tree
        check that tree is connected and has no loops
    
Use `command` --help for command specific options.
"""

import os, sys, argparse, json
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
    del a
    #
    from ColDoc import loggin

if __name__ == '__main__':
    import logging
    logger = logging.getLogger('helper')


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
    open(COLDOC_SITE_SETTINGS,'w').write("""# settings specific for this instance
# This file will be executed after the `settings.py` file in the ColDocDjango directory
# in the source code.
""")
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
    print("TODO : migrate, collectstatic, copy  wsgi.py, create and customize an apache2.conf")
    return True

def create_fake_users(COLDOC_SITE_ROOT):
    #
    import django.contrib.auth as A
    UsMo = A.get_user_model()
    #UsMa = A.models.UserManager()
    UsMo.objects.create_user('foobar',email='foo@test.local',password='barfoo').save()
    print('*** created user "foobar" password "barfoo"')
    UsMo.objects.create_user('jsmith',email='jsmith@test.local',password='123456').save()
    print('*** created user "jsmith" password "123456"')
    UsMo.objects.create_superuser('napoleon',email='nap@test.local',password='adrian').save()
    print('*** created superuser "napoleon" password "adrian"')
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
    coldoc_dir = osjoin(COLDOC_SITE_ROOT,'coldocs', coldoc_nick)
    assert os.path.exists(coldoc_dir), ('Does not exist coldoc_dir=%r\n'%(coldoc_dir))
    #
    blobs_dir = osjoin(coldoc_dir, 'blobs')
    #
    f = osjoin(blobs_dir, '.blob_inator-args.json')
    assert os.path.exists(f), ("File of blob_inator args does not exit: %r\n"%(f,))
    with open(f) as a:
        blobinator_args = json.load(a)
    #
    if environ in CC.ColDoc_environments_cant_be_added_as_children:
        a="Cannot add a child with environ %r"%environ
        logger.error(a)
        return False, a, None
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
    parent_environ = parent_metadata.environ
    if parent_environ in CC.ColDoc_cant_add_children_to_environments:
        a="Cannot add a new child to a blob that has environ=%r " % parent_environ
        logger.error(a)
        return False, a, None
    if parent_environ in CC.ColDoc_cant_add_begin_end_children_to_environments and environ[:2] == 'E_':
        a="Cannot add a \\begin{%s}..\\end{%s} to a blob that has environ=%r " % (environ[2:],environ[2:],parent_environ)
        logger.error(a)
        return False, a, None
    #
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
        filename = osjoin(new_dir,'blob' + lang_ + '.tex')
        if os.path.exists( osjoin(blobs_dir, filename) ):
            logger.error(' output exists %r, trying next UUID' % filename)
            filename = None
    #
    child_metadata = metadata_class(coldoc=parent_metadata.coldoc, uuid=new_uuid)
    #child_metadata.add('uuid', new_uuid)
    child_metadata.add('extension','.tex')
    child_metadata.add('environ',environ)
    if lang is not None:
        child_metadata.add('lang',lang)
    if environ[:2] == 'E_' and environ[2:] in blobinator_args['private_environment']:
        child_metadata.add('access', 'private')
    child_metadata.save()
    child_metadata.add('author',user)
    blob_models.UUID_Tree_Edge(coldoc = parent_metadata.coldoc, parent = parent_uuid, child = new_uuid).save()
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
        f.write("\\input{"+filename+"}")
        if environ[:2] == 'E_' and add_beginend:
            f.write("\\end{"+environ[2:]+"}")
        f.write("\n")
        if selection_start is not None :
            f.write(parent_file[selection_end:])
    #
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


def reparse_all(logger, COLDOC_SITE_ROOT, coldoc_nick, lang = None, act=False):
    " returns (success, message, new_uuid)"
    #
    from ColDoc.utils import slug_re
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
    f = osjoin(blobs_dir, '.blob_inator-args.json')
    assert os.path.exists(f), ("File of blob_inator args does not exit: %r\n"%(f,))
    with open(f) as a:
        blobinator_args = json.load(a)
    #
    from ColDocDjango.ColDocApp.models import DColDoc
    coldoc = list(DColDoc.objects.filter(nickname = coldoc_nick))
    coldoc = coldoc[0]
    #if not coldoc:
    #    return HttpResponse("No such ColDoc %r." % (NICK,), status=http.HTTPStatus.NOT_FOUND)
    from ColDoc.utils import reparse_blob, choose_blob
    from ColDocDjango.UUID.models import DMetadata
    for metadata in DMetadata.objects.filter(coldoc = coldoc):
        for avail_lang in metadata.get('lang'):
            filename, uuid, metadata, lang, ext = choose_blob(blobs_dir=blobs_dir, ext='.tex', lang=avail_lang, metadata=metadata)
            def warn(msg):
                logger.warning('Parsing uuid %r lang %r : %s'%(uuid,lang,msg))
            reparse_blob(filename, metadata, blobs_dir, warn, act=act)


def check_tree(warn, COLDOC_SITE_ROOT, coldoc_nick, lang = None):
    " returns `problems`, a list of problems found in tree"
    # TODO implement some tree check regarding `lang`
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
    from ColDocDjango.ColDocApp.models import DColDoc
    coldoc = list(DColDoc.objects.filter(nickname = coldoc_nick))
    coldoc = coldoc[0]
    #
    from ColDocDjango.UUID.models import DMetadata
    #
    seen = set()
    available = {}
    problems = []
    #
    for metadata in DMetadata.objects.filter(coldoc = coldoc):
        available[ metadata.uuid ] = metadata
    def actor(seen, available, warn, problems, uuid, branch, *v , **k):
        if uuid in branch:
            warn("loop detected along branch %r",branch)
            problems.append(("LOOP", branch + [uuid]))
        ret = True
        if uuid in seen:
            ret = False
            warn("duplicate %r" % uuid)
            problems.append(("DUPLICATE", uuid))
        if uuid in available:
            del available[uuid]
        else:
            ret = False
            warn("already deleted from queue %r" % uuid)
        seen.add(uuid)
        return ret
    from ColDoc.utils import recurse_tree
    from ColDocDjango.UUID.models import DMetadata
    from functools import partial
    action = partial(actor, seen=seen, available=available, warn=warn, problems=problems)
    ret = recurse_tree(coldoc, blobs_dir, DMetadata, action=action)
    if available:
        a = ("Disconnected nodes %r"%available)
        warn(a)
        problems.append(('DISCONNECTED',available))
    assert bool(problems) ^ (bool(ret)), (ret,problems, bool(ret), bool(problems))
    return problems


def main(argv):
    #
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    COLDOC_SITE_ROOT = os.environ.get('COLDOC_SITE_ROOT')
    parser.add_argument('--coldoc-site-root',type=str,\
                        help='root of the coldoc portal (default from env `COLDOC_SITE_ROOT`)', default=COLDOC_SITE_ROOT,
                        required=(COLDOC_SITE_ROOT is None))
    parser.add_argument('--verbose','-v',action='count',default=0)
    if 'add_blob' in sys.argv or  'reparse_all' in sys.argv or 'check_tree' in sys.argv:
        parser.add_argument('--coldoc-nick',type=str,required=True,\
                            help='nickname of the coldoc document')
        parser.add_argument('--lang',type=str,\
                            help='language of  newly created blob')
    if 'reparse_all' in sys.argv:
        parser.add_argument('--act',action='store_true',\
                            help='apply changes')
    if 'add_blob' in sys.argv:
        parser.add_argument('--parent-uuid',type=str,required=True,\
                            help='parent of the newly created blob')
        parser.add_argument('--user',type=str,required=True,\
                            help='user creating the blob')
        parser.add_argument('--environ',type=str,required=True,\
                            help='environment of  newly created blob')
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
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ColDocDjango.settings')
    import django
    django.setup()
    #
    if argv[0] == 'deploy':
        return deploy(COLDOC_SITE_ROOT)
    elif argv[0] == 'create_fake_users':
        return create_fake_users(COLDOC_SITE_ROOT)
    elif argv[0] == 'add_blob':
        ret = add_blob(logger, args.user, COLDOC_SITE_ROOT, args.coldoc_nick,
                        args.parent_uuid, args.environ, args.lang )
        print(ret[1])
        return ret[0] #discard message
    elif argv[0] == 'reparse_all':
        ret = reparse_all(logger, COLDOC_SITE_ROOT, args.coldoc_nick, args.lang, args.act)
    elif argv[0] == 'check_tree':
        problems = check_tree(logger.warning, COLDOC_SITE_ROOT, args.coldoc_nick)
        if problems:
            print('Problems:')
            for a in problems:
                print(' '+repr(a))
        else:
            print("Tree for coldoc %r is fine" % (args.coldoc_nick,)), problems
        return not bool(problems)
    else:
        sys.stderr.write("command not recognized : %r\n" % (argv,))
        sys.stderr.write(__doc__%{'arg0':sys.argv[0]})
        return False
    return ret



if __name__ == '__main__':
    ret = main(sys.argv)
    sys.exit(0 if ret else 13)

