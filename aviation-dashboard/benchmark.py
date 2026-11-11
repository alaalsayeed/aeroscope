"""Exploratory fixed-specification alternatives. Does not replace dashboard models.
All encoders, scaling and model fitting use training folds only. No dependencies.
Run python3 benchmark.py. Results need confirmation on fresh aircraft/time periods.
"""
import json
import math
from pathlib import Path
from analyze import fit, predict, metrics, MONTH

ROOT=Path(__file__).parent

def sigmoid(x):return 1/(1+math.exp(-max(-35,min(35,x))))

def encoder(rows,features):
    spec=[]
    for f in features:
        if isinstance(rows[0][f],str):
            spec.extend((f,'cat',v,1) for v in sorted(set(r[f] for r in rows)))
        else:
            vals=[r[f] for r in rows];mean=sum(vals)/len(vals)
            std=math.sqrt(sum((v-mean)**2 for v in vals)/len(vals))
            spec.append((f,'num',mean,std or 1))
    def encode(r):return [1.]+[float(r[f]==a) if t=='cat' else (r[f]-a)/b for f,t,a,b in spec]
    return encode

def logistic(train,features,balanced=False):
    encode=encoder(train,features);X=[encode(r) for r in train];y=[r['y'] for r in train];n=len(y)
    pos=sum(y);w=[0.]*len(X[0]);w[0]=math.log((pos+.5)/(n-pos+.5)) if not balanced else 0.
    weights=[n/(2*(pos if v else n-pos)) if balanced and 0<pos<n else 1. for v in y]
    # Minimize weighted average log loss + 0.1/2 * squared coefficients.
    for _ in range(400):
        errors=[(sigmoid(sum(a*b for a,b in zip(w,x)))-v)*q for x,v,q in zip(X,y,weights)]
        grad=[sum(e*x[j] for e,x in zip(errors,X))/n+(.1*w[j] if j else 0) for j in range(len(w))]
        w=[v-.1*g for v,g in zip(w,grad)]
    return lambda row:sigmoid(sum(a*b for a,b in zip(w,encode(row))))

def naive_bayes(train,features):
    classes=[]
    for y in [0,1]:
        sub=[r for r in train if r['y']==y];params=[]
        for f in features:
            if isinstance(train[0][f],str):
                cats=set(r[f] for r in train)
                params.append((f,'cat',{v:(sum(r[f]==v for r in sub)+1)/(len(sub)+len(cats)+1) for v in cats},1/(len(sub)+len(cats)+1)))
            else:
                vals=[r[f] for r in sub] or [r[f] for r in train]
                mean=sum(vals)/len(vals);global_mean=sum(r[f] for r in train)/len(train)
                global_var=sum((r[f]-global_mean)**2 for r in train)/len(train)
                var=max(sum((v-mean)**2 for v in vals)/len(vals),.1*global_var,1e-6)
                params.append((f,'num',mean,var))
        classes.append((math.log((len(sub)+1)/(len(train)+2)),params))
    def infer(row):
        scores=[]
        for prior,params in classes:
            score=prior
            for f,t,a,b in params:
                score+=math.log(a.get(row[f],b)) if t=='cat' else -.5*(math.log(2*math.pi*b)+(row[f]-a)**2/b)
            scores.append(score)
        return sigmoid(scores[1]-scores[0])
    return infer

def solve(a,b):
    m=[list(row)+[v] for row,v in zip(a,b)];n=len(b)
    for j in range(n):
        k=max(range(j,n),key=lambda i:abs(m[i][j]));m[j],m[k]=m[k],m[j]
        scale=m[j][j];assert abs(scale)>1e-12
        m[j]=[v/scale for v in m[j]]
        for i in range(n):
            if i!=j:
                f=m[i][j];m[i]=[a-f*b for a,b in zip(m[i],m[j])]
    return [r[-1] for r in m]

def ridge(train,features):
    encode=encoder(train,features);X=[encode(r) for r in train];y=[r['Delay_Hours'] for r in train];k=len(X[0])
    a=[[sum(x[i]*x[j] for x in X)+(1. if i==j and i else 0) for j in range(k)] for i in range(k)]
    b=[sum(x[j]*v for x,v in zip(X,y)) for j in range(k)];w=solve(a,b)
    return lambda r:max(0.,sum(a*b for a,b in zip(w,encode(r))))

def learner(name,train,features,regression=False):
    if name=='Current tree':
        t=fit(train,'Delay_Hours' if regression else 'y',features,not regression)
        return lambda r:predict(t,r)[0]
    if name=='Logistic L2':return logistic(train,features)
    if name=='Balanced logistic L2':return logistic(train,features,True)
    if name=='Naive Bayes':return naive_bayes(train,features)
    if name=='Ridge':return ridge(train,features)
    raise ValueError(name)

def splits(rows,temporal):
    if temporal:
        for month in sorted(set(r['Month'] for r in rows),key=MONTH.get)[1:]:
            yield [i for i,r in enumerate(rows) if MONTH[r['Month']]<MONTH[month]],[i for i,r in enumerate(rows) if r['Month']==month]
    else:
        for aircraft in sorted(set(r['Aircraft_ID'] for r in rows)):
            yield [i for i,r in enumerate(rows) if r['Aircraft_ID']!=aircraft],[i for i,r in enumerate(rows) if r['Aircraft_ID']==aircraft]

def evaluate(rows,features,name,regression=False,temporal=False):
    actual=[];preds=[];ids=[]
    for train_idx,test_idx in splits(rows,temporal):
        train=[rows[i] for i in train_idx];infer=learner(name,train,features,regression)
        for i in test_idx:
            r=rows[i];p=infer(r);assert math.isfinite(p)
            if not regression:assert 0<=p<=1
            actual.append(r['Delay_Hours'] if regression else r['y']);preds.append(p);ids.append(i)
    out=metrics(actual,preds,not regression);out['n']=len(actual)
    if not regression:
        tp,fp,fn=out['TP'],out['FP'],out['FN'];out['F1']=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.
    return {'metrics':out,'row_indices':ids,'predictions':preds,'actual':actual}

def main():
    d=json.loads((ROOT/'dist/results.json').read_text());out={}
    for case in ['case1','case2']:
        rows=d[case]['rows'];features=d[case]['model']['features'];out[case]={}
        for name in ['Current tree','Logistic L2','Balanced logistic L2','Naive Bayes']:
            out[case][name]={mode:evaluate(rows,features,name,temporal=mode=='temporal') for mode in ['aircraft','temporal']}
    out['case2_duration']={}
    for name in ['Current tree','Ridge']:
        out['case2_duration'][name]={mode:evaluate(d['case2']['rows'],d['case2']['model']['features'],name,True,mode=='temporal') for mode in ['aircraft','temporal']}
    out['notes']=[
        'Exploratory comparison: model choices are not validated by an untouched test set. No automatic dashboard replacement.',
        'Model specifications fixed before running this benchmark. No threshold optimization. All classifiers use threshold 0.5.',
        'One-hot category encoders and numeric standardization fitted within each training fold. Logistic L2 penalty=0.1; ridge penalty=1; Naive Bayes variance floor=10% of within-fold global variance.',
        'Month-based validation assumes one unspecified year. Exact timestamps are absent, so 30-day label maturity and observation cutoff cannot be verified.',
        'Task 3 is a causal-identification/data-collection problem; changing the classifier cannot separate tool identity from calibration.'
    ]
    (ROOT/'benchmark-results.json').write_text(json.dumps(out,indent=2))
    for case in ['case1','case2','case2_duration']:
        print(case)
        for name,r in out[case].items():print(name,json.dumps({k:v['metrics'] for k,v in r.items()}))

if __name__=='__main__':main()
