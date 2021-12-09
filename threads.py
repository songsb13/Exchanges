import threading
import time

from Util.pyinstaller_patch import debugger


class CallbackThread(threading.Thread):
    def __init__(self, callback, parameters, break_trigger, fn_name, context=None):
        super(CallbackThread, self).__init__()
        self._callback = callback
        self._break_trigger = break_trigger
        self._parameters = parameters
        self._fn_name = fn_name
        
        self._context = context
        
    def run(self) -> None:
        for _ in range(60):
            if self._break_trigger():
                debugger.debug('[{}], Successfully get event trigger.'.format(self._fn_name))
                break
            time.sleep(1)
        else:
            debugger.debug('[{}], Fail to get event trigger.'.format(self._fn_name))
            return
        
        if self._context:
            with self._context:
                self._callback(**self._parameters)
        else:
            self._callback(**self._parameters)
