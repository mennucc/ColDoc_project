
function copy() {
    let textarea = document.getElementById("id_BlobEditTextarea");
    textarea.select(2,30);
    document.execCommand("copy");
};



function update_editform(){
    let blobeditform = document.getElementById("id_form_blobeditform");
    let textarea = document.getElementById("id_BlobEditTextarea");
    blobeditform.selection_start.value = textarea.selectionStart;
    blobeditform.selection_end.value = textarea.selectionEnd;
};

function restore_editform(){
    let blobeditform = document.getElementById("id_form_blobeditform");
    let textarea = document.getElementById("id_BlobEditTextarea");
    if ( blobeditform.selection_start.value  >= 0 ) {
      textarea.selectionStart = blobeditform.selection_start.value ;
      
    }
    if ( blobeditform.selection_end.value  >= 0 ) {
      textarea.selectionEnd = blobeditform.selection_end.value  ;
    }
    let url = document.location.toString();
    let hash = url.split('#')[1];
    if ( hash == "blob") {
      textarea.focus();
    }
};


function hide_and_show(){
    let blobeditform = document.getElementById("id_form_blobeditform");
    if ( ! blobeditform ) {
	setTimeout(hide_and_show, 200);
    } else {
	let value = blobeditform.split_selection.checked;
	let o1 = document.getElementById("id_div_blobeditform_split_environment");
	let o2 = document.getElementById("id_div_blobeditform_split_add_beginend");
	if (value == true) {
	    o1.style.display = "block";
	    o2.style.display = "block";
	} else {
	    o1.style.display = "none";
	    o2.style.display = "none";
	}
	restore_editform();
    }
};

window.addEventListener('ready', hide_and_show() );

////////////////////
// https://stackoverflow.com/a/18170009/5058564
// https://stackoverflow.com/a/32749586/5058564
$("#id_blobeditform_save_no_reload").click(function() {
  if (! check_primary_tab() ) {
     return false;
  }
  
  update_editform();
  let blobeditform = document.getElementById("id_form_blobeditform");
   // serializes the form's elements.
  let data = $("#id_form_blobeditform").serializeArray();
  // add fake button press
  data = data.concat([ {name: "save_no_reload", value: "save_no_reload"},]);
  // post form
  $.ajax(blobeditform.action, {
	   type: "POST",
	   url: blobeditform.action,
	   data: data,
	   success: function(response)  {
	       msg = response['message'];
	       if ( msg ) {
		 alert(msg); 
	       }
	       if ( 'blobdiff' in response ) {
		 blobdiff = response['blobdiff'];
		 blobdiffdiv = document.getElementById("id_blob_diff");
		 blobdiffdiv.innerHTML = blobdiff;
	       }
	   }
	 });
   // avoid to execute the actual submit of the form.
    return false;
});
