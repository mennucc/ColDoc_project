"use strict";

function session_has_expired() {
 if ( session_expiry_time <= 0 )
    { return false ; }
 const now =  Math.floor(Date.now() / 1000);
 return session_expired_p || ( session_expiry_time <= now );
}


// alert when session is expiring

if ( session_expiry_age >= 0) {
  setTimeout( function() {
       clearTimeout(blob_polling_id);
       clearTimeout(view_polling_id);
       if ( user_can_save ) {
         blob_post('save_no_reload');
	 // should lock the edit area
         alert(alert_expiry_save_message);
       } else {
         alert(alert_expiry_message);
       }
    },
    1000 * (session_expiry_age - 5 ) );
};
