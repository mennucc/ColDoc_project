"use strict";

function copy() {
    let textarea = document.getElementById("id_BlobEditTextarea");
    textarea.select(2,30);
    document.execCommand("copy");
};



function prevent_unload(e) {
//https://developer.mozilla.org/en-US/docs/Web/API/WindowEventHandlers/onbeforeunload
  // Cancel the event
  e.preventDefault(); // If you prevent default behavior in Mozilla Firefox prompt will always be shown
  // Chrome requires returnValue to be set
  e.returnValue = '';
};


var prevent_unload_added = false;

function prevent_unload_remove () {
    if (  prevent_unload_added ) {
// according to https://developer.mozilla.org/en-US/docs/Web/API/EventTarget/addEventListener
// it is not really needed to remove events
    prevent_unload_added = false;
    window.removeEventListener("beforeunload", prevent_unload);
    };
};

function prevent_unload_add() {
    if ( ! prevent_unload_added ) {
       prevent_unload_added = true;
       window.addEventListener("beforeunload", prevent_unload);
    };
};


function update_editform(){
    let blobeditform = document.getElementById("id_form_blobeditform");
 if ( use_CodeMirror && BlobEditCodeMirror != undefined ) {
     blobeditform.selection_start.value = JSON.stringify(BlobEditCodeMirror.getCursor('from'));
     blobeditform.selection_end.value = JSON.stringify(BlobEditCodeMirror.getCursor('to'));
    } else {
    let textarea = document.getElementById("id_BlobEditTextarea");
    blobeditform.selection_start.value = textarea.selectionStart;
    blobeditform.selection_end.value = textarea.selectionEnd;
  }
};

function restore_editform_non_cm(){
    let blobeditform = document.getElementById("id_form_blobeditform");
    let textarea = document.getElementById("id_BlobEditTextarea");
    if ( ! blobeditform ) {
	setTimeout(restore_editform_non_cm, 200);
	return;
    }
    
    // Non CodeMirror code
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
    }
};

////////////////////

window.addEventListener("load", (event) => {
  hide_and_show();
});

//////////////////////////////////////////

const blob_polling_default = 240000;
var blob_polling = blob_polling_default;

// check_changed_md5() is in notifychange.js

function check_blob_changed_md5() { 
   let blob_callback = (ret) => 
      { if( (ret != undefined) && (blob_md5 != ret)) {
      blob_post('save_no_reload');
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

function set_buttons_classes_on_uncompiled (b) {
  blob_uncompiled = b;
    if (  blob_uncompiled ) {
	$("#id_blobeditform_revert").removeClass("btn-outline-info").addClass("btn-warning");
	$("#id_blobeditform_compile").removeClass("btn-outline-info").addClass("btn-warning");
    } else {
	$("#id_blobeditform_revert").removeClass("btn-warning").addClass("btn-outline-info");
	$("#id_blobeditform_compile").removeClass("btn-warning").addClass("btn-outline-info");
    }
};

//////////////////////////////////////////
function update_viewarea(b)
{
    b.forEach( (v,i,a) => {
       let l=v[0];
       let h=v[1];
       let id="id_view_html_" +  l;
       let e = document.getElementById(id);
       //$('#'+id).replaceWith(h);
       if(e) {
	    e.innerHTML = h;
	    //MathJax.Hub.Queue(["Typeset",MathJax.Hub,e]);
	    MathJax.typesetPromise([e]);
	    //console.log("replace " + l);
	  } //else //console.log("replacenot " + l);
       }
    );
};

function _parse_response(response) {
	if ( 'viewarea' in response ) {
	   update_viewarea(JSON.parse(response['viewarea']));
	};
	if ( 'alert' in response ) {
                let alert_msg = JSON.parse(response['alert']);
		if ( alert_msg ) {
		  setTimeout(function() { alert(alert_msg);}, 100); 
		}
	}
	if ( 'message' in response ) {
		let msg = JSON.parse(response['message']);
		let div_messages = document.getElementById("id_messages");
		if ( msg ) {
		 const testDiv = document.createElement('div');
		 testDiv.innerHTML = msg;
		 div_messages.append(testDiv);
		 $('.toast').toast("show");
	       }
	}
}

function ajax_error_handler(jqXHR, error_code, exception_object)  {
	let ne = document.getElementById("id_network_error");
	if (ne) { ne.style.display = 'inline'; }
	$("#id_blobeditform_compile").removeClass("progress-bar-striped progress-bar-animated");
	//Possible values for the second argument (besides null) are "timeout", "error", "abort", and "parsererror".
	switch(error_code) {
	 case "timeout": alert("Network request has timed out"); break;
	 case "error": if (  exception_object ) { alert("Error on request: " + exception_object); }; break;
	 case "abort": alert("abort"); break;
	 default: console.log("While ajax post , error = " + error_code + " ,  exception =" + exception_object); break;
	} 
};

function ajax_views_post() {
 if ( compilation_in_progress ) { 
   $("#id_view").addClass("bg-warning");
   $("#id_blobeditform_compile").removeClass("btn-warning btn-outline-info bg-warning").addClass("bg-info progress-bar-striped progress-bar-animated");
   blob_polling = 0 ; view_polling = 0 ;
 }
 $.ajax(ajax_views_url, {
	   type: "POST",
	   url: ajax_views_url,
	   data: {},
	   error: ajax_error_handler,
	   success: function(response, success_code, jqXHR) {
		let ne = document.getElementById("id_network_error");
		if (ne) { ne.style.display = 'none'; }
		last_textarea_keypress = 0;
		_parse_response(response);
		$("#id_view").removeClass("bg-warning");
		$("#id_blobeditform_compile").removeClass("btn-warning bg-warning bg-info progress-bar-striped progress-bar-animated").addClass("btn-outline-info");
		compilation_in_progress = 0;
		// FIXME set view polling and md5
	   },
	});
 blob_polling = blob_polling_default; setTimeout(poll_blob_changed_md5, blob_polling);
}
//////////////////////////////////////////

var last_textarea_keypress = 0;

// https://stackoverflow.com/a/18170009/5058564
// https://stackoverflow.com/a/32749586/5058564

function blob_post(type) {
  if (! check_primary_tab() ) {
     return false;
  }
  
    if( BlobEditCodeMirror != undefined ){
    BlobEditCodeMirror.save();
  }
  if ( type == "compile_no_reload" ) {
    $("#id_view").addClass("bg-warning");
    $("#id_blobeditform_compile").removeClass("btn-outline-info btn-warning bg-info").addClass("bg-warning progress-bar-striped progress-bar-animated");
    blob_polling = 0 ; view_polling = 0 ;
    compilation_in_progress = 1;
   }

  update_editform();
  let blobeditform = document.getElementById("id_form_blobeditform");
   // serializes the form's elements.
  let data = $("#id_form_blobeditform").serializeArray();
  // add fake button press
  data = data.concat([ {name: type, value: type},]);
  // post form
  $.ajax(blobeditform.action, {
	   type: "POST",
	   url: blobeditform.action,
	   data: data,
	   timeout: 16000,
	   error: ajax_error_handler,
	   success: function(response, success_code, jqXHR) {
	       let ne = document.getElementById("id_network_error");
	       if (ne) { ne.style.display = 'none'; }
	       let blob_uncompiled_ = response['uncompiled'];
	       let blobeditform = document.getElementById("id_form_blobeditform");
	       if ( 'blobdiff' in response ) {
		 let blobdiff = JSON.parse(response['blobdiff']);
		 let blobdiffdiv = document.getElementById("id_blob_diff");
		  if(blobdiffdiv) { blobdiffdiv.innerHTML = '<pre>' + blobdiff + '</pre>'; }
	       } else { console.log("Did not get blobdiff"); }
	       if ( 'blob_md5' in response ) {
		  blob_md5 = response['blob_md5'];
		  blobeditform.file_md5.value = blob_md5;
	       } else { console.log("Did not get blob_md5"); }
	       if ( 'blobeditarea' in response ) {
		  let b = JSON.parse(response['blobeditarea']);
		  blobeditform.BlobEditTextarea.value = b;
		  if( BlobEditCodeMirror != undefined ){
		     // trick 'setValue' will emit a 'change' but we inhibit it
		     last_textarea_keypress = 1;
		     BlobEditCodeMirror.setValue(b);
	            }
	       } else { console.log("Did not get blobeditarea"); }
		last_textarea_keypress = 0;
		if ( type == 'save_no_reload') {
		    $("#id_blobeditform_save_no_reload").removeClass("btn-warning").addClass("btn-primary");
		}
		if ( type == 'compile_no_reload') {
		 $("#id_blobeditform_compile").removeClass("bg-warning").addClass("bg-info");
		 blobeditform.split_selection.checked = false;
		 hide_and_show();
		 setTimeout(ajax_views_post, 100);
		 blob_uncompiled = 0;
		} else set_buttons_classes_on_uncompiled(blob_uncompiled_);
		_parse_response(response);
		prevent_unload_remove();
	   }
	 });
   // avoid to execute the actual submit of the form.
    return false;
};

//$("#id_blobeditform_save_no_reload").click(blob_save_no_reload);


function update_blobedit_timestamp()
{   
    blob_uncompiled = 1;
    if( last_textarea_keypress == 0) {
       $("#id_blobeditform_save_no_reload").removeClass("btn-primary").addClass("btn-warning");
       $("#id_blobeditform_compile").removeClass("btn-outline-info").addClass("btn-warning");
       prevent_unload_add();
   }
   last_textarea_keypress = new Date().getTime();
   // once the user starts editing, the polling is reduced to 10 seconds
   if(blob_polling > 10000) { blob_polling = 10000; setTimeout(poll_blob_changed_md5, blob_polling); }
   return true;
};

