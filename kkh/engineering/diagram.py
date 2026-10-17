"""Read-only diagram export through OMC's supported JSON model-instance API.

Read the raw scripting response twice with JSON, avoiding OMPython's generic
string unescaper (which corrupts quoted modifier values inside this JSON).
No source-regex reconstruction of graphical annotations is used here.
"""
from __future__ import annotations
import json


def layers(model, name):
    graphics=[]
    for element in model.get('elements',[]):
        if element.get('$kind')=='extends' and isinstance(element.get('baseClass'),dict):
            graphics.extend(layers(element['baseClass'],name).get('graphics',[]))
    annotation=model.get('annotation',{}).get(name,{})
    graphics.extend(annotation.get('graphics',[]))
    return {**annotation,'graphics':graphics}


def reference(value):
    if isinstance(value,str):return value
    return '.'.join(p['name']+('['+','.join(str(s) for s in p['subscripts'])+']' if p.get('subscripts') else '')
                    for p in value.get('parts',[]))


def normalize(model):
    components=[]
    def collect(elements):
        for element in elements:
            if element.get('$kind')=='extends':
                base=element.get('baseClass')
                if isinstance(base,dict):collect(base.get('elements',[]))
            if element.get('$kind')!='component' or element.get('generated'):continue
            t=element.get('type',{})
            placement=element.get('annotation',{}).get('Placement',{})
            if not placement:continue
            components.append({'name':element['name'],'type':t.get('name') if isinstance(t,dict) else t,
                'comment':element.get('comment',''),'placement':placement,'icon':layers(t,'Icon') if isinstance(t,dict) else {},
                'modifiers':element.get('modifiers',{}),'source':element.get('source',{}),
                'restriction':t.get('restriction') if isinstance(t,dict) else None})
    collect(model.get('elements',[]))
    return {'class_name':model['name'],'diagram':layers(model,'Diagram'),'icon':layers(model,'Icon'),
            'components':components,'connections':[{'from':reference(c['lhs']),'to':reference(c['rhs']),
               'annotation':c.get('annotation',{})} for c in model.get('connections',[])],
            'source':model.get('source',{}),'method':'OpenModelica getModelInstance JSON',
            'editable':False,'reference':'Native OMEdit is the graphical engineering reference',
            'limitations':['Read-only preview; not a Modelica graphical editor.',
                'Static Rectangle, Ellipse, Polygon, Line and Text primitives are supported. Dynamic graphics, bitmaps, gradients and conditional visibility may be simplified or omitted.',
                'Connections without a Line annotation are listed, not invented as routed native paths.']}


def export(omc, class_name):
    raw=omc.session.sendExpression(f'getModelInstance({class_name})',parsed=False)
    model=json.loads(json.loads(raw))
    if not isinstance(model,dict) or not model.get('name'):
        raise ValueError('OpenModelica could not instantiate this class for diagram export: '+omc.errors())
    return {**normalize(model),'openmodelica_version':omc.version()}
