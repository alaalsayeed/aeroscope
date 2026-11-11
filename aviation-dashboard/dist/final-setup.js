// Connect nested-validation results and selected deployable models to the dashboard.
if(window.FINAL_RESULTS){
  const f=window.FINAL_RESULTS,d=window.DATA;
  function attach(result,old){
    const model=result.final_model;
    const oof=Array(result.aircraft.n);
    result.aircraft.row_indices.forEach((index,i)=>{oof[index]=result.aircraft.predictions[i]});
    return {...old,tree:model.family==='tree'?model.tree:model,features:result.features,
      validation:result.aircraft.metrics,temporal:result.temporal.metrics,temporal_n:result.temporal.n,
      oof,threshold:result.threshold,selected_name:model.name};
  }
  d.case1.model=attach(f.case1,d.case1.model);
  d.case2.model=attach(f.case2,d.case2.model);
  d.case2.duration=attach(f.case2_duration,d.case2.duration);
  d.optimization=f;
  d.methodology.model='Nested model and threshold selection: trees, logistic alternatives, ordinal severity encoding, and ridge duration regression. All scaling and encoders fitted within training folds.';
  d.methodology.validation='Outer leave-one-aircraft-out and expanding-month validation. Inner folds choose models, parameters and thresholds. A one-month training window uses inner aircraft folds. Scores remain internal estimates on a previously explored dataset.';
}
