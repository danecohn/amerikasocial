"""MPRIS media controls through the optional playerctl client."""
import subprocess
from .. import sysutil

ACTIONS={'play-pause':'play-pause','next':'next','previous':'previous','stop':'stop'}


def control(action):
    if action not in ACTIONS:raise ValueError('Unknown media action.')
    return sysutil.run(['playerctl',ACTIONS[action]],timeout=3).code==0


def current():
    if not sysutil.have('playerctl'):return None
    result=sysutil.run(['playerctl','metadata','--format','{{artist}}\n{{title}}\n{{playerName}}'],timeout=3)
    if result.code:return None
    fields=result.out.splitlines()+['','','']
    return {'artist':fields[0],'title':fields[1],'player':fields[2]}
