import threading
import time

from Util.pyinstaller_patch import debugger


class ThreadWrapper(threading.Thread):
    def __init__(self, callback, parameters, break_trigger, fn_name, context=None):
        super(ThreadWrapper, self).__init__()
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
                for key, item in self._parameters.items():
                    setattr(self._callback, key, item)
        else:
            for key, item in self._parameters.items():
                setattr(self._callback, key, item)
        return
