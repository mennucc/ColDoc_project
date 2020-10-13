Permissions
==============

(See in ColDocDjango/users.py for more details).

There is a list of permissions for each UUID. Currently it is:
 'view_view','view_log','view_blob','change_blob','download','commit','view_dmetadata','change_dmetadata'

Permissions are associated to the UUID of the blob,
so they are the same for all languages and/or content types.

Permissions for a specific coldoc
---------------------------------

For each permission above of the form `aaaa_bbbb` and any `coldoc` with nickname `cccc` there is also a permission
`aaaa_bbbb_on_blob_inside_cccc`, that is specific for that coldoc.

- An user that has permission  `aaaa_bbbb` automatically has permission
  `aaaa_bbbb_on_blob_inside_cccc` for any coldoc.

- An user that has permission  `aaaa_bbbb_on_blob_inside_cccc` automatically has permission
  `aaaa_bbbb` for the coldoc with nickname `cccc`.

Permissions for an UUID
-----------------------

An author of a blob has all the above permissions for that blob.

An anonymous user (an user that accesses the portal and is not
authenticated) has very limited permissions: s/he has the `view_view`
permission only if the coldoc has the `anonymous_can_view` flag set to
True, and the blob the UUID `access` state is `open` or `public`.

This is the Permissions meaning and rule for each `UUID`.

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

- `view_log` : permission to  view logs created by `LaTeX` `and plastex`

LaTeX macros
------------

In the coldoc metadata there are three keys: `latex_macros_private`,  `latex_macros_public`
and  `latex_macros_uuid`.

When compiling the `private whole document` the  `latex_macros_private` is automatically insert just after
the `documentclass` ; the  `latex_macros_public` when compiling  `public whole document`;
the `latex_macros_uuid` when compiling one single blob in one UUID

The defaults are:

-  `latex_macros_private` defaults to `\newif\ifColDocPublic\ColDocPublicfalse \newif\ifColDocOneUUID\ColDocOneUUIDfalse`

-  `latex_macros_public` defaults to `\newif\ifColDocPublic\ColDocPublictrue  \newif\ifColDocOneUUID\ColDocOneUUIDfalse`

-  `latex_macros_uuid` defaults to `\newif\ifColDocPublic\ColDocPublicfalse  \newif\ifColDocOneUUID\ColDocOneUUIDtrue`

Note that `\ifColDocPublicfalse` is used when compiling each single blob by itself: this makes sense since in this case
the web interface will make sure that only authorized users can access the content.

The value of these macros can be used to trigger different behaviours in the preamble
and in the document.
----------------------------

If the user is not an `editor`, then
the content served from the buttons `View whole document` and  `View whole document, as PDF`
is compiled from an `anon` tree where all protected content is masked out,
so that the generic user will not see the protected content; indeed it is
not sensible to generate different whole document representations
for each and any user.

Insted when the user accessing it is an `editor` then the content will all be visible;
note that in this case the HTML pages use a green theme, to distinguish.



