from ..utils.optionhandler import OptionHandler


class StyleHandler:

    def __init__(self, owner, save=True):
        self.owner = owner
        self.styles = dict()
        self.load()

    def load(self):
        for k, v in self.owner.core.styles.items():
            handler = OptionHandler(self.owner, options_dict=v)
            self.styles[k] = handler

    def get(self, category: str, key: str, fallback='system'):
        if (handler_base := self.styles.get(category, None)):
            if (op := handler_base.get(key, return_obj=True)):
                if op.changed:
                    return op.value
                else:
                    if fallback and category != fallback:
                        return self.get(category=fallback, key=key, fallback='')
                    else:
                        return op.value
