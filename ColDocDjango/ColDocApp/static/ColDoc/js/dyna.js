
// from http://www.w3schools.com/Ajax/ 

var xmlhttp;

function AJAXcheck_tree(url)
{
 let button_check_tree = document.getElementById("id_button_check_tree");
 if (   button_check_tree ) {   button_check_tree.disabled = true; }
 let check_tree_div = document.getElementById("id_check_tree");
    if (  check_tree_div ) {            check_tree_div.innerHTML = "...computing...";    }
  xmlhttp = GetXmlHttpObject();
  if (xmlhttp==null)
   {
   alert ("Your browser does not support AJAX!");
   return;
  }
  xmlhttp.onreadystatechange=check_tree_state_changed;
  xmlhttp.open("GET",url,true);
  xmlhttp.send(null);
}

function check_tree_state_changed()
{
if (xmlhttp.readyState==4)
  {
    let check_tree_div = document.getElementById("id_check_tree");
    if ( !  check_tree_div ) {
        setTimeout(check_tree_state_changed, 1000);
    }
    check_tree_div.innerHTML = xmlhttp.responseText;
    let button_check_tree = document.getElementById("id_button_check_tree");
    if (   button_check_tree ) {   button_check_tree.disabled = false; }
  }
}


//window.addEventListener('ready', AJAXcheck_tree() );

function GetXmlHttpObject()
{
if (window.XMLHttpRequest)
  {
  // code for IE7+, Firefox, Chrome, Opera, Safari
  return new XMLHttpRequest();
  }
if (window.ActiveXObject)
  {
  // code for IE6, IE5
  return new ActiveXObject("Microsoft.XMLHTTP");
  }
return null;
}

