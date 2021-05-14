import re
from dataclasses import dataclass
from typing import Dict, List

RE_ACL = re.compile(r"(?s)^(?P<addremove>\+|-)(?P<deny>!)?(?P<prefix>\w+):(?P<name>.*?)(?::(?P<mode>.*?))?(?P<perms>(\/\w+){1,})$")
# +!A:Volund:friends/read/boogaloo


@dataclass
class ACLEntry:
    remove: bool
    deny: bool
    identity: IdentityDB
    perms: List[str]
    mode: str = ""


class ACLHandler:
    permissions_base = {"full": 1}
    permissions_custom = {}
    permissions_init = "+S:OWNER/full"
    permissions_implicit = {}

    def __init__(self, obj):
        self.obj = obj

    def integrity_check(self):
        if not self.is_initialized():
            self.initialize()

    def is_initialized(self) -> bool:
        return bool(self.obj.db._acl_init)

    def initialize(self):
        if self.do_initialize():
            self.set_initialized()

    def set_initialized(self):
        self.obj.db._acl_init = True

    def do_initialize(self) -> bool:
        try:
            self.apply_acl(self.parse_acl(self.permissions_init))
        except Exception as e:
            return False
        return True

    def perm_dict(self) -> Dict[str, int]:
        d = dict()
        d.update(self.permissions_base)
        d.update(self.permissions_custom)
        return d

    def is_owner(self, obj_to_check) -> bool:
        return False

    def check_access(self, accessor, perm: str) -> bool:
        return self.check_acl(accessor, perm)

    def check_acl(self, accessor, perm: str) -> bool:
        self.integrity_check()
        pdict = self.perm_dict()
        entries = list()

        # On the off-chance 're fed a non-identity, try and coerce it into one.
        try:
            accessor = accessor.get_identity()
        except Exception:
            return False
        if not accessor:
            return False

        bit = pdict[perm] + 1
        for p in self.permissions_implicit.get(perm, []):
            bit += pdict.get(p, 0)

        for entry in self.obj.acl_entries.all():
            if entry.identity.represents(accessor, entry.mode):
                # First, check for Denies.
                if entry.deny_permissions | bit:
                    return False
                entries.append(entry)

        for entry in entries:
            # Then check for Allows.
            if entry.allow_permissions | bit:
                return True

        return False

    def parse_acl(self, entry, enactor=None) -> List[ACLEntry]:
        entries = list()

        for s in entry.split(','):
            if not (match := RE_ACL.match(s)):
                print(match)
                raise ValueError(f"invalid ACL entry: {s}")
            gd = match.groupdict()
            deny = bool(gd.get('deny', False))
            remove = True if gd.get('addremove') == '-' else False
            if enactor:
                identity = enactor.find_identity(prefix=gd.get('prefix'), name=gd.get('name'))
            else:
                identity = IdentityDB.objects.filter(db_namespace__db_prefix__iexact=gd.get('prefix'), db_key__iexact=gd.get('name')).first()
            if not identity:
                raise ValueError(f"Identity Not found: {s}")
            mode = gd.get('mode', '')
            perms = [p.strip().lower() for p in gd.get('perms').split('/') if p]
            p_dict = self.perm_dict()
            for perm in perms:
                if perm not in p_dict:
                    raise ValueError(f"Permission not found: {perm}")

            acl_e = ACLEntry(remove, deny, identity, perms, mode)
            entries.append(acl_e)

        return entries

    def apply_acl(self, entries: List[ACLEntry], report_to=None):
        p_dict = self.perm_dict()
        for entry in entries:
            mode = entry.mode if entry.mode else ''
            if not (row := self.obj.acl_entries.filter(identity=entry.identity, mode=mode).first()):
                row = self.obj.acl_entries.create(identity=entry.identity, mode=mode)
            bitfield = int(row.allow_permissions if not entry.deny else row.deny_permissions)
            if entry.remove:
                for perm in entry.perms:
                    pval = p_dict.get(perm)
                    if pval & bitfield:
                        bitfield -= pval
            else:
                for perm in entry.perms:
                    pval = p_dict.get(perm)
                    bitfield = bitfield | pval
            if entry.deny:
                row.deny_permissions = bitfield
            else:
                row.allow_permissions = bitfield
            row.save()
            if row.allow_permissions == 0 and row.deny_permissions == 0:
                row.delete()

    def render_acl(self, looker=None):
        self.integrity_check()
