
function copy() {
    let textarea = document.getElementById("id_BlobEditTextarea");
    textarea.select(2,30);
    document.execCommand("copy");
};



function update_editform(){
    let blobeditform = document.getElementById("id_form_blobeditform");
 if ( use_CodeMirror ) {
     blobeditform.selection_start.value = JSON.stringify(BlobEditCodeMirror.getCursor('from'));
     blobeditform.selection_end.value = JSON.stringify(BlobEditCodeMirror.getCursor('to'));
    } else {
    let textarea = document.getElementById("id_BlobEditTextarea");
    blobeditform.selection_start.value = textarea.selectionStart;
    blobeditform.selection_end.value = textarea.selectionEnd;
  }
};

function restore_editform(){
    let blobeditform = document.getElementById("id_form_blobeditform");
    let textarea = document.getElementById("id_BlobEditTextarea");
    if ( ! blobeditform ) {
	setTimeout(restore_editform, 200);
	return;
    }
    // FIXME
    if (  use_CodeMirror )    { return ; } 
    // FIXME
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

window.addEventListener('ready', restore_editform() );

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
    }
};

window.addEventListener('ready', hide_and_show() );

////////////////////

//////////////////////////////////////////

var blob_polling = 240000;

// check_changed_md5() is in unique.js

function check_blob_changed_md5() { 
   let blob_callback = (ret) => 
      { if( (ret != undefined) && (blob_md5 != ret)) {
      blob_save_no_reload();
      blob_md5 = ret; 
   }};
   check_changed_md5(get_blob_md5_url, blob_callback);
};


function poll_blob_changed_md5() {
    if(blob_polling == 0 ) { return ; }
    check_blob_changed_md5();
    setTimeout(poll_blob_changed_md5, blob_polling);
};

// start polling
setTimeout(poll_blob_changed_md5, blob_polling);

///////////////////////////////////////////

var last_textarea_keypress = 0;

// https://stackoverflow.com/a/18170009/5058564
// https://stackoverflow.com/a/32749586/5058564

function blob_save_no_reload() {
  $("#id_blobeditform_save_no_reload").removeClass("btn-warning");
  if (! check_primary_tab() ) {
     return false;
  }
  
    if( BlobEditCodeMirror != undefined ){
    BlobEditCodeMirror.save();
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
		 blobdiffdiv.innerHTML = '<pre>' + blobdiff + '</pre>';
	       } else { console.log("Did not get blobdiff"); }
	       if ( 'blob_md5' in response ) {
		  blob_md5 = response['blob_md5'];
		  let blobeditform = document.getElementById("id_form_blobeditform");
		  blobeditform.file_md5.value = blob_md5;
	       } else { console.log("Did not get blob_md5"); }
	   }
	 });
    //
    last_textarea_keypress = 0;
    $("#id_blobeditform_save_no_reload").addClass("btn-primary");
   // avoid to execute the actual submit of the form.
    return false;
};

$("#id_blobeditform_save_no_reload").click(blob_save_no_reload);


function update_blobedit_timestamp()
{   
    if( last_textarea_keypress == 0) {
       $("#id_blobeditform_save_no_reload").removeClass("btn-primary");
       $("#id_blobeditform_save_no_reload").addClass("btn-warning");
   }
   last_textarea_keypress = new Date().getTime();
   // once the user starts editing, the polling is reduced to 10 seconds
   if(blob_polling > 10000) { blob_polling = 10000; setTimeout(poll_blob_changed_md5, blob_polling); }
   return true;
};

