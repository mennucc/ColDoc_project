Permissions
==============

(See in ColDocDjango/users.py for more details).

There is a list of permissions for each UUID. Currently it is:
 'view_view','view_blob','change_blob','download','commit','view_dmetadata','change_dmetadata'

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
     granted to anonymous users it the property `

  - `private` , it is granted to the author or any user with `view_view` permission

- `view_blob` : permission to  view real content of the blob.
  If the UUID `access` state is

  - `open`  this is always granted to authenticated users.

  - `private` or `public` , it is granted to the author or any user with `view_blob` permission

Protecting protected content
----------------------------

The root UUID of the document refers to the whole document,

so for that the `view_view` is
enforced serving the HTML or PDF from the `anon` tree (instead of the `blobs` tree).




