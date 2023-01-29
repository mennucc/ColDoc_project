"use strict";

function html_hide_substitute(url, identP, identA, identB, identC, identD)
{
  P = document.getElementById(identP);
  A = document.getElementById(identA);
  B = document.getElementById(identB);
  C = document.getElementById(identC);
  D = document.getElementById(identD);
  A.style.display = "inline";
  B.style.display = "inline";
  C.style.display = "none";
  D.style.display = "none";
}

function html_retrieve_substitute(url, identP, identA, identB, identC, identD)
{
  P = document.getElementById(identP);
  A = document.getElementById(identA);
  B = document.getElementById(identB);
  C = document.getElementById(identC);
  D = document.getElementById(identD);
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
     } else { classname == python_main_class ; }
   }
   if (classname == undefined || classname == '' ) { return ; }
   let main = document.getElementsByTagName("main");
   main = main[0];
   main.classList.remove(previous_main_class);
   main.classList.add(classname);
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
