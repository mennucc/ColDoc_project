UUID Permissions
================

(See in ColDocDjango/users.py for more details).

There is a list of permissions for each UUID. Currently it is:
'view_view', 'view_log', 'view_blob', 'change_blob', 'download', 'commit', 'view_dmetadata', 'change_dmetadata'

Permissions are associated to the UUID of the blob,
so they are the same for all languages and/or content types.
(Internally, they are associated to the `DMetadata` class).

Inside Django, the complete name of such permissions is of the form `UUID.name`.

Permissions for a specific coldoc
---------------------------------

For each permission above of the form `aaaa_bbbb` and any `coldoc` with nickname `cccc` there is also a permission
`aaaa_bbbb_on_blob_inside_cccc`, that is specific for that coldoc.

- An user that has permission  `aaaa_bbbb` automatically has permission
  `aaaa_bbbb_on_blob_inside_cccc` for any UUID in any coldoc.

- An user that has permission  `aaaa_bbbb_on_blob_inside_cccc` automatically has permission
  `aaaa_bbbb` for any UUID in the coldoc with nickname `cccc`.

Special users
-------------

An author of a blob has all the above permissions for that blob.

An anonymous user (an user that accesses the portal and is not
authenticated) has very limited permissions: s/he has the `view_view`
permission only if the coldoc has the `anonymous_can_view` flag set to
True, and the blob the UUID `access` state is `open` or `public`.

Meaning of permissions, and rules
---------------------------------

This is the Permissions meaning and rule for each `UUID`.

(Recall that each UUID has an `access` metadata that can be
`open` , `public` or `private`.)

- `view_view` : permission to  view a a `view` (a representation of the blob, as a html or PDF).
  If the UUID `access` state is

  - `open` or `public`, this is always granted to authenticated users; and
     granted to anonymous users if the property `Anonymous can view` is set in the coldoc settings
     (an editor can change it from the main web page for the coldoc)

  - `private` , it is granted to the author or any user with `view_view` permission

- `view_blob` : permission to  view real content of the blob.
  If the UUID `access` state is

  - `open`  this is always granted to authenticated users.

  - `private` or `public` , it is granted to the author or any user with `view_blob` permission

- `download` : permission to download the content of this blob in nice formatted ways.
  If the UUID `access` state is

  - `open`  this is always granted to authenticated users.

  - `private` or `public` , it is granted to the author or any user with `download`.

   Note that the `download` url also requires `view_view` permission.

- `view_log` : permission to  view logs created by `LaTeX` `and plastex`

Local permissions
-----------------

The `ColDoc` portal uses the `django-guardian` library, so that
a specific permission can be given to an user for only one object.

Note that if the user has a certain permission for the whole coldoc,
than it has that permission for any object in that coldoc.
This only holds for permissions listed above (those associated to the `DMetadata` class,
that start with `UUID.`).

Buying local permissions
------------------------

There is a provision so that an user can buy certain permissions
using `eulercoins`. For this, the library `django-wallet` must be installed
(a special version, available on demand); then a function `PRICE_FOR_PERMISSION`
must be defined in the `settings` file (an example is in the `settings_suggested.py` file):
given a `user`, a `blob` (an instance of `DMetadata`) and a  `permission`, the
function will decide if the user can buy that permission for that object, and the price.

Note that an user must have `operate` permissions on `wallet` objects to buy something.


Access to protected content in the whole document
-------------------------------------------------

As aforementioned, the LaTeX data is stored on disk inside a `blobs`
directory tree.

Two versions of the whole document are generated, one from the `blobs` tree,
and in this case the generate document (both HTML and PDF) will contain all the material:
this is the `private` version of the document.

Another version is from the `anon` tree.  The `anon` tree is automatically
generated as a copy of the `blobs` tree where all material with `access` set to `private`
will be masked out. This is the `public` version of the whole document.

LaTeX macros
------------

In the coldoc metadata there are three keys: `latex_macros_private`,  `latex_macros_public`
and  `latex_macros_uuid`.
These contain LaTeX macros.

When compiling the `private whole document` the  `latex_macros_private` is automatically insert just after
the `documentclass` ; the  `latex_macros_public` when compiling  `public whole document`;
the `latex_macros_uuid` when compiling one single blob in one UUID

The defaults are:

- `latex_macros_private` defaults to

  .. code:: tex
	    
	    \newif\ifColDocPublic\ColDocPublicfalse
	    \newif\ifColDocOneUUID\ColDocOneUUIDfalse

- `latex_macros_public` defaults to

  .. code:: tex
	    
	    \newif\ifColDocPublic\ColDocPublictrue
	    \newif\ifColDocOneUUID\ColDocOneUUIDfalse

- `latex_macros_uuid` defaults to

  .. code:: tex

	    \newif\ifColDocPublic\ColDocPublicfalse
	    \newif\ifColDocOneUUID\ColDocOneUUIDtrue

Note that `\ifColDocPublicfalse` is used when compiling each single blob by itself: this makes sense since in this case
the web interface will make sure that only authorized users can access the content.

The value of these macros can be used to trigger different behaviours in the preamble
and in the document.


Accessing the whole document
----------------------------

The whole document can be accessed using buttons
`View whole document` and  `View whole document, as PDF`
in the main page of the coldoc.

These buttons will serve either the `private` or the `public` version.


If the user is an `editor`, or s/he has the `view_view` permission,
then the content served from the buttons is the `private` version
(compile from the material inside the `blobs` directory);
note that in this case the HTML pages use a green theme, to distinguish;
otherwise it is the the `public` version
(compile from the material inside the `anon` directory);
so that the generic user will not see the protected content;
in this case the HTML pages use a blue theme, to distinguish.


Note that an user that is an `author` but not an `editor`
will not see the protected content in the whole document: indeed it is
not sensible to generate different whole document representations
for each and any user.



ColDoc Permissions
==================

(See in ColDocDjango/users.py for more details).

There is a list of permissions for each ColDoc. Currently it is:
'add_blob', 'delete_blob', 'commit', 'view_dcoldoc', 'change_dcoldoc'

Inside Django, the complete name of such permissions is of the form `ColDocApp.name`.

Meaning of permissions, and rules
---------------------------------

This is the Permissions meaning and rule for some of the above.

- `add_blob` : if an user has permission `add_blob` for the whole ColDoc,
   and has permission `view_blob` for a specific UUID, then s/he can add a
   children UUID to that UUID. Moreover the author of a blob can
   always add children to that blob.
