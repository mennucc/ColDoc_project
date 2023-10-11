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
        let o0 = document.getElementById("id_div_blobeditform_split_selection");
        if ( user_can_add_blob) {
	   o0.style.display = "block";
	} else {
	   o0.style.display = "none";
	   blobeditform.split_selection.checked = false;
	}
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
   let blob_callback = (ret) => {
      if( (ret != undefined) && (blob_md5 != ret)) {
        alert("Remote blob content was changed, you may want to reload" );
        blob_md5 = ret;
   }};
   check_changed_md5(get_blob_md5_url, blob_callback);
};

var blob_polling_id = undefined;

function poll_blob_changed_md5() {
    if(blob_polling == 0 ) { return ; }
    // stop when session has expired
    if ( session_has_expired() ) { return ; }
    check_blob_changed_md5();
    if ( session_has_expired() ) { return ; }
    blob_polling_id = setTimeout(poll_blob_changed_md5, blob_polling);
};

// start polling
blob_polling_id = setTimeout(poll_blob_changed_md5, blob_polling);

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
       let view=v[2];
       let md5=v[3];
       let id="id_view_html_" +  l;
       let e = document.getElementById(id);
       if ( view == VIEW ) {
	    view_md5 = md5;
       }
       //$('#'+id).replaceWith(h);
       if(e) {
            MathJax.typesetClear([e])
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
		if ( msg ) {
		 let div_messages = document.getElementById("id_messages");
		 div_messages.innerHTML += msg;
		 $('.toast').toast("show");
		}
	}
	if ( 'arrows_html' in response ) {
		let msg = JSON.parse(response['arrows_html']);
		let div_arrows = document.getElementById("id_navigation_arrows");
		div_arrows.innerHTML = msg;
	}
	if ( 'latex_errors_html' in response ) {
		let msg = JSON.parse(response['latex_errors_html']);
		let div_errors = document.getElementById("id_latex_error_logs");
		div_errors.innerHTML = msg;
		// console.log('error=',msg);
	} // else console.log('no error');
	if ( 'biblio_index_html' in response ) {
		let msg = JSON.parse(response['biblio_index_html']);
		let div_b_i = document.getElementById("id_biblio_index");
		if ( div_b_i ) {
		    div_b_i.innerHTML = msg;
		}
	}
}

function ajax_error_handler(jqXHR, error_code, exception_object)  {
	window.document.title  = '⚠ ' + UUID + ' — ' + NICK + ' — Coldoc ';
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
   // permanently stop view_poll, and disable blob_poll  
   blob_polling = 0 ; view_polling = 0 ;
   clearTimeout(blob_polling_id);
   clearTimeout(view_polling_id);
 }
 $.ajax(ajax_views_url, {
	   type: "POST",
	   url: ajax_views_url,
	   dataType: "json",
	   data: { csrfmiddlewaretoken:  csrf_token },
	   error: ajax_error_handler,
	   success: function(response, success_code, jqXHR) {
		window.document.title  = UUID + ' — ' + NICK + ' — Coldoc ';
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
 if ( ! session_has_expired() ) {
    blob_polling = blob_polling_default;
    blob_polling_id = setTimeout(poll_blob_changed_md5, blob_polling);
  };
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
    window.document.title  = '⏲ ' + UUID + ' — ' + NICK + ' — Coldoc ';
   }
   if ( type == "save_no_reload" ) {
    $("#id_blobeditform_save_no_reload").addClass("progress-bar-striped progress-bar-animated");
   }
   if ( type == "normalize" ) {
    $("#id_blobeditform_normalize").addClass("progress-bar-striped progress-bar-animated");
   }
   if ( type == "revert" ) {
    $("#id_blobeditform_revert").addClass("progress-bar-striped progress-bar-animated");
   }

  update_editform();
  let blobeditform = document.getElementById("id_form_blobeditform");
   // serializes the form's elements.
  let data = $("#id_form_blobeditform").serializeArray();
  // add permissions
  data = data.concat([ {name: 'user_can_save', value: user_can_save},
                       {name: 'user_can_add_blob', value: user_can_add_blob}],);
  // add fake button press
  data = data.concat([ {name: type, value: type},]);
  // post form
  $.ajax(blobeditform.action, {
	   type: "POST",
	   url: blobeditform.action,
	   data: data,
	   dataType: "json",
	   timeout: 16000,
	   error: ajax_error_handler,
	   success: function(response, success_code, jqXHR) {
	       let ne = document.getElementById("id_network_error");
	       if (ne) { ne.style.display = 'none'; }
	       let blob_uncompiled_ = response['uncompiled'];
	       let blobeditform = document.getElementById("id_form_blobeditform");
	       if ( 'session_expired' in response ) {
		  session_expired_p = true;
	       }
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
		     blobeditform.selection_end.value = blobeditform.selection_start.value;
		     BlobEditCodeMirror.setValue(b);
		     // it is triggered after the edit area is refreshed,  in update_blobedit_timestamp()
		     // restore_editform_cm_once()
	            }
	       } else { console.log("Did not get blobeditarea"); }
		last_textarea_keypress = 0;
		if ( (! session_has_expired()) && 
		    (type == 'save_no_reload' || type == 'compile_no_reload' || type == 'revert') ) {
		    $("#id_blobeditform_save_no_reload").removeClass("btn-warning progress-bar-striped progress-bar-animated").addClass("btn-primary");
		    $("#id_blobeditform_revert").removeClass("btn-warning progress-bar-striped progress-bar-animated").addClass("btn-outline-info");
		}
		if ( (! session_has_expired()) && type == 'normalize' ) {
		    $("#id_blobeditform_normalize").removeClass("btn-warning progress-bar-striped progress-bar-animated").addClass("btn-primary");
		}
		if ( type == 'compile_no_reload') {
		 blobeditform.split_selection.checked = false;
		 hide_and_show();
		 if ( ! session_has_expired() ) {
		   $("#id_blobeditform_compile").removeClass("bg-warning").addClass("bg-info");
		   setTimeout(ajax_views_post, 100);
		 };
		 blob_uncompiled = 0;
		} else set_buttons_classes_on_uncompiled(blob_uncompiled_);
		_parse_response(response);
		prevent_unload_remove();
	   }
	 });
   // avoid to execute the actual submit of the form.
    return false;
};


function update_blobedit_timestamp()
{   
    blob_uncompiled = 1;
    if( last_textarea_keypress == 0) {
       $("#id_blobeditform_save_no_reload").removeClass("btn-primary").addClass("btn-warning");
       $("#id_blobeditform_compile").removeClass("btn-outline-info").addClass("btn-warning");
       prevent_unload_add();
   }
   // trick to restore position of cursor after compiling
   if( last_textarea_keypress == 1 && BlobEditCodeMirror) {
     restore_editform_cm_once();
   }
   last_textarea_keypress = new Date().getTime();
   // once the user starts editing, the polling is reduced to 10 seconds
   if(blob_polling > 10000) { 
     blob_polling = 10000;
     clearTimeout(blob_polling_id);
     // and a rapid check is made, that the remote was not changed
     blob_polling_id = setTimeout(poll_blob_changed_md5, 100);
   }
   return true;
};

////////////// CodeMirror specific code

var BlobEditCodeMirror = undefined;


function restore_editform_cm_once(){
    // CodeMirror code
   let url = document.location.toString();
   let blobeditform = document.getElementById("id_form_blobeditform");
   let hash = url.split('#')[1];
   if ( hash == "blob") {
      BlobEditCodeMirror.focus();
    }
    let from = JSON.parse(blobeditform.selection_start.value);
    let to   = JSON.parse(blobeditform.selection_end.value);
    BlobEditCodeMirror.setSelection(from, to);
}


const cmlh_p = import("./cmlh.mjs");

var cmlh = undefined;
var macros_json = undefined;

$.ajax(macros_json_url, {
	   type: "GET",
	   url: macros_json_url,
	   dataType: "json",
	   timeout: 16000,
	   error: () => { macros_json = false;} ,
	   success: ( response ) => {   macros_json = response; }
	   }
);

function cmlh_fulfill(m) {
    cmlh = m;
    if (  macros_json == undefined ) {
     setTimeout(() => { cmlh_fulfill(cmlh); }, 100 );
     return;
    };
    if (  macros_json == false ) { return ; };
    CodeMirror.registerHelper("hint", "stex", (cm) => m.LaTeXHint(cm, macros_json));
};

if (use_CodeMirror) 
 { cmlh_p.then(cmlh_fulfill); };

function activate_BlobEditCodeMirror(e) {
  let textarea = document.getElementById("id_BlobEditTextarea");
  BlobEditCodeMirror = CodeMirror.fromTextArea(textarea, {
      mode: "text/x-stex",
      matchBrackets: true,
      extraKeys: {"Alt-F": "findPersistent", 
                  "Ctrl-Space": "autocomplete"},
      lineNumbers:  true,
      showTrailingSpace : true,
      readOnly: (( ! check_primary_tab() ) || ( ! user_can_save ) )
      // FIXME gutters: ["CodeMirror-linenumbers", "breakpoints"]
      });
  BlobEditCodeMirror.on("change", update_blobedit_timestamp );

  setTimeout(restore_editform_cm_once, 100);
};


function activate_BlobEditCodeMirror_once(e) {
  if( BlobEditCodeMirror == undefined && e.target.href.includes('#blob')) {
    activate_BlobEditCodeMirror(e);
  }
};
