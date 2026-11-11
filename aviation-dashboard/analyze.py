"""Reproducible, dependency-free analyses of the supplied hackathon workbook.
Run: python3 analyze.py [path/to/Cases Data.xlsx]
Small depth-two CART baselines; no external services or invented observations.
"""
import collections
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import zipfile

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
MONTH = {'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4}

def read_book(path):
    with zipfile.ZipFile(path) as z:
        strings = [''.join(s.itertext()) for s in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si', NS)]
        sheets = []
        for number in (2, 4, 6):
            rows = []
            for row in ET.fromstring(z.read(f'xl/worksheets/sheet{number}.xml')).findall('m:sheetData/m:row', NS):
                cells = {}
                for c in row.findall('m:c', NS):
                    v = c.find('m:v', NS)
                    if v is None: continue
                    val = strings[int(v.text)] if c.get('t') == 's' else float(v.text)
                    cells[''.join(x for x in c.get('r') if x.isalpha())] = val
                if cells: rows.append(cells)
            headers = rows[0]
            sheets.append([{headers[k]: row.get(k) for k in headers} for row in rows[1:]])
        return sheets

def loss(values):
    mean = sum(values) / len(values)
    return sum((v - mean) ** 2 for v in values)

def fit(rows, target, features, classification=True, depth=0, max_depth=2, min_leaf=3):
    ys = [float(r[target]) for r in rows]
    node = {'value': (sum(ys)+1)/(len(ys)+2) if classification else sum(ys)/len(ys), 'n': len(rows)}
    if depth == max_depth or len(rows) < 2*min_leaf or len(set(ys)) == 1: return node
    best = None
    for f in features:
        vals = sorted(set(r[f] for r in rows))
        categorical = isinstance(vals[0], str)
        thresholds = vals if categorical else [(a+b)/2 for a,b in zip(vals,vals[1:])]
        for t in thresholds:
            left = [r for r in rows if (r[f] == t if categorical else r[f] <= t)]
            right = [r for r in rows if r not in left]
            if min(len(left),len(right)) < min_leaf: continue
            score = loss([r[target] for r in left]) + loss([r[target] for r in right])
            if best is None or score < best[0]: best = (score,f,t,categorical,left,right)
    if best and best[0] < loss(ys)-1e-10:
        _, f,t,cat,left,right = best
        node.update(feature=f, threshold=t, categorical=cat,
                    left=fit(left,target,features,classification,depth+1,max_depth,min_leaf),
                    right=fit(right,target,features,classification,depth+1,max_depth,min_leaf))
    return node

def predict(tree, row):
    path=[]
    while 'feature' in tree:
        f,t,cat=tree['feature'],tree['threshold'],tree['categorical']
        left = row[f] == t if cat else row[f] <= t
        op = ('=' if left else '≠') if cat else ('≤' if left else '>')
        path.append(f'{f.replace("_"," ")} {op} {t}')
        tree=tree['left' if left else 'right']
    return tree['value'], ' · '.join(path) or 'Training-set baseline', tree['n']

def metrics(actual,pred,classification):
    if not classification: return {'MAE_hours':sum(abs(a-p) for a,p in zip(actual,pred))/len(actual)}
    tp=sum(a==1 and p>=.5 for a,p in zip(actual,pred)); fn=sum(a==1 and p<.5 for a,p in zip(actual,pred))
    fp=sum(a==0 and p>=.5 for a,p in zip(actual,pred)); tn=len(actual)-tp-fn-fp
    return {'accuracy':(tp+tn)/len(actual),'recall':tp/(tp+fn) if tp+fn else None,
            'precision':tp/(tp+fp) if tp+fp else None,'brier':sum((a-p)**2 for a,p in zip(actual,pred))/len(actual),
            'TP':tp,'FN':fn,'FP':fp,'TN':tn}

def model(rows,target,features,classification=True):
    tree=fit(rows,target,features,classification)
    preds=[]; base=[]; explanations=[]
    for row in rows:
        train=[r for r in rows if r['Aircraft_ID'] != row['Aircraft_ID']]
        assert all(r['Aircraft_ID'] != row['Aircraft_ID'] for r in train)
        p,why,n=predict(fit(train,target,features,classification),row)
        preds.append(p); explanations.append(why)
        base.append(sum(r[target] for r in train)/len(train))
    chronological=[]; truth=[]
    for month in sorted(set(r['Month'] for r in rows), key=MONTH.get)[1:]:
        train=[r for r in rows if MONTH[r['Month']]<MONTH[month]]
        test=[r for r in rows if r['Month']==month]
        t=fit(train,target,features,classification)
        chronological.extend(predict(t,r)[0] for r in test); truth.extend(r[target] for r in test)
    return {'tree':tree,'features':features,'validation':metrics([r[target] for r in rows],preds,classification),
            'baseline':metrics([r[target] for r in rows],base,classification),
            'temporal':metrics(truth,chronological,classification),'temporal_n':len(truth),
            'oof':preds,'explanations':explanations}

def groups(rows, key):
    out=[]
    for value in sorted(set(r[key] for r in rows)):
        subset=[r for r in rows if r[key]==value]; n=len(subset); k=sum(r['y'] for r in subset)
        p=k/n; z=1.96; center=(p+z*z/(2*n))/(1+z*z/n)
        delta=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
        out.append({'name':value,'n':n,'defects':k,'rate':p,'low':center-delta,'high':center+delta})
    return out

def main():
    src=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).parent.parent/'Cases Data.xlsx'
    c1,c2,c3=read_book(src)
    for rows,target in [(c1,'Failure_Next_30_Days'),(c2,'Maintenance_Delay'),(c3,'Belt_Defect')]:
        assert all(all(v is not None for v in r.values()) for r in rows)
        for r in rows: r['y']=int(r[target]=='Yes')
    f1=['Flight_Hours','Flight_Cycles','Actuator_Age_Months','Previous_Failures','Maintenance_Events','Leakage_Level','Operation_Time']
    m1=model(c1,'y',f1)
    f2=['Maintenance_Type','Planned_Transport_Time','Part_Available','Technician_Available','Tool_Available']
    m2=model(c2,'y',f2); duration=model(c2,'Delay_Hours',f2,False)
    for r in c2:r['Transport_Overrun_Minutes']=max(0,r['Transport_Time']-r['Planned_Transport_Time'])
    post=model(c2,'y',['Transport_Overrun_Minutes']); post_duration=model(c2,'Delay_Hours',['Transport_Overrun_Minutes'],False)
    for i,r in enumerate(c1):
        p,why,n=predict(m1['tree'],r)
        r.update(probability=p,risk='High' if p>=.5 else 'Medium' if p>=.2 else 'Low', explanation=why,support=n,held_out_probability=m1['oof'][i])
    for i,r in enumerate(c2):
        p,why,n=predict(m2['tree'],r); hours=predict(duration['tree'],r)[0]
        r.update(probability=p,predicted_hours=hours,explanation=why,support=n,held_out_probability=m2['oof'][i],held_out_hours=duration['oof'][i],
                 observed_driver='Transport overrun' if r['Transport_Overrun_Minutes']>0 else 'No recorded constraint')
    # Fisher exact two-sided for calibration x defect. Explicitly descriptive, not causal.
    n=len(c3); positive=sum(r['y'] for r in c3); exposed=sum(r['Tool_Status']=='Needs Calibration' for r in c3)
    a=sum(r['y'] for r in c3 if r['Tool_Status']=='Needs Calibration')
    def hyper(x): return math.comb(positive,x)*math.comb(n-positive,exposed-x)/math.comb(n,exposed)
    observed=hyper(a)
    fisher=sum(hyper(x) for x in range(max(0,exposed-(n-positive)),min(positive,exposed)+1) if hyper(x)<=observed+1e-15)
    result={'source':src.name,'case1':{'rows':c1,'model':m1},'case2':{'rows':c2,'model':m2,'duration':duration,'retrospective':post,'retrospective_duration':post_duration},
            'case3':{'rows':c3,'tools':groups(c3,'Tool_ID'),'calibration':groups(c3,'Tool_Status'),'stations':groups(c3,'Maintenance_Station'),'fisher_p':fisher},
            'methodology':{'validation':'Leave-one-aircraft-out; no aircraft ID used as a feature. Secondary expanding-month evaluation assumes Jan–Apr are chronological within one unspecified year.',
                           'model':'CART depth ≤ 2, minimum leaf size 3; squared-error split criterion; binary leaf probabilities use Laplace smoothing. No tuning on validation results.',
                           'risk':'Illustrative bands: Low <20%, Medium 20–<50%, High ≥50%. Probabilities are uncalibrated; bands require operational validation.',
                           'scope':'Hackathon prototype from 96 supplied records. Associations are not causal evidence and model outputs are not validated maintenance instructions.'}}
    dest=Path(__file__).parent/'dist'; dest.mkdir(exist_ok=True)
    (dest/'data.js').write_text('window.DATA = '+json.dumps(result,indent=2)+';\n')
    (dest/'results.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({'case1':m1['validation'],'case2':m2['validation'],'delay':duration['validation'],'retrospective':post['validation'],'fisher_p':fisher},indent=2))

if __name__=='__main__':main()
