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
