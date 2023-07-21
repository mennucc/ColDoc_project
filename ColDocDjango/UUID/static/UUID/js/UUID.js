"use strict";

function html_hide_substitute(url, identP, identA, identB, identC, identD)
{
  let P = document.getElementById(identP);
  let A = document.getElementById(identA);
  let B = document.getElementById(identB);
  let C = document.getElementById(identC);
  let D = document.getElementById(identD);
  A.style.display = "inline";
  B.style.display = "inline";
  C.style.display = "none";
  D.style.display = "none";
}

function html_retrieve_substitute(url, identP, identA, identB, identC, identD)
{
  let P = document.getElementById(identP);
  let A = document.getElementById(identA);
  let B = document.getElementById(identB);
  let C = document.getElementById(identC);
  let D = document.getElementById(identD);
  $.ajax(B.action, {
	   type: "GET",
	   url: url,
	   success: function(response)  {
	     A.style.display = "none";
	     B.style.display = "none";
	     C.style.display = "inline";
	     // bootstrap 4 need these
	     C.style.top = "0";
	     C.style.right = "0";
             //
             D.innerHTML = response;
             D.style.display = "block";
	     D.append(C);
	     MathJax.typeset();
	     },
	   error: function(){
	     B.style.display = "none";
	     alert('Cannot access element');
           },
	}
   );
};


const main_width_cookie_name = 'main_width';

function mainClassUpdate(classname)
{
   let c = Cookies.get(main_width_cookie_name);
   if (classname == undefined) {
    if ( python_main_class == "") {
      if ( c=='large') { classname = 'container-fluid' ; }
      if ( c=='small') { classname = 'container' ; }
      if ( c==undefined) { classname = 'container' ; }
     } else { classname = python_main_class ; }
   }
   if (classname == undefined || classname == '' ) { return ; }
   let main = document.getElementsByTagName("main");
   main = main[0];
   if ( ! main.classList.contains(classname) ) {
    main.classList.remove(previous_main_class);
    main.classList.add(classname);
   }
   previous_main_class=classname;
   if (classname == 'container') {
     $('#button_width_small').addClass('disabled').removeClass('btn-outline-primary').hide();
     $('#button_width_large').removeClass('disabled').addClass('btn-outline-primary').show();
     Cookies.set(main_width_cookie_name, 'small', { expires: 180, SameSite: 'Lax'});
   } else {
     $('#button_width_large').addClass('disabled').removeClass('btn-outline-primary').hide();
     $('#button_width_small').removeClass('disabled').addClass('btn-outline-primary').show();
     Cookies.set(main_width_cookie_name, 'large', { expires: 180, SameSite: 'Lax'})
   }
}

function session_has_expired() {
 if ( session_expiry_time <= 0 )
    { return false ; }
 const now =  Math.floor(Date.now() / 1000);
 return ( session_expiry_time <= now );
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
