"use strict";

function check_changed_md5(get_md5_url, callback) {
  if ( get_md5_url == '' ) { return undefined; };
  return  $.get( get_md5_url, function( response ) {
     if ( 'file_md5' in response ) {
       let real_file_md5 = response['file_md5'];
       callback( real_file_md5 );
     } else { console.log("Error in getting the MD5 from " + get_md5_url ); callback(undefined); }
   });
};


function check_view_changed_md5() { 
   let view_callback = (ret) => 
      { if((ret != undefined) && (view_md5 != ret)) {
        alert("Remote file was changed, you may want to reload" ); view_md5 = ret; 
      }};
   check_changed_md5(get_view_md5_url, view_callback);
};

//////////////////////////////////////////

var view_polling = 600000;

function poll_view_changed_md5() {
    if(view_polling == 0 ) { return ; }
    check_view_changed_md5();
    setTimeout(poll_view_changed_md5, view_polling);
};

// start polling
setTimeout(poll_view_changed_md5, view_polling);

///////////////////////////////////////////

