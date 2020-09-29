
function copy() {
    let textarea = document.getElementById("id_BlobEditTextarea");
    textarea.select(2,30);
    document.execCommand("copy");
};



function update_and_send(){
    let blobeditform = document.getElementById("id_form_blobeditform");
    let textarea = document.getElementById("id_BlobEditTextarea");
    blobeditform.selection_start.value = textarea.selectionStart;
    blobeditform.selection_end.value = textarea.selectionEnd;
    document.forms["id_form_blobeditform"].submit();
};

function hide_and_show(){
    let blobeditform = document.getElementById("id_form_blobeditform");
    if ( ! blobeditform ) {
	setTimeout(hide_and_show, 1000);
    } else {
	let value = blobeditform.split_selection.checked;
	let o1 = document.getElementById("id_div_blobeditform_split_environment");
	if (value == true) {
	    o1.style.display = "block";
	} else {
	    o1.style.display = "none";
	}
    }
};

window.addEventListener('ready', hide_and_show() );

