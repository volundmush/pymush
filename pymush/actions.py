

class BaseAction:
    name = 'N/A'

    def __init__(self, pid: int, executor: "GameObject"):
        self.pid = pid
        self.executor = executor

