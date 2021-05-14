from tortoise.models import Model
from tortoise import fields


class GameObject(Model):
    objid = fields.CharField(max_length=255, unique=True, null=False, blank=False)


class Host(Model):
    address = fields.CharField(max_length=39, null=False, blank=False)
    hostname = fields.TextField(null=True, blank=True)


class LoginAttempt(Model):
    address = fields.ForeignKeyField('core.Host', related_name='logins')
    timestamp = fields.DatetimeField()
    account = fields.ForeignKeyField('core.GameObject', related_name='logins')


class CreateAttempt(Model):
    address = fields.ForeignKeyField('core.Host', related_name='creates')
    timestamp = fields.DatetimeField()


class SiteLock(Model):
    mask = fields.CharField(max_length=39, null=False, blank=False)
    timestamp = fields.DatetimeField()
    creator = fields.ForeignKeyField('core.GameObject', related_name='sitelocks')


