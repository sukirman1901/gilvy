"""Explicit bridge from reviewed measurements into a reusable product spec.

No vision/tracker runs here. Low-confidence and estimated samples are never
silently promoted to facts. Missing/occluded samples must be resolved upstream.
"""
import copy

from gilvy.errors import GilvyError
from gilvy.product import DEFAULTS, finite, validate


def apply_measured_tracks(spec, report, time_origin=0, *, allow_estimated=False,
                          minimum_confidence=.8):
    """Return (new_spec, provenance). Report has source + tracks, each with
    layer/property/samples[{time,value,status,confidence}]. Times are source
    seconds; subtract time_origin to place them in the film's global clock.
    """
    if (not finite(time_origin) or not finite(minimum_confidence)
        or not 0<=minimum_confidence<=1):
        raise GilvyError('invalid measurement import options')
    if (not isinstance(report,dict) or not isinstance(report.get('source'),str)
        or not report['source'] or not isinstance(report.get('tracks'),list)
        or not report['tracks']):
        raise GilvyError('measurement report requires source and tracks')
    result=copy.deepcopy(spec);nodes={}
    def walk(items):
        for node in items:
            nodes[node['id']]=node
            if node['type']=='group':walk(node['children'])
    validate(result);walk(result['layers']);seen=set();audit=[]
    for track in report['tracks']:
        if not isinstance(track,dict):raise GilvyError('invalid measured track')
        layer=track.get('layer');prop=track.get('property')
        if not isinstance(layer,str) or not isinstance(prop,str):
            raise GilvyError('measurement requires layer/property strings')
        if layer not in nodes or prop not in DEFAULTS or (layer,prop) in seen:
            raise GilvyError('unknown or duplicate measured layer/property')
        seen.add((layer,prop));samples=track.get('samples')
        if not isinstance(samples,list) or not samples:
            raise GilvyError('measurement requires samples')
        keys=[];estimated=0
        for sample in samples:
            if not isinstance(sample,dict):raise GilvyError('invalid measured sample')
            status=sample.get('status');confidence=sample.get('confidence')
            if (status not in ('measured','reviewed','estimated')
                or not finite(confidence) or not minimum_confidence<=confidence<=1
                or (status=='estimated' and not allow_estimated)
                or not finite(sample.get('time')) or not finite(sample.get('value'))):
                raise GilvyError('unresolved, estimated or low-confidence measurement; review before import')
            estimated+=int(status=='estimated')
            keys.append([sample['time']-time_origin,sample['value'],'linear'])
        nodes[layer].setdefault('keyframes',{})[prop]=keys
        audit.append({'layer':layer,'property':prop,'samples':len(keys),'estimated_samples':estimated})
    validate(result)
    return result, {'source':report['source'],'time_origin':time_origin,
                    'minimum_confidence':minimum_confidence,'tracks':audit,
                    'note':'Confidence/status supplied by the reviewer, not independently certified.'}
