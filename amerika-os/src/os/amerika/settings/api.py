"""Explicit settings API. Never dispatch arbitrary Python names or expose credentials.

The D-Bus interface is intended for applications running as the signed-in user.
Agent mutations still enter through the MCP broker and its risk policy.
"""
import copy
import re
from .. import common
from . import pageindex

RULES = {
    'accent': {'type':'string','pattern':'#[0-9a-fA-F]{6}'},
    'secondary': {'type':'string','pattern':'#[0-9a-fA-F]{6}'},
    'wallpaper': {'type':'string','enum':['horizon','grid','dusk']},
    'dock_size': {'type':'integer','minimum':32,'maximum':96},
    'clock_24h': {'type':'boolean'},
    'copilot_app': {'type':'string','enum':['claude','chatgpt','agent','ask']},
}


def schema():
    return {'version':1,'properties':copy.deepcopy(RULES),'additionalProperties':False,
            'pages':pageindex.pages()}


def validate(key,value):
    if key not in RULES:
        raise ValueError('This setting is not writable through the settings API.')
    rule=RULES[key]
    expected={'string':str,'integer':int,'boolean':bool}[rule['type']]
    if type(value) is not expected:
        raise ValueError(f'{key} must be {rule["type"]}.')
    if 'enum' in rule and value not in rule['enum']:
        raise ValueError(f'Invalid value for {key}.')
    if 'pattern' in rule and re.fullmatch(rule['pattern'],value) is None:
        raise ValueError('Colours must look like #ff2e63.')
    if 'minimum' in rule and not rule['minimum']<=value<=rule['maximum']:
        raise ValueError(f'{key} must be between {rule["minimum"]} and {rule["maximum"]}.')
    return value


def get(key=''):
    settings=common.load_settings()
    if not key:return {k:settings.get(k) for k in RULES}
    if key not in RULES:raise ValueError('Unknown settings API key.')
    return settings.get(key)


def set(key,value):
    validate(key,value)
    settings=common.load_settings();settings[key]=value;common.save_settings(settings)
    return {'ok':True,key:value}
