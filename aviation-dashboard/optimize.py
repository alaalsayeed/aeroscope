"""Nested selection of models and thresholds, with group and time outer tests.
Run python3 optimize.py. Standard library only. All folds retain source row IDs.
Exploratory development dataset: no fresh external validation set exists.
"""
import collections
import json
import math
from pathlib import Path
from analyze import fit, predict, metrics, MONTH
from benchmark import sigmoid, solve

ROOT=Path(__file__).parent
SEVERITY={'Normal':0,'Slightly High':1,'High':2,'Very High':3}

def encode_spec(rows,features,ordinal):
    spec=[]
    for f in features:
        if ordinal and f in ['Leakage_Level','Operation_Time']:
            spec.append({'feature':f,'kind':'ordinal','mean':0,'scale':1})
        elif isinstance(rows[0][f],str):
            for v in sorted(set(r[f] for r in rows)):spec.append({'feature':f,'kind':'category','category':v})
        else:
            vals=[r[f] for r in rows];mean=sum(vals)/len(vals)
            std=math.sqrt(sum((v-mean)**2 for v in vals)/len(vals))
            spec.append({'feature':f,'kind':'numeric','mean':mean,'scale':std or 1})
    return spec

def encode(spec,r):
    return [1.]+[float(r[s['feature']]==s['category']) if s['kind']=='category' else SEVERITY[r[s['feature']]] if s['kind']=='ordinal' else (r[s['feature']]-s['mean'])/s['scale'] for s in spec]

def train_model(rows,features,config,regression):
    family=config['family'];name=config['name']
    if family=='tree':return {'family':'tree','name':name,'tree':fit(rows,'Delay_Hours' if regression else 'y',features,not regression,max_depth=config['depth'],min_leaf=config['leaf']),'n':len(rows)}
    spec=encode_spec(rows,features,config.get('ordinal',False));X=[encode(spec,r) for r in rows];n=len(rows);k=len(X[0])
    if family=='ridge':
        y=[r['Delay_Hours'] for r in rows];alpha=config['alpha']
        a=[[sum(x[i]*x[j] for x in X)+(alpha if i==j and i else 0) for j in range(k)] for i in range(k)]
        b=[sum(x[j]*v for x,v in zip(X,y)) for j in range(k)];w=solve(a,b)
    else:
        y=[r['y'] for r in rows];pos=sum(y);balanced=config.get('balanced',False)
        if pos in (0,n):return {'family':'constant','name':name,'value':(pos+1)/(n+2),'n':n}
        w=[0.]*k;w[0]=0. if balanced else math.log((pos+.5)/(n-pos+.5))
        weights=[n/(2*(pos if v else n-pos)) if balanced else 1. for v in y]
        for _ in range(350):
            errors=[(sigmoid(sum(a*b for a,b in zip(w,x)))-v)*q for x,v,q in zip(X,y,weights)]
            grad=[sum(e*x[j] for e,x in zip(errors,X))/n+(.1*w[j] if j else 0) for j in range(k)]
            w=[v-.1*g for v,g in zip(w,grad)]
    return {'family':family,'name':name,'spec':spec,'weights':w,'n':n}

def infer(model,row):
    if model['family']=='tree':return predict(model['tree'],row)[0]
    if model['family']=='constant':return model['value']
    value=sum(a*b for a,b in zip(model['weights'],encode(model['spec'],row)))
    return sigmoid(value) if model['family']=='logistic' else max(0.,value)

def score(actual,prob,regression,threshold=.5):
    if regression:return metrics(actual,prob,False)
    classes=[float(p>=threshold) for p in prob];m=metrics(actual,classes,True)
    m['brier']=sum((a-p)**2 for a,p in zip(actual,prob))/len(actual)
    tp,fp,fn=m['TP'],m['FP'],m['FN']
    m['F1']=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.
    m['F2']=5*tp/(5*tp+4*fn+fp) if 5*tp+4*fn+fp else 0.
    return m

def folds(rows,protocol):
    if protocol=='temporal':
        months=sorted(set(r['Month'] for r in rows),key=MONTH.get)
        for month in months[1:]:yield [i for i,r in enumerate(rows) if MONTH[r['Month']]<MONTH[month]],[i for i,r in enumerate(rows) if r['Month']==month]
    else:
        for aircraft in sorted(set(r['Aircraft_ID'] for r in rows)):
            yield [i for i,r in enumerate(rows) if r['Aircraft_ID']!=aircraft],[i for i,r in enumerate(rows) if r['Aircraft_ID']==aircraft]

def candidates(regression,case):
    configs=[{'family':'tree','name':f'Tree depth {d}, leaf {l}','depth':d,'leaf':l} for d,l in [(1,2),(2,3),(3,2)]]
    if regression:configs += [{'family':'ridge','name':f'Ridge alpha {a}','alpha':a} for a in [.1,1.,10.]]
    elif case!='case3':configs += [
        {'family':'logistic','name':'Logistic L2','balanced':False},
        {'family':'logistic','name':'Balanced logistic L2','balanced':True}]
    if case=='case1':configs.append({'family':'logistic','name':'Ordinal balanced logistic','balanced':True,'ordinal':True})
    return configs

def select(rows,features,configs,regression,case,protocol,cache):
    inner=list(folds(rows,protocol))
    # With only one training month there is no earlier/later inner split;
    # group validation is used solely within that historical training set.
    fallback=not inner
    if fallback:inner=list(folds(rows,'aircraft'))
    if not inner:raise ValueError('Insufficient groups for inner validation')
    ranking=[]
    for config in configs:
        actual=[];prob=[]
        for tr,te in inner:
            training=[rows[i] for i in tr]
            key=(tuple(r['_row'] for r in training),config['name'])
            if key not in cache:cache[key]=train_model(training,features,config,regression)
            model=cache[key]
            for i in te:actual.append(rows[i]['Delay_Hours'] if regression else rows[i]['y']);prob.append(infer(model,rows[i]))
        for threshold in ([.5] if regression else [.2,.35,.5]):
            m=score(actual,prob,regression,threshold)
            objective=-m['MAE_hours'] if regression else m['F2' if case=='case1' else 'F1']
            # Deterministic tie-break: lower Brier; then threshold near 0.5.
            ranking.append((objective,-m.get('brier',0),-abs(threshold-.5),config,threshold,m))
    best=max(ranking,key=lambda x:x[:3])
    return best[3],best[4],best[5],fallback

def run(rows,features,case,regression=False):
    configs=candidates(regression,case);cache={};result={}
    for protocol in ['aircraft','temporal']:
        actual=[];prob=[];classes=[];audit=[];indices=[]
        for tr,te in folds(rows,protocol):
            training=[rows[i] for i in tr]
            config,threshold,inner,fallback=select(training,features,configs,regression,case,protocol,cache)
            model=train_model(training,features,config,regression)
            for i in te:
                p=infer(model,rows[i]);prob.append(p);classes.append(float(p>=threshold));indices.append(rows[i]['_row']);actual.append(rows[i]['Delay_Hours'] if regression else rows[i]['y'])
            audit.append({'train_rows':[rows[i]['_row'] for i in tr],'test_rows':[rows[i]['_row'] for i in te],'model':config['name'],'threshold':threshold,'inner_metrics':inner,'inner_group_fallback':fallback})
        m=metrics(actual,prob,False) if regression else score(actual,classes,False)
        if not regression:m['brier']=sum((a-p)**2 for a,p in zip(actual,prob))/len(actual)
        result[protocol]={'metrics':m,'n':len(actual),'actual':actual,'predictions':prob,'predicted_classes':None if regression else classes,'row_indices':indices,'fold_audit':audit}
        print(case,'duration' if regression else 'classification',protocol,json.dumps(m),flush=True)
    config,threshold,inner,fallback=select(rows,features,configs,regression,case,'temporal',cache)
    model=train_model(rows,features,config,regression)
    result.update(final_model=model,final_config=config,threshold=threshold,features=features,selection_inner_metrics=inner,
                  candidates=configs,selection_objective='MAE' if regression else 'F2' if case=='case1' else 'F1')
    return result

def main():
    data=json.loads((ROOT/'dist/results.json').read_text());out={}
    for case in ['case1','case2','case3']:
        rows=data[case]['rows']
        for i,r in enumerate(rows):r['_row']=i
        features=data[case]['model']['features'] if case!='case3' else ['Tool_ID','Tool_Status','Maintenance_Station']
        out[case]=run(rows,features,case)
    out['case2_duration']=run(data['case2']['rows'],data['case2']['model']['features'],'case2',True)
    out['notes']=[
        'Nested validation: model family, parameters and classification threshold selected using only inner training folds. Outer test records are never used for selection.',
        'Primary objective: F2 for actuator failure detection, F1 for job delay and belt defects, MAE for delay duration. Classification thresholds searched: 0.2, 0.35, 0.5.',
        'The final full-data model is selected by inner expanding-month validation; its training-set results are not the reported outer-validation scores. Outer models can differ by fold.',
        'Research development reused this small dataset across prior experiments. Nested scores remain internal estimates; an independent later dataset is required to confirm gains.',
        'Ordinal severity mapping uses supplied labels Normal=0, Slightly High=1, High=2, Very High=3; it assumes increasing severity and uses no outcome values.',
        'Months have no year or exact cutoff timestamp. The 30-day outcome maturity gap cannot be verified; expanding-month validation is provisional.',
        'Task 3 prediction excludes belt condition, temperature and vibration. Tool identity and calibration remain confounded; predictive success cannot identify a causal effect.',
        'No additional real observations were available or invented.'
    ]
    (ROOT/'dist/final-results.json').write_text(json.dumps(out,indent=2))
    (ROOT/'dist/final-data.js').write_text('window.FINAL_RESULTS = '+json.dumps(out)+';\n')
    print('SAVED final-results.json',flush=True)

if __name__=='__main__':main()
