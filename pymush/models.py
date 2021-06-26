from tortoise.models import Model
from tortoise import fields
from mudrich.text import Text
from typing import Optional, Union, List, Tuple, Type


class MudTextField(fields.JSONField):

    def to_db_value(self, value, instance):
        if isinstance(value, str):
            value = Text(value)
        if isinstance(value, Text):
            value = value.serialize()
        return value

    def to_python_value(self, value) -> Text:
        data = super().to_python_value(value)
        return Text.deserialize(data)


class User(Model):
    id = fields.UUIDField(pk=True)
    # In practice, name will be CASE INSENSITIVE, but adding unique constraint here for indexing doesn't hurt a bit.
    name = fields.CharField(null=True, max_length=320, unique=True)
    name_text = MudTextField(null=False)
    email = fields.CharField(null=True, max_length=320)
    deleted = fields.BooleanField(default=False, null=False, index=True)
    admin_level = fields.IntField(null=True, default=None)
    password_hash = fields.TextField(null=True)
    created = fields.BigIntField(null=False)
    modified = fields.BigIntField(null=False)
    userdata = fields.JSONField(null=True)

    class Meta:
        unique_together = (('is_group', 'name'),)


class ApiCredentials(Model):
    user = fields.ForeignKeyField("pymush.User", related_name='keys', on_delete=fields.CASCADE)
    name = fields.CharField(null=False, max_length=250)
    username = fields.CharField(null=False, max_length=250)
    token = fields.CharField(null=False, max_length=500)

    class Meta:
        unique_together = (('user', 'name'),)


class CodeLibrary(Model):
    user = fields.ForeignKeyField("pymush.User", related_name='libraries', on_delete=fields.CASCADE)
    name = fields.CharField(null=False, max_length=250, unique=True)
    url = fields.CharField(null=False, max_length=600)
    api = fields.ForeignKeyField('pymush.ApiCredentials', related_name='libraries', null=True,
                                 on_delete=fields.RESTRICT)


class Module(Model):
    name = fields.CharField(null=False, max_length=250, unique=True)
    user = fields.ForeignKeyField("pymush.User", related_name='modules', on_delete=fields.CASCADE, null=True)
    type_name = fields.CharField(null=True, max_length=250)
    url = fields.CharField(null=False, max_length=600)
    api = fields.ForeignKeyField('pymush.ApiCredentials', related_name='libraries', null=True,
                                 on_delete=fields.RESTRICT)
    maintainers = fields.ManyToManyField('pymush.User', related_name='allowed_modules')


class Prototype(Model):
    module = fields.ForeignKeyField('pymush.Module', related_name='objects', on_delete=fields.RESTRICT)
    name = fields.CharField(null=False, max_length=100)

    class Meta:
        unique_together = (('module', 'defname'),)


class GameObject(Model):
    id = fields.UUIDField(pk=True)
    type_name = fields.CharField(null=False, max_length=100, index=True)
    module = fields.ForeignKeyField('pymush.Module', related_name='objects', on_delete=fields.RESTRICT)
    key = fields.CharField(null=False, max_length=100)
    prototype = fields.ForeignKeyField('pymush.Prototype', related_name='objects', on_delete=fields.RESTRICT)
    userdata = fields.JSONField(null=True)

    class Meta:
        unique_together = (('module', 'key'),)


class GameRelationType(Model):
    # These names should always be stored in uppercase.
    name = fields.CharField(null=False, unique=True, max_length=30)


class GameRelation(Model):
    relation_type = fields.ForeignKeyField("pymush.GameRelationType", related_name='relations', on_delete=fields.RESTRICT)
    holder = fields.ForeignKeyField("pymush.GameObject", related_name='relations', on_delete=fields.CASCADE)
    target = fields.ForeignKeyField("pymush.GameObject", related_name='related_by', on_delete=fields.CASCADE)
    userdata = fields.JSONField(null=True)

    class Meta:
        unique_together = (('holder', 'relation_type'),)


class GameAttribute(Model):
    # These names should always be stored in uppercase.
    name = fields.CharField(null=False, max_length=100)
    mask = fields.BooleanField(null=False, default=False)
    userdata = fields.JSONField(null=True)

    class Meta:
        unique_together = (('name', 'mask'),)


class GameObjectAttribute(Model):
    holder = fields.ForeignKeyField("pymush.GameObject", related_name='attributes', on_delete=fields.CASCADE)
    owner = fields.ForeignKeyField("pymush.GameObject", null=True, related_name='owned_attributes',
                                   on_delete=fields.SET_NULL)
    attribute = fields.ForeignKeyField('pymush.GameAttribute', related_name='values', on_delete=fields.RESTRICT)
    value = fields.JSONField(null=False)
    userdata = fields.JSONField(null=True)

    class Meta:
        unique_together = (('holder', 'attribute'),)


class LockType(Model):
    # These names should always be stored in lowercase.
    name = fields.CharField(null=False, unique=True, max_length=50)


class GameObjectLock(Model):
    holder = fields.ForeignKeyField("pymush.GameObject", related_name='locks', on_delete=fields.CASCADE)
    owner = fields.ForeignKeyField("pymush.GameObject", null=True, related_name='owned_locks',
                                   on_delete=fields.SET_NULL)
    lock_type = fields.ForeignKeyField("pymush.LockType", related_name='locks', on_delete=fields.RESTRICT)
    value = fields.TextField(null=False)
    userdata = fields.JSONField(null=True)

    class Meta:
        unique_together = (('holder', 'lock_type'),)
