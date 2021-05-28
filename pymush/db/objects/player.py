from . base import GameObject
from typing import Optional


class Player(GameObject):
    type_name = 'PLAYER'
    unique_names = True
    cmd_matchers = ('mobile', 'player', 'script')

    @property
    def account(self):
        aid = self.sys_attributes.get('account', None)
        if aid is not None:
            account = self.service.objects.get(aid, None)
            if account:
                return account

    @account.setter
    def account(self, account: Optional[GameObject] = None):
        if account:
            self.sys_attributes['account'] = int(account)
        else:
            self.sys_attributes.pop('account', None)

    def generate_identifers_name_for(self, viewer):
        if self.game.app.config.dub_system:
            return self.get_dub_or_keyphrase_for(viewer)
        else:
            return self.name
