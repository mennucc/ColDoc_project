// adapted from https://stackoverflow.com/a/23692090/5058564
// noprotect

var NICK;
var UUID;
var NICKUUID = NICK+'/'+UUID;


(function (win)
{
    //Private variables
    var _LOCALSTORAGE_KEY = 'TAB_CONTAINING_'+NICKUUID;
    var RECHECK_WINDOW_DELAY_MS = 100;
    var _initialized = false;
    var _isMainWindow = false;
    var _unloaded = false;
    var _windowArray;
    var _windowId;
    var _isNewWindowPromotedToMain = false;
    var _onWindowUpdated;

    
    function WindowStateManager(isNewWindowPromotedToMain, onWindowUpdated)
    {
        //this.resetWindows();
        _onWindowUpdated = onWindowUpdated;
        _isNewWindowPromotedToMain = isNewWindowPromotedToMain;
        _windowId = Date.now().toString();

        bindUnload();

        determineWindowState.call(this);

        _initialized = true;

        _onWindowUpdated.call(this);
    }

    //Determine the state of the window 
    //If its a main or child window
    function determineWindowState()
    {
        var self = this;
        var _previousState = _isMainWindow;

        _windowArray = localStorage.getItem(_LOCALSTORAGE_KEY);

        if (_windowArray === null || _windowArray === "NaN")
        {
            _windowArray = [];
        }
        else
        {
            _windowArray = JSON.parse(_windowArray);
        }

        if (_initialized)
        {
            //Determine if this window should be promoted
            if (_windowArray.length <= 1 ||
               (_isNewWindowPromotedToMain ? _windowArray[_windowArray.length - 1] : _windowArray[0]) === _windowId)
            {
                _isMainWindow = true;
            }
            else
            {
                _isMainWindow = false;
            }
        }
        else
        {
            if (_windowArray.length === 0)
            {
                _isMainWindow = true;
                _windowArray[0] = _windowId;
                localStorage.setItem(_LOCALSTORAGE_KEY, JSON.stringify(_windowArray));
            }
            else
            {
                _isMainWindow = false;
                _windowArray.push(_windowId);
                localStorage.setItem(_LOCALSTORAGE_KEY, JSON.stringify(_windowArray));
            }
        }

        //If the window state has been updated invoke callback
        if (_previousState !== _isMainWindow)
        {
            _onWindowUpdated.call(this);
        }

        //Perform a recheck of the window on a delay
        setTimeout(function()
                   {
                     determineWindowState.call(self);
                   }, RECHECK_WINDOW_DELAY_MS);
    }

    //Remove the window from the global count
    function removeWindow()
    {
        var __windowArray = JSON.parse(localStorage.getItem(_LOCALSTORAGE_KEY));
        for (var i = 0, length = __windowArray.length; i < length; i++)
        {
            if (__windowArray[i] === _windowId)
            {
                __windowArray.splice(i, 1);
                break;
            }
        }
        //Update the local storage with the new array
        localStorage.setItem(_LOCALSTORAGE_KEY, JSON.stringify(__windowArray));
    }

    //Bind unloading events  
    function bindUnload()
    {
        win.addEventListener('beforeunload', function ()
        {
            if (!_unloaded)
            {
                removeWindow();
            }
        });
        win.addEventListener('unload', function ()
        {
            if (!_unloaded)
            {
                removeWindow();
            }
        });
    }

    WindowStateManager.prototype.isMainWindow = function ()
    {
        return _isMainWindow;
    };

    WindowStateManager.prototype.resetWindows = function ()
    {
        localStorage.removeItem(_LOCALSTORAGE_KEY);
    };

    win.WindowStateManager = WindowStateManager;
})(window);

var WindowStateManager = new WindowStateManager(false, windowUpdated);

function textareaUpdate(isMain)
{
   classname = (isMain ? 'bg-light' : 'bg-warning');
   textarea = document.getElementById("id_BlobEditTextarea");
    if ( !  textarea ) {
        var its = isMain;
        setTimeout(function(){ textareaUpdate(its); }  , 100);
    } else {
      textarea.className = "form-group w-100 "+classname;
      textarea.readOnly = ! isMain;
   }
}

function windowUpdated()
{
    //"this" is a reference to the WindowStateManager
    isMain = this.isMainWindow();
    window.document.title  = 'Coldoc '+ NICKUUID + ( isMain ? "" : "(duplicate tab)") ;
    textareaUpdate(isMain);
}

function check_primary_tab()
{
   isMain = WindowStateManager.isMainWindow();
   if ( ! isMain) {
     alert("This content is opened in another tab/window");
     return false;
   }
   return true;
}

//Resets the count in case something goes wrong in code
//WindowStateManager.resetWindows()
